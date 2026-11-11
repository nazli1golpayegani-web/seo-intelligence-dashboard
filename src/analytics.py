"""Source-aware deterministic analysis. No causal or query-conversion attribution."""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import numpy as np
import pandas as pd

GSC_METRICS = ['clicks', 'impressions', 'ctr', 'position']


def frame(report, columns=()):
    return pd.DataFrame(report.get('rows', [])) if report.get('rows') else pd.DataFrame(columns=list(columns))


def totals(df):
    if df.empty:
        return {x: None for x in GSC_METRICS}
    c, i = df.clicks.sum(min_count=1), df.impressions.sum(min_count=1)
    return {'clicks': c, 'impressions': i, 'ctr': c/i if i > 0 else None,
            'position': (df.position * df.impressions).sum(min_count=1)/i if i > 0 else None}


def aggregate(df, dimensions):
    if df.empty:
        return pd.DataFrame(columns=list(dimensions)+GSC_METRICS)
    data = df.assign(weighted_position=df.position*df.impressions)
    result = data.groupby(dimensions, dropna=False, as_index=False).agg(
        clicks=('clicks','sum'), impressions=('impressions','sum'), weighted_position=('weighted_position','sum'))
    result['ctr'] = result.clicks.div(result.impressions.replace(0,np.nan))
    result['position'] = result.weighted_position.div(result.impressions.replace(0,np.nan))
    return result.drop(columns='weighted_position')


def change(current, previous):
    if previous is None or pd.isna(previous) or previous == 0 or current is None:
        return None
    return (current-previous)/previous


def compare(current, previous, key):
    a, b = current.copy(), previous.copy()
    for df in (a,b):
        if key not in df:
            df[key] = pd.Series(dtype=str)
    out = a.merge(b, on=key, how='outer', suffixes=('', '_previous'))
    # Missing API rows are unknown, not evidence of zero traffic.
    for metric in ('clicks','impressions','position','sessions','keyEvents'):
        if metric in out and metric+'_previous' in out:
            out[metric+'_change'] = out[metric] - out[metric+'_previous']
            out[metric+'_change_pct'] = out[metric+'_change']/out[metric+'_previous'].replace(0,np.nan)
    return out


@dataclass
class URLRules:
    remove_tracking: bool = True
    strip_slash: bool = False
    ignore_protocol: bool = False
    lowercase_path: bool = False


def normalize_url(url, rules=None):
    rules = rules or URLRules()
    u = urlsplit(str(url))
    path = u.path or '/'
    if rules.strip_slash and path != '/':
        path = path.rstrip('/')
    if rules.lowercase_path:
        path = path.lower()
    query = u.query
    if rules.remove_tracking:
        # Preserve non-tracking query ordering/duplicates; do not sort or unquote paths.
        query = '&'.join(part for part in query.split('&') if not re.match(r'(?i)(utm_[^=]*|gclid|fbclid|msclkid)=', part))
    scheme = 'https' if rules.ignore_protocol and u.netloc else u.scheme.lower()
    return urlunsplit((scheme, u.netloc.lower(), path, query, ''))


def match_pages(gsc, ga, origin, rules=None):
    if gsc.empty:
        return gsc.copy(), None
    a = gsc.copy()
    a['match_key'] = a.page.map(lambda u: normalize_url(u, rules))
    if ga.empty:
        a['match_status'] = 'Unmatched'
        return a, 0.0
    b = ga.copy()
    # hostname is required: a GA4 property can span multiple domains.
    if 'hostName' not in b or 'landingPagePlusQueryString' not in b:
        a['match_status'] = 'Unmatched: hostname unavailable'
        return a, 0.0
    scheme = urlsplit(origin).scheme or 'https'
    b['match_key'] = [normalize_url(f'{scheme}://{host}{path}',rules) if str(path).startswith('/') else None
                      for host,path in zip(b.hostName,b.landingPagePlusQueryString)]
    # Never inflate metrics by many-to-many joins after normalization.
    ambiguous = set(a.loc[a.match_key.duplicated(False),'match_key']) | set(b.loc[b.match_key.duplicated(False),'match_key'])
    b = b[~b.match_key.isin(ambiguous) & b.match_key.notna()]
    out = a.merge(b, on='match_key', how='left', validate='many_to_one', indicator=True)
    out['match_status'] = out['_merge'].map({'both':'Matched','left_only':'Unmatched','right_only':'Unmatched'}).astype(str)
    out.loc[out.match_key.isin(ambiguous), 'match_status'] = 'Ambiguous: review URL rules'
    out = out.drop(columns='_merge')
    return out, float((out.match_status=='Matched').mean())


def brand_filter(df, pattern, mode):
    if mode == 'All' or not pattern or df.empty or 'query' not in df:
        return df
    hit = df['query'].str.contains(pattern, case=False, regex=True, na=False)
    return df[hit if mode == 'Brand' else ~hit]


