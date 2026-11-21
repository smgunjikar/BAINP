"""Integration security regression against complete app; isolated temporary data."""
import argparse,sys,time,tempfile,uuid,concurrent.futures,sqlite3
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,required=True);args=p.parse_args()
sys.path.insert(0,str(args.project_root/'apps/neuroaccess/backend'))
from api import create_app
from accounts import password_hash,digest
from fastapi.testclient import TestClient
H={'X-NeuroAccess-Request':'1'};PW='Test-only long password 482!'
profile=dict(display_name='Test profile',age=35,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
checks=0
def check(r,status=200):
 global checks
 assert r.status_code==status,(r.status_code,r.text);checks+=1
 return r.json()
def login(c,email):return check(c.post('/api/login',json={'email':email,'password':PW},headers=H))
def make(c,name='Test',mode='active'):
 uid=str(uuid.uuid4());r=check(c.post('/api/participants',json={'id':uid,'mode':mode,'profile':{**profile,'display_name':name},'consent_to_store':True},headers=H),201);return r
with tempfile.TemporaryDirectory() as d:
 app=create_app(d);ac=app.state.accounts;hashed=password_hash(PW);admin_id=str(uuid.uuid4())
 with ac.connect() as db:db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(admin_id,'admin@example.org','Admin',hashed,'admin','active',time.time()))
 a=TestClient(app,base_url='http://127.0.0.1:8000');b=TestClient(app,base_url='http://127.0.0.1:8000');admin=TestClient(app,base_url='http://127.0.0.1:8000');anon=TestClient(app,base_url='http://127.0.0.1:8000')
 check(anon.get('/api/participants?mode=active'),401)
 check(anon.get('/api/admin/users'),401)
 check(anon.post('/api/login',json={'password':PW},headers=H),422)
 check(a.post('/api/auth/register',json={'email':'a@example.org','password':PW,'name':'A','role':'admin'},headers=H),422)
 for c,email in [(a,'a@example.org'),(b,'b@example.org')]:
  check(c.post('/api/auth/register',json={'email':email,'password':PW,'name':email[0]},headers=H),202)
  check(c.post('/api/login',json={'email':email,'password':PW},headers=H),401)
 login(admin,'admin@example.org')
 users=check(admin.get('/api/admin/users'))['items'];uids={u['email']:u['id'] for u in users}
 for email in ['a@example.org','b@example.org']:check(admin.post('/api/admin/users/'+uids[email],json={'action':'approve','password':PW,'reason':'Approve isolated engineering test'},headers=H))
 login(a,'a@example.org');login(b,'b@example.org')
 pa=make(a,'A private');pb=make(b,'B private')
 check(a.get('/api/admin/users'),403);check(a.get('/api/participants?mode=demo'),403)
 check(a.get('/api/neurovision/status'),403)
 check(a.get('/api/unclassified-future-module'),403)
 check(a.get('/api/session',headers={'Host':'evil.example'}),400)
 check(anon.post('/api/auth/register',content='x'*17000,headers=H),413)
 check(a.post('/api/participants',json={'id':str(uuid.uuid4()),'mode':'demo','profile':profile,'consent_to_store':True},headers=H),403)
 check(a.post('/api/participants',json={'id':str(uuid.uuid4()),'mode':'active','profile':profile,'consent_to_store':True},headers=H),409)
 check(a.get('/api/participants/'+pb['id']+'?mode=active'),404)
 check(a.patch('/api/participants/'+pb['id']+'?mode=active',json={'revision':1,'profile':profile},headers=H),404)
 check(a.delete('/api/participants/'+pb['id']+'?mode=active',headers=H),422) # required confirmation body
 check(a.request('DELETE','/api/participants/'+pb['id']+'?mode=active',json={'confirm_id':pb['id'],'revision':1},headers=H),404)
 check(a.put('/api/owner-profile/'+pb['id']+'?mode=active',json={},headers=H),404)
 sid=str(uuid.uuid4());cb=check(b.post('/api/participants/'+pb['id']+'/checkins?mode=active',json={'id':sid,'participant_revision':1,'instructions_understood':True,'acute_warning':'no'},headers=H),201)
 check(a.get('/api/checkins/'+sid+'?mode=active'),404)
 for prefix,suffix in [('/api/neurocontinuum/v1/participants/','/workspace'),('/api/brainbody/participants/',''),('/api/neuroproof/v1/participants/',''),('/api/neuromimic/v1/participants/','')]:check(a.get(prefix+pb['id']+suffix+'?mode=active'),404)
 def own(pair):
  client,pid=pair
  for i in range(12):
   result=check(client.get('/api/participants?mode=active'));assert [x['id'] for x in result['items']]==[pid]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(own,[(a,pa['id']),(b,pb['id'])]))
 check(a.patch('/api/participants/'+pa['id']+'?mode=active',json={'revision':1,'profile':pa['profile']},headers=H));assert check(a.get('/api/participants/'+pa['id']+'?mode=active'))['revision']==1
 check(a.post('/api/auth/logout-all',json={},headers={'X-NeuroAccess-Request':'1','Origin':'https://evil.example'}),403)
 check(a.post('/api/auth/logout-all',json={}),403)
 check(admin.post('/api/admin/workspace',json={'target':uids['b@example.org'],'password':PW,'reason':'Review reported test failure'},headers=H))
 assert check(admin.get('/api/participants?mode=active'))['items'][0]['id']==pb['id']
 check(admin.post('/api/admin/workspace',json={'target':'legacy','password':PW,'reason':'Check separate legacy test records'},headers=H))
 legacy=make(admin,'Legacy record');demo=make(admin,'Demo record','demo')
 assert len(check(admin.get('/api/participants?mode=active'))['items'])==1
 assert len(check(admin.get('/api/participants?mode=demo'))['items'])==1
 check(b.get('/api/participants/'+legacy['id']+'?mode=active'),404)
 check(admin.request('DELETE','/api/participants/'+demo['id']+'?mode=demo',json={'confirm_id':demo['id'],'revision':1},headers=H))
 assert not check(admin.get('/api/participants?mode=demo'))['items']
 check(admin.post('/api/admin/users/'+uids['b@example.org'],json={'action':'disable','password':PW,'reason':'Test immediate access revocation'},headers=H))
 check(b.get('/api/session'),401)
 check(admin.post('/api/admin/users/'+uids['b@example.org'],json={'action':'enable','password':PW,'reason':'Restore engineering test access'},headers=H))
 recovery=check(admin.post('/api/admin/users/'+uids['b@example.org'],json={'action':'recovery','password':PW,'reason':'Verified identity for recovery test'},headers=H))['recovery_code']
 check(b.post('/api/auth/recover',json={'code':recovery,'new_password':PW},headers=H))
 check(b.post('/api/auth/recover',json={'code':recovery,'new_password':PW},headers=H),400)
 login(b,'b@example.org');cookie=b.cookies.get('bainp_session');check(b.post('/api/logout',json={},headers=H));check(b.get('/api/session',headers={'Cookie':'bainp_session='+cookie}),401)
 audit=check(admin.get('/api/admin/audit'))['items'];assert any(x['action']=='workspace_request_started' for x in audit)
 assert PW not in str(audit) and recovery not in str(audit)
 with ac.connect() as db:
  assert not db.execute('SELECT 1 FROM sessions WHERE token=?',(cookie,)).fetchone()
  try:db.execute('DELETE FROM audit');raise AssertionError('Audit deletion allowed')
  except sqlite3.IntegrityError:pass
 login(a,'a@example.org');check(a.post('/api/auth/password',json={'current_password':PW,'new_password':'Changed testing password 992!'},headers=H));check(a.get('/api/session'),401)
 # Re-create full application; identity and per-account records survive.
 app2=create_app(d);fresh=TestClient(app2,base_url='http://127.0.0.1:8000');login(fresh,'b@example.org');assert check(fresh.get('/api/participants?mode=active'))['items'][0]['id']==pb['id']
print('PASS',checks,'HTTP checks plus concurrent isolation, persistence, token storage and append-only audit assertions.')
