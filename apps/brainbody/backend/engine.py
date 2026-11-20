"""Time-aligned descriptive health context. No disease risk score or causal attribution."""
import hashlib,json,math,statistics
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from bb_dictionary import VERSION,METRICS,REPORTS,SYSTEMS,EVIDENCE
from bb_policy import findings,interval_position,BOUNDARIES

def stamp(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if d.tzinfo is None:return None
        return d.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):return None

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def scope(record):return METRICS[record['metric']]['scope'] if record['kind']=='measurement' else REPORTS[record['kind']]['scope']
def definition(record):return METRICS[record['metric']] if record['kind']=='measurement' else REPORTS[record['kind']]
def group_key(record):
    # Reference ranges are report-specific, while assay/specimen/source/instrument
    # determine whether numeric observations can share a descriptive stream.
    assay=record.get('assay') or {};instrument=record.get('instrument') or {};source=record['source']
    return digest([record.get('metric'),record.get('unit'),source.get('kind'),source.get('organization'),source.get('device_id'),source.get('cohort'),source.get('source_subject'),
                   {k:assay.get(k) for k in ('name','version','laboratory','specimen','method')},
                   {k:instrument.get(k) for k in ('name','version','language')},record.get('measurement_context_key') or record['context']])[:20]
def build(identity,consent,records,cognition=None,wearable=None,reviews=None,synthetic=False):
    # records are consent-filtered by provider. Sensitive contents never enter a
    # default snapshot merely to be hidden by CSS.
    records=json.loads(canonical(records));reviews=reviews or {};wearable=wearable or []
    issues=[];series={};queue=[];nodes=[];edges=[];timeline=[]
    for record in records:
        raw=record['payload'];d=definition(raw);record['scope']=scope(raw);record['system']=d['system'];record['label']=d['label']
        notes=findings(raw);record['interval_position']=interval_position(raw) if raw['kind']=='measurement' else None
        if record['interval_position'] in ('BELOW_SUPPLIED_INTERVAL','ABOVE_SUPPLIED_INTERVAL','REFERENCE_APPLICABILITY_UNCONFIRMED','CLINICAL_DECISION_LIMIT_REQUIRES_REVIEW'):
            notes.append(dict(code=record['interval_position'],text='Position relative to a supplied report interval is not a diagnosis. Check reference applicability and clinical context.'))
        record['findings']=notes;record['numeric_eligible']=raw['kind']=='measurement' and raw['qualifier']=='exact' and raw['value'] is not None and raw['quality']=='usable' and not any(n['code']=='QUANTITATION_LIMIT_REVIEW' for n in notes)
        rid=record['id'];nodes.append(dict(id=rid,type='source_record',label=d['label'],observed_at=raw['observed_at'],available_at=raw['available_at'],known_at=record['known_at'],source=raw['source'],revision=raw['revision'],sha256=record['sha256']))
        for n in notes:
            nid=rid+':'+n['code'];nodes.append(dict(id=nid,type='context_or_quality_statement',label=n['text']));edges.append(dict(source=rid,target=nid,relationship='supports_statement_not_causation'))
            review=reviews.get((rid,raw['revision'],n['code']))
            queue.append(dict(record_id=rid,revision=raw['revision'],label=d['label'],code=n['code'],text=n['text'],status=review['status'] if review else 'pending',note=review['note'] if review else None))
        timeline.append(dict(id=rid,at=raw['observed_at'],label=d['label'],kind=raw['kind'],system=d['system'],quality=raw['quality'],available_at=raw['available_at'],known_at=record['known_at']))
        if raw['kind']=='measurement':
            key=group_key(raw);stream=series.setdefault(key,dict(id=key,metric=raw['metric'],label=d['label'],unit=raw['unit'],system=d['system'],assay=raw.get('assay'),source=raw['source'],points=[]))
            stream['points'].append(dict(id=rid,at=raw['observed_at'],value=raw.get('value'),qualifier=raw['qualifier'],eligible=record['numeric_eligible'],known_at=record['known_at'],available_at=raw['available_at'],interval_position=record['interval_position'],flags=[n['code'] for n in notes]))
    # Original NeuroSense observations retain an explicit unknown availability time.
    # No local receipt timestamp is invented for a legacy record.
    for w in wearable:
        if w.get('metric') not in METRICS or not stamp(w.get('timestamp')):continue
        source=dict(kind='device',organization='NeuroSense stored observations',device_id=w['device'],record_reference=w['source_id'])
        raw=dict(kind='measurement',metric=w['metric'],unit=w['unit'],source=source,context=w['method']+' / '+w['protocol'])
        key=group_key(raw);stream=series.setdefault(key,dict(id=key,metric=w['metric'],label=METRICS[w['metric']]['label'],unit=w['unit'],system=METRICS[w['metric']]['system'],assay=None,source=source,points=[]))
        stream['points'].append(dict(id='sense:'+w['source_id'],at=w['timestamp'],value=w['value'],qualifier='exact',eligible=w['quality']=='usable',known_at=w.get('known_at'),available_at=w.get('available_at'),interval_position='NO_SUPPLIED_REFERENCE',flags=[] if w['quality']=='usable' else ['SOURCE_QUALITY_REVIEW']))
    for stream in series.values():
        stream['points'].sort(key=lambda p:stamp(p['at']))
        daily=defaultdict(list)
        for point in stream['points']:daily[stamp(point['at']).date()].append(point)
        if stream['metric'] in ('steps','sleep_duration'):
            for group in daily.values():
                if len(group)>1:
                    for point in group:point['eligible']=False;point['flags'].append('MULTIPLE_DAILY_SUMMARIES_NOT_AGGREGATED')
    # BP components are checked only within one explicit encounter/source pair.
    paired=defaultdict(dict)
    for record in records:
        r=record['payload']
        if r.get('metric') in ('bp_systolic','bp_diastolic') and r.get('encounter_id') and r['qualifier']=='exact' and r['value'] is not None:
            key=(r['encounter_id'],r['source']['organization'],r['source']['kind'],r['source'].get('device_id'),r['source'].get('cohort'),r['source'].get('source_subject'),r.get('measurement_context_key') or r['context'],r['observed_at']);paired[key].setdefault(r['metric'],[]).append(record)
    for group in paired.values():
        if any(len(x)>1 for x in group.values()):
            targets=sum(group.values(),[]);code='AMBIGUOUS_BP_COMPONENTS'
        elif len(group)==2 and group['bp_systolic'][0]['payload']['value']<group['bp_diastolic'][0]['payload']['value']:
            targets=sum(group.values(),[]);code='INVERTED_BP_COMPONENTS'
        else:continue
        for record in targets:
            record['numeric_eligible']=False;record['findings'].append(dict(code=code,text='Check the source blood-pressure components; no correction was invented.'))
            for stream in series.values():
                for point in stream['points']:
                    if point['id']==record['id']:point['eligible']=False;point['flags'].append(code)
            review=reviews.get((record['id'],record['payload']['revision'],code))
            queue.append(dict(record_id=record['id'],revision=record['payload']['revision'],label=record['label'],code=code,text='Check the source blood-pressure components.',status=review['status'] if review else 'pending',note=review['note'] if review else None))
            nid=record['id']+':'+code;nodes.append(dict(id=nid,type='source_quality_statement',label='Check the source blood-pressure components.'));edges.append(dict(source=record['id'],target=nid,relationship='supports_source_review'))
    for stream in series.values():
        daily=defaultdict(list)
        for point in stream['points']:daily[stamp(point['at']).date()].append(point)
        values=[p['value'] for p in stream['points'] if p['eligible']]
        eligible_days=sorted((day,statistics.median(p['value'] for p in pts if p['eligible'])) for day,pts in daily.items() if any(p['eligible'] for p in pts))
        stream['summary']=dict(total=len(stream['points']),usable=len(values),observed_days=len(daily),eligible_days=len(eligible_days),first=values[0] if values else None,latest=values[-1] if values else None,median=statistics.median(values) if values else None,sample_sd=statistics.stdev(values) if len(values)>1 else None,descriptive_first_last_change=eligible_days[-1][1]-eligible_days[0][1] if len(eligible_days)>1 else None,clinical_change=None,missingness_rate=None)
    alignments=[];cognition=cognition or {}
    for session in cognition.get('session_history',[]):
        anchor=stamp(session['created_at'])
        if not anchor:continue
        prior=[];retrospective=[];unknown=[]
        for record in records:
            raw=record['payload'];observed=stamp(raw['observed_at']);days=3 if raw.get('metric') in ('sleep_duration','sleep_efficiency','heart_rate') or raw['kind']=='sleep_report' else 30
            effective=stamp(raw.get('effective_start'));end=stamp(raw.get('effective_end'))
            # A dated family/medical-history report remains reported context, not a diagnosis of an active condition. Medication exposure requires an explicit effective interval.
            history_start=effective or (observed if raw['kind'] in ('condition','family_history') else None)
            history_active=raw['kind'] in ('condition','medication','family_history') and history_start and history_start<=anchor and (not end or end>=anchor)
            if not history_active and not anchor-timedelta(days=days)<=observed<=anchor:continue
            item=dict(record_id=record['id'],label=record['label'],observed_at=raw['observed_at'],source_kind=raw['source']['kind'])
            if stamp(raw['available_at'])<=anchor and stamp(record['known_at']) and stamp(record['known_at'])<=anchor:prior.append(item)
            else:retrospective.append(item)
        for w in wearable:
            at=stamp(w.get('timestamp'))
            if not at or not anchor-timedelta(days=3)<=at<=anchor:
                continue
            item = dict(record_id='sense:'+w['source_id'], label=METRICS[w['metric']]['label'],
                        observed_at=w['timestamp'], source_kind='device')
            available = stamp(w.get('available_at'))
            received = stamp(w.get('known_at'))
            if not available or not received:
                unknown.append(item)
            elif available <= anchor and received <= anchor:
                prior.append(item)
            else:
                retrospective.append(item)
        alignments.append(dict(session_id=session['id'],session_start=session['created_at'],status=session['status'],protocol=session['protocol'],form=session['form'],known_before_session=prior,retrospectively_entered=retrospective,availability_unknown=unknown,interpretation='Temporal context only; no cause of the cognitive result is established. Anchor is session start, not synchronized acquisition.'))
    task_points=[]
    for task,items in cognition.get('task_series',{}).items():
        if task in ('C06','C09','C10','C12'):continue  # Reports/typed lexical reviews are not generic correctness scores.
        for item in items:
            for metric in ('correct','omissions','median_correct_rt_ms'):
                value=(item.get('summary') or {}).get(metric)
                if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):task_points.append(dict(task=task,metric=metric,value=value,at=item['created_at'],session_id=item['session_id'],condition_group=item.get('condition_group'),status=item['status'],flags=(item.get('summary') or {}).get('quality_flags',[])))
    timeline.sort(key=lambda r:stamp(r['at']),reverse=True)
    result=dict(version=VERSION,identity=identity,synthetic=synthetic,consent=consent,records=records,series=list(series.values()),timeline=timeline,review_queue=queue,alignments=alignments,cognitive_points=task_points,
        systems=[dict(id=k,label=v,records=sum(r['system']==k for r in records),streams=sum(s['system']==k for s in series.values())) for k,v in SYSTEMS.items()],
        graph=dict(nodes=nodes,edges=edges),evidence=EVIDENCE,boundaries=BOUNDARIES,issues=issues,
        predictions=dict(state='NO_VALIDATED_BRAIN_BODY_PREDICTION_MODEL',risk=None,causal_effect=None),
        roadmap=[['BB-1','Dictionary, consent, provenance and unit validation','Implemented'],['BB-2','Cardiovascular, metabolic, sleep and lifestyle workspace','Implemented'],['BB-3','Timeline and NeuroTwin source refresh','Implemented for supported linked sources'],['BB-4','ADNI-linked research','Typed export and research comparison tooling; private cohort not evaluated here'],['BB-5','Evidence-aware explanations and quality review','Implemented; no diagnosis or treatment selection'],['BB-6','Disease-specific multimodal forecasting','Not clinically validated or deployed'],['BB-7','Genomic and molecular research','Professional-summary/research storage boundaries; no automatic genomic or oxidative-stress diagnosis']])
    result['revision']=digest(result);return result
