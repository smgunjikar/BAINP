"""Deterministic measurement-selection prototype; no scores or clinical thresholds."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
VERSION='neuroquest-rules-v2.0.0'
# Operational demo burden interval, explicitly not a clinical follow-up schedule.
COOLDOWN_HOURS=24

def fingerprint(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _select(context):
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
    if intent.get('pause_requested') is True:
        return done('monitor','PARTICIPANT_REQUESTED_PAUSE','Pause testing and return when ready. No assessment is started; keep any existing care plan.')
    if not context['consent']['history_allowed']:
        return done('abstain','HISTORY_PERMISSION_REQUIRED','History is unavailable by permission; repeated testing cannot be excluded.')
    if context['guard'].get('state')!='workflow_permitted':
        return done('abstain','GUARD_ABSTENTION','NeuroGuard or NeuroAccess withheld operational assessment permission.')
    if 'allowed_actions' in context['guard'] and 'existing_neurocognition' not in context['guard']['allowed_actions']:
        return done('abstain','GUARD_ACTION_NOT_PERMITTED','NeuroGuard has not authorized this assessment action.')
    if not context['consent']['assessment_allowed']:
        return done('abstain','ASSESSMENT_PERMISSION_REQUIRED','Assessment permission is required.')
    if not registry['core'] or any(t not in registry['tasks'] for t in registry['core']):
        return done('abstain','CATALOGUE_UNAVAILABLE','The registered native battery could not be verified.')
    if 'C02' in registry['core'] and ('C01' not in registry['core'] or registry['core'].index('C01')>registry['core'].index('C02')):
        return done('abstain','MEMORY_DEPENDENCY_INVALID','Delayed recognition requires the preceding learning phase and the native protocol delay.')
    if profile.get('can_see_and_respond')!='yes' or profile.get('motor_limitation') or (profile.get('vision_limitation') and profile.get('vision_aid') not in ('none','glasses')) or (profile.get('hearing_limitation') and not profile.get('hearing_aid')) or profile.get('assistance')!='none':
        return done('abstain','ACCESSIBILITY_REVIEW_REQUIRED','The registry has no validated alternative for these limitations or assisted administration. Review accommodations before offering this battery.')
    result['accessibility_note']='Eligibility uses confirmed ability to see and respond with usual correction. A recorded vision condition alone is not exclusion. Magnification/other aids require review. This is operational eligibility, not clinical validation.'
    if profile.get('language') not in ('en','ar'):
        return done('abstain','UNSUPPORTED_LANGUAGE','The native interface language is unsupported by this registry adapter.')
    recovery=context.get('recovery')
    if recovery:
        return done('repeat','AUTHORIZED_NATIVE_RECOVERY','Repeat the explicitly prepared research tasks. Original results remain unchanged; repeat equivalence is not established.',task_ids=recovery['order'],executable=True,battery='core',recovery_id=recovery['id'])
    history=context['history']; latest={}
    history=sorted(history,key=lambda r:(r.get('observed_at') or '',r.get('source_id','')),reverse=True)
    for ref in history:
        if ref.get('protocol') not in (None,registry['protocol']):continue
        if ref['task'] not in latest:latest[ref['task']]=ref
    if any(r.get('quality') not in ('QUARANTINED','SOURCE_QC_CLEAR_DESCRIPTIVE_ONLY','CLEAR') for r in latest.values()):
        return done('abstain','SOURCE_QUALITY_UNKNOWN','The source quality status is missing or unrecognized. Review it before offering another assessment.')
    bad=[r for r in latest.values() if r['quality']=='QUARANTINED']
    if bad:
        if context.get('fresh_visit_after_incomplete') and intent['quality_problem_addressed']:
            return done('baseline','INDEPENDENT_RESEARCH_VISIT_AFTER_INTERRUPTION',
                'Offer a new, independent core research battery after explicit acknowledgement and fresh NeuroAccess preparation. Earlier incomplete or unreliable results remain in history and are not treated as valid, equivalent or clinically comparable.',
                task_ids=registry['core'],executable=True,battery='core',
                previous_quality_issues=[dict(task=r['task'],source_id=r.get('source_id'),flags=r.get('flags',[])) for r in bad],
                equivalence_established=False)
        return done('repeat','QUALITY_CORRECTION_REQUIRED' if not intent['quality_problem_addressed'] else 'TARGETED_EXECUTION_UNAVAILABLE',
            'Correct the recorded technical or administration problem. Native single-task repeat execution is not available; no full-battery repeat is launched automatically.',
            quality_issues=[dict(task=r['task'],source_id=r.get('source_id'),flags=r.get('flags',[]),quality=r['quality']) for r in bad],
            task_ids=sorted(r['task'] for r in bad), prerequisites=['Document correction','Supported authorized repeat protocol'], executable=False)
    if intent['target_domain']!='none':
        return done('targeted','COMPARABILITY_AND_EXECUTION_NOT_ESTABLISHED','A domain clarification was requested. Source data do not establish reliable cognitive change and the native API does not expose isolated task execution.', requested_domain=intent['target_domain'])
    clear=[r for r in history if r['quality'] in ('SOURCE_QC_CLEAR_DESCRIPTIVE_ONLY','CLEAR') and r['protocol']==registry['protocol']]
    bysession={}
    for r in clear:bysession.setdefault((r['source_session_id'],r.get('form')),set()).add(r['task'])
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


DECISION_TTL_SECONDS=300

def context_fingerprint(context):
    return fingerprint({k:v for k,v in context.items() if k!='as_of'})

def select(context):
    result=_select(context)
    selected=datetime.fromisoformat(context['as_of'])
    if selected.tzinfo is None:raise ValueError('Timezone-aware decision time required')
    result['expires_at']=(selected+timedelta(seconds=DECISION_TTL_SECONDS)).isoformat()
    result['context_sha256']=context_fingerprint(context)
    result['lifecycle']='proposed_not_executed'
    result['passport']=dict(schema='neuroquest-decision-passport-v2',
        profile_revision=context.get('profile_revision'),consent_revision=context.get('consent_revision'),
        guard_policy=context.get('guard',{}).get('policy'),guard_state=context.get('guard',{}).get('state'),
        source_ids=[r.get('source_id') for r in context['history'] if r.get('source_id')],
        protocol=result['protocol'],task_ids=result['task_ids'],policy=VERSION,
        input_sha256=result['input_sha256'],context_sha256=result['context_sha256'],
        selected_at=result['selected_at'],expires_at=result['expires_at'],
        execution_authority='NeuroContinuum with current native checks',
        clinical_validation=False)
    result['alternatives_considered']=[dict(action='isolated_task',available=False,reason='Native isolated-task execution is not registered.'),
        dict(action='micro_pathway',available=False,reason='No reviewed executable Micro pathway is registered.'),
        dict(action='extended_pathway',available=False,reason='Extended task presence alone does not establish an eligible selection pathway.')]
    return result

def is_current(saved,fresh):
    try:
        return (saved.get('policy')==VERSION and saved.get('context_sha256')==fresh['context_sha256']
            and datetime.fromisoformat(saved['selected_at'])<=datetime.fromisoformat(fresh['selected_at'])<datetime.fromisoformat(saved['expires_at'])
            and all(saved.get(k)==fresh.get(k) for k in ('action','reason_codes','task_ids','executable','protocol')))
    except (ValueError,TypeError,KeyError):return False

# Deliberately separate from the existing task-selection policy. Camera features
# do not affect clinical or psychometric conclusions; this is an operational
# post-assessment disposition based on verified native status and existing care.
POST_ASSESSMENT_POLICY = 'neuroquest-post-assessment-v1.0'

def post_assessment_action(context):
    """Pure, non-executable follow-up guidance, not a new diagnosis or test order."""
    base = dict(policy=POST_ASSESSMENT_POLICY, executable=False, clinical_validation=False,
                decision_kind='operational_follow_up', assessment_selected=False)
    def response(code, title, reason, destination='/neurocontinuum'):
        return base | dict(code=code, title=title, reason=reason, destination=destination)
    if context.get('safety_hold'):
        return response('EXISTING_SAFETY_RESTRICTION', 'Review saved safety guidance',
            'A saved NeuroGuard restriction takes priority. Routine digital testing must not delay appropriate urgent care.')
    if context.get('permission_missing'):
        return response('HISTORY_PERMISSION_REQUIRED', 'Review your information permissions',
            'A consented history is required for an evidence-based follow-up summary.')
    if context.get('concern') == 'yes':
        return response('REPORTED_FUNCTIONAL_CHANGE', 'Discuss reported everyday changes',
            'The existing functional concern requires human assessment; digital test results cannot rule it out.', '/careloop')
    case_state = context.get('case_state')
    if case_state in {'review_requested', 'referral_documented', 'followup_planned', 'monitoring_planned'}:
        return response('CARELOOP_ACTION_OPEN', 'Review your existing care action',
            'A local CareLoop record is open. Its state does not prove that a clinician was contacted or a referral delivered.', '/careloop')
    if context.get('workflow_state') not in ('COMPLETED', 'CANCELLED', None):
        return response('VISIT_STILL_ACTIVE', 'Return to your current visit',
            'Complete or explicitly close the active visit before a new post-assessment action is selected.')
    if context.get('quarantined', 0) > 0 or context.get('disposition') == 'INCOMPLETE_VISIT' or context.get('native_status') == 'interrupted':
        return response('QUALITY_REVIEW_REQUIRED', 'Review assessment quality',
            'Some task evidence was interrupted or quarantined. Review testing conditions and the existing results before considering a separate, freshly prepared research visit.')
    if context.get('accepted', 0) > 0 and context.get('native_status') == 'completed':
        return response('DESCRIPTIVE_RESULTS_AVAILABLE', 'Review your results and monitoring options',
            'Descriptive measurements are available. No validated clinical change threshold or universal repeat schedule is established.')
    return response('NO_VALID_BATTERY_AVAILABLE', 'Review your next assessment options',
        'There is no completed, quality-clear research battery for this visit. The system must not create a score or automatically repeat testing.')
