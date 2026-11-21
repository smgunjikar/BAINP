import sys,tempfile,json
from pathlib import Path
import numpy as np,nibabel as nib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from regional_mri import quantify
with tempfile.TemporaryDirectory() as d:
 root=Path(d);aff=np.diag([1.,2.,3.,1.]);img=nib.Nifti1Image(np.ones((3,3,3)),aff);img.header.set_xyzt_units('mm');img.to_filename(root/'image.nii')
 labels=np.zeros((3,3,3));labels[0]=1;seg=nib.Nifti1Image(labels,aff);seg.header.set_xyzt_units('mm');seg.to_filename(root/'labels.nii')
 r=quantify(root/'image.nii',root/'labels.nii',{'1':'synthetic region'},{});assert abs(r['regions'][0]['volume_mm3']-54)<1e-8
 try:quantify(root/'image.nii',root/'labels.nii',{},{});raise AssertionError('Unknown label passed')
 except ValueError:pass
 aff[0,3]=2;bad=nib.Nifti1Image(labels,aff);bad.header.set_xyzt_units('mm');bad.to_filename(root/'bad.nii')
 try:quantify(root/'image.nii',root/'bad.nii',{'1':'test'},{});raise AssertionError('Mismatch passed')
 except ValueError:pass
print('PASS synthetic physical regional volume, unknown label and affine mismatch.')
