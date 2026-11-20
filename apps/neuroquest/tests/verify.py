"""Independent reproducible engineering checks; only temporary fictional records."""
import importlib.util,json,sys,unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
APPS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(APPS/'neurocontinuum/tests'))
from verify import IntegrationTests,create_app,LocalClient,serve,ExitStack,tempfile,os
spec=importlib.util.spec_from_file_location('quest_policy_test',APPS/'neuroquest/backend/engine.py');policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

class PureTests(unittest.TestCase):
    def context(self):
        return dict(profile=dict(language='en',can_see_and_respond='yes',assistance='none'),intent=dict(functional_concern=False,concerns_checked=True,target_domain='none',quality_problem_addressed=False),registry=dict(protocol='test-v1',core=['C01'],tasks=['C01']),history=[],consent=dict(history_allowed=True,assessment_allowed=True),guard=dict(state='workflow_permitted'),as_of='2026-11-11T12:00:00+00:00')
    def test_baseline(self):self.assertEqual(policy.select(self.context())['action'],'baseline')
    def test_reproducible(self):self.assertEqual(policy.select(self.context()),policy.select(self.context()))
    def test_urgent_over_functional_and_scores(self):
        c=self.context();c['urgent']={'state':'escalate'};c['intent']['functional_concern']=True;self.assertEqual(policy.select(c)['action'],'urgent_guidance')
    def test_functional_not_denied_by_normal_scores(self):
        c=self.context();c['intent']['functional_concern']=True;c['guard']['state']='abstain';self.assertEqual(policy.select(c)['action'],'professional_review')
    def test_guard_binding(self):
        c=self.context();c['guard']['state']='abstain';self.assertFalse(policy.select(c)['executable'])
    def test_missing_history_abstains(self):
        c=self.context();c['consent']['history_allowed']=False;self.assertEqual(policy.select(c)['action'],'abstain')
    def test_registry_cannot_invent_task(self):
        c=self.context();c['registry']['core']=['NONEXISTENT'];self.assertFalse(policy.select(c)['executable'])
    def test_accessibility(self):
        for field in ('motor_limitation','vision_limitation','hearing_limitation'):
            c=self.context();c['profile'][field]=True;self.assertFalse(policy.select(c)['executable'])
    def test_targeted_abstains_from_unverified_execution(self):
        c=self.context();c['intent']['target_domain']='memory';r=policy.select(c);self.assertEqual(r['action'],'targeted');self.assertFalse(r['executable'])
    def test_quality_repeat_requires_correction_and_contract(self):
        c=self.context();c['history']=[dict(task='C01',quality='QUARANTINED')];r=policy.select(c);self.assertEqual(r['action'],'repeat');self.assertFalse(r['executable'])
    def test_recent_monitor_not_clinical_stability_claim(self):
        c=self.context();c['history']=[dict(task='C01',quality='CLEAR',protocol='test-v1',source_session_id='s',observed_at='2026-11-11T10:00:00+00:00')];r=policy.select(c);self.assertEqual(r['action'],'monitor');self.assertFalse(r['executable'])
    def test_old_protocol_not_pooled(self):
        c=self.context();c['history']=[dict(task='C01',quality='CLEAR',protocol='old',source_session_id='s',observed_at='2026-11-11T10:00:00+00:00')];self.assertEqual(policy.select(c)['action'],'baseline')
    def test_partial_sessions_not_combined(self):
        c=self.context();c['registry']['core']=['C01','C02'];c['registry']['tasks']=['C01','C02'];c['history']=[dict(task=t,quality='CLEAR',protocol='test-v1',source_session_id=t,observed_at='2026-11-11T10:00:00+00:00') for t in ('C01','C02')];self.assertEqual(policy.select(c)['action'],'baseline')

