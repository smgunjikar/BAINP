"""BAINP NeuroPulse X V3.2-3.7 research API, isolated from clinical participant records.
Requires existing NeuroAccess authenticated dependency and X-BAINP-Research-Key.
"""
from __future__ import annotations
import csv
import hashlib
import hmac
import importlib.util
import json
import math
import os
import re
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException, Query

VERSION = 'neuropulse-submission-v3.8.0'
SUBJECT = re.compile(r'^sub-\d{3}$')
BANDS = ('delta_uv2','theta_uv2','alpha_uv2','beta_uv2')

def _run():
    raw=os.environ.get('BAINP_NEUROPULSE_MAIN_RUN','')
    if not raw: raise HTTPException(503,'research_run_not_configured')
    p=Path(raw).resolve()
    if not p.is_dir() or any(not (p/n).is_file() for n in ('features.csv','run_summary.json')):
        raise HTTPException(503,'research_run_missing')
    return p

def _key(value):
    secret=os.environ.get('BAINP_NEUROPULSE_RESEARCH_KEY','')
    if len(secret)<24 or not value or not hmac.compare_digest(secret,value):
        raise HTTPException(403,'research_authorization_required')

def _index(run):
    try:
        with (run/'features.csv').open(encoding='utf-8-sig',newline='') as file:
            rows=list(csv.DictReader(file))
        summary=json.loads((run/'run_summary.json').read_text(encoding='utf-8'))
    except (OSError,ValueError,csv.Error) as exc:
        raise HTTPException(503,'invalid_research_index') from exc
    if len(rows)>10000 or len(rows)!=len({r.get('subject') for r in rows}):
        raise HTTPException(503,'invalid_research_index')
    if summary.get('selected') != len(rows):raise HTTPException(503,'research_count_mismatch')
    cleaned=[]
    for r in rows:
        sub=r.get('subject','')
        if not SUBJECT.fullmatch(sub):raise HTTPException(503,'invalid_research_subject')
        state=r.get('status')
        if state not in ('DESCRIPTIVE_AVAILABLE','INSUFFICIENT_WINDOWS','FAILED'):
            raise HTTPException(503,'invalid_research_status')
        def num(k):
            raw=r.get(k,'')
            if raw in ('',None):return None
            try:value=float(raw)
            except (TypeError,ValueError):raise HTTPException(503,'invalid_feature')
            if not math.isfinite(value):raise HTTPException(503,'nonfinite_feature')
            return value
        try:
            total=int(r['windows_total']); retained=int(r['windows_retained']); excluded=int(r['windows_excluded'])
        except (ValueError,KeyError):raise HTTPException(503,'invalid_windows')
        if not 0<=retained<=total or total!=retained+excluded:raise HTTPException(503,'inconsistent_windows')
        cleaned.append(dict(subject=sub,status=state,windows_total=total,windows_retained=retained,
            windows_excluded=excluded,source_sha256=r.get('sha256',''),
            features={b:num(b) if state=='DESCRIPTIVE_AVAILABLE' else None for b in BANDS},clinical_qc_approved=False))
    return cleaned

def _record(run,sub,entry):
    if not SUBJECT.fullmatch(sub):raise HTTPException(404,'subject_not_found')
    path=run/(sub+'.json')
    if not path.is_file():raise HTTPException(503,'missing_subject_report')
    try:record=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):raise HTTPException(503,'invalid_subject_report')
    if record.get('subject')!=sub or record.get('sha256')!=entry['source_sha256'] or record.get('source_unchanged') is not True:
        raise HTTPException(503,'subject_provenance_mismatch')
    return record

def _subject(run,sub):
    if not SUBJECT.fullmatch(sub):raise HTTPException(404,'subject_not_found')
    row=next((r for r in _index(run) if r['subject']==sub),None)
    if row is None:raise HTTPException(404,'subject_not_found')
    return row,_record(run,sub,row)

