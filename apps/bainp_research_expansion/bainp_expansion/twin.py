"""NeuroTwin 3A–3F: strict identity, consent, observation and missingness contracts.
No imputation of absent visits, diagnoses, clinical results or neurophysiological signals.
"""
from __future__ import annotations
import math
from collections import defaultdict
from .common import Blocked, require, identifier, checksum, measured, utc_timestamp, report, digest_json

ALLOWED = {
    'MRI': {'regional_volume_ml','cortical_thickness_mm','wmh_volume_ml'},
    'Cognition': {'domain_score','reaction_time_ms','accuracy_fraction','mmse_score'},
    'EEG': {'alpha_power_uv2_hz','theta_power_uv2_hz','peak_alpha_frequency_hz'},
    'Wearable': {'sleep_hours','step_count','heart_rate_bpm'},
    'Clinical': {'clinician_observed_score','age_years'}
}
UNITS = {
    'regional_volume_ml':'mL','cortical_thickness_mm':'mm','wmh_volume_ml':'mL',
    'domain_score':'score','reaction_time_ms':'ms','accuracy_fraction':'fraction','mmse_score':'score',
    'alpha_power_uv2_hz':'uV2/Hz','theta_power_uv2_hz':'uV2/Hz','peak_alpha_frequency_hz':'Hz',
    'sleep_hours':'hours','step_count':'steps','heart_rate_bpm':'bpm',
    'clinician_observed_score':'score','age_years':'years'}


def identity_link(record:dict):
    """Validate *existing* independently established identity evidence; never infer a link."""
    for k in ('account_namespace','participant_id','research_cohort','research_subject','verification_reference','verified_by','verified_at'):
        require(bool(record.get(k)),'IDENTITY_EVIDENCE_MISSING',k)
    for k in ('account_namespace','participant_id','research_cohort','research_subject','verified_by'):
        identifier(record[k],k)
    require(record.get('identity_verified') is True and record.get('consent_confirmed') is True,
            'EXPLICIT_IDENTITY_AND_CONSENT_REQUIRED')
    require(len(record['verification_reference'].strip())>=15,'IDENTITY_REFERENCE_INSUFFICIENT')
    utc_timestamp(record['verified_at'])
    return report('3A','IDENTITY_EVIDENCE_SUBMITTED_NOT_EXTERNALLY_AUTHENTICATED',{
        'account_namespace':record['account_namespace'],'participant_id':record['participant_id'],
        'research_cohort':record['research_cohort'],'research_subject':record['research_subject'],
        'verification_reference_sha256':digest_json(record['verification_reference']),'verified_by':record['verified_by']},
        ['This standalone contract cannot independently authenticate the reviewer or certify human identity.',
         'The existing BAINP account boundary and verified-link database remain authoritative.'])


def observation(o:dict):
    for k in ('participant_id','visit_id','source_id','modality','metric','unit','observed_at','pipeline_version','source_sha256','quality'):
        require(k in o,'OBSERVATION_FIELD_REQUIRED',k)
    for k in ('participant_id','visit_id','source_id','pipeline_version'):
        identifier(o[k],k)
    checksum(o['source_sha256']);utc_timestamp(o['observed_at'])
    require(o['modality'] in ALLOWED and o['metric'] in ALLOWED[o['modality']],
            'METRIC_MODALITY_NOT_SUPPORTED')
    require(o['unit']==UNITS[o['metric']],'METRIC_UNIT_MISMATCH')
    require(o['quality'] in ('usable','needs_review','invalid'),'OBSERVATION_QUALITY_INVALID')
    require(o.get('consent_confirmed') is True,'OBSERVATION_CONSENT_REQUIRED')
    v=measured(o['value'],'value')
    if o['metric']=='accuracy_fraction':require(0<=v<=1,'FRACTION_OUT_OF_RANGE')
    if o['metric']=='mmse_score':require(0<=v<=30,'MMSE_RANGE_VIOLATION')
    if o['metric']=='sleep_hours':require(0<=v<=24,'SLEEP_HOURS_RANGE_VIOLATION')
    if o['metric'] in ('regional_volume_ml','cortical_thickness_mm','wmh_volume_ml','reaction_time_ms','step_count','heart_rate_bpm'):
        require(v>=0,'NEGATIVE_OBSERVATION')
    if o['modality']=='MRI':
        require(o.get('anatomical_qc')=='RESEARCH_REVIEWED_NOT_CLINICALLY_APPROVED',
                'MRI_REQUIRES_DOCUMENTED_REVIEW')
        require(o.get('verified_identity_link') is True,'MRI_REQUIRES_VERIFIED_IDENTITY_LINK')
    return o