def opportunities(df, minimum=100, lower=4, upper=20, weights=(.45,.35,.20)):
    columns = ['title','target','observation','possible_explanation','action','priority','confidence','limitations','effort','score']
    if df.empty:
        return pd.DataFrame(columns=columns)
    data = df[df.impressions >= minimum].copy()
    if data.empty:
        return pd.DataFrame(columns=columns)
    data['bucket'] = pd.cut(data.position,[0,3,5,10,20,1000])
    benchmarks = data.groupby('bucket',observed=True).agg(clicks=('clicks','sum'),impressions=('impressions','sum'),n=('clicks','size'))
    maximum = max(data.impressions.max(),1)
    output = []
    for _,r in data.iterrows():
        target = r.get('query',r.get('page','Unknown'))
        benchmark = benchmarks.loc[r.bucket] if pd.notna(r.bucket) else None
        expected = benchmark.clicks/benchmark.impressions if benchmark is not None and benchmark.n >= 5 else None
        gap = max(0,(expected-r.ctr)/expected) if expected else 0
        rank = float(lower <= r.position <= upper)
        score = 100*(weights[0]*np.log1p(r.impressions)/np.log1p(maximum) + weights[1]*gap + weights[2]*rank)/sum(weights)
        kind = 'CTR optimization' if gap > .25 else 'Ranking investigation' if rank else None
        if kind:
            output.append(dict(title=kind,target=target,
                observation=f'GSC: {r.impressions:,.0f} impressions, {r.clicks:,.0f} clicks, CTR {r.ctr:.2%}, position {r.position:.1f}.',
                possible_explanation='Snippet or intent mismatch is a hypothesis.' if gap>.25 else 'Average visibility is within the configured ranking window.',
                action='Review query intent and title/snippet; test one change and measure.' if gap>.25 else 'Review content relevance and internal linking opportunities.',
                priority='High' if score>=70 else 'Medium', confidence='Moderate',
                limitations='Partial GSC rows; position buckets do not control for SERP features or intent. No guaranteed traffic forecast.',
                effort='Medium',score=round(score,1)))
    return pd.DataFrame(output,columns=columns).sort_values('score',ascending=False)


def decay(current, previous, key='page', minimum=20, threshold=-.2):
    result = compare(current,previous,key)
    if 'clicks_change_pct' not in result:
        return result.iloc[:0]
    return result[(result.clicks_previous>=minimum)&(result.clicks_change_pct<=threshold)].sort_values('clicks_change')


def overlap(df, minimum=20):
    if df.empty:
        return pd.DataFrame(columns=['query','pages','clicks','impressions','label'])
    data = df[df.impressions>=minimum]
    out = data.groupby('query',as_index=False).agg(pages=('page','nunique'),clicks=('clicks','sum'),impressions=('impressions','sum'))
    out = out[out.pages>1]
    out['label'] = 'Potential Cannibalization — Requires Review'
    return out.sort_values('impressions',ascending=False)


def classify_keywords(current, previous, minimum=100):
    out = compare(current, previous, 'query')
    if out.empty:
        return out
    out['classification'] = 'Insufficient evidence'
    out.loc[out.impressions>=minimum,'classification'] = 'Observed visibility'
    out.loc[(out.impressions>=minimum)&out.position.between(4,20),'classification'] = 'Striking distance'
    out.loc[(out.clicks>=20)&(out.position<=3),'classification'] = 'High performer'
    if 'clicks_change_pct' in out:
        out.loc[(out.clicks_previous>=20)&(out.clicks_change_pct<=-.2),'classification'] = 'Declining'
        out.loc[(out.clicks_previous>=20)&(out.clicks_change_pct>=.2),'classification'] = 'Rising'
    return out


def persistent_decline(current, previous, older, minimum=20, threshold=-.2):
    """Require two consecutive losses on comparable, non-overlapping periods."""
    recent=decay(current,previous,minimum=minimum,threshold=threshold)
    prior=decay(previous,older,minimum=minimum,threshold=threshold)
    out=recent.copy()
    out['decline_pattern']=out.page.map(lambda p:'Two consecutive period losses' if p in set(prior.page) else 'One-period loss; persistence unconfirmed')
    return out


def business_opportunities(matched, minimum_sessions=50):
    columns=['title','target','observation','possible_explanation','action','priority','confidence','limitations','effort','score']
    if matched.empty or 'keyEvents' not in matched or 'sessions' not in matched:
        return pd.DataFrame(columns=columns)
    output=[]
    for _,r in matched[matched.match_status=='Matched'].iterrows():
        if pd.isna(r.sessions) or r.sessions<minimum_sessions:
            continue
        if r.keyEvents>0 and 4<=r.position<=20:
            title='Business-value visibility opportunity'
            action='Review this landing page for search-intent coverage and internal-link opportunities; protect the measured conversion journey.'
        elif r.keyEvents==0:
            title='Organic outcome investigation'
            action='Verify key-event tracking and business relevance, then review the page journey. Zero recorded events does not prove zero leads.'
        else:
            continue
        output.append(dict(title=title,target=r.page,
            observation=f'GSC: {r.clicks:,.0f} clicks, position {r.position:.1f}. GA4: {r.sessions:,.0f} organic sessions, {r.keyEvents:,.0f} key events on the matched page.',
            possible_explanation='Page visibility or the conversion journey may merit investigation; no cause is established.',
            action=action,priority='High',confidence='Moderate',limitations='Page-level association only; no query-to-conversion attribution. Key events are not unique leads.',effort='Medium',score=None))
    return pd.DataFrame(output,columns=columns)


def url_switching(current, previous):
    """Dominant URL changes are review signals, not proof of daily ranking alternation."""
    if current.empty or previous.empty:
        return pd.DataFrame(columns=['query','current_page','previous_page','label'])
    def top(df,name):
        return df.sort_values(['impressions','clicks'],ascending=False).drop_duplicates('query')[['query','page']].rename(columns={'page':name})
    out=top(current,'current_page').merge(top(previous,'previous_page'),on='query')
    out=out[out.current_page!=out.previous_page]
    out['label']='Dominant URL changed between periods — inspect intent and history'
    return out
