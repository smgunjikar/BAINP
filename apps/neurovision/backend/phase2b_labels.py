"""World-coordinate alignment of an externally produced SynthSeg discrete labelmap.

Research only; geometry QC is not anatomical QC. Source images are never overwritten.
"""
from pathlib import Path
import hashlib
import math
import os
import numpy as np

def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()

def assess_arrays(src_shape,src_affine,lab_array,lab_affine):
 """Check arrays before a potentially large resampling operation."""
 arr=np.asarray(lab_array)
 if arr.ndim!=3 or min(arr.shape)<4 or arr.size>64000000:
  raise ValueError('PHASE2B_INVALID_LABEL_DIMENSIONS')
 if not np.isfinite(arr).all() or np.any(arr<0) or not np.equal(arr,np.rint(arr)).all():
  raise ValueError('PHASE2B_LABELS_ARE_NOT_DISCRETE_NONNEGATIVE_INTEGERS')
 if float(np.max(arr))>65535 or len(np.unique(arr))>512 or np.count_nonzero(arr)==0:
  raise ValueError('PHASE2B_INVALID_ATLAS_IDS_OR_EMPTY')
 if len(src_shape)!=3 or np.prod(src_shape)>64000000:
  raise ValueError('PHASE2B_INVALID_SOURCE_DIMENSIONS')
 for affine in (src_affine,lab_affine):
  a=np.asarray(affine)
  if a.shape!=(4,4) or not np.isfinite(a).all() or abs(np.linalg.det(a[:3,:3]))<1e-8:
   raise ValueError('PHASE2B_INVALID_SPATIAL_AFFINE')
 return np.asarray(arr,dtype=np.int32)

def volume_difference(source_count,source_affine,target_count,target_affine):
 src=float(source_count)*abs(float(np.linalg.det(source_affine[:3,:3])))
 dst=float(target_count)*abs(float(np.linalg.det(target_affine[:3,:3])))
 if src<=0:raise ValueError('PHASE2B_EMPTY_ORIGINAL_LABELS')
 return 100*abs(dst-src)/src

def align_synthseg_labels(source_path,label_path,output_path):
 import nibabel as nib
 from nibabel.processing import resample_from_to
 source_path=Path(source_path);label_path=Path(label_path);output_path=Path(output_path)
 if source_path.resolve() in (label_path.resolve(),output_path.resolve()) or label_path.resolve()==output_path.resolve():
  raise ValueError('PHASE2B_SOURCE_AND_LABELS_MUST_BE_DIFFERENT_FILES')
 src=nib.load(str(source_path));lab=nib.load(str(label_path))
 if src.header.get_xyzt_units()[0]!='mm' or lab.header.get_xyzt_units()[0]!='mm':
  raise ValueError('PHASE2B_SPATIAL_UNITS_MUST_BE_MM')
 orig=assess_arrays(src.shape,src.affine,np.asarray(lab.dataobj),lab.affine)
 if tuple(src.shape)==tuple(lab.shape) and np.allclose(src.affine,lab.affine,atol=1e-4,rtol=0):
  aligned=orig.copy();method='already_same_native_grid'
 else:
  x=resample_from_to(lab,(src.shape,src.affine),order=0,mode='constant',cval=0)
  aligned=np.asarray(x.dataobj)
  if not np.isfinite(aligned).all() or not np.equal(aligned,np.rint(aligned)).all():
   raise ValueError('PHASE2B_INTERPOLATION_CHANGED_DISCRETE_LABELS')
  aligned=aligned.astype(np.int32)
  method='affine_world_nearest_neighbor'
 ids_src=set(int(v) for v in np.unique(orig) if v)
 ids_dst=set(int(v) for v in np.unique(aligned) if v)
 if not ids_dst or not ids_src.issubset(ids_dst):
  raise ValueError('PHASE2B_LABELS_LOST_OR_NO_SPATIAL_OVERLAP')
 delta=volume_difference(np.count_nonzero(orig),lab.affine,np.count_nonzero(aligned),src.affine)
 if delta>5:
  raise ValueError(f'PHASE2B_REVIEW_GEOMETRIC_VOLUME_CHANGE_{delta:.2f}_PCT')
 output_path.parent.mkdir(parents=True,exist_ok=True)
 tmp=output_path.with_name(output_path.stem+'.partial.nii.gz')
 # A crashed job may leave a partial file; never mutate the original input.
 if tmp.exists():tmp.unlink()
 header=src.header.copy();header.set_data_dtype(np.int32)
 out=nib.Nifti1Image(aligned,src.affine,header=header)
 out.set_sform(src.affine,code=2)
 nib.save(out,str(tmp))
 check=nib.load(str(tmp))
 if check.shape!=src.shape or not np.allclose(check.affine,src.affine,atol=1e-4,rtol=0):
  tmp.unlink(missing_ok=True);raise ValueError('PHASE2B_OUTPUT_GEOMETRY_FAILED')
 os.replace(tmp,output_path)
 return {'state':'GEOMETRY_REVIEW_ONLY','method':method,
         'original_label_sha256':digest(label_path),'resampled_label_sha256':digest(output_path),
         'mri_sha256':digest(source_path),'label_count':len(ids_dst),
         'total_label_volume_difference_percent':round(delta,3),
         'original_grid_shape':list(lab.shape),'native_grid_shape':list(src.shape),
         'anatomical_qc':'NOT_PERFORMED','clinical_use_authorized':False,
         'limitations':'5 percent volume-change bound is an engineering safeguard, not an anatomical-accuracy threshold.'}
