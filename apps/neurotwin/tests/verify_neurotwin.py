"""Isolated integration checks; no local participant data, dataset or running service used."""
import hashlib,importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'neuroaccess/backend'))
sys.path.insert(0,str(ROOT/'backend'))
import neurotwin_bridge
from nt_engine import build,estimate
from api import create_app
from fastapi.testclient import TestClient
PROFILE=dict(display_name='Isolated twin test',age=60,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.anatomy_prior=os.environ.get('NEUROTWIN_ANATOMY_DIR');os.environ['NEUROTWIN_ANATOMY_DIR']=str(self.root/'anatomy');(self.root/'anatomy').mkdir()
        self.prior=os.environ.get('NEUROVISION_DATA_DIR');os.environ['NEUROVISION_DATA_DIR']=str(self.root/'imaging');(self.root/'imaging').mkdir()
        self.app=create_app(self.root/'db',password='isolated-test-password');self.store=self.app.state.store
        self.client=TestClient(self.app);self.client.headers.update({'X-NeuroAccess-Request':'1'})
        self.assertEqual(self.client.post('/api/login',json={'password':'isolated-test-password'}).status_code,200)
        self.pid=self.new_person('active');self.other=self.new_person('active');self.demo=self.new_person('demo')
        self.url='/api/neurotwin/participants/'+self.pid
    def tearDown(self):
        self.client.close()
        if self.prior is None:os.environ.pop('NEUROVISION_DATA_DIR',None)
        else:os.environ['NEUROVISION_DATA_DIR']=self.prior
        if self.anatomy_prior is None:os.environ.pop('NEUROTWIN_ANATOMY_DIR',None)
        else:os.environ['NEUROTWIN_ANATOMY_DIR']=self.anatomy_prior
        self.tmp.cleanup()
    def new_person(self,mode):
        pid=str(uuid4());r=self.client.post('/api/participants',json={'id':pid,'mode':mode,'profile':PROFILE,'consent_to_store':True});self.assertEqual(r.status_code,201,r.text);return pid
    def snapshot(self):
        r=self.client.get(self.url+'?mode=active');self.assertEqual(r.status_code,200,r.text);return r.json()
    def record(self):
        return dict(source='NeuroPulse',record_id='eeg-1',source_subject='source-subject-1',revision=1,observed_at='2026-01-01T12:00:00+00:00',protocol='verified-rest-v1',provenance='Synthetic test fixture only',identity_verified=True,consent_confirmed=True,observations=[dict(metric='peak_alpha_frequency',value=10.,unit='Hz',context='Pz referenced; test fixture',quality='usable')])
    def scan(self,identifier='a'*24,visit='V1',mode='active'):
        m=dict(cohort='TEST',subject='S1',visit=visit,date='2026-01-01' if visit=='V1' else '2026-02-01',protocol='test',pipeline='test-v1',review='APPROVED',synthetic=mode=='demo',modality='T1w',longitudinal_comparable=True,quality_flags=[],measurements=[dict(id='mask',name='Extraction mask',volume_ml=1400.,status='mask-derived')])
        raw=json.dumps({'metadata':m}).encode();p=self.root/'imaging';(p/(identifier+'.json')).write_bytes(raw)
        entry=dict(id=identifier,package_sha256=hashlib.sha256(raw).hexdigest(),**{k:m[k] for k in ('cohort','subject','visit','date','modality','synthetic')})
        catalog=json.loads((p/'catalog.json').read_text()) if (p/'catalog.json').exists() else []
        catalog=[e for e in catalog if e['id']!=identifier]+[entry];(p/'catalog.json').write_text(json.dumps(catalog));return entry
    def test_auth_modes_and_guard(self):
        with TestClient(self.app) as anon:self.assertEqual(anon.get(self.url+'?mode=active').status_code,401)
        self.assertEqual(self.client.get(self.url+'?mode=demo').status_code,404)
        self.assertEqual(self.client.get(self.url+'?mode=invalid').status_code,422)
        self.assertEqual(self.client.put(self.url+'/source-records?mode=active',headers={'X-NeuroAccess-Request':'0'},json=self.record()).status_code,403)
        d=self.snapshot();self.assertEqual(d['source_states']['NeuroCognition X']['state'],'empty');self.assertIsNone(d['forecast']['value']);self.assertIsNone(d['guard']['diagnosis']);self.assertFalse(d['guard']['biological_replica'])
    def test_versioned_source_updates_and_deletion(self):
        url=self.url+'/source-records?mode=active';r=self.record();a=self.snapshot()['revision']
        self.assertEqual(self.client.put(url,json=r).status_code,200);b=self.snapshot();self.assertNotEqual(a,b['revision']);self.assertEqual(b['series'][0]['points'][0]['value'],10.)
        self.assertTrue(self.client.put(url,json=r).json()['unchanged']);self.assertEqual(self.snapshot()['revision'],b['revision'])
        r['observations'][0]['value']=11.;self.assertEqual(self.client.put(url,json=r).status_code,409)
        r['revision']=2;self.assertEqual(self.client.put(url,json=r).status_code,200);self.assertEqual(self.snapshot()['series'][0]['points'][0]['value'],11.)
        self.assertEqual(self.client.put(url.replace(self.pid,self.other),json=self.record()).status_code,409)
        self.assertEqual(self.client.delete(self.url+'/source-records/eeg-1?mode=active&source=NeuroPulse').status_code,200);self.assertFalse(self.snapshot()['series'])
    def test_units_quality_and_strict_payload(self):
        r=self.record();r['observations'][0]['unit']='uV2';self.assertEqual(self.client.put(self.url+'/source-records?mode=active',json=r).status_code,422)
        r=self.record();r['extra']='ignored?';self.assertEqual(self.client.put(self.url+'/source-records?mode=active',json=r).status_code,422)
        r=self.record();r['identity_verified']=False;self.assertEqual(self.client.put(self.url+'/source-records?mode=active',json=r).status_code,422)
        r=self.record();r['observations'][0]['quality']='invalid';self.assertEqual(self.client.put(self.url+'/source-records?mode=active',json=r).status_code,200);self.assertFalse(self.snapshot()['series'][0]['points'][0]['eligible'])
    def test_wearable_refresh_and_overlap(self):
        with self.store.connect(True) as c:
            c.execute('CREATE TABLE IF NOT EXISTS sense_observations (participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,source_id TEXT,payload TEXT,PRIMARY KEY(participant_id,mode,source_id))')
            for n in range(2):
                p=dict(source_id=str(n),metric='steps',value=6000.,unit='count',timestamp='2026-01-01T12:00:00+00:00',device='test',method='summary',protocol='v1',quality='usable')
                c.execute('INSERT INTO sense_observations VALUES(?,?,?,?)',(self.pid,'active',str(n),json.dumps(p)))
        a=self.snapshot();self.assertEqual(len(a['series'][0]['points']),2);self.assertFalse(any(p['eligible'] for p in a['series'][0]['points']))
        with self.store.connect(True) as c:c.execute('DELETE FROM sense_observations WHERE participant_id=?',(self.pid,))
        b=self.snapshot();self.assertNotEqual(a['revision'],b['revision']);self.assertFalse(b['series'])
    def test_imaging_identity_new_visits_and_integrity(self):
        e=self.scan();self.assertFalse(self.snapshot()['imaging'])
        payload=dict(scan_id=e['id'],expected_sha256=e['package_sha256'],identity_verified=True,note='Verified test fixture identity')
        self.assertEqual(self.client.post(self.url+'/imaging-links?mode=active',json=payload).status_code,200)
        self.assertEqual(len(self.snapshot()['imaging']),1)
        self.assertEqual(self.client.post(self.url.replace(self.pid,self.other)+'/imaging-links?mode=active',json=payload).status_code,409)
        self.assertEqual(self.client.post(self.url.replace(self.pid,self.demo)+'/imaging-links?mode=demo',json=payload).status_code,404)
        self.scan('b'*24,'V2');self.assertEqual(len(self.snapshot()['imaging']),2)
        (self.root/'imaging'/(e['id']+'.json')).write_text('{}')
        d=self.snapshot();self.assertEqual(d['source_states']['NeuroVision']['state'],'error');self.assertFalse(d['imaging']);self.assertTrue(d['issues'])
    def test_cascade_and_synthetic_isolation(self):
        e=self.scan();self.client.post(self.url+'/imaging-links?mode=active',json=dict(scan_id=e['id'],expected_sha256=e['package_sha256'],identity_verified=True,note='Verified test fixture identity'))
        self.client.put(self.url+'/source-records?mode=active',json=self.record())
        before=self.snapshot()['revision'];example=self.client.get('/api/neurotwin/demo-example').json();self.assertEqual(example['identity']['mode'],'demo');self.assertEqual(self.snapshot()['revision'],before)
        r=self.client.request('DELETE','/api/participants/'+self.pid+'?mode=active',json={'confirm_id':self.pid,'revision':1});self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.client.get(self.url+'?mode=active').status_code,404)
        with self.store.connect() as c:
            for table in ('nt_imaging_links','nt_source_records','nt_neural_records','nt_refresh_events','nt_anatomical_records'):self.assertEqual(c.execute('SELECT count(*) FROM '+table+' WHERE participant_id=?',(self.pid,)).fetchone()[0],0)
    def test_trend_abstention_and_known_slope(self):
        points=[dict(at=f'2026-01-{d:02}T12:00:00+00:00',value=float(d),eligible=True) for d in (1,8,15,22)]
        fit=estimate(points);self.assertAlmostEqual(fit['slope_per_30_days'],30.);self.assertEqual(fit['residual_sd'],0);self.assertIsNone(fit['confidence_interval']);self.assertIsNone(fit['reliable_change_index'])
        points[0]['eligible']=False;self.assertEqual(estimate(points)['state'],'INSUFFICIENT_COMPARABLE_DAYS')
    def test_condition_groups_and_no_typed_autoscore(self):
        def r(group,flag=[]):return dict(session_id=group,created_at='2026-01-01T12:00:00+00:00',status='completed',condition_group=group,protocol='test',form='A',summary={'correct':8,'quality_flags':flag})
        # Explicitly complete parent visits; a task alone cannot establish visit eligibility.
        visits=[dict(id=sid,status='completed',created_at='2026-01-01T12:00:00+00:00',protocol='test',form='A',checkin_id='fixture') for sid in ('a','b')]
        d=build({'session_history':visits,'task_series':{'C01':[r('a'),r('b',['FLAG'])],'C09':[r('a')]}},[],[],[],{},dict(mode='active'),[])
        self.assertEqual(len(d['cognitive_records']),3);self.assertEqual(len(d['series']),2);self.assertEqual(sum(p['eligible'] for s in d['series'] for p in s['points']),1)
        old=d['revision'];changed=r('a');changed['reviewed_counts']={'pending_review':1}
        reviewed=build({'session_history':visits,'task_series':{'C09':[changed]}},[],[],[],{},dict(mode='active'),[])
        changed['reviewed_counts']={'pending_review':0,'incorrect':1}
        revised=build({'session_history':visits,'task_series':{'C09':[changed]}},[],[],[],{},dict(mode='active'),[])
        self.assertNotEqual(reviewed['revision'],revised['revision'])
    def neural_payload(self):
        from nt_demo import fixtures
        import copy
        record=copy.deepcopy(fixtures()['control']['neural'][0])
        record.update(record_id='isolated-neural',source_subject='isolated-eeg-subject',source_kind='recorded_research_eeg',synthetic=False,source_sha256='1'*64,identity_verified=True,consent_confirmed=True)
        return record
    def test_complete_demo_profiles_and_isolation(self):
        before=self.snapshot()['revision']
        a=self.client.get('/api/neurotwin/demo-example?profile=control').json()
        b=self.client.get('/api/neurotwin/demo-example?profile=impairment').json()
        self.assertTrue(a['synthetic']);self.assertTrue(b['synthetic'])
        self.assertEqual(len(a['functions']),6);self.assertEqual(len(a['neural_recordings']),8)
        self.assertEqual(len(a['imaging']),8);self.assertEqual(len(a['clinical_records']),8)
        self.assertTrue(all(x['count']>0 for x in a['source_states'].values()))
        self.assertNotEqual(a['forecast']['value'],b['forecast']['value'])
        self.assertEqual(a['forecast']['state'],'SYNTHETIC_SIMULATOR_ONLY')
        self.assertEqual(before,self.snapshot()['revision'])
        rid=a['neural_recordings'][0]['record_id']
        self.assertEqual(self.client.get('/api/neurotwin/demo-neural/'+rid+'?profile=control').status_code,200)
        self.assertEqual(self.client.get('/api/neurotwin/demo-neural/'+rid+'?profile=impairment').status_code,404)
        r=self.client.post('/api/neurotwin/demo-scenario?profile=control&score=60&sleep=6')
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(before,self.snapshot()['revision'])
    def test_neural_contract_identity_updates_and_delete(self):
        p=self.neural_payload();url=self.url+'/neural-records?mode=active'
        self.assertEqual(self.client.put(url,json=p).status_code,200)
        before=self.snapshot();self.assertEqual(len(before['neural_recordings']),1)
        self.assertEqual(self.client.get(self.url+'/neural-records/'+p['record_id']+'?mode=active').status_code,200)
        self.assertEqual(self.client.get(self.url+'/neural-records/'+p['record_id']+'?mode=demo').status_code,404)
        self.assertEqual(self.client.put(url.replace(self.pid,self.other),json=p).status_code,409)
        p['features']['alpha_power']+=1;p['revision']=2
        self.assertEqual(self.client.put(url,json=p).status_code,200)
        self.assertNotEqual(before['revision'],self.snapshot()['revision'])
        self.assertEqual(self.client.delete(self.url+'/neural-records/'+p['record_id']+'?mode=active').status_code,200)
        self.assertFalse(self.snapshot()['neural_recordings'])
    def test_invalid_neural_and_cross_adapter_identity(self):
        p=self.neural_payload();p['channels'].append('extra')
        self.assertEqual(self.client.put(self.url+'/neural-records?mode=active',json=p).status_code,422)
        p=self.neural_payload();p['synthetic']=True
        self.assertEqual(self.client.put(self.url+'/neural-records?mode=active',json=p).status_code,422)
        p=self.neural_payload();self.client.put(self.url+'/neural-records?mode=active',json=p)
        r=self.record();r['source_subject']=p['source_subject']
        self.assertEqual(self.client.put(self.url.replace(self.pid,self.other)+'/source-records?mode=active',json=r).status_code,409)
    def test_inline_mri_access_is_link_gated(self):
        e=self.scan();path=self.url+'/anatomy/'+e['id']+'?mode=active'
        self.assertEqual(self.client.get(path).status_code,404)
        self.client.post(self.url+'/imaging-links?mode=active',json=dict(scan_id=e['id'],expected_sha256=e['package_sha256'],identity_verified=True,note='Verified test fixture identity'))
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.get(path.replace(self.pid,self.other)).status_code,404)
        self.client.delete(self.url+'/imaging-links?mode=active&cohort=TEST&subject=S1')
        self.assertEqual(self.client.get(path).status_code,404)
    def test_monitor_update_hash_and_clinical_fields(self):
        a=self.snapshot();b=self.snapshot();self.assertEqual(a['revision'],b['revision']);self.assertEqual(len(a['governance']['updates']),len(b['governance']['updates']))
        r=self.record();r.update(source='Clinical',record_id='clinical-1',clinical_state='MCI',source_cohort='TEST')
        r['observations']=[dict(metric='clinical_measurement',instrument='MMSE',value=25.,unit='score',quality='usable',context='test baseline'),dict(metric='age',value=65.,unit='years',quality='usable',context='same visit'),dict(metric='education_years',value=12.,unit='years',quality='usable',context='same visit')]
        response=self.client.put(self.url+'/source-records?mode=active',json=r);self.assertEqual(response.status_code,200,response.text)
        d=self.snapshot();self.assertEqual(d['clinical_records'][0]['clinical_state'],'MCI');self.assertNotEqual(d['revision'],a['revision']);self.assertGreater(len(d['governance']['updates']),len(a['governance']['updates']))
        self.assertIsNone(d['forecast']['value'])
    def test_registered_anatomy_hash_link_and_unlink(self):
        e=self.scan();folder=self.root/'imaging';path=folder/(e['id']+'.json');pack=json.loads(path.read_text());pack['metadata']['source_sha256']={'image':'1'*64};raw=json.dumps(pack).encode();path.write_bytes(raw)
        e['package_sha256']=hashlib.sha256(raw).hexdigest();(folder/'catalog.json').write_text(json.dumps([e]))
        self.client.post(self.url+'/imaging-links?mode=active',json=dict(scan_id=e['id'],expected_sha256=e['package_sha256'],identity_verified=True,note='Verified test fixture identity'))
        anatomy=dict(schema='nt-freesurfer-anatomy-v1',synthetic=False,scan_id=e['id'],input_mri_sha256='1'*64,review_reference='Test fixture only',freesurfer_version='test-fixture',measurements=[dict(id='left-hippocampus',name='Left hippocampus fixture',value=3.5,unit='mL',basis='Test segmentation grid')],surfaces=[dict(id='lh',name='Test triangle',vertices_mm=[[0,0,0],[1,0,0],[0,1,0]],faces=[[0,1,2]],coordinate_space='test')])
        raw=json.dumps(anatomy).encode();digest=hashlib.sha256(raw).hexdigest();(self.root/'anatomy'/(digest+'.json')).write_bytes(raw)
        response=self.client.put(self.url+'/anatomical-records?mode=active',json=dict(package_sha256=digest,identity_verified=True,consent_confirmed=True));self.assertEqual(response.status_code,200,response.text)
        snap=self.snapshot();self.assertEqual(len(snap['regional_anatomy']),1);self.assertTrue(any(s['metric']=='left-hippocampus' for s in snap['series']))
        self.assertEqual(self.client.get(self.url+'/anatomical-records/'+digest+'?mode=active').status_code,200)
        self.client.delete(self.url+'/imaging-links?mode=active&cohort=TEST&subject=S1')
        self.assertEqual(self.client.get(self.url+'/anatomical-records/'+digest+'?mode=active').status_code,404)
        self.assertFalse(self.snapshot()['regional_anatomy'])
    def test_neural_invalid_covariance_and_quality(self):
        p=self.neural_payload();p['covariance_uv2']=[[1,2,0,0],[2,1,0,0],[0,0,1,0],[0,0,0,1]]
        self.assertEqual(self.client.put(self.url+'/neural-records?mode=active',json=p).status_code,422)
        p=self.neural_payload();p['quality_flags']=['REVIEW_REQUIRED']
        self.assertEqual(self.client.put(self.url+'/neural-records?mode=active',json=p).status_code,422)
if __name__=='__main__':unittest.main(verbosity=2)
