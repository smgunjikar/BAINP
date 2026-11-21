"""Evidence passports: local record consistency, not clinical correctness."""
import json
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from bainp_continuum_engine import person,consent,now,dump,digest,replay,remember
from bainp_mimic_router import Strict,Mode,permission,require,permissions,audit,saved
VERSION='neuroproof-native-v2.0.0'
class Request(Strict):
    operation_id:UUID=Field(strict=False)
    consent_revision:int=Field(ge=1)
    source:Literal['mimic','quest']
    source_id:UUID=Field(strict=False)
def source_record(c,pid,mode,source,key):
    if source=='mimic':
        require(c,pid,mode,'mimic');row,value=saved(c,pid,mode,key)
    else:
        auth=consent(c,pid,mode)
        if not auth['enabled'] or not auth['history_allowed']:raise HTTPException(403,'quest_history_permission_required')
        row=c.execute('SELECT * FROM nq_decisions WHERE id=? AND participant_id=? AND mode=?',(str(key),str(pid),mode)).fetchone()
        if not row:raise HTTPException(404,'decision_not_found')
        value=json.loads(row['payload'])
        if digest(value)!=row['sha256']:raise HTTPException(409,'decision_integrity_failed')
    if value.get('participant_id')!=str(pid) or value.get('mode')!=mode:raise HTTPException(409,'source_identity_mismatch')
    return row,value

def lifecycle(c,pid,mode,source,source_id,value):
    # Read-time metadata never rewrites the stored decision snapshot.
    if source != 'quest':return 'HISTORICAL_REPORT'
    latest=c.execute('SELECT id FROM nq_decisions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1',(str(pid),mode)).fetchone()
    if not latest or latest['id']!=str(source_id):return 'SUPERSEDED'
    try:
        expiry=datetime.fromisoformat(value['expires_at'])
        if expiry.tzinfo is None:return 'FRESHNESS_UNKNOWN'
        if expiry<=datetime.now(timezone.utc):return 'EXPIRED'
    except (KeyError,ValueError,TypeError):return 'FRESHNESS_UNKNOWN'
    context=value.get('context',{})
    if context.get('profile_revision')!=person(c,pid,mode)['revision']:return 'CONTEXT_CHANGED'
    if context.get('consent_revision')!=consent(c,pid,mode)['revision']:return 'CONTEXT_CHANGED'
    return 'RECENT_RECORD_RECHECK_REQUIRED'

def decode_record(row):
    try:
        value=json.loads(row['payload'])
        return value,digest(value)==row['sha256']
    except (ValueError,TypeError):return None,False


