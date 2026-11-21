"""Reproducible engineering tests in temporary fictional databases; not clinical validation."""
from datetime import datetime,timezone,timedelta
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
APPS=Path(__file__).resolve().parents[2];sys.path.insert(0,str(APPS/'neurocontinuum/tests'))
from verify import IntegrationTests
from local_http import LocalClient
class ShadowTests(IntegrationTests):
    def request(self,suffix,body=None,method='POST',pid=None,mode='demo'):
        return self.client.request('GET' if body is None else method,'/api/neuroshadow/v1/participants/'+(pid or self.pid)+suffix+'?mode='+mode,json=body)
    def permission(self,revision=0,enabled=True,share=False):
        r=self.request('/consent',dict(operation_id=str(uuid4()),expected_revision=revision,enabled=enabled,share_context=share),'PUT');self.assertEqual(r.status_code,200,r.text);return r.json()
    def begin_shadow(self,**extra):
        body=dict(operation_id=str(uuid4()),session_id=str(uuid4()),consent_revision=1,activity='shadow-explore-v1',device=dict(width_bucket=12,height_bucket=8,pixel_ratio_bucket=1,pointer='mouse',reduced_motion=False));body.update(extra)
        r=self.request('/sessions',body);self.assertEqual(r.status_code,200,r.text)
        return r.json()['session_id'],body
    def sample(self,**extra):
        body=dict(operation_id=str(uuid4()),consent_revision=1,duration_ms=10000,events=[dict(t_ms=i*100,kind='move',pointer='mouse',x_bin=i%21,y_bin=(i//3)%21) for i in range(100)],frame_count=500,slow_frames=0,hidden_count=0,resize_count=0);body.update(extra);return body
    def finish_shadow(self,sid,body=None):
        with self.store.connect(True) as c:c.execute('UPDATE ns_sessions SET started_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=11)).isoformat(),sid))
        return self.request('/sessions/'+sid+'/finish',body or self.sample())
    def test_shadow_default_off(self):
        r=self.request('');self.assertEqual(r.status_code,200);self.assertFalse(r.json()['consent']['enabled'])
        r=self.request('/sessions',dict(operation_id=str(uuid4()),session_id=str(uuid4()),consent_revision=1,activity='shadow-explore-v1',device=dict(width_bucket=12,height_bucket=8,pixel_ratio_bucket=1,pointer='mouse',reduced_motion=False)));self.assertEqual(r.status_code,403)
    def test_shadow_auth_and_csrf(self):
        self.assertEqual(LocalClient(self.base).get('/api/neuroshadow/v1/participants/'+self.pid+'?mode=demo').status_code,401)
        r=self.client.post('/api/neuroshadow/v1/participants/'+self.pid+'/sessions?mode=demo',json=None,headers={'X-NeuroAccess-Request':'0'});self.assertEqual(r.status_code,403)
    def test_shadow_active_demo_isolation(self):self.assertEqual(self.request('',mode='active').status_code,404)
    def test_shadow_aggregates_only(self):
        self.permission();sid,_=self.begin_shadow();r=self.finish_shadow(sid);self.assertEqual(r.status_code,200,r.text);summary=r.json()['summary'];self.assertFalse(summary['raw_events_stored']);self.assertEqual(summary['quality']['state'],'TECHNICAL_QC_CLEAR')
        with self.store.connect() as c:
            row=c.execute('SELECT summary FROM ns_sessions WHERE id=?',(sid,)).fetchone()[0]
            self.assertNotIn('x_bin',row);self.assertNotIn('events',json.loads(row));self.assertNotIn('"events":', ''.join(r[0] for r in c.execute('SELECT response FROM ncw_operations')))
    def test_shadow_unknown_typed_content_rejected(self):
        self.permission();sid,_=self.begin_shadow();body=self.sample();body['typed_content']='not permitted';self.assertEqual(self.finish_shadow(sid,body).status_code,422)
    def test_shadow_arbitrary_activity_rejected(self):
        self.permission();r=self.request('/sessions',dict(operation_id=str(uuid4()),session_id=str(uuid4()),consent_revision=1,activity='password-form',device=dict(width_bucket=12,height_bucket=8,pixel_ratio_bucket=1,pointer='mouse',reduced_motion=False)));self.assertEqual(r.status_code,422)
    def test_shadow_short_quarantined(self):
        self.permission();sid,_=self.begin_shadow();r=self.finish_shadow(sid,self.sample(duration_ms=0,events=[],frame_count=0));self.assertEqual(r.json()['summary']['quality']['state'],'QUARANTINED')
    def test_shadow_lag_interruption_and_resize(self):
        self.permission();sid,_=self.begin_shadow();r=self.finish_shadow(sid,self.sample(slow_frames=100,hidden_count=1,resize_count=1));flags=r.json()['summary']['quality']['flags'];self.assertIn('CLIENT_FRAME_INSTABILITY',flags);self.assertIn('ACTIVITY_INTERRUPTED',flags);self.assertIn('VIEWPORT_CHANGED',flags)
    def test_shadow_impossible_server_duration(self):
        self.permission();sid,_=self.begin_shadow();r=self.request('/sessions/'+sid+'/finish',self.sample());self.assertIn('CLIENT_SERVER_DURATION_MISMATCH',r.json()['summary']['quality']['flags'])
    def test_shadow_event_order_rejected(self):
        self.permission();sid,_=self.begin_shadow();body=self.sample();body['events'].reverse();self.assertEqual(self.finish_shadow(sid,body).status_code,422)
    def test_shadow_mixed_input_rejected(self):
        self.permission();sid,_=self.begin_shadow();body=self.sample();body['events'][1]['pointer']='touch';self.assertEqual(self.finish_shadow(sid,body).status_code,422)
    def test_shadow_event_limit(self):
        self.permission();sid,_=self.begin_shadow();body=self.sample(events=[dict(t_ms=0,kind='move',pointer='mouse',x_bin=1,y_bin=1)]*2401);self.assertEqual(self.finish_shadow(sid,body).status_code,422)
    def test_shadow_revocation_blocks_buffer_and_hides_history(self):
        self.permission();sid,_=self.begin_shadow();self.permission(revision=1,enabled=False);self.assertEqual(self.finish_shadow(sid).status_code,403);self.assertEqual(self.request('').json()['sessions'],[])
    def test_shadow_regrant_cannot_upload_old_buffer(self):
        self.permission();sid,_=self.begin_shadow();self.permission(revision=1,enabled=False);self.permission(revision=2);self.assertEqual(self.finish_shadow(sid).status_code,403)
    def test_shadow_idempotency_and_conflict(self):
        self.permission();sid,begin=self.begin_shadow();r=self.request('/sessions',begin);self.assertTrue(r.json()['replayed']);body=self.sample();a=self.finish_shadow(sid,body);b=self.request('/sessions/'+sid+'/finish',body);self.assertEqual(a.json()['sha256'],b.json()['sha256']);body['resize_count']=1;self.assertEqual(self.request('/sessions/'+sid+'/finish',body).status_code,409)
    def test_shadow_one_open_and_discard(self):
        self.permission();sid,body=self.begin_shadow();body.update(operation_id=str(uuid4()),session_id=str(uuid4()));self.assertEqual(self.request('/sessions',body).status_code,409);self.assertEqual(self.request('/sessions/'+sid+'/discard',dict(operation_id=str(uuid4()))).status_code,200);self.begin_shadow()
    def test_shadow_profile_change(self):
        self.permission();sid,_=self.begin_shadow()
        with self.store.connect(True) as c:c.execute('UPDATE participants SET revision=revision+1 WHERE id=?',(self.pid,))
        self.assertEqual(self.finish_shadow(sid).status_code,409)
    def test_shadow_same_condition_comparison(self):
        self.permission()
        for _ in range(2):sid,_=self.begin_shadow();self.assertEqual(self.finish_shadow(sid).status_code,200)
        c=self.request('').json()['comparison'];self.assertEqual(c['state'],'DESCRIPTIVE_SAME_CONDITION_PAIR');self.assertFalse(c['clinical_comparability'])
    def test_shadow_device_change_not_pooled(self):
        self.permission();sid,_=self.begin_shadow();self.finish_shadow(sid);sid,_=self.begin_shadow(device=dict(width_bucket=6,height_bucket=4,pixel_ratio_bucket=1,pointer='mouse',reduced_motion=False));self.finish_shadow(sid);c=self.request('').json()['comparison'];self.assertEqual(c['state'],'INSUFFICIENT_SAME_CONDITION_SESSIONS');self.assertEqual(c['other_condition_count'],1)
    def test_shadow_guard_failure_not_success(self):
        self.permission();sid,_=self.begin_shadow()
        with patch.dict(sys.modules,{'bainp_shadow_guard':None}):r=self.finish_shadow(sid)
        self.assertEqual(r.status_code,503)
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT state FROM ns_sessions WHERE id=?',(sid,)).fetchone()[0],'COLLECTING')
    def test_shadow_sharing_opt_in_and_no_selection_influence(self):
        self.permission(share=True);sid,_=self.begin_shadow();self.finish_shadow(sid);self.grant()
        service=self.app.state.neuroquest
        with self.store.connect() as c:r=service.evaluate(c,self.pid,'demo',self.cid,dict(concerns_checked=True,functional_concern=False,quality_problem_addressed=False,target_domain='none',signs=[]))
        self.assertEqual(r['action'],'baseline');passive=r['context']['passive_context'];self.assertEqual(passive['selection_influence'],'NONE_V1');self.assertNotIn('features',passive);self.assertFalse(passive['clinical_inference_allowed'])
        self.permission(revision=1,share=False)
        with self.store.connect() as c:self.assertEqual(self.app.state.neuroshadow_context(c,self.pid,'demo')['state'],'WITHHELD_BY_NEUROSHADOW_PERMISSION')
    def test_shadow_twin_context_permission_and_identity(self):
        self.permission(share=True);sid,_=self.begin_shadow();self.finish_shadow(sid);self.grant()
        from neurocontinuum_bridge import for_twin
        value=for_twin(self.store,self.pid,'demo')['neuroshadow'];self.assertEqual(value['state'],'DESCRIPTIVE_CONTEXT_ONLY');self.assertEqual(value['reference_id'],sid)
        self.permission(revision=1,share=False);self.assertEqual(for_twin(self.store,self.pid,'demo')['neuroshadow']['state'],'WITHHELD_BY_NEUROSHADOW_PERMISSION')
    def test_shadow_tampered_summary_excluded_from_context(self):
        self.permission(share=True);sid,_=self.begin_shadow();self.finish_shadow(sid)
        with self.store.connect(True) as c:c.execute("UPDATE ns_sessions SET summary='{}' WHERE id=?",(sid,))
        with self.store.connect() as c:self.assertEqual(self.app.state.neuroshadow_context(c,self.pid,'demo')['state'],'NO_CURRENT_QC_CLEAR_CONTEXT')
    def test_shadow_deletion_cascade(self):
        self.permission();sid,_=self.begin_shadow();self.finish_shadow(sid)
        with self.store.connect(True) as c:c.execute('DELETE FROM participants WHERE id=?',(self.pid,))
        with self.store.connect() as c:
            for name in ('ns_sessions','ns_consents','ns_events'):self.assertEqual(c.execute('SELECT count(*) FROM '+name+' WHERE participant_id=?',(self.pid,)).fetchone()[0],0)

def load_tests(loader,tests,pattern):return unittest.TestSuite(ShadowTests(name) for name in loader.getTestCaseNames(ShadowTests) if name.startswith('test_shadow_'))
if __name__=='__main__':unittest.main(verbosity=2)
