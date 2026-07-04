import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings('ignore')
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, HRFlowable, KeepTogether)

d=pickle.load(open('/home/user/hariluker/report/data.pkl','rb'))
clean,s,inv,ds,toy,aged,neg,tv,sm,mp = (d['clean'],d['s'],d['inv'],d['ds'],d['toy'],
                                          d['aged'],d['neg'],d['tv'],d['sm'],d['mp'])
milesummary,milemodel,pbtab,modelretail = d['milesummary'],d['milemodel'],d['pbtab'],d['modelretail']

# ---------- palette ----------
NAVY=colors.HexColor('#0B2545'); STEEL=colors.HexColor('#13315C'); ACCENT=colors.HexColor('#C8102E')
GREEN=colors.HexColor('#1B7A3D'); AMBER=colors.HexColor('#B5651D'); LGREY=colors.HexColor('#EEF1F6')
MGREY=colors.HexColor('#D6DCE5'); DGREY=colors.HexColor('#3A3A3A')

ss=getSampleStyleSheet()
def style(n,**k):
    base=k.pop('parent',ss['Normal']); return ParagraphStyle(n,parent=base,**k)
H1=style('H1',fontName='Helvetica-Bold',fontSize=20,textColor=NAVY,spaceAfter=2,leading=23)
SUB=style('SUB',fontName='Helvetica',fontSize=9.5,textColor=DGREY,spaceAfter=2)
H2=style('H2',fontName='Helvetica-Bold',fontSize=13.5,textColor=colors.white,spaceBefore=4,spaceAfter=4,leading=16)
H3=style('H3',fontName='Helvetica-Bold',fontSize=11,textColor=STEEL,spaceBefore=10,spaceAfter=3)
BODY=style('BODY',fontSize=9.3,textColor=DGREY,leading=13,spaceAfter=4)
BULL=style('BULL',fontSize=10,textColor=DGREY,leading=15,leftIndent=4,spaceAfter=3)
NOTE=style('NOTE',fontSize=8,textColor=colors.HexColor('#6B7280'),leading=10.5,spaceAfter=2)
CELL=style('CELL',fontSize=8.2,textColor=DGREY,leading=10)
CELLB=style('CELLB',fontSize=8.2,fontName='Helvetica-Bold',textColor=NAVY,leading=10)
CW=style('CW',fontSize=8.2,textColor=colors.white,fontName='Helvetica-Bold',leading=10)

def usd(x,dec=0):
    if pd.isna(x): return '—'
    x=float(x); s=f"-${abs(x):,.{dec}f}" if x<0 else f"${x:,.{dec}f}"
    return s
def secbar(txt):
    t=Table([[Paragraph(txt,H2)]],colWidths=[7.5*inch])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),NAVY),('LEFTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    return t

def mktable(headers,rows,widths,aligns=None,hi=None,hcolor=None):
    data=[[Paragraph(h,CW) for h in headers]]+rows
    t=Table(data,colWidths=widths,repeatRows=1)
    stl=[('BACKGROUND',(0,0),(-1,0),STEEL),('TOPPADDING',(0,0),(-1,-1),3.5),
         ('BOTTOMPADDING',(0,0),(-1,-1),3.5),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
         ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(0,0),(-1,-1),0.4,MGREY),
         ('LINEBELOW',(0,0),(-1,0),0.8,NAVY)]
    for i in range(1,len(data)):
        if i%2==0: stl.append(('BACKGROUND',(0,i),(-1,i),LGREY))
    if aligns:
        for c,a in enumerate(aligns): stl.append(('ALIGN',(c,0),(c,-1),a))
    if hi:
        for r,col in hi: stl.append(('BACKGROUND',(0,r),(-1,r),col))
    t.setStyle(TableStyle(stl)); return t

def P(txt,st=CELL,align=None):
    if align: st=style('tmp',parent=st,alignment={'C':TA_CENTER,'L':TA_LEFT}[align])
    return Paragraph(txt,st)

E=[]
# ===== HEADER =====
hdr=Table([[Paragraph("USED VEHICLE BUYER'S REPORT",H1)],
           [Paragraph("Acquisition Targeting &amp; Inventory Health  •  Trailing 30-Day Sales vs. Current Stock",SUB)],
           [Paragraph("Prepared for the Used Car Inventory Team  •  Report date: June 4, 2026",SUB)]],
          colWidths=[7.5*inch])
hdr.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
E+=[hdr,Spacer(1,4),HRFlowable(width='100%',thickness=2,color=ACCENT),Spacer(1,8)]

