"""Account-scoped local care coordination. No provider delivery or clinical attestation."""
import json,sys
from datetime import date,datetime,timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictBool
import bainp_cases as cases
from bainp_sim import digest
SCHEMA='''
CREATE TABLE IF NOT EXISTS careloop_v2_details(
 case_id TEXT PRIMARY KEY REFERENCES careloop_cases(id) ON DELETE CASCADE,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS careloop_v2_audit(
 case_id TEXT NOT NULL REFERENCES careloop_cases(id) ON DELETE CASCADE,version INTEGER NOT NULL,
 actor TEXT NOT NULL,role TEXT NOT NULL,workspace TEXT NOT NULL,action TEXT NOT NULL,at TEXT NOT NULL,
 PRIMARY KEY(case_id,version));
'''
Mode=Literal['active','demo']
Sign=Literal['face','limb','speech','vision','balance','headache']
class Input(BaseModel):
 model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Concern(Input):
 case_id:UUID
 category:Literal['memory','daily_function','sleep','movement','behavior','other']
 concern:str=Field(min_length=5,max_length=1000)
 onset:date|None=None
 reported_by:Literal['self','assisted_self']='self'
 functional_change:StrictBool=False
 consent:StrictBool
 share_with_twin:StrictBool=False
 signs:list[Sign]=Field(default_factory=list,max_length=6)
 safety_checked:StrictBool
 decision_id:UUID|None=None
class Event(Input):
 operation_id:UUID
 expected_version:int=Field(strict=True,ge=1)
 action:Literal['request_review','plan_monitoring','document_referral','plan_followup','confirm_followup','record_outcome','close','reopen','withdraw','report_appointment','record_goal','complete_goal']
 note:str|None=Field(None,min_length=5,max_length=1000)
 reference:str|None=Field(None,min_length=3,max_length=180)
 due_on:date|None=None
 signs:list[Sign]=Field(default_factory=list,max_length=6)
 safety_checked:StrictBool=False

def identity():
 module=sys.modules.get('accounts')
 if not module or not hasattr(module,'require_identity'):raise HTTPException(503,'account_identity_required')
 p=module.require_identity()
 return dict(actor=p['user_id'],role=p['role'],workspace=p.get('target') or p['user_id'])
def audit(c,item,action):
 a=identity();c.execute('INSERT INTO careloop_v2_audit VALUES(?,?,?,?,?,?,?)',(item['id'],item['version'],a['actor'],a['role'],a['workspace'],action,cases.now()))
def guard(signs,checked):
 module=sys.modules.get('bainp_guard')
 if not module or not callable(getattr(module,'urgent',None)):raise HTTPException(503,'safety_service_unavailable')
 result=module.urgent(signs)
 if signs:
  if result.get('state')!='escalate':raise HTTPException(503,'safety_contract_unavailable')
  return result|{'sources':getattr(module,'URGENT_SOURCES',[])}
 if not checked:raise HTTPException(422,'current_safety_check_required')
 return None

def details(c,key):
 r=c.execute('SELECT payload FROM careloop_v2_details WHERE case_id=?',(key,)).fetchone()
 return json.loads(r['payload']) if r else {'source':'legacy_local_record','appointment':None,'goal':None,'decision':None}
def show(c,item):
 v=cases.view_case(c,item)
 if item['state']=='withdrawn':return v
 d=details(c,item['id']);v['details']=d
 v['coordination']={'case':'CLOSED' if item['state']=='closed' else 'RESOLVED' if item['state']=='outcome_recorded' else 'OPEN',
  'referral':'LOCAL_ONLY','appointment':'REPORTED_OUTSIDE_BAINP' if d.get('appointment') else 'NOT_CONFIRMED',
  'provider_connected':False,'clinician_verified':False,'monitored_queue':False,
  'next_step':'Contact an appropriate healthcare service yourself and bring your concern summary. BAINP has not sent a referral or booked an appointment.'}
 v['audit']=[dict(r) for r in c.execute('SELECT * FROM careloop_v2_audit WHERE case_id=? ORDER BY version',(item['id'],))]
 v['limitations']=['Historical events without an actor entry are unattributed legacy records.','Outside confirmations are user-reported, not independently provider-verified.','This summary is not a diagnosis or a monitored clinical service.']
 return v

def decision(c,pid,mode,key):
 if not key:return None
 if not c.execute("SELECT 1 FROM sqlite_master WHERE name='nq_decisions'").fetchone():raise HTTPException(409,'recommendation_service_unavailable')
 rows=c.execute('SELECT * FROM nq_decisions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1',(pid,mode)).fetchall()
 if not rows or rows[0]['id']!=str(key):raise HTTPException(409,'recommendation_not_current')
 d=json.loads(rows[0]['payload'])
 if d.get('action')!='professional_review' or datetime.fromisoformat(d['expires_at'])<=datetime.now(timezone.utc):raise HTTPException(409,'recommendation_expired_or_not_review')
 p=c.execute('SELECT revision FROM participants WHERE id=? AND mode=?',(pid,mode)).fetchone()
 a=c.execute('SELECT * FROM ncw_consents WHERE participant_id=? AND mode=?',(pid,mode)).fetchone()
 passport=d.get('passport',{})
 if not a or not a['enabled'] or not a['case_tracking'] or not p or passport.get('profile_revision')!=p['revision'] or passport.get('consent_revision')!=a['revision']:
  raise HTTPException(409,'recommendation_context_changed')
 # Link is provenance only; current consent and safety are checked independently.
 return {'id':str(key),'recorded_at':rows[0]['created_at'],'reason':d.get('reason'),'status':'current_when_linked','external_delivery':False}

