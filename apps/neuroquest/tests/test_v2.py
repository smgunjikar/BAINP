"""Standalone synthetic policy regression tests. No DB, network or participant data."""
import importlib.util
from pathlib import Path
import unittest
from datetime import datetime,timedelta
spec=importlib.util.spec_from_file_location('quest',Path(__file__).resolve().parents[1]/'backend/engine.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

def ctx():
    return dict(profile=dict(language='en',can_see_and_respond='yes',assistance='none'),
        profile_revision=1,consent_revision=1,intent=dict(functional_concern=False,concerns_checked=True,target_domain='none',quality_problem_addressed=False),
        registry=dict(protocol='fixture',core=['C01','C02'],tasks=['C01','C02']),history=[],
        consent=dict(history_allowed=True,assessment_allowed=True),guard=dict(state='workflow_permitted',allowed_actions=['existing_neurocognition']),as_of='2026-11-16T12:00:00+00:00')
def ref(task='C01',quality='SOURCE_QC_CLEAR_DESCRIPTIVE_ONLY',**kw):
    return dict(task=task,quality=quality,protocol='fixture',source_id=task,source_session_id='s',form='A',observed_at='2026-11-16T11:00:00+00:00',**kw)

class Tests(unittest.TestCase):
    def test_baseline(self):self.assertTrue(policy.select(ctx())['executable'])
    def test_deterministic(self):self.assertEqual(policy.select(ctx()),policy.select(ctx()))
    def test_passport(self):self.assertEqual(policy.select(ctx())['passport']['schema'],'neuroquest-decision-passport-v2')
    def test_expiry(self):
        c=ctx();old=policy.select(c);c['as_of']='2026-11-16T12:05:00+00:00';self.assertFalse(policy.is_current(old,policy.select(c)))
    def test_fresh(self):
        c=ctx();old=policy.select(c);c['as_of']='2026-11-16T12:01:00+00:00';self.assertTrue(policy.is_current(old,policy.select(c)))
    def test_revision(self):
        for key in ('profile_revision','consent_revision'):
            c=ctx();old=policy.select(c);c[key]=2;self.assertFalse(policy.is_current(old,policy.select(c)))
    def test_urgent(self):
        c=ctx();old=policy.select(c);c['urgent']={'state':'escalate'};c['intent']['functional_concern']=True
        fresh=policy.select(c);self.assertEqual(fresh['action'],'urgent_guidance');self.assertFalse(policy.is_current(old,fresh))
    def test_pause(self):
        c=ctx();c['intent']['pause_requested']=True;d=policy.select(c);self.assertEqual(d['action'],'monitor');self.assertFalse(d['executable'])
    def test_guard_scope(self):
        c=ctx();c['guard']['allowed_actions']=[];self.assertFalse(policy.select(c)['executable'])
    def test_consent(self):
        for k in ('history_allowed','assessment_allowed'):
            c=ctx();c['consent'][k]=False;self.assertFalse(policy.select(c)['executable'])
    def test_dependency(self):
        c=ctx();c['registry']['core']=['C02','C01'];self.assertIn('MEMORY_DEPENDENCY_INVALID',policy.select(c)['reason_codes'])
    def test_unknown_quality(self):
        c=ctx();c['history']=[ref(quality='unknown')];self.assertIn('SOURCE_QUALITY_UNKNOWN',policy.select(c)['reason_codes'])
    def test_quality_flags(self):
        c=ctx();c['history']=[ref(quality='QUARANTINED',flags=['DEVICE_FRAME_INSTABILITY'])];d=policy.select(c)
        self.assertFalse(d['executable']);self.assertEqual(d['quality_issues'][0]['flags'],['DEVICE_FRAME_INSTABILITY'])
    def test_correction_not_fake_launch(self):
        c=ctx();c['history']=[ref(quality='QUARANTINED')];c['intent']['quality_problem_addressed']=True
        self.assertIn('TARGETED_EXECUTION_UNAVAILABLE',policy.select(c)['reason_codes'])
    def test_old_bad_protocol(self):
        c=ctx();r=ref(quality='QUARANTINED');r['protocol']='old';c['history']=[r];self.assertEqual(policy.select(c)['action'],'baseline')
    def test_order_independent(self):
        c=ctx();old=ref(quality='QUARANTINED');old['observed_at']='2026-11-15T11:00:00+00:00';c['history']=[old,ref()]
        self.assertEqual(policy.select(c)['action'],'baseline')
    def test_forms_not_pooled(self):
        c=ctx();a=ref();b=ref('C02');b['form']='B';c['history']=[a,b];self.assertEqual(policy.select(c)['action'],'baseline')
    def test_cooldown(self):
        c=ctx();c['history']=[ref(),ref('C02')];self.assertEqual(policy.select(c)['action'],'monitor')
    def test_vision_correction(self):
        c=ctx();c['profile'].update(vision_limitation=True,vision_aid='glasses');self.assertTrue(policy.select(c)['executable'])
    def test_targeted_not_fake(self):
        c=ctx();c['intent']['target_domain']='memory';self.assertFalse(policy.select(c)['executable'])
    def test_functional(self):
        c=ctx();c['intent']['functional_concern']=True;self.assertEqual(policy.select(c)['action'],'professional_review')
    def test_legacy_stale(self):self.assertFalse(policy.is_current({'policy':'v1'},policy.select(ctx())))
if __name__=='__main__':unittest.main(verbosity=2)
