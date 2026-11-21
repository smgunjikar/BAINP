"""End-to-end API/storage verification using isolated temporary data and HTTP.

Starts its own API on a random loopback port. Does not touch operator records,
research data, existing PostgreSQL, or ports 3000/8000. Uses standard-library HTTP.
"""
import copy,json,os,sqlite3,socket,subprocess,sys,tempfile,time,unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4
from urllib.request import Request,build_opener,HTTPCookieProcessor,urlopen
from urllib.error import HTTPError,URLError
from http.cookiejar import CookieJar
ROOT=Path(__file__).resolve().parents[1]
PROFILE=dict(display_name='Demo <test> participant',age=60,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
PRACTICE=dict(protocol='access-practice-v1',interface_language='en',events=[dict(kind='activate',response='button',elapsed_ms=150.0,input='keyboard'),dict(kind='match',response='triangle',elapsed_ms=200.0,input='keyboard'),dict(kind='match',response='circle',elapsed_ms=450.0,input='keyboard')],focus_changes=0)
class NeuroAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        sys.path.insert(0,str(ROOT/'backend'))
        from accounts import Accounts,password_hash
        account_store=Accounts(cls.folder/'identity')
        with account_store.connect() as connection:
            connection.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(str(uuid4()),'test@example.org','Test administrator',password_hash('local-test-code'),'admin','active',time.time()))
        cls.start_server()
        cls.client=build_opener(HTTPCookieProcessor(CookieJar()))
    @classmethod
    def start_server(cls):
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(port)
        env={**os.environ,'NEUROACCESS_DATA_DIR':str(cls.folder)}
        cls.log=open(cls.folder/'server.log','ab')
        cls.proc=subprocess.Popen([sys.executable,'-m','uvicorn','api:create_app','--factory','--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=cls.log,stderr=cls.log)
        for _ in range(100):
            try:
                with urlopen(cls.base+'/api/health',timeout=1) as r:
                    if r.status==200:return
            except (URLError,OSError):time.sleep(.1)
        raise RuntimeError('Isolated API failed to start: '+(cls.folder/'server.log').read_text())
    @classmethod
    def stop_server(cls):
        cls.proc.terminate()
        try:cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:cls.proc.kill();cls.proc.wait()
        cls.log.close()
    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        # Short bounded retries handle transient Windows file-release delays.
        # Cleanup failures still fail verification; they are never hidden.
        for attempt in range(10):
            try:
                cls.temp.cleanup()
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.2)
    def request(self,method,path,body=None,status=200,client=None,headers=None):
        req=Request(self.base+'/api'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-NeuroAccess-Request':'1',**(headers or {})},method=method)
        try:
            with (client or self.client).open(req,timeout=10) as r:code,raw=r.status,r.read()
        except HTTPError as e:code,raw=e.code,e.read()
        self.assertEqual(code,status,raw.decode());return json.loads(raw)
    def test_frontend_proxy(self):
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        api_port=self.base.rsplit(':',1)[1]
        proc=subprocess.Popen([sys.executable,str(ROOT/'backend'/'serve_frontend.py'),'--port',str(port),'--api-port',api_port],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        base='http://127.0.0.1:'+str(port)
        try:
            for _ in range(100):
                try:
                    with urlopen(base,timeout=1) as response:
                        self.assertIn('frame-ancestors',response.headers['Content-Security-Policy']);self.assertIn(b'NeuroAccess',response.read());break
                except (URLError,OSError):time.sleep(.1)
            else:raise RuntimeError('Frontend proxy failed to start')
            browser=build_opener(HTTPCookieProcessor(CookieJar()))
            req=Request(base+'/api/login',data=json.dumps({'email':'test@example.org','password':'local-test-code'}).encode(),headers={'Content-Type':'application/json','X-NeuroAccess-Request':'1'},method='POST')
            with browser.open(req,timeout=5) as response:
                self.assertIn('HttpOnly',response.headers['Set-Cookie']);self.assertEqual(response.status,200)
            with browser.open(base+'/api/session',timeout=5) as response:self.assertTrue(json.load(response)['authenticated'])
            with browser.open(base+'/encoding?id=legacy',timeout=5) as response:self.assertTrue(response.url.endswith('/?mode=active'))
            print('PASS: frontend assets, security headers, same-origin authentication proxy and legacy-route redirects',flush=True)
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    def test_full_flow(self):
        anon=build_opener(HTTPCookieProcessor(CookieJar()))
        self.request('GET','/participants?mode=active',status=401,client=anon)
        self.request('POST','/login',{'email':'test@example.org','password':'wrong'},401,client=anon)
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        self.request('POST','/admin/workspace',{'target':'legacy','password':'local-test-code','reason':'Run isolated core regression test'})
        self.request('GET','/session',headers={'Origin':'https://untrusted.example'},status=403)
        pid=str(uuid4());body=dict(id=pid,mode='active',profile=PROFILE,consent_to_store=True)
        self.request('POST','/participants',{**body,'consent_to_store':False},422)
        self.request('POST','/participants',{**body,'profile':{**PROFILE,'age':10}},422)
        first=self.request('POST','/participants',body,201)
        self.assertEqual(first,self.request('POST','/participants',body,201))
        self.request('GET',f'/participants/{pid}?mode=demo',status=404)
        self.assertEqual(self.request('GET','/participants?mode=demo')['items'],[])
        sid=str(uuid4());check=dict(id=sid,participant_revision=1,instructions_understood=True,acute_warning='no')
        self.request('POST',f'/participants/{pid}/checkins?mode=active',check,201)
        self.assertEqual(self.request('POST',f'/participants/{pid}/checkins?mode=active',check,201)['id'],sid)
        self.request('PUT',f'/checkins/{sid}/practice?mode=demo',PRACTICE,404)
        self.request('PUT',f'/checkins/{sid}/practice?mode=active',{**PRACTICE,'events':PRACTICE['events'][:1]},422)
        saved=self.request('PUT',f'/checkins/{sid}/practice?mode=active',PRACTICE)
        self.assertEqual(saved['practice']['steps_completed'],2);self.assertEqual(saved['practice']['incorrect_actions'],1)
        self.assertEqual(saved,self.request('PUT',f'/checkins/{sid}/practice?mode=active',PRACTICE))
        self.request('PUT',f'/checkins/{sid}/practice?mode=active',{**PRACTICE,'focus_changes':1},409)
        observed_id=str(uuid4())
        self.request('POST',f'/participants/{pid}/checkins?mode=active',dict(id=observed_id,participant_revision=1,instructions_understood=True,acute_warning='no'),201)
        mouse={**PRACTICE,'events':[{**e,'input':'mouse'} for e in PRACTICE['events']]}
        actual_change=self.request('PUT',f'/checkins/{observed_id}/practice?mode=active',mouse)
        self.assertIn('observed_inputs',[x['field'] for x in actual_change['comparison']['changes']])
        self.assertIn('OBSERVED_INPUT_DIFFERS',actual_change['practice']['quality_flags'])
        changed={**PROFILE,'language':'ar','input_method':'touch','motor_limitation':True,'assistance':'navigation','assistance_authorized':True,'high_contrast':True}
        self.request('PATCH',f'/participants/{pid}?mode=active',dict(revision=1,profile=changed))
        self.request('PATCH',f'/participants/{pid}?mode=active',dict(revision=1,profile={**changed,'age':61}),409)
        second_id=str(uuid4());second=self.request('POST',f'/participants/{pid}/checkins?mode=active',dict(id=second_id,participant_revision=2,instructions_understood=True,acute_warning='no'),201)
        self.assertTrue(second['gate']['practice_allowed']);self.assertIn('NAVIGATION_HELP_RECORDED',second['gate']['notes'])
        self.assertEqual(second['comparison']['state'],'conditions_changed')
        self.assertIn('language',[x['field'] for x in second['comparison']['changes']])
        self.assertEqual(self.request('GET',f'/checkins/{sid}?mode=active')['profile'],PROFILE)
        # Persistence through a real server restart; persistent account session remains valid.
        type(self).stop_server();type(self).start_server()
        restored=self.request('GET',f'/participants/{pid}?mode=active');self.assertEqual(restored['revision'],2)
        self.assertEqual(self.request('GET',f'/checkins/{second_id}?mode=active')['comparison'],second['comparison'])
        # Assistance authorization and acute hold are distinct from disability alone.
        unauthorized={**changed,'assistance_authorized':False}
        self.request('PATCH',f'/participants/{pid}?mode=active',dict(revision=2,profile=unauthorized))
        held=self.request('POST',f'/participants/{pid}/checkins?mode=active',dict(id=str(uuid4()),participant_revision=3,instructions_understood=True,acute_warning='no'),201)
        self.assertIn('ASSISTANCE_AUTHORIZATION_NEEDED',held['gate']['reason_codes'])
        self.request('PUT',f"/checkins/{held['id']}/practice?mode=active",PRACTICE,409)
        acute=self.request('POST',f'/participants/{pid}/checkins?mode=active',dict(id=str(uuid4()),participant_revision=3,instructions_understood=True,acute_warning='yes'),201)
        self.assertIn('ACUTE_WARNING_REVIEW',acute['gate']['reason_codes'])
        # Demo records remain separate and survive deleting an active participant.
        demo_id=str(uuid4());self.request('POST','/participants',dict(id=demo_id,mode='demo',profile=PROFILE,consent_to_store=True),201)
        self.request('DELETE',f'/participants/{pid}?mode=active',dict(confirm_id=str(uuid4()),revision=3),422)
        self.request('DELETE',f'/participants/{pid}?mode=active',dict(confirm_id=pid,revision=3))
        self.request('GET',f'/participants/{pid}?mode=active',status=404)
        self.request('GET',f'/checkins/{sid}?mode=active',status=404)
        self.assertEqual(len(self.request('GET','/participants?mode=demo')['items']),1)
        # sqlite3's context manager commits/rolls back but does NOT close the handle.
        # Explicit closing is required before Windows can remove the test database.
        with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM checkins WHERE participant_id=?',(pid,)).fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM participants WHERE id=?',(pid,)).fetchone()[0],0)
            self.assertGreater(c.execute("SELECT count(*) FROM audit_events WHERE action='participant_deleted'").fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM audit_events WHERE entity_id=?',(pid,)).fetchone()[0],0)
        print('PASS: authentication, strict validation, active/demo isolation, exact retries, profile concurrency, practice, comparisons, restart persistence, holds and cascade deletion',flush=True)
if __name__=='__main__':unittest.main(verbosity=2)