# store averages
SA_F,SA_B,SA_T,SA_D=clean.Front.mean(),clean.Back.mean(),clean.Total.mean(),clean.Days.mean()
tr=clean[clean.Source=='Trade']; au=clean[clean.Source=='Auction']
gap=tr.Total.mean()-au.Total.mean(); fgap=tr.Front.mean()-au.Front.mean()
aged_cost=aged.Cost.sum(); aged_ask=aged.Asking.sum()

# ===== EXECUTIVE SUMMARY =====
E+=[secbar("EXECUTIVE SUMMARY"),Spacer(1,6)]
bullets=[
 f"<b>Top 3 buy targets:</b> <b>4Runner</b> (sells in 13 days, {usd(9768)} avg total gross), "
 f"<b>Sienna</b> (14 days, {usd(7327)}), and <b>Tacoma</b> (trade units turn in 27 days at {usd(4641)}). "
 f"All three out-gross and out-turn the store and we are <b>thin</b> on each.",
 f"<b>Trade crushes auction.</b> Trade-acquired units average {usd(tr.Total.mean())} total gross vs. {usd(au.Total.mean())} "
 f"for auction — a <b>{usd(gap)} per-unit gap</b>. The gap is almost entirely up front: trade front gross {usd(tr.Front.mean())} "
 f"vs. auction {usd(au.Front.mean())} (a {usd(fgap)} front swing). Trades also sell faster ({tr.Days.mean():.0f} vs {au.Days.mean():.0f} days).",
 f"<b>{usd(aged_cost)} in capital is tied up in 7 aged units</b> (60+ days) — {usd(aged_ask)} at retail. "
 f"Every one is an inferred auction/wholesale buy; six of seven are late-model Toyota/Ford trucks &amp; SUVs bought too rich.",
 f"<b>Fast movers print money.</b> Units sold in &lt;21 days average {usd(5549)} total gross vs. {usd(3293)} for slower units — "
 f"and carry a {usd(3025)} front vs. {usd(662)}. Speed and gross move together; chase turn, not just price.",
 f"<b>Stop the bleeding on auction Highlanders &amp; RAV4s.</b> Auction Highlanders lose {usd(-2413)} front over 46 days; "
 f"auction RAV4s run {usd(-129)} front across 15 units. 78% of our 32 negative-front deals were auction buys.",
]
for b in bullets:
    E+=[Table([[Paragraph('▸',style('a',parent=BULL,textColor=ACCENT)),Paragraph(b,BULL)]],
              colWidths=[0.22*inch,7.28*inch],
              style=TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),3),('VALIGN',(0,0),(-1,-1),'TOP')]))]

# KPI strip
def kpi(t,v,c=NAVY):
    return Table([[Paragraph(v,style('k',fontName='Helvetica-Bold',fontSize=14,textColor=c,alignment=TA_CENTER))],
                  [Paragraph(t,style('kt',fontSize=7,textColor=DGREY,alignment=TA_CENTER,leading=8.5))]],
                 colWidths=[1.42*inch],
                 style=TableStyle([('BACKGROUND',(0,0),(-1,-1),LGREY),('BOX',(0,0),(-1,-1),0.5,MGREY),
                   ('TOPPADDING',(0,0),(-1,0),6),('BOTTOMPADDING',(0,1),(-1,1),5),('TOPPADDING',(0,1),(-1,1),0)]))
kpis=[kpi("UNITS SOLD / 30 DAYS",f"{len(clean)}"),kpi("AVG TOTAL GROSS",usd(SA_T)),
      kpi("AVG DAYS TO SELL",f"{SA_D:.0f}"),kpi("CURRENT INVENTORY",f"{len(inv)}"),
      kpi("AGED 60+ CAPITAL",usd(aged_cost),ACCENT)]
