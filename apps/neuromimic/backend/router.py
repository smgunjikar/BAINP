"""Native contributor context capture. No diagnosis or automated lab interpretation."""
import json,sys
from typing import Literal
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from bainp_continuum_engine import person,consent,now,dump,digest,replay,remember
VERSION='neuromimic-native-v1.0.0'
DOMAINS=('sleep','medication_review','vitamin_b12','thyroid','metabolic')
Mode=Literal['active','demo']
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',strict=True)
class Permission(Strict):
    operation_id:UUID=Field(strict=False)
    expected_revision:int=Field(ge=0)
    enabled:bool
class Concern(Strict):
    domain:Literal['sleep','medication_review','vitamin_b12','thyroid','metabolic']
    state:Literal['unknown','no_concern_reported','concern_reported']
class Review(Strict):
    operation_id:UUID=Field(strict=False)
    consent_revision:int=Field(ge=1)
    concerns:list[Concern]=Field(min_length=5,max_length=5)
    signs:list[Literal['face','limb','speech','vision','balance','headache']]=Field(default_factory=list,max_length=6)
    functional_concern:bool=False
    request_review:bool=False
class CaseRequest(Strict):operation_id:UUID=Field(strict=False)
SCHEMA='''
CREATE TABLE IF NOT EXISTS nmp_permissions(participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,module TEXT NOT NULL,revision INTEGER NOT NULL,enabled INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(participant_id,mode,module));
CREATE TABLE IF NOT EXISTS nm_reviews(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL,sha256 TEXT NOT NULL,case_id TEXT);
CREATE TABLE IF NOT EXISTS nmp_events(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,module TEXT NOT NULL,at TEXT NOT NULL,action TEXT NOT NULL,reference TEXT NOT NULL);
'''
def permission(c,pid,mode,module):
    row=c.execute('SELECT * FROM nmp_permissions WHERE participant_id=? AND mode=? AND module=?',(str(pid),mode,module)).fetchone()
    return dict(row) if row else dict(revision=0,enabled=0)
def require(c,pid,mode,module):
    person(c,pid,mode);p=permission(c,pid,mode,module)
    if not p['enabled']:raise HTTPException(403,'explicit_'+module+'_permission_required')
    return p

def audit(c,pid,mode,module,action,ref):c.execute('INSERT INTO nmp_events VALUES(?,?,?,?,?,?,?)',(str(uuid4()),str(pid),mode,module,now(),action,ref))
def permissions(router,store,module):
    @router.put('/participants/{pid}/consent')
    def configure(pid:UUID,mode:Mode,payload:Permission):
        request=dict(kind=module+'_permission',**payload.model_dump(mode='json'))
        with store.connect(True) as c:
            person(c,pid,mode);old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            current=permission(c,pid,mode,module)
            if current['revision']!=payload.expected_revision:raise HTTPException(409,'permission_changed_refresh')
            revision=current['revision']+1
            c.execute('INSERT OR REPLACE INTO nmp_permissions VALUES(?,?,?,?,?,?)',(str(pid),mode,module,revision,int(payload.enabled),now()))
            audit(c,pid,mode,module,'permission_changed',str(revision))
            return remember(c,payload.operation_id,str(pid),mode,request,dict(revision=revision,enabled=payload.enabled))

def saved(c,pid,mode,rid):
    row=c.execute('SELECT * FROM nm_reviews WHERE id=? AND participant_id=? AND mode=?',(str(rid),str(pid),mode)).fetchone()
    if not row:raise HTTPException(404,'review_not_found')
    value=json.loads(row['payload'])
    if digest(value)!=row['sha256']:raise HTTPException(409,'review_integrity_failed')
    return row,value

