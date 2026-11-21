"""Read-only technical QC of frozen OASIS outputs; writes a separate report.
No automatic scientific approval, tissue identification, or training eligibility.
"""
import argparse,csv,hashlib,html,json,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import nibabel as nib

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def need(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data-root',type=Path,required=True);a=ap.parse_args()
 root=a.data_root.resolve();base=root/'derived/oasis2/experimental_batch_v1'
 need(base.is_dir(),'Batch directory missing');need(not (base/'RUNNING.lock').exists(),'Batch lock exists; confirm processing stopped before QC')
 with (root/'derived/oasis2/mri_review_queue_v1/acquisition_review_queue.csv').open(encoding='utf-8-sig',newline='') as f:queue=list(csv.DictReader(f))
 need(len(queue)==407,'Expected frozen 407-acquisition queue')
 out=root/'derived/oasis2'/('technical_qc_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
 rows=[];cards=[]
 for i,q in enumerate(queue,1):
  key=q['filename'].replace('.hdr','')+'_'+hashlib.sha256(q['relative_path'].encode()).hexdigest()[:10]
  folder=base/q['session']/key;r={'session':q['session'],'acquisition':key,'technical_status':'FAIL','human_review':'PENDING','notes':''}
  try:
   d=json.loads((folder/'complete.json').read_text(encoding='utf-8'));need(d['row_snapshot']==q,'Queue snapshot differs')
   required=['converted_native.nii.gz','input_LAS.nii.gz','brain.nii.gz','brain_bet.nii.gz','n4_corrected.nii.gz','log_bias_field.nii.gz','n4_brain_only.nii.gz','candidate_classes.nii.gz']+[f'class_{k}_probability.nii.gz' for k in (1,2,3)]+['review.png','mask_review.png','hd_bet.log']
   need(set(required)<=set(d['output_sha256']),'Incomplete output hash manifest')
   for rel,digest in {**d['input_sha256']}.items():
    p=(root/rel).resolve();need(p.is_relative_to(root/'raw'),'Invalid raw input path');need(p.is_file() and sha(p)==digest,'Input missing or hash changed: '+rel)
   for name,digest in d['output_sha256'].items():
    p=(folder/name).resolve();need(p.parent==folder.resolve(),'Invalid output path');need(p.is_file() and sha(p)==digest,'Output missing or hash changed: '+name)
   ref=nib.load(str(folder/'input_LAS.nii.gz'));need(len(ref.shape)==3,'Non-3D input');need(np.isfinite(ref.affine).all() and abs(np.linalg.det(ref.affine[:3,:3]))>0,'Invalid affine');need(nib.aff2axcodes(ref.affine)==('L','A','S'),'Unexpected axis codes')
   arrays={}
   for name in required:
    if name.endswith('.nii.gz') and name!='converted_native.nii.gz':
     im=nib.load(str(folder/name));need(im.shape==ref.shape and np.allclose(im.affine,ref.affine,rtol=0,atol=1e-5),'Geometry mismatch: '+name)
     v=im.get_fdata(dtype=np.float32);need(np.isfinite(v).all(),'Nonfinite voxels: '+name);arrays[name]=v
   mask=arrays['brain_bet.nii.gz'];need(np.isin(mask,[0,1]).all() and mask.any() and not mask.all(),'Invalid mask');m=mask==1
   need(np.array_equal(arrays['brain.nii.gz'],arrays['input_LAS.nii.gz']*m),'Extraction mismatch');need(np.array_equal(arrays['n4_brain_only.nii.gz'],arrays['n4_corrected.nii.gz']*m),'N4 mask mismatch')
   lab=arrays['candidate_classes.nii.gz'];need(np.isin(lab,[0,1,2,3]).all() and (lab[~m]==0).all() and (lab[m]>0).all(),'Invalid labels')
   probs=np.stack([arrays[f'class_{k}_probability.nii.gz'] for k in (1,2,3)]);need(probs.min()>=0 and probs.max()<=1 and np.max(abs(probs[:,m].sum(0)-1))<1e-4 and np.count_nonzero(probs[:,~m])==0,'Invalid probabilities')
   r.update(technical_status='CHECKS_PASSED_REVIEW_PENDING',mask_volume_ml=float(m.sum()*abs(np.linalg.det(ref.affine[:3,:3]))/1000),notes='; '.join(d.get('flags',[])))
  except Exception as e:r['notes']=str(e)
  rows.append(r);print(f'{i}/{len(queue)} {q["session"]}: {r["technical_status"]}',flush=True)
  esc=html.escape;links=' '.join(f'<a href="{esc((folder/n).as_uri(),quote=True)}">{label}</a>' for n,label in [('mask_review.png','Mask image'),('review.png','Candidate classes')])
  cards.append(f'<tr><td>{esc(r["session"])}</td><td>{esc(key)}</td><td>{esc(r["technical_status"])}</td><td>{esc(r["notes"])}</td><td>{links}</td></tr>')
 with (out/'acquisition_qc.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['session','acquisition','technical_status','human_review','notes','mask_volume_ml']);w.writeheader();w.writerows(rows)
 summary={'acquisitions':len(rows),'sessions':len({r['session'] for r in rows}),'technical_failures':sum(r['technical_status']=='FAIL' for r in rows),'human_review_pending':len(rows),'scientific_approval':False,'qc_script_sha256':sha(Path(__file__))}
 (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>OASIS QC</title><style>body{font:16px Arial;margin:30px}td,th{border:1px solid #aaa;padding:8px}table{border-collapse:collapse}a{margin:8px}</style><h1>OASIS technical QC and visual review</h1><p>All human reviews remain pending. Inspect mask exclusion of skull and inclusion of brain, clipping, artefacts and candidate class boundaries. Axis codes do not independently establish anatomical laterality. Candidate classes are not validated tissue identities. Record decisions in a separate reviewed copy of the CSV with reviewer, date and reasons. These checks grant no model eligibility.</p><table><tr><th>Session</th><th>Acquisition</th><th>Technical status</th><th>Notes</th><th>Review images</th></tr>'+''.join(cards)+'</table>',encoding='utf-8')
 print(json.dumps(summary,indent=2));print('REPORT:',out)
 return 1 if summary['technical_failures'] else 0
if __name__=='__main__':sys.exit(main())
