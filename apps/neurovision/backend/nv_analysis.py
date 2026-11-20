"""NeuroVision research processing, separated from the authenticated HTTP server.

No diagnosis, no clinical staging. Optional external SynthSeg model weights are NOT
bundled and are never downloaded implicitly. Results require anatomical review.
"""
from __future__ import annotations
import hashlib, math, os, shutil, subprocess, re
from functools import lru_cache
from pathlib import Path
import numpy as np

# FreeSurfer label dictionary subset; all other ids remain explicitly unverified.
REGIONS = {
 '2':'Left-Cerebral-White-Matter','3':'Left-Cerebral-Cortex',
 '4':'Left-Lateral-Ventricle','5':'Left-Inf-Lat-Vent',
 '7':'Left-Cerebellum-White-Matter','8':'Left-Cerebellum-Cortex',
 '10':'Left-Thalamus','11':'Left-Caudate','12':'Left-Putamen',
 '13':'Left-Pallidum','14':'Third-Ventricle','15':'Fourth-Ventricle',
 '16':'Brain-Stem','17':'Left-Hippocampus','18':'Left-Amygdala',
 '24':'CSF','26':'Left-Accumbens-area','28':'Left-VentralDC',
 '41':'Right-Cerebral-White-Matter','42':'Right-Cerebral-Cortex',
 '43':'Right-Lateral-Ventricle','44':'Right-Inf-Lat-Vent',
 '46':'Right-Cerebellum-White-Matter','47':'Right-Cerebellum-Cortex',
 '49':'Right-Thalamus','50':'Right-Caudate','51':'Right-Putamen',
 '52':'Right-Pallidum','53':'Right-Hippocampus','54':'Right-Amygdala',
 '58':'Right-Accumbens-area','60':'Right-VentralDC',
}

