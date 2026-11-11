from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit
import os
import re
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from src.auth import Login, TokenStore, credentials, AuthError
from src.connectors import Google, APIError, GA_METRICS
from src.storage import settings
from src.analytics import frame, totals, change, match_pages, URLRules, opportunities, decay, overlap, classify_keywords, compare, persistent_decline, business_opportunities, url_switching
from src.demo import Demo
from src.ai import OpenAIProvider
from src.reports import build, pdf

load_dotenv()
st.set_page_config(page_title='SEO Intelligence',page_icon='◈',layout='wide')
st.markdown('''<style>
.block-container{padding-top:2rem;max-width:1600px} h1{letter-spacing:-1.5px} h2{letter-spacing:-.5px}
[data-testid="stMetric"]{background:#141f32;padding:20px;border:1px solid #26364d;border-radius:12px}
[data-testid="stMetricLabel"]{color:#a2b4cc} [data-testid="stSidebar"]{border-right:1px solid #26364d}
</style>''',unsafe_allow_html=True)
PAGES=['SEO Overview','Organic Traffic Analytics','Keyword Intelligence','Landing Page Performance',
'SEO Opportunity Finder','Content Decay & Traffic Loss','SEO Cannibalization Analysis','Technical SEO & Indexing',
'GA4 Business Performance','AI SEO Recommendations','Executive Reports','Connections & Settings']
with st.sidebar:
    st.markdown('## ◈ SEO Intelligence')
    st.caption('SEARCH SIGNALS → BETTER DECISIONS')
    demo=st.toggle('Synthetic demo mode',True)
    page=st.radio('Workspace',PAGES,label_visibility='collapsed')
    st.divider()

cred,account=None,None
if not demo:
    try:
        cred,account=credentials()
    except Exception as e:
        st.error(str(e) if isinstance(e,AuthError) else 'Could not read local credentials. Check the OS keychain.')
account='synthetic-demo' if demo else account or 'disconnected'
config=settings(account)
client=None if demo or not cred else Google(cred,account)

