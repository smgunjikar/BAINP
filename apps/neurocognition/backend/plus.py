"""NeuroCognition participant screening, daily planning and camera research records.
All routes use existing account-scoped storage and authentication. No facial diagnosis.
"""
import json,hashlib,importlib.util,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta,date
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
_spec=importlib.util.spec_from_file_location('ncx_screening',Path(__file__).with_name('screening.py'))
scoring=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=scoring;_spec.loader.exec_module(scoring)
VERSION='ncx-connected-research-3.1.0'
def dump(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def now():return datetime.now(timezone.utc).isoformat()
SCHEMA='''
CREATE TABLE IF NOT EXISTS ncx3_permissions(participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(participant_id,mode));
CREATE TABLE IF NOT EXISTS ncx3_safety_events(participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,record_id TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(participant_id,mode,record_id));
CREATE TABLE IF NOT EXISTS ncx3_records(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL,request TEXT NOT NULL,payload TEXT NOT NULL,sha256 TEXT NOT NULL);
'''
OPTIONS=['Not at all','Several days','More than half the days','Nearly every day']
REGISTRY={
 'PHQ9':dict(title='Depression symptoms · PHQ-9',kind='embedded',domain='mental_health',count=9,maximum=3,timeframe='Over the last 2 weeks, how often have you been bothered by any of the following problems?',options=OPTIONS,items=['Little interest or pleasure in doing things','Feeling down, depressed, or hopeless','Trouble falling or staying asleep, or sleeping too much','Feeling tired or having little energy','Poor appetite or overeating','Feeling bad about yourself — or that you are a failure or have let yourself or your family down','Trouble concentrating on things, such as reading the newspaper or watching television','Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual','Thoughts that you would be better off dead or of hurting yourself in some way'],source='https://www.phqscreeners.com/',credit='Developed by Drs. Robert L. Spitzer, Janet B.W. Williams, Kurt Kroenke and colleagues, with an educational grant from Pfizer Inc. No permission is required to reproduce, translate, display or distribute.'),
 'GAD7':dict(title='Anxiety symptoms · GAD-7',kind='embedded',domain='mental_health',count=7,maximum=3,timeframe='Over the last 2 weeks, how often have you been bothered by the following problems?',options=OPTIONS,items=['Feeling nervous, anxious, or on edge','Not being able to stop or control worrying','Worrying too much about different things','Trouble relaxing','Being so restless that it is hard to sit still','Becoming easily annoyed or irritable','Feeling afraid, as if something awful might happen'],source='https://www.phqscreeners.com/',credit='Developed by Drs. Robert L. Spitzer, Janet B.W. Williams, Kurt Kroenke and colleagues, with an educational grant from Pfizer Inc.'),
 'ASRS6_2024':dict(title='Adult ADHD · official ASRS v1.1 6-question screener',kind='external_responses',domain='adhd',count=6,maximum=4,timeframe='Complete the official unchanged English instrument first; enter its six responses in their original order. This records external administration using the 2024 0–24 research scoring update.',options=['Never','Rarely','Sometimes','Often','Very often'],source='https://www.hcp.med.harvard.edu/ncs/asrs.php',credit='Kessler et al. (2005), Psychological Medicine 35(2), 245–256. Copyright © New York University and President and Fellows of Harvard College. All rights reserved. Original questionnaire and shading remain at the official source.'),
 'AUDIT':dict(title='Alcohol use · AUDIT',kind='external_responses',domain='substance_use',count=10,maximum=4,timeframe='Complete the official WHO AUDIT first. Enter the points assigned to each original response, in order. Items 9 and 10 allow only 0, 2 or 4. This is alcohol screening; it does not assess all drugs.',source='https://www.who.int/publications/i/item/WHO-MSD-MSB-01.6a',credit='World Health Organization, AUDIT: Guidelines for Use in Primary Care, second edition. Questionnaire wording is not reproduced here.'),
 'AQ10_EXTERNAL':dict(title='Autism · licensed AQ-10 result',kind='external_total',domain='autism',count=1,maximum=10,timeframe='Enter a result only from an independently completed, appropriately licensed adult AQ-10. No questionnaire or scoring key is distributed. The recorded total does not diagnose autism.',source='https://www.autismresearchcentre.com/tests/autism-spectrum-quotient-10-items-aq-10-adult/',credit='Allison, Auyeung & Baron-Cohen (2012). Commercial use requires the relevant licence. This is a user-reported external result, not a BAINP-administered screen.'),
 'RPQ_EXTERNAL':dict(title='Brain injury · externally administered RPQ',kind='external_responses',domain='brain_injury',count=16,maximum=4,timeframe='Complete the official Rivermead questionnaire first and enter all original ratings in order. Raw ratings are retained; no diagnostic cutoff is applied. This pathway is not for assessing a new acute injury.',source='https://www.sralab.org/rehabilitation-measures/rivermead-post-concussion-symptom-questionnaire',credit='King et al. (1995). External questionnaire administration. Raw sum 0–64 is descriptive, not a diagnosis.'),
 'FUNCTION5':dict(title='Everyday function · BAINP five-item follow-up',kind='embedded',domain='daily_function',count=5,maximum=3,timeframe='Compared with your usual routine, how much difficulty have you experienced recently? This original questionnaire is not a validated clinical scale.',options=['No reported difficulty','Some difficulty','Much difficulty','Unable without help'],items=['Keeping track of appointments','Remembering planned activities','Following familiar instructions','Managing familiar daily routines','Completing everyday responsibilities'],source=None,credit='BAINP original descriptive questionnaire; no validated cutoff or norms.'),
}
REGISTRY['TAPS1']=dict(title='Substance use · TAPS Part 1',kind='embedded',domain='substance_use',count=4,maximum=4,timeframe='In the PAST 12 MONTHS. Select the applicable original alcohol item below. This is Part 1 only; any reported use calls for appropriate Part 2 assessment and professional context.',options=['Never','Less Than Monthly','Monthly','Weekly','Daily or Almost Daily'],items=['In the PAST 12 MONTHS, how often have you used any tobacco product (for example, cigarettes, e-cigarettes, cigars, pipes, or smokeless tobacco)?','Select the applicable official alcohol item above.','In the PAST 12 MONTHS, how often have you used any drugs including marijuana, cocaine or crack, heroin, methamphetamine (crystal meth), hallucinogens, ecstasy/MDMA?','In the PAST 12 MONTHS, how often have you used any prescription medications just for the feeling, more than prescribed or that were not prescribed for you? Prescription medications that may be used this way include: Opiate pain relievers (for example, OxyContin, Vicodin, Percocet, Methadone); medications for anxiety or sleeping (for example, Xanax, Ativan, Klonopin); medications for ADHD (for example, Adderall or Ritalin).'],source='https://ctnlibrary.org/wp-content/uploads/2026/03/TAPS-Tool-Parts-I-and-II-V2.pdf',credit='NIDA Clinical Trials Network TAPS Tool Part 1, Web Version 2.0; 4.00; 09-19-17. McNeely et al. (2016). Public-domain instrument. Part 2 assessment is not included in this release.')
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',strict=True)
class Permission(Strict):
 expected_revision:int=Field(ge=0)
 screening:bool=False
 daily:bool=False
 camera:bool=False
 cross_engine:bool=False
class Record(Strict):
 id:UUID=Field(strict=False)
 consent_revision:int=Field(ge=1)
class Screen(Record):
 instrument:Literal['PHQ9','GAD7','ASRS6_2024','AUDIT','AQ10_EXTERNAL','RPQ_EXTERNAL','FUNCTION5','TAPS1']
 answers:list[int]=Field(min_length=1,max_length=16)
 alcohol_item:Literal['male_original','female_original']|None=None
 language:Literal['en']='en'
 english_understood:Literal[True]
 external_completed:bool=False
 external_reference:str=Field(default='',max_length=200)
 usage_rights_confirmed:bool=False
 difficulty:Literal['not_difficult','somewhat','very','extremely','not_applicable']
class Daily(Record):
 fatigue:int=Field(ge=0,le=10)
 sleep_hours:float=Field(ge=0,le=24,allow_inf_nan=False)
 pain:int=Field(ge=0,le=10)
 functional_change:bool
 acute_warning:bool
 prefer:Literal['quick','core','extended']='quick'
class Sample(Strict):
 at_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)
 faces:int=Field(ge=0,le=2)
 blink_left:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
 blink_right:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
 jaw_open:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
 center_x:float|None=Field(default=None,ge=-2,le=3,allow_inf_nan=False)
 center_y:float|None=Field(default=None,ge=-2,le=3,allow_inf_nan=False)
 face_width:float|None=Field(default=None,ge=0,le=4,allow_inf_nan=False)
 eye_open_ratio:float|None=Field(default=None,ge=0,le=2,allow_inf_nan=False)
