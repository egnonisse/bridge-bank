import csv, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path('/workspace/scratch/d5a74612ae4a')
UP=ROOT/'upload'
SCHEMAS=['PANIQUE','EVEIL','CASSURE']
bools=['stop_15_touche']+[f'p{p}_{x}' for p in [20,35,50] for x in ['touche','avant_stop']]
days=['jours_avant_stop']+[f'p{p}_jour' for p in [20,35,50]]
nums=['cours_signal','zone_minmax','percentile_rang','rendement_12m_net','pic_max_12m','creux_min_12m','volume_jour','volume_median_60j']
def quant(v,q):
 v=sorted(v)
 if not v:return None
 x=(len(v)-1)*q;a=int(x);b=min(a+1,len(v)-1)
 return v[a]+(v[b]-v[a])*(x-a)
def dist(v):
 if not v:return {'n':0}
 return {'n':len(v),'mean':statistics.mean(v),'median':statistics.median(v),'q05':quant(v,.05),'q25':quant(v,.25),'q75':quant(v,.75),'q95':quant(v,.95),'min':min(v),'max':max(v)}
rows={}
for s in SCHEMAS:
 with (UP/f'cas_{s}.csv').open(encoding='utf-8-sig') as f:
  rr=list(csv.DictReader(f))
 for i,r in enumerate(rr,2):
  r['_line']=i
  for c in bools:r[c]={'True':True,'False':False}[r[c]]
  for c in days:r[c]=int(r[c]) if r[c] else None
  for c in nums:r[c]=float(r[c]) if r[c] else None
  r['_year']=r['date_signal'][:4]
  r['_volume_ok']=r['volume_median_60j'] is not None and r['volume_median_60j']>0 and r['volume_jour']>=r['volume_median_60j']
  r['_gross12']=r['rendement_12m_net']+.028
  errors=[]
  if r['stop_15_touche']!=(r['jours_avant_stop'] is not None):errors.append('stop_bool_day')
  if r['stop_15_touche'] and r['creux_min_12m']>-.15+.00005:errors.append('stop_true_min_above')
  if not r['stop_15_touche'] and r['creux_min_12m']<-.15-.00005:errors.append('stop_false_min_below')
  if r['_gross12']<r['creux_min_12m']-.00011:errors.append('final_below_min')
  if r['_gross12']>r['pic_max_12m']+.00011:errors.append('final_above_max')
  if r['creux_min_12m']>r['pic_max_12m']:errors.append('min_above_max')
  for c in days:
   if r[c] is not None and not (1<=r[c]<=252):errors.append('day_outside_'+c)
  prev=None
  for p in [20,35,50]:
   day=r[f'p{p}_jour']; touch=r[f'p{p}_touche']; before=r[f'p{p}_avant_stop']
   if touch!=(day is not None):errors.append(f'p{p}_bool_day')
   expected=bool(day is not None and (r['jours_avant_stop'] is None or day<r['jours_avant_stop']))
   if before!=expected:errors.append(f'p{p}_before_disagrees_day')
   if day is not None and day==r['jours_avant_stop']:errors.append(f'p{p}_stop_same_day')
   if touch and r['pic_max_12m']<p/100-.00005:errors.append(f'p{p}_true_max_below')
   if not touch and r['pic_max_12m']>p/100+.00005:errors.append(f'p{p}_false_max_above')
   if p>20 and touch and (prev is None or day<prev):errors.append(f'p{p}_sequence')
   prev=day
  z=r['zone_minmax'];expectedzone='0-20' if z<.2 else '20-40' if z<.4 else '40-60' if z<.6 else '60-80' if z<.8 else '80-100'
  if r['zone_tranche']!=expectedzone:errors.append('zone_tranche')
  r['_errors']=errors
  # Pure arithmetic reconstruction. Remains conditional on accurate/export-consistent paths.
  sale=[p/100 for p in [20,35,50] if r[f'p{p}_avant_stop']]
  k=len(sale);remain=3-k
  exit_r=-.15 if r['stop_15_touche'] else r['_gross12']
  r['_plan_gross']=(sum(sale)+remain*exit_r)/3
  r['_plan_net']=r['_plan_gross']-.028
  r['_k']=k
  r['_plan_cat']=f'{k}_targets_then_'+('stop' if r['stop_15_touche'] and k<3 else 'full' if k==3 else 'horizon')
 rows[s]=rr