if page=='Connections & Settings' or (not demo and not cred):
    st.title('Connections & Settings')
    st.caption('Local, single-user application · read-only Google permissions')
    if demo:
        st.info('Demo is synthetic. Turn off Synthetic demo mode to connect your Google account.')
    else:
        st.write('Google account: '+('Connected' if cred else 'Not connected'))
        if not cred:
            if st.button('Connect Google Account',type='primary'):
                try:
                    old=st.session_state.get('login')
                    if old:
                        old.done=True
                    st.session_state.login=Login()
                except Exception:
                    st.error('Cannot start OAuth. Add a Desktop OAuth client JSON at GOOGLE_CLIENT_SECRETS and configure local secure credential storage.')
            login=st.session_state.get('login')
            if login:
                if not login.done:
                    st.link_button('Continue to Google authorization',login.url)
                    st.caption('Open this link on the same computer running Streamlit. It expires after three minutes.')
                elif login.error:
                    st.error(login.error)
                if st.button('Check connection'):
                    st.rerun()
        else:
            if st.button('Disconnect Google account'):
                TokenStore().delete()
                st.session_state.clear()
                st.rerun()
            st.caption('Disconnect deletes local tokens. You can also revoke access from your Google Account security settings. Old cached data stays isolated under its previous connection ID.')
            if st.button('Discover / refresh properties') or 'discovery' not in st.session_state:
                discovered={}
                for source,fn in [('GSC',client.sites),('GA4',client.properties)]:
                    try:
                        discovered[source]=fn()
                    except APIError as e:
                        discovered[source]=[]; st.warning(f'{source}: {e}')
                st.session_state.discovery=discovered
            d=st.session_state.discovery
            c1,c2=st.columns(2)
            c1.success(f'GSC: {len(d.get("GSC",[]))} accessible properties') if d.get('GSC') else c1.warning('GSC: no accessible properties')
            c2.success(f'GA4: {len(d.get("GA4",[]))} accessible properties') if d.get('GA4') else c2.warning('GA4: no accessible properties')
            with st.form('mapping'):
                name=st.text_input('Website name')
                gs=st.selectbox('Search Console property',[None]+[x['siteUrl'] for x in d.get('GSC',[])])
                gs4=st.selectbox('GA4 property',[None]+[x['property'] for x in d.get('GA4',[])],format_func=lambda x:next((f'{p.get("displayName","")} · {x}' for p in d.get('GA4',[]) if p['property']==x),'None') if x else 'None')
                origin=st.text_input('Canonical origin (including https://)',placeholder='https://www.example.com')
                verified=st.checkbox('I verified these properties measure the same website')
                if st.form_submit_button('Save website mapping'):
                    u=urlsplit(origin)
                    if not name or not (gs or gs4) or not verified or u.scheme not in ('http','https') or not u.hostname or u.path not in ('','/') or u.query or u.fragment:
                        st.error('Provide a name, valid origin, at least one property and confirm the mapping.')
                    else:
                        config.setdefault('websites',{})[name]={'gsc':gs,'ga4':gs4,'origin':origin.rstrip('/')}
                        settings(account,config); st.success('Mapping saved.')
            if config.get('websites'):
                st.json(config['websites'])
    with st.form('preferences'):
        st.subheader('Analysis preferences')
        brand=st.text_input('Brand regex (shown explicitly in filters)',config.get('brand','northstar' if demo else ''))
        minimum=st.number_input('Minimum GSC impressions',min_value=10,value=int(config.get('minimum',100)))
        objective=st.selectbox('Business objective',['Lead Generation','E-commerce','Content / Publishing','Custom'],index=['Lead Generation','E-commerce','Content / Publishing','Custom'].index(config.get('objective','Lead Generation')))
        lower=st.number_input('Ranking window: lower position',min_value=1.0,value=float(config.get('lower',4)))
        upper=st.number_input('Ranking window: upper position',min_value=1.0,value=float(config.get('upper',20)))
        strip=st.checkbox('Treat trailing slash variants as the same URL',config.get('strip_slash',False))
        protocol=st.checkbox('Treat HTTP and HTTPS as the same URL',config.get('ignore_protocol',False))
        remove=st.checkbox('Remove utm_*, gclid, fbclid and msclkid parameters',config.get('remove_tracking',True))
        st.caption('Paths stay case-sensitive. Ambiguous normalization matches are excluded, never multiplied.')
        w1=st.slider('Opportunity weight: impressions',0.0,1.0,float(config.get('w1',.45)),.05)
        w2=st.slider('Opportunity weight: internal CTR gap',0.0,1.0,float(config.get('w2',.35)),.05)
        w3=st.slider('Opportunity weight: ranking window',0.0,1.0,float(config.get('w3',.2)),.05)
        if st.form_submit_button('Save preferences'):
            try:
                re.compile(brand)
                if lower>upper:
                    raise ValueError('Ranking window lower bound must not exceed upper bound.')
                if w1+w2+w3==0:
                    raise ValueError('At least one scoring weight must be positive.')
                config.update(brand=brand,minimum=minimum,objective=objective,lower=lower,upper=upper,strip_slash=strip,ignore_protocol=protocol,remove_tracking=remove,w1=w1,w2=w2,w3=w3)
                settings(account,config); st.success('Preferences saved.')
            except (re.error,ValueError) as e:
                st.error(str(e))
    st.stop()

websites={'Northstar Studio':{'gsc':'sc-domain:northstar.example','ga4':'properties/demo','origin':'https://northstar.example'}} if demo else config.get('websites',{})
if not websites:
    st.info('Open Connections & Settings to discover properties and save a website mapping.'); st.stop()
