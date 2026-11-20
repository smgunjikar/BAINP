"""Independent NeuroGuard policy boundary for NeuroTwin research forecasts.
No API can approve a model or change this file. No pickle/code deserialization.
Local process/filesystem permissions still require separate deployment hardening.
"""
import hashlib,json,math,os
from datetime import date,datetime,timezone
import calendar
from pathlib import Path
FEATURES=('baseline_mmse','age','education_years')
def checked_model():
    root=Path(os.environ.get('NEUROTWIN_MODEL_DIR',str(Path.home()/'BAINP_DATA/derived/neurotwin/models')))
    policy=Path(os.environ.get('NEUROTWIN_POLICY_FILE',str(Path.home()/'BAINP_DATA/local/neuroguard/neurotwin_policy.json')))
    if not policy.is_file():return None,['INDEPENDENT_MODEL_REVIEW_REQUIRED']
    try:
        p=json.loads(policy.read_text());raw=(root/'reviewed_model.json').read_bytes();m=json.loads(raw)
        reasons=[]
        if p.get('approved') is not True:reasons.append('MODEL_NOT_APPROVED')
        if not p.get('reviewer') or not p.get('review_reference'):reasons.append('REVIEW_EVIDENCE_MISSING')
        if date.fromisoformat(p['expires_on'])<date.today():reasons.append('MODEL_REVIEW_EXPIRED')
        if hashlib.sha256(raw).hexdigest()!=p.get('model_sha256'):reasons.append('MODEL_HASH_MISMATCH')
        if m.get('schema')!='nt-logistic-24m-v1' or m.get('features')!=list(FEATURES):reasons.append('UNSUPPORTED_MODEL_SCHEMA')
        if m.get('horizon_months')!=24 or m.get('target')!='clinician_recorded_dementia':reasons.append('UNSUPPORTED_TARGET')
        if m.get('synthetic') is not False:reasons.append('SYNTHETIC_MODEL_NOT_ALLOWED')
        if not m.get('external_evaluation') or not m.get('participant_separated'):reasons.append('EXTERNAL_PARTICIPANT_EVALUATION_REQUIRED')
        if p.get('calibration_reviewed') is not True:reasons.append('CALIBRATION_REVIEW_REQUIRED')
        if p.get('approved_cohorts')!=m.get('approved_cohorts') or not p.get('approved_cohorts'):reasons.append('POPULATION_SCOPE_REQUIRED')
        for k in ('mean','scale','coef','minimum','maximum'):
            if len(m[k])!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in m[k]):reasons.append('INVALID_MODEL_PARAMETERS')
        if any(v<=0 for v in m['scale']) or not math.isfinite(m['intercept']):reasons.append('INVALID_MODEL_PARAMETERS')
        for draw in m.get('bootstrap',[]):
            if len(draw)!=4 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in draw):reasons.append('INVALID_UNCERTAINTY_PARAMETERS')
        if len(m.get('bootstrap',[]))<30:reasons.append('SAMPLING_UNCERTAINTY_REQUIRED')
        if reasons:return None,sorted(set(reasons))
        return m,[]
    except (OSError,ValueError,KeyError,TypeError):return None,['MODEL_OR_POLICY_INVALID']
def probability(m,values):
    z=[(v-a)/b for v,a,b in zip(values,m['mean'],m['scale'])]
    def sigmoid(s):return 1/(1+math.exp(-max(-700,min(700,s))))
    point=sigmoid(m['intercept']+sum(a*b for a,b in zip(z,m['coef'])))
    draws=sorted(sigmoid(d[0]+sum(a*b for a,b in zip(z,d[1:]))) for d in m['bootstrap'])
    return point,[draws[int(.025*(len(draws)-1))],draws[int(.975*(len(draws)-1))]]
def forecast(records,overrides=None):
    from neuroevidence_bridge import guard_forecast
    return guard_forecast(_research_forecast(records,overrides))

def _research_forecast(records,overrides=None):
    out=dict(state='UNAVAILABLE_NO_VALIDATED_MODEL',value=None,horizon_months=24,
        target='Clinician-recorded dementia after a baseline MCI assessment',interval=None,
        reasons=[],interpretation='Research only. No diagnosis or exact onset date.')
    m,reasons=checked_model()
    if reasons:return out|{'reasons':reasons}
    visits=[r for r in records if r.get('source')=='Clinical' and r.get('clinical_state')=='MCI']
    visits.sort(key=lambda r:datetime.fromisoformat(r['observed_at'].replace('Z','+00:00')),reverse=True)
    if not visits:return out|{'reasons':['VERIFIED_CLINICAL_MCI_BASELINE_REQUIRED']}
    r=visits[0]
    baseline=datetime.fromisoformat(r['observed_at'].replace('Z','+00:00')).date()
    end=baseline.replace(year=baseline.year+2,day=min(baseline.day,calendar.monthrange(baseline.year+2,baseline.month)[1]))
    if end<date.today():reasons.append('FORECAST_HORIZON_ALREADY_ELAPSED')
    latest=max((v for v in records if v.get('source')=='Clinical'),key=lambda v:datetime.fromisoformat(v['observed_at'].replace('Z','+00:00')),default=r)
    if latest.get('clinical_state')!='MCI':reasons.append('CURRENT_CLINICAL_STATE_NOT_MCI')
    if len([v for v in visits if v['observed_at']==r['observed_at']])>1:reasons.append('AMBIGUOUS_CLINICAL_BASELINE')
    if r.get('source_cohort') not in m['approved_cohorts']:reasons.append('POPULATION_OUTSIDE_REVIEWED_SCOPE')
    if r.get('protocol')!=m['clinical_protocol']:reasons.append('CLINICAL_PROTOCOL_DIFFERS')
    vals={};counts={}
    for o in r['observations']:
        if o['quality']!='usable':continue
        if o['metric']=='clinical_measurement' and o.get('instrument')=='MMSE':vals['baseline_mmse']=o['value'];counts['baseline_mmse']=counts.get('baseline_mmse',0)+1
        elif o['metric'] in ('age','education_years'):vals[o['metric']]=o['value'];counts[o['metric']]=counts.get(o['metric'],0)+1
    if any(v>1 for v in counts.values()):reasons.append('AMBIGUOUS_BASELINE_FEATURE')
    if not all(k in vals for k in FEATURES):reasons.append('SAME_VISIT_MMSE_AGE_EDUCATION_REQUIRED')
    # Scenario overrides alter the model query only, never observed source records.
    if overrides:vals.update(overrides)
    if all(k in vals for k in FEATURES):
        x=[vals[k] for k in FEATURES]
        if any(v<lo or v>hi for v,lo,hi in zip(x,m['minimum'],m['maximum'])):reasons.append('INPUT_OUTSIDE_TRAINING_RANGE')
    if reasons:return out|{'reasons':reasons}
    point,interval=probability(m,x)
    return out|dict(state='REVIEWED_RESEARCH_ESTIMATE',value=point,interval=interval,
        reasons=[],model_version=m['model_version'],baseline_date=r['observed_at'],features=vals,
        external_evaluation=m['external_evaluation'],scenario=bool(overrides),
        interval_type='95% training-participant bootstrap sampling interval; not all model or transport uncertainty',
        interpretation='Conditional research estimate for the reviewed cohort. Hypothetical inputs are associations, not intervention effects.')
