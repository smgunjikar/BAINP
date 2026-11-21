"""Opt-in participant/mode scoped API, mounted inside the native operator boundary."""
from datetime import datetime,timezone
import json,sys
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from bainp_continuum_engine import person,now,dump,digest,replay,remember
from bainp_shadow_engine import VERSION,ACTIVITY,extract
Mode=Literal['active','demo']
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
class Permission(Strict):
    operation_id:UUID=Field(strict=False)
    expected_revision:int=Field(ge=0)
    enabled:bool
    share_context:bool
class Device(Strict):
    width_bucket:int=Field(ge=1,le=100)
    height_bucket:int=Field(ge=1,le=100)
    pixel_ratio_bucket:int=Field(ge=1,le=8)
    pointer:Literal['mouse','touch','pen']
    reduced_motion:bool
class Begin(Strict):
    operation_id:UUID=Field(strict=False)
    session_id:UUID=Field(strict=False)
    consent_revision:int=Field(ge=1)
    activity:Literal['shadow-explore-v1']
    device:Device
class Event(Strict):
    t_ms:int=Field(ge=0,le=120000,multiple_of=50)
    kind:Literal['move','down','up']
    pointer:Literal['mouse','touch','pen']
    x_bin:int=Field(ge=0,le=20)
    y_bin:int=Field(ge=0,le=20)
class Finish(Strict):
    operation_id:UUID=Field(strict=False)
    consent_revision:int=Field(ge=1)
    duration_ms:int=Field(ge=0,le=120000,multiple_of=50)
    events:list[Event]=Field(max_length=2400)
    frame_count:int=Field(ge=0,le=30000)
    slow_frames:int=Field(ge=0,le=30000)
    hidden_count:int=Field(ge=0,le=100)
    resize_count:int=Field(ge=0,le=100)
    @model_validator(mode='after')
    def valid(self):
        if self.slow_frames>self.frame_count:raise ValueError('Invalid frame diagnostics')
        stamps=[e.t_ms for e in self.events]
        if stamps!=sorted(stamps) or any(t>self.duration_ms for t in stamps):raise ValueError('Invalid event timeline')
        if len(self.events)>self.duration_ms/1000*40+20:raise ValueError('Event rate exceeds protocol budget')
        return self
class Operation(Strict):operation_id:UUID=Field(strict=False)
SCHEMA='''
CREATE TABLE IF NOT EXISTS ns_consents(participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,revision INTEGER NOT NULL,enabled INTEGER NOT NULL,share_context INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(participant_id,mode));
CREATE TABLE IF NOT EXISTS ns_sessions(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,consent_revision INTEGER NOT NULL,profile_revision INTEGER NOT NULL,state TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,condition_hash TEXT NOT NULL,device TEXT NOT NULL,summary TEXT,sha256 TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ns_one_open ON ns_sessions(participant_id,mode) WHERE state='COLLECTING';
CREATE TABLE IF NOT EXISTS ns_events(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,at TEXT NOT NULL,action TEXT NOT NULL,payload TEXT NOT NULL);
'''
def permission(c,pid,mode):
    r=c.execute('SELECT * FROM ns_consents WHERE participant_id=? AND mode=?',(str(pid),mode)).fetchone()
    return dict(r) if r else dict(revision=0,enabled=0,share_context=0)
def audit(c,pid,mode,action,payload):c.execute('INSERT INTO ns_events VALUES(?,?,?,?,?,?)',(str(uuid4()),str(pid),mode,now(),action,dump(payload)))
def context(c,pid,mode):
    p=person(c,pid,mode);auth=permission(c,pid,mode)
    if not auth['enabled'] or not auth['share_context']:return dict(state='WITHHELD_BY_NEUROSHADOW_PERMISSION',clinical_inference_allowed=False)
    rows=c.execute("SELECT * FROM ns_sessions WHERE participant_id=? AND mode=? AND state='COMPLETED' AND profile_revision=? ORDER BY finished_at DESC,id DESC LIMIT 50",(str(pid),mode,p['revision'])).fetchall()
    usable=[r for r in rows if r['summary'] and digest(json.loads(r['summary']))==r['sha256'] and json.loads(r['summary'])['quality']['state']=='TECHNICAL_QC_CLEAR']
    result=dict(state='NO_CURRENT_QC_CLEAR_CONTEXT',experimental=True,clinical_inference_allowed=False,selection_influence='NONE_V1',policy=VERSION)
    if usable:
        latest=usable[0];value=json.loads(latest['summary']);result.update(state='DESCRIPTIVE_CONTEXT_ONLY',reference_id=latest['id'],source_hash=latest['sha256'],observed_at=latest['finished_at'],features=value['features'],quality=value['quality'])
    return result

