import csv,json,statistics,math,datetime
from pathlib import Path
ROOT=Path('/workspace/scratch/d5a74612ae4a')
j=json.loads((ROOT/'orgt_api_raw.json').read_text()); vs=dict(j['volume'])
a=[{'d':datetime.datetime.fromtimestamp(x[0]/1000,datetime.timezone.utc).date().isoformat(),'o':x[1],'h':x[2],'l':x[3],'c':x[4],'v':vs[x[0]]} for x in j['ohlc']]
ix={r['d']:i for i,r in enumerate(a)}; c=[r['c'] for r in a]
def calc_rsi(c,n=14):
 out=[None]*len(c); g=sum(max(c[k]-c[k-1],0) for k in range(1,n+1))/n; l=sum(max(c[k-1]-c[k],0) for k in range(1,n+1))/n
 def value(g,l): return 100-100/(1+g/l) if l>0 else 100 if g>0 else 50
 out[n]=value(g,l)
 for k in range(n+1,len(c)):
  g=(g*(n-1)+max(c[k]-c[k-1],0))/n; l=(l*(n-1)+max(c[k-1]-c[k],0))/n; out[k]=value(g,l)
 return out
rsi=calc_rsi(c)
def first(seq,pred): return next((i+1 for i,x in enumerate(seq) if pred(x)),None)
allout=[]
for schema in ['PANIQUE','EVEIL','CASSURE']:
 with (ROOT/'upload'/('cas_'+schema+'.csv')).open() as f: rows=[x for x in csv.DictReader(f) if x['code']=='ORGT']
 for r in rows:
  d=r['date_signal']; i=ix.get(d)
  if i is None: allout.append({'schema':schema,'date':d,'not_found':True}); continue
  b=a[i]; p=float(r['cours_signal']); future=a[i+1:i+253]; fs=[x['c']/b['c']-1 for x in future]
  w=c[max(0,i-1260):i+1]
  ystart=datetime.date.fromisoformat(d).replace(year=int(d[:4])-5).isoformat(); cal=[x['c'] for x in a[:i+1] if x['d']>=ystart]
  zone=lambda w:(b['c']-min(w))/(max(w)-min(w)) if max(w)>min(w) else 0
  strict=lambda w:sum(x<b['c'] for x in w)/len(w)
  stop=first(fs,lambda v:v<=-.15)
  changes=[c[k]-c[k-1] for k in range(i-13,i+1)]
  gg=sum(max(x,0) for x in changes); ll=sum(max(-x,0) for x in changes)
  sma_rsi=100-100/(1+gg/ll) if ll>0 else 100
  out={'schema':schema,'date':d,'api_i':i,'csv_price':p,'api_price':b['c'],'csv_v':float(r['volume_jour']),'api_v':b['v'],'csv_medv':float(r['volume_median_60j']),'api_medv':statistics.median(x['v'] for x in a[max(0,i-60):i]),'rsi_wilder14':round(rsi[i],4),'rsi_sma14':round(sma_rsi,4),'eveil_growth60':b['c']/min(c[max(0,i-60):i])-1,'break250':b['c']>max(c[max(0,i-250):i]),'zone_csv':float(r['zone_minmax']),'zone_1261':zone(w),'zone_cal5':zone(cal),'rank_csv':float(r['percentile_rang']),'rank_1261':strict(w),'rank_cal5':strict(cal),'future_n':len(future),'exit_date':future[-1]['d'],'ret_csv':float(r['rendement_12m_net']),'ret_api':fs[-1]-.028,'peak_csv':float(r['pic_max_12m']),'peak_api_close':max(fs),'peak_api_high':max(x['h']/b['c']-1 for x in future),'trough_csv':float(r['creux_min_12m']),'trough_api_close':min(fs),'trough_api_low':min(x['l']/b['c']-1 for x in future),'stop_csv':int(r['jours_avant_stop']) if r['jours_avant_stop'] else None,'stop_api':stop,'targets':{}}
  for name,t in [('p20',.2),('p35',.35),('p50',.5)]:
   k=first(fs,lambda v:v>=t)
   out['targets'][name]={'day_csv':int(r[name+'_jour']) if r[name+'_jour'] else None,'day_api':k,'before_csv':r[name+'_avant_stop']=='True','before_api':k is not None and (stop is None or k<stop)}
  allout.append(out)
(ROOT/'external_audit_orgt_results.json').write_text(json.dumps(allout,indent=2))
print('Summary',{'n':len(allout),'date_found':sum('not_found' not in r for r in allout),'price_exact':sum(r.get('api_price')==r.get('csv_price') for r in allout),'volume_exact':sum(r.get('api_v')==r.get('csv_v') for r in allout),'ret_close_rounded':sum(abs(r.get('ret_csv',9)-r.get('ret_api',0))<.00006 for r in allout),'ret_dif_over_5pp':sum(abs(r.get('ret_csv',9)-r.get('ret_api',0))>.05 for r in allout)})
for r in allout:
 print(json.dumps({k:r[k] for k in ['schema','date','csv_price','api_price','csv_v','api_v','rsi_wilder14','rsi_sma14','eveil_growth60','break250','zone_csv','zone_1261','ret_csv','ret_api','exit_date','peak_csv','peak_api_close','trough_csv','trough_api_close','stop_csv','stop_api','targets']}))