E+=[Spacer(1,6),Table([kpis],style=TableStyle([('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))]
E+=[Spacer(1,4),Paragraph("Store averages exclude 4 data-quality outliers (see Methodology). Acquisition-source splits use the sold feed's Source Type; current-inventory source is inferred.",NOTE)]

# ===== REPORT 1 VELOCITY =====
E+=[PageBreak(),secbar("REPORT 1 — VELOCITY (how fast we turn)"),Spacer(1,6)]
E+=[Paragraph("Fast movers vs. slow movers",H3),
    Paragraph("\"Fast mover\" = sold in under 21 days. Fast units don't just turn quicker — they carry dramatically more front gross, meaning the right car bought right sells itself.",BODY)]
fast=clean[clean.Days<21]; slow=clean[clean.Days>=21]
rows=[[P('Fast movers (&lt;21 days)',CELLB),P(f"{len(fast)}",align='C'),P(f"{fast.Days.mean():.0f}",align='C'),
       P(usd(fast.Front.mean()),align='C'),P(usd(fast.Back.mean()),align='C'),P(usd(fast.Total.mean()),CELLB,'C')],
      [P('Slower movers (21+ days)',CELL),P(f"{len(slow)}",align='C'),P(f"{slow.Days.mean():.0f}",align='C'),
       P(usd(slow.Front.mean()),align='C'),P(usd(slow.Back.mean()),align='C'),P(usd(slow.Total.mean()),CELLB,'C')]]
E+=[mktable(['Segment','Units','Avg Days','Avg Front','Avg Back','Avg Total'],rows,
            [2.3*inch,0.8*inch,0.95*inch,1.1*inch,1.1*inch,1.25*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'],
            hi=[(1,colors.HexColor('#E3F1E8'))])]

E+=[Paragraph("Velocity by model — Toyota core (ranked fastest to slowest)",H3)]
rows=[]
tvs=tv.sort_values('Days')
for m,r in tvs.iterrows():
    fast_flag = '★ FAST' if r['Days']<21 else ''
    rows.append([P(m,CELLB),P(f"{int(r['n'])}",align='C'),P(f"{r['Days']:.0f}",align='C'),
                 P(usd(r['Front']),align='C'),P(usd(r['Total']),align='C'),
                 P(fast_flag,style('f',parent=CELL,textColor=GREEN,alignment=TA_CENTER))])
E+=[mktable(['Model','Units','Avg Days to Sell','Avg Front','Avg Total','Flag'],rows,
            [1.7*inch,0.8*inch,1.45*inch,1.1*inch,1.1*inch,1.35*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'])]

E+=[Paragraph("Days-to-sell by acquisition source",H3)]
rows=[]
for srcn,lab,c in [('Trade','Trade-acquired',GREEN),('Auction','Auction / Wholesale',AMBER)]:
    g=clean[clean.Source==srcn]
    rows.append([P(lab,CELLB),P(f"{len(g)}",align='C'),P(f"{g.Days.mean():.0f} days",style('d',parent=CELLB,textColor=c,alignment=TA_CENTER)),
                 P(f"{(g.Days<21).mean()*100:.0f}%",align='C')])
E+=[mktable(['Source','Units','Avg Days to Sell','% Fast (&lt;21d)'],rows,
            [2.3*inch,1.0*inch,1.7*inch,1.5*inch],['LEFT','CENTER','CENTER','CENTER'])]
E+=[Paragraph("<b>Read:</b> trade-acquired units turn ~7 days faster than auction units and are far more likely to be fast movers. Auction inventory sits longer and erodes front gross while it ages.",BODY)]

E+=[Paragraph("Mileage sweet spot — fast vs. slow movers (actual sold mileage)",H3)]
fm,sm2=milesummary['fast'],milesummary['slow']
rows=[[P('Fast movers (&lt;21 days)',CELLB),P(f"{fm['n']}",align='C'),P(f"{fm['miles']:,.0f} mi",CELLB,'C'),
       P(f"{fm['year']:.0f}",align='C'),P(f"{fm['tradepct']:.0f}% trade",style('a',parent=CELL,textColor=GREEN,alignment=TA_CENTER)),P(usd(fm['retail']),align='C')],
      [P('Slower movers (21+ days)',CELL),P(f"{sm2['n']}",align='C'),P(f"{sm2['miles']:,.0f} mi",CELLB,'C'),
       P(f"{sm2['year']:.0f}",align='C'),P(f"{sm2['tradepct']:.0f}% trade",style('a',parent=CELL,textColor=AMBER,alignment=TA_CENTER)),P(usd(sm2['retail']),align='C')]]
E+=[mktable(['Segment','Units','Median Miles','Median Yr','Source mix','Median Retail'],rows,
            [1.95*inch,0.7*inch,1.15*inch,0.85*inch,1.1*inch,1.05*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'],hi=[(1,colors.HexColor('#E3F1E8'))])]
E+=[Paragraph("<b>The surprise:</b> our fast movers are NOT the low-mileage units — they are <b>older, higher-mileage trade-ins</b> "
   f"(median {fm['miles']:,.0f} mi, MY{fm['year']:.0f}, {fm['tradepct']:.0f}% trade-sourced) that we bought right and priced to market. "
   f"The slow movers are <b>newer, lower-mileage auction units</b> (median {sm2['miles']:,.0f} mi, MY{sm2['year']:.0f}) sitting on thin front gross. "
   "Mileage is not the gating factor — <b>acquisition source and price-to-market are.</b> Don't shy away from a higher-mile trade that pencils.",BODY)]
E+=[Paragraph("Mileage sweet spot by model (Toyota core, median of sold units)",H3)]
rows=[]
for m,r in milemodel.sort_values('Days').iterrows():
    rows.append([P(m,CELLB),P(f"{int(r['n'])}",align='C'),P(f"{r['Miles']:,.0f} mi",align='C'),
                 P(usd(r['Retail']),align='C'),P(f"{r['Days']:.0f}",align='C')])
E+=[mktable(['Model','Units','Median Miles Sold','Median Retail','Avg Days'],rows,
            [1.6*inch,0.85*inch,1.5*inch,1.2*inch,1.0*inch],['LEFT','CENTER','CENTER','CENTER','CENTER'])]
E+=[Paragraph("Within a model, the bands that actually move: <b>4Runner ~40k mi</b>, <b>Tacoma/Prius ~35k</b>, <b>RAV4 ~30k</b>, "
   "while <b>Sienna and Highlander</b> retail fine up to <b>65k–80k mi</b>. Buy to the band the nameplate supports rather than chasing the lowest odometer.",BODY)]

# ===== REPORT 2 GROSS =====
E+=[PageBreak(),secbar("REPORT 2 — GROSS PROFIT (front, back &amp; total)"),Spacer(1,6)]
E+=[Paragraph("Acquisition-source breakdown — the headline number",H3)]
rows=[]
for srcn,lab,c in [('Trade','Trade-In',GREEN),('Auction','Auction / Wholesale',AMBER)]:
    g=clean[clean.Source==srcn]
    rows.append([P(lab,CELLB),P(f"{len(g)}",align='C'),P(usd(g.Front.mean()),align='C'),
                 P(usd(g.Back.mean()),align='C'),P(usd(g.Total.mean()),CELLB,'C'),P(f"{g.Days.mean():.0f}",align='C')])
rows.append([P('GROSS GAP (Trade − Auction)',style('g',parent=CELLB,textColor=ACCENT)),P('',align='C'),
             P(usd(fgap),style('g',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),
             P(usd(tr.Back.mean()-au.Back.mean()),align='C'),
             P(usd(gap),style('g',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),P('',align='C')])
E+=[mktable(['Source','Units','Avg Front','Avg Back','Avg Total','Avg Days'],rows,
            [2.3*inch,0.7*inch,1.1*inch,1.1*inch,1.1*inch,0.95*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'],
            hi=[(3,colors.HexColor('#FBE4E7'))])]
E+=[Paragraph(f"<b>Trade-in units deliver {usd(gap)} more total gross per unit</b> than auction buys, and the entire advantage is front-end: trades hold {usd(tr.Front.mean())} front vs. nearly zero ({usd(au.Front.mean())}) on auction. Auction relies on back-end (F&amp;I) to stay positive. Every retail-quality trade we keep instead of wholesaling is worth ~{usd(gap)}.",BODY)]

E+=[Paragraph("Average gross by model &amp; year range (Toyota core)",H3)]
rows=[]
gm=clean[clean.Make=='Toyota'].groupby('Model').agg(n=('Total','size'),F=('Front','mean'),B=('Back','mean'),
    T=('Total','mean')).query('n>=2').sort_values('T',ascending=False)
for m,r in gm.iterrows():
    beat='✓' if r['T']>SA_T else ''
    rows.append([P(m,CELLB),P(f"{int(r['n'])}",align='C'),P(usd(r['F']),align='C'),P(usd(r['B']),align='C'),
                 P(usd(r['T']),CELLB,'C'),P(beat,style('b',parent=CELL,textColor=GREEN,alignment=TA_CENTER))])
E+=[mktable(['Model','Units','Avg Front','Avg Back','Avg Total','Beats Store Avg'],rows,
            [1.55*inch,0.7*inch,1.1*inch,1.1*inch,1.15*inch,1.4*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'])]
E+=[Paragraph(f"Store average total gross = <b>{usd(SA_T)}</b> (front {usd(SA_F)} / back {usd(SA_B)}). Models with ✓ beat it. 4Runner and Sienna are the gross leaders by a wide margin.",NOTE)]
yb=clean.groupby('YrBand').agg(n=('Total','size'),F=('Front','mean'),B=('Back','mean'),T=('Total','mean'))
yb=yb.reindex(['2023-2026','2020-2022','2016-2019','2011-2015']).dropna()
rows=[[P(i,CELLB),P(f"{int(r['n'])}",align='C'),P(usd(r['F']),align='C'),P(usd(r['B']),align='C'),P(usd(r['T']),CELLB,'C')] for i,r in yb.iterrows()]
E+=[Paragraph("Average gross by model-year band (all units)",H3),
    mktable(['Year Range','Units','Avg Front','Avg Back','Avg Total'],rows,
            [1.7*inch,0.9*inch,1.2*inch,1.2*inch,1.25*inch],['LEFT','CENTER','CENTER','CENTER','CENTER'])]

# Price band (real retail)
rows=[]
for pb,r in pbtab.iterrows():
    rows.append([P(pb,CELLB),P(f"{int(r['n'])}",align='C'),P(f"{r['Days']:.0f}",align='C'),
                 P(usd(r['F']),align='C'),P(usd(r['B']),align='C'),P(usd(r['T']),CELLB,'C'),P(f"{r['Mi']:,.0f}",align='C')])
E+=[Paragraph("Average gross by price band (actual retail price)",H3),
    mktable(['Price Band','Units','Avg Days','Avg Front','Avg Back','Avg Total','Med. Miles'],rows,
            [1.3*inch,0.7*inch,0.85*inch,1.0*inch,1.0*inch,1.05*inch,1.1*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER','CENTER'])]
E+=[Paragraph("Total gross rises with price point — the <b>$30k–$50k</b> band is the profit core (avg total ~$4,200–$4,500). "
   "The <b>$20k–$30k</b> band is the danger zone: thin front ($552) on newer, low-mile units (these are the auction late-models that sit). "
   "Cheaper <b>sub-$20k</b> high-mileage trades actually hold the best <i>front</i> gross ($2,162).",BODY)]

# Top gross units beating store avg
E+=[Paragraph(f"Units that beat the store average total gross ({usd(SA_T)})",H3)]
beat=clean[clean.Total>SA_T].sort_values('Total',ascending=False).head(12)
rows=[]
for _,r in beat.iterrows():
    rows.append([P(f"{int(r['Year'])} {r['Make']} {r['ModelRaw']}",CELL),P(r['Source'],align='C'),
                 P(usd(r['Front']),align='C'),P(usd(r['Back']),align='C'),P(usd(r['Total']),CELLB,'C'),P(f"{int(r['Days'])}",align='C')])
E+=[mktable(['Vehicle','Source','Front','Back','Total','Days'],rows,
            [2.4*inch,1.05*inch,1.0*inch,1.0*inch,1.05*inch,0.6*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'])]
E+=[Paragraph(f"{len(clean[clean.Total>SA_T])} of {len(clean)} units beat the store average (top 12 shown).",NOTE)]

# Negative front
E+=[Paragraph("Negative front-gross deals — common traits",H3)]
nau=neg[neg.Source=='Auction']; ntr=neg[neg.Source=='Trade']
rows=[[P('Auction / Wholesale',CELLB),P(f"{len(nau)}",align='C'),P(usd(nau.Front.mean()),align='C'),P(f"{nau.Days.mean():.0f}",align='C'),P(f"{nau.Year.mean():.0f}",align='C')],
      [P('Trade-In',CELLB),P(f"{len(ntr)}",align='C'),P(usd(ntr.Front.mean()),align='C'),P(f"{ntr.Days.mean():.0f}",align='C'),P(f"{ntr.Year.mean():.0f}",align='C')],
      [P('All negative-front',style('x',parent=CELLB,textColor=ACCENT)),P(f"{len(neg)}",style('x',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),
       P(usd(neg.Front.mean()),style('x',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),P(f"{neg.Days.mean():.0f}",align='C'),P(f"{neg.Year.mean():.0f}",align='C')]]
E+=[mktable(['Source','# Deals','Avg Front','Avg Days','Avg Model Yr'],rows,
            [2.1*inch,1.0*inch,1.2*inch,1.1*inch,1.4*inch],['LEFT','CENTER','CENTER','CENTER','CENTER'],
            hi=[(3,colors.HexColor('#FBE4E7'))])]
topneg=neg.groupby('Model').size().sort_values(ascending=False)
nstr=', '.join([f"{m} ({n})" for m,n in topneg.head(5).items()])
E+=[Paragraph(f"<b>Common traits:</b> {len(neg)} of {len(clean)} sold units ({len(neg)/len(clean)*100:.0f}%) lost money up front. "
   f"<b>78% were auction buys.</b> They skew late-model (avg MY {neg.Year.mean():.0f}) and age on the lot ({neg.Days.mean():.0f} days avg — well past the 21-day fast line). "
   f"Concentration: {nstr}. Translation: we are overpaying at auction for newer Camry/Highlander/RAV4 and grinding the front to zero to move them.",BODY)]

# ===== REPORT 3 INVENTORY HEALTH =====
E+=[PageBreak(),secbar("REPORT 3 — CURRENT INVENTORY HEALTH"),Spacer(1,6)]
E+=[Paragraph("Days supply &amp; sell-through by model (Toyota)",H3),
    Paragraph("Days supply = current units in stock ÷ daily sales rate (units sold last 30 ÷ 30). Bands: <b>&lt;30 = THIN (buy more)</b>, 30–60 = healthy, 60–90 = heavy, 90+ = overstocked. Sell-through = sold ÷ (sold + in stock).",NOTE)]
bandcolor={'THIN (buy)':colors.HexColor('#E3F1E8'),'Healthy':colors.white,'Heavy':colors.HexColor('#FBEFD9'),
           'Overstock':colors.HexColor('#FBE4E7'),'No sales (dead)':colors.HexColor('#FBE4E7')}
bandlabel={'THIN (buy)':'THIN — buy','Healthy':'Healthy','Heavy':'Heavy','Overstock':'Overstock','No sales (dead)':'Dead (no sales)'}
rows=[]; hi=[]
tshow=toy.sort_values('days_supply')
i=1
for (mk,m),r in tshow.iterrows():
    dsv='∞' if r['days_supply']==np.inf else f"{r['days_supply']:.0f}"
    rows.append([P(m,CELLB),P(f"{int(r['sold30'])}",align='C'),P(f"{int(r['instock'])}",align='C'),
                 P(dsv,CELLB,'C'),P(f"{r['sellthru']*100:.0f}%",align='C'),
                 P(bandlabel[r['band']],style('bb',parent=CELL,alignment=TA_CENTER,fontName='Helvetica-Bold'))])
    hi.append((i,bandcolor[r['band']])); i+=1
E+=[mktable(['Model','Sold 30d','In Stock','Days Supply','Sell-Through','Status'],rows,
            [1.4*inch,0.95*inch,0.9*inch,1.1*inch,1.15*inch,1.5*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'],hi=hi)]
E+=[Paragraph("<b>Read:</b> our entire fast-selling core (4Runner, Tacoma, Camry, RAV4, Highlander, Prius, Crown) is THIN — we are selling faster than we're stocking. Meanwhile <b>Tundra (7 in stock, 0 sold), Grand Highlander (5), Land Cruiser (2), Sequoia and Corolla</b> are heavy or dead. Reallocate auction spend from trucks-that-sit toward the thin core.",BODY)]

E+=[Paragraph("Aged unit flags — every current unit over 60 days",H3)]
rows=[]
for _,r in aged.iterrows():
    rows.append([P(r['Vehicle'],CELLB),P(f"{int(r['AgeD'])}",style('a',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),
                 P(usd(r['Asking']),align='C'),P(usd(r['Cost']),align='C'),
                 P(f"{r['Odo']:,.0f}",align='C'),P('Auction*',align='C')])
rows.append([P('TOTAL — 7 aged units',style('t',parent=CELLB,textColor=ACCENT)),P('',align='C'),
             P(usd(aged.Asking.sum()),style('t',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),
             P(usd(aged.Cost.sum()),style('t',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),P('',align='C'),P('',align='C')])
E+=[mktable(['Vehicle','Days','Asking','Cost','Odometer','Source*'],rows,
            [2.45*inch,0.6*inch,1.0*inch,1.0*inch,1.0*inch,0.95*inch],
            ['LEFT','CENTER','CENTER','CENTER','CENTER','CENTER'],hi=[(len(rows),colors.HexColor('#FBE4E7'))])]
E+=[Paragraph(f"*Source inferred (no sales appraiser on record → auction/wholesale). <b>{usd(aged_cost)} of capital ({usd(aged_ask)} retail) is locked in these 7 units.</b> All are late-model and were bought at thin markups (asking barely above cost) — classic auction over-pays. Priority: price-to-market and move before 90 days.",BODY)]

# ===== BUYER'S TARGET LIST =====
E+=[PageBreak(),secbar("BUYER'S TARGET LIST — what to chase"),Spacer(1,6)]
E+=[Paragraph("Ranked buy list: fast movers + above-average gross + thin in stock",H3),
    Paragraph("Ideal acquisition price = actual median sold retail − target front gross (preferred source). Preferred source is whichever grossed better on the sold data.",NOTE)]

ask=modelretail
def srcrow(m,src): 
    g=clean[(clean.Make=='Toyota')&(clean.Model==m)&(clean.Source==src)]; return g
def dsval(m):
    r=toy.xs(('Toyota',m)); return ('∞' if r['days_supply']==np.inf else f"{r['days_supply']:.0f}")

# (model, preferred source, note)
targets=[('4Runner','Trade'),('Sienna','Trade'),('Tacoma','Trade'),('Camry','Trade'),('Prius','Trade')]
rows=[]
rank=1
buycards=[]
for m,psrc in targets:
    mr=tv.loc[m] if m in tv.index else clean[(clean.Make=='Toyota')&(clean.Model==m)].agg({'Days':'mean','Front':'mean','Back':'mean','Total':'mean'})
    g=srcrow(m,psrc)
    tf=g.Front.mean() if len(g) else mr['Front']
    askp=ask.get(m,np.nan)
    if pd.isna(askp):
        acq='turn play (0 in stock)'
    else:
        lo=askp-tf*1.15; hi=askp-tf*0.85
        acq=f"{usd(lo)}–{usd(hi)}"
    mdays=mr['Days'] if 'Days' in mr else clean[(clean.Make=='Toyota')&(clean.Model==m)].Days.mean()
    rows.append([P(f"{rank}",style('r',parent=CELLB,textColor=ACCENT,alignment=TA_CENTER)),
                 P(f"Toyota {m}",CELLB),
                 P(acq,align='C'),
                 P(f"{mdays:.0f}",align='C'),
                 P(usd(mr['Front']),align='C'),P(usd(mr['Total']),align='C'),
                 P(psrc,style('s',parent=CELL,textColor=GREEN,alignment=TA_CENTER,fontName='Helvetica-Bold')),
                 P(dsval(m),CELLB,'C')])
    rank+=1
E+=[mktable(['#','Year/Make/Model','Ideal Acq. Price','Avg Days','Avg Front','Avg Total','Pref. Source','Days Supply'],rows,
            [0.3*inch,1.5*inch,1.35*inch,0.7*inch,0.85*inch,0.85*inch,0.95*inch,0.85*inch],
            ['CENTER','LEFT','CENTER','CENTER','CENTER','CENTER','CENTER','CENTER'])]
E+=[Paragraph("<b>How to read the buy list:</b> these are model-level averages; <i>preferred source</i> is the channel that has delivered the better front gross. "
   "<b>#1 4Runner</b> is the standout — fastest turn and richest gross in the store, and we're nearly out. "
   "<b>Sienna</b> posts the #2 gross and trades flip in ~6 days (model stock reads 'healthy' only because volume is low — buy every clean one). "
   "<b>Tacoma, Camry and Prius</b> are all thin; the catch is <b>source</b>: trade Camrys gross "
   f"{usd(srcrow('Camry','Trade').Total.mean())} in 21 days while auction Camrys grind to {usd(srcrow('Camry','Auction').Total.mean())} over 42 days. Prioritize trade acquisition on these.",BODY)]

# DO NOT BUY
E+=[Paragraph("DO NOT BUY / slow down",H3)]
auh=clean[(clean.Make=='Toyota')&(clean.Model=='Highlander')&(clean.Source=='Auction')]
aur=clean[(clean.Make=='Toyota')&(clean.Model=='RAV4')&(clean.Source=='Auction')]
auc=clean[(clean.Make=='Toyota')&(clean.Model=='Camry')&(clean.Source=='Auction')]
dnb=[
 [P('Auction Highlanders',CELLB),P('Weak gross + slow',align='C'),
  P(f"{len(auh)} units · {usd(auh.Front.mean())} front · {usd(auh.Total.mean())} total · {auh.Days.mean():.0f} days. Worst money-loser in the store.",CELL)],
 [P('Auction RAV4s',CELLB),P('Margin-thin',align='C'),
  P(f"{len(aur)} units · {usd(aur.Front.mean())} front · {usd(aur.Total.mean())} total · {aur.Days.mean():.0f} days. High volume, near-zero front; back-end carries it.",CELL)],
 [P('Auction Camrys',CELLB),P('Slow + flat front',align='C'),
  P(f"{len(auc)} units · {usd(auc.Front.mean())} front · {auc.Days.mean():.0f} days. Buy Camrys on TRADE, not auction.",CELL)],
 [P('Tundra (in stock)',CELLB),P('Overstocked / dead',align='C'),
  P("7 in stock, 0 sold in 30 days. Stop adding full-size trucks until these move.",CELL)],
 [P('Grand Highlander / Land Cruiser',CELLB),P('Dead stock',align='C'),
  P("5 + 2 units in stock, zero sales in 30 days. No proven turn — avoid speculative buys.",CELL)],
 [P('Corolla / Sequoia',CELLB),P('Heavy + low gross',align='C'),
  P(f"Days supply 52 / 60. Corolla gross only {usd(2969)}. Adequately stocked — no urgency.",CELL)],
]
t=Table([[Paragraph(h,CW) for h in ['Target','Why','Detail']]]+dnb,
        colWidths=[1.9*inch,1.35*inch,4.25*inch],repeatRows=1)
tstl=[('BACKGROUND',(0,0),(-1,0),ACCENT),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
      ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
      ('LINEBELOW',(0,0),(-1,-1),0.4,MGREY),('ALIGN',(1,0),(1,-1),'CENTER')]
for i in range(1,len(dnb)+1):
    if i%2==0: tstl.append(('BACKGROUND',(0,i),(-1,i),colors.HexColor('#FCEEF0')))
t.setStyle(TableStyle(tstl))
E+=[t]
E+=[Paragraph(f"<b>The pattern is the source, not the model.</b> The same nameplates that make money on trade (Highlander, RAV4, Camry) lose money at auction. "
   f"Our auction desk is paying retail-minus-nothing for late-model units, then bleeding front gross as they age. Shift the mix toward trade and toward the thin core above.",BODY)]

# ===== METHODOLOGY =====
E+=[Spacer(1,10),HRFlowable(width='100%',thickness=0.6,color=MGREY),Spacer(1,4),
    Paragraph("Methodology &amp; data notes",style('m',fontName='Helvetica-Bold',fontSize=8.5,textColor=STEEL,spaceAfter=2))]
notes=[
 f"Sources: \"sold units – 30 days\" ({len(s)} sold records) and \"current inventory 6-4\" ({len(inv)} in-stock units).",
 "Days-to-sell uses the sold feed's Vehicle Age (days in inventory). 4 outliers with front gross beyond ±$15k (a +$52.6k Sienna, two +$20k Camrys, and a −$33.4k RAV4) are excluded from all averages as data-entry anomalies; counts include them.",
 "Mileage, retail sale price, and acquisition source now come directly from the sold feed (actuals, not proxies). Price bands use real retail price; the mileage analysis uses actual sold odometer; buy-list acquisition prices anchor on each model's median actual sold retail minus the target front gross. A few sold records with a blank/$0 retail price are excluded from price-band and acquisition math only.",
 "Current-inventory acquisition source is INFERRED (a recorded sales appraiser → trade; otherwise auction/wholesale) because the inventory feed has no explicit source field. Sold-unit source uses the feed's Source Type and is exact.",
 "Model groupings normalize trims to the base nameplate (e.g., Camry XSE → Camry, Tacoma 4WD → Tacoma).",
]
for n in notes: E+=[Paragraph("• "+n,NOTE)]

def footer(canvas,doc):
    canvas.saveState()
    canvas.setStrokeColor(MGREY); canvas.setLineWidth(0.5)
    canvas.line(0.75*inch,0.55*inch,7.75*inch,0.55*inch)
    canvas.setFont('Helvetica',7.5); canvas.setFillColor(colors.HexColor('#6B7280'))
    canvas.drawString(0.75*inch,0.4*inch,"Used Vehicle Buyer's Report — Confidential, internal use")
    canvas.drawRightString(7.75*inch,0.4*inch,f"Page {doc.page}")
    canvas.setFont('Helvetica-Bold',7.5); canvas.setFillColor(NAVY)
    canvas.drawCentredString(4.25*inch,0.4*inch,"Prepared June 4, 2026")
    canvas.restoreState()

doc=SimpleDocTemplate('/home/user/hariluker/report/Buyers_Report.pdf',pagesize=letter,
    leftMargin=0.75*inch,rightMargin=0.75*inch,topMargin=0.6*inch,bottomMargin=0.7*inch,
    title="Used Vehicle Buyer's Report",author="Used Car Inventory Analytics")
doc.build(E,onFirstPage=footer,onLaterPages=footer)
print("PDF BUILT")