def _guard(record,row):
    """Invoke real existing NeuroGuard deterministic claim checker if installed.
    Records deliberately not quality-qualified: decision must abstain/block.
    """
    path=Path(__file__).resolve().parents[2]/'neuroguard'/'backend'/'guard.py'
    if not path.is_file():return {'state':'abstain','reason':'NEUROGUARD_NOT_INSTALLED','policy_version':None,'live_policy_invoked':False}
    try:
        spec=importlib.util.spec_from_file_location('np_v3_guard_policy',path)
        if spec is None or spec.loader is None:raise RuntimeError('missing policy loader')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        example=next(( (k,v) for k,v in row['features'].items() if v is not None),None)
        if not example:return {'state':'abstain','reason':'NO_QUALIFIED_FEATURES','policy_version':module.VERSION,'live_policy_invoked':True}
        band,value=example
        eid='eeg:'+row['subject']+':'+band
        nodes={eid:{'type':'direct_observation','claim':'measurement','eligible':False,
            'statement':'Unreviewed EEG descriptive research feature','value':value,'unit':'µV²'}}
        result=module.check_claim('measurement',eid,nodes,value=value,unit='µV²')
        if result.get('state')=='accept':raise RuntimeError('unreviewed EEG released unexpectedly')
        return dict(result,live_policy_invoked=True)
    except Exception:
        return {'state':'abstain','reason':'NEUROGUARD_POLICY_UNAVAILABLE','policy_version':None,'live_policy_invoked':False}

def _evidence(run,row,record):
    return {'schema':'neuropulse-research-evidence-v3',
      'source_run':run.name,'subject':row['subject'],'source_sha256':row['source_sha256'],
      'source_unchanged_at_processing':True,'processing_schema':record.get('schema'),
      'sampling_hz':record.get('sampling_hz'),'window_seconds':record.get('window_seconds'),
      'amplitude_review_threshold_uv':record.get('amplitude_review_threshold_uv'),
      'windows_retained':row['windows_retained'],'windows_total':row['windows_total'],
      'excluded_intervals':record.get('excluded_intervals',[]),
      'quality':'REVIEW_REQUIRED','research_only':True,'clinical_release':False,
      'identity_linked_to_bainp_participant':False,
      'limitations':record.get('important_limitations',[]),
      'neuroproof_native_passport_created':False,
      'note':'Source-linked research evidence envelope. Native NeuroProof passports require verified BAINP participant linkage and consent.'}

