from datetime import date
import json
from unittest.mock import Mock, patch
import pandas as pd
import pytest
from src.storage import Cache
from src.connectors import Google, APIError, GA_METRICS
from src.analytics import totals, aggregate, normalize_url, URLRules, match_pages, compare, opportunities, decay, overlap, brand_filter
from src.demo import Demo, generate
from src.ai import validate
from src.reports import build,pdf
from src.auth import credentials, AuthError, Login


def response(data,status=200,text='',headers=None):
    r=Mock(status_code=status,text=text,headers=headers or {})
    r.json.return_value=data
    return r


@pytest.fixture
def api(tmp_path):
    session=Mock()
    return Google(session=session,cache=Cache(tmp_path/'cache.sqlite'),sleep=Mock())


def test_gsc_pagination(api):
    row={'keys':['test'],'clicks':2,'impressions':20,'ctr':.1,'position':3}
    api.session.request.side_effect=[response({'rows':[row]}),response({'rows':[]})]
    report=api.gsc('sc-domain:example.com','2026-01-01','2026-01-02',['query'],page_size=1)
    assert report['rows'][0]['query']=='test'
    assert api.session.request.call_args_list[1].kwargs['json']['startRow']==1
    assert report['partial'] is True


def test_ga_pagination_and_channel(api):
    api.session.request.side_effect=[response({'metrics':[{'apiName':'sessions'}]}),response({}),
        response({'rows':[{'dimensionValues':[{'value':'mobile'}],'metricValues':[{'value':'2'}]}],'rowCount':2}),
        response({'rows':[{'dimensionValues':[{'value':'desktop'}],'metricValues':[{'value':'3'}]}],'rowCount':2})]
    r=api.ga('properties/123','2026-01-01','2026-01-02',['deviceCategory'],google_only=True,metrics=['sessions'],page_size=1)
    assert len(r['rows'])==2
    body=api.session.request.call_args.kwargs['json']
    assert body['offset']=='1'
    f=body['dimensionFilter']['andGroup']['expressions']
    assert f[0]['filter']['stringFilter']['value']=='Organic Search'
    assert f[1]['filter']['stringFilter']['value']=='google / organic'


def test_partial_pagination_not_cached(api):
    api.session.request.side_effect=[response({'metrics':[{'apiName':'sessions'}]}),response({}),response({'rows':[],'rowCount':2})]
    with pytest.raises(APIError,match='ended early'):
        api.ga('properties/1','2026-01-01','2026-01-02',[],metrics=['sessions'])


def test_retry_and_redacted_error(api):
    api.session.request.side_effect=[response({},429),response({'ok':True})]
    assert api.request('GET','https://example.test')['ok']
    api.sleep.assert_called_once()
    api.session.request.side_effect=[response({},401,text='access_token=SECRET')]
    with pytest.raises(APIError) as e:
        api.request('GET','https://example.test')
    assert 'SECRET' not in str(e.value)


def test_permission_not_retried(api):
    api.session.request.return_value=response({},403)
    with pytest.raises(APIError):
        api.request('GET','x')
    api.sleep.assert_not_called()


def test_cache_fallback_and_account_isolation(api):
    first=api.cached('x',{'property':'1'},lambda:{'rows':[1]})
    def fail():
        raise APIError('network')
    r=api.cached('x',{'property':'1'},fail,True)
    assert r['rows']==[1] and r['stale_error']=='network'
    assert Cache.key('a','x',{})!=Cache.key('b','x',{})
    assert Cache.key('a','x',{'p':'1'})!=Cache.key('a','x',{'p':'2'})


def test_property_discovery(api):
    api.session.request.side_effect=[response({'siteEntry':[{'siteUrl':'sc-domain:x'}]}),
       response({'accountSummaries':[{'propertySummaries':[{'property':'properties/1'}]}],'nextPageToken':'next'}),
       response({'accountSummaries':[{'propertySummaries':[{'property':'properties/2'}]}]})]
    assert api.sites()[0]['siteUrl']=='sc-domain:x'
    assert len(api.properties())==2


def test_technical_api(api):
    api.session.request.side_effect=[response({'sitemap':[{'path':'https://x/sitemap.xml','errors':'0'}]}),
                                    response({'inspectionResult':{'indexStatusResult':{'verdict':'PASS'}}})]
    assert api.sitemaps('sc-domain:x')[0]['errors']=='0'
    assert api.inspect('sc-domain:x','https://x/')['inspectionResult']['indexStatusResult']['verdict']=='PASS'
    assert api.session.request.call_args.kwargs['json']['siteUrl']=='sc-domain:x'


def sample():
    return pd.DataFrame([{'query':'a','page':'https://example.com/A/','clicks':10,'impressions':100,'ctr':.1,'position':2},
                         {'query':'b','page':'https://example.com/B/','clicks':90,'impressions':900,'ctr':.1,'position':10}])


def test_weighted_metrics_and_missing():
    r=totals(sample())
    assert r['ctr']==.1 and r['position']==9.2
    assert totals(pd.DataFrame())['clicks'] is None
    assert aggregate(sample().assign(group='x'),['group']).position.iloc[0]==9.2


