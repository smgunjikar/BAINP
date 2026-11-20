"""Deterministic research safety contract. Server-side library, NOT a public API.

Only trusted host adapters may construct inputs. No diagnosis or clearance.
Call within the host's authorized workspace transaction; see docs/INTEGRATION.md.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

VERSION = 'neuroguard-safety-v2.0.0'
SCHEMA = 'neuroguard-safety-passport-v2'
ACTIONS = {
    'launch_cognitive_task': ('assessment', 'cognitive', False),
    'collect_wearable': ('wearable', 'wearable', False),
    'collect_eeg': ('eeg', 'eeg', False),
    'collect_passive': ('passive', 'passive', False),
    'process_mri': ('imaging', 'mri', False),
    'interpret_cognitive': ('assessment', 'cognitive', True),
    'interpret_wearable': ('wearable', 'wearable', True),
    'interpret_eeg': ('eeg', 'eeg', True),
    'interpret_mri': ('imaging', 'mri', True),
    'interpret_passive': ('passive', 'passive', True),
    'compare_visits': ('history', 'longitudinal', True),
    'research_forecast': ('forecast', 'model', True),
    'confirm_referral_delivery': ('care_sharing', 'care', True),
}
QC_REQUIRED = {
    'cognitive': ('protocol_complete', 'timing_valid', 'device_suitable'),
    'wearable': ('sensor_verified', 'coverage_adequate', 'calibration_valid', 'artifacts_reviewed'),
    'eeg': ('sampling_valid', 'channels_verified', 'electrodes_verified', 'artifacts_reviewed'),
    'mri': ('acquisition_reviewed', 'orientation_verified', 'segmentation_approved'),
    'passive': ('duration_adequate', 'device_suitable', 'input_quality_valid'),
    'longitudinal': ('identity_matched', 'chronology_valid', 'protocol_comparable', 'units_comparable'),
    'model': ('model_review_current', 'population_supported', 'purpose_supported', 'calibration_reviewed', 'in_distribution', 'uncertainty_supported'),
    'care': ('delivery_verified',),
}
LIMITATIONS = [
    'Operational research permission only; not clinical validation or a diagnosis.',
    'Absence of a reported warning does not rule out an emergency.',
    'Host authentication, source verification and execution-time integration are required.',
]
TEXT = {
    'URGENT_GUIDANCE': 'Stop routine testing. Seek emergency help now using your local emergency number. This application has not contacted emergency services.',
    'UNAVAILABLE': 'Current safety information could not be verified. Try again or seek support; protected actions remain paused.',
    'HOLD': 'Resolve the listed permission, readiness or quality issue before continuing.',
    'ABSTAIN': 'Available evidence does not support the requested output.',
    'REVIEW': 'A professional review is appropriate before this routine action proceeds. A local case is not a delivered referral.',
    'PERMIT': 'This specific research action is permitted with the recorded conditions.',
}
TEXT_HI = {
    'URGENT_GUIDANCE': 'नियमित परीक्षण रोकें। अपने स्थानीय आपातकालीन नंबर पर अभी सहायता लें। इस ऐप ने आपातकालीन सेवाओं से संपर्क नहीं किया है।',
    'UNAVAILABLE': 'वर्तमान सुरक्षा जानकारी सत्यापित नहीं हो सकी। सुरक्षित कार्रवाई अभी रुकी हुई है। दोबारा प्रयास करें या सहायता लें।',
    'HOLD': 'आगे बढ़ने से पहले सूची में दी गई अनुमति, तैयारी या गुणवत्ता की समस्या ठीक करें।',
    'ABSTAIN': 'उपलब्ध जानकारी अनुरोधित निष्कर्ष का समर्थन नहीं करती।',
    'REVIEW': 'इस नियमित कार्रवाई से पहले पेशेवर समीक्षा उचित है। स्थानीय रिकॉर्ड बनने का अर्थ रेफरल भेजा जाना नहीं है।',
    'PERMIT': 'दर्ज शर्तों के अनुसार इस विशेष शोध कार्रवाई की अनुमति है।',
}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def stamp(now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('Timezone-aware server time required')
    return now.astimezone(timezone.utc).isoformat()

def parse_time(value):
    if not isinstance(value, str): raise ValueError('Timestamp required')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None: raise ValueError('Timezone required')
    return dt

def valid_context(c):
    """Validate structure before any permit; booleans must be actual booleans."""
    if not isinstance(c, dict): return False
    strings = ('workspace_id', 'participant_id', 'actor_id', 'session_id', 'action')
    if any(not isinstance(c.get(k), str) or not 0 < len(c[k]) <= 200 for k in strings): return False
    if c.get('mode') not in ('active', 'demo'): return False
    if any(type(c.get(k)) is not int or c[k] < 0 for k in ('input_revision', 'consent_revision')): return False
    if any(type(c.get(k)) is not bool for k in ('authorized', 'service_available', 'inputs_verified', 'warning_reviewed', 'functional_review_required')): return False
    if not isinstance(c.get('urgent_signs'), list) or any(not isinstance(x, str) or not x or len(x)>200 for x in c['urgent_signs']): return False
    if not isinstance(c.get('consents'), dict) or any(type(x) is not bool for x in c['consents'].values()): return False
    if not isinstance(c.get('readiness'), dict) or any(type(x) is not bool for x in c['readiness'].values()): return False
    if not isinstance(c.get('sources'), list) or len(c['sources']) > 1000: return False
    for s in c['sources']:
        if not isinstance(s, dict): return False
        for k in ('id', 'revision', 'participant_id', 'workspace_id', 'mode', 'modality', 'quality', 'protocol', 'sha256'):
            if not isinstance(s.get(k), str) or not s[k]: return False
        if len(s['sha256']) != 64 or any(x not in '0123456789abcdef' for x in s['sha256']): return False
        if s['quality'] not in ('usable', 'missing', 'quarantined', 'unreviewed'): return False
        if not isinstance(s.get('checks'), dict) or any(type(x) is not bool for x in s['checks'].values()): return False
    try:
        canonical(c)
        parse_time(c['observed_at'])
        parse_time(c['valid_until'])
    except (ValueError, TypeError, KeyError, OverflowError): return False
    return True

def evaluate(context, *, now=None, ttl_seconds=300):
    """Evaluate trusted server snapshot. Result alone is NOT an execution token."""
    now = now or datetime.now(timezone.utc)
    evaluated_at = stamp(now)
    if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 300: raise ValueError('TTL must be 1..300 seconds')
    c = context if isinstance(context, dict) else {}
    status, reasons = 'UNAVAILABLE', ['INVALID_SAFETY_CONTEXT']
    valid = valid_context(c)
    if valid:
        scope, modality, requires_sources = ACTIONS.get(c['action'], (None, None, False))
        # Unauthorized callers receive no source-bearing decision through GuardStore.
        # Pure evaluator still gives urgent public guidance precedence over consent.
        if c['urgent_signs']:
            status, reasons = 'URGENT_GUIDANCE', ['REPORTED_ACUTE_WARNING']
        elif not c['authorized']:
            status, reasons = 'HOLD', ['AUTHORIZATION_REQUIRED']
        elif not c['service_available'] or not c['inputs_verified'] or not c['warning_reviewed']:
            status, reasons = 'UNAVAILABLE', ['CURRENT_SAFETY_VERIFICATION_REQUIRED']
        elif parse_time(c['observed_at']) > now or parse_time(c['valid_until']) <= now or parse_time(c['valid_until']) <= parse_time(c['observed_at']):
            status, reasons = 'UNAVAILABLE', ['SAFETY_INPUTS_EXPIRED_OR_FUTURE']
        elif scope is None:
            status, reasons = 'ABSTAIN', ['UNSUPPORTED_ACTION']
        elif c['consents'].get(scope) is not True:
            status, reasons = 'HOLD', ['CONSENT_REQUIRED:' + scope]
        elif c['functional_review_required'] and c['action'] != 'confirm_referral_delivery':
            status, reasons = 'REVIEW', ['NEW_FUNCTIONAL_CONCERN']
        elif not requires_sources:
            required = ('task_compatible', 'device_ready', 'instructions_understood')
            missing = [k for k in required if c['readiness'].get(k) is not True]
            status, reasons = ('HOLD', ['READINESS_REQUIRED:' + k for k in missing]) if missing else ('PERMIT', [])
        else:
            matching = [s for s in c['sources'] if s['modality'] == modality]
            reasons = []
            if not matching: reasons.append('SOURCE_MISSING:' + modality)
            for s in matching:
                if any(s[k] != c[k] for k in ('workspace_id', 'participant_id', 'mode')):
                    reasons.append('SOURCE_IDENTITY_MISMATCH:' + s['id'])
                if s['quality'] != 'usable': reasons.append('SOURCE_' + s['quality'].upper() + ':' + s['id'])
                reasons.extend('QC_REQUIRED:' + k + ':' + s['id'] for k in QC_REQUIRED[modality] if s['checks'].get(k) is not True)
            status = 'HOLD' if reasons else 'PERMIT'
            if reasons and modality == 'model': status = 'ABSTAIN'
            # No clinical-prediction action exists; only reviewed research forecasts.
    expires = now + timedelta(seconds=ttl_seconds)
    if valid: expires = min(expires, parse_time(c['valid_until']))
    result = dict(schema=SCHEMA, decision_id=str(uuid4()), status=status,
        reason_codes=sorted(set(reasons)), allowed_actions=[c['action']] if status=='PERMIT' else [],
        blocked_actions=[] if status=='PERMIT' else ([c['action']] if valid else []),
        next_step={'PERMIT':'continue','HOLD':'review_conditions','ABSTAIN':'review_evidence','REVIEW':'request_professional_review','URGENT_GUIDANCE':'seek_emergency_help','UNAVAILABLE':'retry_or_support'}[status],
        text=TEXT[status], text_hi=TEXT_HI[status], policy_version=VERSION,
        evaluated_at=evaluated_at, expires_at=stamp(expires), clinical_clearance=False,
        emergency_ruled_out=False, limitations=list(LIMITATIONS),
        context_sha256=digest(c) if valid else None,
        source_observation_ids=[s['id'] for s in c['sources']] if valid else [])
    for k in ('workspace_id', 'participant_id', 'actor_id', 'session_id', 'mode', 'action', 'input_revision', 'consent_revision'):
        result[k] = c.get(k) if valid else None
    return result

def verify_execution(decision, current_context, *, now=None):
    """Re-evaluate immutable STORED decision against freshly loaded context.

