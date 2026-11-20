"""NeuroSense research benchmark: nested participant CV, no clinical deployment.
Each row is one participant. Imputation, selection and scaling are fitted ONLY
inside training folds. Saved predictions are outer-fold held-out predictions.
"""
import argparse, hashlib, json, html, platform
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectPercentile, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score, classification_report, confusion_matrix

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def specs(smoke=False):
    # Small, prespecified grids limit computation and researcher degrees of freedom.
    n=10 if smoke else 200
    return {
      'dummy':(DummyClassifier(strategy='prior'),{}),
      'logistic':(LogisticRegression(class_weight='balanced',max_iter=5000,random_state=42),{'model__C':[.01,.1,1]}),
      'forest':(RandomForestClassifier(n_estimators=n,class_weight='balanced',n_jobs=2,random_state=42),{'model__min_samples_leaf':[3,8]}),
      'boosting':(HistGradientBoostingClassifier(class_weight='balanced',max_iter=10 if smoke else 120,early_stopping=False,random_state=42),{'model__max_leaf_nodes':[7,15],'model__l2_regularization':[1,10]})}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    files=['participant_features.csv','participant_labels_coverage.csv','fold_assignments.csv']
    hashes={f:sha(a.input/f) for f in files}
    x=pd.read_csv(a.input/files[0],dtype={'participant':str}).set_index('participant')
    labels=pd.read_csv(a.input/files[1],dtype={'participant':str}).set_index('participant')
    folds=pd.read_csv(a.input/files[2],dtype={'participant':str}).set_index('participant')
    if any(not z.index.is_unique for z in [x,labels,folds]): raise ValueError('Duplicate participant IDs')
    if set(x.index)!=set(labels.index) or set(x.index)!=set(folds.index): raise ValueError('Participant ID sets differ')
    labels=labels.loc[x.index];folds=folds.loc[x.index,'fold']
    x=x.apply(pd.to_numeric,errors='raise')
    if np.isinf(x.to_numpy()).any(): raise ValueError('Infinite feature value')
    allowed={'Healthy',"Parkinson's",'Atypical Parkinsonism','Essential Tremor','Multiple Sclerosis','Other Movement Disorders'}
    if set(labels.condition)!=allowed: raise ValueError('Unexpected labels: verify mapping before proceeding')
    if set(folds)!=set(range(1,6)): raise ValueError('Expected original five outer folds')
    targets={'six_class':allowed,'pd_vs_healthy':{'Healthy',"Parkinson's"},'pd_vs_other_movement':{"Parkinson's",'Atypical Parkinsonism','Essential Tremor','Other Movement Disorders'}}
    out=a.input/('nested_v2_'+('SMOKE_' if a.smoke else '')+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
    report={'version':'neurosense-nested-v2','smoke_only':a.smoke,'provenance':hashes,'script_sha256':sha(Path(__file__)),'versions':{'python':platform.python_version(),'sklearn':sklearn.__version__,'numpy':np.__version__,'pandas':pd.__version__},'targets':{},'limitations':['Exploratory reuse of a previously inspected cohort; no untouched external validation.','Cross-sectional diagnostic-group association, not diagnosis or presymptomatic detection.','Alternate binary targets are separate research questions, not improvements to six-class accuracy.','Rare-class estimates are unstable. No clinical calibration or deployment.']}
    for target,groups in targets.items():
        keep=labels.condition.isin(groups);X=x.loc[keep];y=labels.loc[keep,'condition'].copy();ff=folds.loc[keep]
        if target=='pd_vs_other_movement': y=y.map(lambda z: 'PD' if z=="Parkinson's" else 'Other movement groups')
        classes=sorted(y.unique());td=out/target;td.mkdir();results={};prediction_rows=[];selected=[];tuning=[]
        pd.DataFrame({'participant':X.index,'condition':y.values,'fold':ff.values}).to_csv(td/'cohort_and_folds.csv',index=False)
        for name,(model,grid) in specs(a.smoke).items():
            pred=pd.Series(index=X.index,dtype=object)
            for k in range(1,6):
                train=np.flatnonzero(ff.to_numpy()!=k);test=np.flatnonzero(ff.to_numpy()==k)
                if set(y.iloc[test])!=set(classes) or y.iloc[train].value_counts().min()<3: raise ValueError('Insufficient class coverage in folds')
                pipe=Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True)),('select',SelectPercentile(f_classif)),('scale',StandardScaler()),('model',model)])
                params=dict(grid);params['select__percentile']=[100] if name=='dummy' else ([10] if a.smoke else [5,15])
                search=GridSearchCV(pipe,params,scoring='balanced_accuracy',cv=StratifiedKFold(3,shuffle=True,random_state=100+k),n_jobs=1,error_score='raise',refit=True)
                search.fit(X.iloc[train],y.iloc[train]);best=search.best_estimator_;p=best.predict(X.iloc[test]);pred.iloc[test]=p
                prob=best.predict_proba(X.iloc[test])
                for j,idx in enumerate(test): prediction_rows.append({'participant':X.index[idx],'model':name,'fold':k,'actual':y.iloc[idx],'predicted':p[j],**{'p_'+c:float(prob[j,l]) for l,c in enumerate(best.classes_)}})
                tuning.append({'model':name,'fold':k,'inner_balanced_accuracy':float(search.best_score_),'parameters':search.best_params_})
                if name!='dummy':
                    for col in X.columns[best.named_steps['select'].get_support()]:selected.append({'model':name,'fold':k,'feature':col})
                pd.DataFrame(prediction_rows).to_csv(td/'held_out_predictions.csv',index=False)
                print(target,name,'outer fold',k,'saved',flush=True)
            results[name]={'balanced_accuracy':float(balanced_accuracy_score(y,pred)),'macro_f1':float(f1_score(y,pred,average='macro')),'confusion_matrix':confusion_matrix(y,pred,labels=classes).tolist(),'per_class':classification_report(y,pred,output_dict=True,zero_division=0)}
        pd.DataFrame(selected).to_csv(td/'selected_features.csv',index=False)
        (td/'tuning.json').write_text(json.dumps(tuning,indent=2))
        report['targets'][target]={'class_counts':y.value_counts().to_dict(),'classes':classes,'participants':len(X),'models':results}
        (out/'comparison.json').write_text(json.dumps(report,indent=2))
    if hashes!={f:sha(a.input/f) for f in files}:raise RuntimeError('Inputs changed during run')
    rows=''.join('<tr><td>'+html.escape(t)+'</td><td>'+m+'</td><td>'+format(v['balanced_accuracy'],'.3f')+'</td><td>'+format(v['macro_f1'],'.3f')+'</td></tr>' for t,r in report['targets'].items() for m,v in r['models'].items())
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>NeuroSense research comparison</title><style>body{font:18px system-ui;max-width:1100px;margin:40px auto}td,th{padding:12px;border-bottom:1px solid #ccc}table{border-collapse:collapse}</style><h1>NeuroSense nested evaluation</h1><p>Research only. '+('SMOKE TEST â€” do not interpret scores.' if a.smoke else 'Participant-held-out results; not clinical validation.')+'</p><table><tr><th>Target</th><th>Model</th><th>Balanced accuracy</th><th>Macro F1</th></tr>'+rows+'</table><ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in report['limitations'])+'</ul><p>Detailed class results: comparison.json. Each target folder includes predictions, tuning parameters and selected features.</p>',encoding='utf-8')
    print('REPORT:',out,flush=True)
if __name__=='__main__':main()
