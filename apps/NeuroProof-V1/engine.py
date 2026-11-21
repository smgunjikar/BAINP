"""Evidence traceability checks, not clinical correctness verification."""
from hashlib import sha256
import json
VERSION='neuroproof-passport-v1.0.0'
def digest(value):return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def passport(recommendation,observations,expected_hash=None):
    for key in ('participant_id','mode','policy','action','evidence_ids','limitations'):
        if key not in recommendation:raise ValueError('Missing recommendation contract: '+key)
    if not recommendation['participant_id'] or recommendation['mode'] not in ('active','demo'):raise ValueError('Invalid identity')
    index={}
    for item in observations:
        if item.get('participant_id')!=recommendation['participant_id'] or item.get('mode')!=recommendation['mode']:raise ValueError('Evidence identity mismatch')
        if not item.get('id') or item['id'] in index:raise ValueError('Missing or duplicate evidence ID')
        index[item['id']]=item
    missing=[];unusable=[];incomplete=[];support=[]
    for ref in recommendation['evidence_ids']:
        item=index.get(ref)
        if item is None:missing.append(ref);continue
        if item.get('quality')!='source_verified':unusable.append(ref)
        if not all(item.get(k) for k in ('source','observed_at','processing_version')):incomplete.append(ref)
        support.append(item)
    current=digest(recommendation)
    checks=dict(unresolved_references=missing,rejected_quality=unusable,incomplete_provenance=incomplete,hash_matches=None if expected_hash is None else current==expected_hash)
    valid=not(missing or unusable or incomplete) and checks['hash_matches'] is not False
    result=dict(passport_version=VERSION,participant_id=recommendation['participant_id'],mode=recommendation['mode'],recommendation=recommendation,supporting_observations=support,checks=checks,
        traceability_status='CONSISTENT_AVAILABLE_RECORDS' if valid else 'REVIEW_REQUIRED',clinical_correctness='NOT_ESTABLISHED',
        limitations=['Reference resolution does not prove that evidence supports the clinical conclusion.','Local hashes are not signatures or external tamper-proof evidence.','Source authenticity, guideline applicability and clinical validity require independent review.'])
    return result|{'passport_sha256':digest(result)}
