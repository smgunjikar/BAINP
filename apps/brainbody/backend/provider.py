"""Read current consent and immutable record revisions; same participant/mode only."""
import json,math
from datetime import datetime,timezone
from bb_engine import build,stamp,digest
from bb_dictionary import METRICS
from bb_identity import conflicting_owner,ownership_index
SCHEMA='''
CREATE TABLE IF NOT EXISTS bb_consents(participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,revision INTEGER,scopes TEXT,authorization_reference TEXT,known_at TEXT,PRIMARY KEY(participant_id,mode,revision));
CREATE TABLE IF NOT EXISTS bb_records(id TEXT PRIMARY KEY,participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,source_key TEXT,scope TEXT NOT NULL,UNIQUE(participant_id,mode,source_key));
CREATE TABLE IF NOT EXISTS bb_versions(record_id TEXT REFERENCES bb_records(id) ON DELETE CASCADE,revision INTEGER,payload TEXT,known_at TEXT,sha256 TEXT,PRIMARY KEY(record_id,revision));
CREATE TABLE IF NOT EXISTS bb_identity_links(participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,cohort TEXT,source_subject TEXT,PRIMARY KEY(mode,cohort,source_subject));
CREATE TABLE IF NOT EXISTS bb_reviews(record_id TEXT REFERENCES bb_records(id) ON DELETE CASCADE,revision INTEGER,finding_code TEXT,status TEXT,note TEXT,known_at TEXT,PRIMARY KEY(record_id,revision,finding_code));
CREATE INDEX IF NOT EXISTS bb_person_records ON bb_records(participant_id,mode);
'''
def consent_at(c,pid,mode,asof=None):
    rows=[dict(r) for r in c.execute('SELECT * FROM bb_consents WHERE participant_id=? AND mode=? ORDER BY revision',(str(pid),mode))]
    if not rows:return dict(revision=0,scopes=[],authorization_reference=None,known_at=None)
    current=rows[-1];historical=[r for r in rows if not asof or stamp(r['known_at'])<=asof]
    scopes=set(json.loads(current['scopes'])) & (set(json.loads(historical[-1]['scopes'])) if historical else set())
    return dict(revision=current['revision'],scopes=sorted(scopes),authorization_reference=current['authorization_reference'],known_at=current['known_at'])
