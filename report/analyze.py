import pandas as pd, numpy as np, re, warnings, json
warnings.filterwarnings('ignore')

SOLD='/root/.claude/uploads/0795adae-e827-4a1c-b9e2-98ab9993cb13/864b92b4-sold_units_30_days.csv'
INV ='/root/.claude/uploads/0795adae-e827-4a1c-b9e2-98ab9993cb13/78bd985e-current_inventory_64.xls'

def money(x):
    if pd.isna(x): return np.nan
    s=str(x).replace('$','').replace(',','').strip()
    if s in ('','-','nan'): return np.nan
    return float(s)

# ---------- SOLD ----------
s=pd.read_csv(SOLD)
s=s[s['Year'].astype(str).str.strip()!='-'].copy()        # drop totals row
s['Year']=pd.to_numeric(s['Year'],errors='coerce')
s['Front']=s['Front Gross'].map(money)
s['Back']=s['Back Gross'].map(money)
s['Total']=s['Front']+s['Back']
s['Days']=pd.to_numeric(s['Vehicle Age'],errors='coerce')
s['Retail']=s['Retail Price'].map(money).replace(0,np.nan)
s['Miles']=pd.to_numeric(s['Mileage'],errors='coerce')
s['Make']=s['Make'].str.strip().str.title()
s['ModelRaw']=s['Model'].str.strip()
# base model normalization
def basemodel(m):
    m=re.sub(r'\b4WD|2WD|AWD|FWD\b','',m).strip()
    repl={'Tacoma 4WD':'Tacoma','Camry XSE':'Camry','Accord Hybrid':'Accord','Accord Sedan':'Accord',
          'Ioniq Hybrid':'Ioniq','Grand Cherokee L':'Grand Cherokee','Wrangler Unlimited':'Wrangler'}
    for k,v in repl.items():
        if m.startswith(k): return v
    # strip trailing trim words for multiword
    parts=m.split()
    return parts[0] if len(parts)>1 and parts[0] in ('Tacoma','Camry','Accord','Ioniq') else m
s['Model']=s['ModelRaw'].map(basemodel)
def src(x):
    x=str(x).strip()
    if x.startswith('Trade'): return 'Trade'
    if x.startswith('Auction'): return 'Auction'
    return 'Unknown'
s['Source']=s['Source Type'].map(src)
# year range band
def yrband(y):
    if pd.isna(y): return 'Unknown'
    if y>=2023: return '2023-2026'
    if y>=2020: return '2020-2022'
    if y>=2016: return '2016-2019'
    return '2011-2015'
s['YrBand']=s['Year'].map(yrband)
# outlier flag (data quality) on front gross
s['Outlier']= (s['Front']>15000)|(s['Front']<-10000)
clean=s[~s['Outlier']].copy()

print("=== SOLD: total rows", len(s), "| outliers excluded from averages:", s['Outlier'].sum(), "===")
print(s[s['Outlier']][['Year','Make','Model','Front','Back','Days','Source']].to_string())
print("\n=== STORE AVG (clean) ===")
print("Front %.0f Back %.0f Total %.0f  | avg days %.1f  | n=%d"%(
    clean['Front'].mean(),clean['Back'].mean(),clean['Total'].mean(),clean['Days'].mean(),len(clean)))

print("\n=== SOURCE BREAKDOWN (clean) ===")
g=clean.groupby('Source').agg(n=('Total','size'),Front=('Front','mean'),Back=('Back','mean'),
    Total=('Total','mean'),Days=('Days','mean'))
print(g.round(0).to_string())

print("\n=== FAST vs SLOW (21d) ===")
clean['Fast']=clean['Days']<21
print(clean.groupby('Fast').agg(n=('Days','size'),Front=('Front','mean'),Total=('Total','mean'),Days=('Days','mean')).round(0).to_string())

print("\n=== VELOCITY by MODEL (Toyota, n>=2) ===")
tv=clean[clean['Make']=='Toyota'].groupby('Model').agg(n=('Days','size'),Days=('Days','mean'),
    Front=('Front','mean'),Total=('Total','mean')).query('n>=2').sort_values('Days')
print(tv.round(0).to_string())

print("\n=== GROSS by MODEL (Toyota n>=2) ===")
print(tv.sort_values('Total',ascending=False).round(0).to_string())

print("\n=== Source by model Toyota (front gross) ===")
sm=clean[clean['Make']=='Toyota'].groupby(['Model','Source']).agg(n=('Total','size'),Front=('Front','mean'),Total=('Total','mean'),Days=('Days','mean'))
print(sm.round(0).to_string())

print("\n\n########## INVENTORY ##########")
inv=pd.read_excel(INV)
inv['Year']=pd.to_numeric(inv['Vehicle'].str.split().str[0],errors='coerce')
inv['Make']=inv['Vehicle'].str.split().str[1].str.title()
def invmodel(v):
    p=str(v).split()
    if len(p)<3: return 'Unknown'
    m=p[2]
    two=' '.join(p[2:4]) if len(p)>=4 else m
    if two in ('Grand Highlander','Land Cruiser'): return two
    return m
