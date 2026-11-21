"""Authenticated API mounted inside the existing NeuroAccess application."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from bainp_continuum_engine import Engine, VERSION, POLICY, person, consent, session, audit_chain, readiness_changes
from bainp_continuum_ports import Ports

Mode = Literal['active','demo']
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
class ConsentInput(Strict):
    operation_id: UUID = Field(strict=False)
    expected_revision: int = Field(ge=0)
    enabled: bool
    history_allowed: bool
    assessment_allowed: bool
    case_tracking: bool
class SessionInput(Strict):
    operation_id: UUID = Field(strict=False)
    session_id: UUID = Field(strict=False)
    checkin_id: UUID | None = Field(default=None, strict=False)
    acknowledge_prior_quality: bool = False
class RecoveryInput(Strict):
    operation_id:UUID=Field(strict=False)
    expected_version:int=Field(ge=1)
    checkin_id:UUID=Field(strict=False)
    correction_confirmed:bool
    correction:Literal['device_checked','input_checked','instructions_reviewed','interruption_resolved','other_reviewed']

class CommandInput(Strict):
    operation_id: UUID = Field(strict=False)
    expected_version: int = Field(ge=1)
    action: Literal['advance','pause','resume','cancel','finish_incomplete','retry','sync','request_review','safety']
    signs: list[Literal['face','limb','speech','vision','balance','headache']] = Field(default_factory=list, max_length=6)

"""Deterministic presentation policy. No diagnosis, new scoring or autonomous action."""
def journey_action(workspace):
    auth=workspace['consent'];sessions=workspace['sessions']
    base=dict(participant_id=workspace['participant_id'],mode=workspace['mode'],policy='participant-journey-v1',clinical_validation=False,consent_revision=auth['revision'])
    def result(kind,title,reason,**extra):return base|dict(kind=kind,title=title,reason=reason)|extra
    # Persisted safety holds take precedence over routine assessment selection.
    for s in sessions:
        safety=s['payload'].get('safety') or {}
        if safety.get('state')=='escalate' or s['payload'].get('reason')=='NEUROQUEST_URGENT_OVERRIDE':
            return result('safety','Review urgent safety guidance','A saved safety restriction requires attention.',session_id=s['id'])
    if not auth['enabled']:return result('consent','Review your monitoring permissions','Profile storage consent does not authorize assessment or monitoring.')
    if not auth['assessment_allowed']:return result('consent','Review assessment permission','Assessment permission is currently withheld. Support remains accessible.')
    current=next((s for s in sessions if s['state'] not in ('COMPLETED','CANCELLED')),None)
    if current:
        extra=dict(session_id=current['id'],expected_version=current['version'],state=current['state'])
        state=current['state'];body=current['payload']
        if state in ('BLOCKED','FAILED'):
            reason=body.get('reason','The workflow cannot safely continue.')
            if state=='BLOCKED' and reason in ('NATIVE_ASSESSMENT_INTERRUPTED_NO_COMPLETION_INFERRED',
                    'NEUROQUEST_REPEAT', 'NEUROQUEST_TARGETED', 'NEUROQUEST_ABSTAIN'):
                return result('incomplete','Review your incomplete visit',
                    'Earlier tasks and any quality warnings remain saved. You can end this incomplete visit without claiming assessment completion.',**extra)
            return result('review','Review what needs attention',reason,**extra)
        if state=='PAUSED':return result('command','Resume your monitoring session','Continue from saved workflow progress.',command='resume',**extra)
        if state=='ASSESSING':return result('assessment','Open your selected assessment','The existing workflow selected this pathway. Current eligibility must still be checked.',**extra)
        if state in ('CREATED','AUTHORIZED','VALIDATING','AWAITING_ACTION','RECORDING'):return result('command','Continue your monitoring journey','The next workflow step checks evidence, safety or result validity.',command='advance',**extra)
        return result('review','Review your session','This workflow state needs operator review.',**extra)
    if sessions and sessions[0]['state']=='COMPLETED':
        s=sessions[0];return result('summary','View your session summary','The digital session ended. Any clinical review case has its own status.',summary=s['payload'].get('summary',{}),session_id=s['id'])
    # An immutable check-in may belong to only one journey. After closing an
    # incomplete visit, a genuinely new check-in AND explicit acknowledgement
    # are required; never re-offer the check-in used by the cancelled session.
    prior=sessions[0] if sessions else None
    prior_incomplete=bool(prior and prior['state']=='CANCELLED'
        and (prior['payload'].get('summary') or {}).get('disposition')=='INCOMPLETE_VISIT')
    linked={s['checkin_id'] for s in sessions}
    ready=next((c for c in workspace['checkins']
        if c['status']=='completed' and c.get('readiness_compatible', False)
        and c['id'] not in linked
        and (not prior_incomplete or c['created_at']>prior['updated_at'])),None)
    if not ready:
        return result('checkin',
            'Complete a new accessibility check-in' if prior_incomplete else 'Complete your accessibility check-in',
            'Your previous incomplete measurements are preserved. Confirm current conditions and complete a new usability practice before an independent visit.' if prior_incomplete
            else 'Save current conditions and complete usability practice before routine assessment.')
    return result('start',
        'Begin a separate research visit' if prior_incomplete else 'Prepare your recommended pathway',
        'The earlier incomplete records are preserved. Confirm your separate visit before NeuroQuest selects an eligible action.' if prior_incomplete
        else 'NeuroContinuum will apply safety checks before NeuroQuest selects from supported tasks.',
        checkin_id=ready['id'],acknowledge_prior_quality=prior_incomplete)


def mount(app, store, authenticated, cognitive_router):
    ports = Ports(app, store, cognitive_router)
    engine = Engine(store, ports)
    app.state.neurocontinuum = engine
    # Load the read-only reconciliation module before participant-home mounts.
    import importlib.util
    import sys
    from pathlib import Path
    followup_path = Path(__file__).with_name('followup.py')
    followup_spec = importlib.util.spec_from_file_location('bainp_continuum_followup', followup_path)
    followup_module = importlib.util.module_from_spec(followup_spec)
    sys.modules[followup_spec.name] = followup_module
    followup_spec.loader.exec_module(followup_module)
    app.state.neurocontinuum_followup = followup_module
    router = APIRouter(prefix='/api/neurocontinuum/v1', dependencies=[Depends(authenticated)])

    @router.get('/status')
    def status():
        return dict(version=VERSION, policy=POLICY, storage='existing BAINP SQLite',
                    identity='existing authenticated local operator', independent_clinician_roles=False,
                    guard_connected=ports.guard_ready(), careloop_connected=ports.cases_ready(), modules=ports.directory(),
                    scope='Workflow coordination. No diagnosis, treatment, prediction, scoring or retraining.',
                    warning='Existing warning-sign guidance does not create or deliver an emergency referral.')

    @router.get('/participants/{pid}/workspace')
    def workspace(pid: UUID, mode: Mode):
        with store.connect() as connection:
            p = person(connection, pid, mode)
            import json
            profile = json.loads(p['profile'])
            authorization = consent(connection, pid, mode)
            items = [dict(r) | {'payload':json.loads(r['payload'])} for r in connection.execute('SELECT * FROM ncw_sessions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 100', (str(pid),mode))]
            # A consent withdrawal hides retained content from this workflow while preserving the existing deletion boundary.
            if not authorization['enabled']:
                for item in items:
                    item['payload'] = {k:v for k,v in item['payload'].items() if k not in ('history','result','recommendation')}
            checkins = [dict(r) for r in connection.execute('SELECT id,status,created_at,participant_revision,profile FROM checkins WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 50', (str(pid),mode))]
            for checkin in checkins:
                changed = readiness_changes(json.loads(checkin.pop('profile')), profile)
                checkin['readiness_compatible'] = not changed
                checkin['readiness_changed_fields'] = changed
            references = [json.loads(r['payload']) for r in connection.execute('SELECT payload FROM ncw_observation_refs WHERE participant_id=? AND mode=? ORDER BY rowid DESC LIMIT 100', (str(pid),mode))] if authorization['enabled'] and authorization['history_allowed'] else []
            cases = []
            if authorization['enabled'] and authorization['case_tracking'] and ports.cases_ready():
                cases = [dict(r) for r in connection.execute('SELECT id,state,version,priority,updated_at FROM careloop_cases WHERE participant_id=? AND mode=? ORDER BY updated_at DESC LIMIT 30', (str(pid),mode))]
            follow_up = followup_module.build(connection, str(pid), mode)
            return dict(post_assessment=follow_up,participant_id=str(pid),mode=mode,display_name=profile['display_name'],profile_revision=p['revision'],
                        preferences={key:profile[key] for key in ('language','text_size','high_contrast','reduced_motion','input_method','assistance')},
                        consent=authorization,sessions=items,checkins=checkins,observation_references=references,cases=cases,
                        modules=ports.directory(),clinical_validation=False)

    @router.get('/participants/{pid}/post-assessment')
    def post_assessment(pid: UUID, mode: Mode):
        with store.connect() as connection:
            return followup_module.build(connection, str(pid), mode)

    @router.get('/participants/{pid}/next-action')
    def next_action(pid: UUID, mode: Mode):
        snapshot=workspace(pid,mode)
        action=journey_action(snapshot)
        if action['kind']=='assessment':
            from bainp_continuum_engine import source_results,native_status
            with store.connect() as c:
                item=session(c,action['session_id'],mode)
                p=person(c,pid,mode)
                access=ports.access(item['checkin_id'],mode)
                holds=engine.access_reasons(c,item,p,access)
                verdict=ports.workflow_decision(dict(participant_id=str(pid),source_participant_id=str(pid),mode=mode,source_mode=mode,
                    checkin_id=item['checkin_id'],monitoring_consent=bool(snapshot['consent']['enabled']),assessment_consent=bool(snapshot['consent']['assessment_allowed']),native_guard_available=ports.guard_ready(),access_reasons=holds))
                if verdict.get('state')!='workflow_permitted' or 'existing_neurocognition' not in verdict.get('allowed_actions',[]):
                    action.update(kind='review',title='Review assessment restrictions',reason='Current access or safety checks withhold routine testing.')
                else:
                    native,attempts=source_results(c,item)
                    if native_status(native,attempts)=='completed':action.update(kind='command',command='advance',title='Review your saved results',reason='Results are saved; workflow quality validation is pending.')
                    elif native_status(native,attempts)=='interrupted':
                        action.update(kind='incomplete',title='Review your interrupted assessment',
                            reason='Your original attempt is retained. End the incomplete visit explicitly or review the source attempt; no completed score is inferred.')
                    else:
                        action['url']=ports.cognition_url(item['checkin_id'],mode)+'&journey=1&person='+str(pid)
        return dict(next_action=action,display_name=snapshot['display_name'],profile_revision=snapshot['profile_revision'],consent=snapshot['consent'],checkins=snapshot['checkins'],role='local_operator_assisted_participant',independent_participant_auth=False)

    @router.put('/participants/{pid}/consent')
    def configure(pid: UUID, mode: Mode, payload: ConsentInput):
        return engine.configure(str(pid), mode, payload.model_dump(mode='json'))

    @router.post('/participants/{pid}/sessions')
    def start(pid: UUID, mode: Mode, payload: SessionInput):
        return engine.start(str(pid), mode, payload.model_dump(mode='json'))

    @router.post('/sessions/{sid}/commands')
    def command(sid: UUID, mode: Mode, payload: CommandInput):
        if payload.signs and payload.action != 'safety':
            raise HTTPException(422, 'warning_signs_only_for_safety_action')
        return engine.command(str(sid), mode, payload.model_dump(mode='json'))

    @router.post('/sessions/{sid}/recovery')
    def recover(sid:UUID,mode:Mode,payload:RecoveryInput):
        return engine.prepare_recovery(str(sid),mode,payload.model_dump(mode='json'))

    @router.get('/sessions/{sid}/evidence')
    def evidence(sid: UUID, mode: Mode):
        with store.connect() as connection:
            item = session(connection, sid, mode)
            authorization = consent(connection, item['participant_id'], mode)
            if not authorization['enabled']:
                raise HTTPException(403, 'workflow_consent_required_for_evidence_export')
            return dict(version=VERSION, session=item, audit=audit_chain(connection,sid), clinical_validation=False)

    app.include_router(router)
    # Keep participant onboarding inside the already account-scoped NC namespace.
    # Guard in participant.mount also supports hosts that mount it separately.
    import importlib.util
    import sys
    from pathlib import Path
    name = 'bainp_continuum_participant_v2'
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / 'participant' / 'backend.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    module.mount(app, store, authenticated, cognitive_router)
