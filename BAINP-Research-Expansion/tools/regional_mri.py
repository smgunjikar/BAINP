"""Quantify existing anatomical label maps; does not create or validate segmentation.
Dependencies: numpy, nibabel in your existing imaging environment.
Example: python regional_mri.py --image scan.nii.gz --labels atlas_labels.nii.gz --names names.json --atlas MyAtlas-v1 --pipeline MyPipeline --pipeline-version 1 --scanner ScannerA --acquisition-protocol T1-v1 --output regions.json
names.json maps positive integer label IDs to anatomical names. Use the label producer's actual dictionary.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import nibabel as nib

def quantify(image,labels,names,metadata):
 im=nib.load(str(image));seg=nib.load(str(labels))
 if len(im.shape)!=3 or seg.shape!=im.shape:raise ValueError('Require matching 3D images; no implicit resampling.')
 if not np.allclose(im.affine,seg.affine,rtol=0,atol=1e-5):raise ValueError('Affine mismatch: label alignment requires review.')
 if im.header.get_xyzt_units()[0]!='mm' or seg.header.get_xyzt_units()[0]!='mm':raise ValueError('Both image headers must explicitly use millimetres.')
 data=seg.get_fdata()
 if not np.isfinite(data).all() or not np.isfinite(im.get_fdata()).all():raise ValueError('Non-finite image/label data.')
 if np.any(data<0) or np.any(data!=np.floor(data)):raise ValueError('Label IDs must be nonnegative integers.')
 voxel=abs(float(np.linalg.det(im.affine[:3,:3])))
 if not 0<voxel<1000:raise ValueError('Implausible voxel volume; verify spatial units.')
 ids,counts=np.unique(data.astype(np.int64),return_counts=True);regions=[]
 for key,count in zip(ids,counts):
  if key==0:continue
  name=names.get(str(key))
  if not isinstance(name,str) or not name.strip():raise ValueError('Missing anatomical name for label '+str(key))
  regions.append({'label':int(key),'name':name,'volume_mm3':int(count)*voxel})
 if not regions:raise ValueError('No positive anatomical labels found.')
 def sha(p):
  h=hashlib.sha256()
  with Path(p).open('rb') as f:
   for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
  return h.hexdigest()
 return dict(metadata,schema='bainp-regional-volumes-v1',image_sha256=sha(image),labels_sha256=sha(labels),regions=regions,voxel_mm3=voxel,quality_status='requires_anatomical_review',clinical_use=False,limitations=['A matching header does not establish anatomical segmentation accuracy.','No model inference, norms, atrophy diagnosis, WMH, microbleed or PET analysis.'])
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['image','labels','names','output']:p.add_argument('--'+name,type=Path,required=True)
 for name in ['atlas','pipeline','pipeline-version','scanner','acquisition-protocol']:p.add_argument('--'+name,required=True)
 args=p.parse_args();result=quantify(args.image,args.labels,json.loads(args.names.read_text()),{k:getattr(args,k) for k in ['atlas','pipeline','pipeline_version','scanner','acquisition_protocol']})
 with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
 print('Saved regional measurements for anatomical review:',args.output)
