"""Clinician-review prototype. No diagnosis, lab thresholds or medication advice."""
from hashlib import sha256
import json
VERSION='neuromimic-rules-v1.0.0'
DOMAINS=('sleep','medication_review','vitamin_b12','thyroid','metabolic')
def analyze(context):
    if not context.get('participant_id') or context.get('mode') not in ('active','demo'):
        raise ValueError('Participant and mode are required')
    if context.get('consent') is not True:raise PermissionError('Explicit clinical-context permission required')
    guard=context.get('guard',{})
    if guard.get('state')=='escalate':
        return dict(policy=VERSION,action='urgent_guard_path',findings=[],guard=guard,limitations=['Contributor review must not delay urgent guidance or referrals.'])
    if guard.get('state')!='review_permitted':
        return dict(policy=VERSION,action='abstain',findings=[],limitations=['Independent review permission unavailable.'])
    observations=context.get('observations',[]);findings=[];missing=[]
    for item in observations:
        if item.get('participant_id')!=context['participant_id'] or item.get('mode')!=context['mode']:
            raise ValueError('Cross-participant or cross-mode evidence rejected')
        if not all(item.get(k) for k in ('id','source','observed_at','domain','quality')):
            raise ValueError('Incomplete provenance')
    for domain in DOMAINS:
        refs=[o for o in observations if o['domain']==domain and o['quality']=='source_verified']
        if not refs:missing.append(domain);continue
        reported=[o for o in refs if o.get('clinician_flagged') is True or o.get('participant_reported_concern') is True]
        if reported:findings.append(dict(domain=domain,classification='reported_or_clinician_flagged_contributor_for_review',evidence_ids=[o['id'] for o in reported],next_action='Clinician review of the source information; no cause established.'))
    return dict(policy=VERSION,participant_id=context['participant_id'],mode=context['mode'],action='professional_review',findings=findings,missing_domains=missing,
        input_sha256=sha256(json.dumps(context,sort_keys=True,allow_nan=False).encode()).hexdigest(),
        limitations=['Reported contributors can coexist with neurological disease.','No automated lab interpretation, medication changes or treatment recommendations.','No contributor is ruled out by missing information.','Clinical review and necessary specialist referrals must proceed independently.'])
