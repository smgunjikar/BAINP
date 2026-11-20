#!/usr/bin/env python3
"""Prepare an original-grid SynthSeg label map for research review.

Requires numpy, scipy, nibabel. Does not modify original files.
No clinical validity is implied by successful geometry checks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mri', type=Path, required=True)
    p.add_argument('--labels', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    mri_path, label_path, out_dir = a.mri.resolve(), a.labels.resolve(), a.output_dir.resolve()
    for path in (mri_path, label_path):
        if not path.is_file():
            p.error(f'Input missing: {path}')
    if out_dir == mri_path.parent or out_dir == label_path.parent:
        p.error('Use a separate output directory, not an input directory')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_nii = out_dir / 'chris_t1_labels_native_grid.nii.gz'
    out_json = out_dir / 'alignment_qc.json'
    if out_nii.exists() or out_json.exists():
        p.error('Output already exists. Outputs are create-only; choose a new output directory.')

    mri = nib.load(str(mri_path))
    labels = nib.load(str(label_path))
    for name, image in [('MRI', mri), ('segmentation', labels)]:
        if len(image.shape) != 3:
            raise ValueError(f'{name} must be a 3D volume: {image.shape}')
        if not np.isfinite(image.affine).all() or abs(np.linalg.det(image.affine[:3, :3])) < 1e-8:
            raise ValueError(f'{name} has an invalid or singular affine')
    if np.prod(mri.shape) > 150_000_000:
        raise ValueError('Unusually large MRI; review resource limits before continuing')
    # These are native SynthSeg integer anatomical labels, not probabilities.
    native = np.asarray(labels.dataobj)
    if not np.isfinite(native).all() or not np.all(native == np.rint(native)):
        raise ValueError('Segmentation is not a finite integer label image')
    if np.min(native) < 0 or np.max(native) > np.iinfo(np.int32).max:
        raise ValueError('Segmentation has invalid label values')
    original_count = int(np.count_nonzero(native))
    if original_count == 0:
        raise ValueError('Segmentation contains no nonzero labels')

    # Convert by physical/world coordinate; nearest neighbor prevents label blending.
    aligned = resample_from_to(labels, (mri.shape, mri.affine), order=0, mode='constant', cval=0)
    aligned_array = np.asarray(aligned.dataobj)
    if not np.isfinite(aligned_array).all() or not np.all(aligned_array == np.rint(aligned_array)):
        raise ValueError('Resampling produced noninteger/nonfinite label data')
    aligned_array = aligned_array.astype(np.int32)
    result_count = int(np.count_nonzero(aligned_array))
    if result_count == 0:
        raise ValueError('Resampling produced an empty segmentation. Review affines.')

    src_mm3 = original_count * abs(float(np.linalg.det(labels.affine[:3, :3])))
    target_mm3 = result_count * abs(float(np.linalg.det(mri.affine[:3, :3])))
    delta_pct = 100.0 * abs(target_mm3 - src_mm3) / src_mm3
    # Conservative geometric acceptance gate; this is NOT anatomical accuracy QC.
    if delta_pct > 5.0:
        raise ValueError(f'Volume changed by {delta_pct:.2f}% after resampling; review before importing')
    src_ids = set(int(x) for x in np.unique(native) if x != 0)
    tgt_ids = set(int(x) for x in np.unique(aligned_array) if x != 0)
    missing_ids = sorted(src_ids - tgt_ids)
    if missing_ids:
        raise ValueError(f'Labels disappeared after resampling: {missing_ids}')

    hdr = mri.header.copy()
    hdr.set_data_dtype(np.int32)
    out = nib.Nifti1Image(aligned_array, mri.affine, header=hdr)
    out.set_qform(mri.get_qform(), code=int(mri.header['qform_code']))
    out.set_sform(mri.get_sform(), code=int(mri.header['sform_code']))
    # Preserve an explicit valid affine in case qform/sform codes were zero.
    if int(out.header['qform_code']) == 0 and int(out.header['sform_code']) == 0:
        out.set_sform(mri.affine, code=2)
    nib.save(out, str(out_nii))
    reloaded = nib.load(str(out_nii))
    if reloaded.shape != mri.shape or not np.allclose(reloaded.affine, mri.affine, atol=1e-5):
        out_nii.unlink(missing_ok=True)
        raise RuntimeError('Saved label image does not match MRI geometry')
    report = {
        'status': 'GEOMETRY_CHECK_PASSED_NOT_ANATOMICAL_QC',
        'mri_sha256': sha256(mri_path),
        'synthseg_sha256': sha256(label_path),
        'aligned_sha256': sha256(out_nii),
        'mri_shape': list(mri.shape),
        'segmentation_shape': list(labels.shape),
        'output_shape': list(reloaded.shape),
        'original_nonzero_labels': len(src_ids),
        'result_nonzero_labels': len(tgt_ids),
        'source_label_volume_mm3': round(src_mm3, 2),
        'resampled_label_volume_mm3': round(target_mm3, 2),
        'label_volume_difference_percent': round(delta_pct, 3),
        'resampling': 'nearest-neighbor; physical-coordinate affine mapping',
        'limitations': 'Geometric consistency only; anatomical segmentation accuracy and clinical validity not established',
    }
    with out_json.open('x', encoding='utf-8') as fp:
        json.dump(report, fp, indent=2)
    print(json.dumps(report, indent=2))
    print(f'ALIGNED LABELS: {out_nii}')
    print(f'QC REPORT: {out_json}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        sys.exit(1)
