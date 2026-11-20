"""NeuroContinuum: native BAINP orchestration, without scientific scoring or inference."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from uuid import UUID, uuid4

from fastapi import HTTPException

# Administrative changes do not invalidate immutable readiness snapshots.
# All other changed fields require review, including unknown future fields.
PROFILE_INFORMATION_FIELDS = {'display_name', 'age', 'birth_date', 'education_years', 'digital_familiarity'}
def vision_label_only_change(before, after):
    """A history label is not a change in demonstrated interaction ability."""
    return (isinstance(before.get('vision_limitation'), bool)
            and isinstance(after.get('vision_limitation'), bool)
            and before.get('can_see_and_respond') == after.get('can_see_and_respond') == 'yes'
            and before.get('vision_aid') == after.get('vision_aid')
            and after.get('vision_aid') in ('none', 'glasses'))

def readiness_changes(before, after):
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ['invalid_profile_snapshot']
    return sorted(k for k in set(before) | set(after)
                  if k not in PROFILE_INFORMATION_FIELDS and before.get(k) != after.get(k)
                  and not (k == 'vision_limitation' and vision_label_only_change(before, after)))

VERSION = 'neurocontinuum-native-v1.0.0'
POLICY = 'existing-access-fixed-cognition-v1'
TERMINAL = {'COMPLETED', 'CANCELLED'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS ncw_consents(
 participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL, revision INTEGER NOT NULL, enabled INTEGER NOT NULL,
 history_allowed INTEGER NOT NULL, assessment_allowed INTEGER NOT NULL,
 case_tracking INTEGER NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(participant_id,mode));
CREATE TABLE IF NOT EXISTS ncw_sessions(
 id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,checkin_id TEXT REFERENCES checkins(id) ON DELETE CASCADE,
 state TEXT NOT NULL,version INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 payload TEXT NOT NULL, UNIQUE(mode,checkin_id));
CREATE UNIQUE INDEX IF NOT EXISTS ncw_one_open ON ncw_sessions(participant_id,mode)
 WHERE state NOT IN ('COMPLETED','CANCELLED');
CREATE TABLE IF NOT EXISTS ncw_events(
 session_id TEXT NOT NULL REFERENCES ncw_sessions(id) ON DELETE CASCADE,
 sequence INTEGER NOT NULL,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,sha256 TEXT NOT NULL,
 PRIMARY KEY(session_id,sequence));
CREATE TABLE IF NOT EXISTS ncw_operations(
 operation_id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,request_hash TEXT NOT NULL,response TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ncw_observation_refs(
 id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,workflow_session_id TEXT NOT NULL REFERENCES ncw_sessions(id) ON DELETE CASCADE,
 source_attempt_id TEXT NOT NULL REFERENCES nc_attempts(id) ON DELETE CASCADE,
 source_hash TEXT NOT NULL,payload TEXT NOT NULL, UNIQUE(mode,participant_id,source_attempt_id,source_hash));
'''

def now():
    return datetime.now(timezone.utc).isoformat()

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return sha256(dump(value).encode()).hexdigest()

def deny(code, status=409):
    raise HTTPException(status, code)

def person(connection, pid, mode):
    row = connection.execute('SELECT * FROM participants WHERE id=? AND mode=?', (str(pid), mode)).fetchone()
    if row is None:
        deny('participant_not_found', 404)
    if not row['consent_at']:
        deny('source_storage_consent_missing')
    return row

def consent(connection, pid, mode):
    row = connection.execute('SELECT * FROM ncw_consents WHERE participant_id=? AND mode=?', (str(pid), mode)).fetchone()
    return dict(row) if row else dict(revision=0, enabled=0, history_allowed=0, assessment_allowed=0, case_tracking=0)

def session(connection, sid, mode):
    row = connection.execute('SELECT * FROM ncw_sessions WHERE id=? AND mode=?', (str(sid), mode)).fetchone()
    if row is None:
        deny('workflow_session_not_found', 404)
    person(connection, row['participant_id'], mode)
    return dict(row) | {'payload': json.loads(row['payload'])}

def replay(connection, op, pid, mode, request):
    row = connection.execute('SELECT * FROM ncw_operations WHERE operation_id=?', (str(op),)).fetchone()
    if row is None:
        return None
    if row['participant_id'] != str(pid) or row['mode'] != mode or row['request_hash'] != digest(request):
        deny('operation_key_conflict')
    return json.loads(row['response']) | {'replayed': True}

def remember(connection, op, pid, mode, request, response):
    connection.execute('INSERT INTO ncw_operations VALUES(?,?,?,?,?)',
                       (str(op), str(pid), mode, digest(request), dump(response)))
    return response

def append_event(connection, item, operation_id, action, before, reason, evidence=None):
    previous = connection.execute('SELECT sequence,sha256 FROM ncw_events WHERE session_id=? ORDER BY sequence DESC LIMIT 1', (item['id'],)).fetchone()
    sequence = previous['sequence'] + 1 if previous else 1
    previous_hash = previous['sha256'] if previous else 'GENESIS'
    event = dict(session_id=item['id'], participant_id=item['participant_id'], mode=item['mode'],
                 sequence=sequence, at=now(), actor='authenticated_local_operator', operation_id=str(operation_id),
                 action=action, from_state=before, to_state=item['state'], reason=reason,
                 version=VERSION, policy=POLICY, evidence=evidence or {}, previous_hash=previous_hash)
    connection.execute('INSERT INTO ncw_events VALUES(?,?,?,?,?)',
                       (item['id'], sequence, dump(event), previous_hash, digest(event)))

def save(connection, item):
    item['updated_at'] = now()
    connection.execute('UPDATE ncw_sessions SET state=?,version=?,updated_at=?,payload=? WHERE id=?',
                       (item['state'], item['version'], item['updated_at'], dump(item['payload']), item['id']))

def audit_chain(connection, sid):
    previous = 'GENESIS'
    events = []
    valid = True
    for row in connection.execute('SELECT * FROM ncw_events WHERE session_id=? ORDER BY sequence', (str(sid),)):
        event = json.loads(row['payload'])
        valid = valid and event['sequence'] == len(events)+1 and row['previous_hash'] == previous and event['previous_hash'] == previous and row['sha256'] == digest(event)
        previous = row['sha256']
        events.append(event | {'sha256': previous})
    return dict(valid=bool(valid), events=events, head=previous,
                limitation='Local hash linkage; no external signature or tamper-proof guarantee.')

def source_results(connection, item):
    native = connection.execute('SELECT * FROM nc_sessions WHERE checkin_id=? AND participant_id=? AND mode=?',
                                (item['checkin_id'], item['participant_id'], item['mode'])).fetchone()
    if native is None:
        return None, []
    native = dict(native)
    # The native battery can be explicitly closed with available incomplete evidence.
    # That is not equivalent to an in-progress task or a completed battery.
    closure_table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nc_session_closures'").fetchone()
    if closure_table:
        closure = connection.execute('SELECT reason FROM nc_session_closures WHERE session_id=?',(native['id'],)).fetchone()
        if closure:
            native['closed_incomplete_reason'] = closure['reason']
    attempts = []
    for row in connection.execute('SELECT * FROM nc_attempts WHERE session_id=? ORDER BY task,id', (native['id'],)):
        summary = json.loads(row['summary']) if row['summary'] else None
        reference = dict(attempt_id=row['id'], session_id=row['session_id'], task=row['task'],
                         status=row['status'], finished_at=row['finished_at'], protocol=native['protocol'],
                         form=native['form'], summary=summary)
        reference['source_hash'] = digest(reference)
        attempts.append(reference)
    return dict(native), attempts

def native_status(native, attempts):
    if not native:
        return 'not_started'
    manifest = json.loads(native['manifest'])
    order = manifest.get('_meta', {}).get('order') or [task for task in manifest if task != '_meta']
    if not order:
        deny('unsupported_cognitive_manifest')
    by = {a['task']: a for a in attempts}
    if native.get('closed_incomplete_reason'):
        return 'interrupted'
    if any(a['status'] == 'interrupted' for a in attempts):
        return 'interrupted'
    return 'completed' if all(task in by and by[task]['status'] == 'completed' for task in order) else 'in_progress'

def reference_quality(attempt):
    summary = attempt['summary']
    if attempt['status'] != 'completed' or not attempt['finished_at'] or not isinstance(summary, dict):
        return 'QUARANTINED', ['SOURCE_RESULT_INCOMPLETE']
    flags = summary.get('quality_flags')
    if not isinstance(flags, list) or any(not isinstance(x, str) for x in flags):
        return 'QUARANTINED', ['QUALITY_CONTRACT_UNAVAILABLE']
    if flags:
        return 'QUARANTINED', flags
    return 'SOURCE_QC_CLEAR_DESCRIPTIVE_ONLY', []

class Engine:
    def __init__(self, store, ports):
        self.store, self.ports = store, ports
        with store.connect() as connection:
            connection.executescript(SCHEMA)

    def configure(self, pid, mode, payload):
        request = {'kind': 'consent', **payload}
        with self.store.connect(True) as connection:
            person(connection, pid, mode)
            old = replay(connection, payload['operation_id'], pid, mode, request)
            if old:
                return old
            current = consent(connection, pid, mode)
            if current['revision'] != payload['expected_revision']:
                deny('workflow_consent_changed_refresh')
            # bainp_no_change_consent_v1: preserve evidence/session for unchanged scopes.
            scopes = ('enabled', 'history_allowed', 'assessment_allowed', 'case_tracking')
            if current['revision'] > 0 and all(bool(current[key]) == payload[key] for key in scopes):
                return remember(connection, payload['operation_id'], pid, mode, request,
                                dict(revision=current['revision'], replayed=False))
            revision = current['revision'] + 1
            connection.execute('INSERT INTO ncw_consents VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(participant_id,mode) DO UPDATE SET revision=excluded.revision,enabled=excluded.enabled,history_allowed=excluded.history_allowed,assessment_allowed=excluded.assessment_allowed,case_tracking=excluded.case_tracking,updated_at=excluded.updated_at',
                               (str(pid), mode, revision, int(payload['enabled']), int(payload['history_allowed']), int(payload['assessment_allowed']), int(payload['case_tracking']), now()))
            # Every scope change forces explicit revalidation. Withdrawal cannot be bypassed by an old session.
            for row in connection.execute("SELECT id FROM ncw_sessions WHERE participant_id=? AND mode=? AND state NOT IN ('COMPLETED','CANCELLED')", (str(pid), mode)).fetchall():
                item = session(connection, row['id'], mode)
                before = item['state']
                item['state'] = 'BLOCKED'
                item['version'] += 1
                item['payload']['reason'] = 'WORKFLOW_CONSENT_CHANGED'
                item['payload']['safety'] = None
                item['payload']['recommendation'] = None
                item['payload']['history'] = None
                save(connection, item)
                append_event(connection, item, payload['operation_id'], 'consent_changed', before, 'WORKFLOW_CONSENT_CHANGED', {'consent_revision': revision})
            return remember(connection, payload['operation_id'], pid, mode, request, dict(revision=revision, replayed=False))

    def start(self, pid, mode, payload):
        request = {'kind': 'start', **payload}
        with self.store.connect(True) as connection:
            person(connection, pid, mode)
            old = replay(connection, payload['operation_id'], pid, mode, request)
            if old:
                return old
            authorization = consent(connection, pid, mode)
            if not authorization['enabled']:
                deny('explicit_workflow_consent_required')
            existing = connection.execute("SELECT id FROM ncw_sessions WHERE participant_id=? AND mode=? AND state NOT IN ('COMPLETED','CANCELLED')", (str(pid), mode)).fetchone()
            if existing:
                return remember(connection, payload['operation_id'], pid, mode, request, dict(session_id=existing['id'], resumed_existing=True, replayed=False))
            cid = payload.get('checkin_id')
            if not cid:
                deny('new_completed_checkin_required', 422)
            check = connection.execute('SELECT participant_id,mode,status,created_at FROM checkins WHERE id=?', (cid,)).fetchone()
            if check is None or check['participant_id'] != str(pid) or check['mode'] != mode:
                deny('checkin_identity_mismatch', 422)
            if check['status'] != 'completed':
                deny('checkin_preparation_incomplete', 409)
            prior = connection.execute('SELECT id FROM ncw_sessions WHERE mode=? AND checkin_id=?', (mode, cid)).fetchone()
            if prior:
                deny('checkin_already_linked_create_fresh_preparation')
            last = connection.execute('SELECT updated_at,payload FROM ncw_sessions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1', (str(pid),mode)).fetchone()
            previous_incomplete = bool(last and (json.loads(last['payload']).get('summary') or {}).get('disposition') == 'INCOMPLETE_VISIT')
            acknowledged = payload.get('acknowledge_prior_quality') is True
            if previous_incomplete:
                if not acknowledged:
                    deny('confirm_prior_incomplete_quality_before_new_visit')
                if check['created_at'] <= last['updated_at']:
                    deny('new_preparation_after_prior_incomplete_visit_required')
            elif acknowledged:
                deny('quality_acknowledgement_not_applicable', 422)
            stamp = now()
            body = dict(protocol=POLICY, reason='SESSION_CREATED', consent_revision=authorization['revision'],
                        history=None, safety=None, recommendation=None, result=None, summary=None, retries=0,
                        independent_reassessment=acknowledged, preceding_visit_incomplete=previous_incomplete)
            item = dict(id=payload['session_id'], participant_id=str(pid), mode=mode, checkin_id=cid,
                        state='CREATED', version=1, created_at=stamp, updated_at=stamp, payload=body)
            if connection.execute('SELECT 1 FROM ncw_sessions WHERE id=?', (item['id'],)).fetchone():
                deny('session_key_conflict')
            connection.execute('INSERT INTO ncw_sessions VALUES(?,?,?,?,?,?,?,?,?)',
                               (item['id'], str(pid), mode, cid, 'CREATED', 1, stamp, stamp, dump(body)))
            append_event(connection, item, payload['operation_id'], 'start', None, 'SESSION_CREATED')
            return remember(connection, payload['operation_id'], pid, mode, request, dict(session_id=item['id'], replayed=False))

    def preflight(self, sid, mode, payload):
        with self.store.connect() as connection:
            item = session(connection, sid, mode)
            old = replay(connection, payload['operation_id'], item['participant_id'], mode, {'kind': 'command', **payload})
            if old:
                return item, {}, old
            if item['version'] != payload['expected_version']:
                deny('workflow_session_changed_refresh')
            p = person(connection, item['participant_id'], mode)
            authorization = consent(connection, p['id'], mode)
            context = dict(profile_revision=p['revision'], consent_revision=authorization['revision'])
        # Read-only module calls happen before the write transaction. No nested write lock or model invocation.
        action = payload['action']
        try:
            if action in ('advance', 'resume', 'retry', 'sync') and authorization['enabled']:
                if item['checkin_id']:
                    context['access'] = self.ports.access(item['checkin_id'], mode)
                if item['state'] == 'AUTHORIZED' and action in ('advance', 'retry'):
                    context['history'] = self.ports.history(item['participant_id'], mode) if authorization['history_allowed'] else {'state': 'WITHHELD_BY_CONSENT', 'observations': [], 'sources': {}}
                if item['state'] == 'VALIDATING' or action == 'resume':
                    context['guard_loaded'] = self.ports.guard_ready()
        except HTTPException as error:
            if error.status_code in (401, 403, 404):
                raise
            context['module_error'] = 'DEPENDENCY_UNAVAILABLE'
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            context['module_error'] = 'DEPENDENCY_UNAVAILABLE'
        return item, context, None

    def command(self, sid, mode, payload):
        initial, context, old = self.preflight(sid, mode, payload)
        if old:
            return old
        request = {'kind': 'command', **payload}
        with self.store.connect(True) as connection:
            item = session(connection, sid, mode)
            old = replay(connection, payload['operation_id'], item['participant_id'], mode, request)
            if old:
                return old
            if item['version'] != payload['expected_version']:
                deny('workflow_session_changed_refresh')
            p = person(connection, item['participant_id'], mode)
            authorization = consent(connection, p['id'], mode)
            action, before, body = payload['action'], item['state'], item['payload']
            reason = action.upper()
            if context.get('profile_revision') != p['revision'] or context.get('consent_revision') != authorization['revision']:
                deny('context_changed_revalidate')
            if action == 'safety':
                safety = self.ports.urgent(payload['signs'])
                body['safety'] = safety
                if safety.get('state') != 'escalate' and payload['signs']:
                    deny('guard_escalation_contract_failed', 503)
                if payload['signs']:
                    item['state'] = 'COMPLETED'
                    body['summary'] = dict(accepted_references=0, quarantined_references=0, disposition='SAFETY_PATH', delivery='NO_EXTERNAL_CONTACT')
                    reason = 'GUARD_ESCALATION_DIGITAL_SESSION_ENDED'
                else:
                    reason = 'NO_SELECTED_SIGN_DOES_NOT_RULE_OUT_EMERGENCY'
            elif action == 'request_review':
                if not authorization['enabled'] or not authorization['case_tracking']:
                    deny('explicit_case_tracking_consent_required')
                body['care_case_id'] = self.create_case(connection, item, reason='operator_requested_workflow_review')
                reason = 'EXISTING_CARELOOP_CASE_RECORDED_NO_EXTERNAL_DELIVERY'
            elif before in TERMINAL:
                deny('workflow_session_ended')
            elif action == 'cancel':
                item['state'] = 'CANCELLED'
                reason = 'WORKFLOW_CANCELLED_SOURCE_ASSESSMENT_UNCHANGED'
            elif action == 'finish_incomplete':
                if before not in ('ASSESSING', 'BLOCKED'):
                    deny('incomplete_closure_requires_assessment_or_blocked_state')
                if (body.get('safety') or {}).get('state') == 'escalate' or body.get('reason') == 'NEUROQUEST_URGENT_OVERRIDE':
                    deny('urgent_safety_restriction_cannot_be_cleared')
                if before == 'BLOCKED' and body.get('reason') not in (
                        'NATIVE_ASSESSMENT_INTERRUPTED_NO_COMPLETION_INFERRED',
                        'NEUROQUEST_REPEAT', 'NEUROQUEST_TARGETED', 'NEUROQUEST_ABSTAIN'):
                    deny('blocked_workflow_requires_original_issue_review')
                native, attempts = source_results(connection, item)
                if any(a['status'] == 'running' for a in attempts):
                    deny('native_attempt_running_finish_or_abandon_in_neurocognition_first')
                if native and native_status(native, attempts) == 'completed':
                    deny('native_results_complete_synchronize_instead')
                body['summary'] = dict(
                    disposition='INCOMPLETE_VISIT', clinical_validation=False,
                    accepted_references=0, quarantined_references=sum(a['status'] != 'completed' for a in attempts),
                    source_session_id=native['id'] if native else None,
                    completed_task_attempts=sum(a['status'] == 'completed' for a in attempts),
                    interrupted_task_attempts=sum(a['status'] == 'interrupted' for a in attempts),
                    note='The guided visit ended without a valid completed battery. Original measurements and quality flags remain unchanged. No clinical inference is made.')
                item['state'] = 'CANCELLED'
                reason = 'INCOMPLETE_VISIT_CLOSED_EVIDENCE_PRESERVED'
            elif not authorization['enabled'] or not authorization['assessment_allowed']:
                item['state'] = 'BLOCKED'
                reason = 'APPLICABLE_WORKFLOW_CONSENT_REQUIRED'
            elif action == 'pause':
                if before in ('PAUSED', 'FAILED', 'BLOCKED'):
                    deny('workflow_transition_not_allowed')
                body['paused_from'] = before
                item['state'] = 'PAUSED'
            elif action == 'resume':
                if before not in ('PAUSED', 'BLOCKED'):
                    deny('workflow_transition_not_allowed')
                body['access_reasons'] = []
                body['safety'] = None
                body['recommendation'] = None
                body['history'] = None
                body['consent_revision'] = authorization['revision']
                item['state'] = 'AUTHORIZED'
                reason = 'RESUMED_REVALIDATION_REQUIRED'
            elif action == 'retry':
                if before != 'FAILED' or body['retries'] >= 3:
                    deny('retry_not_allowed_or_exhausted')
                body['retries'] += 1
                item['state'] = body.get('failed_from', 'AUTHORIZED')
                reason = 'RETRY_SCHEDULED_NO_FALSE_SUCCESS'
            elif context.get('module_error'):
                body['failed_from'] = before
                item['state'] = 'FAILED'
                reason = context['module_error']
            elif action in ('advance', 'sync'):
                if action == 'sync' and before != 'ASSESSING':
                    deny('sync_only_while_assessing')
                access = context.get('access')
                # Recheck the authoritative check-in inside the same write snapshot.
                access_reasons = self.access_reasons(connection, item, p, access)
                body['access_reasons'] = access_reasons
                if access_reasons:
                    item['state'] = 'BLOCKED'
                    reason = 'NEUROACCESS_HOLD'
                    body['access_reasons'] = access_reasons
                elif before == 'CREATED':
                    item['state'] = 'AUTHORIZED'
                    body['profile_revision'] = p['revision']
                    body['consent_revision'] = authorization['revision']
                    reason = 'EXISTING_NEUROACCESS_CONTEXT_AUTHORIZED'
                elif before == 'AUTHORIZED':
                    body['history'] = context.get('history')
                    item['state'] = 'VALIDATING'
                    reason = 'PARTICIPANT_SOURCE_REFERENCES_RETRIEVED'
                elif before == 'VALIDATING':
                    if not context.get('guard_loaded'):
                        body['failed_from'] = before
                        item['state'] = 'FAILED'
                        reason = 'NEUROGUARD_UNAVAILABLE_FAIL_CLOSED'
                    else:
                        verdict = self.ports.workflow_decision(dict(participant_id=p['id'],source_participant_id=p['id'],
                            mode=mode,source_mode=item['mode'],checkin_id=item['checkin_id'],
                            profile_revision=p['revision'],consent_revision=authorization['revision'],
                            monitoring_consent=bool(authorization['enabled']),assessment_consent=bool(authorization['assessment_allowed']),
                            native_guard_available=True,access_reasons=access_reasons))
                        body['safety'] = verdict
                        if verdict.get('state') != 'workflow_permitted' or 'existing_neurocognition' not in verdict.get('allowed_actions',[]):
                            item['state'] = 'BLOCKED'
                            reason = 'INDEPENDENT_WORKFLOW_GUARD_ABSTAINED'
                        else:
                            item['state'] = 'AWAITING_ACTION'
                            reason = 'WORKFLOW_GATE_PASSED_NO_CLINICAL_CLEARANCE'
                elif before == 'AWAITING_ACTION':
                    if 'existing_neurocognition' not in (body.get('safety') or {}).get('allowed_actions', []):
                        deny('safety_permission_missing')
                    # neuroquest_native_selection_v1
                    if hasattr(self.ports,'quest_recommend'):
                        recommendation=self.ports.quest_recommend(connection,item)
                        body['recommendation']=recommendation
                        if recommendation['executable']:
                            item['state']='ASSESSING'
                        elif recommendation['action'] in ('monitor','professional_review','urgent_guidance'):
                            item['state']='COMPLETED'
                            body['summary']=dict(disposition=recommendation['action'],accepted_references=0,quarantined_references=0,clinical_validation=False)
                            if recommendation['action']=='professional_review' and authorization['case_tracking']:
                                body['care_case_id']=self.create_case(connection,item,'operator_requested_workflow_review')
                        else:
                            item['state']='BLOCKED'
                        body['reason']='NEUROQUEST_'+recommendation['action'].upper()
                        item['version']+=1
                        save(connection,item)
                        append_event(connection,item,payload['operation_id'],action,before,body['reason'],dict(decision_id=recommendation['decision_id'],decision_sha256=recommendation['sha256'],policy=recommendation['policy']))
                        return remember(connection,payload['operation_id'],item['participant_id'],mode,request,dict(session_id=item['id'],state=item['state'],version=item['version'],reason=body['reason']))
                    body['recommendation'] = dict(engine='NeuroCognition X', policy=POLICY,
                        reason='Fixed existing assessment pathway; native task catalogue, diagnostics and selection remain authoritative.',
                        url=self.ports.cognition_url(item['checkin_id'], mode), clinical_optimization=False)
                    item['state'] = 'ASSESSING'
                    reason = 'EXISTING_ASSESSMENT_PATHWAY_READY'
                elif before == 'ASSESSING':
                    native, attempts = source_results(connection, item)
                    state = native_status(native, attempts)
                    body['assessment_status'] = state
                    if state == 'completed':
                        body['result'] = dict(native_session_id=native['id'], source_hash=digest(attempts), attempts=attempts)
                        item['state'] = 'RECORDING'
                        reason = 'NATIVE_RESULTS_RECEIVED_PENDING_VALIDITY_CHECK'
                    elif state == 'interrupted':
                        item['state'] = 'BLOCKED'
                        reason = 'NATIVE_ASSESSMENT_INTERRUPTED_NO_COMPLETION_INFERRED'
                    else:
                        reason = 'NATIVE_ASSESSMENT_' + state.upper()
                elif before == 'RECORDING':
                    native, attempts = source_results(connection, item)
                    saved = body.get('result') or {}
                    if not native or native['id'] != saved.get('native_session_id') or digest(attempts) != saved.get('source_hash'):
                        deny('native_result_changed_sync_again')
                    accepted, quarantined = self.persist_references(connection, item, attempts)
                    if quarantined and authorization['case_tracking']:
                        body['care_case_id'] = self.create_case(connection, item, 'source_quality_review_requested')
                    body['summary'] = dict(accepted_references=accepted, quarantined_references=quarantined,
                        disposition='DESCRIPTIVE_REFERENCES_ONLY', source_session_id=native['id'],
                        care_case_id=body.get('care_case_id'), clinical_validation=False,
                        note='Original NeuroCognition measurements and quality flags are unchanged. No diagnosis or prediction.')
                    item['state'] = 'COMPLETED'
                    reason = 'WORKFLOW_COMPLETED_REFERENCES_PRESERVED'
                else:
                    deny('workflow_transition_not_allowed')
            else:
                deny('workflow_action_not_supported', 422)
            body['reason'] = reason
            item['version'] += 1
            save(connection, item)
            append_event(connection, item, payload['operation_id'], action, before, reason,
                         dict(profile_revision=p['revision'], consent_revision=authorization['revision'],
                              native_session_id=(body.get('result') or {}).get('native_session_id'),
                              source_hash=(body.get('result') or {}).get('source_hash'),
                              care_case_id=body.get('care_case_id'), safety=body.get('safety')))
            return remember(connection, payload['operation_id'], p['id'], mode, request,
                            dict(session_id=item['id'], state=item['state'], version=item['version'], reason=reason, replayed=False))

    def prepare_recovery(self, sid, mode, payload):
        from recovery import ticket
        import battery
        with self.store.connect(True) as c:
            item=session(c,sid,mode);pid=item['participant_id']
            request={'kind':'task_recovery',**payload}
            old=replay(c,payload['operation_id'],pid,mode,request)
            if old:return old
            if item['version']!=payload['expected_version']:deny('workflow_session_changed_refresh')
            if item['state']!='BLOCKED':deny('recovery_requires_blocked_workflow')
            auth=consent(c,pid,mode)
            if not all(auth.get(k) for k in ('enabled','history_allowed','assessment_allowed')):deny('recovery_consent_required',403)
            if payload['correction_confirmed'] is not True:deny('correction_confirmation_required',422)
            # Recompute against the original source; the client cannot choose arbitrary tasks.
            decision=self.ports.quest_recommend(c,item)
            if decision['action']!='repeat' or decision['executable'] or not decision.get('quality_issues'):deny('no_supported_quality_recovery')
            tasks=set(decision['task_ids'])
            if not tasks or not tasks.issubset(set(battery.ORDER)):deny('recovery_task_not_supported')
            if tasks & {'C01','C02'}:tasks.update(('C01','C02'))
            order=[t for t in battery.ORDER if t in tasks]
            cid=payload['checkin_id']
            row=c.execute('SELECT * FROM checkins WHERE id=? AND participant_id=? AND mode=?',(cid,pid,mode)).fetchone()
            if not row:deny('recovery_checkin_not_found',404)
            if cid==item['checkin_id'] or c.execute('SELECT 1 FROM nc_sessions WHERE checkin_id=?',(cid,)).fetchone() or ticket(c,cid,mode):deny('new_unused_preparation_required')
            if c.execute('SELECT 1 FROM ncw_sessions WHERE checkin_id=?',(cid,)).fetchone():deny('preparation_already_linked')
            p=person(c,pid,mode)
            holds=self.access_reasons(c,{**item,'checkin_id':cid},p,None)
            if holds:deny('recovery_preparation_required:'+','.join(holds))
            if row['created_at']<=item['created_at']:deny('complete_fresh_preparation_for_recovery')
            sources=[q['source_id'] for q in decision['quality_issues'] if q.get('source_id')]
            if len(sources)!=len(decision['quality_issues']):deny('recovery_source_identity_missing')
            # Bounded research recovery: no hidden infinite repeat cycle.
            count=c.execute('SELECT count(*) FROM nc_recoveries WHERE workflow_id=?',(sid,)).fetchone()[0]
            if count>=1:deny('recovery_limit_review_required')
            rid=payload['operation_id'];stamp=now()
            data=dict(order=order,source_attempts=sources,correction=payload['correction'],previous_checkin_id=item['checkin_id'],consent_revision=auth['revision'],profile_revision=p['revision'],decision_id=decision['decision_id'])
            c.execute('INSERT INTO nc_recoveries VALUES(?,?,?,?,?,?,?)',(rid,pid,mode,sid,cid,dump(data),stamp))
            before=item['state'];body=item['payload'];body['recovery_id']=rid;body['recommendation']=None;body['access_reasons']=[];body['result']=None;body['history']=None
            item['checkin_id']=cid;item['state']='AUTHORIZED';item['version']+=1
            c.execute('UPDATE ncw_sessions SET checkin_id=? WHERE id=?',(cid,sid))
            body['reason']='RECOVERY_PREPARED_REVALIDATION_REQUIRED';save(c,item)
            append_event(c,item,payload['operation_id'],'prepare_recovery',before,body['reason'],data)
            return remember(c,payload['operation_id'],pid,mode,request,dict(session_id=sid,state=item['state'],version=item['version'],recovery_id=rid,task_ids=order))

    def access_reasons(self, connection, item, p, preflight):
        if not item['checkin_id']:
            return ['CREATE_AND_SELECT_A_NEUROACCESS_CHECKIN']
        row = connection.execute('SELECT * FROM checkins WHERE id=? AND participant_id=? AND mode=?',
                                 (item['checkin_id'], p['id'], item['mode'])).fetchone()
        if row is None:
            return ['CHECKIN_IDENTITY_UNAVAILABLE']
        changed = readiness_changes(json.loads(row['profile']), json.loads(p['profile']))
        if changed:
            return ['PROFILE_CHANGED_NEW_CHECKIN_REQUIRED'] + ['READINESS_FIELD_CHANGED:' + key for key in changed]
        gate = json.loads(row['gate'])
        conditions = json.loads(row['conditions'])
        reasons = list(gate.get('reason_codes') or [])
        if gate.get('practice_allowed') is not True or conditions.get('acute_warning') != 'no' or conditions.get('instructions_understood') is not True:
            reasons.append('EXISTING_ACCESS_GATE_HOLD')
        if row['status'] != 'completed' or not row['practice']:
            reasons.append('NEUROACCESS_PREPARATION_INCOMPLETE')
        if preflight:
            if preflight.get('participant_id') != p['id']:
                deny('native_access_identity_mismatch', 503)
            reasons += list(preflight.get('reasons') or [])
        return sorted(set(reasons))

    def persist_references(self, connection, item, attempts):
        accepted = quarantined = 0
        for attempt in attempts:
            quality, flags = reference_quality(attempt)
            if quality == 'QUARANTINED':
                quarantined += 1
                continue
            # Native NeuroGuard verifies exact-source numeric claim release, not clinical validity.
            decisions = []
            for key, value in attempt['summary'].items():
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                    continue
                node_id = f"{attempt['attempt_id']}:{key}"
                unit = 'ms' if key.endswith('_ms') else None
                node = dict(type='direct_observation', claim='measurement', eligible=True, value=value,
                            unit=unit, statement='Recorded source summary; clinical validation not established.')
                decision = self.ports.check_claim('measurement', node_id, {node_id: node}, value, node['unit'])
                if decision.get('state') != 'accept':
                    deny('native_neuroguard_rejected_source_envelope', 503)
                decisions.append(dict(metric=key, state=decision['state'], policy_version=decision.get('policy_version')))
            reference = dict(source='NeuroCognition X', participant_id=item['participant_id'], mode=item['mode'],
                workflow_session_id=item['id'], source_attempt_id=attempt['attempt_id'], source_session_id=attempt['session_id'],
                source_hash=attempt['source_hash'], task=attempt['task'], observed_at=attempt['finished_at'],
                protocol=attempt['protocol'], form=attempt['form'], quality=quality, flags=flags,
                permitted_use='descriptive_research_workflow', clinical_validation=False, guard_decisions=decisions)
            connection.execute('INSERT OR IGNORE INTO ncw_observation_refs VALUES(?,?,?,?,?,?,?)',
                (str(uuid4()), item['participant_id'], item['mode'], item['id'], attempt['attempt_id'], attempt['source_hash'], dump(reference)))
            accepted += 1
        return accepted, quarantined

    def create_case(self, connection, item, reason):
        if not self.ports.cases_ready():
            deny('careloop_adapter_unavailable', 503)
        existing = item['payload'].get('care_case_id')
        if existing:
            case = self.ports.case_select(connection, item['mode'], item['participant_id'], existing)
            if case['state'] == 'withdrawn':
                deny('care_case_withdrawn_no_automatic_reopening')
            return existing
        case_id = str(uuid4())
        payload = dict(case_id=case_id, category='memory', concern='NeuroContinuum workflow review: '+reason.replace('_', ' ')+'. Source findings are descriptive and do not establish a diagnosis.',
                       screening='unsure', signs=[], consent=True, share_with_twin=False)
        case = self.ports.case_intake(connection, item['mode'], item['participant_id'], payload, 'professional_review_suggested')
        if case['state'] == 'recorded':
            row = self.ports.case_select(connection, item['mode'], item['participant_id'], case_id)
            self.ports.case_transition(connection, row, dict(operation_id=str(uuid4()), expected_version=case['version'],
                action='request_review', note='Review requested by authorized local workflow. No external delivery is asserted.', reference=None, due_on=None))
        return case_id

def summary_for_twin(store, pid, mode):
    with store.connect() as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='ncw_sessions'").fetchone():
            return dict(state='adapter_not_initialized', sessions=[])
        authorization = consent(connection, pid, mode)
        if not authorization['enabled'] or not authorization['history_allowed']:
            return dict(state='withheld_by_workflow_consent', sessions=[])
        rows = connection.execute('SELECT id,state,version,updated_at FROM ncw_sessions WHERE participant_id=? AND mode=? ORDER BY updated_at DESC LIMIT 20', (str(pid), mode)).fetchall()
        return dict(state='workflow_history_available', version=VERSION, sessions=[dict(row) for row in rows],
                    interpretation='Workflow state markers only. No new clinical measurement, disease score or model retraining.')
