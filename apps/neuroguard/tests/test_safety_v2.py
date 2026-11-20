import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from safety_v2 import evaluate, verify_execution, QC_REQUIRED, digest
from safety_store import GuardStore, AccessDenied, Conflict, verify_audit_chain
from policy_release import check_release
import continuum_policy

NOW=datetime(2026,11,16,12,tzinfo=timezone.utc)
def context(action='launch_cognitive_task'):
    return dict(workspace_id='w1',participant_id='p1',actor_id='a1',session_id='s1',mode='active',action=action,
        input_revision=1,consent_revision=1,authorized=True,service_available=True,inputs_verified=True,
        warning_reviewed=True,functional_review_required=False,urgent_signs=[],
        consents=dict(assessment=True,wearable=True,eeg=True,imaging=True,passive=True,history=True,forecast=True,care_sharing=True),
        readiness=dict(task_compatible=True,device_ready=True,instructions_understood=True),sources=[],
        observed_at=NOW.isoformat(),valid_until=(NOW+timedelta(minutes=10)).isoformat())
def source(modality):
    return dict(id='o1',revision='1',participant_id='p1',workspace_id='w1',mode='active',modality=modality,quality='usable',
                protocol='fixture-only-v1',sha256='a'*64,checks={k:True for k in QC_REQUIRED[modality]})
def run(c): return evaluate(c,now=NOW)

