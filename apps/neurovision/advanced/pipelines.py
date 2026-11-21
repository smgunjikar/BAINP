"""Scientific-tool adapters. External binaries and model weights are user-installed.

All operations are local explicit CLI operations. NEVER expose arbitrary commands to HTTP.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from functools import lru_cache


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def read_nii(path):
    import nibabel as nib
    import numpy as np
    p = Path(path).resolve(strict=True)
    if not str(p).lower().endswith(('.nii', '.nii.gz')): raise ValueError('REQUIRES_NIFTI')
    image = nib.load(str(p))
    if len(image.shape) != 3 or min(image.shape) < 4 or max(image.shape) > 2048:
        raise ValueError('EXPECTED_3D_NIFTI')
    if image.header.get_xyzt_units()[0] != 'mm': raise ValueError('SPATIAL_UNITS_MUST_BE_MM')
    array = image.get_fdata(dtype=np.float32)
    if not np.isfinite(array).all(): raise ValueError('NON_FINITE_IMAGE')
    return image, array


def no_overwrite(path):
    p = Path(path)
    if p.exists(): raise FileExistsError('OUTPUT_EXISTS_REFUSING_OVERWRITE: ' + str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path, value):
    p = no_overwrite(path)
    with p.open('x', encoding='utf-8') as fh:
        json.dump(value, fh, indent=2, allow_nan=False)
    return p


def envelope(operation, paths, result):
    return {
        'schema': 'BAINP_NEUROIMAGING_RESEARCH_V5',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'operation': operation,
        'inputs_sha256': {key: digest(value) for key, value in paths.items()},
        'result': result,
        'data_type': 'RESEARCH_NOT_CLINICALLY_VALIDATED',
        'clinical_use_authorized': False,
        'regulatory_status': 'NO_BAINP_CLEARANCE_CLAIM',
        'source_provenance_required': True,
    }


def _wsl_prefix():
    if os.name != 'nt' or os.getenv('NEUROVISION_SYNTHSEG_WSL') != '1': return None
    if not shutil.which('wsl.exe'): return None
    distro = os.getenv('NEUROVISION_SYNTHSEG_DISTRO', 'Ubuntu')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,40}', distro): raise ValueError('INVALID_WSL_DISTRO')
    return ['wsl.exe', '--distribution', distro, '--exec']


def _wsl_path(prefix, p):
    run = subprocess.run(prefix + ['wslpath', '-a', '-u', str(Path(p).resolve())],
                         capture_output=True, text=True, timeout=20)
    if run.returncode or not run.stdout.strip().startswith('/'):
        raise RuntimeError('WSL_PATH_CONVERSION_FAILED')
    return run.stdout.strip()


@lru_cache(maxsize=2)
def freesurfer_model_ready(model):
    """Only reports whether an executable is found, never clinical model validity."""
    name={'synthseg':'mri_synthseg','wmh-synthseg':'mri_WMHsynthseg'}.get(model)
    if not name: return False
    if shutil.which(name): return True
    prefix=_wsl_prefix()
    if prefix is None: return False
    setup='if [ -n "${FREESURFER_HOME:-}" ] && [ -f "$FREESURFER_HOME/SetUpFreeSurfer.sh" ]; then . "$FREESURFER_HOME/SetUpFreeSurfer.sh"; fi; '
    try:
        run=subprocess.run(prefix+['bash','-lc',setup+'command -v '+name+' >/dev/null'],
                           capture_output=True,text=True,timeout=25)
        return run.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False


def run_freesurfer(model, source, output, timeout_sec=7200):
    """Run installed, documented FreeSurfer CLI. Does not download weights."""
    source = Path(source).resolve(strict=True)
    output = no_overwrite(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if model not in ('synthseg', 'wmh-synthseg'): raise ValueError('MODEL_NOT_ALLOWED')
    binary = {'synthseg': 'mri_synthseg', 'wmh-synthseg': 'mri_WMHsynthseg'}[model]
    exe = shutil.which(binary)
    prefix = _wsl_prefix() if exe is None else None
    extra = ['--vol', str(output.parent / 'seg_volumes.csv'), '--qc', str(output.parent / 'seg_qc.csv'), '--cpu'] if model == 'synthseg' else ['--csv_vols', str(output.parent / 'wmh_volumes.csv'), '--device', 'cpu']
    if exe:
        cmd = [exe, '--i', str(source), '--o', str(output)] + extra
    elif prefix:
        w_in = _wsl_path(prefix, source)
        w_out = _wsl_path(prefix, output)
        if model == 'synthseg':
            w_v = _wsl_path(prefix, output.parent / 'seg_volumes.csv')
            w_q = _wsl_path(prefix, output.parent / 'seg_qc.csv')
            args = [w_in, w_out, w_v, w_q]
            call = 'exec mri_synthseg --i "$1" --o "$2" --vol "$3" --qc "$4" --cpu'
        else:
            w_v = _wsl_path(prefix, output.parent / 'wmh_volumes.csv')
            args = [w_in, w_out, w_v]
            call = 'exec mri_WMHsynthseg --i "$1" --o "$2" --csv_vols "$3" --device cpu'
        setup = 'if [ -n "${FREESURFER_HOME:-}" ] && [ -f "$FREESURFER_HOME/SetUpFreeSurfer.sh" ]; then . "$FREESURFER_HOME/SetUpFreeSurfer.sh"; fi; '
        cmd = prefix + ['bash', '-lc', setup + call, 'bainp-v5', *args]
    else:
        raise RuntimeError(binary.upper() + '_NOT_INSTALLED: install official FreeSurfer and model weights; WSL2 is optional')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('MODEL_TIMEOUT') from exc
    # Do not write logs with arbitrary full commands or file paths to avoid sensitive name leakage.
    if run.returncode or not output.is_file():
        raise RuntimeError('MODEL_FAILED: exit=' + str(run.returncode) + ' · consult your local FreeSurfer logs')
    return {'tool': binary, 'output_sha256': digest(output),
            'source_sha256': digest(source), 'model_installed_and_executed': True,
            'review': 'ANATOMICAL_REVIEW_REQUIRED', 'clinical_use_authorized': False}


def resample_discrete_to_source(source, segmentation, destination):
    import nibabel as nib
    import numpy as np
    from nibabel.processing import resample_from_to
    from .core import discrete_labels
    src, _ = read_nii(source)
    seg, x = read_nii(segmentation)
    discrete_labels(x)
    if src.shape != seg.shape or not np.allclose(src.affine, seg.affine, atol=1e-4, rtol=0):
        seg = resample_from_to(seg, (src.shape, src.affine), order=0)
    native = discrete_labels(seg.get_fdata(dtype=np.float32))
    target = no_overwrite(destination)
    out = nib.Nifti1Image(native.astype(np.int32), src.affine, src.header.copy())
    out.header.set_xyzt_units('mm')
    nib.save(out, str(target))
    return {'native_segmentation_sha256': digest(target), 'label_count': len(np.unique(native)) - int(0 in native),
            'resampling': 'NEAREST_NEIGHBOR_WHEN_NEEDED', 'qc_required': True}


def rigid_registration(fixed, moving, output_dir, baseline_mask=None, followup_mask=None):
    """3D rigid registration; research only, NOT a validated longitudinal atrophy model."""
    import SimpleITK as sitk
    import numpy as np
    from .core import paired_volumes, dice, exact_grid
    output_dir = Path(output_dir).resolve()
    if output_dir.exists(): raise FileExistsError('OUTPUT_DIRECTORY_ALREADY_EXISTS')
    output_dir.mkdir(parents=True)
    fixed_img, moving_img = sitk.ReadImage(str(fixed)), sitk.ReadImage(str(moving))
    if fixed_img.GetDimension() != 3 or moving_img.GetDimension() != 3:
        raise ValueError('EXPECTED_3D_IMAGES')
    init = sitk.CenteredTransformInitializer(fixed_img, moving_img, sitk.Euler3DTransform(),
                                            sitk.CenteredTransformInitializerFilter.GEOMETRY)
    r = sitk.ImageRegistrationMethod()
    r.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)
    r.SetMetricSamplingStrategy(r.RANDOM)
    r.SetMetricSamplingPercentage(0.2, seed=42)
    r.SetInterpolator(sitk.sitkLinear)
    r.SetOptimizerAsGradientDescent(learningRate=1.0, numberOfIterations=100,
                                    convergenceMinimumValue=1e-6, convergenceWindowSize=10)
    r.SetOptimizerScalesFromPhysicalShift()
    r.SetInitialTransform(init, inPlace=False)
    transform = r.Execute(sitk.Cast(fixed_img, sitk.sitkFloat32), sitk.Cast(moving_img, sitk.sitkFloat32))
    sitk.WriteTransform(transform, str(output_dir / 'rigid.tfm'))
    resampled = sitk.Resample(moving_img, fixed_img, transform, sitk.sitkLinear, 0.0, moving_img.GetPixelID())
    sitk.WriteImage(resampled, str(output_dir / 'followup_registered.nii.gz'))
    result = {'state': 'RESEARCH_RIGID_ALIGNMENT_NOT_LONGITUDINAL_VALIDATION',
              'registration_metric': float(r.GetMetricValue()), 'stop_condition': str(r.GetOptimizerStopConditionDescription()),
              'transform_sha256': digest(output_dir / 'rigid.tfm'),
              'registered_image_sha256': digest(output_dir / 'followup_registered.nii.gz'),
              'longitudinal_atrophy_validated': False,
              'limitations': ['Rigid registration does not estimate tissue loss or prove comparability.',
                              'Scan protocol changes, harmonization and segmentation repeatability need independent QC.']}
    if baseline_mask and followup_mask:
        native_base, n_base = read_nii(baseline_mask)
        native_follow, n_follow = read_nii(followup_mask)
        fixed_native,_=read_nii(fixed);follow_native,_=read_nii(moving)
        exact_grid(fixed_native.shape,fixed_native.affine,native_base.shape,native_base.affine)
        exact_grid(follow_native.shape,follow_native.affine,native_follow.shape,native_follow.affine)
        if not np.isin(n_base, [0, 1]).all() or not np.isin(n_follow, [0, 1]).all():
            raise ValueError('MASKS_MUST_BE_BINARY')
        # Native measurement volumes remain native; resampled masks are ONLY for overlap QC.
        native = paired_volumes(n_base, native_base.affine, n_follow, native_follow.affine, label_id=1)
        b_ref = sitk.ReadImage(str(baseline_mask))
        f_mov = sitk.ReadImage(str(followup_mask))
        if b_ref.GetSize() != fixed_img.GetSize() or f_mov.GetSize() != moving_img.GetSize():
            raise ValueError('MASKS_MUST_MATCH_THEIR_RESPECTIVE_NATIVE_SCANS')
        f_reg = sitk.Resample(f_mov, fixed_img, transform, sitk.sitkNearestNeighbor, 0, f_mov.GetPixelID())
        sitk.WriteImage(f_reg, str(output_dir / 'followup_mask_registered.nii.gz'))
        a = sitk.GetArrayFromImage(b_ref) > 0
        b = sitk.GetArrayFromImage(f_reg) > 0
        result.update(native_volumes=native, mask_overlap_dice_after_registration=dice(a, b))
    return result


def external_simnibs_script(script, head_model, output_dir, confirmation=False, timeout_sec=7200):
    """Runs a LOCAL specialist-authored script using official SimNIBS Python.
    Script is executable Python. Deliberately not exposed over HTTP.
    No electrode placement or treatment dosing recommendations are generated.
    """
    if not confirmation: raise PermissionError('EXPLICIT_LOCAL_SCRIPT_EXECUTION_CONFIRMATION_REQUIRED')
    exe = shutil.which('simnibs_python')
    if exe is None: raise RuntimeError('SIMNIBS_PYTHON_NOT_INSTALLED')
    source = Path(script).resolve(strict=True)
    head = Path(head_model).resolve(strict=True)
    out = Path(output_dir).resolve()
    if source.suffix != '.py' or not head.is_dir() or not any(head.glob('*.msh')):
        raise ValueError('REQUIRES_AUDITED_LOCAL_PYTHON_SCRIPT_AND_GENERATED_SIMNIBS_MESH')
    if out.exists(): raise FileExistsError('OUTPUT_DIRECTORY_ALREADY_EXISTS')
    out.mkdir(parents=True)
    run = subprocess.run([exe, str(source)], cwd=str(out), capture_output=True, text=True, timeout=timeout_sec)
    (out / 'solver.stdout.log').write_text(run.stdout[-100000:], encoding='utf-8')
    (out / 'solver.stderr.log').write_text(run.stderr[-100000:], encoding='utf-8')
    if run.returncode: raise RuntimeError('SIMNIBS_FAILED_EXIT_' + str(run.returncode))
    produced = [str(p.relative_to(out)) for p in out.rglob('*.msh')]
    return {'state': 'RESEARCH_SOLVER_EXECUTED_REQUIRES_SPECIALIST_VALIDATION',
            'script_sha256': digest(source), 'mesh_count': len(produced),
            'outputs': produced, 'clinical_use_authorized': False,
            'no_treatment_recommendation': True}
