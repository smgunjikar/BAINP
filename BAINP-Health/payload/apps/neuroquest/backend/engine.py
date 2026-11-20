"""Deterministic measurement-selection prototype; no scores or clinical thresholds."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
VERSION='neuroquest-rules-v1.2.0'
# Operational demo burden interval, explicitly not a clinical follow-up schedule.
COOLDOWN_HOURS=24

def fingerprint(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def select(context):
    """Pure function: identical explicit context -> identical recommendation."""
    profile=context['profile']; intent=context['intent']; registry=context['registry']
    result=dict(policy=VERSION, action='abstain', reason_codes=[], task_ids=[], executable=False,
        protocol=registry['protocol'], selected_at=context['as_of'], next_eligible_at=None,
        evidence=context['history'], input_sha256=fingerprint(context), clinical_validation=False,
        uncertainty=['No calibrated reliable-change threshold or alternate-form equivalence is available.'],
        comparison='Do not pool different protocols, forms, administration conditions or selected batteries.',
        burden_policy=dict(hours=COOLDOWN_HOURS, status='engineering_cooldown_not_clinical_schedule'),
        external_contact=False)
    def done(action,code,text,**extra):
        result.update(action=action,reason_codes=[code],reason=text,**extra)
        return result
    if context.get('urgent',{}).get('state')=='escalate':
        return done('urgent_guidance','NEUROGUARD_URGENT_OVERRIDE','Follow existing NeuroGuard guidance before routine testing.',guidance=context['urgent'])
    if intent['functional_concern']:
        return done('professional_review','NEW_FUNCTIONAL_CONCERN','Professional review is appropriate to request regardless of digital task results.',destination='/careloop')
    if not context['consent']['history_allowed']:
        return done('abstain','HISTORY_PERMISSION_REQUIRED','History is unavailable by permission; repeated testing cannot be excluded.')
    if context['guard'].get('state')!='workflow_permitted':
        return done('abstain','GUARD_ABSTENTION','NeuroGuard or NeuroAccess withheld operational assessment permission.')
    if not context['consent']['assessment_allowed']:
        return done('abstain','ASSESSMENT_PERMISSION_REQUIRED','Assessment permission is required.')
    if not registry['core'] or any(t not in registry['tasks'] for t in registry['core']):
        return done('abstain','CATALOGUE_UNAVAILABLE','The registered native battery could not be verified.')
    if profile.get('can_see_and_respond')!='yes' or profile.get('motor_limitation') or (profile.get('vision_limitation') and profile.get('vision_aid') not in ('none','glasses')) or (profile.get('hearing_limitation') and not profile.get('hearing_aid')) or profile.get('assistance')!='none':
        return done('abstain','ACCESSIBILITY_REVIEW_REQUIRED','The registry has no validated alternative for these limitations or assisted administration. Review accommodations before offering this battery.')
    result['accessibility_note']='Eligibility uses confirmed ability to see and respond with usual correction. A recorded vision condition alone is not exclusion. Magnification/other aids require review. This is operational eligibility, not clinical validation.'
    if profile.get('language') not in ('en','ar'):
        return done('abstain','UNSUPPORTED_LANGUAGE','The native interface language is unsupported by this registry adapter.')
    history=context['history']; latest={}
    for ref in history:
        if ref['task'] not in latest:latest[ref['task']]=ref
    bad=[r for r in latest.values() if r['quality']=='QUARANTINED']
    if bad:
        return done('repeat','QUALITY_CORRECTION_REQUIRED' if not intent['quality_problem_addressed'] else 'TARGETED_EXECUTION_UNAVAILABLE',
            'Correct the recorded technical or administration problem. Native single-task repeat execution is not available; no full-battery repeat is launched automatically.',
            task_ids=sorted(r['task'] for r in bad), prerequisites=['Document correction','Supported authorized repeat protocol'], executable=False)
    if intent['target_domain']!='none':
        return done('targeted','COMPARABILITY_AND_EXECUTION_NOT_ESTABLISHED','A domain clarification was requested. Source data do not establish reliable cognitive change and the native API does not expose isolated task execution.', requested_domain=intent['target_domain'])
    clear=[r for r in history if r['quality']!='QUARANTINED' and r['protocol']==registry['protocol']]
    bysession={}
    for r in clear:bysession.setdefault(r['source_session_id'],set()).add(r['task'])
    complete=any(set(registry['core']).issubset(tasks) for tasks in bysession.values())
    if complete and intent['concerns_checked']:
        stamp=max(r['observed_at'] for r in clear if r['observed_at'])
        try:
            eligible=datetime.fromisoformat(stamp)+timedelta(hours=COOLDOWN_HOURS)
            current=datetime.fromisoformat(context['as_of'])
            if current.tzinfo is None or eligible.tzinfo is None or eligible>current+timedelta(hours=COOLDOWN_HOURS):raise ValueError('clock')
        except (TypeError,ValueError):
            return done('abstain','SOURCE_TIMESTAMP_INVALID','Review source timestamp or clock before scheduling.')
        if current<eligible:
            return done('monitor','RECENT_COMPLETE_SOURCE_BATTERY','No immediate repeat under the engineering burden policy. Keep any existing clinical follow-up plan.',next_eligible_at=eligible.isoformat())
    if complete and not intent['concerns_checked']:
        return done('abstain','CURRENT_CONCERNS_UNKNOWN','Check current functional concerns before another assessment.')
    return done('baseline' if not complete else 'reassessment','NO_COMPLETE_CURRENT_PROTOCOL_BASELINE' if not complete else 'OPERATIONAL_COOLDOWN_ELAPSED',
        'Offer the existing core research battery after native diagnostics and preparation. This does not establish a clinically valid baseline.',
        task_ids=registry['core'],executable=True,battery='core',language_status='interface_available_translation_not_clinically_validated')
