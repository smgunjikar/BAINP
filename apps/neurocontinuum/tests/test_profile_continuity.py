"""Synthetic readiness comparison tests; no participant database is opened."""
import importlib.util, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('continuity_policy',Path(__file__).resolve().parents[1]/'backend/engine.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_information_changes(self):
  for field in m.PROFILE_INFORMATION_FIELDS:
   with self.subTest(field=field):self.assertEqual(m.readiness_changes({field:1},{field:2}),[])
 def test_accessibility_changes(self):
  for field in ['language','input_method','device_type','vision_limitation','vision_aid','hearing_limitation','hearing_aid','motor_limitation','assistance','assistance_authorized','can_see_and_respond','text_size','high_contrast','reduced_motion']:
   with self.subTest(field=field):self.assertEqual(m.readiness_changes({field:1},{field:2}),[field])
 def test_unknown_field_review(self):self.assertEqual(m.readiness_changes({}, {'future_safety_input':True}),['future_safety_input'])
 def test_bad_snapshot(self):self.assertEqual(m.readiness_changes(None,{}),['invalid_profile_snapshot'])
 def test_same(self):self.assertEqual(m.readiness_changes({'language':'en'},{'language':'en'}),[])
if __name__=='__main__':unittest.main(verbosity=2)
