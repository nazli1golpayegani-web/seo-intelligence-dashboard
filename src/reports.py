from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

LABELS={
'English':['SEO Intelligence Report','Executive Summary','Search Visibility','Organic Website Engagement','Business Outcomes','Top SEO Opportunities','Performance Risks','Prioritized Action Plan','Measurement Limitations'],
'Deutsch':['SEO-Intelligence-Bericht','Zusammenfassung','Sichtbarkeit in der Suche','Organische Website-Interaktion','Geschäftsergebnisse','SEO-Chancen','Leistungsrisiken','Priorisierter Maßnahmenplan','Messgrenzen']}


def build(site,prop,start,end,gsc,ga,opps,risks,language='English',demo=False,limitations=None):
    labels=LABELS[language]; de=language=='Deutsch'
    def val(x):
        return '—' if x is None or (isinstance(x,float) and pd.isna(x)) else f'{x:,.3f}' if isinstance(x,(int,float)) else str(x)
    lines=[f'# {labels[0]}',f'{site} | GA4: {prop or "—"} | {start} → {end}',
           f'UTC: {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
           '**SYNTHETIC DEMO DATA**' if demo else '**Google Search Console + Google Analytics 4**',
           f'## {labels[1]}',
           'Suchsichtbarkeit und Website-Ergebnisse werden getrennt bewertet. Ursachen sind ohne weitere Prüfung nicht bestätigt.' if de else 'Search visibility and website outcomes are measured separately. Potential causes require further investigation.',
           f'## {labels[2]}']
    lines += [f'- GSC {k}: {val(v)}' for k,v in gsc.items()]
    lines += [f'## {labels[3]}']+[f'- GA4 {k}: {val(ga.get(k))}' for k in ['sessions','engagedSessions','engagementRate']]
    lines += [f'## {labels[4]}']+[f'- GA4 {k}: {val(ga.get(k))}' for k in ['keyEvents','sessionKeyEventRate','totalRevenue']]
    lines += [f'## {labels[5]}']
    for _,r in opps.head(10).iterrows():
        lines += [f'- {r.target}: {r.observation}']
    lines += [f'## {labels[6]}',f'{len(risks)} '+('Seiten mit Rückgang im Periodenvergleich; keine bestätigte Ursache.' if de else 'pages declined in the selected comparison; no confirmed cause.')]
    for _,r in risks.head(10).iterrows():
        lines += [f'- {r.get("page", "")}: GSC Δ clicks {val(r.get("clicks_change"))}']
    lines += [f'## {labels[7]}']
    for _,r in opps.head(10).iterrows():
        action=('Suchintention, Titel und interne Verlinkung prüfen; eine Änderung testen und messen.' if de else r.action)
        lines += [f'- {r.target}: {action}']
    lines += [f'## {labels[8]}',
        'GSC-Klicks sind keine GA4-Sitzungen. Suchanfragen lassen sich nicht einzelnen Conversions zuordnen. API-Zeilen sind unvollständig; Datenschutz, Zeitzonen, Consent und Tracking beeinflussen Messwerte. Fehlende Werte sind nicht null.' if de else 'GSC clicks are not GA4 sessions. Queries cannot be attributed to individual conversions. API rows are incomplete; privacy, time zones, consent and tracking affect measurements. Missing values are not zero.']
    lines += [str(x) for x in (limitations or [])]
    return '\n\n'.join(lines)


def pdf(markdown):
    fonts=Path(__file__).resolve().parents[1]/'assets'/'fonts'
    pdfmetrics.registerFont(TTFont('ReportSans',str(fonts/'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('ReportSansBold',str(fonts/'DejaVuSans-Bold.ttf')))
    output=BytesIO(); styles=getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName='ReportSansBold' if style.name.startswith(('Heading','Title')) else 'ReportSans'
    styles['BodyText'].leading=15
    styles['Title'].textColor=colors.HexColor('#14243a')
    styles['Heading2'].textColor=colors.HexColor('#147c71')
    story=[]
    for line in markdown.splitlines():
        if not line.strip():
            continue
        style='Title' if line.startswith('# ') else 'Heading2' if line.startswith('## ') else 'BodyText'
        text=line.lstrip('# ').replace('**','').replace('→',' to ').replace('—','N/A').replace('Δ','change')
        story.extend([Paragraph(escape(text),styles[style]),Spacer(1,7)])
    def footer(canvas,doc):
        canvas.setFont('ReportSans',8); canvas.setFillColor(colors.grey)
        canvas.drawString(45,28,'SEO Intelligence | '+str(doc.page))
    SimpleDocTemplate(output,pagesize=(595.28,841.89),rightMargin=45,leftMargin=45,topMargin=45,bottomMargin=45).build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
