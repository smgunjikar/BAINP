"""Single-owner local imaging worker. Run with bainp-brain; no network listener."""
import argparse,json,os,time,sys,traceback,threading,math,re
import nibabel as nib
from pathlib import Path
from nv_queue import jobs,root,save
# Engine imports NumPy/nibabel/skimage only in this research process.
from engine import make_package,save_package,sha
from nv_analysis import segment_to_native, synthseg_available, REGIONS

def acquire():
 jobs().mkdir(parents=True,exist_ok=True);f=(jobs()/'worker.lock').open('a+b')
 f.seek(0);f.write(b'0');f.flush();f.seek(0)
 try:
  if os.name=='nt':
   import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  else:
   import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 except OSError:f.close();return None
 return f

def all_job_roots():
 yield root()
 workspaces=root()/'workspaces'
 if workspaces.is_dir():
  for directory in sorted(workspaces.iterdir()):
   if directory.is_dir() and not directory.is_symlink() and re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',directory.name):
    yield directory

def process(p,storage):
 job=json.loads(p.read_text())
 if job['state']!='queued':return
 job['state']='processing';job['updated_at']=time.time();save(p,job)
 try:
  source=p.parent/job['source']
  if sha(source)!=job['sha256']:raise ValueError('Uploaded file integrity check failed')
  probe=nib.load(str(source))
  if len(probe.shape)!=3 or math.prod(probe.shape)>64000000 or max(probe.shape)>1024:raise ValueError('Expected a 3D scan with at most 64 million voxels; use the local companion for larger data')
  spec=job['spec'];meta={k:spec[k] for k in ['cohort','subject','visit','modality','protocol']};meta.update(pipeline='authorized-browser-nifti-v1',review='UNRECORDED',synthetic=False,longitudinal_comparable=False,source_kind='Authorized browser NIfTI import')
  if spec['visit_date']:meta['date']=spec['visit_date']
  # Optional upstream masks and labelmaps must have identical native image geometry.
  aux=job.get('aux',{})
  mask=None;labels=None
  for kind in ('mask','labels'):
   name=aux.get(kind,{}).get('source')
   if not name:continue
   path=p.parent/name
   if not path.is_file() or sha(path)!=aux[kind]['sha256']:
    raise ValueError('Uploaded '+kind+' integrity check failed')
   if kind=='mask':mask=path
   else:labels=path
  lut=None
  if job.get('analysis_pipeline')=='phase2b-external-synthseg':
   supplied=labels
   if not supplied:raise ValueError('PHASE2B_SEGMENTATION_LABEL_FILE_MISSING')
   from phase2b_labels import align_synthseg_labels
   native=p.parent/'phase2b_labels_native.nii.gz'
   record=align_synthseg_labels(source,supplied,native)
   labels=native
   meta.update(pipeline='external-synthseg-supplied-unreviewed',
               phase2b_alignment=record,review='UNRECORDED',longitudinal_comparable=False,
               segmentation_source={'labels_original_sha256':sha(supplied),'source_mri_sha256':sha(source),
                                    'resampling':'world-coordinate-nearest-neighbor',
                                    'clinical_validation':False})
   lut=REGIONS
  if job.get('analysis_pipeline')=='wmh-synthseg':
   _project_root=__import__('pathlib').Path(__file__).resolve().parents[3]
   if str(_project_root) not in sys.path:sys.path.insert(0,str(_project_root))
   from apps.neurovision.advanced.pipelines import run_freesurfer,resample_discrete_to_source
   native=p.parent/'native_wmh_synthseg.nii.gz'
   upstream=p.parent/'wmh_synthseg_output.nii.gz'
   model_record=run_freesurfer('wmh-synthseg',source,upstream)
   native_record=resample_discrete_to_source(source,upstream,native)
   labels=native
   meta.update(pipeline='freesurfer-wmh-synthseg-external-model',
               segmentation_source={'model':model_record,'native':native_record},
               review='UNRECORDED',longitudinal_comparable=False,
               lesion_interpretation='UNVALIDATED_RESEARCH_WMH_LABELS')
   lut=dict(REGIONS)
   lut['77']='White matter hyperintensity (WMH) — unreviewed'
  if job.get('analysis_pipeline')=='synthseg':
   labels=p.parent/'native_synthseg.nii.gz'
   record=segment_to_native(source,labels,p.parent/'synthseg_work')
   meta.update(pipeline='freesurfer-synthseg-automated-research',
               segmentation_source=record,review='UNRECORDED',
               longitudinal_comparable=False)
   lut=REGIONS
  if labels is not None:
   # Native technical QC is a research metadata attachment; never auto-accept anatomy.
   # New V5 module is imported from the BAINP project root, not from the browser API.
   from pathlib import Path as _Path
   _project_root=_Path(__file__).resolve().parents[3]
   if str(_project_root) not in sys.path:sys.path.insert(0,str(_project_root))
   from apps.neurovision.advanced.core import segmentation_qc
   import numpy as np
   src_obj=nib.load(str(source));lab_obj=nib.load(str(labels))
   if src_obj.shape != lab_obj.shape or not np.allclose(src_obj.affine,lab_obj.affine,atol=1e-4,rtol=0):
    raise ValueError('SEGMENTATION_NATIVE_GEOMETRY_NOT_ALIGNED')
   meta['v5_technical_qc']=segmentation_qc(src_obj.get_fdata(dtype=np.float32),
                                          lab_obj.get_fdata(dtype=np.float32),src_obj.affine)
  package=make_package(source,mask,labels,meta,lut)
  job.update(state='complete',package_id=save_package(storage,package))
 except Exception as exc:
  job.update(state='failed',error=str(exc)[:240]);(p.parent/'processing_error.log').write_text(traceback.format_exc(),encoding='utf-8')
 job['updated_at']=time.time();save(p,job);print(job['id'],job['state'],flush=True)
 # Uploaded source retained outside Git for provenance/reprocessing; no source loss.

