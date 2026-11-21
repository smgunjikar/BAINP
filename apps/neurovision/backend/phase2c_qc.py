"""BAINP Phase 2C: account-scoped anatomical QC + provenance evidence.

Technical evidence only. No diagnosis, regulatory claim, anatomical approval,
identity linking, or longitudinal trend authorization occurs here.
"""
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from nv_queue import jobs

SCAN_ID = re.compile(r'^[a-f0-9]{24}$')
DIGEST = re.compile(r'^[a-f0-9]{64}$')
MAX_REVIEW_BYTES = 1024 * 1024
MAX_RAW_BYTES = 64 * 1024 * 1024


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def package_metadata(storage, entry):
    """Fail closed when the immutable saved package is modified."""
    sid = entry.get('id')
    if not isinstance(sid, str) or not SCAN_ID.fullmatch(sid):
        raise HTTPException(404, 'scan_not_found')
    path = storage / (sid + '.json')
    if path.is_symlink() or not path.is_file():
        raise HTTPException(503, 'imaging_package_unavailable')
    try:
        raw = path.read_bytes()
        if not DIGEST.fullmatch(entry.get('package_sha256') or ''):
            raise ValueError('missing catalog digest')
        if hashlib.sha256(raw).hexdigest() != entry['package_sha256']:
            raise ValueError('package digest mismatch')
        pack = json.loads(raw)
        meta = pack['metadata']
        if meta.get('synthetic') is not False:
            raise ValueError('demo or missing source flag')
        if any(meta.get(x) != entry.get(x) for x in ('cohort', 'subject', 'visit')):
            raise ValueError('imaging identity mismatch')
        return meta
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        raise HTTPException(503, 'imaging_package_integrity_failed')


def retained_label_provenance(job, folder, packaged_digest, alignment):
    """Check retained original label bytes; a resampled label has a distinct digest."""
    supplied = (job.get('aux') or {}).get('labels')
    if not isinstance(supplied, dict):
        return {'state': 'RETAINED_LABEL_UPLOAD_UNAVAILABLE'}
    name = supplied.get('source')
    if name not in ('labels.nii', 'labels.nii.gz'):
        return {'state': 'RETAINED_LABEL_UPLOAD_NAME_INVALID'}
    path = folder / name
    try:
        if path.is_symlink() or not path.is_file():
            return {'state': 'RETAINED_LABEL_UPLOAD_MISSING'}
        if path.stat().st_size > MAX_RAW_BYTES:
            return {'state': 'RETAINED_LABEL_UPLOAD_EXCEEDS_AUDIT_LIMIT'}
        actual = sha256_file(path)
        if actual != supplied.get('sha256'):
            return {'state': 'RETAINED_LABEL_UPLOAD_HASH_MISMATCH'}
        if actual == packaged_digest:
            return {'state': 'UPLOADED_AND_PACKAGED_LABEL_SHA256_VERIFIED', 'uploaded_sha256': actual}
        if isinstance(alignment, dict) and (
            actual == alignment.get('original_label_sha256') and
            packaged_digest == alignment.get('resampled_label_sha256')
        ):
            derived = folder / 'phase2b_labels_native.nii.gz'
            if derived.is_symlink() or not derived.is_file() or derived.stat().st_size > MAX_RAW_BYTES:
                return {'state': 'ALIGNED_LABEL_DERIVATIVE_UNAVAILABLE'}
            if sha256_file(derived) == packaged_digest:
                return {'state': 'ORIGINAL_AND_RESAMPLED_LABEL_SHA256_VERIFIED',
                        'uploaded_sha256': actual, 'resampled_sha256': packaged_digest}
        return {'state': 'UPLOADED_LABEL_VERIFIED_PACKAGED_LABEL_UNEXPLAINED'}
    except OSError:
        return {'state': 'RETAINED_LABEL_REHASH_ERROR'}


