import sys,tempfile,uuid,time,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'apps/neuroaccess/backend'))
from api import create_app
from accounts import password_hash
from fastapi.testclient import TestClient
h={'X-NeuroAccess-Request':'1'};pw='Testing health password 952!'
with tempfile.TemporaryDirectory() as d:
 app=create_app(d);ac=app.state.accounts
 with ac.connect() as c:
  for name in ['a','b']:c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),name+'@example.org',name,password_hash(pw),'user','active',time.time()))
 a,b=[TestClient(app,base_url='http://127.0.0.1:8000') for _ in range(2)]
 assert a.get('/api/auth/health').status_code==401
 for cli,name in [(a,'a'),(b,'b')]:assert cli.post('/api/login',json={'email':name+'@example.org','password':pw},headers=h).status_code==200
 body={'revision':0,'consent':True,'details':{'allergies':'Test only','height_cm':'180'}}
 assert a.put('/api/auth/health',json=body,headers=h).status_code==200
 assert b.get('/api/auth/health').json()['details']=={}
 assert a.get('/api/auth/health').json()['details']['allergies']=='Test only'
 assert a.put('/api/auth/health',json=body,headers=h).status_code==409
 assert a.put('/api/auth/health',json={**body,'revision':1,'consent':False},headers=h).status_code==422
 assert a.put('/api/auth/health',json={**body,'revision':1,'details':{'height_cm':'nan'}},headers=h).status_code==422
 assert a.delete('/api/auth/health?revision=0',headers=h).status_code==409
 assert a.delete('/api/auth/health?revision=1',headers=h).status_code==200
 assert a.get('/api/auth/health').json()['details']=={}
print('PASS private health storage, consent, validation, stale write/delete protection and clearing')
spec=importlib.util.spec_from_file_location('policy',Path(__file__).parent/'payload/apps/neuroquest/backend/engine.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c=dict(profile=dict(language='en',can_see_and_respond='yes',assistance='none',vision_limitation=True,vision_aid='glasses'),intent=dict(functional_concern=False,concerns_checked=True,target_domain='none',quality_problem_addressed=False),registry=dict(protocol='test',core=['C01'],tasks=['C01']),history=[],consent=dict(history_allowed=True,assessment_allowed=True),guard=dict(state='workflow_permitted'),as_of='2026-11-15T12:00:00+00:00')
assert m.select(c)['action']=='baseline'
for ability in ['no','unsure']:
 c['profile']['can_see_and_respond']=ability;assert m.select(c)['action']=='abstain'
c['profile']['can_see_and_respond']='yes'
for aid in ['magnifier','other']:
 c['profile']['vision_aid']=aid;assert m.select(c)['action']=='abstain'
c['profile']['vision_aid']='glasses';c['consent']['assessment_allowed']=False;assert m.select(c)['action']=='abstain'
print('PASS recorded vision condition with glasses, unresolved access, modified aids and consent restriction')