inv['Model']=inv['Vehicle'].map(invmodel)
inv['Asking']=pd.to_numeric(inv['AskingPrice'],errors='coerce')
inv['Cost']=pd.to_numeric(inv['Cost'],errors='coerce')
inv['Odo']=pd.to_numeric(inv['Odometer'],errors='coerce')
inv['AgeD']=pd.to_numeric(inv['Age'],errors='coerce')
inv['SrcProxy']=np.where(inv['Appr. Salesperson'].notna(),'Trade(inferred)','Auction/Other(inferred)')

print("Inv units:",len(inv)," Toyota:",(inv['Make']=='Toyota').sum())

# DAYS SUPPLY by model (all makes with stock)
soldcnt=clean.groupby(['Make','Model']).size().rename('sold30')
invcnt=inv.groupby(['Make','Model']).size().rename('instock')
ds=pd.concat([soldcnt,invcnt],axis=1).fillna(0)
ds['daily']=ds['sold30']/30
ds['days_supply']=np.where(ds['daily']>0, ds['instock']/ds['daily'], np.inf)
ds['sellthru']=ds['sold30']/(ds['sold30']+ds['instock'])
def band(d):
    if d==np.inf: return 'No sales (dead)'
    if d<30: return 'THIN (buy)'
    if d<60: return 'Healthy'
    if d<90: return 'Heavy'
    return 'Overstock'
ds['band']=ds['days_supply'].map(band)
toy=ds[(ds.index.get_level_values('Make')=='Toyota')&((ds['instock']>0)|(ds['sold30']>0))].copy()
print("\n=== TOYOTA DAYS SUPPLY / SELL-THROUGH ===")
print(toy.sort_values('days_supply').round(2).to_string())

print("\n=== AGED 60+ UNITS ===")
aged=inv[inv['AgeD']>60].sort_values('AgeD',ascending=False)
print(aged[['Vehicle','AgeD','Asking','Cost','SrcProxy','Odo']].to_string())
print("Total tied up (asking) in 60+:", aged['Asking'].sum(), " total cost:", aged['Cost'].sum())

print("\n=== NEGATIVE FRONT DEALS (sold, clean) ===")
neg=clean[clean['Front']<0]
print("count",len(neg),"avg age",round(neg['Days'].mean(),1),"avg year",round(neg['Year'].mean(),1))
print(neg.groupby('Source').agg(n=('Front','size'),Front=('Front','mean'),Days=('Days','mean')).round(0).to_string())
print(neg.groupby('Model').size().sort_values(ascending=False).head(8).to_string())

# Mileage profile from inventory (proxy, since sold has none)
print("\n=== MILEAGE PROFILE current inv by model (Toyota n>=2) ===")
mp=inv[inv['Make']=='Toyota'].groupby('Model').agg(n=('Odo','size'),Odo=('Odo','median')).query('n>=2').sort_values('Odo')
print(mp.round(0).to_string())

# --- REAL mileage (now in sold feed) ---
fast=clean[clean['Days']<21]; slow=clean[clean['Days']>=21]
milesummary={
 'fast':{'n':len(fast),'miles':fast['Miles'].median(),'year':fast['Year'].median(),
         'tradepct':(fast['Source']=='Trade').mean()*100,'retail':fast['Retail'].median()},
 'slow':{'n':len(slow),'miles':slow['Miles'].median(),'year':slow['Year'].median(),
         'tradepct':(slow['Source']=='Trade').mean()*100,'retail':slow['Retail'].median()},
}
print("\n=== REAL MILEAGE fast vs slow ==="); print(milesummary)
# mileage by Toyota model (real)
milemodel=clean[clean['Make']=='Toyota'].groupby('Model').agg(
    n=('Miles','size'),Miles=('Miles','median'),Retail=('Retail','median'),Days=('Days','mean')).query('n>=3').sort_values('Miles')
print(milemodel.round(0).to_string())

# --- PRICE BANDS (real retail) ---
def pband(p):
    if pd.isna(p): return 'Unknown'
    if p<20000: return 'Under $20k'
    if p<30000: return '$20k–$30k'
    if p<40000: return '$30k–$40k'
    if p<50000: return '$40k–$50k'
    return '$50k+'
clean['PB']=clean['Retail'].map(pband)
pborder=['Under $20k','$20k–$30k','$30k–$40k','$40k–$50k','$50k+']
pbtab=clean[clean['PB']!='Unknown'].groupby('PB').agg(
    n=('Total','size'),Days=('Days','mean'),F=('Front','mean'),B=('Back','mean'),
    T=('Total','mean'),Mi=('Miles','median')).reindex([p for p in pborder])
pbtab=pbtab.dropna(subset=['n'])
print("\n=== PRICE BANDS (real retail) ==="); print(pbtab.round(0).to_string())

# model median sold retail for buy-list anchor
modelretail=clean[clean['Make']=='Toyota'].groupby('Model')['Retail'].median()

# Save objects for PDF
import pickle
pickle.dump({'clean':clean,'s':s,'inv':inv,'ds':ds,'toy':toy,'aged':aged,'neg':neg,
             'tv':tv,'sm':sm,'mp':mp,'milesummary':milesummary,'milemodel':milemodel,
             'pbtab':pbtab,'modelretail':modelretail}, open('/home/user/hariluker/report/data.pkl','wb'))
print("\nSAVED pickle.")
