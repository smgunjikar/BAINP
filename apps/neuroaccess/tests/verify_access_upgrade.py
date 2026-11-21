"""Account isolation and onboarding regression; temporary fictional accounts only.
Run: python apps/neurocontinuum/tests/verify_continuity.py
Requires the existing account-enabled NeuroAccess host and its test dependencies.
"""
from pathlib import Path
import sys, tempfile, uuid, time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from api import create_app
from accounts import password_hash
from fastapi.testclient import TestClient
H={'X-NeuroAccess-Request':'1'}
PROFILE=dict(display_name='Fictional participant',age=40,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
checks=0
def expect(response,code):
 global checks
 assert response.status_code==code,(response.status_code,response.text)
 checks+=1
 return response.json()
with tempfile.TemporaryDirectory() as d:
 app=create_app(d);account=app.state.accounts;pw='Fictional test password 930!'
 with account.connect() as c:
  for name in ('first','second'):
   c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),name+'@example.org',name,password_hash(pw),'user','active',time.time()))
 clients=[TestClient(app,base_url='http://127.0.0.1:8000') for _ in range(3)]
 ids=[]
 for client,name in zip(clients,('first','second')):
  expect(client.post('/api/login',json={'email':name+'@example.org','password':pw},headers=H),200)
  pid=str(uuid.uuid4());ids.append(pid)
  expect(client.post('/api/participants',json={'id':pid,'mode':'active','profile':PROFILE,'consent_to_store':True},headers=H),201)
 a,b,anonymous=clients;pid=ids[0]
 base='/api/neurocontinuum/v1/participant-home/participants/'+pid
 expect(anonymous.get(base+'?mode=active'),401)
 expect(a.get(base+'?mode=active'),200)
 expect(b.get(base+'?mode=active'),404)
 expect(a.get(base+'?mode=demo'),403)
 body=dict(operation_id=str(uuid.uuid4()),expected_version=0,step='welcome',answer={'acknowledged':True})
 expect(b.put(base+'/onboarding?mode=active',json=body,headers=H),404)
 expect(a.put(base+'/onboarding?mode=active',json=body,headers=H),200)
 expect(a.put(base+'/onboarding?mode=active',json=body,headers=H),200) # same intent replay
 conflict={**body,'operation_id':str(uuid.uuid4())}
 expect(a.put(base+'/onboarding?mode=active',json=conflict,headers=H),409)
 skip={**body,'operation_id':str(uuid.uuid4()),'expected_version':1,'step':'concerns','answer':{'everyday_changes':'no'}}
 expect(a.put(base+'/onboarding?mode=active',json=skip,headers=H),409)
 for step,answer,revision in [('profile',{'profile_revision':1},1),('accessibility',{'profile_revision':1,'choice':'none'},2)]:
  expect(a.put(base+'/onboarding?mode=active',json=dict(operation_id=str(uuid.uuid4()),expected_version=revision,step=step,answer=answer),headers=H),200)
 data=expect(a.get(base+'?mode=active'),200)
 assert data['onboarding']['answers']['accessibility']['choice']=='none'
 assert data['workspace']['cases']==[]
 expect(b.get('/api/neurocontinuum/v1/participants/'+pid+'/next-action?mode=active'),404)
 expect(a.get('/api/auth/readiness/'+pid),200)
 expect(b.get('/api/auth/readiness/'+pid),404)
 expect(anonymous.get('/api/auth/readiness/'+pid),401)
 expect(a.get('/api/auth/readiness/'+pid+'?mode=demo'),403)
 payload={'revision':0,'consent':True,'details':{'blood_type':'unknown','wheelchair':'no'}}
 expect(a.put('/api/auth/health',json=payload,headers=H),200)
 data=expect(a.get('/api/auth/health'),200);assert data['details']['wheelchair']=='no'
 assert expect(b.get('/api/auth/health'),200)['details']=={}
 expect(a.put('/api/auth/health',json={**payload,'revision':1,'details':{'blood_type':'invalid'}},headers=H),422)
 expect(a.put('/api/auth/health',json={**payload,'revision':1,'details':{'wheelchair':'maybe'}},headers=H),422)
 print(f'PASS {checks} assertions including private readiness, health fields, explicit no and invalid choices.')
