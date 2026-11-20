"""Run with the installed NeuroAccess environment. All records are temporary and fictional."""
from pathlib import Path
import sys,tempfile,uuid,time,json,io,sqlite3
from datetime import date
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from api import create_app,Profile
from accounts import password_hash
from fastapi.testclient import TestClient
H={'X-NeuroAccess-Request':'1'}
P=dict(display_name='Fictional User',age=40,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
count=0
def check(r,status):
 global count
 assert r.status_code==status,(status,r.status_code,r.text)
 count+=1
 return r.json()
today=date.today();dob=date(today.year-30,1,1).isoformat()
assert Profile(**{**P,'birth_date':dob}).age==30
for bad in ('2099-01-01','2000-02-30','bad'):
 try:Profile(**{**P,'birth_date':bad})
 except ValueError:pass
 else:raise AssertionError(bad)
with tempfile.TemporaryDirectory() as directory:
 app=create_app(directory);accounts=app.state.accounts;password='Fictional verification password 773!'
 with accounts.connect() as c:
  for name,role in [('one','user'),('two','user'),('admin','admin')]:c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),name+'@example.test',name,password_hash(password),role,'active',time.time()))
 clients=[TestClient(app,base_url='http://127.0.0.1:8000') for _ in range(4)]
 a,b,admin,anon=clients
 pids=[]
 for client,name in zip(clients,['one','two','admin']):
  check(client.post('/api/login',json={'email':name+'@example.test','password':password},headers=H),200)
  pid=str(uuid.uuid4());pids.append(pid)
  data=check(client.post('/api/participants',json={'id':pid,'mode':'active','profile':{**P,'display_name':name,'birth_date':dob},'consent_to_store':True},headers=H),201)
  assert data['profile']['age']==30
 pid=pids[0];endpoint='/api/auth/profile-health/'+pid
 check(anon.get(endpoint),401);check(b.get(endpoint),404);check(a.get(endpoint+'?mode=demo'),403)
 initial=check(a.get(endpoint),200);assert initial['revision']==0 and initial['current_age']==30
 body={'revision':0,'consent':False,'details':{'skin_type':'IV','wheelchair':'no','medication_status':'yes','medications':'Fictional medicine','allergy_status':'no','additional_notes':'<script>not executable</script>'}}
 check(a.put(endpoint,json=body,headers=H),422)
 body['consent']=True;check(a.put(endpoint,json=body,headers=H),200)
 check(a.put(endpoint,json=body,headers=H),409)
 saved=check(a.get(endpoint),200);assert saved['details']['wheelchair']=='no' and saved['details']['skin_type']=='IV'
 for details in ({'skin_type':'VII'},{'height_cm':'NaN'},{'birth_date':dob},{'allergy_status':'no','allergies':'Peanuts'},{'medication_status':'no','medications':'Drug'},{'memory_changes':'maybe'}):check(a.put(endpoint,json={'revision':1,'consent':True,'details':details},headers=H),422)
 check(b.put(endpoint,json={**body,'revision':1},headers=H),404)
 with patch('urllib.request.urlopen') as network:
  check(a.post('/api/auth/medications/search',json={'term':'aspirin','consent':False},headers=H),422);network.assert_not_called()
 fixture={'drugGroup':{'conceptGroup':[{'conceptProperties':[{'name':'Fictional medicine 5 mg','rxcui':'123'}]}]}}
 with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(fixture).encode())) as network:
  result=check(a.post('/api/auth/medications/search',json={'term':'Fictional','consent':True},headers=H),200)
  assert result['items'][0]['rxcui']=='123'
  assert network.call_args.args[0].full_url=='https://rxnav.nlm.nih.gov/REST/drugs.json?name=Fictional'
 with patch('urllib.request.urlopen',side_effect=OSError('offline')):check(a.post('/api/auth/medications/search',json={'term':'Fictional','consent':True},headers=H),503)
 check(a.post('/api/auth/export-health-workspace',json={'confirm':False},headers=H),422)
 exported=check(a.post('/api/auth/export-health-workspace',json={'confirm':True},headers=H),200)
 assert 'users' not in exported['tables'] and pids[1] not in json.dumps(exported)
 assert exported['tables']['profile_health'][0]['participant_id']==pid
 check(anon.post('/api/auth/export-health-workspace',json={'confirm':True},headers=H),401)
 check(a.delete(endpoint+'?revision=0',headers=H),409)
 check(a.delete(endpoint+'?revision=1',headers=H),200)
 assert check(a.get(endpoint),200)['details']=={}
 # Same administrator workspace, distinct test profiles.
 second=str(uuid.uuid4());check(admin.post('/api/participants',json={'id':second,'mode':'active','profile':P,'consent_to_store':True},headers=H),201)
 ep='/api/auth/profile-health/'+pids[2]
 check(admin.put(ep,json={'revision':0,'consent':True,'details':{'allergies':'Fictional allergen'}},headers=H),200)
 assert check(admin.get('/api/auth/profile-health/'+second),200)['details']=={}
 # Clear and account isolation persist across fresh request clients.
 assert check(b.get('/api/auth/profile-health/'+pids[1]),200)['details']=={}
 print(f'PASS {count} HTTP checks: DOB, participant isolation, consent, revisions, validation, medication lookup fixtures/offline handling, export isolation, clearing.')