class PolicyTests(unittest.TestCase):
    def test_01_specific_permit(self):
        d=run(context());self.assertEqual(d['status'],'PERMIT');self.assertFalse(d['clinical_clearance']);self.assertFalse(d['emergency_ruled_out'])
    def test_02_acute_precedence(self):
        c=context();d=run(c);c['urgent_signs']=['speech'];c['consents']={}
        self.assertEqual(verify_execution(d,c,now=NOW)['status'],'URGENT_GUIDANCE')
    def test_03_revisions_invalidate(self):
        for key in ('input_revision','consent_revision'):
            c=context();d=run(c);c[key]+=1
            self.assertEqual(verify_execution(d,c,now=NOW)['reason_codes'],['STALE_OR_INVALID_DECISION'])
    def test_04_modality_consent(self):
        for action,scope in [('collect_wearable','wearable'),('collect_eeg','eeg'),('process_mri','imaging'),('collect_passive','passive')]:
            c=context(action);c['consents'][scope]=False;self.assertEqual(run(c)['status'],'HOLD')
    def test_05_unauthorized(self):
        c=context();c['authorized']=False;self.assertEqual(run(c)['allowed_actions'],[])
    def test_06_cognitive_incomplete(self):
        c=context('interpret_cognitive');s=source('cognitive');s['checks']['protocol_complete']=False;c['sources']=[s]
        self.assertIn('QC_REQUIRED:protocol_complete:o1',run(c)['reason_codes'])
    def test_07_mri_qc(self):
        c=context('interpret_mri');s=source('mri');s['checks']['segmentation_approved']=False;c['sources']=[s]
        self.assertEqual(run(c)['status'],'HOLD')
    def test_08_missing_not_normal(self):
        for modality in ('wearable','eeg'):
            c=context('interpret_'+modality);s=source(modality);s['quality']='missing';c['sources']=[s]
            self.assertIn('SOURCE_MISSING:o1',run(c)['reason_codes'])
    def test_09_no_disease_prediction(self):
        self.assertEqual(run(context('diagnose_parkinsons'))['status'],'ABSTAIN')
    def test_10_functional_review(self):
        c=context();c['functional_review_required']=True;self.assertEqual(run(c)['status'],'REVIEW')
    def test_11_local_case_not_delivery(self):
        c=context('confirm_referral_delivery');s=source('care');s['checks']['delivery_verified']=False;c['sources']=[s]
        self.assertEqual(run(c)['status'],'HOLD')
    def test_12_unavailable(self):
        for k in ('service_available','inputs_verified','warning_reviewed'):
            c=context();c[k]=False;self.assertEqual(run(c)['status'],'UNAVAILABLE')
    def test_13_serializable_passport(self):
        d=run(context());self.assertEqual(json.loads(json.dumps(d)),d);self.assertEqual(d['input_revision'],1)
    def test_14_expired_decision(self):
        c=context();d=run(c);self.assertEqual(verify_execution(d,c,now=NOW+timedelta(seconds=301))['status'],'HOLD')
    def test_15_false_string_rejected(self):
        for k in ('authorized','service_available','inputs_verified'):
            c=context();c[k]='false';self.assertEqual(run(c)['status'],'UNAVAILABLE')
    def test_16_invalid_context(self):
        for c in (None,[],{},'x',{'authorized':True}): self.assertEqual(run(c)['status'],'UNAVAILABLE')
    def test_17_missing_boolean(self):
        c=context();del c['warning_reviewed'];self.assertEqual(run(c)['status'],'UNAVAILABLE')
    def test_18_source_identity(self):
        c=context('interpret_mri');s=source('mri');s['participant_id']='p2';c['sources']=[s]
        self.assertIn('SOURCE_IDENTITY_MISMATCH:o1',run(c)['reason_codes'])
    def test_19_bad_timestamps(self):
        for time in ('invalid','2026-11-16T12:00:00'):
            c=context();c['valid_until']=time;self.assertEqual(run(c)['status'],'UNAVAILABLE')
    def test_20_vision_not_blanket_block(self):
        c=context();c['reported_vision_limitation']=True
        self.assertEqual(run(c)['status'],'PERMIT')
        c['readiness']['task_compatible']=False;self.assertEqual(run(c)['status'],'HOLD')
    def test_21_unsupported_model(self):
        c=context('research_forecast');s=source('model');s['checks']['model_review_current']=False;c['sources']=[s]
        self.assertEqual(run(c)['status'],'ABSTAIN')
    def test_22_legacy_strict_consent(self):
        c=dict(participant_id='p',source_participant_id='p',mode='active',source_mode='active',monitoring_consent=True,assessment_consent=True,native_guard_available=True,checkin_id='c',access_reasons=[])
        self.assertEqual(continuum_policy.evaluate(c)['state'],'workflow_permitted')
        c['assessment_consent']='false';self.assertEqual(continuum_policy.evaluate(c)['state'],'abstain')
        c['assessment_consent']=True;c['urgent_signs']=['speech'];self.assertEqual(continuum_policy.evaluate(c)['allowed_actions'],[])
    def test_34_public_guidance_without_consent(self):
        from safety_v2 import public_warning_guidance
        self.assertEqual(public_warning_guidance(True,'hi')['status'],'URGENT_GUIDANCE')
        self.assertFalse(public_warning_guidance(False)['emergency_ruled_out'])
    def test_35_legacy_unknown_claim(self):
        import guard
        node=dict(type=None,claim='invented',eligible=True,statement='unsafe')
        self.assertEqual(guard.check_claim('invented','x',{'x':node})['state'],'block')
    def test_36_legacy_malformed_evidence(self):
        import guard
        self.assertEqual(guard.check_claim('measurement','x',{'x':{}})['reason'],'EVIDENCE_MALFORMED')
    def test_37_legacy_string_eligibility(self):
        import guard
        node=dict(type='direct_observation',claim='measurement',eligible='false',statement='x',value=2,unit='x')
        self.assertEqual(guard.check_claim('measurement','x',{'x':node},2,'x')['state'],'abstain')
    def test_23_policy_evidence(self):
        p,b=b'policy',b'pass'
        m=dict(policy_version='v2',reviewer_id='reviewer',clinical_review_reference='review',hazard_review_reference='risk',regression_reference='test',approved=True,regression_passed=True,policy_sha256=hashlib.sha256(p).hexdigest(),regression_sha256=hashlib.sha256(b).hexdigest(),reviewed_at=NOW.isoformat(),expires_at=(NOW+timedelta(days=1)).isoformat())
        self.assertEqual(check_release(m,p,b,now=NOW),[])
        self.assertIn('POLICY_HASH_MISMATCH',check_release(m,b'changed',b,now=NOW))
        m['regression_passed']=False;self.assertIn('REGRESSION_PASS_REQUIRED',check_release(m,p,b,now=NOW))

class TrackedConnection(sqlite3.Connection):
    closed = False
    def close(self):
        super().close()
        self.closed = True

