import sys,tempfile,uuid,time,math,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'apps/neuroaccess/backend'))
from api import create_app
from accounts import password_hash
from research_lab import signal_features,score
from fastapi.testclient import TestClient
H={'X-NeuroAccess-Request':'1'};PW='Research isolated password 483!';n=0
def check(r,status=200):
 global n
 assert r.status_code==status,(r.status_code,r.text);n+=1;return r.json()
with tempfile.TemporaryDirectory() as d:
 app=create_app(d);ac=app.state.accounts
 with ac.connect() as c:
  hashed=password_hash(PW)
  for name,role in [('a','admin'),('b','admin'),('u','user')]:c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),name+'@example.org',name,hashed,role,'active',time.time()))
 a,b,u,anon=[TestClient(app,base_url='http://127.0.0.1:8000') for _ in range(4)]
 check(anon.get('/api/research-lab/catalogue'),401)
 for cli,name in [(a,'a'),(b,'b'),(u,'u')]:check(cli.post('/api/login',json={'email':name+'@example.org','password':PW},headers=H))
 check(u.get('/api/research-lab/catalogue'),403);check(a.get('/api/research-lab/catalogue'))
 payload={'task':'spatial-sequence','consent':True,'access':{'can_perceive':True,'can_respond':True,'assistance':'none','urgent_concern':False}}
 check(a.post('/api/research-lab/start',json=payload),403)
 check(a.post('/api/research-lab/start',json={**payload,'consent':False},headers=H),422)
 for key,value in [('can_perceive',False),('urgent_concern',True),('assistance','answers')]:check(a.post('/api/research-lab/start',json={**payload,'access':{**payload['access'],key:value}},headers=H),422)
 start=check(a.post('/api/research-lab/start',json=payload,headers=H));rid=start['id']
 check(b.post('/api/research-lab/complete/'+rid,json={},headers=H),404)
 check(a.post('/api/research-lab/complete/'+rid+'?mode=demo',json={},headers=H),404)
 body={'state':'completed','answers':start['plan']['sequences'],'hidden_count':0,'consent':True}
 result=check(a.post('/api/research-lab/complete/'+rid,json=body,headers=H));assert result['metrics']['correct_trials']==6
 again=check(a.post('/api/research-lab/complete/'+rid,json=body,headers=H));assert again['id']==result['id']
 check(a.post('/api/research-lab/complete/'+rid,json={**body,'hidden_count':1},headers=H),409)
 assert check(b.get('/api/research-lab/records'))['items']==[]
 assert check(a.get('/api/research-lab/records?mode=demo'))['items']==[]
 for task in ['response-control','paired-association']:
  st=check(a.post('/api/research-lab/start',json={**payload,'task':task},headers=H));p=st['plan'];answers=[250 if go else None for go in p['go']] if task=='response-control' else [p['pairs'][i] for query in p['queries'] for i in query]
  r=check(a.post('/api/research-lab/complete/'+st['id'],json={**body,'answers':answers},headers=H));assert (r['metrics']['missed_go']==0 if task=='response-control' else r['metrics']['correct_responses']==8)
 st=check(a.post('/api/research-lab/start',json=payload,headers=H));r=check(a.post('/api/research-lab/complete/'+st['id'],json={**body,'state':'aborted','answers':[]},headers=H));assert r['metrics']=={} and 'INTERRUPTED' in r['quality_flags']
 raw='t,ax,ay,az\n'+'\n'.join(f'{i/100},{math.sin(2*math.pi*5*i/100)},0,0' for i in range(1200))
 imp={'consent':True,'csv':raw,'metadata':{'units':'m/s2','device':'synthetic','protocol':'sine-v1','placement':'bench'}}
 r=check(a.post('/api/research-lab/import/motion',json=imp,headers=H));assert abs(r['features'][0]['peak_3_12_hz']-5)<.1 and 'FLAT_CHANNEL' in r['quality_flags']
 check(a.post('/api/research-lab/import/motion',json={**imp,'metadata':{**imp['metadata'],'units':'g'}},headers=H),422)
 check(a.post('/api/research-lab/import/motion',json={**imp,'csv':raw.replace('0.01,','0.00,',1)},headers=H),422)
 check(a.post('/api/research-lab/import/voice',json={'consent':True,'data':{'duration_s':12,'sample_hz':48000,'rms':.1,'clipping_fraction':0}},headers=H))
 check(a.post('/api/research-lab/import/voice',json={'consent':True,'data':{}},headers=H),422)
 eeg='t,C3\n'+'\n'.join(f'{i/128},{10*math.sin(2*math.pi*10*i/128)}' for i in range(1536))
 er=check(a.post('/api/research-lab/import/eeg',json={'consent':True,'csv':eeg,'metadata':{'units':'uV','device':'synthetic','protocol':'sine-v1','reference':'simulation'}},headers=H));assert er['features'][0]['relative_power']['alpha']>.95
 data={'schema':'bainp-regional-volumes-v1','atlas':'test','pipeline':'test','pipeline_version':'1','scanner':'test','acquisition_protocol':'T1','image_sha256':'a'*64,'labels_sha256':'b'*64,'regions':[{'label':1,'name':'synthetic region','volume_mm3':50}]}
 ir=check(a.post('/api/research-lab/import/imaging',json={'consent':True,'data':data},headers=H));data2=copy.deepcopy(data);data2['regions'][0]['volume_mm3']=48
 ir2=check(a.post('/api/research-lab/import/imaging',json={'consent':True,'data':data2},headers=H));r=check(a.get('/api/research-lab/compare?first='+ir['id']+'&second='+ir2['id']));assert r['regions'][0]['difference_mm3']==-2
 check(b.get('/api/research-lab/compare?first='+ir['id']+'&second='+ir2['id']),404)
 data2['scanner']='different';ir3=check(a.post('/api/research-lab/import/imaging',json={'consent':True,'data':data2},headers=H));check(a.get('/api/research-lab/compare?first='+ir['id']+'&second='+ir3['id']),422)
 check(a.post('/api/research-lab/start',content=b' '*1000001,headers=H),413)
 check(a.post('/api/research-lab/start',content=b'{"x":NaN}',headers=H),422)
 restarted=TestClient(create_app(d),base_url='http://127.0.0.1:8000');check(restarted.post('/api/login',json={'email':'a@example.org','password':PW},headers=H));assert len(check(restarted.get('/api/research-lab/records'))['items'])>0
 with ac.connect() as c:assert c.execute("SELECT COUNT(*) FROM audit WHERE action='research_record_created'").fetchone()[0]>0
print('PASS',n,'HTTP assertions; isolation, consent, idempotence, three tasks, interruption, signal recovery, MRI mismatch and persistence.')
