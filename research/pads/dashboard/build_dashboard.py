"""Build a local, read-only NeuroSense research dashboard from a nested-v2 report.
Validates saved predictions against summary metrics; never runs patient inference.
"""
import argparse,csv,json,hashlib,html
from pathlib import Path
from collections import Counter

def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def build(root):
 r=json.loads((root/'comparison.json').read_text(encoding='utf-8-sig'))
 if r.get('version')!='neurosense-nested-v2' or r.get('smoke_only') is not False:raise ValueError('Requires a full nested-v2 report')
 for target,t in r['targets'].items():
  if target not in {'six_class','pd_vs_healthy','pd_vs_other_movement'}:raise ValueError('Unknown target')
  folder=root/target;cohort=rows(folder/'cohort_and_folds.csv');pred=rows(folder/'held_out_predictions.csv');features=rows(folder/'selected_features.csv')
  ids={v['participant']:v for v in cohort}
  if len(ids)!=len(cohort) or len(ids)!=t['participants']:raise ValueError('Duplicate/missing participants')
  if dict(Counter(v['condition'] for v in cohort))!=t['class_counts']:raise ValueError('Class counts differ')
  for model,s in t['models'].items():
   pp=[v for v in pred if v['model']==model]
   if len(pp)!=len(ids) or set(v['participant'] for v in pp)!=set(ids):raise ValueError('Prediction coverage mismatch')
   classes=t['classes'];cm=[[0]*len(classes) for _ in classes]
   for v in pp:
    c=ids[v['participant']]
    if v['actual']!=c['condition'] or v['fold']!=c['fold']:raise ValueError('Fold or label mismatch')
    cm[classes.index(v['actual'])][classes.index(v['predicted'])]+=1
   ba=sum(cm[i][i]/sum(cm[i]) for i in range(len(classes)))/len(classes)
   if cm!=s['confusion_matrix'] or abs(ba-s['balanced_accuracy'])>1e-10:raise ValueError('Metrics do not match predictions')
   counts=Counter(v['feature'] for v in features if v['model']==model)
   s['stable_features']=[{'feature':k,'folds':v} for k,v in counts.most_common(25)]
   if any(v>5 for v in counts.values()):raise ValueError('Duplicate selected features')
  print('PASS:',target,len(ids),'participants; predictions and confusion matrices verified')
 r['report_sha256']=hashlib.sha256((root/'comparison.json').read_bytes()).hexdigest()
 # No participant-level records are embedded in this aggregate dashboard.
 data=json.dumps(r).replace('<','\\u003c')
 template=Path(__file__).with_name('dashboard_template.html').read_text(encoding='utf-8')
 out=root/'neurosense_dashboard.html';out.write_text(template.replace('__DATA__',data),encoding='utf-8');print('DASHBOARD:',out)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args();build(a.report)
