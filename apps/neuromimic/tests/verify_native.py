import sys,json,unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
APPS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(APPS/'neurocontinuum/tests'))
from verify import IntegrationTests
from local_http import LocalClient
class NativeTests(IntegrationTests):
    def req(self,module,suffix='',body=None,method='POST',mode='demo'):
        return self.client.request('GET' if body is None else method,'/api/'+module+'/v1/participants/'+self.pid+suffix+'?mode='+mode,json=body)
    def permit(self,module='neuromimic',enabled=True,revision=0):
        r=self.req(module,'/consent',dict(operation_id=str(uuid4()),expected_revision=revision,enabled=enabled),'PUT');self.assertEqual(r.status_code,200,r.text)
    def body(self):return dict(operation_id=str(uuid4()),consent_revision=1,concerns=[dict(domain=d,state='concern_reported' if d=='sleep' else 'unknown') for d in ('sleep','medication_review','vitamin_b12','thyroid','metabolic')])
    def review(self):
        r=self.req('neuromimic','/reviews',self.body());self.assertEqual(r.status_code,200,r.text);return r.json()
    def test_native_auth(self):
        self.assertEqual(LocalClient(self.base).get('/api/neuromimic/v1/participants/'+self.pid+'?mode=demo').status_code,401)
        self.assertEqual(self.client.post('/api/neuroproof/v1/participants/'+self.pid+'/passports?mode=demo',headers={'X-NeuroAccess-Request':'0'}).status_code,403)
    def test_native_default_off(self):self.assertEqual(self.req('neuromimic','/reviews',self.body()).status_code,403)
    def test_native_identity(self):
        self.permit();self.assertEqual(self.req('neuromimic','/reviews',self.body(),mode='active').status_code,404)
    def test_native_review(self):
        self.permit();r=self.review()['review'];self.assertEqual(r['action'],'professional_review');self.assertEqual(len(r['findings']),1);self.assertEqual(len(r['missing_domains']),4)
    def test_native_idempotence(self):
        self.permit();b=self.body();a=self.req('neuromimic','/reviews',b).json();self.assertEqual(a['id'],self.req('neuromimic','/reviews',b).json()['id']);b['functional_concern']=True;self.assertEqual(self.req('neuromimic','/reviews',b).status_code,409)
    def test_native_duplicate_domain(self):
        self.permit();b=self.body();b['concerns'][1]=b['concerns'][0];self.assertEqual(self.req('neuromimic','/reviews',b).status_code,422)
    def test_native_guard_missing(self):
        self.permit()
        with patch.dict(sys.modules,{'bainp_guard':None}):self.assertEqual(self.req('neuromimic','/reviews',self.body()).status_code,503)
    def test_native_urgent(self):
        self.permit();b=self.body();b['signs']=['face'];r=self.req('neuromimic','/reviews',b).json()['review'];self.assertEqual(r['action'],'urgent_guard_path');self.assertEqual(r['findings'],[])
    def test_native_revocation(self):
        self.permit();b=self.body();self.req('neuromimic','/reviews',b);self.permit(enabled=False,revision=1);self.assertEqual(self.req('neuromimic').json()['records'],[]);self.assertEqual(self.req('neuromimic','/reviews',b).status_code,403)
    def test_native_careloop(self):
        self.permit();rid=self.review()['id'];b=dict(operation_id=str(uuid4()));self.assertEqual(self.req('neuromimic','/reviews/'+rid+'/case',b).status_code,403);self.grant(case_tracking=True);a=self.req('neuromimic','/reviews/'+rid+'/case',b);self.assertEqual(a.status_code,200,a.text);second=self.req('neuromimic','/reviews/'+rid+'/case',dict(operation_id=str(uuid4())));self.assertEqual(a.json()['case_id'],second.json()['case_id']);self.assertFalse(a.json()['contacted_clinician'])
    def test_native_proof_and_withdrawal(self):
        self.permit();self.permit('neuroproof');rid=self.review()['id'];b=dict(operation_id=str(uuid4()),consent_revision=1,source='mimic',source_id=rid);r=self.req('neuroproof','/passports',b);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['passport']['clinical_correctness'],'NOT_ESTABLISHED');self.assertEqual(r.json()['id'],self.req('neuroproof','/passports',b).json()['id']);self.permit(enabled=False,revision=1);self.assertEqual(self.req('neuroproof').json()['records'],[]);self.assertEqual(self.req('neuroproof','/passports',b).status_code,403)
    def test_native_tamper(self):
        self.permit();self.permit('neuroproof');rid=self.review()['id']
        with self.store.connect(True) as c:c.execute("UPDATE nm_reviews SET sha256='tampered' WHERE id=?",(rid,))
        b=dict(operation_id=str(uuid4()),consent_revision=1,source='mimic',source_id=rid);self.assertEqual(self.req('neuroproof','/passports',b).status_code,409)
    def test_native_quest_passport(self):
        self.permit('neuroproof');self.grant()
        body=dict(operation_id=str(uuid4()),checkin_id=self.cid,concerns_checked=True)
        r=self.client.post('/api/neuroquest/v1/participants/'+self.pid+'/recommendations?mode=demo',json=body);self.assertEqual(r.status_code,200,r.text)
        rid=r.json()['decision_id'];result=self.req('neuroproof','/passports',dict(operation_id=str(uuid4()),consent_revision=1,source='quest',source_id=rid));self.assertEqual(result.status_code,200,result.text)
    def test_native_delete_cascade(self):
        self.permit();self.review()
        with self.store.connect(True) as c:
            c.execute('DELETE FROM participants WHERE id=?',(self.pid,))
            self.assertEqual(c.execute('SELECT count(*) FROM nm_reviews WHERE participant_id=?',(self.pid,)).fetchone()[0],0)
def load_tests(loader,tests,pattern):return unittest.TestSuite(NativeTests(n) for n in loader.getTestCaseNames(NativeTests) if n in NativeTests.__dict__ and n.startswith('test_native_'))
if __name__=='__main__':unittest.main(verbosity=2)