def test_normalization_conservative():
    assert normalize_url('HTTPS://Example.COM/A/?utm_source=x&item=2')=='https://example.com/A/?item=2'
    assert normalize_url('https://example.com/A/')!=normalize_url('https://example.com/a/')
    assert normalize_url('https://example.com/A/')!=normalize_url('https://example.com/A')
    assert normalize_url('https://example.com/A/',URLRules(strip_slash=True))=='https://example.com/A'
    assert normalize_url('https://example.com/a?item=1')!=normalize_url('https://example.com/a?item=2')


def test_page_matching_host_and_ambiguity():
    ga=pd.DataFrame([{'hostName':'example.com','landingPagePlusQueryString':'/A/','sessions':5},
                     {'hostName':'other.com','landingPagePlusQueryString':'/B/','sessions':10}])
    result,coverage=match_pages(sample(),ga,'https://example.com')
    assert coverage==.5 and result.clicks.sum()==100
    assert result.loc[result.page.str.endswith('/B/'),'sessions'].isna().all()
    assert 'sessions' in result and 'clicks' in result
    ga=pd.concat([ga,ga.iloc[:1]])
    result,coverage=match_pages(sample(),ga,'https://example.com')
    assert coverage==0


def test_opportunity_and_overlap():
    df=sample()
    opps=opportunities(df)
    assert len(opps)==1 and opps.iloc[0].target=='b'
    df['query']='same'
    assert overlap(df).iloc[0]['pages']==2
    assert 'Requires Review' in overlap(df).iloc[0]['label']


def test_decline_and_missing_rows():
    before=sample(); after=before.copy(); after['clicks']*=.5
    assert len(decay(after,before,minimum=5))==2
    out=compare(after.iloc[:1],before,'page')
    assert pd.isna(out.iloc[1].clicks_change)


def test_demo_dates_filter_and_missing_revenue():
    demo=Demo(date(2026,1,1),date(2026,1,4))
    g=demo.gsc('x',date(2026,1,2),date(2026,1,2),['date'])
    assert [r['date'] for r in g['rows']]==['2026-01-02']
    all_=demo.ga('x',date(2026,1,1),date(2026,1,4),[])['rows'][0]
    google=demo.ga('x',date(2026,1,1),date(2026,1,4),[],google_only=True)['rows'][0]
    assert all_['sessions']>google['sessions']
    assert pd.isna(all_['totalRevenue'])
    assert brand_filter(sample(),'a','Brand')['query'].tolist()==['a']


def test_ai_validation():
    r=dict(evidence_ids=[0],problem='p',observed_data='invented',interpretation='hypothesis',action='review',business_rationale='r',expected_direction='unknown',priority='High',confidence='Moderate',additional_data_required='crawl')
    out=validate({'recommendations':[r]},[{'observation':'GSC: 100 impressions'}])
    assert out.recommendations[0].observed_data=='GSC: 100 impressions'
    r['evidence_ids']=[5]
    with pytest.raises(ValueError):
        validate({'recommendations':[r]},[{'observation':'x'}])


def test_report_exports():
    for lang in ['English','Deutsch']:
        text=build('site','prop','2026-01-01','2026-01-28',totals(sample()),{},opportunities(sample()),pd.DataFrame(),lang,True)
        assert 'SYNTHETIC DEMO' in text
        assert pdf(text).startswith(b'%PDF-')


def test_refresh_credentials():
    store=Mock(); store.read.return_value={'credentials':{},'account':'abc'}
    cred=Mock(expired=True); cred.to_json.return_value='{}'
    with patch('src.auth.Credentials.from_authorized_user_info',return_value=cred):
        actual,account=credentials(store)
        cred.refresh.assert_called_once(); store.save.assert_called_once()
        assert account=='abc'
        cred.refresh.side_effect=Exception('SECRET')
        with pytest.raises(AuthError,match='revoked'):
            credentials(store)


def test_oauth_callback_and_state(tmp_path):
    import requests
    from urllib.parse import urlparse
    flow=Mock(); flow.authorization_url.return_value=('https://accounts.google.com/auth','state-123')
    flow.credentials.to_json.return_value='{"token":"mock"}'
    store=Mock()
    with patch('src.auth.InstalledAppFlow.from_client_secrets_file',return_value=flow):
        login=Login('unused',store)
        base=flow.redirect_uri
        assert requests.get(base+'?state=invalid&code=bad',timeout=2).status_code==400
        assert not login.done
        assert requests.get(base+'?state=state-123&code=good',timeout=2).status_code==200
        assert login.done and login.error is None
        flow.fetch_token.assert_called_once_with(code='good')
        store.save.assert_called_once()


def test_sustained_decline_and_switching():
    from src.analytics import persistent_decline,url_switching,business_opportunities
    older=sample(); prior=older.copy(); prior['clicks']*=.5
    current=prior.copy(); current['clicks']*=.5
    result=persistent_decline(current,prior,older,minimum=1)
    assert (result.decline_pattern=='Two consecutive period losses').all()
    switched=sample(); switched.loc[0,'page']='https://example.com/new/'
    assert len(url_switching(switched,sample()))==1
    matched=sample().assign(match_status='Matched',sessions=100,keyEvents=5)
    assert len(business_opportunities(matched))==1
