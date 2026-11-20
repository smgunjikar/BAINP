"""NeuroAccess v1: local authenticated participant records and accessibility check-ins.

Stores active and fictional demo records separately in persistent SQLite. Check-in
snapshots are immutable; profile edits affect future check-ins only. This module
implements usability preparation, not a validated cognitive assessment or diagnosis.
"""
from __future__ import annotations
import argparse, hashlib, hmac, json, os, secrets, sqlite3, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

VERSION='neuroaccess-v1'
ORIGINS={'http://127.0.0.1:3000','http://localhost:3000'}
Mode=Literal['active','demo']

def now(): return datetime.now(timezone.utc).isoformat()
def dump(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def root_path():
    home=Path(os.environ.get('USERPROFILE',str(Path.home())))
    return Path(os.environ.get('NEUROACCESS_DATA_DIR',str(home/'BAINP_DATA'/'local'/'neuroaccess_v1')))

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class Profile(Strict):
    display_name:str=Field(min_length=1,max_length=80)
    age:int=Field(ge=18,le=110)
    education_years:int=Field(ge=0,le=40)
    digital_familiarity:Literal['low','medium','high']
    language:Literal['en','ar']
    vision_limitation:bool
    vision_aid:Literal['none','glasses','magnifier','other']
    hearing_limitation:bool
    hearing_aid:bool
    motor_limitation:bool
    input_method:Literal['keyboard','mouse','touch','assistive']
    device_type:Literal['desktop','laptop','tablet','phone']
    text_size:Literal['standard','large','extra_large']
    high_contrast:bool
    reduced_motion:bool
    assistance:Literal['none','navigation','responses']
    assistance_authorized:bool
    can_see_and_respond:Literal['yes','no','unsure']
    @field_validator('display_name')
    @classmethod
    def name(cls,v):
        v=' '.join(v.split())
        if not v:raise ValueError('Display name cannot be blank')
        return v
class CreatePerson(Strict):
    id:UUID=Field(strict=False)
    mode:Mode
    profile:Profile
    consent_to_store:bool
    @field_validator('consent_to_store')
    @classmethod
    def consent(cls,v):
        if v is not True:raise ValueError('Consent to store is required')
        return v
class UpdatePerson(Strict):
    revision:int=Field(ge=1)
    profile:Profile
class NewCheckin(Strict):
    id:UUID=Field(strict=False)
    participant_revision:int=Field(ge=1)
    instructions_understood:bool
    acute_warning:Literal['no','yes','unsure']
class PracticeEvent(Strict):
    kind:Literal['activate','match']
    response:Literal['button','triangle','circle']
    elapsed_ms:float=Field(ge=0,le=3600000,allow_inf_nan=False)
    input:Literal['keyboard','mouse','touch','pen','assistive','unknown']
class Practice(Strict):
    protocol:Literal['access-practice-v1']
    interface_language:Literal['en','ar']
    events:list[PracticeEvent]=Field(min_length=2,max_length=50)
    focus_changes:int=Field(ge=0,le=10000)
class DeletePerson(Strict):
    confirm_id:UUID=Field(strict=False)
    revision:int=Field(ge=1)
class Login(Strict):
    password:str=Field(min_length=1,max_length=256)

COMPARISON_FIELDS=['language','input_method','device_type','vision_limitation','vision_aid',
 'hearing_limitation','hearing_aid','motor_limitation','assistance','text_size','high_contrast','reduced_motion']

def gate(profile,conditions):
    """No blanket hold for disability, Arabic or authorized assistance.

    This preparation is visual/text-based with no audio requirements. Actual task
    suitability is evaluated separately when future cognitive tasks are implemented.
    Acute answers are an unvalidated conservative prototype hold, not medical triage.
    """
    blocks=[];notes=[]
    if conditions['acute_warning']!='no':blocks.append('ACUTE_WARNING_REVIEW')
    if not conditions['instructions_understood']:blocks.append('INSTRUCTIONS_NOT_CONFIRMED')
    if profile['can_see_and_respond']!='yes':blocks.append('ACCESS_SUPPORT_NEEDED')
    if profile['assistance']!='none' and not profile['assistance_authorized']:blocks.append('ASSISTANCE_AUTHORIZATION_NEEDED')
    if profile['assistance']=='responses':notes.append('RESPONSES_ASSISTED')
    if profile['assistance']=='navigation':notes.append('NAVIGATION_HELP_RECORDED')
    if profile['language']=='ar':notes.append('ARABIC_UI_NOT_CLINICALLY_VALIDATED')
    if profile['digital_familiarity']=='low':notes.append('DIGITAL_FAMILIARITY_SUPPORT')
    if profile['vision_limitation'] or profile['hearing_limitation'] or profile['motor_limitation']:notes.append('ACCOMMODATIONS_RECORDED')
    return dict(state='needs_review_or_support' if blocks else 'ready_for_usability_practice',
                practice_allowed=not blocks,reason_codes=blocks,notes=notes)

def comparison(previous,current):
    if previous is None:return dict(state='baseline',changes=[],clinical_comparability_established=False)
    changes=[dict(field=f,before=previous[f],after=current[f]) for f in COMPARISON_FIELDS if previous[f]!=current[f]]
    return dict(state='conditions_changed' if changes else 'no_recorded_condition_changes',changes=changes,
                clinical_comparability_established=False)

SCHEMA='''
CREATE TABLE IF NOT EXISTS participants (
 id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('active','demo')),
 profile TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 creation_payload TEXT NOT NULL, consent_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkins (
 id TEXT PRIMARY KEY, participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL, profile TEXT NOT NULL, participant_revision INTEGER NOT NULL,
 conditions TEXT NOT NULL, gate TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, completed_at TEXT, practice TEXT, comparison TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_checkins_person ON checkins(participant_id,created_at);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity_id TEXT NOT NULL,
 mode TEXT NOT NULL, recorded_at TEXT NOT NULL);
'''

class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            version=c.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1,2,3,4,5):raise RuntimeError('Unsupported database version; migration required')
            if version==0 and c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone():
                raise RuntimeError('Refusing to initialize an unrelated database')
            c.executescript(SCHEMA)
            # Additive v1 -> v2 migration: preserve every existing profile/check-in.
            c.execute("""CREATE TABLE IF NOT EXISTS cognitive_encoding (
             id TEXT PRIMARY KEY, checkin_id TEXT NOT NULL UNIQUE REFERENCES checkins(id) ON DELETE CASCADE,
             protocol TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('running','completed','interrupted')),
             condition_snapshot TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, result TEXT)""")
            from battery import initialize
            initialize(c)
            c.execute('PRAGMA user_version=5')
    @contextmanager
    def connect(self,write=False):
        c=sqlite3.connect(self.path,timeout=10)
        c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA journal_mode=WAL')
        try:
            if write:c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except Exception:c.rollback();raise
        finally:c.close()

