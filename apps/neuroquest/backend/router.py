"""Existing operator authentication, storage, Guard and cognition adapters only."""
from pathlib import Path
import json
import sys
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from bainp_continuum_engine import person,consent,now,dump,digest,replay,remember,append_event,save
from bainp_quest_engine import select,VERSION,is_current

class Intent(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    pause_requested:bool=False
    concerns_checked:bool=False
    functional_concern:bool=False
    quality_problem_addressed:bool=False
    target_domain:Literal['none','memory','attention','executive','language']='none'
    signs:list[Literal['face','limb','speech','vision','balance','headache']]=Field(default_factory=list,max_length=6)
class Request(Intent):
    operation_id:UUID=Field(strict=False)
    checkin_id:UUID|None=Field(default=None,strict=False)

def registry():
    import battery
    # Native session order is authoritative; extended tasks are listed but not independently executable.
    return dict(protocol=battery.VERSION,core=list(battery.ORDER),tasks=list(battery.ORDER)+list(battery.EXTENDED),
        execution='native_predefined_batteries_only',single_task_execution=False,clinical_comparability=False,
        accessibility_metadata='No validated alternative-task mappings in the current native catalogue.',
        pathways={'core':'native_predefined_battery','micro':'unavailable','extended':'not_selected_by_current_policy'},
        entries=[dict(id=t,execution='within_native_battery',prerequisites=['C01 and protocol-defined delay'] if t=='C02' else [],
                      clinical_validation=False) for t in list(battery.ORDER)+list(battery.EXTENDED)])

class Service:
    def __init__(self,engine):
        self.engine=engine;self.store=engine.store;self.ports=engine.ports
        with self.store.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS nq_decisions(
                id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
                mode TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL,sha256 TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS nq_participant ON nq_decisions(participant_id,mode,created_at);''')
    def evaluate(self,c,pid,mode,cid,intent,*,fresh_visit_after_incomplete=False):
        p=person(c,pid,mode);auth=consent(c,pid,mode)
        if not auth['enabled']:raise HTTPException(403,'workflow_permission_required')
        # Urgent and review pathways do not depend on routine source services or a prepared check-in.
        if intent['signs'] or intent['functional_concern']:
            urgent={}
            if intent['signs']:
                module=sys.modules.get('bainp_guard')
                if not module or not callable(getattr(module,'urgent',None)):
                    raise HTTPException(503,'urgent_guard_unavailable_use_existing_emergency_guidance')
                urgent=module.urgent(intent['signs'])|{'sources':getattr(module,'URGENT_SOURCES',[])}
                if urgent.get('state')!='escalate':raise HTTPException(503,'urgent_guard_contract_failed')
            context=dict(participant_id=str(pid),mode=mode,profile_revision=p['revision'],consent_revision=auth['revision'],
                profile={},consent={k:bool(auth[k]) for k in ('enabled','history_allowed','assessment_allowed','case_tracking')},
                intent=intent,registry=dict(protocol=None,core=[],tasks=[]),guard=dict(state='urgent_override' if urgent else 'review_path',allowed_actions=[]),
                urgent=urgent,history=[],as_of=now())
            decision=select(context)
            return decision|dict(participant_id=str(pid),mode=mode,checkin_id=str(cid) if cid else None,context=context)
        if not cid:raise HTTPException(422,'select_saved_checkin_for_routine_assessment')
        check=c.execute('SELECT * FROM checkins WHERE id=? AND participant_id=? AND mode=?',(str(cid),str(pid),mode)).fetchone()
        if not check:raise HTTPException(404,'participant_checkin_not_found')
        profile=json.loads(p['profile'])
        urgent=self.ports.urgent(intent['signs']) if intent['signs'] else {}
        access=self.ports.access(str(cid),mode)
        item=dict(checkin_id=str(cid),participant_id=str(pid),mode=mode,payload={})
        holds=self.engine.access_reasons(c,item,p,access)
        guard=self.ports.workflow_decision(dict(participant_id=str(pid),source_participant_id=str(pid),mode=mode,source_mode=mode,
            checkin_id=str(cid),monitoring_consent=bool(auth['enabled']),assessment_consent=bool(auth['assessment_allowed']),
            native_guard_available=self.ports.guard_ready(),access_reasons=holds,urgent_signs=intent['signs'],functional_review_required=intent['functional_concern']))
        history=self.ports.history(str(pid),mode) if auth['history_allowed'] else dict(observations=[],excluded=[])
        refs=[r for r in history['observations']+history.get('excluded',[]) if r['source']=='NeuroCognition X']
        refs.sort(key=lambda r:(r.get('observed_at') or '',r['source_id']),reverse=True)
        context=dict(participant_id=str(pid),mode=mode,profile_revision=p['revision'],consent_revision=auth['revision'],
            profile=profile,consent={k:bool(auth[k]) for k in ('enabled','history_allowed','assessment_allowed','case_tracking')},
            intent=intent,registry=registry(),guard=guard,urgent=urgent,history=refs,as_of=now(),
            fresh_visit_after_incomplete=bool(fresh_visit_after_incomplete))
        from recovery import ticket,authorization
        recovery=ticket(c,cid,mode)
        if recovery:
            reasons=authorization(c,recovery,allow_prelaunch=True)
            if reasons:raise HTTPException(409,','.join(reasons))
            context['recovery']=dict(id=recovery['id'],order=recovery['details']['order'])
        # neuroshadow_quest_context_v1: contextual reference only, no selection influence.
        if hasattr(self.ports,'shadow_context'):
            context['passive_context']=self.ports.shadow_context(c,str(pid),mode)
        decision=select(context)
        decision.update(participant_id=str(pid),mode=mode,checkin_id=str(cid),context=context)
        return decision
    def record(self,c,decision):
        did=str(uuid4());payload=dump(decision)
        if decision['action']=='urgent_guidance':
            for row in c.execute("SELECT * FROM ncw_sessions WHERE participant_id=? AND mode=? AND state NOT IN ('COMPLETED','CANCELLED')",(decision['participant_id'],decision['mode'])).fetchall():
                item=dict(row);item['payload']=json.loads(item['payload']);before=item['state']
                item['state']='BLOCKED';item['version']+=1
                item['payload'].update(safety=decision['guidance'],recommendation=None,reason='NEUROQUEST_URGENT_OVERRIDE',access_reasons=['URGENT_SAFETY_REVIEW_REQUIRED'])
                save(c,item)
                append_event(c,item,str(uuid4()),'safety_override',before,'NEUROQUEST_URGENT_OVERRIDE',dict(decision_id=did))

        c.execute('INSERT INTO nq_decisions VALUES(?,?,?,?,?,?)',(did,decision['participant_id'],decision['mode'],now(),payload,digest(decision)))
        return decision|{'decision_id':did,'sha256':digest(decision)}
    def for_workflow(self,c,item):
        row=c.execute('SELECT payload FROM nq_decisions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(item['participant_id'],item['mode'])).fetchone()
        saved=json.loads(row['payload']) if row else None
        # Never inherit a decision intended for another check-in or person.
        intent=saved['context']['intent'] if saved and saved.get('checkin_id')==item['checkin_id'] else Intent().model_dump()
        independent=bool(item.get('payload',{}).get('independent_reassessment'))
        if independent:
            intent=dict(intent,quality_problem_addressed=True,concerns_checked=True)
        # Recompute safety, profile and source evidence. No unchecked client-side bypass.
        result=self.record(c,self.evaluate(c,item['participant_id'],item['mode'],item['checkin_id'],intent,
            fresh_visit_after_incomplete=independent))
        if result['executable']:result['url']=self.ports.cognition_url(item['checkin_id'],item['mode'])
        return result

def mount(app):
    engine=app.state.neurocontinuum;service=Service(engine);app.state.neuroquest=service
    engine.ports.quest_recommend=service.for_workflow
    # Reuse the exact dependency from the already mounted authenticated NC router.
    from neurocontinuum_bridge import _quest_auth
    router=APIRouter(prefix='/api/neuroquest/v1',dependencies=[Depends(_quest_auth)])
    @router.get('/registry')
    def catalogue():return dict(version=VERSION,**registry())
    @router.get('/participants/{pid}')
    def workspace(pid:UUID,mode:Literal['active','demo']):
        with service.store.connect() as c:
            p=person(c,pid,mode);auth=consent(c,pid,mode)
            records=[]
            if auth['enabled'] and auth['history_allowed']:
                records=[dict(id=r['id'],created_at=r['created_at'],decision=json.loads(r['payload']),sha256=r['sha256'],integrity_ok=digest(json.loads(r['payload']))==r['sha256']) for r in c.execute('SELECT * FROM nq_decisions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,rowid DESC LIMIT 30',(str(pid),mode))]
            checkins=[dict(r) for r in c.execute('SELECT id,status,created_at FROM checkins WHERE participant_id=? AND mode=? ORDER BY created_at DESC LIMIT 50',(str(pid),mode))]
            current=None
            if records:
                latest=records[0]
                try:
                    saved=latest['decision']
                    fresh=service.evaluate(c,str(pid),mode,saved.get('checkin_id'),saved['context']['intent'])
                    current=latest['id'] if latest['integrity_ok'] and is_current(saved,fresh) else None
                except (HTTPException,KeyError,ValueError,TypeError,RuntimeError):
                    current=None
            for record in records:
                record['lifecycle']='current' if record['id']==current else 'historical_not_executable'
            return dict(current_decision_id=current,participant_id=str(pid),name=json.loads(p['profile'])['display_name'],consent=auth,checkins=checkins,decisions=records,registry=registry())
    @router.post('/participants/{pid}/recommendations')
    def recommend(pid:UUID,mode:Literal['active','demo'],payload:Request):
        request={'kind':'neuroquest',**payload.model_dump(mode='json')}
        with service.store.connect(True) as c:
            person(c,pid,mode)
            authorization=consent(c,pid,mode)
            if not authorization['enabled']:raise HTTPException(403,'workflow_permission_required')
            old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:
                latest=c.execute('SELECT id FROM nq_decisions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(str(pid),mode)).fetchone()
                if not latest or latest['id']!=old.get('decision_id'):raise HTTPException(409,'decision_superseded_reevaluate')
                if old['context']['consent_revision']!=authorization['revision']:raise HTTPException(409,'permission_revision_changed_reevaluate')
                intent=payload.model_dump(exclude={'operation_id','checkin_id'})
                fresh=service.evaluate(c,str(pid),mode,payload.checkin_id,intent)
                if not is_current(old,fresh):raise HTTPException(409,'decision_stale_reevaluate_with_new_operation')
                return old
            intent=payload.model_dump(exclude={'operation_id','checkin_id'})
            result=service.record(c,service.evaluate(c,str(pid),mode,payload.checkin_id,intent))
            return remember(c,payload.operation_id,str(pid),mode,request,result)
    app.include_router(router)