class Camera(Record):
 session_id:UUID|None=Field(default=None,strict=False)
 attempt_id:UUID|None=Field(default=None,strict=False)
 model:Literal['mediapipe-face-landmarker-float16-v1']
 samples:list[Sample]=Field(min_length=1,max_length=7201)
 client_duration_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)

def make_router(store,authenticated,analytics,checkin,gate):
 r=APIRouter(prefix='/hub',dependencies=[Depends(authenticated)])
 def person(c,pid,mode):
  row=c.execute('SELECT * FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone()
  if not row:raise HTTPException(404,'participant_not_found')
  return row
 def auth(c,pid,mode,scope=None,revision=None):
  p=person(c,pid,mode);row=c.execute('SELECT * FROM ncx3_permissions WHERE participant_id=? AND mode=?',(str(pid),mode)).fetchone()
  value=dict(revision=row['revision'],**json.loads(row['payload'])) if row else dict(revision=0,screening=False,daily=False,camera=False,cross_engine=False)
  if scope and not value[scope]:raise HTTPException(403,scope+'_permission_required')
  if revision is not None and value['revision']!=revision:raise HTTPException(409,'permission_changed_refresh')
  return p,value
 def values(c,pid,mode,kind,all_records=False):
  out=[]
  for row in c.execute('SELECT * FROM ncx3_records WHERE participant_id=? AND mode=? AND kind=? ORDER BY created_at DESC,id DESC'+('' if all_records else ' LIMIT 100'),(str(pid),mode,kind)):
   try:
    payload=json.loads(row['payload']);ok=hashlib.sha256(dump(payload).encode()).hexdigest()==row['sha256']
   except (ValueError,TypeError):ok=False
   if not ok:raise HTTPException(409,'record_integrity_failed')
   out.append(dict(id=row['id'],created_at=row['created_at'],**payload))
  return out
 def save(c,pid,mode,kind,b,result):
  request=dump(b.model_dump(mode='json'));old=c.execute('SELECT * FROM ncx3_records WHERE id=?',(str(b.id),)).fetchone()
  if old:
   if (old['participant_id'],old['mode'],old['kind'],old['request'])!=(str(pid),mode,kind,request):raise HTTPException(409,'record_id_conflict')
   value=json.loads(old['payload'])
   if hashlib.sha256(dump(value).encode()).hexdigest()!=old['sha256']:raise HTTPException(409,'record_integrity_failed')
   return dict(id=old['id'],created_at=old['created_at'],**value)
  value=dict(data=b.model_dump(mode='json'),result=result,version=VERSION);at=now();raw=dump(value)
  c.execute('INSERT INTO ncx3_records VALUES(?,?,?,?,?,?,?,?)',(str(b.id),str(pid),mode,kind,at,request,raw,hashlib.sha256(raw.encode()).hexdigest()))
  return dict(id=str(b.id),created_at=at,**value)
 @r.get('/{pid}/permissions')
 def permissions(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:return auth(c,pid,mode)[1]
 @r.put('/{pid}/permissions')
 def set_permissions(pid:UUID,mode:Literal['active','demo'],b:Permission):
  with store.connect(True) as c:
   _,old=auth(c,pid,mode)
   if old['revision']!=b.expected_revision:raise HTTPException(409,'permission_changed_refresh')
   value=b.model_dump(exclude={'expected_revision'});revision=old['revision']+1
   c.execute('INSERT OR REPLACE INTO ncx3_permissions VALUES(?,?,?,?)',(str(pid),mode,revision,dump(value)))
   return dict(revision=revision,**value)
 @r.get('/{pid}/registry')
 def registry(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:person(c,pid,mode)
  return dict(instruments=REGISTRY,version=VERSION,adult_only=True)
 @r.post('/{pid}/screenings')
 def screen(pid:UUID,mode:Literal['active','demo'],b:Screen):
  with store.connect(True) as c:
   p,_=auth(c,pid,mode,'screening',b.consent_revision);profile=json.loads(p['profile']);age=profile.get('age')
   if type(age) is not int or age<18:raise HTTPException(422,'adult_profile_required')
   spec=REGISTRY[b.instrument]
   if spec['kind'].startswith('external') and (not b.external_completed or not b.external_reference.strip() or not b.usage_rights_confirmed):raise HTTPException(422,'official_external_administration_and_rights_confirmation_required')
   if len(b.answers)!=spec['count'] or any(type(x) is not int or x<0 or x>spec['maximum'] for x in b.answers):raise HTTPException(422,'complete_valid_responses_required')
   if b.instrument in scoring.REGISTRY:result=scoring.score(b.instrument,b.answers,age)
   elif b.instrument=='TAPS1':
    if b.alcohol_item is None:raise HTTPException(422,'original_alcohol_item_branch_required')
    categories=[name for name,x in zip(['tobacco','alcohol','illicit_substances','prescription_misuse'],b.answers) if x>0]
    result=dict(total=len(categories),reported_use_categories=categories,band='part2_assessment_indicated' if categories else 'no_use_reported_in_part1',clinical_diagnosis=False,interpretation='Number of categories with reported use, not a substance-use severity score. TAPS Part 2 and appropriate clinical follow-up are required for risk assessment.')
   elif b.instrument=='AUDIT':
    if any(x not in (0,2,4) for x in b.answers[8:]):raise HTTPException(422,'audit_items_9_10_require_0_2_4')
    result=dict(total=sum(b.answers),band='external_score_requires_professional_context',clinical_diagnosis=False)
   elif b.instrument=='AQ10_EXTERNAL':result=dict(total=b.answers[0],classification='USER_REPORTED_EXTERNAL_TOTAL',clinical_diagnosis=False,interpretation='Original licensed instrument and clinical context required; no BAINP autism diagnosis.')
   elif b.instrument=='RPQ_EXTERNAL':result=dict(raw_sum=sum(b.answers),classification='ORIGINAL_RAW_RATINGS_NOT_MODIFIED_RPQ3_RPQ13',clinical_diagnosis=False,interpretation='No injury diagnosis or recovery conclusion from this sum.')
   else:result=dict(total=sum(b.answers),clinical_diagnosis=False,interpretation='Original descriptive function ratings; no validated cutoff.')
   result.update(instrument=b.instrument,language='en',scoring_version='nc-screening-3.1',difficulty=b.difficulty)
   if result.get('immediate_human_safety_review'):
    c.execute('INSERT OR IGNORE INTO ncx3_safety_events VALUES(?,?,?,?)',(str(pid),mode,str(b.id),now()))
    result['guidance']='Your response needs prompt human support and assessment. If you may act on these thoughts or cannot stay safe, contact local emergency services or go to the nearest emergency department. BAINP has not contacted anyone. Do not wait for a routine test.'
   return save(c,pid,mode,'screening',b,result)
 @r.get('/{pid}/screenings')
 def screenings(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:
   auth(c,pid,mode,'screening');return dict(items=values(c,pid,mode,'screening'))
 @r.post('/{pid}/daily')
 def daily(pid:UUID,mode:Literal['active','demo'],b:Daily):
  with store.connect(True) as c:
   auth(c,pid,mode,'daily',b.consent_revision)
   result=dict(classification='SELF_REPORTED',acute_warning=b.acute_warning,review_suggested=b.functional_change,clinical_diagnosis=False)
   if b.acute_warning:result['guidance']='Stop routine testing and obtain urgent medical help for a possible acute emergency. BAINP has not contacted a service.'
   return save(c,pid,mode,'daily',b,result)
 @r.get('/{pid}/daily')
 def daily_history(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:
   auth(c,pid,mode,'daily');return dict(items=values(c,pid,mode,'daily'))
 def plan_value(c,pid,mode):
  _,permission=auth(c,pid,mode,'daily')
  records=values(c,pid,mode,'daily');screenings=values(c,pid,mode,'screening') if permission['screening'] else []
  holds=automatic_holds(c,pid,mode)
  result=dict(version=VERSION,as_of=now(),battery=None,tasks=[],executable=False,clinical_validation=False,reason='',next_eligible_at=None)
  if holds:return result|dict(reason='Current automatic-plan hold: '+', '.join(holds))
  if not records: return result|dict(reason='Complete a daily context report first.')
  latest=records[0];data=latest['data']
  if datetime.now(timezone.utc)-datetime.fromisoformat(latest['created_at'])>timedelta(hours=24):return result|dict(reason='Daily context is older than 24 hours; refresh it.')
  if data['acute_warning']:return result|dict(reason='Urgent medical guidance takes priority over routine testing.')
  if data['functional_change']:return result|dict(reason='New everyday-function concerns need professional review. Open CareLoop; a local record is not a delivered referral.')
  if screenings and any(x['result'].get('immediate_human_safety_review') and datetime.now(timezone.utc)-datetime.fromisoformat(x['created_at'])<timedelta(days=14) for x in screenings):return result|dict(reason='A recent safety-relevant questionnaire response needs human review before automated routine planning.')
  if data['fatigue']>=7 or data['pain']>=7:return result|dict(reason='High reported fatigue or pain: rest or seek appropriate advice before another routine assessment.')
  row=c.execute('SELECT * FROM checkins WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1',(str(pid),mode)).fetchone()
  if not row:return result|dict(reason='Complete NeuroAccess preparation first.')
  reasons=gate(checkin(c,row['id'],mode))
  if reasons:return result|dict(reason='Current preparation requires review: '+', '.join(reasons))
  last=c.execute('SELECT * FROM nc_sessions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1',(str(pid),mode)).fetchone()
  last_activity=c.execute('SELECT MAX(COALESCE(a.finished_at,a.started_at)) FROM nc_attempts a JOIN nc_sessions n ON n.id=a.session_id WHERE n.participant_id=? AND n.mode=?',(str(pid),mode)).fetchone()[0]
  if last_activity:
   next_time=datetime.fromisoformat(last_activity)+timedelta(hours=24)
   if datetime.now(timezone.utc)<next_time:return result|dict(reason='The 24-hour engineering burden interval has not elapsed.',next_eligible_at=next_time.isoformat())
  if c.execute('SELECT 1 FROM nc_sessions WHERE checkin_id=?',(row['id'],)).fetchone():return result|dict(reason='This preparation already belongs to a session. Resume it or create a fresh check-in.')
  guard=sys.modules.get('bainp_guard')
  if not guard or not callable(getattr(guard,'urgent',None)):return result|dict(reason='NeuroGuard is unavailable; no automatic launch.')
  safety=guard.urgent([])
  if safety.get('state')=='escalate':return result|dict(reason='NeuroGuard requires urgent guidance.')
  baseline_complete=False
  for prior in c.execute('SELECT id,manifest FROM nc_sessions WHERE participant_id=? AND mode=?',(str(pid),mode)):
   required=json.loads(prior['manifest']).get('_meta',{}).get('order',[])
   finished={a['task'] for a in c.execute("SELECT task FROM nc_attempts WHERE session_id=? AND status='completed'",(prior['id'],))}
   if {'C01','C02','C03','C04','C05','C06'}.issubset(set(required)&finished):baseline_complete=True
  battery=data['prefer'] if baseline_complete else 'core' 
  tasks=['C03','C05','C06'] if battery=='quick' else ['C01','C03','C04','C05','C02','C06']+(['C07','C08','C09','C10'] if battery=='extended' else [])
  return result|dict(reason='First visit uses core; follow-up uses your selected burden preference after current preparation checks.',battery=battery,tasks=tasks,checkin_id=row['id'],executable=True,authority='NeuroCognition research follow-up proposal; native task execution rechecks preparation. NeuroQuest/Continuum remains the existing guided clinical workflow.',duration='Not calibrated; actual duration includes practice and memory delay.')
 @r.get('/{pid}/plan')
 def plan(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:return plan_value(c,pid,mode)
 @r.post('/{pid}/camera')
 def camera(pid:UUID,mode:Literal['active','demo'],b:Camera):
  with store.connect(True) as c:
   auth(c,pid,mode,'camera',b.consent_revision)
   if b.attempt_id and not b.session_id:raise HTTPException(422,'session_required_for_attempt')
   if b.session_id:
    session=c.execute('SELECT * FROM nc_sessions WHERE id=? AND participant_id=? AND mode=?',(str(b.session_id),str(pid),mode)).fetchone()
    if not session:raise HTTPException(404,'session_not_found')
   if b.attempt_id and not c.execute('SELECT 1 FROM nc_attempts WHERE id=? AND session_id=?',(str(b.attempt_id),str(b.session_id))).fetchone():raise HTTPException(404,'attempt_not_found')
   times=[x.at_ms for x in b.samples]
   if any(y<=x for x,y in zip(times,times[1:])) or times[-1]>b.client_duration_ms:raise HTTPException(422,'invalid_camera_sample_times')
   valid=[x for x in b.samples if x.faces==1];result=dict(samples=len(b.samples),single_face_samples=len(valid),single_face_fraction=len(valid)/len(b.samples),timing='CLIENT_REPORTED_APPROXIMATE',clinical_diagnosis=False,interpretation='Descriptive landmarks and movement only. Not attention, emotion, effort, disease or structural brain measurement.',model=b.model,raw_video_stored=False)
   import statistics
   for metric in ('blink_left','blink_right','jaw_open','center_x','center_y','face_width','eye_open_ratio'):
    vals=[getattr(x,metric) for x in valid if getattr(x,metric) is not None]
    result[metric]=dict(mean=statistics.mean(vals),minimum=min(vals),maximum=max(vals),n=len(vals)) if vals else None
   return save(c,pid,mode,'camera',b,result)
 @r.get('/{pid}/camera')
 def camera_history(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:
   auth(c,pid,mode,'camera');return dict(items=values(c,pid,mode,'camera'))
 @r.get('/{pid}/overview')
 def overview(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:
   _,permission=auth(c,pid,mode);sources={}
   if permission['cross_engine']:
    tables={x['name'] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name,table in [('NeuroSense','sense_observations'),('NeuroTwin','nt_source_records'),('NeuroImaging_links','nt_imaging_links'),('NeuroTwin_EEG','nt_neural_records'),('NeuroContinuum','ncw_sessions')]:
     if table not in tables:sources[name]=dict(state='UNAVAILABLE',count=None);continue
     count=c.execute('SELECT count(*) FROM '+table+' WHERE participant_id=? AND mode=?',(str(pid),mode)).fetchone()[0]
     sources[name]=dict(state='LINKED_RECORDS_PRESENT' if count else 'NO_LINKED_RECORDS',count=count,interpretation='Record availability only; no diagnostic fusion or normal finding implied.')
   wearable={}
   if permission['cross_engine'] and 'sense_observations' in tables:
    import statistics
    grouped={}
    for row in c.execute('SELECT payload FROM sense_observations WHERE participant_id=? AND mode=?',(str(pid),mode)):
     try:v=json.loads(row['payload'])
     except (ValueError,TypeError):continue
     # Keep units and acquisition method separate; never pool incompatible devices/methods.
     key=(v.get('metric'),v.get('unit'),v.get('device'),v.get('method'),v.get('protocol'))
     grouped.setdefault(key,[]).append(v)
    for i,(key,items) in enumerate(grouped.items()):
     valid=[x for x in items if x.get('quality')=='usable' and type(x.get('value')) in (int,float)]
     wearable[str(i)]=dict(metric=key[0],unit=key[1],device=key[2],method=key[3],protocol=key[4],records=len(items),usable=len(valid),excluded=len(items)-len(valid),mean=statistics.mean(x['value'] for x in valid) if valid else None,latest=max((x.get('timestamp','') for x in valid),default=None),interpretation='Descriptive within-source summary; no disease inference or causal relationship with cognition established.')
   return dict(cognition=analytics(pid,mode),sources=sources,wearable=wearable,cross_engine_permission=permission['cross_engine'],interpretation='Quality-aware source overview; clinical multimodal fusion is not validated.')
 @r.get('/{pid}/export')
 def export(pid:UUID,mode:Literal['active','demo']):
  with store.connect() as c:
   _,permission=auth(c,pid,mode);out={}
   for scope,kind in [('screening','screening'),('daily','daily'),('camera','camera')]:
    if permission[scope]:out[kind]=values(c,pid,mode,kind,all_records=True)
   if not out:raise HTTPException(403,'no_export_scope_enabled')
   if permission['daily']:out['safety_review_events']=[dict(x) for x in c.execute('SELECT record_id,created_at FROM ncx3_safety_events WHERE participant_id=? AND mode=?',(str(pid),mode))]
   return JSONResponse(dict(schema=VERSION,participant_id=str(pid),mode=mode,exported_at=now(),records=out),headers={'Cache-Control':'no-store','Content-Disposition':'attachment; filename="neurocognition-records.json"'})
 @r.delete('/{pid}/records/{rid}')
 def delete(pid:UUID,rid:UUID,mode:Literal['active','demo']):
  with store.connect(True) as c:
   person(c,pid,mode);row=c.execute('SELECT * FROM ncx3_records WHERE id=? AND participant_id=? AND mode=?',(str(rid),str(pid),mode)).fetchone()
   if not row:raise HTTPException(404,'record_not_found')
   c.execute('DELETE FROM ncx3_records WHERE id=?',(str(rid),));return dict(deleted=True)
 return r,plan_value

def automatic_holds(c,pid,mode):
 tables={v['name'] for v in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 guard=sys.modules.get('bainp_guard')
 if not guard or not callable(getattr(guard,'urgent',None)):return ['neuroguard_unavailable']
 if 'nq_decisions' in tables:
  decision=c.execute('SELECT payload,sha256 FROM nq_decisions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1',(str(pid),mode)).fetchone()
  if decision:
   try:
    value=json.loads(decision['payload'])
    # Original source digest uses canonical JSON; malformed or modified decisions fail closed.
    if hashlib.sha256(dump(value).encode()).hexdigest()!=decision['sha256']:return ['neuroquest_decision_integrity_failed']
    if value.get('action') in ('urgent_guidance','professional_review'):return ['neuroquest_'+value['action']+'_takes_precedence']
    if value.get('action') in ('repeat','targeted','abstain') and not value.get('executable'):return ['neuroquest_current_action_requires_resolution']
    safety=value.get('context',{}).get('guard',{})
    if safety.get('state') not in (None,'workflow_permitted'):return ['neuroguard_current_restriction']
   except (ValueError,TypeError,KeyError):return ['neuroquest_decision_invalid']
 if 'ncw_sessions' in tables:
  for session in c.execute("SELECT payload FROM ncw_sessions WHERE participant_id=? AND mode=? AND state NOT IN ('COMPLETED','CANCELLED')",(str(pid),mode)):
   try:
    if json.loads(session['payload']).get('safety',{}).get('state')=='escalate':return ['neurocontinuum_urgent_safety_state']
   except (ValueError,TypeError):return ['neurocontinuum_state_invalid']
 row=c.execute('SELECT * FROM ncx3_permissions WHERE participant_id=? AND mode=?',(str(pid),mode)).fetchone()
 if not row or not json.loads(row['payload']).get('daily'):return ['daily_permission_required']
 if c.execute('SELECT 1 FROM ncx3_safety_events WHERE participant_id=? AND mode=?',(str(pid),mode)).fetchone():return ['questionnaire_safety_response_requires_human_review']
 latest=c.execute("SELECT * FROM ncx3_records WHERE participant_id=? AND mode=? AND kind='daily' ORDER BY created_at DESC,id DESC LIMIT 1",(str(pid),mode)).fetchone()
 if not latest:return ['daily_context_required']
 try:
  v=json.loads(latest['payload'])
  if hashlib.sha256(dump(v).encode()).hexdigest()!=latest['sha256']:return ['daily_record_integrity_failed']
  if datetime.now(timezone.utc)-datetime.fromisoformat(latest['created_at'])>timedelta(hours=24):return ['daily_context_stale']
  d=v['data']
  if d['acute_warning']:return ['acute_warning_requires_urgent_guidance']
  if d['functional_change']:return ['functional_change_requires_review']
  if d['fatigue']>=7 or d['pain']>=7:return ['high_reported_burden']
  # Retained safety events remain holds even if questionnaire display permission changes.
  for s in c.execute("SELECT payload,created_at FROM ncx3_records WHERE participant_id=? AND mode=? AND kind='screening' ORDER BY created_at DESC LIMIT 100",(str(pid),mode)):
   if datetime.now(timezone.utc)-datetime.fromisoformat(s['created_at'])<timedelta(days=14) and json.loads(s['payload'])['result'].get('immediate_human_safety_review'):return ['recent_questionnaire_safety_response_requires_human_review']
 except (ValueError,KeyError,TypeError):return ['daily_record_invalid']
 return []