def audit(c,action,entity,mode):
    c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',(action,entity,mode,now()))
def person(c,identifier,mode):
    row=c.execute('SELECT * FROM participants WHERE id=? AND mode=?',(identifier,mode)).fetchone()
    if row is None:raise HTTPException(404,'participant_not_found')
    return row
def view_person(row):
    return dict(id=row['id'],mode=row['mode'],profile=json.loads(row['profile']),revision=row['revision'],
                created_at=row['created_at'],updated_at=row['updated_at'],consent_at=row['consent_at'])
def checkin(c,identifier,mode):
    row=c.execute('SELECT * FROM checkins WHERE id=? AND mode=?',(identifier,mode)).fetchone()
    if row is None:raise HTTPException(404,'checkin_not_found')
    return row
def view_checkin(c,row):
    profile=json.loads(row['profile'])
    return dict(id=row['id'],participant_id=row['participant_id'],mode=row['mode'],profile=profile,
      participant_revision=row['participant_revision'],conditions=json.loads(row['conditions']),gate=json.loads(row['gate']),
      status=row['status'],created_at=row['created_at'],completed_at=row['completed_at'],
      practice=json.loads(row['practice']) if row['practice'] else None,
      comparison=json.loads(row['comparison']),
      clinical_validation='not_established')