def read_context(store,pid,mode,asof=None,include_sensitive=False,cognition=None,cognition_analytics=None):
    cutoff=asof or datetime.now(timezone.utc);items={};review_rows={};wear=[];issues=[];withheld=False
    with store.connect() as c:
        p=c.execute('SELECT * FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone()
        if p is None:raise LookupError('participant_not_found')
        identity=dict(participant_id=str(pid),mode=mode,display_name=json.loads(p['profile'])['display_name'],profile_revision=p['revision'])
        consent=consent_at(c,pid,mode,asof)
        allowed=[s for s in consent['scopes'] if include_sensitive or s!='genomic_summary']
        if 'genomic_summary' in consent['scopes'] and not include_sensitive:
            withheld=bool(c.execute("SELECT 1 FROM bb_records WHERE participant_id=? AND mode=? AND scope='genomic_summary' LIMIT 1",(str(pid),mode)).fetchone())
        rows=[]
        if allowed:
            rows=c.execute('SELECT r.id,v.revision,v.payload,v.known_at,v.sha256 FROM bb_records r JOIN bb_versions v ON v.record_id=r.id WHERE r.participant_id=? AND r.mode=? AND r.scope IN ('+','.join('?' for _ in allowed)+') ORDER BY r.id,v.revision',[str(pid),mode,*allowed])
        peer_owners=None
        for row in rows:
            if stamp(row['known_at'])>cutoff:continue
            raw=json.loads(row['payload'])
            if raw['source'].get('cohort') and peer_owners is None:peer_owners=ownership_index(c,mode)
            if conflicting_owner(c,pid,mode,raw['source'].get('cohort'),raw['source'].get('source_subject'),peer_owners):
                issues.append('A source subject conflicts with another module participant link and was excluded.');continue
            if stamp(raw['observed_at'])>cutoff or stamp(raw['available_at'])>cutoff:continue
            from bb_engine import scope
            needed=scope(raw)
            if needed not in consent['scopes']:continue
            if needed=='genomic_summary' and not include_sensitive:withheld=True;continue
            items[row['id']]=dict(id=row['id'],payload=raw,known_at=row['known_at'],sha256=row['sha256'])
        review_query=[]
        if allowed:review_query=c.execute('SELECT q.* FROM bb_reviews q JOIN bb_records r ON r.id=q.record_id WHERE r.participant_id=? AND r.mode=? AND r.scope IN ('+','.join('?' for _ in allowed)+')',[str(pid),mode,*allowed])
        for row in review_query:
            key=(row['record_id'],row['revision'],row['finding_code'])
            if stamp(row['known_at'])<=cutoff:review_rows[key]=dict(row)
            elif asof:review_rows[key]={'status':'historical_review_state_not_reconstructed','note':None}
        exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sense_observations'").fetchone()
        if exists and 'context' in consent['scopes']:
            for row in c.execute('SELECT payload FROM sense_observations WHERE participant_id=? AND mode=? ORDER BY source_id',(str(pid),mode)):
                try:
                    w=json.loads(row['payload'])
                    metric = METRICS.get(w['metric'])
                    if not metric or metric['scope'] != 'context' or metric['assay_required'] or 'device' not in metric['origins']:
                        raise ValueError('metric is not eligible for the wearable context adapter')
                    if w['unit'] not in metric['units'] or not isinstance(w['value'],(int,float)) or isinstance(w['value'],bool) or not math.isfinite(w['value']) or w['value']<0 or not stamp(w['timestamp']):raise ValueError()
                    if not all(isinstance(w.get(field), str) and w[field].strip() for field in ('device','method','protocol','source_id')):
                        raise ValueError('missing wearable provenance')
                    if w.get('quality') not in ('usable','review','invalid'):
                        raise ValueError('invalid wearable quality')
                    observed = stamp(w['timestamp'])
                    available = stamp(w.get('available_at'))
                    received = stamp(w.get('known_at'))
                    if available and received and (available < observed or received < available):
                        issues.append('A wearable record had inconsistent availability timestamps. Its timing is shown as unknown.')
                        available = received = None
                        w.update(available_at=None, known_at=None)
                    if asof and (not available or not received):
                        issues.append('Legacy wearable availability/receipt times are unknown; those records are withheld from historical replay.');continue
                    if observed <= cutoff and all(clock is None or clock <= cutoff for clock in (available, received)):
                        wear.append(w)
                except (ValueError,KeyError,TypeError,OverflowError):issues.append('A legacy wearable record failed validation and was excluded.')
    if cognition is None and cognition_analytics and 'context' in consent['scopes']:
        try:cognition=cognition_analytics(pid=pid,mode=mode)
        except (ValueError,KeyError,TypeError):issues.append('Cognitive context source could not be read.')
    if 'context' not in consent['scopes']:cognition={}
    if asof and cognition:
        cognition=json.loads(json.dumps(cognition))
        cognition['session_history']=[dict(s,status='historical_start_only_result_status_not_reconstructed') for s in cognition.get('session_history',[]) if stamp(s['created_at']) and stamp(s['created_at'])<=cutoff]
        finished={}
        with store.connect() as c:
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nc_attempts'").fetchone():
                finished={(r['session_id'],r['task']):stamp(r['finished_at']) for r in c.execute('SELECT a.session_id,a.task,a.finished_at FROM nc_attempts a JOIN nc_sessions s ON s.id=a.session_id WHERE s.participant_id=? AND s.mode=?',(str(pid),mode))}
        cognition['task_series']={task:[p for p in points if finished.get((p['session_id'],task)) and finished[(p['session_id'],task)]<=cutoff] for task,points in cognition.get('task_series',{}).items()}
        issues.append('Historical cognitive points require a verified source finish time; current whole-battery status is not reconstructed.')
    result=build(identity,consent,list(items.values()),cognition,wear,review_rows)
    result.update(as_of=asof.isoformat() if asof else None,sensitive_included=include_sensitive and 'genomic_summary' in consent['scopes'],genomic_content_withheld=withheld)
    result['issues'].extend(sorted(set(issues)))
    result['source_status']=dict(context='authorized' if consent['scopes'] else 'consent_required',wearable='stored_source_available' if wear else 'no_authorized_observations',cognition='available' if (cognition or {}).get('session_history') else 'no_authorized_sessions')
    result['revision']=digest({k:v for k,v in result.items() if k!='revision'});return result

def for_twin(store,pid,mode,cognition=None):
    result=read_context(store,pid,mode,cognition=cognition,include_sensitive=False)
    return summary_for_twin(result)
def summary_for_twin(result):
    # The twin receives a bounded nonsensitive context summary, not genomic contents.
    latest=[]
    for s in result['series']:
        point=s['points'][-1] if s['points'] else None
        if point:latest.append(dict(label=s['label'],value=point['value'],qualifier=point['qualifier'],unit=s['unit'],observed_at=point['at'],interval_position=point['interval_position'],source=s['source']['kind']))
    return dict(version=result['version'],revision=result['revision'],synthetic=result['synthetic'],authorized_scopes=[s for s in result['consent']['scopes'] if s!='genomic_summary'],record_count=len(result['records']),pending_reviews=sum(r['status']=='pending' for r in result['review_queue']),issues=result['issues'],latest=latest[:12],recent_alignments=result['alignments'][-3:],interpretation='Source-linked descriptive context, not a cause, disease diagnosis or model-derived prevention benefit.')