def wmh_ready():
 try:
  _project_root=__import__('pathlib').Path(__file__).resolve().parents[3]
  if str(_project_root) not in sys.path:sys.path.insert(0,str(_project_root))
  from apps.neurovision.advanced.pipelines import freesurfer_model_ready
  return freesurfer_model_ready('wmh-synthseg')
 except (ValueError,OSError,ImportError,RuntimeError):return False

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true');args=parser.parse_args();lock=acquire()
 if lock is None:print('NeuroVision import worker already running.');return
 print('NeuroVision worker ready. Import uploads remain local.',flush=True)
 stop=threading.Event()
 def heartbeat():
  # Sole heartbeat writer. Never race with the processing thread on Windows.
  while not stop.is_set():
   payload={'time':time.time(),'pid':os.getpid(),'protocol':'tenant-v2',
            'analysis_version':'v5','synthseg_available':synthseg_available(),
            'wmh_synthseg_available':wmh_ready()}
   for attempt in range(5):
    try:
     save(jobs()/'heartbeat.json',payload)
     break
    except (PermissionError,OSError) as exc:
     if attempt == 4:
      print('NeuroVision heartbeat write failed:',repr(exc),file=sys.stderr,flush=True)
     elif stop.wait(0.15*(attempt+1)):
      break
   stop.wait(2)
 thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
 # A held OS lock guarantees a prior processing owner is gone before recovery.
 for storage in all_job_roots():
  for p in jobs(storage).glob('*/job.json'):
   job=json.loads(p.read_text())
   if job['state']=='processing':job['state']='queued';save(p,job)
 try:
  while True:
   for storage in all_job_roots():
    for p in sorted(jobs(storage).glob('*/job.json')):
     try:process(p,storage)
     except Exception:traceback.print_exc()
   if not args.watch:break
   time.sleep(2)
 finally:
  stop.set()
  thread.join(timeout=5)
  lock.close()
  # Stale heartbeat is ignored by the API after its 15-second TTL.
  # Deletion causes WinError 32 if a Windows process is reading the file.

if __name__=='__main__':main()