def cognitive_trajectory(records:list[dict]):
    """No inferred trend across different instruments, protocols or assessment conditions."""
    require(bool(records),'COGNITIVE_RECORDS_MISSING')
    for r in records:
        require(r.get('modality')=='Cognition','COGNITIVE_RECORD_REQUIRED')
        observation(r)
    subjects={r['participant_id'] for r in records};require(len(subjects)==1,'CROSS_PERSON_COGNITION_BLOCKED')
    valid=[r for r in records if r['quality']=='usable' and r.get('session_status')=='completed'
           and r.get('timing_qc')=='usable' and r.get('condition_qc')=='usable']
    groups=defaultdict(list)
    for r in valid:
        key=(r['metric'],r.get('instrument'),r.get('condition'),r['pipeline_version'],r['unit'])
        require(all(key[1:3]),'COGNITIVE_INSTRUMENT_OR_CONDITION_MISSING')
        groups[key].append(r)
    summaries=[]
    for key,rows in groups.items():
        rows=sorted(rows,key=lambda x:x['observed_at'])
        distinct=len({r['visit_id'] for r in rows})
        state='OBSERVED_REPEATED_MEASURES_NOT_CLINICAL_TREND' if distinct>=3 else 'INSUFFICIENT_DISTINCT_VISITS_FOR_TREND'
        summaries.append({'metric':key[0],'instrument':key[1],'condition':key[2],
                          'protocol_version':key[3],'visits':distinct,'state':state,
                          'observed':[(r['observed_at'],r['value']) for r in rows]})
    return report('3C','CONDITION_STRATIFIED_COGNITION',{'participant_id':records[0]['participant_id'],
            'total_sessions':len(records),'eligible_sessions':len(valid),'groups':summaries},
            ['Observed repetitions are not clinically validated cognitive change.',
             'Instrument/condition/protocol mismatches are never pooled.'])


def eeg_band_features(signals, sampling_hz:float, metadata:dict):
    """Welch PSD only on externally consented, annotated, artifact-reviewed EEG.

    Input is [channels, samples] in microvolts, not wearable heart rate samples.
    """
    require(metadata.get('modality')=='EEG' and metadata.get('artifact_review')=='accepted' and
            metadata.get('referencing') and metadata.get('pipeline_version') and
            metadata.get('source_sha256') and metadata.get('consent_confirmed') is True,
            'EEG_MONTAGE_ARTIFACT_QC_CONSENT_REQUIRED')
    checksum(metadata['source_sha256'])
    import numpy as np
    from scipy.signal import welch
    a=np.asarray(signals,dtype=np.float64)
    fs=measured(sampling_hz,'sampling_hz',1)
    require(a.ndim==2 and 1<=a.shape[0]<=256 and a.shape[1]>=int(fs*4),
            'EEG_CHANNELS_OR_DURATION_UNSUPPORTED')
    require(np.isfinite(a).all(),'EEG_NONFINITE_INPUT')
    require(fs>=64,'EEG_SAMPLING_RATE_TOO_LOW')
    f,p=welch(a,fs=fs,nperseg=min(int(fs*2),a.shape[1]),axis=1)
    bands={'delta':(1,4),'theta':(4,8),'alpha':(8,13),'beta':(13,30)}
    means={}
    for k,(lo,hi) in bands.items():
        mask=(f>=lo)&(f<hi)
        require(int(mask.sum())>=2,'INSUFFICIENT_EEG_SPECTRAL_RESOLUTION')
        means[k]=float(np.mean(np.trapezoid(p[:,mask],f[mask],axis=1)))
    return report('3D','EEG_SPECTRAL_FEATURES_EXPLORATORY',{'bands_uv2':means,
        'sample_rate_hz':fs,'duration_sec':a.shape[1]/fs,
        'channel_count':int(a.shape[0]),'metadata':metadata},
        ['Reference, artifacts, epoch selection, filtering and electrode montage affect PSD.',
         'No electrical whole-brain simulation or clinical neural diagnosis is inferred.'])


def behavior_clinical(records:list[dict]):
    by_source=defaultdict(list)
    for r in records:
        require(r.get('modality') in ('Wearable','Clinical'),'BEHAVIOR_CLINICAL_SOURCE_REQUIRED')
        observation(r)
        by_source[r['modality']].append(r)
    participants={x['participant_id'] for x in records}
    require(len(participants)==1,'MIXED_PARTICIPANT_CONTEXT_BLOCKED')
    quality={source:{'usable':sum(x['quality']=='usable' for x in entries),
                     'needs_review':sum(x['quality']=='needs_review' for x in entries),
                     'invalid':sum(x['quality']=='invalid' for x in entries)} for source,entries in by_source.items()}
    return report('3E','CONSENTED_CONTEXT_OBSERVATIONS_VERIFIED',{'participant_id':next(iter(participants)),
        'quality':quality,'observation_count':len(records)},
        ['These records are observations; changes in sleep or activity cannot be asserted to cause brain changes.',
         'Missing wearable periods are not treated as zero or imputed.'])


