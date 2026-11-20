"""Native integration verification. Only fictional data in temporary databases.

Assessment-completion fixtures arrange stored source rows; these tests do not
validate human cognitive performance, task timing, scientific scoring or diagnosis.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from local_http import LocalClient, serve
APPS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(APPS/'neuroaccess/backend'))
from api import create_app

PROFILE=dict(display_name='Fictional NC integration participant',age=60,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
PRACTICE=dict(protocol='access-practice-v1',interface_language='en',events=[dict(kind='activate',response='button',elapsed_ms=150.0,input='keyboard'),dict(kind='match',response='triangle',elapsed_ms=200.0,input='keyboard'),dict(kind='match',response='circle',elapsed_ms=450.0,input='keyboard')],focus_changes=0)
DEVICE=dict(user_agent='isolated-native-workflow-fixture',width=1200,height=800,pixel_ratio=1.0,pointer='fine',refresh_median_ms=16.7,refresh_max_ms=18.0,timer_resolution_ms=.1)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        resources=ExitStack();self.addCleanup(resources.close)
        self.temp=Path(resources.enter_context(tempfile.TemporaryDirectory()))
        resources.enter_context(patch.dict(os.environ,{k:str(self.temp/k) for k in ('NEUROVISION_DATA_DIR','NEUROTWIN_MODEL_DIR','NEUROTWIN_POLICY_FILE','NEUROTWIN_ANATOMY_DIR','NEUROPULSE_DATA_DIR')}))
        self.app=create_app(self.temp/'operator',password='fictional-nc-operator')
        self.store=self.app.state.store
        self.base=resources.enter_context(serve(self.app))
        self.client=LocalClient(self.base);self.client.headers['X-NeuroAccess-Request']='1'
        self.assertEqual(self.client.post('/api/login',json={'password':'fictional-nc-operator'}).status_code,200)
        self.pid=self.make_person()
        self.cid=self.checkin(self.pid)

    def make_person(self,mode='demo'):
        pid=str(uuid4())
        response=self.client.post('/api/participants',json=dict(id=pid,mode=mode,profile=PROFILE,consent_to_store=True))
        self.assertEqual(response.status_code,201,response.text)
        return pid

    def checkin(self,pid,mode='demo',acute='no',prepare=True):
        cid=str(uuid4())
        response=self.client.post(f'/api/participants/{pid}/checkins?mode={mode}',json=dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning=acute))
        self.assertEqual(response.status_code,201,response.text)
        if prepare and acute=='no':
            self.assertEqual(self.client.put(f'/api/checkins/{cid}/practice?mode={mode}',json=PRACTICE).status_code,200)
        return cid

    def call(self,path,body=None,method='POST',mode='demo',status=200):
        result=self.client.request('GET' if body is None else method,'/api/neurocontinuum/v1'+path+('?mode='+mode),json=body)
        self.assertEqual(result.status_code,status,result.text)
        return result.json()

    def grant(self,pid=None,revision=0,**updates):
        body=dict(operation_id=str(uuid4()),expected_revision=revision,enabled=True,history_allowed=True,assessment_allowed=True,case_tracking=False)
        body.update(updates)
        return self.call('/participants/'+(pid or self.pid)+'/consent',body,method='PUT')

    def start(self,cid=None,pid=None):
        return self.call('/participants/'+(pid or self.pid)+'/sessions',dict(operation_id=str(uuid4()),session_id=str(uuid4()),checkin_id=cid or self.cid))['session_id']

    def work(self):
        return self.call('/participants/'+self.pid+'/workspace')

    def item(self,sid):
        return next(s for s in self.work()['sessions'] if s['id']==sid)

    def cmd(self,sid,action='advance',version=None,status=200,**fields):
        body=dict(operation_id=str(uuid4()),expected_version=version or self.item(sid)['version'],action=action,signs=[])
        body.update(fields)
        return self.call('/sessions/'+sid+'/commands',body,status=status)

    def assessing(self):
        self.grant();sid=self.start()
        for expected in ['AUTHORIZED','VALIDATING','AWAITING_ACTION','ASSESSING']:
            self.assertEqual(self.cmd(sid)['state'],expected)
        return sid

    def complete_source_fixture(self,sid,flagged=False):
        # Real native session-creation endpoint; only source completion is an isolated fixture.
        workflow=self.item(sid)
        response=self.client.post('/api/ncx/checkins/'+workflow['checkin_id']+'/sessions?mode=demo',json=dict(id=str(uuid4()),device=DEVICE,battery='core'))
        self.assertEqual(response.status_code,201,response.text)
        native=response.json()
        with self.store.connect(True) as c:
            for index,task in enumerate(native['order']):
                summary=dict(correct=3,median_correct_rt_ms=250.0,quality_flags=['DEVICE_FRAME_INSTABILITY'] if flagged and index==0 else [],clinical_score=None)
                c.execute('INSERT INTO nc_attempts VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),native['id'],task,'completed',native['created_at'],native['created_at'],'{}',json.dumps(summary)))
        return native

    def test_existing_authentication_and_request_boundary(self):
        anonymous=LocalClient(self.base)
        self.assertEqual(anonymous.get('/api/neurocontinuum/v1/status').status_code,401)
        self.assertEqual(self.client.post('/api/neurocontinuum/v1/participants/'+self.pid+'/sessions?mode=demo',json={},headers={'X-NeuroAccess-Request':'0'}).status_code,403)
        self.assertEqual(self.client.get('/api/neurocontinuum/v1/status',headers={'Origin':'https://outside.example'}).status_code,403)

    def test_native_guard_and_careloop_adapters(self):
        state=self.call('/status')
        self.assertTrue(state['guard_connected']);self.assertTrue(state['careloop_connected'])
        self.assertEqual(state['storage'],'existing BAINP SQLite')
        self.assertFalse(state['independent_clinician_roles'])

    def test_explicit_consent_and_strict_payload(self):
        self.call('/participants/'+self.pid+'/sessions',dict(operation_id=str(uuid4()),session_id=str(uuid4()),checkin_id=self.cid),status=409)
        self.call('/participants/'+self.pid+'/consent',dict(operation_id=str(uuid4()),expected_revision=0,enabled='true',history_allowed=True,assessment_allowed=True,case_tracking=False),method='PUT',status=422)

    def test_start_idempotency_and_single_open_session(self):
        self.grant();body=dict(operation_id=str(uuid4()),session_id=str(uuid4()),checkin_id=self.cid)
        first=self.call('/participants/'+self.pid+'/sessions',body)
        self.assertTrue(self.call('/participants/'+self.pid+'/sessions',body)['replayed'])
        self.assertEqual(self.start(),first['session_id'])
        self.assertEqual(len(self.work()['sessions']),1)
        self.assertEqual(len(self.call('/sessions/'+first['session_id']+'/evidence')['audit']['events']),1)

    def test_same_operation_different_intent_rejected(self):
        self.grant();body=dict(operation_id=str(uuid4()),session_id=str(uuid4()),checkin_id=self.cid)
        self.call('/participants/'+self.pid+'/sessions',body)
        self.call('/participants/'+self.pid+'/sessions',body|{'session_id':str(uuid4())},status=409)

    def test_participant_and_mode_isolation(self):
        self.grant();other=self.make_person();foreign=self.checkin(other)
        self.call('/participants/'+self.pid+'/sessions',dict(operation_id=str(uuid4()),session_id=str(uuid4()),checkin_id=foreign),status=422)
        self.call('/participants/'+self.pid+'/workspace',mode='active',status=404)
        sid=self.start();self.call('/sessions/'+sid+'/evidence',mode='active',status=404)

    def test_existing_access_hold_cannot_be_overridden(self):
        self.grant();blocked=self.checkin(self.pid,acute='yes',prepare=False)
        sid=self.start(cid=blocked)
        self.assertEqual(self.cmd(sid)['state'],'BLOCKED')
        self.assertIn('EXISTING_ACCESS_GATE_HOLD',self.item(sid)['payload']['access_reasons'])

    def test_profile_revision_change_blocks_old_checkin(self):
        self.grant();sid=self.start()
        response=self.client.request('PATCH','/api/participants/'+self.pid+'?mode=demo',json=dict(revision=1,profile=PROFILE|{'text_size':'large'}))
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.cmd(sid)['state'],'BLOCKED')

    def test_native_assessment_path_no_fake_result(self):
        sid=self.assessing();item=self.item(sid)
        self.assertIn('/cognition?',item['payload']['recommendation']['url'])
        self.assertIn(self.cid,item['payload']['recommendation']['url'])
        self.assertEqual(self.cmd(sid,'sync')['state'],'ASSESSING')
        self.assertEqual(self.item(sid)['payload']['assessment_status'],'not_started')
        self.assertEqual(self.work()['observation_references'],[])

    def test_existing_source_results_preserved_without_rescoring(self):
        sid=self.assessing();native=self.complete_source_fixture(sid)
        self.assertEqual(self.cmd(sid,'sync')['state'],'RECORDING')
        self.assertEqual(self.cmd(sid)['state'],'COMPLETED')
        refs=self.work()['observation_references']
        self.assertEqual(len(refs),len(native['order']))
        self.assertTrue(all(r['source_session_id']==native['id'] and not r['clinical_validation'] for r in refs))
        with self.store.connect() as c:
            self.assertEqual(json.loads(c.execute('SELECT summary FROM nc_attempts LIMIT 1').fetchone()[0])['median_correct_rt_ms'],250.0)
        audit=self.call('/sessions/'+sid+'/evidence')['audit'];self.assertTrue(audit['valid'])

    def test_quality_flags_quarantined_and_native_case_reused(self):
        sid=self.assessing();self.grant(revision=1,case_tracking=True)
        self.cmd(sid,'resume')
        for _ in range(3):self.cmd(sid)
        native=self.complete_source_fixture(sid,flagged=True)
        self.cmd(sid,'sync');self.cmd(sid)
        summary=self.item(sid)['payload']['summary']
        self.assertEqual(summary['quarantined_references'],1)
        self.assertEqual(summary['accepted_references'],len(native['order'])-1)
        case_id=summary['care_case_id'];self.assertTrue(case_id)
        self.cmd(sid,'request_review');self.assertEqual(len(self.work()['cases']),1)
        case=self.client.get('/api/prevention/cases/'+case_id+'?mode=demo&person='+self.pid)
        self.assertEqual(case.status_code,200,case.text);self.assertEqual(case.json()['state'],'review_requested')

    def test_native_guard_rejection_rolls_back_reference_insert(self):
        sid=self.assessing();self.complete_source_fixture(sid);self.cmd(sid,'sync')
        with patch('bainp_guard.check_claim',return_value={'state':'block'}):
            self.cmd(sid,status=503)
        self.assertEqual(self.item(sid)['state'],'RECORDING')
        self.assertEqual(self.work()['observation_references'],[])

    def test_pause_resume_and_cancellation(self):
        sid=self.assessing();self.cmd(sid,'pause');self.assertEqual(self.item(sid)['state'],'PAUSED')
        self.cmd(sid,'resume');self.assertEqual(self.item(sid)['state'],'AUTHORIZED')
        self.assertIsNone(self.item(sid)['payload']['safety'])
        self.cmd(sid,'cancel');self.cmd(sid,status=409)

    def test_consent_change_blocks_and_hides_history(self):
        sid=self.assessing();self.grant(revision=1,enabled=False,history_allowed=False,assessment_allowed=False)
        item=self.item(sid);self.assertEqual(item['state'],'BLOCKED')
        self.assertNotIn('history',item['payload'])
        self.call('/sessions/'+sid+'/evidence',status=403)

    def test_source_dependency_failure_not_success(self):
        self.grant();sid=self.start();self.cmd(sid)
        with patch.object(self.app.state.neurocontinuum.ports,'history',side_effect=RuntimeError('unavailable')):
            self.assertEqual(self.cmd(sid)['state'],'FAILED')
        self.assertIsNone(self.item(sid)['payload']['result'])
        self.cmd(sid,'retry');self.assertEqual(self.item(sid)['state'],'AUTHORIZED')

    def test_guard_unavailable_blocks_task_selection(self):
        self.grant();sid=self.start();self.cmd(sid);self.cmd(sid)
        with patch.object(self.app.state.neurocontinuum.ports,'guard_ready',return_value=False):
            self.assertEqual(self.cmd(sid)['state'],'FAILED')

    def test_independent_workflow_guard_abstention_is_binding(self):
        self.grant();sid=self.start();self.cmd(sid);self.cmd(sid)
        with patch('bainp_continuum_guard.evaluate',return_value={'state':'abstain','allowed_actions':[]}):
            self.assertEqual(self.cmd(sid)['state'],'BLOCKED')
        self.assertIsNone(self.item(sid)['payload']['recommendation'])

    def test_workflow_guard_binds_identity_mode_and_restrictions(self):
        from bainp_continuum_guard import evaluate
        base=dict(participant_id=self.pid,source_participant_id=self.pid,mode='demo',source_mode='demo',
                  checkin_id=self.cid,monitoring_consent=True,assessment_consent=True,native_guard_available=True,access_reasons=[])
        self.assertEqual(evaluate(base)['allowed_actions'],['existing_neurocognition'])
        for change in ({'source_participant_id':str(uuid4())},{'source_mode':'active'},{'access_reasons':['hold']},{'assessment_consent':False}):
            self.assertEqual(evaluate(base|change)['state'],'abstain')
            self.assertEqual(evaluate(base|change)['allowed_actions'],[])
        self.assertFalse(evaluate(base)['clinical_clearance'])

    def test_stale_version_and_duplicate_command(self):
        self.grant();sid=self.start();body=dict(operation_id=str(uuid4()),expected_version=1,action='advance',signs=[])
        self.call('/sessions/'+sid+'/commands',body)
        self.assertTrue(self.call('/sessions/'+sid+'/commands',body)['replayed'])
        self.cmd(sid,version=1,status=409)

    def test_concurrent_intents_do_not_lose_updates(self):
        self.grant();sid=self.start();engine=self.app.state.neurocontinuum
        bodies=[dict(operation_id=str(uuid4()),expected_version=1,action='advance',signs=[]) for _ in range(2)]
        def run(body):
            from fastapi import HTTPException
            try:return engine.command(sid,'demo',body)['version']
            except HTTPException as e:return e.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,bodies))
        self.assertEqual(sorted(results),[2,409])
        self.assertEqual(self.item(sid)['version'],2)

    def test_warning_path_native_guidance_without_false_referral(self):
        self.grant();sid=self.start();self.grant(revision=1,enabled=False,assessment_allowed=False)
        self.assertEqual(self.cmd(sid,'safety',signs=['speech'])['state'],'COMPLETED')
        item=self.item(sid)
        self.assertEqual(item['payload']['safety']['state'],'escalate')
        self.assertEqual(item['payload']['summary']['delivery'],'NO_EXTERNAL_CONTACT')
        self.assertEqual(self.work()['cases'],[])

    def test_participant_deletion_cascades_extension_data(self):
        sid=self.assessing()
        response=self.client.delete('/api/participants/'+self.pid+'?mode=demo',json=dict(confirm_id=self.pid,revision=1))
        self.assertEqual(response.status_code,200,response.text)
        with self.store.connect() as c:
            for table in ('ncw_consents','ncw_sessions','ncw_operations','ncw_events','ncw_observation_refs'):
                self.assertEqual(c.execute('SELECT count(*) FROM '+table).fetchone()[0],0)

    def test_audit_tamper_detection(self):
        self.grant();sid=self.start()
        with self.store.connect(True) as c:
            c.execute("UPDATE ncw_events SET sha256='modified' WHERE session_id=?",(sid,))
        self.assertFalse(self.call('/sessions/'+sid+'/evidence')['audit']['valid'])

    def test_unknown_command_never_runs_arbitrary_script(self):
        self.grant();sid=self.start()
        self.call('/sessions/'+sid+'/commands',dict(operation_id=str(uuid4()),expected_version=1,action='run_mri',signs=[]),status=422)
        self.assertEqual(self.item(sid)['version'],1)

    def test_existing_platform_registry_preserved(self):
        result=self.client.get('/api/platform/v1/status')
        if result.status_code==404:
            self.skipTest('Optional Platform Core is not installed.')
        self.assertEqual(result.status_code,200,result.text)
        names={m['name'] for m in result.json()['modules']}
        self.assertIn('NeuroContinuum',names)
        self.assertTrue({'NeuroAccess','NeuroCognition X','NeuroGuard','CareLoop'}.issubset(names))

    def test_native_twin_receives_workflow_markers_only(self):
        if not (APPS/'neurotwin/backend/router.py').is_file():
            self.skipTest('Optional NeuroTwin source is not installed.')
        self.grant();sid=self.start()
        result=self.client.get('/api/neurotwin/participants/'+self.pid+'?mode=demo')
        self.assertEqual(result.status_code,200,result.text)
        self.assertIn('neurocontinuum',result.json())
        marker=result.json()['neurocontinuum']
        self.assertEqual(marker['sessions'][0]['id'],sid)
        self.assertNotIn('disease_probability',marker)

if __name__=='__main__':
    unittest.main(verbosity=2)
