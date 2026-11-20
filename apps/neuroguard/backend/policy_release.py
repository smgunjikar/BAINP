"""Offline release-evidence verifier; never approves clinical policy by itself.

Deployment operators must independently verify reviewer identity and evidence.
No runtime route is provided for changing policy or approving a model.
"""
from datetime import datetime, timezone
try:
    from .safety_v2 import digest, parse_time
except ImportError:
    from safety_v2 import digest, parse_time

def check_release(manifest, policy_bytes, regression_bytes, *, now=None):
    import hashlib
    now=now or datetime.now(timezone.utc)
    reasons=[]
    if not isinstance(manifest,dict): return ['RELEASE_MANIFEST_INVALID']
    for key in ('policy_version','reviewer_id','clinical_review_reference','hazard_review_reference','regression_reference'):
        if not isinstance(manifest.get(key),str) or not manifest[key].strip(): reasons.append('REQUIRED:'+key)
    if manifest.get('approved') is not True: reasons.append('REVIEW_APPROVAL_REQUIRED')
    if manifest.get('regression_passed') is not True: reasons.append('REGRESSION_PASS_REQUIRED')
    if manifest.get('policy_sha256')!=hashlib.sha256(policy_bytes).hexdigest(): reasons.append('POLICY_HASH_MISMATCH')
    if manifest.get('regression_sha256')!=hashlib.sha256(regression_bytes).hexdigest(): reasons.append('REGRESSION_HASH_MISMATCH')
    try:
        if not parse_time(manifest['reviewed_at'])<=now<parse_time(manifest['expires_at']): reasons.append('RELEASE_REVIEW_NOT_CURRENT')
    except (KeyError,ValueError,TypeError): reasons.append('RELEASE_REVIEW_TIME_INVALID')
    return reasons