def mount(app):
    from neurocontinuum_bridge import _quest_auth
    store=app.state.store
    with store.connect() as c:c.executescript(SCHEMA)
    router=APIRouter(prefix='/api/neuromimic/v1',dependencies=[Depends(_quest_auth)])
    permissions(router,store,'mimic')
    @router.get('/participants/{pid}')
    def workspace(pid:UUID,mode:Mode):
        with store.connect() as c:
            p=person(c,pid,mode);auth=permission(c,pid,mode,'mimic');rows=[]
            if auth['enabled']:
                for r in c.execute('SELECT * FROM nm_reviews WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 50',(str(pid),mode)):
                    value=json.loads(r['payload']);ok=digest(value)==r['sha256']
                    rows.append(dict(id=r['id'],created_at=r['created_at'],integrity_ok=ok,case_id=r['case_id'],review=value if ok else None))
            return dict(name=json.loads(p['profile'])['display_name'],consent=auth,records=rows,version=VERSION)
    @router.post('/participants/{pid}/reviews')
    def review(pid:UUID,mode:Mode,payload:Review):
        request=dict(kind='mimic_review',**payload.model_dump(mode='json'))
        with store.connect(True) as c:
            auth=require(c,pid,mode,'mimic')
            if auth['revision']!=payload.consent_revision:raise HTTPException(403,'permission_changed_refresh')
            old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            if set(x.domain for x in payload.concerns)!=set(DOMAINS):raise HTTPException(422,'each_domain_required_once')
            guard=sys.modules.get('bainp_guard')
            if not guard or not callable(getattr(guard,'urgent',None)):raise HTTPException(503,'neuroguard_unavailable')
            guidance=guard.urgent(payload.signs)
            urgent=guidance.get('state')=='escalate'
            if payload.signs and not urgent:raise HTTPException(503,'unexpected_guard_response')
            rid=str(uuid4());at=now()
            observations=[dict(id=rid+':'+x.domain,participant_id=str(pid),mode=mode,domain=x.domain,state=x.state,source='local_operator_recorded_participant_report',observed_at=at,quality='SELF_REPORTED_NOT_CLINICALLY_VERIFIED',processing_version=VERSION) for x in payload.concerns]
            findings=[] if urgent else [o for o in observations if o['state']=='concern_reported']
            action='urgent_guard_path' if urgent else 'professional_review' if findings or payload.functional_concern or payload.request_review else 'information_recorded'
            value=dict(participant_id=str(pid),mode=mode,policy=VERSION,created_at=at,consent_revision=auth['revision'],action=action,findings=findings,observations=observations,missing_domains=[o['domain'] for o in observations if o['state']=='unknown'],functional_concern=payload.functional_concern,requested_review=payload.request_review,guard=guidance,guard_sources=getattr(guard,'URGENT_SOURCES',[]) if urgent else [],clinical_validation=False,limitations=['Recorded reports are not verified clinical findings.','No lab interpretation, medication advice, causal conclusion or neurological exclusion.','Missing information does not rule out a contributor.','Routine contributor review must not delay urgent care or specialist referral.'])
            c.execute('INSERT INTO nm_reviews VALUES(?,?,?,?,?,?,NULL)',(rid,str(pid),mode,at,dump(value),digest(value)))
            audit(c,pid,mode,'mimic','review_recorded',rid)
            return remember(c,payload.operation_id,str(pid),mode,request,dict(id=rid,review=value,sha256=digest(value)))
    @router.post('/participants/{pid}/reviews/{rid}/case')
    def create_case(pid:UUID,rid:UUID,mode:Mode,payload:CaseRequest):
        with store.connect(True) as c:
            require(c,pid,mode,'mimic');auth=consent(c,pid,mode)
            if not auth['enabled'] or not auth['case_tracking']:raise HTTPException(403,'enable_neurocontinuum_case_tracking_permission')
            row,value=saved(c,pid,mode,rid)
            if row['case_id']:return dict(case_id=row['case_id'],contacted_clinician=False)
            cases=sys.modules.get('bainp_cases')
            if not cases:raise HTTPException(503,'careloop_unavailable')
            case_id=str(uuid4());data=dict(case_id=case_id,category='memory',concern='NeuroMimic reported context review. Evidence record: '+str(rid)+'. No cause established.',share_with_twin=False)
            result=cases.intake(c,mode,str(pid),data,'professional_review_suggested')
            item=cases.select_case(c,mode,str(pid),case_id)
            cases.transition(c,item,dict(operation_id=str(payload.operation_id),expected_version=result['version'],action='request_review',note='Participant requested local follow-up. Review Mimic evidence and any urgent guidance first.',reference=None,due_on=None))
            c.execute('UPDATE nm_reviews SET case_id=? WHERE id=?',(case_id,str(rid)))
            audit(c,pid,mode,'mimic','careloop_requested',case_id)
            return dict(case_id=case_id,contacted_clinician=False)
    app.include_router(router)
