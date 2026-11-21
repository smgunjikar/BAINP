"""Additive participant presentation and persisted onboarding. No clinical inference.
Uses existing local-operator authentication; this is not participant account isolation.
"""
import json
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from bainp_continuum_engine import person, consent, now, dump, replay, remember, source_results, native_status

STEPS = ('welcome', 'profile', 'accessibility', 'consent', 'concerns')
SCOPES = ('enabled', 'assessment_allowed', 'history_allowed', 'case_tracking')
SCHEMA = '''CREATE TABLE IF NOT EXISTS participant_onboarding_v1 (
participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
mode TEXT NOT NULL CHECK(mode IN ('active','demo')), version INTEGER NOT NULL,
answers TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(participant_id,mode));'''
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
class Save(Strict):
    operation_id: UUID = Field(strict=False)
    expected_version: int = Field(ge=0)
    step: Literal['welcome','profile','accessibility','consent','concerns']
    answer: dict
class Welcome(Strict):
    acknowledged: Literal[True]
class Profile(Strict):
    profile_revision: int = Field(ge=1)
class Accessibility(Profile):
    choice: Literal['none','needed','later']
class Permission(Strict):
    consent_revision: int = Field(ge=1)
    shadow_revision: int = Field(ge=0)
    enabled: bool
    assessment_allowed: bool
    history_allowed: bool
    case_tracking: bool
    shadow_enabled: bool
class Concerns(Strict):
    everyday_changes: Literal['no','yes','prefer_not_to_answer']
MODELS = dict(welcome=Welcome, profile=Profile, accessibility=Accessibility, consent=Permission, concerns=Concerns)

def state(c, pid, mode):
    row = c.execute('SELECT * FROM participant_onboarding_v1 WHERE participant_id=? AND mode=?',(str(pid),mode)).fetchone()
    return dict(version=row['version'],answers=json.loads(row['answers']),updated_at=row['updated_at']) if row else dict(version=0,answers={},updated_at=None)

def missing(answers):
    return next((s for s in STEPS if s not in answers), None)

