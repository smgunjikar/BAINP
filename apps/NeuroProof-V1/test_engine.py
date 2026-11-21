import unittest
from engine import passport
class Tests(unittest.TestCase):
 def test_missing_reference(self):
  r=passport(dict(participant_id='fictional',mode='demo',policy='test',action='review',evidence_ids=['missing'],limitations=[]),[]);self.assertEqual(r['traceability_status'],'REVIEW_REQUIRED')
 def test_identity(self):
  with self.assertRaises(ValueError):passport(dict(participant_id='fictional',mode='demo',policy='test',action='review',evidence_ids=[],limitations=[]),[dict(id='x',participant_id='other',mode='demo')])
 def test_hash_mismatch(self):
  r=passport(dict(participant_id='fictional',mode='demo',policy='test',action='review',evidence_ids=[],limitations=[]),[],expected_hash='wrong');self.assertFalse(r['checks']['hash_matches'])
if __name__=='__main__':unittest.main()
