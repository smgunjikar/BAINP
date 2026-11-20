import unittest
from engine import analyze
class Tests(unittest.TestCase):
 def test_consent(self):
  with self.assertRaises(PermissionError):analyze(dict(participant_id='fictional',mode='demo'))
 def test_missing(self):
  r=analyze(dict(participant_id='fictional',mode='demo',consent=True,guard={'state':'review_permitted'}));self.assertEqual(len(r['missing_domains']),5)
 def test_urgent(self):
  r=analyze(dict(participant_id='fictional',mode='demo',consent=True,guard={'state':'escalate'}));self.assertEqual(r['action'],'urgent_guard_path')
if __name__=='__main__':unittest.main()
