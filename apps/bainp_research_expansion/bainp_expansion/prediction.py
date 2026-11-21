"""NeuroTwin 3G: leakage-aware baseline-model development, external evaluation.
Does not deploy a clinical predictor or infer causal scenario effects.
"""
from __future__ import annotations
import csv, math
from .common import Blocked, require, measured, report, digest_json

TARGET_NAME = 'outcome_12mo'
BAD_FEATURE_NAMES = ('target','label','outcome','future','post_baseline','after_visit','followup','12mo')


def _load_csv(path, features, require_label=True):
    with open(path,newline='',encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    require(bool(rows),'EMPTY_MODEL_DATA')
    required={'participant_id','baseline_date','site_id',*features}
    if require_label:required.add(TARGET_NAME)
    require(required<=set(rows[0]),'MODEL_DATA_COLUMNS_MISSING',str(required-set(rows[0])))
    samples=[];groups=[];y=[];sites=[]
    for r in rows:
        require(r['participant_id'] and r['site_id'] and r['baseline_date'], 'MODEL_ID_OR_DATE_MISSING')
        from .common import utc_timestamp
        utc_timestamp(r['baseline_date'])
        samples.append([measured(float(r[k]),k) for k in features])
        groups.append(r['participant_id']);sites.append(r['site_id'])
        if require_label:
            require(r[TARGET_NAME] in ('0','1'),'BINARY_OUTCOME_REQUIRED')
            y.append(int(r[TARGET_NAME]))
    return samples,groups,y,sites


def train_exploratory(train_csv, feature_names, external_csv=None, min_subjects=30):
    """Group-disjoint internal holdout; optional independent external set.

    Explicitly *not* a validated 12-month model without long-term outcome adjudication,
    temporal leakage audits, external calibration and sufficient representative samples.
    """
    import numpy as np
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, brier_score_loss
    require(isinstance(feature_names,list) and len(feature_names)>=1 and len(set(feature_names))==len(feature_names),
            'MODEL_FEATURES_REQUIRED')
    require(all(f.isidentifier() and not any(b in f.lower() for b in BAD_FEATURE_NAMES) for f in feature_names),
            'LEAKAGE_PRONE_FEATURE_NAME')
    x,groups,labels,sites=_load_csv(train_csv,feature_names)
    require(len(set(groups))>=min_subjects,'INSUFFICIENT_INDEPENDENT_SUBJECTS')
    require(len(set(labels))==2 and min(labels.count(0),labels.count(1))>=8,'INSUFFICIENT_CLASS_EVENTS')
    # One baseline per participant prevents duplicate-person leakage and temporal repetition.
    require(len(groups)==len(set(groups)),'REPEATED_PARTICIPANT_ROWS_IN_BASELINE_MODEL')
    x=np.asarray(x,dtype=float);y=np.asarray(labels,dtype=int)
    split=GroupShuffleSplit(n_splits=1,test_size=0.25,random_state=42)
    tr,te=next(split.split(x,y,groups=np.asarray(groups)))
    require(len(set(y[tr]))==2 and len(set(y[te]))==2,'MODEL_HOLDOUT_HAS_SINGLE_CLASS')
    scaler=StandardScaler().fit(x[tr]);model=LogisticRegression(max_iter=1000,random_state=42)
    model.fit(scaler.transform(x[tr]),y[tr])
    p=model.predict_proba(scaler.transform(x[te]))[:,1]
    metrics={'n_train':len(tr),'n_internal_holdout':len(te),
        'internal_roc_auc':float(roc_auc_score(y[te],p)),
        'internal_brier_score':float(brier_score_loss(y[te],p)),
        'split': 'GroupShuffleSplit, subject-disjoint, random_state=42'}
    weights={'features':feature_names,'standard_scaler_mean':[float(z) for z in scaler.mean_],
        'standard_scaler_scale':[float(z) for z in scaler.scale_],
        'coef':[float(z) for z in model.coef_[0]],'intercept':float(model.intercept_[0]),
        'target':TARGET_NAME,'horizon_days':365,'model_type':'regularized_logistic_regression',
        'training_subject_count':len(groups),'clinical_deployment_authorized':False}
    if external_csv:
        ex,g,yext,sites_ext=_load_csv(external_csv,feature_names)
        require(not set(groups).intersection(g),'EXTERNAL_VALIDATION_SUBJECT_OVERLAP')
        require(len(set(yext))==2,'EXTERNAL_VALIDATION_SINGLE_CLASS')
        # No fitting or recalibration on external samples.
        xp=np.asarray(ex)
        pred=model.predict_proba(scaler.transform(xp))[:,1]
        metrics['external_n']=len(yext)
        metrics['external_roc_auc']=float(roc_auc_score(yext,pred))
        metrics['external_brier_score']=float(brier_score_loss(yext,pred))
        metrics['external_sites']=sorted(set(sites_ext))
    weights['artifact_sha256']=digest_json(weights)
    return report('3G','EXPLORATORY_MODEL_NOT_APPROVED',{'metrics':metrics,'safe_json_model':weights},
        ['Outcome ascertainment and feature leakage require independent human audit.',
         'Group-disjoint internal holdout is not external validation.',
         'External evaluation alone does not establish clinical safety, transportability or calibration.',
         'Forecasts and hypothetical feature changes are not causal treatment effects.'])


def explore_scenario(model_json,features):
    """Offline hypothetical prediction only; no clinical use or causal recommendation."""
    import numpy as np
    w=model_json.get('facts',{}).get('safe_json_model',model_json) if isinstance(model_json,dict) else {}
    expected_digest=w.get('artifact_sha256')
    require(expected_digest and digest_json({k:v for k,v in w.items() if k!='artifact_sha256'})==expected_digest,
            'MODEL_ARTIFACT_HASH_MISMATCH')
    require(w.get('clinical_deployment_authorized') is False and w.get('model_type')=='regularized_logistic_regression',
            'UNSUPPORTED_OR_UNSAFE_MODEL_ARTIFACT')
    keys=w['features'];require(set(features)==set(keys),'SCENARIO_FEATURE_SET_MISMATCH')
    x=np.asarray([measured(features[k],k) for k in keys],dtype=float)
    mean=np.asarray(w['standard_scaler_mean'],dtype=float);scale=np.asarray(w['standard_scaler_scale'],dtype=float)
    co=np.asarray(w['coef'],dtype=float)
    require(len(keys)==len(mean)==len(scale)==len(co) and np.all(scale>0),'INVALID_MODEL_COEFFICIENTS')
    z=float(np.dot((x-mean)/scale,co)+w['intercept'])
    p=float(1/(1+math.exp(-max(-700,min(700,z)))))
    return report('3G','HYPOTHETICAL_EXPLORATORY_SCORE_NOT_CLINICAL_RISK',
        {'hypothetical_model_output':p,'input_features':features},
        ['Feature perturbations are not interventions, and score differences are not causal effects.',
         'Uncalibrated observational models are not diagnostic or personalized treatment advice.'])