def mount(app):
    engine=app.state.neurocontinuum;store=engine.store
    from neurocontinuum_bridge import _quest_auth
    with store.connect() as c:c.executescript(SCHEMA)
    app.state.neuroshadow_context=lambda c,pid,mode:context(c,pid,mode)
    def for_quest(c,pid,mode):
        result=context(c,pid,mode)
        # NQ records only a contextual source reference and technical status, not duplicated features.
        return {k:v for k,v in result.items() if k!='features'}
    engine.ports.shadow_context=for_quest
    router=APIRouter(prefix='/api/neuroshadow/v1',dependencies=[Depends(_quest_auth)])
    @router.get('/participants/{pid}')
    def workspace(pid:UUID,mode:Mode):
        with store.connect() as c:
            p=person(c,pid,mode);auth=permission(c,pid,mode);rows=[]
            if auth['enabled']:
                for row in c.execute('SELECT * FROM ns_sessions WHERE participant_id=? AND mode=? ORDER BY started_at DESC,id DESC LIMIT 50',(str(pid),mode)):
                    value=json.loads(row['summary']) if row['summary'] else None
                    rows.append(dict(id=row['id'],state=row['state'],started_at=row['started_at'],finished_at=row['finished_at'],condition_hash=row['condition_hash'],profile_revision=row['profile_revision'],summary=value,integrity_ok=digest(value)==row['sha256'] if value else None))
            comparison=dict(state='INSUFFICIENT_SAME_CONDITION_SESSIONS',clinical_comparability=False)
            clear=[r for r in rows if r['integrity_ok'] and r['summary']['quality']['state']=='TECHNICAL_QC_CLEAR' and r['profile_revision']==p['revision']]
            if clear:
                latest=clear[0];prior=next((r for r in clear[1:] if r['condition_hash']==latest['condition_hash']),None)
                comparison.update(latest_id=latest['id'],other_condition_count=sum(r['condition_hash']!=latest['condition_hash'] for r in clear[1:]))
                if prior:
                    comparison.update(state='DESCRIPTIVE_SAME_CONDITION_PAIR',previous_id=prior['id'],deltas={k:round(latest['summary']['features'][k]-prior['summary']['features'][k],6) for k in ('normalized_path_length','click_count','movement_gap_count')},interpretation='Difference only. No cognitive change, stability or disease conclusion.')
            return dict(name=json.loads(p['profile'])['display_name'],consent=auth,sessions=rows,comparison=comparison,version=VERSION,activity=ACTIVITY)
    @router.get('/participants/{pid}/consent')
    def get_permission(pid:UUID,mode:Mode):
        with store.connect() as c:
            person(c,pid,mode)
            return permission(c,pid,mode)
    @router.put('/participants/{pid}/consent')
    def configure(pid:UUID,mode:Mode,payload:Permission):
        request={'kind':'shadow_permission',**payload.model_dump(mode='json')}
        with store.connect(True) as c:
            person(c,pid,mode);old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            auth=permission(c,pid,mode)
            if auth['revision']!=payload.expected_revision:raise HTTPException(409,'permission_changed_refresh')
            if payload.share_context and not payload.enabled:raise HTTPException(422,'sharing_requires_collection_permission')
            revision=auth['revision']+1
            c.execute('INSERT OR REPLACE INTO ns_consents VALUES(?,?,?,?,?,?)',(str(pid),mode,revision,int(payload.enabled),int(payload.share_context),now()))
            c.execute("UPDATE ns_sessions SET state='INTERRUPTED',finished_at=? WHERE participant_id=? AND mode=? AND state='COLLECTING'",(now(),str(pid),mode))
            audit(c,pid,mode,'permission_changed',dict(revision=revision,enabled=payload.enabled,share_context=payload.share_context))
            return remember(c,payload.operation_id,str(pid),mode,request,dict(revision=revision,enabled=payload.enabled,share_context=payload.share_context))
    @router.post('/participants/{pid}/sessions')
    def begin(pid:UUID,mode:Mode,payload:Begin):
        request={'kind':'shadow_begin',**payload.model_dump(mode='json')}
        with store.connect(True) as c:
            p=person(c,pid,mode);auth=permission(c,pid,mode)
            if not auth['enabled'] or auth['revision']!=payload.consent_revision:raise HTTPException(403,'current_explicit_shadow_consent_required')
            old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            if c.execute("SELECT 1 FROM ns_sessions WHERE participant_id=? AND mode=? AND state='COLLECTING'",(str(pid),mode)).fetchone():raise HTTPException(409,'unfinished_collection_discard_or_revoke_first')
            if c.execute('SELECT 1 FROM ns_sessions WHERE id=?',(str(payload.session_id),)).fetchone():raise HTTPException(409,'session_id_already_used')
            if c.execute('SELECT count(*) FROM ns_sessions WHERE participant_id=? AND mode=? AND started_at>=?',(str(pid),mode,now()[:10])).fetchone()[0]>=50:raise HTTPException(429,'daily_research_session_budget_reached')
            device=payload.device.model_dump();condition=digest(dict(activity=ACTIVITY,version=VERSION,profile_revision=p['revision'],device=device))
            c.execute('INSERT INTO ns_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(str(payload.session_id),str(pid),mode,auth['revision'],p['revision'],'COLLECTING',now(),None,condition,dump(device),None,None))
            audit(c,pid,mode,'collection_started',dict(session_id=str(payload.session_id),consent_revision=auth['revision']))
            return remember(c,payload.operation_id,str(pid),mode,request,dict(session_id=str(payload.session_id),state='COLLECTING',consent_revision=auth['revision']))
    @router.post('/participants/{pid}/sessions/{sid}/finish')
    def finish(pid:UUID,sid:UUID,mode:Mode,payload:Finish):
        request={'kind':'shadow_finish','sid':str(sid),**payload.model_dump(mode='json')}
        with store.connect(True) as c:
            p=person(c,pid,mode);auth=permission(c,pid,mode)
            if not auth['enabled'] or auth['revision']!=payload.consent_revision:raise HTTPException(403,'collection_permission_changed_discard_buffer')
            row=c.execute('SELECT * FROM ns_sessions WHERE id=? AND participant_id=? AND mode=?',(str(sid),str(pid),mode)).fetchone()
            if not row:raise HTTPException(404,'session_not_found')
            old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            if row['state']!='COLLECTING' or row['consent_revision']!=auth['revision']:raise HTTPException(409,'collection_not_open')
            if row['profile_revision']!=p['revision']:raise HTTPException(409,'profile_changed_discard_collection')
            device=json.loads(row['device'])
            if any(e.pointer!=device['pointer'] for e in payload.events):raise HTTPException(422,'mixed_pointer_types_not_comparable')
            features=extract(payload.events,payload.duration_ms)
            server_ms=(datetime.now(timezone.utc)-datetime.fromisoformat(row['started_at'])).total_seconds()*1000
            diagnostics=dict(frame_count=payload.frame_count,slow_frames=payload.slow_frames,hidden_count=payload.hidden_count,resize_count=payload.resize_count,server_duration_mismatch=payload.duration_ms>server_ms+2000)
            policy=sys.modules.get('bainp_shadow_guard')
            if not policy or not callable(getattr(policy,'evaluate',None)):raise HTTPException(503,'shadow_guard_unavailable')
            quality=policy.evaluate(features,diagnostics)
            summary=dict(version=VERSION,activity=ACTIVITY,features=features,diagnostics=diagnostics,quality=quality,condition_hash=row['condition_hash'],raw_events_stored=False,clinical_interpretation='None. Experimental digital interaction measurements.')
            c.execute("UPDATE ns_sessions SET state='COMPLETED',finished_at=?,summary=?,sha256=? WHERE id=?",(now(),dump(summary),digest(summary),str(sid)))
            audit(c,pid,mode,'aggregates_saved',dict(session_id=str(sid),summary_hash=digest(summary),quality=quality['state']))
            return remember(c,payload.operation_id,str(pid),mode,request,dict(session_id=str(sid),summary=summary,sha256=digest(summary)))
    @router.post('/participants/{pid}/sessions/{sid}/discard')
    def discard(pid:UUID,sid:UUID,mode:Mode,payload:Operation):
        request={'kind':'shadow_discard','sid':str(sid),**payload.model_dump(mode='json')}
        with store.connect(True) as c:
            person(c,pid,mode);old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            row=c.execute('SELECT state FROM ns_sessions WHERE id=? AND participant_id=? AND mode=?',(str(sid),str(pid),mode)).fetchone()
            if not row:raise HTTPException(404,'session_not_found')
            if row['state']=='COLLECTING':c.execute("UPDATE ns_sessions SET state='INTERRUPTED',finished_at=? WHERE id=?",(now(),str(sid)))
            audit(c,pid,mode,'collection_discarded',dict(session_id=str(sid)))
            return remember(c,payload.operation_id,str(pid),mode,request,dict(state='DISCARDED'))
    app.include_router(router)