def agg(rr):
 n=len(rr)
 if not n:return {'n':0}
 out={'n':n,'codes':len(set(r['code'] for r in rr)),'first':min(r['date_signal'] for r in rr),'last':max(r['date_signal'] for r in rr),'win_count':sum(r['rendement_12m_net']>0 for r in rr),'win':sum(r['rendement_12m_net']>0 for r in rr)/n,'median':statistics.median(r['rendement_12m_net'] for r in rr),'hold12_dist':dist([r['rendement_12m_net'] for r in rr]),'stop_count':sum(r['stop_15_touche'] for r in rr),'stop_touche':sum(r['stop_15_touche'] for r in rr)/n,'stop_day_dist':dist([r['jours_avant_stop'] for r in rr if r['stop_15_touche']]),'drawdown_dist':dist([r['creux_min_12m'] for r in rr]),'max_dist':dist([r['pic_max_12m'] for r in rr]),'plan_net_dist':dist([r['_plan_net'] for r in rr]),'plan_win_count':sum(r['_plan_net']>0 for r in rr),'plan_win':sum(r['_plan_net']>0 for r in rr)/n,'plan_categories':dict(Counter(r['_plan_cat'] for r in rr)),'invalid_count':sum(bool(r['_errors']) for r in rr)}
 for p in [20,35,50]:
  for end in ['avant_stop','touche']:
   name=f'p{p}_'+('touche_sans_contrainte' if end=='touche' else end)
   out[name+'_count']=sum(r[f'p{p}_{end}'] for r in rr)
   out[name]=out[name+'_count']/n
 return out

saved=json.loads((UP/'resume.json').read_text())
out={'definitions':{'plan':'equal thirds at .20/.35/.50 if before first stop; unsold units -.15 at stop or final gross=net+.028 at J252; subtract .028 once','error_tolerance':.00011},'schemas':{},'json_mismatches':[],'errors':[]}
for s,rr in rows.items():
 total=agg(rr);zones={z:agg([r for r in rr if r['zone_tranche']==z]) for z in ['0-20','20-40','40-60','60-80','80-100']}
 d={'total':total,'zones':zones,'volume_ok':agg([r for r in rr if r['_volume_ok']]),'volume_and_zone2040':agg([r for r in rr if r['_volume_ok'] and r['zone_tranche']=='20-40']),'by_year':{y:agg([r for r in rr if r['_year']==y]) for y in sorted(set(r['_year'] for r in rr))},'by_year_zone2040':{y:agg([r for r in rr if r['_year']==y and r['zone_tranche']=='20-40']) for y in sorted(set(r['_year'] for r in rr))},'orgt':agg([r for r in rr if r['code']=='ORGT']),'without_orgt':agg([r for r in rr if r['code']!='ORGT']),'orgt_zone2040':agg([r for r in rr if r['code']=='ORGT' and r['zone_tranche']=='20-40']),'without_orgt_zone2040':agg([r for r in rr if r['code']!='ORGT' and r['zone_tranche']=='20-40']),'valid_only':agg([r for r in rr if not r['_errors']]),'valid_only_zone2040':agg([r for r in rr if not r['_errors'] and r['zone_tranche']=='20-40']),'orgt_rows':[r for r in rr if r['code']=='ORGT']}
 out['schemas'][s]=d
 for group,actual,expect in [('total',total,saved[s]['total'])]+[(z,zones[z],v) for z,v in saved[s]['zones'].items()]:
  for key,v in expect.items():
   if round(actual[key],3)!=v:out['json_mismatches'].append({'schema':s,'group':group,'key':key,'csv':actual[key],'json':v})
 for r in rr:
  if r['_errors']:out['errors'].append(r)
(ROOT/'aggregate_audit_results.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
print('JSON_MISMATCHES',json.dumps(out['json_mismatches']))
for s,d in out['schemas'].items():
 print('\nSCHEMA',s)
 for label in ['total','volume_ok','volume_and_zone2040','orgt','without_orgt','orgt_zone2040','without_orgt_zone2040','valid_only','valid_only_zone2040']:
  a=d[label];print(label,json.dumps(a))
 print('ZONES',json.dumps({z:{k:v for k,v in a.items() if k in ['n','win_count','win','median','stop_count','p20_avant_stop_count','p35_avant_stop_count','p50_avant_stop_count','plan_net_dist','plan_win','invalid_count']} for z,a in d['zones'].items()}))
 print('YEARS',json.dumps({z:{k:v for k,v in a.items() if k in ['n','win','median','stop_touche','p20_avant_stop','plan_net_dist','plan_win','invalid_count']} for z,a in d['by_year'].items()}))
 print('YEARS_ZONE2040',json.dumps({z:{k:v for k,v in a.items() if k in ['n','win','median','stop_touche','p20_avant_stop','plan_net_dist','plan_win','invalid_count']} for z,a in d['by_year_zone2040'].items()}))
print('\nERROR_COUNTS',dict(Counter(e for r in out['errors'] for e in r['_errors'])))
for r in out['errors']:print('ERROR_ROW',r['schema'],r['code'],r['date_signal'],r['_line'],r['_errors'])