with st.sidebar:
    website=st.selectbox('Website',list(websites))
    preset=st.selectbox('Reporting period',['Last 7 days','Last 28 days','Last 3 months','Last 6 months','Last 12 months','Custom'],index=1)
    end=date.today()-timedelta(days=3)
    days={'Last 7 days':7,'Last 28 days':28,'Last 3 months':90,'Last 6 months':180,'Last 12 months':365}.get(preset,28)
    dates=st.date_input('Date range',value=(end-timedelta(days=days-1),end),max_value=date.today())
    if len(dates)!=2:
        st.info('Select a start and end date.'); st.stop()
    start,end=dates
    if start>end:
        st.error('Start must precede end.'); st.stop()
    comparison=st.selectbox('Compare with',['Previous period','Year over year'])
    device=st.selectbox('Device',['All','mobile','desktop','tablet'])
    country=st.selectbox('Country',['All','Germany','United Kingdom','United States','France','Iran'])
    search_type=st.selectbox('GSC search type',['web','image','video','news','discover','googleNews'])
    page_filter=st.text_input('Page contains (path or full URL)')
    brand_mode=st.selectbox('GSC brand segment',['All','Brand','Non-brand'])
    st.caption('Brand regex: '+(config.get('brand','northstar' if demo else '') or 'not configured'))
    google_only=st.selectbox('GA4 acquisition',['All Organic Search','Google organic'])=='Google organic'
    recent=st.checkbox('Include incomplete recent GSC data',False)
    refresh=st.button('Refresh selected reports')

site=websites[website]
period=(end-start).days+1
if comparison=='Year over year':
    pstart=(pd.Timestamp(start)-pd.DateOffset(years=1)).date()
    pend=(pd.Timestamp(end)-pd.DateOffset(years=1)).date()
else:
    pend=start-timedelta(days=1); pstart=pend-timedelta(days=period-1)
if pstart<date.today()-timedelta(days=480):
    st.warning('The comparison extends beyond typical GSC retention. Missing historical rows are unavailable, not zero.')
if (date.today()-end).days<3:
    st.warning('Recent reporting dates may be incomplete. GSC finalized data can lag; GA4 processing also takes time.')
if demo:
    @st.cache_data(show_spinner=False)
    def demo_client(a,b):
        return Demo(a,b)
    client=demo_client(min(pstart,start),end)

filters=[]; ga_filters=[]
def gf(name,value,match='EXACT'):
    return {'filter':{'fieldName':name,'stringFilter':{'value':value,'matchType':match}}}
if device!='All':
    filters.append({'dimension':'device','operator':'equals','expression':device})
    ga_filters.append(gf('deviceCategory',device))
if country!='All':
    iso={'Germany':'deu','United Kingdom':'gbr','United States':'usa','France':'fra','Iran':'irn'}[country]
    filters.append({'dimension':'country','operator':'equals','expression':iso}); ga_filters.append(gf('country',country))
if page_filter:
    filters.append({'dimension':'page','operator':'contains','expression':page_filter})
    u=urlsplit(page_filter)
    ga_filters.append(gf('landingPagePlusQueryString',(u.path or '/')+('?' + u.query if u.query else '') if u.netloc else page_filter,'CONTAINS'))
    if u.hostname:
        ga_filters.append(gf('hostName',u.hostname))
brand=config.get('brand','northstar' if demo else '')
if brand_mode!='All':
    if not brand:
        st.warning('Configure a brand regex in Settings first.'); st.stop()
    filters.append({'dimension':'query','operator':'includingRegex' if brand_mode=='Brand' else 'excludingRegex','expression':brand})
    st.info('Brand segmentation applies only to GSC. GA4 has no equivalent query-level filter; its outcomes remain the selected organic acquisition segment.')
if search_type!='web':
    st.info('Search type filters GSC only. GA4 organic sessions cannot be assigned to this GSC search type.')

st.caption('WORKSPACE / '+website.upper())
st.title(page)
st.caption(f'{start:%d %b %Y} – {end:%d %b %Y}  ·  vs {pstart:%d %b %Y} – {pend:%d %b %Y}')
if demo:
    st.warning('SYNTHETIC DEMO DATA · No Google account is connected. All values are generated for demonstration.')