def hash_file(path:Path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def checked_grid(a,b,atol=1e-4):
 if a.shape != b.shape or not np.allclose(a.affine,b.affine,atol=atol,rtol=0):
  raise ValueError('GRID_MISMATCH: explicit same-grid coregistration is required')
 if not np.isfinite(a.affine).all() or abs(np.linalg.det(a.affine[:3,:3]))<1e-9:
  raise ValueError('INVALID_AFFINE')
 if a.header.get_xyzt_units()[0]!='mm' or b.header.get_xyzt_units()[0]!='mm':
  raise ValueError('SPATIAL_UNIT_NOT_MM')

def label_volumes(labels,affine):
 array=np.asarray(labels)
 if array.ndim!=3 or not np.isfinite(array).all() or np.any(array<0) or not np.equal(array,np.round(array)).all():
  raise ValueError('LABELS_MUST_BE_DISCRETE_NONNEGATIVE_3D')
 voxel_ml=abs(float(np.linalg.det(np.asarray(affine)[:3,:3])))/1000.0
 if not math.isfinite(voxel_ml) or voxel_ml<=0:raise ValueError('BAD_VOXEL_VOLUME')
 ids,counts=np.unique(array.astype(np.int64),return_counts=True)
 return [{'label_id':int(k),'region':REGIONS.get(str(int(k)),'Unverified label '+str(int(k))),
          'voxel_count':int(n),'volume_ml':float(n*voxel_ml),
          'quality':'UNREVIEWED'} for k,n in zip(ids,counts) if k>0]

def pet_suvr(pet,roi,reference,affine):
 """Descriptive mean PET target uptake / mean reference uptake, no Centiloid."""
 v=np.asarray(pet,dtype=np.float64);target=np.asarray(roi).astype(bool);ref=np.asarray(reference).astype(bool)
 if v.ndim!=3 or target.shape!=v.shape or ref.shape!=v.shape:raise ValueError('PET_MASK_GEOMETRY_MISMATCH')
 if not np.isfinite(v).all() or np.any(v<0) or not target.any() or not ref.any() or np.any(target & ref):
  raise ValueError('INVALID_PET_INPUTS_OR_OVERLAPPING_ROIS')
 denominator=float(np.mean(v[ref]))
 if denominator<=0:raise ValueError('PET_REFERENCE_ZERO')
 return {'suvr':float(np.mean(v[target])/denominator),
         'target_voxels':int(target.sum()),'reference_voxels':int(ref.sum()),
         'state':'DESCRIPTIVE_RESEARCH_ONLY','centiloid':None,
         'limitations':['Requires aligned PET/ROI/reference images and appropriate tracer protocol',
                        'No partial-volume correction or validated Centiloid calibration']}

def descriptive_reference(value,age,rows,region,group='all'):
 """Reference comparison only when documented, non-synthetic dataset is supplied."""
 candidates=[]
 for r in rows:
  try:
   if (r['region']==region and r.get('group','all')==group
       and float(r['age_min'])<=age<=float(r['age_max'])
       and int(r['n'])>=30 and r.get('synthetic','false').lower()=='false'
       and r.get('source') and r.get('protocol') and r.get('reference_version')
       and float(r['sd_ml'])>0):candidates.append(r)
  except (KeyError,TypeError,ValueError):continue
 if len(candidates)!=1:return {'state':'REFERENCE_UNAVAILABLE','z_score':None,'percentile':None}
 r=candidates[0];z=(float(value)-float(r['mean_ml']))/float(r['sd_ml'])
 return {'state':'DESCRIPTIVE_UNVALIDATED_REFERENCE','z_score':float(z),
         'percentile':50*(1+math.erf(z/math.sqrt(2))),
         'reference':{k:r[k] for k in ('source','reference_version','protocol','n','age_min','age_max')},
         'limitations':'Do not treat this as a diagnostic normative percentile without calibration and cohort comparability.'}

def flair_signal_candidates(flair,mask,voxel_ml,threshold=5.0,min_volume_ml=0.05):
 """Exploratory high-signal outliers, NOT a validated WMH/lesion detector."""
 from scipy.ndimage import label
 a=np.asarray(flair,dtype=np.float32);m=np.asarray(mask,dtype=bool)
 if a.ndim!=3 or a.shape!=m.shape or not m.any() or not np.isfinite(a).all():raise ValueError('FLAIR_AND_BRAIN_MASK_REQUIRED')
 vals=a[m];median=float(np.median(vals));mad=float(np.median(np.abs(vals-median)))
 if mad<=1e-7:raise ValueError('INSUFFICIENT_FLAIR_CONTRAST')
 score=(a-median)/(1.4826*mad)
 cc,n=label((score>=threshold)&m)
 minimum=max(3,math.ceil(min_volume_ml/voxel_ml));candidate=np.zeros(a.shape,dtype=np.uint8);volumes=[]
 for k in range(1,n+1):
  count=int((cc==k).sum())
  if count>=minimum:candidate[cc==k]=1;volumes.append(round(count*voxel_ml,5))
 return candidate,{'state':'EXPLORATORY_SIGNAL_OUTLIERS_NOT_LESIONS',
                   'candidate_count':len(volumes),'candidate_volumes_ml':volumes,
                   'algorithm':{'MAD_threshold':threshold,'min_volume_ml':min_volume_ml},
                   'interpretation':'Intensity outliers may be artifact, anatomy, or pathology. No disease inference.'}

def _wsl_prefix():
 if os.name!='nt' or os.environ.get('NEUROVISION_SYNTHSEG_WSL')!='1' or not shutil.which('wsl.exe'):
  return None
 distro=os.environ.get('NEUROVISION_SYNTHSEG_DISTRO','Ubuntu')
 if not re.fullmatch(r'[A-Za-z0-9_.-]{1,40}',distro):return None
 return ['wsl.exe','--distribution',distro,'--exec']

_WSL_SETUP='if [ -n "${FREESURFER_HOME:-}" ] && [ -f "$FREESURFER_HOME/SetUpFreeSurfer.sh" ]; then . "$FREESURFER_HOME/SetUpFreeSurfer.sh"; fi; '
@lru_cache(maxsize=1)
def synthseg_available():
 if shutil.which('mri_synthseg'):return True
 prefix=_wsl_prefix()
 if prefix is None:return False
 try:
  probe=subprocess.run(prefix+['bash','-lc',_WSL_SETUP+'command -v mri_synthseg >/dev/null'],
                       timeout=25,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  return probe.returncode==0
 except (OSError,subprocess.TimeoutExpired):return False

def _wslpath(prefix,path):
 result=subprocess.run(prefix+['wslpath','-a','-u',str(Path(path).resolve())],
                       timeout=15,capture_output=True,text=True)
 if result.returncode!=0 or not result.stdout.strip().startswith('/'):
  raise RuntimeError('WSL_PATH_CONVERSION_FAILED')
 return result.stdout.strip()

def segment_to_native(image:Path,output:Path,working:Path):
 """Run installed FreeSurfer SynthSeg, resample labels to MRI native grid with NN."""
 import nibabel as nib
 from nibabel.processing import resample_from_to
 exe=shutil.which('mri_synthseg')
 prefix=_wsl_prefix() if not exe else None
 if not exe and not (prefix and synthseg_available()):
  raise RuntimeError('SYNTHSEG_NOT_INSTALLED: FreeSurfer model unavailable. On Windows configure FreeSurfer under WSL2 and set NEUROVISION_SYNTHSEG_WSL=1 before starting the worker.')
 working.mkdir(parents=True,exist_ok=True)
 provisional=working/'synthseg_output.nii.gz';volumes_csv=working/'synthseg_volumes.csv';qc_csv=working/'synthseg_qc.csv'
 if exe:
  cmd=[exe,'--i',str(image),'--o',str(provisional),'--vol',str(volumes_csv),'--qc',str(qc_csv),'--cpu']
 else:
  src,out,vol,qc=(_wslpath(prefix,p) for p in (image,provisional,volumes_csv,qc_csv))
  command=_WSL_SETUP+'exec mri_synthseg --i "$1" --o "$2" --vol "$3" --qc "$4" --cpu'
  cmd=prefix+['bash','-lc',command,'bainp-synthseg',src,out,vol,qc]
 try:
  p=subprocess.run(cmd,check=False,timeout=7200,capture_output=True,text=True)
 except subprocess.TimeoutExpired as exc:raise RuntimeError('SYNTHSEG_TIMEOUT') from exc
 if p.returncode or not provisional.is_file():raise RuntimeError('SYNTHSEG_FAILED: inspect local worker log and model installation')
 original=nib.load(str(image));labels=nib.load(str(provisional));data=labels.get_fdata(dtype=np.float32)
 if data.ndim!=3 or not np.isfinite(data).all() or np.any(data<0):raise RuntimeError('SYNTHSEG_INVALID_LABELS')
 if original.shape!=labels.shape or not np.allclose(original.affine,labels.affine,atol=1e-4,rtol=0):
  labels=resample_from_to(labels,(original.shape,original.affine),order=0)
  data=labels.get_fdata(dtype=np.float32)
 if not np.equal(data,np.round(data)).all():raise RuntimeError('SYNTHSEG_LABELS_NOT_INTEGERS')
 if original.header.get_xyzt_units()[0]!='mm':raise RuntimeError('SOURCE_UNITS_NOT_MM')
 result=nib.Nifti1Image(data.astype(np.int16),original.affine,header=original.header.copy())
 result.header.set_xyzt_units('mm');nib.save(result,str(output))
 if not output.exists():raise RuntimeError('SEGMENTATION_SAVE_FAILED')
 return {'segmentation_sha256':hash_file(output),'tool':'FreeSurfer SynthSeg',
         'model_executable':'mri_synthseg (native)' if exe else 'mri_synthseg (WSL2)','upstream_volumes_csv':str(volumes_csv),
         'upstream_qc_csv':str(qc_csv),'status':'UNREVIEWED_RESEARCH_OUTPUT'}
