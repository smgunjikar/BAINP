"""Offline fixed 24-month MCI-to-clinician-recorded-dementia logistic baseline.
One baseline per participant; full follow-up needed for negative labels.
No auto-deployment or NeuroGuard policy writes. No claim of clinical validity.
"""
import argparse,calendar,csv,hashlib,json,math
from datetime import date
from pathlib import Path
FEATURES=['baseline_mmse','age','education_years']
def horizon(d):return d.replace(year=d.year+2,day=min(d.day,calendar.monthrange(d.year+2,d.month)[1]))
def read_cohort(path):
    rows=[];excluded=[];seen=set()
    with path.open(encoding='utf-8-sig',newline='') as f:
        for line,r in enumerate(csv.DictReader(f),2):
            key=r['participant_id']
            if key in seen:raise ValueError('Duplicate baseline participant: '+str(key))
            seen.add(key)
            if r['baseline_state']!='MCI':excluded.append([line,'not baseline MCI']);continue
            index=date.fromisoformat(r['index_date']);end=date.fromisoformat(r['followup_end_date']);event=date.fromisoformat(r['event_date']) if r.get('event_date') else None
            if end>date.today() or index>date.today():raise ValueError('Future clinical follow-up dates are not observed outcomes')
            if end<index or (event and (event<=index or event>end)):raise ValueError('Invalid chronology on CSV line '+str(line))
            death=date.fromisoformat(r['death_date']) if r.get('death_date') else None
            if death and (death<index or death>end or (event and event>death)):raise ValueError('Invalid death/outcome chronology on CSV line '+str(line))
            if death and death<=horizon(index) and not event:excluded.append([line,'competing death before horizon; fixed-horizon model not appropriate']);continue
            if event and r.get('event_name')!='clinician_recorded_dementia':raise ValueError('Event definition must be clinician_recorded_dementia')
            target=int(bool(event and event<=horizon(index)))
            if not target and end<horizon(index):excluded.append([line,'incomplete 24-month event-free follow-up']);continue
            x=[float(r[k]) for k in FEATURES]
            if any(not math.isfinite(v) for v in x) or not 0<=x[0]<=30 or not 18<=x[1]<=110 or not 0<=x[2]<=40:raise ValueError('Invalid baseline feature range')
            rows.append(dict(key=key,x=x,y=target,cohort=r['cohort'],participant=r['participant_id']))
    return rows,excluded

def train(train_path,external_path,out,protocol,synthetic=False,seed=413,bootstraps=60):
    import numpy as np,sklearn
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score,brier_score_loss,log_loss,balanced_accuracy_score
    from sklearn.calibration import calibration_curve
    rows,excluded=read_cohort(train_path)
    if len(rows)<40 or min(sum(r['y']==i for r in rows) for i in (0,1))<10:raise ValueError('Need at least 40 eligible participants and 10 per class for this engineering workflow')
    X=np.asarray([r['x'] for r in rows]);y=np.asarray([r['y'] for r in rows]);idx=np.arange(len(rows))
    tr,te=train_test_split(idx,test_size=.25,stratify=y,random_state=seed)
    def fit(indices):
        scaler=StandardScaler().fit(X[indices]);model=LogisticRegression(C=1,max_iter=2000,random_state=seed).fit(scaler.transform(X[indices]),y[indices]);return scaler,model
    scaler,model=fit(tr)
    def evaluate(xs,ys):
        proba=model.predict_proba(scaler.transform(xs))[:,1];true,pred=calibration_curve(ys,proba,n_bins=5,strategy='quantile')
        return dict(n=len(ys),positive=int(sum(ys)),roc_auc=float(roc_auc_score(ys,proba)),brier=float(brier_score_loss(ys,proba)),log_loss=float(log_loss(ys,proba)),balanced_accuracy=float(balanced_accuracy_score(ys,proba>=.5)),calibration={'observed':true.tolist(),'predicted':pred.tolist()},note='Brier score alone does not establish calibration. No model/hyperparameter selection was performed.')
    internal=evaluate(X[te],y[te]);external=None;ext_rows=[];ext_excluded=[]
    if external_path:
        ext_rows,ext_excluded=read_cohort(external_path)
        # Literal participant IDs must be globally de-duplicated by the data owner;
        # different aliases cannot be detected by code alone.
        if {r['participant'] for r in rows}&{r['participant'] for r in ext_rows}:raise ValueError('Participant overlap with external cohort')
        if {r['cohort'] for r in rows}&{r['cohort'] for r in ext_rows}:raise ValueError('External evaluation requires a separate cohort label')
        if len(ext_rows)<20 or len({r['y'] for r in ext_rows})<2:raise ValueError('External evaluation needs at least 20 participants and both outcomes')
        external=evaluate(np.array([r['x'] for r in ext_rows]),np.array([r['y'] for r in ext_rows]))
    # Keep the evaluated training subset model: do not refit on held-out participants.
    gen=np.random.default_rng(seed);draws=[]
    for _ in range(bootstraps):
        sample=gen.choice(tr,size=len(tr),replace=True)
        if len(set(y[sample]))<2:continue
        s,m=fit(sample)
        # Convert each bootstrap fit into the main training scaler coordinates.
        coef=m.coef_[0]*scaler.scale_/s.scale_
        intercept=m.intercept_[0]+np.sum(m.coef_[0]*(scaler.mean_-s.mean_)/s.scale_)
        draws.append([float(intercept),*coef.tolist()])
    artifact=dict(schema='nt-logistic-24m-v1',model_version='nt-progression-logistic-v1',synthetic=synthetic,
      target='clinician_recorded_dementia',horizon_months=24,features=FEATURES,clinical_protocol=protocol,
      mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),coef=model.coef_[0].tolist(),intercept=float(model.intercept_[0]),
      minimum=X[tr].min(axis=0).tolist(),maximum=X[tr].max(axis=0).tolist(),bootstrap=draws,
      participant_separated=True,internal_evaluation=internal,external_evaluation=external,
      approved_cohorts=sorted({r['cohort'] for r in rows+ext_rows}),
      training_sha256=hashlib.sha256(train_path.read_bytes()).hexdigest(),external_sha256=hashlib.sha256(external_path.read_bytes()).hexdigest() if external_path else None,
      exclusions={'training':excluded,'external':ext_excluded},seed=seed,sklearn=sklearn.__version__,
      status='CANDIDATE_NOT_APPROVED',limitations=['Complete-case fixed-horizon analysis excludes censored participants and competing deaths; selection bias is possible.','External evidence and calibration require independent scientific review.','This is not a survival model; time-to-event/censoring modeling is future work.','Baseline MMSE must not be replaced with an unvalidated NeuroCognition score.','Held-out participants remain excluded from the exported fitted model.'])
    out.mkdir(parents=True,exist_ok=True);raw=json.dumps(artifact,indent=2,allow_nan=False).encode();(out/'candidate_model.json').write_bytes(raw)
    (out/'model_card.md').write_text('# Candidate progression model\n\nFixed prespecified logistic regression. Not deployed or approved.\n\n'+json.dumps({'internal':internal,'external':external,'limitations':artifact['limitations']},indent=2))
    print('CANDIDATE:',out/'candidate_model.json');return artifact
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--external',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--clinical-protocol',required=True);p.add_argument('--synthetic',action='store_true');a=p.parse_args();train(a.cohort,a.external,a.output,a.clinical_protocol,a.synthetic)
