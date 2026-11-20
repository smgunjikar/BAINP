"""State summaries and explicit-assumption illustrative filtering."""
import math
from nt_engine import fingerprint,stamp,estimate
from nt_guard import forecast
from nt_monitor import governance
DOMAIN={'C01':'Episodic learning','C02':'Delayed memory','C03':'Attention','C04':'Executive control','C05':'Processing speed','C06':'Everyday function','C07':'Working memory','C08':'Visuospatial','C09':'Language','C10':'Verbal executive function','C11':'Motor observation','C12':'Assessment context'}
def local_level(points,measurement_variance,process_variance_per_day):
    """1D local-level Kalman filter, specified variances; not a fitted biological model."""
    if measurement_variance<=0 or process_variance_per_day<0:raise ValueError('invalid variance')
    state=None;variance=None;previous=None;out=[]
    for p in sorted(points,key=lambda x:x['at']):
        if not p['eligible']:continue
        at=stamp(p['at'])
        if at is None:continue
        if state is None:state=p['value'];variance=measurement_variance
        else:
            variance+=process_variance_per_day*max(0,(at-previous).total_seconds()/86400)
            gain=variance/(variance+measurement_variance)
            state+=gain*(p['value']-state);variance*=1-gain
        previous=at
        out.append(dict(at=p['at'],value=state,lower=state-1.96*math.sqrt(variance),upper=state+1.96*math.sqrt(variance)))
    return out

def enhance(result,records,neural,history=None,synthetic=False):
    # Supplied regional anatomy is plotted only within the same processing/region/unit group.
    regional={}
    for package in result.get('regional_anatomy',[]):
        scan=next((i for i in result['imaging'] if i['id']==package['scan_id']),None)
        if not scan:continue
        m=scan['metadata']
        for measurement in package['measurements']:
            key=fingerprint(['freesurfer',measurement['id'],measurement['unit'],package.get('freesurfer_version'),m.get('protocol'),m.get('pipeline')])[:20]
            series=regional.setdefault(key,dict(id=key,source='NeuroVision',metric=measurement['id'],label=measurement['name'],unit=measurement['unit'],condition=key[:12],points=[]))
            series['points'].append(dict(at=m['date']+'T12:00:00+00:00' if m.get('date') else None,value=measurement['value'],eligible=False,flags=['REGIONAL_LONGITUDINAL_COMPARABILITY_REQUIRES_REVIEW'],record_id=package['scan_id']))
    for series in regional.values():
        series['points'].sort(key=lambda p:p['at'] or '')
        series.update(total=len(series['points']),eligible=0,estimate=estimate(series['points']),coverage=dict(observed_days=len({p['at'] for p in series['points'] if p['at']}),span_days=None,expected_schedule=None,missingness_rate=None))
    result['series'].extend(regional.values())
    result['version']='neurotwin-research-v2.0.0'
    result['synthetic']=synthetic
    result['domains']=[dict(id=k,label=v,sessions=sum(r['task']==k for r in result.get('cognitive_records',[]))) for k,v in DOMAIN.items()]
    result['clinical_records']=[r for r in records if r['source']=='Clinical']
    result['neural_recordings']=neural
    result['forecast']=forecast(records) if not synthetic else result['forecast']
    result['governance']=governance(result['source_states'],history or [])
    result['functions']=[
      dict(id='A',name='Anatomical Twin',state='available' if result['imaging'] else 'verified MRI needed',detail='Inline MRI intensity, native-grid measurements and supplied surfaces. Regional anatomy/thickness require a reviewed anatomical pipeline.'),
      dict(id='B',name='Neural Twin',state='available' if neural else 'linked EEG needed',detail='Recorded waveforms, spectral features and channel covariance when supplied. Sensor dependencies are not anatomical connections.'),
      dict(id='C',name='Cognitive Twin',state='available' if result.get('cognitive_records') else 'repeated assessments needed',detail='Performance histories remain grouped by conditions. Active practice-effect adjustment needs an evaluated calibration.'),
      dict(id='D',name='Predictive Twin',state=result['forecast']['state'],detail='24-month cohort-specific research workflow. Active inference requires an independently reviewed model and supported inputs.'),
      dict(id='E',name='Scenario research',state='synthetic simulator' if synthetic else result['forecast']['state'],detail='Hypothetical model queries leave observed measurements unchanged. No causal or treatment-effect inference.'),
      dict(id='F',name='Continuous updating',state='source refresh enabled',detail='Verified source data refresh while visible. Retraining and deployment are separate controlled steps.')]
    result['roadmap']=[['NT-1','Timeline, provenance and missing-data indicators','Implemented'],['NT-2','Condition-specific historical fits','Implemented; calibrated practice/RCI unavailable'],['NT-3','Inline MRI and supplied surfaces','Implemented for linked prepared packages; no new segmentation'],['NT-4','Progression research','Offline training/evaluation and independent model gate; private cohort not evaluated here'],['NT-5','Linked EEG and wearable integration','Record APIs and displays; actual device acquisition remains source-specific'],['NT-6','Whole-brain network simulation','Not implemented; channel covariance is not a whole-brain model'],['NT-7','Prospective clinical evaluation','Not performed']]
    result['revision']=fingerprint({k:v for k,v in result.items() if k not in ('revision','read_started_at','read_finished_at','governance')})
    return result

def toy_forecast(score,variability=0.,sleep=7.):
    # These coefficients are intentionally invented for interface demonstration.
    def probability(offset):return 1/(1+math.exp(-(-2.6+(.055*(80-score))+.018*variability+.1*(7-sleep)+offset)))
    return dict(state='SYNTHETIC_SIMULATOR_ONLY',target='Invented follow-up event, not a disease outcome',horizon_months=24,
                value=probability(0),interval=[probability(-.5),probability(.5)],
                interval_type='Assumed coefficient sensitivity band; NOT a confidence interval',
                reasons=[],model_version='invented-demo-logit-v1',
                interpretation='Invented coefficients and values. Not fitted to ADNI, OASIS, PADS or OpenNeuro. No clinical interpretation.')
