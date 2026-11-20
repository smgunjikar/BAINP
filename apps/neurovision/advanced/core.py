"""BAINP Imaging V5: explicit, non-diagnostic image measurements.

Pure computation; no account access, I/O, diagnosis, or implicit image registration.
All arrays use the voxel grid of the supplied image. Affine is in millimetres.
"""
from __future__ import annotations
import math
from typing import Any
import numpy as np


def voxel_volume_ml(affine: Any) -> float:
    a = np.asarray(affine, dtype=np.float64)
    if a.shape != (4, 4) or not np.isfinite(a).all() or not np.allclose(a[3], [0, 0, 0, 1], atol=1e-8):
        raise ValueError('INVALID_AFFINE')
    v = abs(float(np.linalg.det(a[:3, :3]))) / 1000.0
    if not math.isfinite(v) or v < 1e-7 or v > 10.0:
        raise ValueError('VOXEL_GEOMETRY_OUT_OF_SCOPE')
    return v


def exact_grid(a_shape, a_affine, b_shape, b_affine, tol=1e-4):
    if tuple(a_shape) != tuple(b_shape) or not np.allclose(a_affine, b_affine, atol=tol, rtol=0):
        raise ValueError('GRID_MISMATCH_REGISTRATION_REQUIRED')
    voxel_volume_ml(a_affine)
    return True


def discrete_labels(data, max_unique=512):
    arr = np.asarray(data)
    if arr.ndim != 3 or min(arr.shape) < 4 or not np.isfinite(arr).all():
        raise ValueError('INVALID_LABEL_VOLUME')
    if np.any(arr < 0) or not np.equal(arr, np.rint(arr)).all():
        raise ValueError('LABELS_MUST_BE_NONNEGATIVE_INTEGERS')
    vals = np.unique(arr)
    if len(vals) > max_unique or vals.max(initial=0) > 65535:
        raise ValueError('LABELS_NOT_A_DISCRETE_ATLAS')
    return arr.astype(np.int32, copy=False)


def region_volumes(labels, affine, names=None):
    arr = discrete_labels(labels)
    vv = voxel_volume_ml(affine)
    ids, counts = np.unique(arr, return_counts=True)
    names = names or {}
    return [{'label_id': int(k), 'label_name': str(names.get(str(int(k)), f'Unverified label {int(k)}')),
             'voxel_count': int(c), 'volume_ml': round(float(c) * vv, 6),
             'state': 'NATIVE_GRID_UNREVIEWED'} for k, c in zip(ids, counts) if k != 0]


def dice(a, b):
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    if a.shape != b.shape: raise ValueError('DICE_GEOMETRY_MISMATCH')
    total = int(a.sum()) + int(b.sum())
    return 1.0 if total == 0 else 2.0 * float(np.count_nonzero(a & b)) / total


def segmentation_qc(image, labels, affine, expected_min_fraction=0.005, expected_max_fraction=0.85):
    """Technical QC only. Never concludes atlas accuracy or authorizes clinical use."""
    im = np.asarray(image, dtype=np.float32)
    lab = discrete_labels(labels)
    if im.shape != lab.shape or not np.isfinite(im).all(): raise ValueError('MRI_LABEL_GEOMETRY_OR_VALUE_ERROR')
    vv = voxel_volume_ml(affine)
    fg = lab > 0
    frac = float(fg.mean())
    warnings = []
    if not fg.any(): warnings.append('EMPTY_SEGMENTATION')
    if frac < expected_min_fraction: warnings.append('VERY_SMALL_LABEL_FRACTION')
    if frac > expected_max_fraction: warnings.append('VERY_LARGE_LABEL_FRACTION')
    if any(np.any(np.take(fg, ix, axis=ax)) for ax in range(3) for ix in (0, -1)):
        warnings.append('SEGMENTATION_TOUCHES_VOLUME_BOUNDARY')
    vals = im[fg]
    if vals.size > 0 and float(np.std(vals)) < 1e-6: warnings.append('LOW_SIGNAL_VARIATION_WITHIN_LABELS')
    unique = np.unique(lab)
    if len(unique[unique > 0]) < 2: warnings.append('FEW_ANATOMICAL_LABELS')
    return {
        'state': 'TECHNICAL_QC_REVIEW_REQUIRED',
        'clinical_use_authorized': False,
        'human_anatomical_review': 'PENDING',
        'segmented_voxels': int(fg.sum()),
        'segmented_fraction': round(frac, 6),
        'segmented_native_grid_ml': round(float(fg.sum()) * vv, 6),
        'label_count': int((unique > 0).sum()),
        'warnings': warnings,
        'limitations': ['Automated technical heuristics cannot validate anatomical correctness.',
                        'Discrete voxel-count volumes can differ from upstream soft-volume estimates.',
                        'Atlas labels must be checked against the exact model and label dictionary.']
    }


