"""Independent operational workflow gate. Not medical triage or clinical clearance.

This adapter is new; it does not pretend the earlier claim-release Guard already
exposed a task-authorization API. No scientific score or disease threshold is used.
"""
from hashlib import sha256
import json

VERSION='neuroguard-continuum-workflow-v1.1'

def fingerprint(context):
    return sha256(json.dumps(context,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def evaluate(context):
    if not isinstance(context, dict):
        return dict(state='abstain', reason_codes=['INVALID_CONTEXT'], allowed_actions=[], policy=VERSION,
                    clinical_clearance=False, emergency_ruled_out=False)
    reasons=[]
    # These fields are optional in the legacy host contract. Absence is not a
    # negative safety finding; the adapter is not a full V2 authorization.
    if context.get('urgent_signs'):
        reasons.append('REPORTED_ACUTE_WARNING')
    if context.get('functional_review_required') is True:
        reasons.append('PROFESSIONAL_REVIEW_REQUIRED')
    if 'authorized' in context and context['authorized'] is not True:
        reasons.append('AUTHORIZATION_REQUIRED')
    if context.get('participant_id') != context.get('source_participant_id') or not context.get('participant_id'):
        reasons.append('PARTICIPANT_IDENTITY_MISMATCH')
    if context.get('mode') not in ('active','demo') or context.get('mode')!=context.get('source_mode'):
        reasons.append('SOURCE_MODE_MISMATCH')
    if context.get('monitoring_consent') is not True or context.get('assessment_consent') is not True:
        reasons.append('APPLICABLE_WORKFLOW_CONSENT_REQUIRED')
    if context.get('native_guard_available') is not True:
        reasons.append('NATIVE_GUARD_UNAVAILABLE')
    if not context.get('checkin_id') or context.get('access_reasons'):
        reasons.append('EXISTING_ACCESS_HOLD')
    return dict(state='abstain' if reasons else 'workflow_permitted',reason_codes=reasons,
                allowed_actions=[] if reasons else ['existing_neurocognition'],
                policy=VERSION,context_sha256=fingerprint(context),
                authority='NeuroGuard operational workflow adapter', enforcement_scope='legacy_workflow_checks_only',
                v2_execution_authorized=False,
                clinical_clearance=False,emergency_ruled_out=False,
                text='Operational permission only. Existing assessment restrictions and source-quality checks remain mandatory; this does not rule out an emergency.')
