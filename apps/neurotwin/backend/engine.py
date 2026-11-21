"""NeuroTwin research summaries. No diagnosis, imputation, RCI or clinical forecasts.
Source records are authoritative; every snapshot is recomputed from current records.
"""
import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone

VERSION = 'neurotwin-research-v2.0.0'
COGNITIVE_METRICS = {
    'correct': ('Correct responses / withholds', 'count'),
    'hits': ('Recognition hits', 'count'),
    'false_alarms': ('Recognition false alarms', 'count'),
    'correct_sequences': ('Correct spatial sequences', 'count'),
    'max_correct_span': ('Largest correct presented span', 'items'),
    'position_errors': ('Sequence position errors', 'count'),
    'median_response_rt_ms': ('Median response time', 'ms'),
    'omissions': ('Omissions', 'count'),
    'incorrect_responses': ('Incorrect responses', 'count'),
    'median_correct_rt_ms': ('Median correct response time', 'ms'),
    'rt_sample_sd_ms': ('Response-time variability', 'ms'),
    'switch_cost_ms': ('Switch cost', 'ms'),
}

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def stamp(value):
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is None: return None
        return d.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None

def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def estimate(points, aggregation='one observation per UTC day'):
    """Exploratory slope, using daily medians to avoid weighting repeat same-day tests.
    This does not establish clinical comparability or remove practice effects.
    Residual spread is not a confidence or prediction interval.
    """
    daily = defaultdict(list)
    for p in points:
        if p['eligible'] and stamp(p['at']) and numeric(p['value']):
            daily[stamp(p['at']).date().isoformat()].append(p['value'])
    days = sorted(daily)
    base = dict(state='INSUFFICIENT_COMPARABLE_DAYS', days=len(days),
                aggregation=aggregation, slope_per_30_days=None, residual_sd=None,
                confidence_interval=None, practice_effect_estimate=None,
                reliable_change_index=None, clinical_change=None)
    if len(days) < 4: return base
    x = [(datetime.fromisoformat(d)-datetime.fromisoformat(days[0])).days for d in days]
    base['span_days'] = x[-1]
    if x[-1] < 7: return base | {'state': 'INSUFFICIENT_TIME_SPAN'}
    y = [statistics.median(daily[d]) for d in days]
    xm, ym = statistics.mean(x), statistics.mean(y)
    slope = sum((a-xm)*(b-ym) for a,b in zip(x,y))/sum((a-xm)**2 for a in x)
    spread = math.sqrt(sum((b-(ym+slope*(a-xm)))**2 for a,b in zip(x,y))/(len(x)-2))
    return base | dict(state='EXPLORATORY_DESCRIPTIVE_FIT', slope_per_30_days=slope*30,
                       residual_sd=spread, caveat='Unadjusted for practice, serial correlation, time of day and unmeasured context. No validated uncertainty interval.')

