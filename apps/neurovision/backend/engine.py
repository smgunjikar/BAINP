"""NeuroVision imaging packages v1. Source images are read-only.
Native-grid measurements; resampled display images; explicit research provenance.
"""
import argparse,base64,csv,hashlib,json,os,platform,uuid
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import nibabel as nib
from scipy.ndimage import map_coordinates,gaussian_filter
from nibabel.processing import resample_to_output,resample_from_to
from skimage.measure import marching_cubes
from preview_geometry import preview
VERSION='neurovision-imaging-v2'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def dump(p,v):
 tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(v,allow_nan=False),encoding='utf-8');os.replace(tmp,p)
def load_image(p):
 im=nib.load(str(p));v=im.get_fdata(dtype=np.float32)
 if v.ndim!=3 or min(v.shape)<4 or not np.isfinite(v).all():raise ValueError('Require finite 3D image with dimensions >=4')
 if not np.isfinite(im.affine).all() or abs(np.linalg.det(im.affine[:3,:3]))<1e-9:raise ValueError('Invalid affine')
 units=im.header.get_xyzt_units()[0]
 if units!='mm':raise ValueError('Spatial unit must explicitly be mm; got '+units)
 return im,v

def make_package(image,mask,labels,meta,region_names=None):
 if type(meta.get('synthetic')) is not bool:raise ValueError('synthetic metadata must be boolean')
 for key in ['cohort','subject','visit','protocol','pipeline','review']:
  if not isinstance(meta.get(key),str) or not meta[key].strip():raise ValueError('Require nonempty metadata '+key)
 im,v=load_image(image);source_paths={'image':Path(image)};native_mask=None;lab=None
 def aligned(p):
  obj,x=load_image(p)
  if obj.shape!=im.shape or not np.allclose(obj.affine,im.affine,rtol=0,atol=1e-4):raise ValueError('Overlay native grid/affine mismatch; registration must be established upstream')
  return obj,x
 if mask:
  mi,mv=aligned(mask);source_paths['mask']=Path(mask)
  if not np.isin(mv,[0,1]).all() or not mv.any() or mv.all():raise ValueError('Require a nonempty binary brain mask')
  native_mask=mv>0
 if labels:
  li,lab=aligned(labels);source_paths['labels']=Path(labels)
  if np.any(lab<0) or np.any(lab>65535) or not np.equal(lab,np.round(lab)).all():raise ValueError('Require integer overlay labels 0..65535')
  if len(np.unique(lab))>512:raise ValueError('Too many distinct labels; verify the segmentation is a discrete atlas image')
  if native_mask is not None and np.any(lab[~native_mask]>0):raise ValueError('Labels outside supplied mask')
 hashes={k:sha(p) for k,p in source_paths.items()}
 voxel_ml=abs(float(np.linalg.det(im.affine[:3,:3])))/1000
 measurements=[]
 if native_mask is not None:measurements.append({'voxel_count':int(native_mask.sum()),'fraction_of_mask_percent':100.0,'id':'mask','name':'Brain-extraction mask','volume_ml':float(native_mask.sum()*voxel_ml),'status':'mask-derived; requires review'})
 label_ids=[]
 if lab is not None:
  label_ids=[int(k) for k in np.unique(lab) if k>0]
  for k in label_ids:
   if not k:continue
   measurements.append({'voxel_count':int(np.count_nonzero(lab==k)),'fraction_of_mask_percent':float(100*np.count_nonzero(lab==k)/native_mask.sum()) if native_mask is not None else None,'id':str(k),'name':(region_names or {}).get(str(k),'Unreviewed label '+str(k)),'volume_ml':float(np.count_nonzero(lab==k)*voxel_ml),'status':'Named upstream atlas label; independent anatomical QC required' if region_names else 'Unreviewed discrete label ID; anatomical structure not verified'})
 # Resample only for display to a physical RAS+ cardinal grid. No native measurements
 # are taken from the reduced display resolution.
 spacing=max(2.0,float(max(np.asarray(im.shape)*nib.affines.voxel_sizes(im.affine)))/120)
 display=resample_to_output(im,voxel_sizes=spacing,order=1);dv=display.get_fdata(dtype=np.float32)
 nonzero=v[v!=0];lo,hi=np.percentile(nonzero if len(nonzero) else v,[1,99]);hi=max(float(hi),float(lo)+1e-6)
 gray=np.clip((dv-lo)/(hi-lo)*255,0,255).astype(np.uint8)
 overlay=np.zeros(gray.shape,np.uint8)
 if lab is not None:
  # Display palette remaps arbitrary native atlas IDs; native IDs/volumes are unchanged.
  display_labels=resample_from_to(li,display,order=0).get_fdata().astype(np.int32)
  for idx,k in enumerate(label_ids):overlay[display_labels==k]=1+(idx%254)
 elif native_mask is not None:overlay=resample_from_to(mi,display,order=0).get_fdata().astype(np.uint8)
 display_mask=np.zeros(gray.shape,np.uint8)
 if native_mask is not None:display_mask=resample_from_to(mi,display,order=0).get_fdata().astype(np.uint8)
 surfaces=[]
 center=nib.affines.apply_affine(im.affine,(np.asarray(im.shape)-1)/2)
 boundary_fields=[]
 if native_mask is not None:boundary_fields.append((0,'MRI-derived brain mask',native_mask))
 if lab is not None:
  # Bounded top-volume mesh preview: all native label measurements remain available.
  surface_ids=sorted(label_ids,key=lambda k:int(np.count_nonzero(lab==k)),reverse=True)[:12]
  for k in surface_ids:boundary_fields.append((k,(region_names or {}).get(str(k),'Unreviewed label '+str(k)),lab==k))
 for k,name,binary in boundary_fields:
  if binary.sum()<8:continue
  # Native-grid boundary with a small display-only Gaussian smoothing.
  # Native voxel-count measurements are never computed from this mesh.
  field=gaussian_filter(np.pad(binary.astype(np.float32),1),sigma=.6)
  for step in (3,4,5,6,8):
   verts,faces,_,_=marching_cubes(field,level=.5,step_size=step,allow_degenerate=False)
   if len(faces)<=25000:break
  verts-=1
  intensity=map_coordinates(v,verts.T,order=1,mode='nearest')
  values=np.clip((intensity-lo)/(hi-lo),0,1)
  world=nib.affines.apply_affine(im.affine,verts)-center
  surfaces.append({'id':int(k),'name':name,'vertices_mm':np.round(world,2).tolist(),'center_mm':center.tolist(),'faces':faces.tolist(),'intensity':np.round(values,3).tolist(),'mesh_sampling_voxels':step})
 # Visualization-only fallback when no anatomical brain mask was supplied.
 preview_info=None
 if native_mask is None:
  # Never break a valid MRI import solely because a nonessential preview fails.
  if v.size<=24000000:
   try:preview_info=preview(v,im.affine,float(lo),float(hi))
   except (RuntimeError,ValueError,MemoryError):preview_info=None
  if preview_info:
   surfaces.insert(0,preview_info['surface'])
   measurements.insert(0,preview_info['measurement'])
 flags=[]
 if native_mask is None:flags.append('NO_BRAIN_MASK')
 if preview_info:flags.append('IMAGE_FOREGROUND_PREVIEW_NOT_ANATOMICAL')
 if native_mask is None and v.size>24000000:flags.append('PREVIEW_SKIPPED_RESOURCE_LIMIT')
 if lab is not None and len(label_ids)>12:flags.append('SURFACE_PREVIEW_SHOWS_ONLY_12_LARGEST_LABELS')
 if lab is None:flags.append('NO_SEGMENTATION_OVERLAY')
 if im.header['sform_code']==0 and im.header['qform_code']==0:flags.append('NO_EXPLICIT_SFORM_OR_QFORM')
 if native_mask is not None and any(np.any(np.take(native_mask,j,axis=i)) for i in range(3) for j in [0,-1]):flags.append('MASK_TOUCHES_VOLUME_EDGE')
 meta=dict(meta);meta.update({'version':VERSION,'source_sha256':hashes,'native_shape':list(im.shape),'native_affine':im.affine.tolist(),'native_axes':list(nib.aff2axcodes(im.affine)),'voxel_ml':voxel_ml,'display_shape':list(gray.shape),'display_affine':display.affine.tolist(),'display_spacing_mm':spacing,'intensity_window':[float(lo),hi],'quality_flags':flags,'measurements':measurements,'spatial_unit':'mm','surface_type':'native-grid mask/label boundary or image signal foreground preview; NOT cortical thickness','preview_method':preview_info['method'] if preview_info else None,'preview_cutoff':preview_info['cutoff'] if preview_info else None,'limitations':['No diagnosis or pathology inference.','Image foreground preview includes head/skull/scalp and is not an anatomical segmentation or brain volume.','Unknown label IDs are not verified anatomical structures; an upstream atlas dictionary and anatomical QC are required.','No cortical thickness, diffusion tractography, atlas registration or disease model is computed by this viewer.','Display resampling and smoothed mask surfaces are for visualization; measurements use native grids.','Header-based orientation requires independent anatomical verification.'],'software':{'python':platform.python_version(),'numpy':np.__version__,'nibabel':nib.__version__},'engine_sha256':sha(Path(__file__))})
 if hashes!={k:sha(p) for k,p in source_paths.items()}:raise RuntimeError('Inputs changed during preparation')
 return {'metadata':meta,'volume':base64.b64encode(gray.tobytes()).decode(),'overlay':base64.b64encode(overlay.tobytes()).decode(),'brain_mask':base64.b64encode(display_mask.tobytes()).decode(),'surfaces':surfaces}