def make_router(store,authenticated):
 with store.connect() as c:c.executescript(SCHEMA)
 router=APIRouter(prefix='/api/prevention/careloop/v2',dependencies=[Depends(authenticated)])
 def owner(c,mode,person):
  identity()
  if person is None:raise HTTPException(422,'select_participant')
  pid=str(person);cases.require_owner(c,mode,pid);return pid
 @router.get('/cases')
 def listing(mode:Mode,person:UUID):
  with store.connect() as c:
   pid=owner(c,mode,person)
   rows=c.execute('SELECT * FROM careloop_cases WHERE participant_id=? AND mode=? ORDER BY updated_at DESC,id',(pid,mode)).fetchall()
   return {'cases':[show(c,r) for r in rows],'provider_connected':False,'clinical_queue_available':False}
 @router.get('/cases/{key}')
 def read(key:UUID,mode:Mode,person:UUID):
  with store.connect() as c:
   pid=owner(c,mode,person);return show(c,cases.select_case(c,mode,pid,str(key)))
 @router.post('/cases')
 def create(payload:Concern,mode:Mode,person:UUID|None=None):
  identity();urgent=guard(payload.signs,payload.safety_checked)
  if urgent:return {'case':None,'safety':urgent}
  if not payload.consent:raise HTTPException(422,'explicit_case_consent_required')
  if payload.onset and payload.onset>date.today():raise HTTPException(422,'onset_cannot_be_future')
  with store.connect(True) as c:
   pid=owner(c,mode,person);data=payload.model_dump(mode='json')
   prior=c.execute('SELECT * FROM careloop_cases WHERE id=?',(str(payload.case_id),)).fetchone()
   if prior:
    if prior['participant_id']!=pid or prior['mode']!=mode or prior['intake_digest']!=digest(data):raise HTTPException(409,'case_key_conflict')
    return {'case':show(c,prior),'replayed':True}
   linked=decision(c,pid,mode,payload.decision_id)
   v=cases.intake(c,mode,pid,data,'professional_review_suggested' if payload.functional_change else 'local_followup')
   d={'onset':data['onset'],'reported_by':data['reported_by'],'functional_change':data['functional_change'],'consent_recorded_at':cases.now(),'decision':linked,'appointment':None,'goal':None}
   c.execute('INSERT INTO careloop_v2_details VALUES(?,?)',(v['id'],json.dumps(d)))
   audit(c,v,'intake');return {'case':show(c,cases.select_case(c,mode,pid,v['id']))}
 @router.post('/cases/{key}/events')
 def event(key:UUID,payload:Event,mode:Mode,person:UUID):
  identity()
  if payload.action!='withdraw':
   urgent=guard(payload.signs,payload.safety_checked)
   if urgent:return {'case':None,'safety':urgent}
   if not payload.note:raise HTTPException(422,'workflow_note_required')
  elif payload.note or payload.reference or payload.due_on:raise HTTPException(422,'withdrawal_uses_no_case_details')
  with store.connect(True) as c:
   pid=owner(c,mode,person);item=cases.select_case(c,mode,pid,str(key));data=payload.model_dump(mode='json');rd=digest(data)
   prev=c.execute('SELECT request_digest FROM careloop_events WHERE case_id=? AND operation_id=?',(str(key),str(payload.operation_id))).fetchone()
   if prev:
    if prev['request_digest']!=rd:raise HTTPException(409,'operation_key_conflict')
    return show(c,item)
   if item['state']=='withdrawn':raise HTTPException(409,'case_withdrawn')
   if item['version']!=payload.expected_version:raise HTTPException(409,'case_changed_refresh')
   if payload.action in ('report_appointment','record_goal','complete_goal'):
    if item['state']=='closed':raise HTTPException(409,'reopen_case_first')
    d=details(c,str(key))
    if payload.action=='report_appointment':
     if not payload.due_on or not payload.reference:raise HTTPException(422,'appointment_date_and_reported_reference_required')
     d['appointment']={'date':data['due_on'],'reference':payload.reference,'note':payload.note,'verification':'user_report_only','recorded_at':cases.now()}
    elif payload.action=='record_goal':d['goal']={'description':payload.note,'due_on':data['due_on'],'status':'planned','approval':'self_recorded_not_clinician_approved'}
    else:
     if not d.get('goal'):raise HTTPException(409,'no_goal_to_complete')
     d['goal']['status']='reported_completed';d['goal']['completion_note']=payload.note
    c.execute('INSERT INTO careloop_v2_details VALUES(?,?) ON CONFLICT(case_id) DO UPDATE SET payload=excluded.payload',(str(key),json.dumps(d)))
    at=cases.now();version=item['version']+1
    c.execute('UPDATE careloop_cases SET version=?,updated_at=? WHERE id=?',(version,at,str(key)))
    c.execute('INSERT INTO careloop_events VALUES(?,?,?,?,?,?,?,?,?,?)',(str(key),version,str(payload.operation_id),rd,payload.action,item['state'],payload.note,payload.reference,data['due_on'],at))
   else:
    cases.transition(c,item,data)
   item=cases.select_case(c,mode,pid,str(key));audit(c,item,payload.action);return show(c,item)
 @router.get('/cases/{key}/export')
 def export(key:UUID,mode:Mode,person:UUID):
  from fastapi.responses import JSONResponse
  with store.connect() as c:
   pid=owner(c,mode,person);item=cases.select_case(c,mode,pid,str(key))
   if item['state']=='withdrawn':raise HTTPException(403,'case_withdrawn')
   return JSONResponse({'format':'bainp-careloop-action-passport-v2','exported_at':cases.now(),'case':show(c,item)},headers={'Cache-Control':'no-store','Content-Disposition':'attachment; filename="careloop-summary.json"'})
 return router
