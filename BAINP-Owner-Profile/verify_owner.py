"""Run against extracted patched source with --project-root; uses temporary records only."""
import sys,tempfile,argparse,uuid
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,required=True);args=p.parse_args()
sys.path.insert(0,str(args.project_root/'apps/neuroaccess/backend'))
from api import create_app
from fastapi.testclient import TestClient
H={'X-NeuroAccess-Request':'1'}
profile=dict(display_name='Owner test',age=30,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
with tempfile.TemporaryDirectory() as d:
 app=create_app(d,'verification-only')
 with TestClient(app) as c:
  assert c.get('/api/owner-profile?mode=active').status_code==401
  assert c.post('/api/login',json={'password':'wrong'},headers=H).status_code==401
  assert c.post('/api/login',json={'password':'verification-only'},headers=H).status_code==200
  old=c.cookies.get('na_session')
  pid=str(uuid.uuid4())
  r=c.post('/api/participants',json={'id':pid,'mode':'active','profile':profile,'consent_to_store':True},headers=H)
  assert r.status_code==201,r.text
  rev=r.json()['revision']
  assert c.put('/api/owner-profile/'+pid+'?mode=demo',json={},headers=H).status_code==404
  assert c.put('/api/owner-profile/'+pid+'?mode=active',json={},headers=H).status_code==200
  assert c.get('/api/owner-profile?mode=active').json()['participant_id']==pid
  assert c.patch('/api/participants/'+pid+'?mode=active',json={'revision':rev,'profile':profile},headers=H).json()['revision']==rev
  changed={**profile,'reduced_motion':True}
  assert c.patch('/api/participants/'+pid+'?mode=active',json={'revision':rev,'profile':changed},headers=H).json()['revision']==rev+1
  assert c.post('/api/logout',json={},headers=H).status_code==200
  assert c.get('/api/session',headers={'Cookie':'na_session='+old}).status_code==401
  c.post('/api/login',json={'password':'verification-only'},headers=H);old=c.cookies.get('na_session')
  c.post('/api/login',json={'password':'verification-only'},headers=H)
  assert c.get('/api/session',headers={'Cookie':'na_session='+old}).status_code==401
 with TestClient(create_app(d,'verification-only')) as c:
  assert c.get('/api/session',headers={'Cookie':'na_session='+old}).status_code==401
  c.post('/api/login',json={'password':'verification-only'},headers=H)
  assert c.get('/api/owner-profile?mode=active').json()['participant_id']==pid
print('PASS: unauthorized access, wrong password, mode isolation, saved owner selection, no-op save, real edit, logout revocation, single session and restart persistence.')
