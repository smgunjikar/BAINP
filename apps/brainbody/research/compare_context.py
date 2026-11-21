"""Offline participant-separated baseline-vs-context cognitive-change comparison.
No clinical deployment, causal effect, disease probability or universal biomarker model.
"""
import argparse,csv,json,math
from datetime import datetime,timezone
from pathlib import Path
BASE=['baseline_score','age','education_years'];CONTEXT=['bp_systolic','hba1c_percent','sleep_hours']
REQUIRED=['cohort','participant_id','index_time','feature_available_at','target_time','cognitive_instrument','cognitive_version','bp_context','hba1c_assay','hba1c_specimen','sleep_source',*BASE,'target_score',*CONTEXT]
def time(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timezone-aware timestamps required')
    return d.astimezone(timezone.utc)
def load(path):
    rows=[];ids=set();contexts=set();cohorts=set()
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not set(REQUIRED)<=set(reader.fieldnames or []):raise ValueError('Required analysis columns missing: '+str(sorted(set(REQUIRED)-set(reader.fieldnames or []))))
        for r in reader:
            if not r['participant_id'] or r['participant_id'] in ids:raise ValueError('One globally resolved baseline per participant required')
            ids.add(r['participant_id']);cohorts.add(r['cohort']);contexts.add(tuple(r[k] for k in ['cognitive_instrument','cognitive_version','bp_context','hba1c_assay','hba1c_specimen','sleep_source']))
            if any(not r[k] for k in ['cohort','cognitive_instrument','cognitive_version','bp_context','hba1c_assay','hba1c_specimen','sleep_source']):raise ValueError('Instrument, assay and source context cannot be blank')
            index,available,target=map(time,[r['index_time'],r['feature_available_at'],r['target_time']])
            if available>index:raise ValueError('Future-context leakage: feature became available after prediction index')
            if target>datetime.now(timezone.utc) or index>=target:raise ValueError('Unobserved/future or unordered outcome')
            if not 335<=(target-index).total_seconds()/86400<=395:raise ValueError('This predeclared comparison requires 12-month follow-up within 30 days')
            values={}
            for k in BASE+CONTEXT+['target_score']:
                values[k]=float(r[k]) if r[k].strip() else float('nan')
                if r[k].strip() and not math.isfinite(values[k]):raise ValueError('Nonfinite supplied values')
            if any(not math.isfinite(values[k]) for k in BASE+['target_score']):raise ValueError('Baseline covariates and target cannot be missing')
            if not 18<=values['age']<=110 or not 0<=values['education_years']<=40:raise ValueError('Unsupported demographic range')
            if any(math.isfinite(values[k]) and not lo<=values[k]<=hi for k,lo,hi in [('bp_systolic',0,float('inf')),('hba1c_percent',0,100),('sleep_hours',0,24)]):raise ValueError('Context value outside its declared physical/unit range')
            rows.append(values|dict(subgroup=r.get('subgroup','not_supplied')))
    if len(cohorts)!=1 or len(contexts)!=1:raise ValueError('Analyse one cohort and one prespecified instrument/assay/source context at a time; do not fuse unrelated people or assays')
    if len(rows)<30:raise ValueError('At least 30 independent participants required for this engineering workflow; this is not a scientific power calculation')
    return rows,dict(cohort=next(iter(cohorts)),context=next(iter(contexts)))
def compare(path,out,seed=602):
    import numpy as np,sklearn
    from sklearn.model_selection import KFold
    from sklearn.pipeline import make_pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    rows,metadata=load(path);target=np.array([r['target_score']-r['baseline_score'] for r in rows]);pred={name:np.empty(len(rows)) for name in ['baseline','with_context']};folds=[]
    split=KFold(n_splits=5,shuffle=True,random_state=seed)
    for fold,(train,test) in enumerate(split.split(rows),1):
        metrics={}
        for name,features in [('baseline',BASE),('with_context',BASE+CONTEXT)]:
            X=np.array([[r[k] for k in features] for r in rows]);model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler(),Ridge(alpha=1.))
            model.fit(X[train],target[train]);p=model.predict(X[test]);pred[name][test]=p;metrics[name]=dict(mae=float(np.mean(abs(target[test]-p))),rmse=float(np.sqrt(np.mean((target[test]-p)**2))))
        folds.append(dict(fold=fold,train_participants=len(train),test_participants=len(test),metrics=metrics))
    errors={name:abs(target-p) for name,p in pred.items()};delta=errors['with_context']-errors['baseline'];rng=np.random.default_rng(seed)
    boot=sorted(float(np.mean(delta[rng.integers(0,len(rows),len(rows))])) for _ in range(500))
    subgroup={}
    for group in sorted({r['subgroup'] for r in rows}):
        indices=np.array([i for i,r in enumerate(rows) if r['subgroup']==group]);subgroup[group]=dict(n=len(indices),mae={name:float(np.mean(e[indices])) for name,e in errors.items()} if len(indices)>=10 else None,note='Small-group estimates suppressed' if len(indices)<10 else 'Descriptive subgroup audit; not a fairness certification')
    result=dict(version='bbc-context-comparison-v1',**metadata,n=len(rows),target='12-month cognitive-score change',seed=seed,sklearn=sklearn.__version__,participant_separated=True,
        folds=folds,overall={name:dict(mae=float(np.mean(e)),rmse=float(np.sqrt(np.mean((target-pred[name])**2)))) for name,e in errors.items()},
        paired_context_minus_baseline_mae=float(np.mean(delta)),paired_error_bootstrap_interval=[boot[12],boot[487]],
        interval_note='Descriptive participant resampling conditional on these cross-validated predictions; fold dependence and all uncertainty are not covered.',
        missing_context={k:sum(not math.isfinite(r[k]) for r in rows) for k in CONTEXT},subgroups=subgroup,
        interpretation='Negative paired error difference indicates lower observed prediction error in this evaluation. More context is not assumed to help. No causal benefit or disease probability is established.',
        limitations=['Single-cohort retrospective comparison, no external evaluation or clinical deployment.','Owner must resolve aliases and verify source availability; code cannot independently verify clinical identities.','BP in mmHg, HbA1c in %, sleep in hours are explicit input definitions, not auto-converted.','Five-fold training-only imputation/scaling; prespecified Ridge alpha 1, no model selection.'])
    out.mkdir(parents=True,exist_ok=True);(out/'comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False));print('REPORT:',out/'comparison.json');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();compare(a.input,a.output)
