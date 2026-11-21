"""Coherent synthetic health context for the same fictional NeuroTwin profiles."""
from datetime import datetime,timedelta,timezone
from bb_engine import build,digest
from bb_provider import summary_for_twin

def demo_snapshot(profile='control',include_sensitive=False):
    impairment=profile=='impairment';records=[];start=datetime(2025,1,1,9,tzinfo=timezone.utc)
    def add(rid,kind,at,**extra):
        raw=dict(revision=1,kind=kind,observed_at=at.isoformat(),available_at=(at+timedelta(minutes=10)).isoformat(),source=dict(kind='self_report',organization='Fictional context source',record_reference=rid),identity_verified=True,quality='usable',context='Synthetic protocol/context; every value is invented',qualifier='exact',disclosure_authorized=False,needs_review=False)
        raw.update(extra)
        records.append(dict(id=rid,payload=raw,known_at=(at+timedelta(minutes=15)).isoformat(),sha256=digest(raw)))
    for visit in range(8):
        at=start+timedelta(days=30*visit);encounter='synthetic-'+profile+'-'+str(visit)
        for metric,value,unit in [('bp_systolic',120+visit*.3+(18 if impairment else 0),'mmHg'),('bp_diastolic',78+visit*.15+(7 if impairment else 0),'mmHg'),('sleep_duration',7.4-(visit*.10 if impairment else .02*visit),'h'),('activity_minutes',160-(visit*7 if impairment else 0),'min/week')]:
            add(encounter+'-'+metric,'measurement',at,metric=metric,value=value,unit=unit,encounter_id=encounter)
        for metric,value,unit in [('hba1c',5.4+(1.2 if impairment else 0)+visit*.015,'%'),('ldl_cholesterol',100+(22 if impairment else 0)+visit,'mg/dL'),('nfl',12+(6 if impairment else 0)+visit*.2,'pg/mL')]:
            rid=encounter+'-'+metric
            raw=dict(revision=1,kind='measurement',observed_at=(at-timedelta(days=3)).isoformat(),available_at=(at-timedelta(days=1)).isoformat(),source=dict(kind='lab_report',organization='Invented laboratory',record_reference=rid),identity_verified=True,metric=metric,value=value,unit=unit,qualifier='exact',quality='usable',context='Invented same-person assay example; not real reference data',assay=dict(name='Synthetic '+metric+' assay',version='illustration-v1',laboratory='Invented laboratory',specimen='whole_blood' if metric=='hba1c' else 'serum' if metric=='ldl_cholesterol' else 'plasma',method='Illustrative only'),reference=dict(kind='reference_interval',lower=0,upper=6 if metric=='hba1c' else 200 if metric=='ldl_cholesterol' else 100,unit=unit,source='INVENTED display interval, not a clinical reference',population_context='Fictional demonstration only',applies_to_participant='yes'),needs_review=False)
            records.append(dict(id=rid,payload=raw,known_at=(at-timedelta(hours=20)).isoformat(),sha256=digest(raw)))
    add('synthetic-'+profile+'-history','condition',start,summary='Fictional pre-existing medical context reported; no condition is inferred by the engine.',effective_start=(start-timedelta(days=365)).isoformat())
    add('synthetic-'+profile+'-sleep-report','sleep_report',start+timedelta(days=210),summary='Fictional report of recent sleep disruption.' if impairment else 'Fictional report of a stable recent sleep routine.',needs_review=impairment)
    add('synthetic-'+profile+'-medication','medication',start+timedelta(days=180),summary='Fictional report of a medication review. No drug or dosage recommendation is generated.',effective_start=(start+timedelta(days=180)).isoformat())
    add('synthetic-'+profile+'-lifestyle','lifestyle_report',start,summary='Fictional activity and smoking history for demonstration; no personalized risk score.')
    add('synthetic-'+profile+'-wellbeing','wellbeing_report',start,summary='Fictional wellbeing discussion documented. No questionnaire items or validated scale result is fabricated.')
    add('synthetic-'+profile+'-family','family_history',start,summary='Fictional family-history context; relative names and raw genetic variants are absent.',relative_degree='first')
    raw=dict(revision=1,kind='measurement',observed_at=start.isoformat(),available_at=(start+timedelta(minutes=10)).isoformat(),source=dict(kind='research_lab',organization='Fictional molecular research laboratory',record_reference='synthetic-'+profile+'-oxidative'),identity_verified=True,metric='f2_isoprostanes',value=.4+(0.2 if impairment else 0),unit='ng/mL',qualifier='exact',quality='review',context='Invented peripheral experimental result, not neuronal oxidative injury',assay=dict(name='Illustrative research assay',version='invented-v1',laboratory='Fictional lab',specimen='urine',method='Illustration only'),needs_review=True)
    records.append(dict(id=raw['source']['record_reference'],payload=raw,known_at=(start+timedelta(minutes=15)).isoformat(),sha256=digest(raw)))
    if include_sensitive:
        raw=dict(revision=1,kind='professional_genomic_finding',observed_at=start.isoformat(),available_at=(start+timedelta(minutes=10)).isoformat(),source=dict(kind='professional_report',organization='Fictional professional',record_reference='synthetic-genomic-'+profile),identity_verified=True,quality='review',qualifier='exact',context='Invented professional context; no genotype is provided',summary='A fictional professional report exists. No genotype, pathogenic variant or disease probability is specified.',professional_interpretation_reference='Fictional report reference; not an actual genetic test',disclosure_authorized=True,needs_review=True)
        records.append(dict(id=raw['source']['record_reference'],payload=raw,known_at=(start+timedelta(minutes=15)).isoformat(),sha256=digest(raw)))
    try:
        from nt_demo import fixtures
        cog=fixtures()[profile]['cognition'];wear=fixtures()[profile]['wearable']
    except ImportError:
        cog={'session_history':[dict(id='synthetic-session-'+str(i),created_at=(start+timedelta(days=i*30,hours=1)).isoformat(),status='completed',protocol='invented-context-demo-v1',form='illustrative') for i in range(8)],'task_series':{}}
        cog['task_series']={'C03':[dict(session_id='synthetic-session-'+str(i),created_at=(start+timedelta(days=i*30,hours=1)).isoformat(),status='completed',condition_group='synthetic-attention-condition',summary={'correct':18-(i//2 if impairment else 0),'omissions':i//3 if impairment else 0,'median_correct_rt_ms':600+(i*25 if impairment else i*2),'quality_flags':[]}) for i in range(8)]}
        wear=[dict(source_id='synthetic-'+profile+'-heart-'+str(i),metric='heart_rate',value=65+(i*.5 if impairment else i*.1),unit='bpm',timestamp=(start+timedelta(days=i*30)).isoformat(),device='Fictional wearable',method='synthetic summary',protocol='invented-context-v1',quality='usable') for i in range(8)]
    consent=dict(revision=1,scopes=['context','clinical_biomarkers','family_history','genomic_summary','molecular_research'],authorization_reference='Fictional demonstration consent',known_at=(start-timedelta(days=30)).isoformat())
    result=build(dict(participant_id='fictional-'+profile,mode='demo',display_name='Fictional '+('cognitive-impairment' if impairment else 'control')+' scenario',profile_revision=1),consent,records,cog,wear,synthetic=True)
    result.update(as_of=None,sensitive_included=include_sensitive,genomic_content_withheld=not include_sensitive,demo_profile=profile,source_status=dict(context='synthetic',wearable='synthetic',cognition='synthetic'))
    result['revision']=digest({k:v for k,v in result.items() if k!='revision'});return result

def demo_context(profile='control'):return summary_for_twin(demo_snapshot(profile))