def create_app(data_dir=None,password=None):
    """App factory accepts an isolated directory/password for tests; no auth bypass."""
    folder=Path(data_dir) if data_dir else root_path();folder.mkdir(parents=True,exist_ok=True)
    secret_path=folder/'local_operator_secret.txt'
    if password is None:
        if not secret_path.exists():
            secret_path.write_text(secrets.token_urlsafe(24),encoding='utf-8')
            try:secret_path.chmod(0o600)
            except OSError:pass
        password=secret_path.read_text(encoding='utf-8').strip()
    signing_key=hashlib.sha256(('neuroaccess-cookie:'+password).encode()).digest()
    expected_password=hashlib.sha256(password.encode()).digest()
    store=Store(folder/'neuroaccess.sqlite3');app=FastAPI(title='NeuroAccess local prototype',version='1.0.0',docs_url=None,redoc_url=None)
    app.state.store=store
    failures={}
    # Owner-only local sessions. Restart invalidates sessions; logout revokes them.
    sessions={}
    from threading import RLock
    session_lock=RLock()
    with store.connect(True) as c:
        c.execute("CREATE TABLE IF NOT EXISTS owner_preferences (key TEXT PRIMARY KEY,value TEXT NOT NULL)")

    @app.middleware('http')
    async def boundary(request,call_next):
        origin=request.headers.get('origin')
        if origin and origin not in ORIGINS:return JSONResponse({'detail':'origin_not_allowed'},403)
        if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('x-neuroaccess-request')!='1':
            return JSONResponse({'detail':'request_header_required'},403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
        return response
    from fastapi.exceptions import RequestValidationError
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):
        # Do not echo names, raw trial arrays, NaN or exception objects.
        return JSONResponse({'detail':[{'loc':e['loc'],'msg':e['msg'],'type':e['type']} for e in exc.errors()]},422)
    @app.exception_handler(sqlite3.Error)
    async def storage_error(request,exc):return JSONResponse({'detail':'storage_unavailable'},503)
    def authenticated(request:Request):
        token=request.cookies.get('na_session','')
        with session_lock:
            expires=sessions.get(token,0)
            if expires <= time.time():
                sessions.pop(token,None)
                raise HTTPException(401,'login_required')
    @app.get('/api/health')
    def health():return {'service':VERSION,'status':'ok'}
    @app.post('/api/login')
    def login(payload:Login,request:Request,response:Response):
        host=request.client.host if request.client else 'local';stamp=time.monotonic()
        attempts=[t for t in failures.get(host,[]) if stamp-t<60]
        if len(attempts)>=10:raise HTTPException(429,'too_many_login_attempts')
        if not hmac.compare_digest(hashlib.sha256(payload.password.encode()).digest(),expected_password):
            failures[host]=attempts+[stamp];raise HTTPException(401,'invalid_password')
        failures.pop(host,None)
        token=secrets.token_urlsafe(32)
        with session_lock:
            sessions.clear()  # One active owner session for private testing.
            sessions[token]=time.time()+8*3600
        response.set_cookie('na_session',token,max_age=8*3600,httponly=True,samesite='strict',secure=False,path='/api')
        return {'authenticated':True,'local_only':True,'role':'owner'}
    @app.get('/api/session',dependencies=[Depends(authenticated)])
    def session():return {'authenticated':True,'version':VERSION,'role':'owner','registration_enabled':False,'storage':'persistent_local_sqlite'}
    @app.post('/api/logout')
    def logout(request:Request,response:Response):
        with session_lock:sessions.pop(request.cookies.get('na_session',''),None)
        response.delete_cookie('na_session',path='/api')
        return {'logged_out':True}
    @app.get('/api/owner-profile',dependencies=[Depends(authenticated)])
    def owner_profile(mode:Mode):
        with store.connect() as c:
            row=c.execute('SELECT value FROM owner_preferences WHERE key=?',('profile:'+mode,)).fetchone()
            found=c.execute('SELECT id FROM participants WHERE id=? AND mode=?',(row['value'],mode)).fetchone() if row else None
            return {'participant_id':found['id'] if found else None}
    @app.put('/api/owner-profile/{participant_id}',dependencies=[Depends(authenticated)])
    def choose_owner_profile(participant_id:UUID,mode:Mode):
        with store.connect(True) as c:
            person(c,str(participant_id),mode)
            c.execute('INSERT OR REPLACE INTO owner_preferences(key,value) VALUES(?,?)',('profile:'+mode,str(participant_id)))
            audit(c,'owner_profile_selected',str(participant_id),mode)
        return {'participant_id':str(participant_id)}
    @app.get('/api/participants',dependencies=[Depends(authenticated)])
    def list_people(mode:Mode,q:str='',offset:int=0):
        if len(q)>80 or offset<0 or offset>100000:raise HTTPException(422,'invalid_search')
        with store.connect() as c:
            rows=c.execute('SELECT * FROM participants WHERE mode=? AND (instr(lower(json_extract(profile,\'$.display_name\')),lower(?))>0 OR instr(id,?)>0) ORDER BY updated_at DESC,id DESC LIMIT 51 OFFSET ?',
                           (mode,q.strip(),q.strip(),offset)).fetchall()
            return dict(items=[view_person(r) for r in rows[:50]],has_more=len(rows)>50,offset=offset)
    @app.post('/api/participants',dependencies=[Depends(authenticated)],status_code=201)
    def create_person(payload:CreatePerson):
        identity=str(payload.id);normalized=payload.model_dump(mode='json')
        with store.connect(True) as c:
            existing=c.execute('SELECT * FROM participants WHERE id=?',(identity,)).fetchone()
            if existing:
                if json.loads(existing['creation_payload'])!=normalized:raise HTTPException(409,'idempotency_conflict')
                return view_person(existing)
            stamp=now();c.execute('INSERT INTO participants VALUES(?,?,?,?,?,?,?,?)',
              (identity,payload.mode,dump(normalized['profile']),1,stamp,stamp,dump(normalized),stamp))
            audit(c,'participant_created',identity,payload.mode)
            return view_person(person(c,identity,payload.mode))
    @app.get('/api/participants/{participant_id}',dependencies=[Depends(authenticated)])
    def get_person(participant_id:UUID,mode:Mode):
        with store.connect() as c:return view_person(person(c,str(participant_id),mode))
    @app.patch('/api/participants/{participant_id}',dependencies=[Depends(authenticated)])
    def update_person(participant_id:UUID,mode:Mode,payload:UpdatePerson):
        identity=str(participant_id);profile=payload.profile.model_dump(mode='json')
        with store.connect(True) as c:
            row=person(c,identity,mode)
            if row['revision']!=payload.revision:
                if row['revision']==payload.revision+1 and json.loads(row['profile'])==profile:return view_person(row)
                raise HTTPException(409,'profile_changed_reload')
            # bainp_no_change_profile_v1: an unchanged save is not a profile revision.
            if json.loads(row['profile']) == profile:
                return view_person(row)
            c.execute('UPDATE participants SET profile=?,revision=revision+1,updated_at=? WHERE id=?',(dump(profile),now(),identity))
            audit(c,'profile_updated',identity,mode);return view_person(person(c,identity,mode))
    @app.delete('/api/participants/{participant_id}',dependencies=[Depends(authenticated)])
    def delete_person(participant_id:UUID,mode:Mode,payload:DeletePerson):
        identity=str(participant_id)
        if str(payload.confirm_id)!=identity:raise HTTPException(422,'delete_confirmation_mismatch')
        with store.connect(True) as c:
            row=person(c,identity,mode)
            if row['revision']!=payload.revision:raise HTTPException(409,'profile_changed_reload')
            # Remove identifying audit links as well as the participant's cascaded records.
            c.execute('DELETE FROM audit_events WHERE entity_id=? OR entity_id IN (SELECT id FROM checkins WHERE participant_id=?)',(identity,identity))
            c.execute('DELETE FROM participants WHERE id=? AND mode=?',(identity,mode))
            audit(c,'participant_deleted','deleted-record',mode)
            return {'deleted':True,'participant_id':identity,'checkins_deleted':True}
    @app.get('/api/participants/{participant_id}/checkins',dependencies=[Depends(authenticated)])
    def list_checkins(participant_id:UUID,mode:Mode):
        with store.connect() as c:
            person(c,str(participant_id),mode)
            rows=c.execute('SELECT * FROM checkins WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC',(str(participant_id),mode)).fetchall()
            return {'items':[view_checkin(c,r) for r in rows]}
    @app.post('/api/participants/{participant_id}/checkins',dependencies=[Depends(authenticated)],status_code=201)
    def create_checkin(participant_id:UUID,mode:Mode,payload:NewCheckin):
        identity=str(payload.id);conditions=payload.model_dump(mode='json');conditions.pop('id');conditions.pop('participant_revision')
        with store.connect(True) as c:
            p=person(c,str(participant_id),mode)
            old=c.execute('SELECT * FROM checkins WHERE id=?',(identity,)).fetchone()
            if old:
                if old['participant_id']!=str(participant_id) or old['mode']!=mode or old['participant_revision']!=payload.participant_revision or json.loads(old['conditions'])!=conditions:raise HTTPException(409,'idempotency_conflict')
                return view_checkin(c,old)
            if p['revision']!=payload.participant_revision:raise HTTPException(409,'profile_changed_reload')
            profile=json.loads(p['profile']);verdict=gate(profile,conditions)
            previous=c.execute("SELECT id,profile,practice FROM checkins WHERE participant_id=? AND mode=? AND status='completed' ORDER BY created_at DESC,id DESC LIMIT 1",(str(participant_id),mode)).fetchone()
            comparison_snapshot=comparison(json.loads(previous['profile']) if previous else None,profile)
            comparison_snapshot['reference_checkin_id']=previous['id'] if previous else None
            comparison_snapshot['reference_observed_inputs']=json.loads(previous['practice'])['observed_inputs'] if previous and previous['practice'] else None
            c.execute('INSERT INTO checkins VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
              (identity,str(participant_id),mode,p['profile'],p['revision'],dump(conditions),dump(verdict),
               'ready' if verdict['practice_allowed'] else 'needs_support',now(),None,None,dump(comparison_snapshot)))
            audit(c,'checkin_created',identity,mode);return view_checkin(c,checkin(c,identity,mode))
    @app.get('/api/checkins/{checkin_id}',dependencies=[Depends(authenticated)])
    def get_checkin(checkin_id:UUID,mode:Mode):
        with store.connect() as c:return view_checkin(c,checkin(c,str(checkin_id),mode))
    @app.put('/api/checkins/{checkin_id}/practice',dependencies=[Depends(authenticated)])
    def save_practice(checkin_id:UUID,mode:Mode,payload:Practice):
        normalized=payload.model_dump(mode='json');identity=str(checkin_id)
        stage=0;errors=0
        for e in normalized['events']:
            if stage>1:raise HTTPException(422,'extra_practice_events')
            if e['kind']!=('activate' if stage==0 else 'match'):raise HTTPException(422,'practice_order_invalid')
            correct=e['response']==('button' if stage==0 else 'circle')
            if correct:stage+=1
            else:errors+=1
        if stage!=2:raise HTTPException(422,'practice_incomplete')
        with store.connect(True) as c:
            row=checkin(c,identity,mode)
            if not json.loads(row['gate'])['practice_allowed']:raise HTTPException(409,'checkin_needs_support')
            # The original payload is retained separately from derived counts for exact retries.
            if row['practice']:
                if json.loads(row['practice'])['submitted']!=normalized:raise HTTPException(409,'practice_already_saved')
                return view_checkin(c,row)
            profile=json.loads(row['profile'])
            if payload.interface_language!=profile['language']:raise HTTPException(422,'practice_language_mismatch')
            inputs=sorted({e['input'] for e in normalized['events']})
            quality=[]
            if payload.focus_changes:quality.append('FOCUS_CHANGED_DURING_PRACTICE')
            if profile['assistance']=='responses':quality.append('RESPONSES_ASSISTED')
            if any(v!=profile['input_method'] for v in inputs):quality.append('OBSERVED_INPUT_DIFFERS')
            comp=json.loads(row['comparison'])
            prior_inputs=comp.get('reference_observed_inputs')
            if prior_inputs is not None and prior_inputs!=inputs:
                comp['changes'].append(dict(field='observed_inputs',before=prior_inputs,after=inputs))
                comp['state']='conditions_changed'
            result=dict(submitted=normalized,units={'elapsed_ms':'ms','steps_completed':'count','incorrect_actions':'count','focus_changes':'count'},measurement_method='native_button_activation',steps_completed=2,incorrect_actions=errors,observed_inputs=inputs,quality_flags=quality,
                        interpretation='usability_practice_only_not_cognitive_score',timing='client_reported_approximate_ms')
            c.execute("UPDATE checkins SET practice=?,status='completed',completed_at=?,comparison=? WHERE id=?",(dump(result),now(),dump(comp),identity))
            audit(c,'practice_completed',identity,mode);return view_checkin(c,checkin(c,identity,mode))
    # NeuroCognition X shares authentication, mode boundaries and persistent storage.
    from battery import make_router
    cognitive_router = make_router(store,authenticated)
    app.include_router(cognitive_router)
    from sense_store import make_router as sense_router
    app.include_router(sense_router(store,authenticated))
    from neurovision_bridge import make_router as vision_router
    app.include_router(vision_router(authenticated))
    from neurovision_import_bridge import make_router as vision_import_router
    app.include_router(vision_import_router(authenticated))
    from neurotwin_bridge import make_router as twin_router
    cognitive_analytics = next((r.endpoint for r in cognitive_router.routes if getattr(r, 'path', '') == '/api/ncx/participants/{pid}/analytics'), None)
    app.include_router(twin_router(store, authenticated, cognitive_analytics))
    from brainbody_bridge import make_router as brainbody_router
    bb_cognitive_analytics = next((r.endpoint for r in cognitive_router.routes if getattr(r, 'path', '') == '/api/ncx/participants/{pid}/analytics'), None)
    app.include_router(brainbody_router(store, authenticated, bb_cognitive_analytics))
    from neuroevidence_bridge import make_router as evidence_router
    ng_cognition_router = locals().get('cognitive_router')
    ng_cognition_analytics = next((route.endpoint for route in ng_cognition_router.routes
        if getattr(route, 'path', '') == '/api/ncx/participants/{pid}/analytics'), None) if ng_cognition_router else None
    app.include_router(evidence_router(store, authenticated, ng_cognition_analytics))
    from prevention_bridge import make_router as prevention_router
    app.include_router(prevention_router(store, authenticated, locals().get('ng_cognition_analytics')))
    from arena_platform_bridge import mount as mount_arena_platform
    mount_arena_platform(app, store, authenticated)
    from neurocontinuum_bridge import mount as mount_neurocontinuum
    mount_neurocontinuum(app, store, authenticated, cognitive_router)
    return app

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Initialize NeuroAccess local storage and show the local operator login code.')
    parser.add_argument('--show-login',action='store_true');args=parser.parse_args()
    app=create_app()
    print('Persistent data directory:',root_path())
    if args.show_login:print('LOCAL OPERATOR LOGIN CODE:',(root_path()/'local_operator_secret.txt').read_text(encoding='utf-8'))