def retained_provenance(storage, scan_id, expected, packaged_label_digest=None, alignment=None):
    """Rehash only the retained input of an exact completed job for this package.

    No caller-controlled filesystem paths are accepted or followed.
    """
    folder = jobs(storage)
    if not folder.is_dir():
        return {'state': 'RAW_SOURCE_NOT_AVAILABLE_FOR_RECHECK'}
    examined = 0
    for record in folder.glob('*/job.json'):
        examined += 1
        if examined > 3000:
            return {'state': 'SOURCE_JOB_SEARCH_LIMIT'}
        if record.is_symlink():
            continue
        try:
            job = json.loads(record.read_text(encoding='utf-8'))
            if job.get('state') != 'complete' or job.get('package_id') != scan_id:
                continue
            source = job.get('source')
            if source not in ('source.nii', 'source.nii.gz'):
                return {'state': 'UNSAFE_OR_UNKNOWN_RETAINED_FILENAME'}
            candidate = record.parent / source
            if candidate.is_symlink() or not candidate.is_file():
                return {'state': 'RETAINED_SOURCE_MISSING'}
            if candidate.stat().st_size > MAX_RAW_BYTES:
                return {'state': 'RETAINED_SOURCE_EXCEEDS_AUDIT_LIMIT'}
            rehashed = sha256_file(candidate)
            return {
                'state': 'SOURCE_SHA256_VERIFIED' if rehashed == expected == job.get('sha256') else 'SOURCE_SHA256_MISMATCH',
                'source_sha256': rehashed,
                'job_sha256_matches': job.get('sha256') == rehashed,
                'package_source_sha256_matches': expected == rehashed,
                'labels': retained_label_provenance(job, record.parent, packaged_label_digest, alignment),
            }
        except (OSError, ValueError, TypeError, UnicodeError):
            return {'state': 'RETAINED_SOURCE_AUDIT_ERROR'}
    return {'state': 'RAW_SOURCE_NOT_AVAILABLE_FOR_RECHECK'}


def evaluate_measurements(measurements, voxel_ml, worker_qc):
    """Arithmetic checks; no biological norms or clinically meaningful cutoffs."""
    flags = []
    if not isinstance(measurements, list):
        return {'state': 'NOT_VERIFIABLE', 'flags': ['MEASUREMENTS_MISSING'], 'region_count': 0}
    region_ids = set()
    volume_total = 0.0
    for row in measurements:
        if not isinstance(row, dict):
            flags.append('MALFORMED_MEASUREMENT')
            continue
        k = str(row.get('id', ''))
        if not k.isdecimal() or int(k) <= 0:
            continue  # Derived nonatlas rows (e.g. the intensity preview) are excluded.
        if k in region_ids:
            flags.append('DUPLICATED_LABEL_ID')
        region_ids.add(k)
        try:
            voxels = row['voxel_count']
            value = row['volume_ml']
            if type(voxels) is not int or voxels < 1 or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError()
            if not isinstance(voxel_ml, (float, int)) or voxel_ml <= 0 or not math.isfinite(voxel_ml):
                raise ValueError()
            if abs(voxels * voxel_ml - value) > max(1e-4, value * 1e-6):
                flags.append('LABEL_VOLUME_ARITHMETIC_MISMATCH')
            volume_total += value
        except (KeyError, ValueError, TypeError):
            flags.append('INVALID_LABEL_MEASUREMENT')
    if not region_ids:
        flags.append('NO_NAMED_ATLAS_LABELS')
    if isinstance(worker_qc, dict) and isinstance(worker_qc.get('label_count'), int):
        if worker_qc['label_count'] != len(region_ids):
            flags.append('REGION_COUNT_DIFFERS_FROM_WORKER_QC')
    return {'state': 'ARITHMETIC_REVIEW_REQUIRED' if flags else 'ARITHMETIC_CONSISTENT_NOT_ANATOMICAL_QC',
            'flags': sorted(set(flags)), 'region_count': len(region_ids),
            'total_discrete_label_volume_ml': round(volume_total, 6)}