class StoreTests(unittest.TestCase):
    def connect(self):
        con = sqlite3.connect(self.path, factory=TrackedConnection)
        self.connections.append(con)
        return con

    @contextmanager
    def database(self):
        con = self.connect()
        try:
            with con:
                yield con
        finally:
            con.close()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'host.sqlite'
        self.connections=[]
        con=self.connect()
        con.execute('CREATE TABLE host_context(payload TEXT)');con.execute('INSERT INTO host_context VALUES(?)',(json.dumps(context()),))
        con.execute('CREATE TABLE host_actions(id TEXT)');con.commit();con.close()
        self.store=GuardStore(self.connect,lambda db,a,w,p,op:a=='a1' and w=='w1' and p=='p1',lambda db,a,w,p,action:json.loads(db.execute('SELECT payload FROM host_context').fetchone()[0]) | {'action':action})
    def tearDown(self):
        leaked = [con for con in self.connections if not con.closed]
        try:
            self.assertEqual(len(leaked), 0, 'SQLite connection leak: close every connection explicitly')
        finally:
            for con in leaked:
                con.close()
            self.tmp.cleanup()
    def decide(self,key='d'):return self.store.decide('a1','w1','p1','launch_cognitive_task',key,now=NOW)
    def operation(self,con,d):con.execute('INSERT INTO host_actions VALUES(?)',(d['decision_id'],));return {'saved':True}
    def execute(self,d,key='e',op=None):return self.store.execute('a1','w1','p1',d['decision_id'],key,op or self.operation,now=NOW)
    def test_24_duplicate_decision(self):self.assertEqual(self.decide(),self.decide())
    def test_25_duplicate_execution(self):
        d=self.decide();self.assertTrue(self.execute(d)['executed']);self.assertTrue(self.execute(d)['replayed'])
        with self.database() as c:self.assertEqual(c.execute('SELECT count(*) FROM host_actions').fetchone()[0],1)
    def test_26_crossuser_read(self):
        d=self.decide()
        with self.assertRaises(AccessDenied):self.store.read('a2','w1','p1',d['decision_id'])
    def test_27_crossuser_write(self):
        d=self.decide()
        with self.assertRaises(AccessDenied):self.store.execute('a2','w1','p1',d['decision_id'],'x',self.operation,now=NOW)
    def test_28_execution_reloads_safety(self):
        d=self.decide();c=context();c['urgent_signs']=['speech']
        with self.database() as db:db.execute('UPDATE host_context SET payload=?',(json.dumps(c),))
        r=self.execute(d);self.assertFalse(r['executed']);self.assertEqual(r['decision']['status'],'URGENT_GUIDANCE')
    def test_29_atomic_rollback(self):
        def fail(con,d):self.operation(con,d);raise ValueError('failure')
        d=self.decide()
        with self.assertRaises(ValueError):self.execute(d,op=fail)
        with self.database() as c:self.assertEqual(c.execute('SELECT count(*) FROM host_actions').fetchone()[0],0)
    def test_30_audit(self):
        d=self.decide();self.execute(d)
        with self.database() as c:
            self.assertTrue(verify_audit_chain(c,'w1'))
            with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM ng_v2_events')
    def test_31_idempotency_conflict(self):
        self.decide();c=context();c['input_revision']=2
        with self.database() as db:db.execute('UPDATE host_context SET payload=?',(json.dumps(c),))
        with self.assertRaises(Conflict):self.decide()
    def test_32_read_logged(self):
        d=self.decide();self.assertEqual(self.store.read('a1','w1','p1',d['decision_id']),d)
        with self.database() as c:self.assertEqual(c.execute('SELECT count(*) FROM ng_v2_events').fetchone()[0],2)
    def test_38_different_key_same_decision(self):
        d=self.decide();self.execute(d)
        self.assertTrue(self.execute(d,'different')['replayed'])
        with self.database() as c:self.assertEqual(c.execute('SELECT count(*) FROM host_actions').fetchone()[0],1)
    def test_39_concurrent_retries(self):
        from concurrent.futures import ThreadPoolExecutor
        d=self.decide()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda n:self.execute(d,str(n)),range(4)))
        self.assertEqual(sum(r['executed'] for r in results),1)
    def test_40_audit_tamper_detected(self):
        self.decide()
        with self.database() as c:
            c.execute('DROP TRIGGER ng_v2_events_update')
            c.execute("UPDATE ng_v2_events SET payload='{}'")
            self.assertFalse(verify_audit_chain(c,'w1'))
    def test_41_scoped_context_rejected(self):
        self.store.load_context=lambda *a:context()|dict(workspace_id='other')
        with self.assertRaises(AccessDenied):self.decide()
    def test_33_failure_loader_no_action(self):
        d=self.decide()
        def fail(*args):raise RuntimeError('service down')
        self.store.load_context=fail
        with self.assertRaises(RuntimeError):self.execute(d)
        with self.database() as c:self.assertEqual(c.execute('SELECT count(*) FROM host_actions').fetchone()[0],0)

if __name__=='__main__':unittest.main(verbosity=2)