class NativeTests(IntegrationTests):
    def setUp(self):
        import time
        from accounts import password_hash
        resources=ExitStack();self.addCleanup(resources.close)
        self.temp=Path(resources.enter_context(tempfile.TemporaryDirectory()))
        resources.enter_context(patch.dict(os.environ,{k:str(self.temp/k) for k in ('NEUROVISION_DATA_DIR','NEUROTWIN_MODEL_DIR','NEUROTWIN_POLICY_FILE','NEUROTWIN_ANATOMY_DIR','NEUROPULSE_DATA_DIR')}))
        self.app=create_app(self.temp/'operator',password='fictional-nc-operator')
        self.store=self.app.state.store
        password='Fictional integration test 773!'
        with self.app.state.accounts.connect() as c:
            c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(str(uuid4()),'quest@example.test','Test admin',password_hash(password),'admin','active',time.time()))
        self.base=resources.enter_context(serve(self.app))
        self.client=LocalClient(self.base);self.client.headers['X-NeuroAccess-Request']='1'
        self.assertEqual(self.client.post('/api/login',json={'email':'quest@example.test','password':password}).status_code,200)
        self.assertEqual(self.client.post('/api/admin/workspace',json={'target':'legacy','password':password,'reason':'Isolated synthetic NeuroQuest integration test'}).status_code,200)
        self.pid=self.make_person();self.cid=self.checkin(self.pid)

    def test_quest_superseded_retry(self):
        self.grant();op=str(uuid4());self.assertEqual(self.quest(operation_id=op).status_code,200)
        self.assertEqual(self.quest(signs=['speech'],checkin_id=None).status_code,200)
        self.assertEqual(self.quest(operation_id=op).status_code,409)
    def test_quest_history_currentness(self):
        self.grant();r=self.quest();self.assertEqual(r.status_code,200,r.text)
        data=self.client.get('/api/neuroquest/v1/participants/'+self.pid+'?mode=demo').json()
        self.assertEqual(data['current_decision_id'],r.json()['decision_id'])
        self.assertEqual(data['decisions'][0]['lifecycle'],'current')
    def test_quest_expired_retry(self):
        self.grant();op=str(uuid4());r=self.quest(operation_id=op);self.assertEqual(r.status_code,200,r.text)
        from datetime import datetime,timedelta
        later=(datetime.fromisoformat(r.json()['selected_at'])+timedelta(minutes=6)).isoformat()
        with patch('bainp_quest_router.now',return_value=later):
            self.assertEqual(self.quest(operation_id=op).status_code,409)

    def quest(self,**extra):
        body=dict(operation_id=str(uuid4()),checkin_id=self.cid,concerns_checked=True);body.update(extra)
        return self.client.post('/api/neuroquest/v1/participants/'+self.pid+'/recommendations?mode=demo',json=body)
    def test_quest_auth_boundary(self):
        from local_http import LocalClient
        self.assertEqual(LocalClient(self.base).get('/api/neuroquest/v1/registry').status_code,401)
        self.grant();r=self.client.post('/api/neuroquest/v1/participants/'+self.pid+'/recommendations?mode=demo',json=None,headers={'X-NeuroAccess-Request':'0'});self.assertEqual(r.status_code,403)
    def test_quest_withdrawal_prevents_replay(self):
        self.grant();op=str(uuid4());self.assertEqual(self.quest(operation_id=op).status_code,200);self.grant(revision=1,enabled=False);self.assertEqual(self.quest(operation_id=op).status_code,403)
    def test_quest_history_scope_hides_retained_evidence(self):
        self.grant();self.quest();self.grant(revision=1,history_allowed=False)
        r=self.client.get('/api/neuroquest/v1/participants/'+self.pid+'?mode=demo');self.assertEqual(r.json()['decisions'],[])
    def test_quest_urgent_does_not_depend_on_routine_services(self):
        self.grant()
        with patch.object(self.app.state.neurocontinuum.ports,'access',side_effect=RuntimeError('offline')),patch.object(self.app.state.neurocontinuum.ports,'history',side_effect=RuntimeError('offline')):
            r=self.quest(signs=['face'],checkin_id=None)
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['action'],'urgent_guidance');self.assertEqual(r.json()['context']['guard']['allowed_actions'],[])
    def test_quest_urgent_blocks_open_workflow(self):
        sid=self.assessing();r=self.quest(signs=['limb'],checkin_id=None)
        self.assertEqual(r.status_code,200,r.text);item=self.item(sid);self.assertEqual(item['state'],'BLOCKED');self.assertIsNone(item['payload']['recommendation']);self.assertEqual(item['payload']['safety']['state'],'escalate')
        audit=self.call('/sessions/'+sid+'/evidence')['audit'];self.assertTrue(audit['valid'])
    def test_quest_review_without_checkin_or_history_dependency(self):
        self.grant()
        with patch.object(self.app.state.neurocontinuum.ports,'history',side_effect=RuntimeError('offline')):
            r=self.quest(functional_concern=True,checkin_id=None)
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['action'],'professional_review')
    def test_quest_routine_requires_checkin(self):
        self.grant();self.assertEqual(self.quest(checkin_id=None).status_code,422)
    def test_quest_native(self):
        self.grant();r=self.quest();self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['action'],'baseline');self.assertEqual(r.json()['task_ids'],__import__('battery').ORDER)
    def test_quest_mode_isolation(self):
        self.grant();r=self.client.get('/api/neuroquest/v1/participants/'+self.pid+'?mode=active');self.assertEqual(r.status_code,404)
    def test_quest_idempotency(self):
        self.grant();op=str(uuid4());a=self.quest(operation_id=op);b=self.quest(operation_id=op);self.assertEqual(a.json()['decision_id'],b.json()['decision_id']);self.assertTrue(b.json()['replayed']);self.assertEqual(self.quest(operation_id=op,functional_concern=True).status_code,409)
    def test_quest_urgent(self):
        self.grant();r=self.quest(signs=['limb']);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['action'],'urgent_guidance')
    def test_quest_workflow_careloop(self):
        self.grant(case_tracking=True);r=self.quest(functional_concern=True);self.assertEqual(r.status_code,200,r.text);sid=self.start()
        for _ in range(4):out=self.cmd(sid)
        self.assertEqual(out['state'],'COMPLETED');self.assertTrue(self.item(sid)['payload']['care_case_id'])
    def test_quest_rechecks_withdrawal(self):
        self.grant();self.quest();self.grant(revision=1,enabled=False);self.assertEqual(self.quest().status_code,403)

def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(PureTests)
    for name in loader.getTestCaseNames(NativeTests):
        if name.startswith('test_quest_'):suite.addTest(NativeTests(name))
    return suite
if __name__=='__main__':unittest.main(verbosity=2)