def create_evidence(storage, entry, reviews):
    meta = package_metadata(storage, entry)
    hashes = meta.get('source_sha256') or {}
    image_hash = hashes.get('image', '')
    if not isinstance(image_hash, str) or not DIGEST.fullmatch(image_hash) or entry.get('image_sha256') != image_hash:
        raise HTTPException(503, 'source_digest_metadata_inconsistent')
    labels_hash = hashes.get('labels')
    labels_present = isinstance(labels_hash, str) and bool(DIGEST.fullmatch(labels_hash))
    worker_qc = meta.get('v5_technical_qc') if isinstance(meta.get('v5_technical_qc'), dict) else None
    counts = evaluate_measurements(meta.get('measurements'), meta.get('voxel_ml'), worker_qc)
    source = retained_provenance(storage, entry['id'], image_hash, labels_hash, meta.get('phase2b_alignment'))
    flags = list(counts['flags'])
    flags.extend(str(x) for x in (meta.get('quality_flags') or []) if isinstance(x, str))
    if worker_qc is None:
        flags.append('WORKER_TECHNICAL_QC_MISSING')
    else:
        flags.extend(str(x) for x in (worker_qc.get('warnings') or []) if isinstance(x, str))
    if not labels_present:
        flags.append('SEGMENTATION_LABELS_MISSING')
    if source['state'] != 'SOURCE_SHA256_VERIFIED':
        flags.append('RETAINED_SOURCE_NOT_VERIFIED')
    if labels_present and source.get('labels', {}).get('state') not in (
        'UPLOADED_AND_PACKAGED_LABEL_SHA256_VERIFIED',
        'ORIGINAL_AND_RESAMPLED_LABEL_SHA256_VERIFIED'
    ):
        flags.append('RETAINED_LABELS_NOT_FULLY_VERIFIED')
    note = reviews[-1] if reviews else None
    state = note.get('disposition', 'UNREVIEWED') if note else 'UNREVIEWED'
    if state not in ('UNREVIEWED', 'NEEDS_REVIEW', 'REJECTED'):
        state = 'NEEDS_REVIEW'
    return {
        'schema': 'BAINP_PHASE2C_QC_EVIDENCE_V1',
        'scan_id': entry['id'], 'research_cohort': meta.get('cohort'),
        'research_subject': meta.get('subject'), 'research_visit': meta.get('visit'),
        'package_sha256': entry['package_sha256'], 'package_integrity': 'SHA256_VERIFIED',
        'source_image_sha256': image_hash,
        'atlas_label_sha256': labels_hash if labels_present else None,
        'retained_input': source,
        'geometry': {'native_shape': meta.get('native_shape'), 'native_axes': meta.get('native_axes'),
                     'voxel_ml': meta.get('voxel_ml'), 'worker_verified_native_grid': bool(worker_qc),
                     'phase2b_alignment': meta.get('phase2b_alignment')},
        'technical_qc': worker_qc or {'state': 'NOT_RECORDED'},
        'atlas_measurements': counts, 'labels_present': labels_present,
        'quality_flags': sorted(set(flags)),
        'review': {'status': state, 'event_count': len(reviews),
                   'last_event': {k: note.get(k) for k in ('at','disposition','planes_inspected','alignment','boundaries','note')} if note else None},
        'neurotwin': {'identity_link': 'MUST_BE_VERIFIED_SEPARATELY',
                      'longitudinal_eligible': False, 'clinical_approval': False},
        'meaning': 'Geometric/arithmetic/source-integrity verification and research findings only. No anatomical acceptance, disease diagnosis, normative classification or validated longitudinal inference.',
    }


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_package_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    disposition: Literal['NEEDS_REVIEW', 'REJECTED']
    planes_inspected: list[Literal['axial','coronal','sagittal']] = Field(min_length=1,max_length=3)
    alignment: Literal['appears_aligned', 'concern', 'not_assessed']
    boundaries: Literal['appear_consistent', 'concern', 'not_assessed']
    note: str = Field(min_length=20, max_length=1000)
    acknowledged_research_only: Literal[True]

    @model_validator(mode='after')
    def valid(self):
        if len(set(self.planes_inspected)) != len(self.planes_inspected):
            raise ValueError('duplicate plane inspection')
        if not self.note.strip() or any(ord(c) < 32 and c not in '\n\t' for c in self.note):
            raise ValueError('invalid finding note')
        return self


def append_review(storage, sid, principal, payload, log_path):
    if log_path.is_symlink():
        raise HTTPException(503, 'review_log_path_unsafe')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file() and log_path.stat().st_size > MAX_REVIEW_BYTES - 4096:
        raise HTTPException(507, 'review_log_limit_reached')
    event = {'at': time.time(), 'account': str(principal.get('user_id', 'local')),
             'scan_id': sid, **payload.model_dump(exclude={'expected_package_sha256','acknowledged_research_only'})}
    raw = (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    fd = os.open(log_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        if os.write(fd, raw) != len(raw):
            raise OSError('Incomplete review log write')
        os.fsync(fd)
    finally:
        os.close(fd)
    return event


def register_routes(router, authenticated, scan_entry, read_review, review_log):
    """Use the existing account isolation and audit log trusted by NeuroTwin."""
    @router.get('/phase2c/evidence/{package_id}')
    def evidence(package_id: str, mode: Literal['active']='active', principal=Depends(authenticated)):
        storage, entry = scan_entry(principal, package_id)
        return create_evidence(storage, entry, read_review(storage, package_id))

    @router.post('/phase2c/reviews/{package_id}', status_code=201)
    def finding(package_id: str, payload: ReviewFinding, mode: Literal['active']='active', principal=Depends(authenticated)):
        storage, entry = scan_entry(principal, package_id)
        # Check integrity AND source metadata before accepting any audit event.
        prior = read_review(storage, package_id)
        create_evidence(storage, entry, prior)
        if prior and prior[-1].get('disposition') == 'REJECTED' and payload.disposition != 'REJECTED':
            raise HTTPException(409, 'rejected_package_cannot_be_reopened_by_user')
        if entry['package_sha256'] != payload.expected_package_sha256:
            raise HTTPException(409, 'package_changed_reload_before_review')
        event = append_review(storage, package_id, principal, payload, review_log(storage, package_id))
        return {'recorded': True, 'scan_id': package_id,
                'disposition': event['disposition'], 'clinical_approval': False,
                'longitudinal_eligible': False,
                'message': 'Research observation recorded. Independent anatomical review remains necessary.'}
