"""Official REST APIs through google-auth AuthorizedSession; injectable transport for tests."""
import random
import time
from urllib.parse import quote
from google.auth.transport.requests import AuthorizedSession
from .storage import Cache

GSC = 'https://www.googleapis.com/webmasters/v3'
GA = 'https://analyticsdata.googleapis.com/v1beta'
ADMIN = 'https://analyticsadmin.googleapis.com/v1beta'
GA_METRICS = ['sessions', 'activeUsers', 'newUsers', 'engagedSessions', 'engagementRate',
              'keyEvents', 'sessionKeyEventRate', 'totalRevenue', 'screenPageViews']


class APIError(Exception):
    pass


class Google:
    def __init__(self, credentials=None, account='test', cache=None, session=None, sleep=time.sleep):
        self.session = session or AuthorizedSession(credentials)
        self.account = account
        self.cache = cache or Cache()
        self.sleep = sleep

    def request(self, method, url, body=None):
        for attempt in range(5):
            try:
                r = self.session.request(method, url, json=body, timeout=45)
            except Exception:
                if attempt == 4:
                    raise APIError('Network request failed; cached data remains available.') from None
                self.sleep(min(2**attempt + random.random(), 20))
                continue
            if r.status_code < 400:
                return r.json()
            retry = r.status_code in (429, 500, 502, 503, 504)
            if r.status_code == 403:
                retry = any(x in r.text for x in ('rateLimitExceeded', 'userRateLimitExceeded', 'quotaExceeded'))
            if retry and attempt < 4:
                try:
                    delay = min(float(r.headers.get('Retry-After', 2**attempt)), 30)
                except ValueError:
                    delay = 2**attempt
                self.sleep(delay)
                continue
            messages = {401: 'Authorization expired. Reconnect Google.',
                        403: 'Access denied or quota exhausted. Check property permission and enabled APIs.',
                        400: 'Google rejected the report. Check metric compatibility, dates and filters.',
                        429: 'Google quota exhausted. Try again later.'}
            raise APIError(messages.get(r.status_code, f'Google API failed (HTTP {r.status_code}).'))

    def cached(self, name, payload, loader, refresh=False):
        key = self.cache.key(self.account, name, payload)
        hit = self.cache.get(key)
        if hit and not refresh:
            return {**hit[0], 'synced_at': hit[1], 'cached': True}
        try:
            value = loader()
            self.cache.put(key, value)
            return {**value, 'synced_at': time.time(), 'cached': False}
        except APIError as e:
            hit = self.cache.get(key, stale=True)
            if hit:
                return {**hit[0], 'synced_at': hit[1], 'cached': True, 'stale_error': str(e)}
            raise

    def sites(self):
        return self.request('GET', GSC + '/sites').get('siteEntry', [])

    def properties(self):
        result, token = [], None
        while True:
            url = ADMIN + '/accountSummaries?pageSize=200'
            if token:
                url += '&pageToken=' + quote(token, safe='')
            data = self.request('GET', url)
            for account in data.get('accountSummaries', []):
                result.extend(account.get('propertySummaries', []))
            token = data.get('nextPageToken')
            if not token:
                return result

    def key_events(self, prop):
        rows, token = [], None
        while True:
            url = f'{ADMIN}/{prop}/keyEvents?pageSize=200'
            if token:
                url += '&pageToken=' + quote(token, safe='')
            result = self.request('GET', url)
            rows.extend(result.get('keyEvents', []))
            token = result.get('nextPageToken')
            if not token:
                return rows

    def gsc(self, site, start, end, dimensions, filters=None, search_type='web', final=True, refresh=False, page_size=25000):
        body = {'startDate': str(start), 'endDate': str(end), 'dimensions': dimensions,
                'type': search_type, 'dataState': 'final' if final else 'all', 'rowLimit': page_size}
        if filters:
            body['dimensionFilterGroups'] = [{'filters': filters}]

        def load():
            rows, offset = [], 0
            while True:
                data = self.request('POST', f'{GSC}/sites/{quote(site, safe="")}/searchAnalytics/query', {**body, 'startRow': offset})
                batch = data.get('rows', [])
                rows.extend(dict(zip(dimensions, r.get('keys', [])), **{k: r[k] for k in ('clicks','impressions','ctr','position')}) for r in batch)
                if len(batch) < page_size:
                    break
                offset += len(batch)
                if offset >= 1000000:
                    raise APIError('Pagination safety limit reached; narrow the date range.')
            return {'rows': rows, 'source': 'GSC', 'partial': True,
                    'notice': 'Top rows only; anonymized queries and Google API limits prevent complete query coverage. Finalized data.' if final else 'Recent data may be incomplete; top-row and privacy limits apply.'}
        return self.cached('gsc', [site, body], load, refresh)

    def ga(self, prop, start, end, dimensions, filters=None, google_only=False, refresh=False, metrics=None, page_size=100000):
        metrics = metrics or GA_METRICS
        clauses = [{'filter': {'fieldName': 'sessionDefaultChannelGroup', 'stringFilter': {'value': 'Organic Search', 'matchType': 'EXACT'}}}]
        if google_only:
            clauses.append({'filter': {'fieldName': 'sessionSourceMedium', 'stringFilter': {'value': 'google / organic', 'matchType': 'EXACT'}}})
        clauses.extend(filters or [])
        body = {'dateRanges': [{'startDate': str(start), 'endDate': str(end)}],
                'dimensions': [{'name': x} for x in dimensions], 'metrics': [{'name': x} for x in metrics],
                'dimensionFilter': {'andGroup': {'expressions': clauses}}, 'limit': str(page_size), 'returnPropertyQuota': True}

        def load():
            meta = self.request('GET', f'{GA}/{prop}/metadata')
            available = {m['apiName'] for m in meta.get('metrics', [])}
            selected = [m for m in metrics if m in available]
            if not selected:
                raise APIError('Requested GA4 metrics are unavailable.')
            request = {**body, 'metrics': [{'name': m} for m in selected]}
            self.request('POST', f'{GA}/{prop}:checkCompatibility',
                         {k: request[k] for k in ('dimensions','metrics','dimensionFilter')})
            rows, offset, metadata, quota = [], 0, {}, {}
            while True:
                data = self.request('POST', f'{GA}/{prop}:runReport', {**request, 'offset': str(offset)})
                batch = data.get('rows', [])
                for row in batch:
                    out = dict(zip(dimensions, [v.get('value','') for v in row.get('dimensionValues', [])]))
                    out.update(zip(selected, [float(v['value']) for v in row.get('metricValues', [])]))
                    rows.append(out)
                metadata = data.get('metadata', {})
                quota = data.get('propertyQuota', {})
                offset += len(batch)
                if offset >= data.get('rowCount', 0):
                    break
                if not batch:
                    raise APIError('GA4 pagination ended early; report was not cached.')
            return {'rows': rows, 'source': 'GA4', 'metadata': metadata, 'quota': quota,
                    'missing_metrics': sorted(set(metrics)-set(selected))}
        return self.cached('ga', [prop, body], load, refresh)

    def sitemaps(self, site):
        return self.request('GET', f'{GSC}/sites/{quote(site, safe="")}/sitemaps').get('sitemap', [])

    def inspect(self, site, url):
        return self.request('POST', 'https://searchconsole.googleapis.com/v1/urlInspection/index:inspect',
                            {'siteUrl': site, 'inspectionUrl': url})
