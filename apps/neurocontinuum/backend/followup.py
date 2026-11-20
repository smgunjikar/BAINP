"""Read-only, permission-scoped post-assessment evidence summary.

No scores, diagnosis, clinical trends, new visits or CareLoop transitions are
created here. This module reconciles native source records and gives NeuroQuest
only operational quality and existing review status.
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any
from fastapi import HTTPException

from bainp_continuum_engine import consent, person, reference_quality, source_results, native_status

VERSION = 'neurocontinuum-post-assessment-v1.0'


def _table_exists(connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _safe_json(raw: Any) -> dict:
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _recommend(context: dict) -> dict:
    module = sys.modules.get('bainp_quest_engine')
    fn = getattr(module, 'post_assessment_action', None) if module else None
    if not callable(fn):
        return dict(code='DECISION_ENGINE_UNAVAILABLE', title='Review your saved evidence',
                    reason='NeuroQuest is unavailable; no automatic assessment or monitoring decision can be made.',
                    destination='/neurocontinuum', executable=False,
                    policy='neuroquest-unavailable', clinical_validation=False)
    return fn(context)


def _existing_safety_hold(connection, pid: str, mode: str) -> bool:
    for row in connection.execute(
        'SELECT payload FROM ncw_sessions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 100',
        (pid, mode),
    ):
        data = _safe_json(row['payload'])
        if (data.get('safety') or {}).get('state') == 'escalate' or data.get('reason') == 'NEUROQUEST_URGENT_OVERRIDE':
            return True
    return False


def _existing_concern(connection, pid: str, mode: str) -> str:
    if not _table_exists(connection, 'participant_onboarding_v1'):
        return 'unknown'
    row = connection.execute(
        'SELECT answers FROM participant_onboarding_v1 WHERE participant_id=? AND mode=?', (pid, mode)
    ).fetchone()
    if not row:
        return 'unknown'
    concern = (_safe_json(row['answers']).get('concerns') or {}).get('everyday_changes')
    return concern if concern in ('yes', 'no', 'prefer_not_to_answer') else 'unknown'


def _review_case(connection, pid: str, mode: str, allowed: bool) -> dict:
    result = dict(state='withheld_by_permission' if not allowed else 'no_record',
                  local_record_only=True, external_delivery_confirmed=False)
    if not allowed or not _table_exists(connection, 'careloop_cases'):
        return result
    row = connection.execute(
        'SELECT id,state,updated_at FROM careloop_cases '
        'WHERE participant_id=? AND mode=? ORDER BY updated_at DESC,id DESC LIMIT 1',
        (pid, mode),
    ).fetchone()
    if row:
        result.update(state=row['state'], case_id=row['id'], updated_at=row['updated_at'])
    return result


def _camera(connection, pid: str, mode: str, native_id: str | None, attempt_ids: set[str]) -> dict:
    base = dict(state='not_configured', linked_batches=0, backend_confirmed_samples=0,
                single_face_samples=0, participant_unlinked_batches=0,
                rejected_linkage_batches=0, integrity_failures=0,
                valid_time_alignment=False, clinically_interpretable=False,
                note='Camera observations are experimental. Recorded samples do not establish continuous coverage, attention or diagnosis.')
    if not (_table_exists(connection, 'ncx3_permissions') and _table_exists(connection, 'ncx3_records')):
        return base
    permission_row = connection.execute(
        'SELECT payload FROM ncx3_permissions WHERE participant_id=? AND mode=?', (pid, mode)
    ).fetchone()
    permission = _safe_json(permission_row['payload']) if permission_row else {}
    if permission.get('camera') is not True:
        base['state'] = 'withheld_by_camera_permission'
        return base
    if permission.get('cross_engine') is not True:
        base['state'] = 'withheld_by_cross_engine_permission'
        return base
    base['state'] = 'no_linked_camera_records' if native_id else 'no_native_assessment_to_link'
    for row in connection.execute(
        "SELECT id, payload, sha256 FROM ncx3_records WHERE participant_id=? AND mode=? AND kind='camera' "
        'ORDER BY created_at DESC,id DESC LIMIT 200', (pid, mode)
    ):
        # Reject corrupt records rather than displaying saved measurements as verified.
        if hashlib.sha256(row['payload'].encode('utf-8')).hexdigest() != row['sha256']:
            base['integrity_failures'] += 1
            continue
        stored = _safe_json(row['payload'])
        data = stored.get('data') if isinstance(stored.get('data'), dict) else {}
        result = stored.get('result') if isinstance(stored.get('result'), dict) else {}
        session_id = data.get('session_id')
        attempt_id = data.get('attempt_id')
        if not native_id or session_id != native_id:
            base['participant_unlinked_batches'] += 1
            continue
        if attempt_id and attempt_id not in attempt_ids:
            base['rejected_linkage_batches'] += 1
            continue
        samples, single = result.get('samples'), result.get('single_face_samples')
        if not (type(samples) is int and type(single) is int and 0 <= single <= samples):
            base['integrity_failures'] += 1
            continue
        base['linked_batches'] += 1
        base['backend_confirmed_samples'] += samples
        base['single_face_samples'] += single
    if base['linked_batches']:
        base['state'] = 'linked_derived_camera_records'
    return base


def build(connection, pid: str, mode: str) -> dict:
    """Reconcile one most-recent workflow with its real native source session."""
    person(connection, pid, mode)  # Enforces exact participant ownership and existing source-storage consent.
    authorization = consent(connection, pid, mode)
    result = dict(version=VERSION, participant_id=pid, mode=mode,
                  state='withheld_by_workflow_permission', workflow=None,
                  cognitive=None, camera=dict(state='withheld_by_workflow_permission'),
                  neurotwin=dict(state='withheld_by_workflow_permission', inference_executed=False),
                  careloop=dict(state='withheld_by_workflow_permission'),
                  next_action=None,
                  limitation='Research record review only. Workflow completion is not clinical validation.')
    if not (authorization['enabled'] and authorization['history_allowed']):
        result['next_action'] = _recommend(dict(safety_hold=False, permission_missing=True))
        return result
    safety = _existing_safety_hold(connection, pid, mode)
    case = _review_case(connection, pid, mode, bool(authorization['case_tracking']))
    concern = _existing_concern(connection, pid, mode)
    result['careloop'] = case
    row = connection.execute(
        'SELECT * FROM ncw_sessions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1',
        (pid, mode),
    ).fetchone()
    if row is None:
        result['state'] = 'no_workflow_visit'
        result['cognitive'] = dict(state='not_assessed', accepted=0, quarantined=0, tasks=[], native_status='not_started')
        result['camera'] = _camera(connection, pid, mode, None, set())
        result['neurotwin'] = dict(state='no_cognitive_references', eligible_descriptive_references=0,
                                  inference_executed=False, clinical_comparability_established=False)
        result['next_action'] = _recommend(dict(safety_hold=safety, permission_missing=False,
            concern=concern, case_state=case['state'], workflow_state=None, native_status='not_started',
            accepted=0, quarantined=0))
        return result
    item = dict(row) | {'payload': _safe_json(row['payload'])}
    native, attempts = source_results(connection, item)
    native_id = native['id'] if native else None
    disposition = (item['payload'].get('summary') or {}).get('disposition')
    result['workflow'] = dict(session_id=item['id'], state=item['state'],
                              disposition=disposition, source_session_id=native_id,
                              updated_at=item['updated_at'])
    try:
        source_status = native_status(native, attempts)
    except (ValueError, KeyError, TypeError, HTTPException):
        source_status = 'source_contract_unavailable'
    accepted = quarantined = 0
    tasks = []
    for attempt in attempts:
        quality, flags = reference_quality(attempt)
        if quality == 'QUARANTINED':
            quarantined += 1
        else:
            accepted += 1
        tasks.append(dict(task=attempt['task'], attempt_id=attempt['attempt_id'],
                          status=attempt['status'], quality=quality, flags=flags,
                          source_hash=attempt['source_hash']))
    reported = item['payload'].get('summary') or {}
    reported_accepted, reported_quarantined = reported.get('accepted_references'), reported.get('quarantined_references')
    # Incomplete closure can count only interrupted tasks; its legacy numbers are
    # not necessarily equivalent to a full source-quality audit.
    counts_match = (reported_accepted == accepted and reported_quarantined == quarantined) if item['state'] == 'COMPLETED' and reported_accepted is not None else None
    result['state'] = 'source_review_available'
    result['cognitive'] = dict(native_status=source_status, protocol=native.get('protocol') if native else None,
        form=native.get('form') if native else None, accepted=accepted, quarantined=quarantined,
        tasks=tasks, workflow_counts_match_source=counts_match,
        explanation='Quality-clear values are descriptive only; quarantined attempts are not interpreted or silently repaired.')
    result['camera'] = _camera(connection, pid, mode, native_id,
                               {attempt['attempt_id'] for attempt in attempts})
    result['neurotwin'] = dict(state='eligible_source_references_only',
        eligible_descriptive_references=accepted,
        inference_executed=False, clinical_comparability_established=False,
        explanation='Source provenance is available for longitudinal research review. This response does not insert NeuroTwin records or calculate a trend.')
    result['next_action'] = _recommend(dict(safety_hold=safety, permission_missing=False,
        concern=concern, case_state=case['state'], workflow_state=item['state'],
        native_status=source_status, accepted=accepted, quarantined=quarantined,
        disposition=disposition))
    return result
