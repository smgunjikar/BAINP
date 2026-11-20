"""BAINP NeuroVision V4 research-only calculations; run in bainp-brain.

Requires numpy, scipy, nibabel. No clinical interpretation and no network access.
Usage: python Run-Research.py <subcommand> --help
"""
from __future__ import annotations
import argparse,csv,json,os,sys,hashlib,math,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from nv_analysis import (checked_grid,label_volumes,pet_suvr,
                         descriptive_reference,flair_signal_candidates,hash_file)

def emit(path,report):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise RuntimeError('Refusing to overwrite an existing research report')
 t=p.with_name(p.name+'.new')
 try:t.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8');os.replace(t,p)
 finally:t.unlink(missing_ok=True)

def image(path):
 import nibabel as nib
 p=Path(path)
 if not p.is_file() or p.suffix.lower() not in ('.nii','.gz','.mgz'):raise ValueError('Require an existing NIfTI/MGZ input file')
 obj=nib.load(str(p));data=obj.get_fdata(dtype='float32')
 if data.ndim!=3 or not __import__('numpy').isfinite(data).all():raise ValueError('Finite 3D scan required')
 return obj,data

def base(cmd,files):return {'schema':'BAINP-RESEARCH-V4','method':cmd,'review':'UNREVIEWED',
   'diagnosis':None,'input_sha256':{name:hash_file(Path(path)) for name,path in files.items()}}

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('volumes');a.add_argument('--labels',required=True);a.add_argument('--out',required=True)
 a=sub.add_parser('pet');a.add_argument('--pet',required=True);a.add_argument('--roi',required=True);a.add_argument('--reference',required=True);a.add_argument('--tracer',required=True);a.add_argument('--out',required=True)
 a=sub.add_parser('flair-outliers');a.add_argument('--flair',required=True);a.add_argument('--mask',required=True);a.add_argument('--out',required=True);a.add_argument('--map',required=True)
 a=sub.add_parser('reference');a.add_argument('--csv',required=True);a.add_argument('--age',required=True,type=float);a.add_argument('--region',required=True);a.add_argument('--volume-ml',required=True,type=float);a.add_argument('--group',default='all');a.add_argument('--out',required=True)
 a=sub.add_parser('tes-check');a.add_argument('--head-model',required=True);a.add_argument('--out',required=True)
 args=p.parse_args();files={};report=None
 if args.command=='volumes':
  x,v=image(args.labels);files={'labels':args.labels};report=base('native-grid-volumes',files)
  report['regions']=label_volumes(v,x.affine)
 elif args.command=='pet':
  pet,v=image(args.pet);target,t=image(args.roi);ref,r=image(args.reference)
  checked_grid(pet,target);checked_grid(pet,ref)
  files={'pet':args.pet,'roi':args.roi,'reference':args.reference};report=base('PET-SUVR',files)
  report.update(pet_suvr(v,t>0,r>0,pet.affine));report['tracer']=args.tracer
 elif args.command=='flair-outliers':
  import nibabel as nib
  flair,v=image(args.flair);mask,m=image(args.mask);checked_grid(flair,mask)
  voxel_ml=abs(float(__import__('numpy').linalg.det(flair.affine[:3,:3])))/1000
  binary,output=flair_signal_candidates(v,m>0,voxel_ml)
  report=base('FLAIR-signal-outliers',{'flair':args.flair,'mask':args.mask});report.update(output)
  if Path(args.map).exists():raise RuntimeError('Refusing to overwrite the existing candidate map')
  i=nib.Nifti1Image(binary.astype('uint8'),flair.affine,flair.header.copy());nib.save(i,args.map)
  report['output_candidate_map_sha256']=hash_file(Path(args.map))
 elif args.command=='reference':
  if not math.isfinite(args.age) or not math.isfinite(args.volume_ml) or args.volume_ml<0:raise ValueError('Bad age/volume')
  with open(args.csv,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
  report=base('reference-comparison',{'csv':args.csv});report.update(descriptive_reference(args.volume_ml,args.age,rows,args.region,args.group))
  report['measurement']={'region':args.region,'volume_ml':args.volume_ml,'age':args.age,'group':args.group}
 elif args.command=='tes-check':
  folder=Path(args.head_model)
  if not folder.is_dir():raise ValueError('A generated SimNIBS head-model directory is required')
  meshes=list(folder.glob('*.msh'))
  report=base('SimNIBS-readiness',{});report.update({'head_model_folder':str(folder),
        'mesh_count':len(meshes),'simnibs_executable':bool(shutil.which('simnibs')),
        'state':'READY_FOR_SPECIALIST_REVIEW' if meshes and shutil.which('simnibs') else 'NOT_READY',
        'electric_field':None,'treatment_recommendation':None})
 emit(args.out,report)
 print('BAINP research report saved. No clinical conclusion. Output:',args.out)
if __name__=='__main__':main()
