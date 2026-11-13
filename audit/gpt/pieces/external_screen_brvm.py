import csv,json,datetime,statistics,concurrent.futures,urllib.request,time,math
from pathlib import Path
ROOT=Path('/workspace/scratch/d5a74612ae4a'); OUT=ROOT/'external_screen_raw';OUT.mkdir(exist_ok=True)
codes=set()
for schema in ['PANIQUE','EVEIL','CASSURE']:
 codes.update(r['code'] for r in csv.DictReader(open(ROOT/'upload'/('cas_'+schema+'.csv'))))
codes.update(['BBGC','BICB','LNBB','ORAC','UNLC'])
def fetch(code):
 p=OUT/(code+'.json')
 existing={'ORGT':ROOT/'orgt_api_raw.json','SIVC':ROOT/'external_audit_SIVC_raw.json','SNTS':ROOT/'external_audit_SNTS_raw.json'}.get(code)
 if p.exists():return code,json.loads(p.read_text()),'cached'
 if existing and existing.exists():
  j=json.loads(existing.read_text());p.write_text(json.dumps(j));return code,j,'reused'
 u='https://www.richbourse.com/common/mouvements/technique-donnees?symbole='+code+'&complet=1'
 try:
  req=urllib.request.Request(u,headers={'Referer':'https://www.richbourse.com/common/mouvements/technique/'+code,'User-Agent':'Mozilla/5.0','X-Requested-With':'XMLHttpRequest'})
  with urllib.request.urlopen(req,timeout=20) as r:b=r.read()
  j=json.loads(b);p.write_bytes(b);return code,j,'fetched'
 except Exception as e:return code,{'error':str(e)},'error'
def stats(code,j):
 if 'ohlc' not in j:return {'code':code,'error':j.get('error',str(j)[:200])}
 vd=dict(j['volume']);a=[{'date':datetime.datetime.fromtimestamp(x[0]/1000,datetime.timezone.utc).date().isoformat(),'o':x[1],'h':x[2],'l':x[3],'c':x[4],'v':vd.get(x[0],0)} for x in j['ohlc'] if x[4]>0 and x[0]<=1794527999999]
 a.sort(key=lambda x:x['date']);c=[x['c'] for x in a];N=len(c)
 if N<15:return {'code':code,'n':N,'last':a[-1] if a else None}
 n=14;g=sum(max(c[k]-c[k-1],0) for k in range(1,n+1))/n;l=sum(max(c[k-1]-c[k],0) for k in range(1,n+1))/n
 for k in range(n+1,N):g=(13*g+max(c[k]-c[k-1],0))/14;l=(13*l+max(c[k-1]-c[k],0))/14
 rsi=100-100/(1+g/l) if l>0 else 100
 price=c[-1];today=a[-1]['date'];five_start=str(int(today[:4])-5)+today[4:];five=[x['c'] for x in a if x['date']>=five_start]
 out={'code':code,'n':N,'date':today,'price':price,'rsi14':rsi,'vol':a[-1]['v'],'zone_minmax5':(price-min(five))/(max(five)-min(five)) if max(five)>min(five) else None,'rank5_le':sum(x<=price for x in five)/len(five),'first5':next(x['date'] for x in a if x['date']>=five_start),'max5':max(five),'min5':min(five)}
 for window in [20,60,250]:
  b=a[max(0,N-window-1):N-1];out['prior'+str(window)+'_n']=len(b)
  out['high'+str(window)+'_close']=max(x['c'] for x in b);out['low'+str(window)+'_close']=min(x['c'] for x in b)
  out['high'+str(window)+'_intraday']=max(x['h'] for x in b);out['low'+str(window)+'_intraday']=min(x['l'] for x in b)
  out['r'+str(window)]=price/c[-window-1]-1 if N>window else None
  if window in [20,60]:
   out['volmed'+str(window)]=statistics.median(x['v'] for x in b);out['volmean'+str(window)]=statistics.mean(x['v'] for x in b)
   out['amountmed'+str(window)+'_approx']=statistics.median(x['v']*x['c'] for x in b);out['amountmean'+str(window)+'_approx']=statistics.mean(x['v']*x['c'] for x in b)
 for w in [20,50,200]:out['ma'+str(w)]=statistics.mean(c[-w:]) if N>=w else None
 out['volratio60']=a[-1]['v']/out['volmed60'] if out['volmed60'] else None
 out['distance_high250']=price/out['high250_close']-1
 breaks=[]
 for i in range(max(250,N-60),N):
  prev=max(c[i-250:i])
  if c[i]>prev:breaks.append({'date':a[i]['date'],'age':N-1-i,'price':c[i],'prior250high':prev,'vol':a[i]['v'],'volratio60':a[i]['v']/statistics.median(x['v'] for x in a[i-60:i]) if statistics.median(x['v'] for x in a[i-60:i]) else None})
 out['breakouts60']=breaks
 out['badjumps60']=[{'date':a[i]['date'],'r':c[i]/c[i-1]-1} for i in range(max(1,N-60),N) if abs(c[i]/c[i-1]-1)>.12]
 return out
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 for code,j,status in ex.map(fetch,sorted(codes)):
  results.append(stats(code,j))
(ROOT/'external_screen_metrics.json').write_text(json.dumps(results,indent=2))
for r in results:
 if 'price' not in r:print(r);continue
 print(r['code'],r['date'],'P',r['price'],'RSI',round(r['rsi14'],1),'r20',round(100*r['r20'],1) if r['r20'] is not None else None,'r60',round(100*r['r60'],1) if r['r60'] is not None else None,'distH250',round(100*r['distance_high250'],1),'Vmed60',round(r['volmed60']),'AmtMedM',round(r['amountmed60_approx']/1e6,1),'Vratio',round(r['volratio60'],2) if r['volratio60'] is not None else None,'lastbreak',r['breakouts60'][-1] if r['breakouts60'] else None,'badjumps',r['badjumps60'])
