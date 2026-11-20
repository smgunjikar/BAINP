"""Experimental personal-change screening v1; deterministic, no diagnosis.
Daily medians avoid counting dense sampling as independent baseline days.
Only identical device/method/protocol streams are compared. Historical window
is 28 days; minimum 14 observed days. Threshold is a research heuristic.
"""
from datetime import datetime,timedelta
from statistics import median
from collections import defaultdict
VERSION='sense-personal-change-v1'
FLOORS={'heart_rate':5.0,'sleep_duration':0.5,'steps':1000.0,'movement_rms':0.02}
def analyze(items):
 groups=defaultdict(list)
 for x in items:
  if x['quality']=='usable':groups[(x['metric'],x['unit'],x['device'],x['method'],x['protocol'])].append(x)
 results=[]
 for key,values in groups.items():
  metric,unit,device,method,protocol=key;days=defaultdict(list)
  for v in values:
   day=datetime.fromisoformat(v['timestamp'].replace('Z','+00:00')).date();days[day].append(v['value'])
  latest=max(days);history={d:median(v) for d,v in days.items() if latest-timedelta(days=28)<=d<latest}
  entry=dict(metric=metric,unit=unit,device=device,method=method,protocol=protocol,latest_day=latest.isoformat(),baseline_days=len(history),missing_baseline_days=28-len(history),state='insufficient_evidence')
  if metric not in FLOORS:entry['reason']='unsupported_metric'
  elif len(history)<14:entry['reason']='requires_14_observed_baseline_days'
  elif metric in ('steps','sleep_duration') and any(len(v)>1 for v in days.values()):entry['reason']='daily_summary_duplicates_or_overlapping_intervals_require_review'
  else:
   base=median(history.values());mad=median(abs(v-base) for v in history.values());scale=max(1.4826*mad,FLOORS[metric]);current=median(days[latest]);score=(current-base)/scale
   entry.update(state='unusual_change' if abs(score)>=3 else 'within_research_band',baseline_median=base,current_daily_median=current,difference=current-base,robust_score=round(score,3),threshold=3.0,aggregation='UTC daily median; daily totals required for steps and sleep',reason='experimental_statistical_screen_not_clinical_threshold')
  results.append(entry)
 return dict(version=VERSION,streams=results,excluded_observations=sum(x['quality']!='usable' for x in items),interpretation='Statistical deviations only. Cause, disease and clinical significance are not established.',continuous_collection=False)