def save_package(out,package):
 out.mkdir(parents=True,exist_ok=True);lock=out/'WRITE.lock'
 fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
 try:
  m=package['metadata'];identifier=hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()[:24]
  p=out/(identifier+'.json');dump(p,package)
  catalog=out/'catalog.json';items=json.loads(catalog.read_text()) if catalog.exists() else []
  entry={k:m.get(k) for k in ['cohort','subject','visit','date','protocol','pipeline','review','synthetic']};entry.update(id=identifier,package_sha256=sha(p),acquisition=m.get('acquisition',''),modality=m.get('modality','unspecified'),image_sha256=m.get('source_sha256',{}).get('image'))
  # Replace older viewer versions of the same exact image and research identity.
  retained=[]
  for x in items:
   same=all(x.get(k)==entry.get(k) for k in ['cohort','subject','visit'])
   old_hash=x.get('image_sha256')
   if same and old_hash is None:
    old_file=out/(x['id']+'.json')
    if old_file.exists():old_hash=json.loads(old_file.read_text())['metadata'].get('source_sha256',{}).get('image')
   if x['id']!=identifier and not (same and old_hash==entry['image_sha256']):retained.append(x)
  items=retained+[entry];dump(catalog,items)
  return identifier
 finally:lock.unlink()
def oasis(args):
 records=sorted(args.oasis_root.glob('*/*/complete.json'))
 if not records:raise ValueError('No complete.json acquisitions found at supplied OASIS output root')
 reviews={}
 if args.review_csv:
  with args.review_csv.open(encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    # Explicit session/acquisition key avoids cross-session review collisions.
    reviews[(r.get('session'),r.get('acquisition'))]=r.get('human_review','UNRECORDED')
 count=0;seen_visits=set()
 for done in records:
  visit=done.parent.parent.name
  if not args.all_acquisitions and visit in seen_visits:continue
  seen_visits.add(visit)
  if args.limit and count>=args.limit:break
  rec=json.loads(done.read_text());folder=done.parent
  expected=rec.get('output_sha256',{})
  required=['input_LAS.nii.gz','brain_bet.nii.gz','candidate_classes.nii.gz']
  for name in required:
   if name not in expected or sha(folder/name)!=expected[name]:raise ValueError('Processed artifact hash mismatch: '+str(folder/name))
  row=rec['row_snapshot'];review=reviews.get((row['session'],folder.name),'UNRECORDED')
  meta={'cohort':'OASIS-2','subject':row['subject'],'visit':row['session'],'date':None,'protocol':'unknown_acquisition_metadata','pipeline':rec['recipe']['script_sha256'],'review':review,'synthetic':False,'source_kind':'Processed authorized research acquisition','upstream_flags':rec.get('flags',[]),'upstream_manifest_sha256':sha(done),'upstream_recipe':rec['recipe'],'longitudinal_comparable':False,'acquisition':folder.name,'modality':'T1w'}
  package=make_package(folder/required[0],folder/required[1],folder/required[2],meta)
  key=save_package(args.out,package);count+=1;print('PREPARED:',row['session'],key,flush=True)
 print('PASS:',count,'packages. Catalog:',args.out/'catalog.json')
def demo(out):
 import tempfile
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp);x,y,z=np.mgrid[-1:1:48j,-1:1:56j,-1:1:48j];r=x*x/.7+y*y/.9+z*z/.8;mask=(r<.85).astype(np.uint8);labels=np.where(mask,np.where(r<.35,1,np.where(r<.65,2,3)),0).astype(np.uint8);v=(labels*40+mask*(20*np.cos(x*30)**2)).astype(np.float32)
  for name,data in [('image',v),('mask',mask),('labels',labels)]:
   im=nib.Nifti1Image(data,np.diag([3.,3.,3.,1.]));im.header.set_xyzt_units('mm');nib.save(im,p/(name+'.nii.gz'))
  for visit,date in [('fixture-1','2025-01-01'),('fixture-2','2026-01-01')]:
   pkg=make_package(p/'image.nii.gz',p/'mask.nii.gz',p/'labels.nii.gz',{'cohort':'SYNTHETIC','subject':'Fictional imaging phantom','visit':visit,'date':date,'protocol':'phantom-v1','pipeline':VERSION,'review':'SYNTHETIC_ONLY','synthetic':True,'longitudinal_comparable':False,'source_kind':'Mathematical phantom; NOT a human MRI'})
   save_package(out,pkg)
 print('PASS: synthetic phantom packages generated:',out)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['oasis','image','demo']);p.add_argument('--out',type=Path,required=True);p.add_argument('--oasis-root',type=Path);p.add_argument('--limit',type=int,default=8);p.add_argument('--all-acquisitions',action='store_true');p.add_argument('--review-csv',type=Path);p.add_argument('--image',type=Path);p.add_argument('--mask',type=Path);p.add_argument('--labels',type=Path);p.add_argument('--metadata',type=Path);p.add_argument('--lut',type=Path);a=p.parse_args()
 if a.limit<0:p.error('limit >=0 required')
 if a.action=='demo':demo(a.out)
 elif a.action=='oasis':
  if not a.oasis_root:p.error('--oasis-root required')
  oasis(a)
 else:
  if not a.image or not a.metadata:p.error('--image and --metadata required')
  meta=json.loads(a.metadata.read_text(encoding='utf-8-sig'))
  for k in ['cohort','subject','visit','protocol','pipeline','review','synthetic']:
   if k not in meta:raise ValueError('Missing metadata '+k)
  lut=json.loads(a.lut.read_text()) if a.lut else None
  print('PREPARED:',save_package(a.out,make_package(a.image,a.mask,a.labels,meta,lut)))
if __name__=='__main__':main()
