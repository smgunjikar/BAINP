"""Nested-CV clinical benchmark. Requires numpy, pandas, scikit-learn."""
import argparse, hashlib, json, platform
from pathlib import Path
import numpy as np
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, GridSearchCV

FEATURES=['earlier_age','earlier_educ','earlier_mmse','earlier_cdr']
ALPHAS=[0.01,0.1,1.0,10.0,100.0,1000.0]

def require(ok,msg):
    if not ok: raise ValueError(msg)

def scores(y,p):
    return {'MAE':float(np.mean(np.abs(y-p))), 'RMSE':float(np.sqrt(np.mean((y-p)**2)))}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=Path.home()/'BAINP_DATA')
    ap.add_argument('--cohort-dir',type=Path)
    ap.add_argument('--output-dir',type=Path)
    a=ap.parse_args(); base=a.data_root/'derived/oasis2'
    src=a.cohort_dir or base/'clinical_cohort_v1'; out=a.output_dir or base/'clinical_benchmark_v1'
    require(not out.exists(),'Output directory already exists; use a new --output-dir to preserve results.')
    plan=json.loads((src/'analysis_plan.json').read_text(encoding='utf-8-sig'))
    for name,digest in plan['output_sha256'].items():
        require(Path(name).name==name,'Invalid manifest filename')
        require(hashlib.sha256((src/name).read_bytes()).hexdigest()==digest,'Checksum mismatch: '+name)
    tables={n:pd.read_csv(src/(n+'.csv')).set_index('subject') for n in ['clinical_features','clinical_targets','participant_folds']}
    x=tables['clinical_features'].sort_index(); y=tables['clinical_targets']; f=tables['participant_folds']
    require(list(x.columns)==FEATURES,'Unexpected predictors')
    for t in tables.values():
        require(t.index.is_unique and not t.index.hasnans and set(t.index)==set(x.index),'Invalid participant join')
    y=y.loc[x.index,'later_mmse'].to_numpy(float); folds=f.loc[x.index,'outer_fold'].to_numpy()
    require(len(x)==plan['primary_participants'] and set(folds)=={1,2,3,4,5},'Cohort/fold mismatch')
    X=x.to_numpy(float)
    require(np.isfinite(y).all() and not np.isinf(X).any(),'Invalid values')
    require(np.isfinite(X[:,2]).all(),'Persistence requires baseline MMSE')
    pred=np.full(len(y),np.nan); visits=np.zeros(len(y),int); details=[]; inner_audit=[]
    for k in range(1,6):
        tr=np.flatnonzero(folds!=k); te=np.flatnonzero(folds==k)
        inner=list(KFold(n_splits=5,shuffle=True,random_state=42+k).split(tr))
        for j,(it,iv) in enumerate(inner,1):
            require(not set(tr[it])&set(te) and not set(tr[iv])&set(te),'Inner/outer leakage')
            inner_audit.append({'outer_fold':k,'inner_fold':j,'train_subjects':x.index[tr[it]].tolist(),'validation_subjects':x.index[tr[iv]].tolist()})
        pipe=Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler()),('ridge',Ridge(solver='svd'))])
        search=GridSearchCV(pipe,{'ridge__alpha':ALPHAS},scoring='neg_mean_absolute_error',cv=inner,n_jobs=1,error_score='raise')
        search.fit(X[tr],y[tr]); pred[te]=search.predict(X[te]); visits[te]+=1
        details.append({'outer_fold':k,'train_n':len(tr),'test_n':len(te),'alpha':search.best_params_['ridge__alpha'],'ridge':scores(y[te],pred[te]),'persistence':scores(y[te],X[te,2])})
        print('Finished fold',k,flush=True)
    require(np.all(visits==1) and np.isfinite(pred).all(),'Incomplete out-of-fold predictions')
    persistence=X[:,2]; result={'ridge':scores(y,pred),'persistence':scores(y,persistence)}
    rng=np.random.default_rng(42); boot=[]
    for _ in range(5000):
        idx=rng.integers(0,len(y),len(y)); rs=scores(y[idx],pred[idx]); ps=scores(y[idx],persistence[idx])
        boot.append([rs['MAE'],rs['RMSE'],ps['MAE'],ps['RMSE'],rs['MAE']-ps['MAE'],rs['RMSE']-ps['RMSE']])
    labels=['ridge_MAE','ridge_RMSE','persistence_MAE','persistence_RMSE','ridge_minus_persistence_MAE','ridge_minus_persistence_RMSE']
    result.update({'participants':len(y),'folds':details,'bootstrap_95_percentile_intervals':dict(zip(labels,np.percentile(boot,[2.5,97.5],axis=0).T.tolist())),
      'uncertainty_note':'Conditional bootstrap of fixed paired out-of-fold predictions; does not include full model refitting or fold variability.',
      'alpha_grid':ALPHAS,'primary_metric':'MAE','predictions_clipped':False,'ridge_predictions_outside_0_30':int(((pred<0)|(pred>30)).sum()),
      'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
      'analysis_plan_sha256':hashlib.sha256((src/'analysis_plan.json').read_bytes()).hexdigest(),
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'limitations':['Exploratory internal validation only.','Selected visits within 18–30 months, not exact two-year prognosis.','Clinical-only; MRI QC unresolved.','No deployment model fitted.']})
    out.mkdir(parents=True)
    pd.DataFrame({'subject':x.index,'outer_fold':folds,'later_mmse':y,'persistence_prediction':persistence,'ridge_prediction':pred}).to_csv(out/'out_of_fold_predictions.csv',index=False)
    (out/'benchmark_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'inner_fold_audit.json').write_text(json.dumps(inner_audit,indent=2),encoding='utf-8')
    print('CLINICAL BENCHMARK SUMMARY')
    print(json.dumps(result,indent=2)); print('Output:',out)

if __name__=='__main__': main()