def mount(app):
    from neurocontinuum_bridge import _quest_auth
    store=app.state.store
    with store.connect() as c:c.executescript('CREATE TABLE IF NOT EXISTS np_passports(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,source TEXT NOT NULL,source_id TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL,sha256 TEXT NOT NULL);')
    router=APIRouter(prefix='/api/neuroproof/v1',dependencies=[Depends(_quest_auth)])
    permissions(router,store,'proof')
    @router.get('/participants/{pid}')
    def workspace(pid:UUID,mode:Mode):
        with store.connect() as c:
            p=person(c,pid,mode);auth=permission(c,pid,mode,'proof');sources=[];records=[]
            if auth['enabled']:
                for source,table,allowed in [('mimic','nm_reviews',permission(c,pid,mode,'mimic')['enabled']),('quest','nq_decisions',consent(c,pid,mode)['enabled'] and consent(c,pid,mode)['history_allowed'])]:
                    if not allowed:continue
                    for r in c.execute('SELECT id,created_at,payload,sha256 FROM '+table+' WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 50',(str(pid),mode)):
                        value=json.loads(r['payload']);sources.append(dict(source=source,id=r['id'],created_at=r['created_at'],action=value.get('action'),integrity_ok=digest(value)==r['sha256']))
                    for r in c.execute('SELECT * FROM np_passports WHERE participant_id=? AND mode=? AND source=? ORDER BY created_at DESC,id DESC LIMIT 50',(str(pid),mode,source)):
                        value,ok=decode_record(r);current=False;state='INTEGRITY_FAILED' if not ok else 'SOURCE_UNAVAILABLE'
                        try:
                            row,original=source_record(c,pid,mode,source,r['source_id']);current=ok and row['sha256']==value.get('source_sha256');state=lifecycle(c,pid,mode,source,r['source_id'],original)
                        except HTTPException:pass
                        records.append(dict(id=r['id'],created_at=r['created_at'],integrity_ok=ok,source_unchanged=current,lifecycle=state,passport=value if ok else None))
            return dict(name=json.loads(p['profile'])['display_name'],consent=auth,sources=sources,records=records,version=VERSION)
    @router.post('/participants/{pid}/passports')
    def create(pid:UUID,mode:Mode,payload:Request):
        request=dict(kind='proof_create',**payload.model_dump(mode='json'))
        with store.connect(True) as c:
            auth=require(c,pid,mode,'proof')
            if auth['revision']!=payload.consent_revision:raise HTTPException(403,'permission_changed_refresh')
            row,value=source_record(c,pid,mode,payload.source,payload.source_id)
            old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            checks=[]
            if payload.source=='mimic':
                evidence=value['observations'];checks=[dict(reference=o['id'],state='RECORDED_SELF_REPORT_NOT_VERIFIED') for o in evidence]
            else:
                evidence=value.get('context',{}).get('history',[])
                current=app.state.neurocontinuum.ports.history(str(pid),mode)
                index={(o['source'],o['source_id']):o for o in current['observations']+current.get('excluded',[])}
                for o in evidence:
                    latest=index.get((o.get('source'),o.get('source_id')))
                    state='UNRESOLVED' if latest is None else 'CHANGED' if latest.get('source_hash')!=o.get('source_hash') else 'REJECTED_QUALITY' if latest.get('quality')=='QUARANTINED' else 'REFERENCE_MATCH'
                    checks.append(dict(reference=o.get('source_id'),state=state))
            limitations=['Local hashes verify consistency, not source authenticity or clinical correctness.','This passport does not grant clinical clearance or release authorization.','Source policy explanations are preserved, not independently proven.','Research-paper relevance and scientific validity are not automatically verified.','An empty evidence list is not positive evidence of health.']
            if payload.source=='quest' and value.get('context',{}).get('passive_context'):limitations.append('Passive context is preserved in the source decision but not independently revalidated by this passport.')
            passport=dict(version=VERSION,participant_id=str(pid),mode=mode,created_at=now(),source=payload.source,source_id=str(payload.source_id),source_sha256=row['sha256'],recommendation=value,evidence=evidence,checks=checks,traceability_status='NO_REFERENCES' if not checks else 'REVIEW_REQUIRED' if any(x['state']!='REFERENCE_MATCH' for x in checks) else 'AVAILABLE_RECORDS_CONSISTENT',clinical_correctness='NOT_ESTABLISHED',limitations=limitations)
            passport.update(schema_version='2.0',snapshot_kind='SAVED_SOURCE_AT_PASSPORT_CREATION',
                decision_time=value.get('selected_at',value.get('created_at')),
                safety_evidence=value.get('context',{}).get('guard',value.get('guard')),
                safety_authorization='HISTORICAL_ONLY_RECHECK_AT_EXECUTION',
                policy_version=value.get('policy',value.get('passport',{}).get('policy')),
                source_consent_revision=value.get('context',{}).get('consent_revision',value.get('consent_revision')),
                proof_consent_revision=auth['revision'],
                missing_evidence=(['SOURCE_REFERENCES'] if not evidence else [])+(['SAFETY_RECORD'] if not value.get('context',{}).get('guard',value.get('guard')) else []),
                evidence_classification='SELF_REPORTED' if payload.source=='mimic' else 'SOURCE_DECISION_WITH_RECORDED_REFERENCES',
                external_care_status='NOT_VERIFIED_BY_THIS_PASSPORT',
                replay_status='NOT_EXECUTED',clinical_validation=False)
            key=str(uuid4());c.execute('INSERT INTO np_passports VALUES(?,?,?,?,?,?,?,?)',(key,str(pid),mode,payload.source,str(payload.source_id),passport['created_at'],dump(passport),digest(passport)))
            audit(c,pid,mode,'proof','passport_created',key)
            return remember(c,payload.operation_id,str(pid),mode,request,dict(id=key,passport=passport,sha256=digest(passport)))
    @router.get('/participants/{pid}/passports/{key}/export')
    def export(pid:UUID,key:UUID,mode:Mode):
        with store.connect(True) as c:
            require(c,pid,mode,'proof')
            row=c.execute('SELECT * FROM np_passports WHERE id=? AND participant_id=? AND mode=?',(str(key),str(pid),mode)).fetchone()
            if not row:raise HTTPException(404,'passport_not_found')
            value,ok=decode_record(row)
            if not ok:raise HTTPException(409,'passport_integrity_failed')
            original,source=source_record(c,pid,mode,row['source'],row['source_id'])
            if original['sha256']!=value['source_sha256']:raise HTTPException(409,'source_changed_review_required')
            audit(c,pid,mode,'proof','passport_exported',str(key))
            return JSONResponse(dict(id=str(key),passport=value,sha256=row['sha256'],
                exported_at=now(),lifecycle=lifecycle(c,pid,mode,row['source'],row['source_id'],source)),
                headers={'Cache-Control':'no-store','Content-Disposition':'attachment; filename="neuroproof-'+str(key)+'.json"'})
    app.include_router(router)