def lesion_mask_metrics(binary_mask, affine, minimum_voxels=3):
    """Quantify PROVIDED lesion mask; never infer pathology from image intensity."""
    from scipy.ndimage import label
    x = np.asarray(binary_mask)
    if x.ndim != 3 or not np.isfinite(x).all() or not np.isin(x, [0, 1]).all():
        raise ValueError('PROVIDED_LESION_MASK_MUST_BE_BINARY_3D')
    vv = voxel_volume_ml(affine)
    conn, n = label(x.astype(bool))
    sizes = np.bincount(conn.ravel())[1:]
    kept = sorted([int(i) for i in sizes if i >= minimum_voxels], reverse=True)
    return {'state': 'PROVIDED_MASK_DESCRIPTIVE_NOT_VALIDATED',
            'lesion_voxels': int(np.count_nonzero(x)),
            'lesion_volume_ml': round(float(np.count_nonzero(x)) * vv, 6),
            'connected_components_at_least_minimum': len(kept),
            'component_volumes_ml': [round(k * vv, 6) for k in kept],
            'minimum_voxels': int(minimum_voxels),
            'clinical_use_authorized': False}


def pet_suvr(pet, roi, reference):
    p = np.asarray(pet, np.float64)
    r = np.asarray(roi)
    ref = np.asarray(reference)
    if p.ndim != 3 or p.shape != r.shape or p.shape != ref.shape:
        raise ValueError('PET_ROI_REFERENCE_SHAPES_DIFFER')
    if not np.isfinite(p).all() or (p < 0).any():
        raise ValueError('INVALID_PET_INTENSITY')
    if not np.isin(r, [0, 1]).all() or not np.isin(ref, [0, 1]).all():
        raise ValueError('PET_TARGET_AND_REFERENCE_MUST_BE_BINARY_MASKS')
    target, background = r > 0, ref > 0
    if not target.any() or not background.any() or np.any(target & background):
        raise ValueError('EMPTY_OR_OVERLAPPING_PET_REGIONS')
    denominator = float(np.mean(p[background]))
    if denominator <= 0: raise ValueError('ZERO_REFERENCE_UPTAKE')
    return {'suvr': float(np.mean(p[target]) / denominator),
            'target_mean': float(np.mean(p[target])), 'reference_mean': denominator,
            'state': 'DESCRIPTIVE_RESEARCH_ONLY', 'centiloid': None,
            'requires': 'PET and both masks must already share exactly the same physical grid.'}


def centiloid_from_validated_calibration(suvr, calibration):
    """Only an externally supplied pipeline-specific verified conversion is supported."""
    if calibration.get('status') != 'independently_validated' or not all(calibration.get(k) for k in
            ('source', 'tracer', 'reference_region', 'processing_pipeline', 'validation_id')):
        raise ValueError('CENTILOID_CALIBRATION_NOT_VERIFIED')
    slope, intercept = float(calibration['slope']), float(calibration['intercept'])
    if not all(map(math.isfinite, [slope, intercept, suvr])) or slope <= 0:
        raise ValueError('INVALID_CALIBRATION')
    return {'centiloid': slope * suvr + intercept, 'calibration': calibration,
            'state': 'CALCULATED_FROM_SUPPLIED_CALIBRATION_REQUIRES_INDEPENDENT_REVIEW',
            'clinical_use_authorized': False}


def paired_volumes(base_labels, base_affine, follow_labels, follow_affine, label_id):
    """Two native-grid observations; does NOT imply reliable longitudinal atrophy."""
    a, b = discrete_labels(base_labels), discrete_labels(follow_labels)
    k = int(label_id)
    if k <= 0: raise ValueError('LABEL_ID_MUST_BE_POSITIVE')
    va = float((a == k).sum()) * voxel_volume_ml(base_affine)
    vb = float((b == k).sum()) * voxel_volume_ml(follow_affine)
    return {'label_id': k, 'baseline_volume_ml': va, 'followup_volume_ml': vb,
            'delta_ml': vb - va, 'change_pct': (vb - va) / va * 100 if va > 0 else None,
            'state': 'UNHARMONIZED_OBSERVATIONS_NOT_ATROPHY',
            'requirements': ['Same participant verified', 'Acquisition comparability checked',
                             'Registration and segmentation repeatability assessed', 'Human QC review']}