notices=[]
def fetch(source,dimensions,previous=False,metrics=None,range_override=None):
    a,b=range_override or ((pstart,pend) if previous else (start,end))
    prop=site['gsc' if source=='gsc' else 'ga4']
    columns=dimensions+(['clicks','impressions','ctr','position'] if source=='gsc' else (metrics or GA_METRICS))
    if not prop:
        return pd.DataFrame(columns=columns)
    try:
        if source=='gsc':
            result=client.gsc(prop,a,b,dimensions,filters=filters,search_type=search_type,final=not recent,refresh=refresh)
        else:
            result=client.ga(prop,a,b,dimensions,filters=ga_filters,google_only=google_only,refresh=refresh,metrics=metrics)
        if result.get('stale_error'):
            st.warning('Showing stale cache: '+result['stale_error'])
        if result.get('synced_at'):
            notices.append(f'{source.upper()} last successful sync: '+datetime.fromtimestamp(result['synced_at'],timezone.utc).isoformat(timespec='seconds'))
        if result.get('metadata'):
            notices.append('GA4 report metadata: '+str(result['metadata']))
        if result.get('missing_metrics'):
            notices.append('Unavailable metrics: '+', '.join(result['missing_metrics']))
        if result.get('notice'):
            notices.append(result['notice'])
        return frame(result,columns)
    except APIError as e:
        st.warning(f'{source.upper()} report unavailable: {e}')
        notices.append(f'{source.upper()} unavailable: {e}')
        return pd.DataFrame(columns=columns)

def show_table(df,name='table'):
    if df.empty:
        st.info('No observations are available for this selection. Try another date range or check property access.')
    else:
        st.dataframe(df,width='stretch',hide_index=True)
        st.download_button('Download CSV',df.to_csv(index=False).encode(),file_name=name+'.csv',mime='text/csv',key='download_'+name)

def chart(df,x,y,title):
    if not df.empty and y in df:
        d=df.copy()
        if x=='date':
            d[x]=pd.to_datetime(d[x].astype(str),format='mixed')
        fig=px.line(d,x=x,y=y,title=title,template='plotly_dark',color_discrete_sequence=['#35d0b2'])
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',height=300,margin=dict(l=0,r=0,t=45,b=0))
        if y=='position':
            fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig,width='stretch')

def metric_cards(values,old,source,keys):
    cols=st.columns(3)
    for i,k in enumerate(keys):
        value=values.get(k); before=old.get(k); pct=change(value,before)
        label=f'{source} · {k}'
        display='Unavailable' if value is None or pd.isna(value) else f'{value:.2%}' if k in ('ctr','engagementRate','sessionKeyEventRate') else f'{value:,.1f}' if k=='position' else f'{value:,.0f}'
        cols[i%3].metric(label,display,None if pct is None else f'{pct:+.1%}',delta_color='inverse' if k=='position' else 'normal')

def get_opps():
    q=fetch('gsc',['query'])
    return opportunities(q,int(config.get('minimum',100)),lower=config.get('lower',4),upper=config.get('upper',20),weights=(config.get('w1',.45),config.get('w2',.35),config.get('w3',.2)))

if page=='SEO Overview':
    current=totals(fetch('gsc',[])); previous=totals(fetch('gsc',[],True))
    metric_cards(current,previous,'GSC',['clicks','impressions','ctr','position'])
    st.subheader('Organic acquisition')
    ga=fetch('ga',[]); gp=fetch('ga',[],True)
    metric_cards(ga.iloc[0].to_dict() if not ga.empty else {},gp.iloc[0].to_dict() if not gp.empty else {},'GA4',['sessions','engagedSessions','engagementRate','keyEvents','sessionKeyEventRate','totalRevenue'])
    st.caption('GSC clicks ≠ GA4 sessions. Key events are event counts, not unique leads. Rates are fractions; revenue currency comes from GA4 report metadata.')
    gd=fetch('gsc',['date']); ad=fetch('ga',['date'])
    left,right=st.columns(2)
    with left:
        chart(gd,'date','clicks','Search clicks'); chart(gd,'date','ctr','Search CTR'); chart(ad,'date','sessions','Organic sessions')
    with right:
        chart(gd,'date','impressions','Search impressions'); chart(gd,'date','position','Average search position'); chart(ad,'date','keyEvents','Organic key events')
    st.subheader('SEO insights')
    delta=change(current.get('clicks'),previous.get('clicks'))
    st.info('Search clicks changed '+f'{delta:+.1%} in this comparison. Investigate demand, ranking and CTR separately.' if delta is not None else 'Insufficient comparable click data for a growth estimate.')
    t1,t2,t3,t4=st.tabs(['Top pages','Top queries','Devices','Countries'])
    for tab,dim in zip([t1,t2,t3,t4],['page','query','device','country']):
        with tab:
            df=fetch('gsc',[dim]); show_table(df.sort_values('clicks',ascending=False) if not df.empty else df,dim)

