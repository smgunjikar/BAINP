import importlib.util,unittest,json
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'neuroquest/tests/verify.py';s=importlib.util.spec_from_file_location('quest_fixture',p);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
class Tests(q.NativeTests):
 def test_information_edit_preserves_preparation(self):
  self.grant();sid=self.start()
  before=self.client.get('/api/participants/'+self.pid+'?mode=demo').json()
  with self.store.connect() as c:snapshot=dict(c.execute('SELECT * FROM checkins WHERE id=?',(self.cid,)).fetchone())
  profile=json.loads(snapshot['profile']);profile.update(display_name='Updated fictional name',age=42,education_years=15)
  r=self.client.request('PATCH','/api/participants/'+self.pid+'?mode=demo',json=dict(revision=1,profile=profile));self.assertEqual(r.status_code,200,r.text)
  self.assertTrue(self.work()['checkins'][0]['readiness_compatible'])
  for expected in ['AUTHORIZED','VALIDATING','AWAITING_ACTION','ASSESSING']:self.assertEqual(self.cmd(sid)['state'],expected)
  with self.store.connect() as c:self.assertEqual(dict(c.execute('SELECT * FROM checkins WHERE id=?',(self.cid,)).fetchone()),snapshot)
 def test_previously_blocked_can_resume(self):
  self.grant();sid=self.start()
  with self.store.connect(True) as c:
   c.execute("UPDATE ncw_sessions SET state='BLOCKED' WHERE id=?",(sid,))
  self.assertEqual(self.cmd(sid,action='resume')['state'],'AUTHORIZED')
  for expected in ['VALIDATING','AWAITING_ACTION','ASSESSING']:self.assertEqual(self.cmd(sid)['state'],expected)
 def test_readiness_edit_explained(self):
  self.grant();sid=self.start()
  with self.store.connect() as c:profile=json.loads(c.execute('SELECT profile FROM participants WHERE id=?',(self.pid,)).fetchone()['profile'])
  profile['text_size']='large'
  r=self.client.request('PATCH','/api/participants/'+self.pid+'?mode=demo',json=dict(revision=1,profile=profile));self.assertEqual(r.status_code,200,r.text)
  self.assertFalse(self.work()['checkins'][0]['readiness_compatible'])
  self.assertEqual(self.cmd(sid)['state'],'BLOCKED')
  self.assertIn('READINESS_FIELD_CHANGED:text_size',self.item(sid)['payload']['access_reasons'])
if __name__=='__main__':
 unittest.main(verbosity=2)
