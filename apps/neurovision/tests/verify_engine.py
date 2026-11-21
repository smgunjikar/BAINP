"""Synthetic checks only. Never opens or changes operator imaging records."""
import sys,tempfile,json,os,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import numpy as np
import nibabel as nib
from engine import make_package,save_package
from router import make_router
from fastapi import FastAPI,HTTPException,Request
from fastapi.testclient import TestClient
class ImagingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name);self.old=os.environ.get('NEUROVISION_DATA_DIR');os.environ['NEUROVISION_DATA_DIR']=str(self.p/'packages')
  mask=np.zeros((16,18,20),np.uint8);mask[3:12,4:14,5:16]=1;self.count=int(mask.sum());self.aff=np.diag([-2.,3.,4.,1.]);self.aff[0,3]=30
  for name,data in [('image',mask.astype(float)*80),('mask',mask),('labels',mask)]:
   im=nib.Nifti1Image(data,self.aff);im.header.set_xyzt_units('mm');nib.save(im,self.p/(name+'.nii.gz'))
  self.meta=dict(cohort='FIXTURE',subject='subject-1',visit='visit-1',date='2025-01-01',protocol='same',pipeline='same',review='APPROVED',synthetic=False,longitudinal_comparable=True)
 def tearDown(self):
  if self.old is None:os.environ.pop('NEUROVISION_DATA_DIR',None)
  else:os.environ['NEUROVISION_DATA_DIR']=self.old
  self.temp.cleanup()
 def package(self,meta=None):return make_package(self.p/'image.nii.gz',self.p/'mask.nii.gz',self.p/'labels.nii.gz',meta or self.meta)
 def test_native_volume_and_display(self):
  p=self.package();self.assertAlmostEqual(p['metadata']['measurements'][0]['volume_ml'],self.count*.024);self.assertEqual(p['metadata']['native_axes'],['L','A','S']);self.assertTrue(p['surfaces']);self.assertEqual(p['surfaces'][0]['id'],0);self.assertEqual(p['metadata']['measurements'][0]['voxel_count'],self.count);self.assertIn('brain_mask',p);self.assertEqual(list(nib.aff2axcodes(np.array(p['metadata']['display_affine']))),['R','A','S'])
 def test_repreparation_replaces_catalog_entry(self):
  root=self.p/'packages';save_package(root,self.package());save_package(root,self.package(dict(self.meta,review='REVIEWED_AGAIN')));self.assertEqual(len(json.loads((root/'catalog.json').read_text())),1)
 def test_misaligned_overlay_rejected(self):
  im=nib.load(self.p/'labels.nii.gz');a=self.aff.copy();a[0,3]+=1;nib.save(nib.Nifti1Image(im.get_fdata(),a,im.header),self.p/'labels.nii.gz')
  with self.assertRaisesRegex(ValueError,'grid'):self.package()
 def test_auth_modes_integrity_and_comparison(self):
  root=self.p/'packages';first=save_package(root,self.package());second=save_package(root,self.package(dict(self.meta,visit='visit-2',date='2026-01-01')))
  def auth(request:Request):
   if request.cookies.get('fixture')!='yes':raise HTTPException(401,'login_required')
  app=FastAPI();app.include_router(make_router(auth));c=TestClient(app)
  self.assertEqual(c.get('/api/neurovision/scans?mode=active').status_code,401);c.cookies.set('fixture','yes')
  self.assertEqual(len(c.get('/api/neurovision/scans?mode=active').json()['items']),2)
  self.assertEqual(c.get('/api/neurovision/scans/'+first+'?mode=demo').status_code,404)
  path=f'/api/neurovision/compare?mode=active&baseline={first}&followup={second}'
  self.assertEqual(c.get(path).json()['state'],'DESCRIPTIVE_DIFFERENCE_ONLY')
  # Same-visit acquisitions cannot masquerade as longitudinal followup.
  image=nib.load(self.p/'image.nii.gz');values=image.get_fdata();values[7,7,7]+=1;nib.save(nib.Nifti1Image(values,image.affine,image.header),self.p/'image.nii.gz')
  third=save_package(root,self.package(dict(self.meta,date='2026-01-01')))
  result=c.get(f'/api/neurovision/compare?mode=active&baseline={first}&followup={third}').json();self.assertIn('REPEATED_ACQUISITION_NOT_LONGITUDINAL_VISIT',result['reasons']);self.assertFalse(result['changes'])
  p=root/(first+'.json');p.write_text(p.read_text()+' ');self.assertEqual(c.get('/api/neurovision/scans/'+first+'?mode=active').status_code,409)
if __name__=='__main__':unittest.main(verbosity=2)