elif page in ('Organic Traffic Analytics','GA4 Business Performance'):
    st.caption('Objective: '+config.get('objective','Lead Generation'))
    a=fetch('ga',[]); b=fetch('ga',[],True)
    metric_cards(a.iloc[0].to_dict() if not a.empty else {},b.iloc[0].to_dict() if not b.empty else {},'GA4',['sessions','engagedSessions','engagementRate','keyEvents','sessionKeyEventRate','totalRevenue'])
    st.info('Key events can occur multiple times in a session. Session key event rate is provided by GA4; it is not calculated as event count / sessions.')
    chart(fetch('ga',['date']),'date','sessions','Organic acquisition trend')
    tabs=st.tabs(['Landing pages','Devices','Countries','Google vs other organic','Key event analysis'])
    for tab,dims in zip(tabs[:4],[['hostName','landingPagePlusQueryString'],['deviceCategory'],['country'],['sessionSourceMedium']]):
        with tab:
            show_table(fetch('ga',dims),'ga_'+dims[-1])
    with tabs[4]:
        if demo:
            st.info('Demo key events: generate_lead. Synthetic revenue is deliberately unavailable.')
        elif site.get('ga4'):
            try:
                events=client.key_events(site['ga4'])
                names=[e['eventName'] for e in events]
                if not names:
                    st.warning('No key events are configured or available for this property.')
                else:
                    chosen=st.multiselect('Relevant configured key events',names,default=names)
                    ev=fetch('ga',['eventName'],metrics=['keyEvents'])
                    show_table(ev[ev.eventName.isin(chosen)] if not ev.empty else ev,'key_events')
            except APIError as e:
                st.warning(str(e))
        st.caption('Event-level reports show event counts only; session-level rates remain in the KPI report.')

elif page=='Keyword Intelligence':
    a=fetch('gsc',['query']); b=fetch('gsc',['query'],True)
    result=classify_keywords(a,b,config.get('minimum',100))
    search=st.text_input('Find a query')
    if search and not result.empty:
        result=result[result['query'].str.contains(search,case=False,regex=False,na=False)]
    show_table(result,'keywords')
    if not a.empty:
        st.plotly_chart(px.scatter(a,x='impressions',y='clicks',color='position',hover_name='query',template='plotly_dark'),width='stretch')
        st.plotly_chart(px.histogram(a,x='position',nbins=20,title='Average position distribution (query rows)',template='plotly_dark'),width='stretch')
    st.subheader('Query-to-page relationships'); show_table(fetch('gsc',['query','page']),'query_pages')

elif page=='Landing Page Performance':
    a=fetch('gsc',['page']); b=fetch('ga',['hostName','landingPagePlusQueryString'])
    result,coverage=match_pages(a,b,site['origin'],URLRules(remove_tracking=config.get('remove_tracking',True),strip_slash=config.get('strip_slash',False),ignore_protocol=config.get('ignore_protocol',False)))
    st.metric('Unambiguous page-match coverage','Unavailable' if coverage is None else f'{coverage:.1%}')
    st.caption('Coverage is the share of retrieved GSC page rows matched. GA4 outcomes belong to the page and chosen organic channel, not individual GSC queries. HTTP/HTTPS matching uses the configured origin because GA4 hostname has no protocol.')
    if not result.empty and 'sessions' in result and 'keyEvents' in result:
        result['business_status']='Review tracking and business context'
        result.loc[(result.sessions>=50)&(result.keyEvents==0),'business_status']='Traffic with no recorded key events'
        result.loc[result.keyEvents>0,'business_status']='Recorded page-level key events'
        result.loc[result.match_status!='Matched','business_status']='No reliable cross-source match'
    show_table(result,'landing_pages')

