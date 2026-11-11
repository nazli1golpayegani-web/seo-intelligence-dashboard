"""Deterministic synthetic observations, with trends and an unmatched landing page."""
import hashlib
import numpy as np
import pandas as pd
from .analytics import aggregate, totals
from .connectors import GA_METRICS

QUERIES = [('northstar studio','/'),('seo consultant','/services/seo/'),('seo agency cologne','/services/seo/'),
           ('seo checklist','/journal/seo-checklist/'),('seo checklist','/resources/checklist/'),
           ('google analytics audit','/services/analytics/'),('content strategy','/journal/content-strategy/'),
           ('technical seo','/services/technical-seo/'),('seo pricing','/pricing/'),('northstar contact','/contact/')]


def generate(start, end):
    rows, ga = [], []
    for day in pd.date_range(start,end):
        rng = np.random.default_rng(int(hashlib.sha256(str(day.date()).encode()).hexdigest()[:8],16))
        epoch = (day-pd.Timestamp('2025-01-01')).days
        for j,(query,path) in enumerate(QUERIES):
            trend = max(.2,1+epoch*.0007) if j != 6 else max(.2,2-(epoch%180)/90)
            for device in ['mobile','desktop']:
                country = 'deu' if device=='mobile' else 'gbr'
                impressions = int(rng.integers(25,170)*trend)
                pos = float(1.8+j*1.4+rng.uniform(-.6,.6))
                ctr = .16/(1+j*.45) if j not in (2,8) else .006
                clicks = int(rng.binomial(impressions,ctr))
                rows.append(dict(date=str(day.date()),query=query,page='https://northstar.example'+path,
                                 device=device,country=country,search_type='web',clicks=clicks,impressions=impressions,ctr=clicks/impressions,position=pos))
        for j,path in enumerate(dict.fromkeys(p for _,p in QUERIES)):
            if path=='/resources/checklist/':
                continue  # Intentional unmatched GSC page.
            for device in ['mobile','desktop']:
                for source in ['google / organic','bing / organic']:
                    n = int(rng.integers(5,35)*(1+epoch*.0004)*(1 if source.startswith('google') else .2))
                    engaged = int(n*.72)
                    key_events = int(rng.binomial(n,.08)) if j!=5 else 0
                    ga.append(dict(date=day.strftime('%Y%m%d'),hostName='northstar.example',landingPagePlusQueryString=path,
                        deviceCategory=device,country='Germany' if device=='mobile' else 'United Kingdom',
                        sessionSourceMedium=source,sessionDefaultChannelGroup='Organic Search',sessions=n,
                        activeUsers=max(0,n-2),newUsers=int(n*.6),engagedSessions=engaged,engagementRate=engaged/n if n else 0,
                        keyEvents=key_events,sessionKeyEventRate=key_events/n if n else 0,totalRevenue=np.nan,
                        screenPageViews=n*2))
    return pd.DataFrame(rows),pd.DataFrame(ga)


class Demo:
    def __init__(self,start,end):
        self.g, self.a = generate(start,end)

    def gsc(self,site,start,end,dimensions,filters=None,search_type='web',**kwargs):
        d = self.g[self.g.date.between(str(start),str(end))]
        d = d[d.search_type==search_type]
        for f in filters or []:
            if f['operator']=='equals':
                d=d[d[f['dimension']]==f['expression']]
            elif f['operator']=='contains':
                d=d[d[f['dimension']].str.contains(f['expression'],regex=False)]
            elif f['operator'] in ('includingRegex','excludingRegex'):
                hit=d[f['dimension']].str.contains(f['expression'],case=False,regex=True)
                d=d[hit if f['operator']=='includingRegex' else ~hit]
        out=aggregate(d,dimensions) if dimensions else pd.DataFrame([totals(d)]) if not d.empty else pd.DataFrame()
        return {'rows':out.to_dict('records'),'notice':'SYNTHETIC DEMO DATA — not connected to Google.','source':'GSC'}

    def ga(self,prop,start,end,dimensions,filters=None,google_only=False,metrics=None,**kwargs):
        d=self.a[self.a.date.between(str(start).replace('-',''),str(end).replace('-',''))]
        if google_only:
            d=d[d.sessionSourceMedium=='google / organic']
        for f in filters or []:
            spec=f['filter']; sf=spec['stringFilter']
            d=d[d[spec['fieldName']].str.contains(sf['value'],regex=False)] if sf.get('matchType')=='CONTAINS' else d[d[spec['fieldName']]==sf['value']]
        metrics=metrics or GA_METRICS
        if d.empty:
            return {'rows':[],'source':'GA4'}
        sums=[m for m in metrics if m not in ('engagementRate','sessionKeyEventRate')]
        out=d.groupby(dimensions,as_index=False)[sums].sum(min_count=1) if dimensions else pd.DataFrame([{m:d[m].sum(min_count=1) for m in sums}])
        if 'engagementRate' in metrics:
            out['engagementRate']=out.engagedSessions/out.sessions.replace(0,np.nan)
        if 'sessionKeyEventRate' in metrics:
            # Synthetic events are at most one per session, explicitly constructed that way.
            out['sessionKeyEventRate']=out.keyEvents/out.sessions.replace(0,np.nan)
        return {'rows':out.to_dict('records'),'source':'GA4','metadata':{'currencyCode':'EUR','timeZone':'Europe/Berlin'},'missing_metrics':['totalRevenue']}
