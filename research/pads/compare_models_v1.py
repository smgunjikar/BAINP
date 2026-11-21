"""Participant-held-out exploratory comparison. Fixed settings; no clinical model deployment."""
import argparse,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import balanced_accuracy_score,f1_score,confusion_matrix,classification_report,log_loss
from sklearn.utils.class_weight import compute_sample_weight

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--features',type=Path,required=True);ap.add_argument('--patients',type=Path,required=True);a=ap.parse_args()
 f=a.features;d=pd.read_csv(f/'recording_features.csv',dtype={'participant':str});c=pd.read_csv(f/'coverage.csv',dtype={'participant':str})
 keys=['participant','task','wrist'];assert not d.duplicated(keys).any(),'Duplicate feature rows'
 assert not c.duplicated(keys).any(),'Duplicate coverage rows'
 assert set(map(tuple,d[keys].values))==set(map(tuple,c.loc[c.status=='FEATURES_READY',keys].values)),'Coverage mismatch'
 ids=sorted(c.participant.unique());assert len(ids)==469 and set(d.participant)==set(ids),'Participant coverage mismatch'
 metrics=[k for k in d if k not in keys+['windows']];assert np.isfinite(d[metrics].to_numpy(float)).all(),'Invalid features'
 wide=d.pivot(index='participant',columns=['task','wrist'],values=metrics).reindex(ids);wide.columns=['__'.join(t) for t in wide.columns]
 y=[];provenance={}
 for pid in ids:
  p=a.patients/f'patient_{pid}.json';v=json.loads(p.read_text(encoding='utf-8-sig'));assert str(v['id']).zfill(3)==pid,'ID mismatch'
  label=v.get('condition');assert isinstance(label,str) and label.strip(),'Missing condition'
  y.append(label.strip());provenance[p.name]=sha(p)
 y=np.array(y);classes=sorted(set(y));counts={k:int(sum(y==k)) for k in classes}
 print('Exact dataset condition labels:',counts,flush=True)
 assert len(classes)>=2 and min(counts.values())>=5,'Each raw condition requires >=5 participants; share label counts before defining a grouping.'
 out=f/('models_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
 wide.to_csv(out/'participant_features.csv');pd.DataFrame({'participant':ids,'condition':y,'missing_features':wide.isna().sum(axis=1).values}).to_csv(out/'participant_labels_coverage.csv',index=False)
 models={
 'dummy':lambda:make_pipeline(SimpleImputer(strategy='median'),DummyClassifier(strategy='prior')),
 'logistic_regression':lambda:make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=0.1,class_weight='balanced',max_iter=3000,random_state=42)),
 'random_forest':lambda:make_pipeline(SimpleImputer(strategy='median'),RandomForestClassifier(n_estimators=300,min_samples_leaf=5,max_features='sqrt',class_weight='balanced',n_jobs=2,random_state=42)),
 'gradient_boosting':lambda:make_pipeline(SimpleImputer(strategy='median'),HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=7,l2_regularization=1,early_stopping=False,random_state=42))}
 # One row per person makes these stratified splits participant-held-out.
 splits=list(StratifiedKFold(5,shuffle=True,random_state=42).split(wide,y));folds=np.zeros(len(ids),int)
 for k,(_,test) in enumerate(splits,1):folds[test]=k
 pd.DataFrame({'participant':ids,'fold':folds}).to_csv(out/'fold_assignments.csv',index=False)
 report={};predictions=[]
 for name,factory in models.items():
  pred=np.empty(len(ids),object);prob=np.zeros((len(ids),len(classes)));fold_scores=[]
  for k,(train,test) in enumerate(splits,1):
   model=factory();kwargs={}
   if name=='gradient_boosting':kwargs['histgradientboostingclassifier__sample_weight']=compute_sample_weight('balanced',y[train])
   model.fit(wide.iloc[train],y[train],**kwargs);pred[test]=model.predict(wide.iloc[test]);p=model.predict_proba(wide.iloc[test])
   for j,label in enumerate(model.classes_):prob[test,classes.index(label)]=p[:,j]
   fold_scores.append(float(balanced_accuracy_score(y[test],pred[test])))
   print(name,'fold',k,'balanced accuracy',round(fold_scores[-1],4),flush=True)
  report[name]={'balanced_accuracy':float(balanced_accuracy_score(y,pred)),'macro_f1':float(f1_score(y,pred,average='macro')),'log_loss':float(log_loss(y,prob,labels=classes)),'fold_balanced_accuracy':fold_scores,'confusion_matrix':confusion_matrix(y,pred,labels=classes).tolist(),'classification_report':classification_report(y,pred,labels=classes,output_dict=True,zero_division=0)}
  for i,pid in enumerate(ids):predictions.append({'participant':pid,'fold':int(folds[i]),'model':name,'actual':y[i],'predicted':pred[i],**{'probability_'+label:float(prob[i,j]) for j,label in enumerate(classes)}})
 pd.DataFrame(predictions).to_csv(out/'held_out_predictions.csv',index=False)
 (out/'comparison.json').write_text(json.dumps({'classes':classes,'class_counts':counts,'participants':len(ids),'features':len(wide.columns),'models':report,'limits':['Exploratory cross-validation; no independent external test cohort.','Fixed hyperparameters; choosing a winner on these results introduces selection optimism.','Probabilities not clinically calibrated.','Missing values imputed inside each training fold; missingness may confound results.'],'provenance':{'feature_sha256':sha(f/'recording_features.csv'),'coverage_sha256':sha(f/'coverage.csv'),'label_hashes':provenance,'script_sha256':sha(Path(__file__)),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__}},indent=2),encoding='utf-8')
 print('REPORT:',out)
if __name__=='__main__':main()