def _research_passport(run, row, record):
    """Immutable-on-read NeuroProof-compatible *research* record, not patient passport."""
    envelope = _evidence(run,row,record)
    envelope['neuroguard'] = _guard(record,row)
    envelope['reference_type'] = 'RESEARCH_DATASET_SOURCE_ONLY'
    envelope['processing_run_kind'] = 'OFFLINE_REPRODUCIBLE'
    envelope['neuroproof_native_passport_created'] = False
    canonical = json.dumps(envelope,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    envelope['evidence_sha256'] = hashlib.sha256(canonical.encode('utf8')).hexdigest()
    envelope['evidence_sha256_scope'] = 'canonical_envelope_excluding_digest_fields'
    return envelope

def _read_segment(run,sub,record,start,duration,channels,max_points):
    """Server-side bounded read, no raw EEG download. Explicit research source root."""
    import numpy as np
    import mne
    dataset=os.environ.get('BAINP_NEUROPULSE_EEG_ROOT','')
    if not dataset:raise HTTPException(503,'raw_eeg_root_not_configured')
    base=Path(dataset).resolve()
    expected=(base/sub/'eeg'/f'{sub}_task-eyesclosed_eeg.set').resolve()
    if not expected.is_file() or not expected.is_relative_to(base):raise HTTPException(503,'raw_recording_missing')
    # For each requested segment, source must match stored original processing path.
    if Path(record.get('source','')).resolve()!=expected:raise HTTPException(409,'source_recording_mismatch')
    try:raw=mne.io.read_raw_eeglab(str(expected),preload=False,verbose='ERROR')
    except Exception as exc:raise HTTPException(422,'raw_eeg_decode_failed') from exc
    fs=float(raw.info['sfreq']); end=min(float(raw.n_times/fs),start+duration)
    if start>=end:raise HTTPException(422,'segment_out_of_bounds')
    eeg=[i for i,k in enumerate(raw.get_channel_types()) if k=='eeg']
    if not eeg:raise HTTPException(422,'no_eeg_channels')
    selected=eeg[:channels]; i0=int(start*fs);i1=min(raw.n_times,int(end*fs))
    try:signal=raw.get_data(picks=selected,start=i0,stop=i1)
    except Exception as exc:raise HTTPException(422,'segment_decode_failed') from exc
    if signal.size==0 or not bool(np.isfinite(signal).all()):raise HTTPException(422,'nonfinite_or_empty_signal')
    skip=max(1,int(math.ceil(signal.shape[1]/max_points)))
    clipped=signal[:,::skip]; times=(i0+np.arange(clipped.shape[1])*skip)/fs
    return raw, selected, signal, {'time_s':times.round(4).tolist(),
       'channels':[raw.ch_names[k] for k in selected],
       'signals_uv':(clipped*1e6).round(3).tolist(),
       'source':'ACTUAL_RAW_EEGLAB_SEGMENT','sampling_hz':fs,
       'display_downsample_only':True,'signal_processing':'No filtering or artifact correction applied',
       'research_only':True,'clinical_qc_approved':False}

def make_router(authenticated):
    router=APIRouter(prefix='/api/neuropulse/intelligence/v3',dependencies=[Depends(authenticated)])
    def grant(x_bainp_research_key: str | None=Header(default=None)):_key(x_bainp_research_key)
    secured=[Depends(grant)]

    @router.get('/overview',dependencies=secured)
    def overview():
        run=_run();rows=_index(run)
        counts={state:sum(r['status']==state for r in rows) for state in ('DESCRIPTIVE_AVAILABLE','INSUFFICIENT_WINDOWS','FAILED')}
        return {'version':VERSION,'source_run':run.name,'total':len(rows),'counts':counts,
          'research_only':True,'clinical_qc_approved':False,'participant_linkage':'UNVERIFIED',
          'subject_records':rows}

    @router.get('/subjects/{sub}',dependencies=secured)
    def subject(sub:str):
        run=_run();row,record=_subject(run,sub)
        return {'row':row,'sampling_hz':record.get('sampling_hz'),'duration_s':record.get('duration_s'),
          'channels':record.get('eeg_channels',[]),'excluded_intervals':record.get('excluded_intervals',[]),
          'quality_decision':_guard(record,row),'evidence':_research_passport(run,row,record),
          'research_only':True,'clinical_qc_approved':False}

    @router.get('/subjects/{sub}/evidence',dependencies=secured)
    def evidence(sub:str):
        run=_run();row,record=_subject(run,sub)
        return _research_passport(run,row,record)

    @router.get('/subjects/{sub}/waveform',dependencies=secured)
    def waveform(sub:str,start_s:float=Query(0,ge=0),duration_s:float=Query(5,gt=0,le=10),
                 channels:int=Query(4,ge=1,le=8),max_points:int=Query(900,ge=100,le=1500)):
        run=_run();row,record=_subject(run,sub)
        _raw,_selected,_signal,payload=_read_segment(run,sub,record,start_s,duration_s,channels,max_points)
        payload.update({'subject':sub,'quality':'REVIEW_REQUIRED','source_sha256_recorded':row['source_sha256']})
        return payload

    @router.get('/subjects/{sub}/spectrum',dependencies=secured)
    def spectrum(sub:str,start_s:float=Query(0,ge=0),duration_s:float=Query(10,ge=4,le=10),channels:int=Query(4,ge=1,le=8)):
        import numpy as np
        from scipy.signal import welch
        run=_run();row,record=_subject(run,sub)
        raw, selected, sig, _=_read_segment(run,sub,record,start_s,duration_s,channels,1500)
        sf=float(raw.info['sfreq']); nperseg=min(sig.shape[1],max(16,int(sf*2)))
        f,p=welch(sig,fs=sf,nperseg=nperseg,axis=1,scaling='density')
        mask=(f>=.5)&(f<=40)
        take=np.flatnonzero(mask)[::max(1,int(math.ceil(mask.sum()/300)))]
        return {'subject':sub,'channels':[raw.ch_names[i] for i in selected],
          'frequency_hz':f[take].round(3).tolist(),
          'psd_uv2_per_hz':(p[:,take]*1e12).round(6).tolist(),
          'method':'scipy.signal.welch on raw, unfiltered selected segment',
          'exploratory_not_cohort_feature':True,'review_required':True,'research_only':True}

    @router.get('/subjects/{sub}/events',dependencies=secured)
    def events(sub:str):
        run=_run();row,record=_subject(run,sub)
        return {'subject':sub,'annotations':[dict(v,type='PROCESSING_EXCLUSION') for v in record.get('excluded_intervals',[])],
          'event_detection_performed':False,'seizure_predictions':False,
          'note':'Processing exclusion intervals are NOT seizure labels or AI detections.'}

    @router.get('/processing',dependencies=secured)
    def processing():
        run=_run();rows=_index(run)
        return {'source_run':run.name,'mode':'COMPLETED_OFFLINE_BATCH','records':len(rows),
          'job_submission_available':False,'retry_available':False,
          'reason':'NeuroCore background-job interface not verified; no job actions exposed',
          'failures':[r['subject'] for r in rows if r['status']=='FAILED'],
          'version':VERSION, 'recovery': 'NEW_EXPLICIT_PROCESSING_RUN_ONLY',
          'neurocore_native_queue_connected':False}

    @router.get('/arena/compare',dependencies=secured)
    def compare(a:str,b:str):
        run=_run();ra,_=_subject(run,a);rb,_=_subject(run,b)
        if a==b:raise HTTPException(422,'compare_requires_distinct_subjects')
        if ra['status']!='DESCRIPTIVE_AVAILABLE' or rb['status']!='DESCRIPTIVE_AVAILABLE':
            raise HTTPException(422,'insufficient_features_for_comparison')
        return {'type':'EXPLORATORY_CROSS_SECTIONAL_DESCRIPTIVE','subjects':[a,b],
         'band_differences_uv2':{band:ra['features'][band]-rb['features'][band] for band in BANDS},
         'research_only':True,'clinical_comparison_permitted':False,
         'not_longitudinal':True,'not_a_machine_learning_evaluation':True,
         'note':'No group claims or AD/FTD classifier performance inferred.'}

    @router.get('/connections',dependencies=secured)
    def connections():
        return {'neuroguard':'LIVE_CLAIM_CHECK_ON_SUBJECT_REQUEST_IF_AVAILABLE',
         'neuroproof':'LIVE_RESEARCH_PASSPORT_ENVELOPE_NO_PATIENT_PASSPORT',
         'neurocore':'OFFLINE_BATCH_STATUS_ONLY_NO_JOB_CONTROL',
         'neurosignal_arena':'DESCRIPTIVE_CROSS_SUBJECT_COMPARISON_ONLY',
         'neurotwin':'BLOCKED_UNVERIFIED_PARTICIPANT_LINKAGE',
         'neurocognition':'NOT_SYNCHRONIZED_WITH_EEG',
         'neurocontinuum':'OPTIONAL_NO_ROUTINE_WORKFLOW_DEPENDENCY',
         'neuroquest':'NO_AUTONOMOUS_EEG_SELECTION',
         'consent':'RESEARCH_DATASET_ISOLATED_FROM_BAINP_PARTICIPANTS',
         'research_only':True}
    return router