elif page=='SEO Opportunity Finder':
    opps=get_opps()
    st.caption('Internal opportunity score, not a Google metric or forecast. Weights are configurable in Settings.')
    st.latex(r'100\times\frac{w_I\,\log(1+I)/\log(1+I_{max})+w_C\,CTRgap+w_R\,RankingWindow}{w_I+w_C+w_R}')
    st.caption('CTR gap uses impression-weighted peers in position buckets (1–3, 3–5, 5–10, 10–20, >20), minimum five peers. Missing benchmark contributes no CTR bonus. Ranking window: 4–20. Business relevance and trend are not inferred by this score.')
    order=st.selectbox('Sort opportunities',['Score','Priority','Effort'])
    if not opps.empty:
        opps=opps.sort_values({'Score':'score','Priority':'priority','Effort':'effort'}[order],ascending=order!='Score')
    show_table(opps,'opportunities')
    for _,r in opps.head(6).iterrows():
        with st.expander(f'{r.priority} · {r.title} · {r.target}'):
            st.write(r.observation); st.write(r.action); st.caption(r.limitations)
    st.subheader('Measured page-level business opportunities')
    matched,_=match_pages(fetch('gsc',['page']),fetch('ga',['hostName','landingPagePlusQueryString']),site['origin'],URLRules(remove_tracking=config.get('remove_tracking',True),strip_slash=config.get('strip_slash',False),ignore_protocol=config.get('ignore_protocol',False)))
    show_table(business_opportunities(matched),'business_opportunities')
    st.subheader('Content & internal-link candidates')
    qp=fetch('gsc',['query','page'])
    if not qp.empty:
        clusters=qp.groupby('page',as_index=False).agg(queries=('query',lambda x:', '.join(sorted(set(x))[:8])),impressions=('impressions','sum'))
        show_table(clusters,'content_clusters')
    st.info('Query groups are content-review and internal-link candidates. They do not prove missing content or missing links; inspect the pages and crawl before making changes.')

elif page=='Content Decay & Traffic Loss':
    minimum=st.number_input('Minimum previous-period clicks',min_value=1,value=20)
    threshold=st.slider('Minimum click loss (%)',5,90,20)
    a=fetch('gsc',['page']); b=fetch('gsc',['page'],True)
    result=decay(a,b,minimum=minimum,threshold=-threshold/100)
    if comparison=='Previous period' and st.checkbox('Check persistence over a third equal-length period'):
        older_end=pstart-timedelta(days=1); older_start=older_end-timedelta(days=period-1)
        older=fetch('gsc',['page'],range_override=(older_start,older_end))
        result=persistent_decline(a,b,older,minimum=minimum,threshold=-threshold/100)
    show_table(result,'content_decay')
    st.info('Two-period losses are investigation signals. Sustained decay requires multiple comparable periods. Falling impressions may reflect demand or rankings; lower CTR may reflect SERP or intent changes. No cause is established here.')
    chart(fetch('gsc',['date']),'date','clicks','Historical clicks in selected period')
    for dim in ['device','country']:
        st.subheader(dim.title()+' movement')
        show_table(compare(fetch('gsc',[dim]),fetch('gsc',[dim],True),dim),'decline_'+dim)
    st.subheader('GA4 landing-page movement')
    ga=fetch('ga',['landingPagePlusQueryString']); gp=fetch('ga',['landingPagePlusQueryString'],True)
    show_table(compare(ga,gp,'landingPagePlusQueryString'),'ga_decline')

elif page=='SEO Cannibalization Analysis':
    qp=fetch('gsc',['query','page']); previous=fetch('gsc',['query','page'],True)
    show_table(overlap(qp),'overlap')
    st.subheader('Possible URL switching')
    show_table(url_switching(qp,previous),'switching')
    st.warning('Multiple URLs for a query show overlap, not proven cannibalization. Different intent, sitelinks and content differentiation can be valid. No automatic redirects, canonicals or deletion are recommended.')
    if not qp.empty:
        query=st.selectbox('Inspect query',sorted(qp['query'].unique()))
        st.write('Current period'); show_table(qp[qp['query']==query],'overlap_current')
        st.write('Comparison period'); show_table(previous[previous['query']==query],'overlap_previous')