Do not pass a browser-supplied decision here. GuardStore enforces stored retrieval.
The host must lock the current source state through action commit.
"""
    now = now or datetime.now(timezone.utc)
    fresh = evaluate(current_context, now=now)
    if fresh['status'] != 'PERMIT': return fresh
    try:
        valid = (decision['schema']==SCHEMA and decision['policy_version']==VERSION
                 and decision['status']=='PERMIT' and decision['context_sha256']==fresh['context_sha256']
                 and decision['allowed_actions']==fresh['allowed_actions']
                 and parse_time(decision['evaluated_at']) <= now < parse_time(decision['expires_at']))
    except (KeyError, TypeError, ValueError): valid = False
    if valid: return fresh
    return fresh | dict(status='HOLD', reason_codes=['STALE_OR_INVALID_DECISION'], allowed_actions=[],
                        blocked_actions=[current_context['action']], next_step='refresh_decision', text='The earlier permission is no longer current. Refresh the decision.',
                        text_hi='पहले दी गई अनुमति अब वर्तमान नहीं है। निर्णय दोबारा जाँचें।')


def public_warning_guidance(reported_acute_warning, language='en'):
    """Public/offline text only. No identity, consent, storage or permission needed.

    This cannot identify an emergency from arbitrary clinical data.
    """
    if reported_acute_warning is True:
        return dict(status='URGENT_GUIDANCE', text=(TEXT_HI if language=='hi' else TEXT)['URGENT_GUIDANCE'],
                    allowed_actions=[], emergency_contacted=False, emergency_ruled_out=False)
    return dict(status='UNASSESSED', text='This application cannot rule out a medical emergency.',
                allowed_actions=[], emergency_contacted=False, emergency_ruled_out=False)