def assemble_multimodal(records:list[dict],requested_modalities=('MRI','Cognition','EEG','Wearable','Clinical')):
    """Feature table per explicit participant+visit; does NOT infer cross-modality simultaneity."""
    require(bool(records),'NO_MULTIMODAL_OBSERVATIONS')
    seen=set();table={};modalities=set(requested_modalities)
    require(modalities<=set(ALLOWED),'UNSUPPORTED_MODALITY')
    for r in records:
        observation(r)
        require(r['modality'] in modalities,'MODALITY_NOT_DECLARED')
        key=(r['participant_id'],r['visit_id']);feature=(r['modality'],r['metric'],r['pipeline_version'])
        sig=key+feature
        require(sig not in seen,'DUPLICATE_FEATURE_PER_VISIT')
        seen.add(sig)
        visit=table.setdefault(key,{'participant_id':key[0],'visit_id':key[1],
                                    'features':{},'missing_modalities':[],
                                    'provenance':{},'ready_modalities':[]})
        if r['quality']=='usable':
            field='__'.join(feature)
            visit['features'][field]=r['value']
            visit['provenance'][field]=r['source_sha256']
            if r['modality'] not in visit['ready_modalities']:visit['ready_modalities'].append(r['modality'])
    for v in table.values():
        v['missing_modalities']=sorted(modalities-set(v['ready_modalities']))
        v['ready_modalities'].sort()
        v['feature_table_complete']=len(v['ready_modalities'])>=2 and not v['missing_modalities']
        v['fusion_eligible']=False  # synchronization and cohort/model QC unverified
        v['temporal_synchronization_proven']=False
    return report('3F','MISSINGNESS_AWARE_FEATURE_TABLE',{'visits':list(table.values()),
        'requested_modalities':sorted(modalities),'n_visits':len(table)},
        ['Matching a visit identifier alone does not establish time synchronization.',
         'No feature imputation, causality or clinical fusion prediction is performed.'])


def structural_twin(qc_evidence:dict,review_ledger_state:dict,identity:dict,regional_measurements:list[dict]):
    """Research structural twin contract; no linking based on cohort/name similarity."""
    identity_link(identity)
    require(not identity.get('synthetic_example'), 'SYNTHETIC_IDENTITY_EVIDENCE_BLOCKED')
    require(qc_evidence.get('package_integrity')=='SHA256_VERIFIED' and
            qc_evidence.get('retained_input',{}).get('state')=='SOURCE_SHA256_VERIFIED',
            'MRI_SOURCE_INTEGRITY_REQUIRED')
    require(qc_evidence.get('scan_id')==review_ledger_state.get('package_id'),
            'STRUCTURAL_EVIDENCE_REVIEW_PACKAGE_MISMATCH')
    require(qc_evidence.get('research_cohort')==identity.get('research_cohort') and
            qc_evidence.get('research_subject')==identity.get('research_subject'),
            'STRUCTURAL_IDENTITY_MISMATCH')
    require(review_ledger_state.get('state')=='RESEARCH_REVIEWED_NOT_CLINICALLY_APPROVED',
            'INDEPENDENT_ANATOMICAL_REVIEW_NOT_RECORDED')
    require(qc_evidence.get('atlas_measurements',{}).get('state')=='ARITHMETIC_CONSISTENT_NOT_ANATOMICAL_QC',
            'ATLAS_ARITHMETIC_QC_REQUIRED')
    require(len(regional_measurements)>0,'NAMED_REGION_MEASUREMENTS_REQUIRED')
    rows=[]
    for r in regional_measurements:
        identifier(str(r['region']),'region')
        rows.append({'region':r['region'],'volume_ml':measured(r['volume_ml'],'region_volume',0.000001),
                     'unit':'mL','pipeline_version':r['pipeline_version']})
    return report('3B','LOCAL_RESEARCH_CONTRACT_ONLY_PERSONAL_LINK_NOT_ESTABLISHED',{
        'participant_id':identity['participant_id'],'scan_id':qc_evidence['scan_id'],
        'cohort':identity['research_cohort'],'subject':identity['research_subject'],
        'regions':rows,'review_event_count':review_ledger_state['review_count']},
        ['Independent reviewer identity must be authenticated by the host system.',
         'Research-reviewed anatomy is not clinically accepted anatomy.',
         'A single scan cannot establish longitudinal atrophy or brain-age prediction.'])