elif page=='Technical SEO & Indexing':
    st.info('URL Inspection reports Google’s indexed version; it does not test the live page. GSC + GA4 do not constitute a full technical crawl.')
    if demo:
        st.info('Live sitemap and URL inspection actions require a connected Search Console property. No fabricated inspection results are shown.')
    elif not site.get('gsc'):
        st.info('Map a Search Console property first.')
    else:
        if st.button('Retrieve search appearance breakdown'):
            show_table(fetch('gsc',['searchAppearance']),'search_appearance')
        if st.button('Retrieve submitted sitemaps'):
            try:
                st.json(client.sitemaps(site['gsc']))
            except APIError as e:
                st.error(str(e))
        url=st.text_input('URL to inspect',site['origin']+'/')
        if st.button('Inspect this URL'):
            host=urlsplit(url).hostname or ''; prop=site['gsc']
            allowed=host==prop.removeprefix('sc-domain:') or host.endswith('.'+prop.removeprefix('sc-domain:')) if prop.startswith('sc-domain:') else url.startswith(prop)
            if not allowed or urlsplit(url).scheme not in ('http','https'):
                st.error('URL must belong to the selected Search Console property.')
            elif datetime.now().timestamp()-st.session_state.get('last_inspection',0)<5:
                st.warning('Please wait before another inspection.')
            else:
                st.session_state.last_inspection=datetime.now().timestamp()
                try:
                    st.json(client.inspect(prop,url))
                except APIError as e:
                    st.error(str(e))

elif page=='AI SEO Recommendations':
    opps=get_opps(); st.subheader('Evidence-backed rule recommendations'); show_table(opps,'rules')
    st.caption('Optional external AI receives only the first ten opportunity records, including query text. Review this payload before sending. Query/page strings are treated as untrusted data.')
    language=st.selectbox('AI language',['English','Deutsch'])
    payload=opps.head(10).to_dict('records')
    with st.expander('Exact external AI payload'):
        st.json(payload)
    consent=st.checkbox('Send the displayed evidence to OpenAI for analysis')
    if st.button('Generate AI interpretation',disabled=not consent or not payload):
        try:
            response=OpenAIProvider().analyze(payload,language)
            st.json(response.model_dump())
            st.warning('AI interpretation is unverified. Evidence references and schema were validated; causal and qualitative claims still require human review.')
        except Exception as e:
            st.error(str(e) if isinstance(e,ValueError) else 'AI analysis failed. Rule-based recommendations remain available.')

elif page=='Executive Reports':
    language=st.selectbox('Report language',['English','Deutsch'])
    g=totals(fetch('gsc',[])); a=fetch('ga',[]); opps=get_opps()
    risks=decay(fetch('gsc',['page']),fetch('gsc',['page'],True))
    limitations=[f'Filters: device={device}; country={country}; search type={search_type}; page={page_filter or "all"}; GSC brand={brand_mode}; GA4={"Google organic" if google_only else "All Organic Search"}.',f'Comparison: {pstart} to {pend}.']+list(dict.fromkeys(notices))
    report=build(site['gsc'] or website,site['ga4'],start,end,g,a.iloc[0].to_dict() if not a.empty else {},opps,risks,language,demo,limitations)
    c1,c2=st.columns(2)
    c1.download_button('Download Markdown',report,'seo-report.md','text/markdown')
    c2.download_button('Download PDF',pdf(report),'seo-report.pdf','application/pdf')
    st.markdown(report)

with st.expander('Data quality & measurement notes'):
    st.write('GSC returns top rows and suppresses some queries. Query/page sums may differ from site totals. Clicks use GSC reporting conventions; GA4 sessions depend on tracking, consent, attribution and property time zone. Missing rows and missing metrics are unavailable, never assumed zero.')
    for n in dict.fromkeys(notices):
        st.caption(n)
