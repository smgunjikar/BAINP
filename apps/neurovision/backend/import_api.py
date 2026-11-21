"""Authenticated bounded NIfTI upload queue; processing stays in research worker.
No arbitrary server path arguments and no research-to-live identity inference.
"""
import json,os,re,secrets,time,hashlib,shutil
from pathlib import Path
from datetime import date
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from fastapi import APIRouter,Depends,HTTPException,Request
MAX_BYTES=64*1024*1024
from nv_queue import root,jobs,save,storage_root
class ImportSpec(BaseModel):
 model_config=ConfigDict(extra='forbid')
 filename:str=Field(min_length=1,max_length=160)
 mask_filename:str=Field(default="",max_length=160)
 labels_filename:str=Field(default="",max_length=160)
 cohort:str=Field(min_length=1,max_length=80)
 subject:str=Field(min_length=1,max_length=80)
 visit:str=Field(min_length=1,max_length=80)
 modality:Literal['T1w','T2w','FLAIR','other-3D']
 protocol:str=Field(min_length=1,max_length=100)
 visit_date:str=''
 authorized:Literal[True]
 @model_validator(mode='after')
 def valid(self):
  if '/' in self.filename or '\\' in self.filename or not self.filename.lower().endswith(('.nii','.nii.gz')):raise ValueError('Select .nii or .nii.gz')
  for name in (self.mask_filename,self.labels_filename):
   if name and ('/' in name or '\\' in name or not name.lower().endswith(('.nii','.nii.gz'))):raise ValueError('Invalid segmentation filename')
  for s in [self.cohort,self.subject,self.visit,self.protocol]:
   if not s.strip() or any(ord(c)<32 for c in s):raise ValueError('Invalid metadata')
  if self.visit_date:date.fromisoformat(self.visit_date)
  return self
def job_path(identifier,principal):
 if not re.fullmatch('[0-9a-f]{32}',identifier):raise HTTPException(404,'import_not_found')
 p=jobs(storage_root(principal,'active'))/identifier/'job.json'
 if not p.exists():raise HTTPException(404,'import_not_found')
 return p
def worker_health():
 p=jobs()/'heartbeat.json'
 try:
  heartbeat=json.loads(p.read_text(encoding='utf-8'))
  online=0<=time.time()-float(heartbeat['time'])<15 and heartbeat.get('protocol')=='tenant-v2'
 except (OSError,ValueError,KeyError,TypeError):online=False
 return online

def queue_counts(principal):
 counts={k:0 for k in ('awaiting_upload','awaiting_overlays','queued','processing','complete','failed')}
 active_jobs=jobs(storage_root(principal,'active'))
 if not active_jobs.is_dir():return counts
 for p in active_jobs.glob('*/job.json'):
  try:
   state=json.loads(p.read_text(encoding='utf-8')).get('state')
   if state in counts:counts[state]+=1
  except (OSError,ValueError):continue
 return counts

class AttachExistingLabels(BaseModel):
 model_config=ConfigDict(extra='forbid')
 expected_source_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
 attested_same_research_acquisition:Literal[True]

class ReviewNote(BaseModel):
 model_config=ConfigDict(extra='forbid')
 disposition:Literal['NEEDS_REVIEW','REJECTED']
 note:str=Field(min_length=15,max_length=1000)

def scan_entry(principal, package_id):
 if not re.fullmatch(r'[0-9a-f]{24}',package_id):raise HTTPException(404,'scan_not_found')
 storage=storage_root(principal,'active')
 catalog=storage/'catalog.json'
 try: entries=json.loads(catalog.read_text(encoding='utf-8')) if catalog.is_file() else []
 except (ValueError,OSError):raise HTTPException(503,'catalog_unavailable')
 entry=next((x for x in entries if x.get('id')==package_id and x.get('synthetic') is False),None)
 if not entry:raise HTTPException(404,'scan_not_in_account')
 return storage,entry

def review_log(storage,package_id):
 return storage/'review_events'/ (package_id+'.jsonl')

def read_review(storage,package_id):
 path=review_log(storage,package_id)
 if not path.is_file():return []
 if path.stat().st_size>1024*1024:raise HTTPException(503,'review_log_requires_maintenance')
 try:return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
 except (OSError,ValueError):raise HTTPException(503,'review_log_unreadable')