def mount(app, store, authenticated, cognitive_router):
    if getattr(app.state, "continuum_participant_mounted", False):
        return
    engine = app.state.neurocontinuum
    with store.connect() as c:
        c.executescript(SCHEMA)
    base='/api/neurocontinuum/v1/participant-home'
    router=APIRouter(prefix=base,dependencies=[Depends(authenticated)])
    def native_workspace(pid,mode):
        with store.connect() as c:
            p=person(c,pid,mode);auth=consent(c,pid,mode)
            sessions=[dict(r)|{'payload':json.loads(r['payload'])} for r in c.execute('SELECT * FROM ncw_sessions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 100',(str(pid),mode))]
            if not auth['enabled']:
                for item in sessions:item['payload']={k:v for k,v in item['payload'].items() if k not in ('history','result','recommendation')}
            checkins=[dict(r) for r in c.execute('SELECT id,status,created_at,participant_revision FROM checkins WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 50',(str(pid),mode))]
            cases=[]
            if auth['enabled'] and auth['case_tracking'] and c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='careloop_cases'").fetchone():
                cases=[dict(r) for r in c.execute('SELECT id,state,version,priority,updated_at FROM careloop_cases WHERE participant_id=? AND mode=? ORDER BY updated_at DESC LIMIT 30',(str(pid),mode))]
            return dict(participant_id=str(pid),mode=mode,consent=auth,sessions=sessions,checkins=checkins,cases=cases)
    def shadow(c,pid,mode):
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ns_consents'").fetchone():
            return dict(revision=0,enabled=0,available=False)
        row=c.execute('SELECT * FROM ns_consents WHERE participant_id=? AND mode=?',(str(pid),mode)).fetchone()
        return (dict(row) if row else dict(revision=0,enabled=0)) | dict(available=True)
    def action(kind,title,reason,**more):
        return dict(kind=kind,title=title,reason=reason,**more)
    def route(pid,mode,saved,workspace):
        answers=saved['answers'];sessions=workspace['sessions'];auth=workspace['consent']
        # Saved native safety restrictions precede routine onboarding and task suggestions.
        for s in sessions:
            if (s['payload'].get('safety') or {}).get('state')=='escalate' or s['payload'].get('reason')=='NEUROQUEST_URGENT_OVERRIDE':
                return action('safety','Review saved safety guidance','Routine assessment is withheld. Open your saved guidance and seek appropriate support.',url=f'/neurocontinuum?mode={mode}&person={pid}')
        step=missing(answers)
        if step:
            return action('onboarding','Continue your setup','Your saved answers are ready when you are.',step=step)
        if not auth['enabled'] or not auth['assessment_allowed']:
            return action('limited','Your preferences are saved','Assessments are switched off. You can still review your profile, privacy choices and support.')
        if answers['concerns']['everyday_changes']=='yes':
            return action('review','Discuss your everyday changes','Your answer is saved. This prototype cannot evaluate its clinical significance. Review it with an appropriate professional; do not use another test as a substitute.',url=f'/careloop?mode={mode}&person={pid}')
        current=next((s for s in sessions if s['state'] not in ('COMPLETED','CANCELLED')),None)
        if current:
            extra=dict(session_id=current['id'],expected_version=current['version'])
            if current['state'] in ('BLOCKED','FAILED'):
                reason=current['payload'].get('reason')
                if current['state']=='BLOCKED' and reason in ('NATIVE_ASSESSMENT_INTERRUPTED_NO_COMPLETION_INFERRED',
                        'NEUROQUEST_REPEAT','NEUROQUEST_TARGETED','NEUROQUEST_ABSTAIN'):
                    return action('incomplete','Your previous assessment is incomplete',
                        'Your recorded responses remain saved. Review the incomplete visit before starting a new one; no valid score is inferred.',
                        code=reason,url=f'/neurocontinuum?mode={mode}&person={pid}',**extra)
                return action('review','Your session needs attention','Your setup is retained. Review the current restriction before continuing.',code=reason,url=f'/neurocontinuum?mode={mode}&person={pid}',**extra)
            if current['state']=='PAUSED':
                return action('command','Resume your saved journey','The workflow rechecks current permissions and eligibility. Task resumption depends on its protocol.',command='resume',**extra)
            if current['state']=='ASSESSING':
                with store.connect() as c:
                    p=person(c,pid,mode)
                    holds=engine.access_reasons(c,current,p,engine.ports.access(current['checkin_id'],mode))
                    verdict=engine.ports.workflow_decision(dict(participant_id=str(pid),source_participant_id=str(pid),mode=mode,source_mode=mode,
                        checkin_id=current['checkin_id'],monitoring_consent=bool(auth['enabled']),assessment_consent=bool(auth['assessment_allowed']),native_guard_available=engine.ports.guard_ready(),access_reasons=holds))
                    if verdict.get('state')!='workflow_permitted' or 'existing_neurocognition' not in verdict.get('allowed_actions',[]):
                        holds=holds+['CURRENT_GUARD_WITHHOLDS_ASSESSMENT']
                    native,attempts=source_results(c,current)
                if holds:return action('review','Review assessment readiness','Your current setup needs review before testing.',code=', '.join(holds),url=f'/neurocontinuum?mode={mode}&person={pid}')
                status=native_status(native,attempts)
                if status=='completed':return action('command','Review your saved results','Quality review is next.',command='advance',**extra)
                if status=='interrupted':return action('incomplete','Review interrupted assessment','An interrupted assessment is not a completed result.',url=f'/neurocontinuum?mode={mode}&person={pid}')
                return action('assessment','Open your selected assessment','Read the task instructions before beginning.',url=engine.ports.cognition_url(current['checkin_id'],mode)+'&journey=1&person='+str(pid),**extra)
            return action('command','Continue your guided journey','The next step checks permissions, safety and the available assessment catalogue.',command='advance',**extra)
        if sessions and sessions[0]['state']=='COMPLETED':
            return action('summary','Your session summary is ready','Review results and limitations before deciding on a follow-up.',summary=sessions[0]['payload'].get('summary',{}),url=f'/neurocontinuum?mode={mode}&person={pid}')
        previous=sessions[0] if sessions else None
        incomplete=bool(previous and (previous['payload'].get('summary') or {}).get('disposition')=='INCOMPLETE_VISIT')
        linked={s['checkin_id'] for s in sessions}
        with store.connect() as c:
            p=person(c,pid,mode)
            for checkin in workspace['checkins']:
                if checkin['id'] in linked or (incomplete and checkin['created_at']<=previous['updated_at']):
                    continue
                if checkin['status']=='completed' and not engine.access_reasons(c,dict(checkin_id=checkin['id'],mode=mode),p,engine.ports.access(checkin['id'],mode)):
                    return action('start','Begin a separate research visit' if incomplete else 'Prepare your first assessment',
                        'A fresh, independent visit retains the previous incomplete evidence and is not an equivalent repeat.' if incomplete else 'The existing workflow checks safety and asks NeuroQuest for a supported next action.',
                        checkin_id=checkin['id'],acknowledge_prior_quality=incomplete)
        return action('checkin','Complete a new accessibility check-in' if incomplete else 'Check your assessment setup',
            'Your incomplete records remain saved. A fresh check-in is required before a separate research visit.' if incomplete else 'Confirm today’s conditions and try the controls. This is usability practice, not a cognitive score.')
    @router.get('/participants/{pid}')
    def home(pid:UUID,mode:Literal['active','demo']):
        workspace=native_workspace(pid,mode)
        with store.connect() as c:
            p=person(c,pid,mode);saved=state(c,pid,mode);optional=shadow(c,pid,mode)
            follow_up=app.state.neurocontinuum_followup.build(c,str(pid),mode)
        return dict(participant=dict(id=str(pid),revision=p['revision'],profile=json.loads(p['profile'])),onboarding=saved,
                    next_action=route(pid,mode,saved,workspace),workspace=workspace,shadow=optional,post_assessment=follow_up,
                    steps=list(STEPS),identity='local_operator_assisted_participant',independent_participant_auth=False,
                    clinical_validation=False)
    @router.put('/participants/{pid}/onboarding')
    def save(pid:UUID,mode:Literal['active','demo'],payload:Save):
        from pydantic import ValidationError
        try:answer=MODELS[payload.step].model_validate(payload.answer).model_dump(mode='json')
        except ValidationError:raise HTTPException(422,'invalid_onboarding_answer') from None
        request={'kind':'participant_onboarding_v1',**payload.model_dump(mode='json')}
        with store.connect(True) as c:
            p=person(c,pid,mode);old=replay(c,payload.operation_id,str(pid),mode,request)
            if old:return old
            current=state(c,pid,mode)
            if current['version']!=payload.expected_version:raise HTTPException(409,'onboarding_changed_reload')
            # Completed steps are editable; future mandatory steps cannot be skipped.
            first=missing(current['answers'])
            if first and STEPS.index(payload.step)>STEPS.index(first):raise HTTPException(409,'complete_previous_step')
            if payload.step in ('profile','accessibility') and answer['profile_revision']!=p['revision']:
                raise HTTPException(409,'profile_changed_reload')
            if payload.step=='accessibility' and answer['choice']=='none':
                profile=json.loads(p['profile'])
                if any(profile[k] for k in ('vision_limitation','hearing_limitation','motor_limitation')) or profile['assistance']!='none':
                    raise HTTPException(422,'accommodations_conflict_review_profile')
            if payload.step=='consent':
                auth=consent(c,pid,mode);optional=shadow(c,pid,mode)
                if answer['consent_revision']!=auth['revision'] or any(answer[k]!=bool(auth[k]) for k in SCOPES):
                    raise HTTPException(409,'save_native_permissions_first')
                if answer['shadow_revision']!=optional['revision'] or answer['shadow_enabled']!=bool(optional['enabled']):
                    raise HTTPException(409,'save_shadow_permission_first')
            current['answers'][payload.step]=answer
            version=current['version']+1
            c.execute('INSERT INTO participant_onboarding_v1 VALUES(?,?,?,?,?) ON CONFLICT(participant_id,mode) DO UPDATE SET version=excluded.version,answers=excluded.answers,updated_at=excluded.updated_at',
                      (str(pid),mode,version,dump(current['answers']),now()))
            return remember(c,payload.operation_id,str(pid),mode,request,dict(version=version,saved_step=payload.step))
    app.include_router(router)
    app.state.continuum_participant_mounted = True