def build(cognition, wearable, imaging, forwarded, source_states, identity, links):
    series = {}
    cognitive_records = []
    timeline = []
    issues = []
    # A completed task does not establish that its parent battery completed.
    # Retain raw task measurements from interrupted/cancelled sessions for review,
    # but do not include them in fitted longitudinal research summaries.
    session_statuses = {}
    for session in cognition.get('session_history', []):
        sid = session.get('id')
        if sid is None:
            continue
        status = str(session.get('status') or 'UNVERIFIED').lower()
        if sid in session_statuses and session_statuses[sid] != status:
            session_statuses[sid] = 'INCONSISTENT'
        else:
            session_statuses[sid] = status
    def session_flags(session_id):
        status = session_statuses.get(session_id, 'UNVERIFIED')
        if status == 'completed':
            return status, []
        if status == 'interrupted':
            return status, ['PARENT_SESSION_INTERRUPTED']
        if status in ('cancelled', 'canceled'):
            return status, ['PARENT_SESSION_CANCELLED']
        return status, ['PARENT_SESSION_STATUS_UNVERIFIED']
    def add(source, metric, label, unit, condition, point):
        key = fingerprint([source, metric, unit, condition])[:20]
        item = series.setdefault(key, dict(id=key, source=source, metric=metric, label=label,
                     unit=unit, condition=condition, points=[]))
        item['points'].append(point)
    for session in cognition.get('session_history', []):
        timeline.append(dict(id='cognition:'+session['id'], source='NeuroCognition X',
            at=session['created_at'], title='Cognitive assessment', status=session['status'],
            detail=session['protocol']+' · form '+str(session['form']),
            href='/cognition-results?mode='+identity['mode']+'&session='+session['id']+'&checkin='+session['checkin_id']))
    for task, records in cognition.get('task_series', {}).items():
        # Typed naming/category answers need item-level human review. Preserve source
        # summaries, but do not derive correctness counts from limited dictionaries.
        for r in records:
            sm = r.get('summary') or {}
            parent_status, parent_flags = session_flags(r['session_id'])
            cognitive_records.append(dict(task=task,session_id=r['session_id'],at=r['created_at'],status=r['status'],parent_session_status=parent_status,condition_group=r.get('condition_group'),protocol=r['protocol'],form=r['form'],summary=sm,reviewed_counts=r.get('reviewed_counts')))
            flags = list(sm.get('quality_flags') or []) + parent_flags
            condition = str(r.get('condition_group') or 'UNVERIFIED')
            eligible = r['status']=='completed' and parent_status=='completed' and not flags and condition!='UNVERIFIED'
            for metric, (label, unit) in COGNITIVE_METRICS.items():
                value = sm.get(metric)
                if numeric(value) and task not in ('C06','C09','C10','C12'):
                    add('NeuroCognition X',task+':'+metric,task+' · '+label,unit,condition,
                        dict(at=r['created_at'],value=value,eligible=eligible,
                             flags=flags+([] if r['status']=='completed' else ['ATTEMPT_NOT_COMPLETED']),
                             record_id=r['session_id'],protocol=r['protocol'],form=r['form']))
            if task=='C11':
                for window in sm.get('windows',[]):
                    hand=window.get('hand','unrecorded')
                    if numeric(window.get('rate_per_second')):
                        add('NeuroCognition X','C11:'+hand+':tap_rate','C11 · '+hand+' motor tap rate','taps/s',condition+':'+hand,
                            dict(at=r['created_at'],value=window['rate_per_second'],eligible=False,flags=flags+['MOTOR_DEVICE_OBSERVATION_NOT_COGNITIVE_SCORE'],record_id=r['session_id'],protocol=r['protocol'],form=r['form']))
    for r in wearable:
        # Records from different devices/methods/protocols are never pooled.
        condition = fingerprint([r['device'],r['method'],r['protocol']])[:12]
        add('NeuroSense',r['metric'],r['metric'].replace('_',' ').title(),r['unit'],condition,
            dict(at=r['timestamp'],value=r['value'],eligible=r['quality']=='usable',
                 flags=[] if r['quality']=='usable' else ['QUALITY_'+r['quality'].upper()],
                 record_id=r['source_id'],device=r['device'],method=r['method'],protocol=r['protocol']))
    for record in forwarded:
        for r in record['observations']:
            add(record['source'], r['metric'], r['metric'].replace('_',' ').title(), r['unit'],
                fingerprint([record['source_subject'],record['protocol'],r['context'],r.get('instrument')])[:12],
                dict(at=record['observed_at'],value=r['value'],eligible=r['quality']=='usable',
                     flags=[] if r['quality']=='usable' else ['QUALITY_'+r['quality'].upper()],
                     record_id=record['record_id'],protocol=record['protocol'],
                     provenance=record['provenance'],revision=record['revision']))
        timeline.append(dict(id=record['source']+':'+record['record_id'],source=record['source'],
            at=record['observed_at'],title='Linked source measurements',status='recorded',
            detail=record['protocol'],href=None))
    for scan in imaging:
        m = scan['metadata']
        timeline.append(dict(id='vision:'+scan['id'],source='NeuroVision',at=m.get('date'),
            title='Verified linked MRI · '+str(m.get('visit')),status=m.get('review','UNRECORDED'),
            detail=str(m.get('modality'))+' · '+str(m.get('pipeline')),
            href='/neurovision?mode='+identity['mode'], scan_id=scan['id']))
        for row in m.get('measurements',[]):
            if not numeric(row.get('volume_ml')): continue
            eligible = (m.get('review')=='APPROVED' and m.get('longitudinal_comparable') is True
                        and not m.get('quality_flags') and m.get('date'))
            # Date-only MRI visits are explicitly day-resolution, represented at UTC noon.
            at = m.get('date')+'T12:00:00+00:00' if m.get('date') else None
            add('NeuroVision',str(row['id']),row['name'],'mL',
                fingerprint([m.get('cohort'),m.get('subject'),m.get('protocol'),m.get('pipeline'),row['name']])[:12],
                dict(at=at,value=row['volume_ml'],eligible=bool(eligible),
                     flags=list(m.get('quality_flags',[]))+([] if eligible else ['COMPARABILITY_NOT_ESTABLISHED']),
                     record_id=scan['id'],visit=m.get('visit'),status=row.get('status'),date_precision='day'))
    for item in series.values():
        item['points'].sort(key=lambda p:stamp(p['at']) or datetime.min.replace(tzinfo=timezone.utc))
        # Repeated acquisitions within the same MRI visit are not repeated visits.
        if item['source']=='NeuroVision':
            visits=defaultdict(list)
            for p in item['points']: visits[p.get('visit')].append(p)
            for group in visits.values():
                if len(group)>1:
                    for p in group: p['eligible']=False;p['flags'].append('MULTIPLE_ACQUISITIONS_PER_VISIT')
        # Do not silently sum/median multiple daily step or sleep summaries; they may overlap.
        if item['source']=='NeuroSense' and item['metric'] in ('steps','sleep_duration'):
            days=defaultdict(list)
            for p in item['points']:
                if stamp(p['at']):days[stamp(p['at']).date()].append(p)
            for group in days.values():
                if len(group)>1:
                    for p in group:p['eligible']=False;p['flags'].append('OVERLAPPING_DAILY_SUMMARIES_UNRESOLVED')
        item['estimate']=estimate(item['points'],'median within UTC day; same condition only')
        item['total']=len(item['points']);item['eligible']=sum(p['eligible'] for p in item['points'])
        dates=sorted({stamp(p['at']).date() for p in item['points'] if stamp(p['at'])})
        item['coverage']=dict(observed_days=len(dates),span_days=(dates[-1]-dates[0]).days+1 if dates else 0,
                              expected_schedule=None,missingness_rate=None)
    timeline.sort(key=lambda p:stamp(p['at']) or stamp((p['at'] or '')+'T12:00:00+00:00') or datetime.min.replace(tzinfo=timezone.utc),reverse=True)
    for source,state in source_states.items():
        if state['state']=='error':issues.append(source+': source read failed; no substituted data.')
    # Fingerprint current source content rather than a poll time. Source removals,
    # changes and human reviews therefore invalidate the prior derived snapshot.
    payload=dict(version=VERSION,identity=identity,source_states=source_states,
                 series=list(series.values()),timeline=timeline,imaging=imaging,links=links,cognitive_records=cognitive_records,
                 cognition_sessions=cognition.get('total_sessions',0),issues=issues,
                 forecast=dict(state='UNAVAILABLE_NO_VALIDATED_MODEL',value=None,horizon=None,
                    reason='No evaluated, calibrated participant-level progression model is installed.'),
                 guard=dict(state='RESEARCH_DESCRIPTIVE_ONLY',diagnosis=None,biological_replica=False,
                    causal_interpretation=False,practice_adjustment=False,
                    notes=['Data are linked by participant identity, not by similar names or research groups.',
                           'Condition groups are kept separate. Flagged and interrupted-visit records remain visible and are excluded from fitted trends.',
                           'Missing data are not filled. Expected schedules are unknown; missingness percentages are not invented.',
                           'A descriptive slope is not reliable clinical change. No calibrated forecast or disease risk is generated.']))
    payload['revision']=fingerprint(payload)
    return payload