def make_router(authenticated):
 r=APIRouter(prefix='/api/neurovision',dependencies=[Depends(authenticated)])
 @r.get('/import-worker')
 def status(mode:Literal['active']='active',principal=Depends(authenticated)):
  return {'online':worker_health(),'upload_limit_mb':64,'queue':queue_counts(principal),
          'worker_script':'apps\\neurovision\\Start-ImagingWorker.ps1',
          'note':'Run the separate local imaging worker in the bainp-brain conda environment.'}
 @r.post('/import-jobs',status_code=201)
 def create(spec:ImportSpec,mode:Literal['active'],principal=Depends(authenticated)):
  active_jobs=jobs(storage_root(principal,'active'))
  active_jobs.mkdir(parents=True,exist_ok=True)
  pending=0
  for p in active_jobs.glob('*/job.json'):
   if json.loads(p.read_text())['state'] in ['awaiting_upload','awaiting_overlays','queued','processing']:pending+=1
  if pending>=5:raise HTTPException(409,'five_imports_already_pending')
  identifier=secrets.token_hex(16);folder=active_jobs/identifier;folder.mkdir()
  save(folder/'job.json',{'id':identifier,'state':'awaiting_upload','created_at':time.time(),'updated_at':time.time(),'spec':spec.model_dump(),'mode':'active'})
  return {'id':identifier,'state':'awaiting_upload'}
 @r.put('/import-jobs/{identifier}/image')
 async def upload(identifier:str,request:Request,mode:Literal['active']='active',principal=Depends(authenticated)):
  p=job_path(identifier,principal);job=json.loads(p.read_text())
  if job['state']!='awaiting_upload':raise HTTPException(409,'import_already_uploaded')
  # Exclusive file creation prevents overlapping uploads for the same job.
  tmp=p.parent/'source.upload'
  try:f=tmp.open('xb')
  except FileExistsError:raise HTTPException(409,'upload_already_in_progress')
  size=0;digest=hashlib.sha256()
  try:
   with f:
    async for block in request.stream():
     size+=len(block)
     if size>MAX_BYTES:raise HTTPException(413,'scan_exceeds_64_mb_use_local_import_script')
     f.write(block);digest.update(block)
   if size<32:raise HTTPException(422,'scan_is_empty_or_too_small')
   filename='source.nii.gz' if job['spec']['filename'].lower().endswith('.nii.gz') else 'source.nii'
   os.replace(tmp,p.parent/filename);extra=bool(job['spec'].get('mask_filename') or job['spec'].get('labels_filename'))
   state='awaiting_overlays' if extra else 'queued'
   job.update(state=state,updated_at=time.time(),source=filename,bytes=size,sha256=digest.hexdigest());save(p,job)
   return {'id':identifier,'state':state,'bytes':size}
  except BaseException:
   tmp.unlink(missing_ok=True);raise
 @r.put('/import-jobs/{identifier}/aux/{kind}')
 async def upload_aux(identifier:str,kind:Literal['mask','labels'],request:Request,mode:Literal['active']='active',principal=Depends(authenticated)):
  p=job_path(identifier,principal);job=json.loads(p.read_text(encoding='utf-8'))
  if job['state']!='awaiting_overlays':raise HTTPException(409,'overlay_upload_not_expected')
  if not job['spec'].get(kind+'_filename'):raise HTTPException(422,'overlay_type_not_requested')
  if kind in job.get('aux',{}):raise HTTPException(409,'overlay_already_uploaded')
  temp=p.parent/(kind+'.upload')
  try:f=temp.open('xb')
  except FileExistsError:raise HTTPException(409,'overlay_upload_in_progress')
  total=0;digest=hashlib.sha256()
  try:
   with f:
    async for block in request.stream():
     total+=len(block)
     if total>MAX_BYTES:raise HTTPException(413,'overlay_exceeds_64mb')
     f.write(block);digest.update(block)
   if total<32:raise HTTPException(422,'overlay_empty_or_too_small')
   # Never permit the MRI intensity file to masquerade as a mask or atlas,
   # nor the same file to be declared as both mask and segmentation labels.
   if digest.hexdigest()==job.get('sha256'):
    raise HTTPException(422,'auxiliary_file_identical_to_mri_select_actual_binary_mask_or_atlas')
   if any(item.get('sha256')==digest.hexdigest() for item in job.get('aux',{}).values()):
    raise HTTPException(422,'duplicate_mask_and_label_file_not_allowed')
   name=kind+('.nii.gz' if job['spec'][kind+'_filename'].lower().endswith('.nii.gz') else '.nii')
   os.replace(temp,p.parent/name)
   job.setdefault('aux',{})[kind]={'source':name,'bytes':total,'sha256':digest.hexdigest()}
   job['updated_at']=time.time();save(p,job)
   return {'id':identifier,'kind':kind,'bytes':total,'state':'awaiting_overlays'}
  except BaseException:
   temp.unlink(missing_ok=True);raise
 @r.post('/import-jobs/{identifier}/finalize')
 def finalize(identifier:str,mode:Literal['active']='active',principal=Depends(authenticated)):
  p=job_path(identifier,principal);job=json.loads(p.read_text(encoding='utf-8'))
  if job['state']!='awaiting_overlays':raise HTTPException(409,'not_awaiting_overlays')
  for kind in ('mask','labels'):
   if job['spec'].get(kind+'_filename') and kind not in job.get('aux',{}):
    raise HTTPException(409,'missing_'+kind+'_upload')
  job['state']='queued';job['updated_at']=time.time();save(p,job)
  return {'id':identifier,'state':'queued'}
 @r.post('/import-jobs/{identifier}/cancel')
 def cancel_incomplete(identifier:str,mode:Literal['active']='active',principal=Depends(authenticated)):
  p=job_path(identifier,principal);job=json.loads(p.read_text(encoding='utf-8'))
  if job['state'] not in ('awaiting_upload','awaiting_overlays'):
   raise HTTPException(409,'only_incomplete_uploads_can_be_cancelled')
  job['state']='cancelled';job['updated_at']=time.time();save(p,job)
  # Keep source bytes for audit; never remove or modify another participant's jobs.
  return {'id':identifier,'state':'cancelled'}
 @r.post('/import-jobs/refresh-package/{package_id}',status_code=201)
 def refresh_package(package_id:str,mode:Literal['active']='active',principal=Depends(authenticated)):
  if not re.fullmatch(r'[0-9a-f]{24}',package_id):raise HTTPException(404,'scan_not_found')
  storage=storage_root(principal,'active')
  catalog_file=storage/'catalog.json'
  items=json.loads(catalog_file.read_text(encoding='utf-8')) if catalog_file.exists() else []
  if not any(x.get('id')==package_id for x in items):raise HTTPException(404,'scan_not_in_account')
  previous=None
  active_jobs=jobs(storage)
  pending=0
  for p in active_jobs.glob('*/job.json'):
   try:
    job=json.loads(p.read_text(encoding='utf-8'))
    if job.get('state') in ('awaiting_upload','awaiting_overlays','queued','processing'):pending+=1
    if job.get('package_id')==package_id and job.get('state')=='complete':previous=(p,job)
   except (OSError,ValueError):continue
  if pending>=5:raise HTTPException(409,'five_imports_already_pending')
  if not previous:raise HTTPException(409,'original_upload_not_available_for_refresh')
  original,job=previous
  source=original.parent/job['source']
  if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=job['sha256']:
   raise HTTPException(409,'original_scan_integrity_error')
  identifier=secrets.token_hex(16);folder=active_jobs/identifier;folder.mkdir(parents=True,exist_ok=False)
  try:
   shutil.copy2(source,folder/job['source'])
   for kind,obj in job.get('aux',{}).items():
    old=original.parent/obj['source']
    if not old.is_file() or hashlib.sha256(old.read_bytes()).hexdigest()!=obj['sha256']:
     raise HTTPException(409,'original_'+kind+'_integrity_error')
    shutil.copy2(old,folder/obj['source'])
   next_job={k:v for k,v in job.items() if k not in ('id','state','package_id','error')}
   next_job.update(id=identifier,state='queued',created_at=time.time(),updated_at=time.time(),refresh_of=original.parent.name)
   save(folder/'job.json',next_job)
  except BaseException:
   shutil.rmtree(folder,ignore_errors=True);raise
  return {'id':identifier,'state':'queued','reason':'rebuild_with_current_engine'}
 @r.get('/analysis-capabilities')
 def analysis_capabilities(mode:Literal['active']='active',principal=Depends(authenticated)):
  # The worker reports capabilities from ITS Python process; the API must not guess.
  heartbeat=jobs()/'heartbeat.json'
  try:
   entry=json.loads(heartbeat.read_text(encoding='utf-8'))
   active=(time.time()-float(entry['time'])<15 and entry.get('protocol')=='tenant-v2')
  except (OSError,ValueError,KeyError,TypeError):entry={};active=False
  compatible=bool(active and entry.get('analysis_version')=='v5')
  return {'worker_online':active,'worker_compatible':compatible,
          'synthseg_installed':bool(compatible and entry.get('synthseg_available')),
          'wmh_synthseg_installed':bool(compatible and entry.get('wmh_synthseg_available')),
          'anatomical_segmentation':'RESTART_WORKER_WITH_V5' if active and not compatible else ('ready_unvalidated' if compatible and entry.get('synthseg_available') else 'model_not_available'),
          'automatic_lesion_diagnosis':'NOT_INSTALLED',
          'clinical_norms':'REQUIRES_VALIDATED_REFERENCE','pet_quantification':'REQUIRES_PET_AND_MASKS',
          'tes_fem':'REQUIRES_SIMNIBS_HEAD_MODEL_AND_SPECIALIST'}
 @r.post('/analysis-jobs/from-scan/{package_id}',status_code=201)
 def analyze_existing(package_id:str,model:Literal['synthseg','wmh-synthseg']='synthseg',mode:Literal['active']='active',principal=Depends(authenticated)):
  if not re.fullmatch(r'[0-9a-f]{24}',package_id):raise HTTPException(404,'scan_not_found')
  storage=storage_root(principal,'active');catalog=storage/'catalog.json'
  items=json.loads(catalog.read_text(encoding='utf-8')) if catalog.is_file() else []
  if not any(x.get('id')==package_id and x.get('synthetic') is False for x in items):
   raise HTTPException(404,'scan_not_in_own_workspace')
  health=analysis_capabilities(mode,principal)
  if not health['worker_online']:raise HTTPException(503,'IMAGING_WORKER_OFFLINE')
  if model=='synthseg' and not health['synthseg_installed']:raise HTTPException(503,'SYNTHSEG_NOT_INSTALLED_IN_BAINP_BRAIN')
  if model=='wmh-synthseg' and not health['wmh_synthseg_installed']:raise HTTPException(503,'WMH_SYNTHSEG_NOT_INSTALLED_IN_BAINP_BRAIN')
  pending=0;source_job=None
  for p in jobs(storage).glob('*/job.json'):
   try:job=json.loads(p.read_text(encoding='utf-8'))
   except (ValueError,OSError):continue
   if job.get('state') in ('awaiting_upload','awaiting_overlays','queued','processing'):pending+=1
   if job.get('package_id')==package_id and job.get('state')=='complete' and 'source' in job:source_job=(p,job)
  if pending>=5:raise HTTPException(409,'too_many_pending_jobs')
  if not source_job:raise HTTPException(409,'RETAINED_MRI_SOURCE_NOT_AVAILABLE')
  old,job=source_job;source=old.parent/job['source']
  if (not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=job['sha256']):
   raise HTTPException(409,'SOURCE_INTEGRITY_MISMATCH')
  identifier=secrets.token_hex(16);folder=jobs(storage)/identifier;folder.mkdir(parents=True,exist_ok=False)
  try:
   shutil.copy2(source,folder/job['source'])
   payload={k:v for k,v in job.items() if k not in ('id','state','package_id','error','aux','refresh_of')}
   payload.update(id=identifier,state='queued',created_at=time.time(),updated_at=time.time(),
                  analysis_pipeline=model,analysis_of=package_id)
   save(folder/'job.json',payload)
  except BaseException:shutil.rmtree(folder,ignore_errors=True);raise
  return {'id':identifier,'state':'queued','analysis':model,'research_only':True}
 @r.post('/import-jobs/from-scan/{package_id}/labels',status_code=201)
 def attach_labels(package_id:str,payload:AttachExistingLabels,mode:Literal['active']='active',principal=Depends(authenticated)):
  # No caller-provided filesystem paths; source is discovered by tenant + verified package.
  storage,entry=scan_entry(principal,package_id)
  if entry.get('image_sha256')!=payload.expected_source_sha256:
   raise HTTPException(409,'selected_mri_sha256_does_not_match_provided_reference')
  matches=[];pending=0
  for path in jobs(storage).glob('*/job.json'):
   try:j=json.loads(path.read_text(encoding='utf-8'))
   except (ValueError,OSError):continue
   if j.get('state') in ('awaiting_upload','awaiting_overlays','queued','processing'):pending+=1
   if (j.get('state')=='complete' and j.get('package_id')==package_id and
       j.get('sha256')==payload.expected_source_sha256 and j.get('source')):
    matches.append((path,j))
  if pending>=5:raise HTTPException(409,'five_imports_already_pending')
  if not matches:raise HTTPException(409,'retained_original_mri_unavailable_reimport_with_labels')
  old,source_job=max(matches,key=lambda p:p[1].get('created_at',0))
  original=old.parent/source_job['source']
  if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest()!=payload.expected_source_sha256:
   raise HTTPException(409,'retained_mri_integrity_failed')
  identifier=secrets.token_hex(16);folder=jobs(storage)/identifier
  folder.mkdir(parents=True,exist_ok=False)
  try:
   shutil.copy2(original,folder/source_job['source'])
   spec=dict(source_job['spec']);spec.update(mask_filename='',labels_filename='synthseg_labels.nii.gz')
   new={k:v for k,v in source_job.items() if k in ('source','sha256','bytes','mode')}
   new.update(id=identifier,state='awaiting_overlays',spec=spec,created_at=time.time(),updated_at=time.time(),
              analysis_pipeline='phase2b-external-synthseg',analysis_of=package_id,
              original_source_sha256=payload.expected_source_sha256,aux={})
   save(folder/'job.json',new)
  except BaseException:
   shutil.rmtree(folder,ignore_errors=True);raise
  return {'id':identifier,'state':'awaiting_overlays','research_only':True,'source_verified':True}
 @r.get('/import-jobs/reviews/{package_id}')
 def get_review(package_id:str,mode:Literal['active']='active',principal=Depends(authenticated)):
  storage,entry=scan_entry(principal,package_id)
  path=storage/(package_id+'.json')
  try:
   raw=path.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=entry['package_sha256']:raise ValueError('package digest mismatch')
   meta=json.loads(raw)['metadata']
  except (OSError,ValueError,KeyError):raise HTTPException(503,'scan_package_integrity_failed')
  history=read_review(storage,package_id)
  return {'scan_id':package_id,'review':history[-1]['disposition'] if history else 'UNREVIEWED',
          'notes_count':len(history),'technical_qc':meta.get('v5_technical_qc'),
          'geometric_qc':meta.get('phase2b_alignment'),
          'has_real_atlas_labels':bool(meta.get('source_sha256',{}).get('labels')),
          'neurotwin_trend_eligible':False,
          'note':'Technical and user review do not establish validated anatomical acceptance or longitudinal comparability.'}
 @r.post('/import-jobs/reviews/{package_id}')
 def add_review(package_id:str,payload:ReviewNote,mode:Literal['active']='active',principal=Depends(authenticated)):
  storage,entry=scan_entry(principal,package_id)
  if not entry.get('package_sha256'):raise HTTPException(409,'package_integrity_not_recorded')
  # Researcher and participant may flag an issue, but may not approve clinical anatomy.
  record={'at':time.time(),'account':str(principal.get('user_id','local')),
          'scan_id':package_id,'disposition':payload.disposition,'note':payload.note}
  path=review_log(storage,package_id);path.parent.mkdir(parents=True,exist_ok=True)
  fd=os.open(path,os.O_APPEND|os.O_CREAT|os.O_WRONLY,0o600)
  try:
   os.write(fd,(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))
   os.fsync(fd)
  finally:os.close(fd)
  return {'scan_id':package_id,'review':payload.disposition,'recorded':True,'neurotwin_trend_eligible':False}
 @r.get('/import-jobs/{identifier}')
 def get(identifier:str,mode:Literal['active']='active',principal=Depends(authenticated)):
  job=json.loads(job_path(identifier,principal).read_text());response={k:v for k,v in job.items() if k in ['id','state','error','package_id','bytes','created_at','updated_at']};response['worker_online']=worker_health();return response
 # Load the Phase 2C module from beside this API module, regardless of the
 # calling process's working directory or module search path.
 import importlib.util as _phase2c_import_util
 import sys as _phase2c_sys
 from pathlib import Path as _Phase2CPath
 _phase2c_path = _Phase2CPath(__file__).resolve().with_name('phase2c_qc.py')
 _phase2c_name = '_bainp_neurovision_phase2c_qc'
 _phase2c_mod = _phase2c_sys.modules.get(_phase2c_name)
 if _phase2c_mod is None:
  _phase2c_spec = _phase2c_import_util.spec_from_file_location(_phase2c_name, _phase2c_path)
  if _phase2c_spec is None or _phase2c_spec.loader is None:
   raise ImportError('Could not load Phase 2C from ' + str(_phase2c_path))
  _phase2c_mod = _phase2c_import_util.module_from_spec(_phase2c_spec)
  _phase2c_sys.modules[_phase2c_name] = _phase2c_mod
  try:
   _phase2c_spec.loader.exec_module(_phase2c_mod)
  except BaseException:
   _phase2c_sys.modules.pop(_phase2c_name, None)
   raise
 register_phase2c_routes = _phase2c_mod.register_routes
 register_phase2c_routes(r, authenticated, scan_entry, read_review, review_log)
 return r
