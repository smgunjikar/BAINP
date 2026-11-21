"""Invented-cohort checks only; use bainp-brain with NumPy/scikit-learn."""
import csv,importlib.util,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('bbc_compare',ROOT/'research/compare_context.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ResearchTests(unittest.TestCase):
    def cohort(self,p):
        rng=np.random.default_rng(602);rows=[]
        for i in range(80):
            baseline=float(rng.uniform(16,28));bp=float(rng.uniform(100,160));hba=float(rng.uniform(4.5,8));sleep=float(rng.uniform(5,8));target=baseline+.02*(bp-120)-.3*(hba-5.5)+.2*(sleep-7)+float(rng.normal(0,.4))
            rows.append(dict(cohort='SYNTHETIC',participant_id='fictional-'+str(i),index_time='2020-01-01T00:00:00Z',feature_available_at='2019-12-31T00:00:00Z',target_time='2020-12-31T00:00:00Z',cognitive_instrument='Invented score',cognitive_version='invented-v1',bp_context='Sitting synthetic',hba1c_assay='Synthetic same assay',hba1c_specimen='whole_blood',sleep_source='Synthetic self report',baseline_score=baseline,target_score=target,age=float(rng.uniform(55,80)),education_years=int(rng.integers(6,20)),bp_systolic='' if i%11==0 else bp,hba1c_percent=hba,sleep_hours=sleep,subgroup='synthetic-A' if i<40 else 'synthetic-B'))
        self.save(p,rows);return rows
    def save(self,p,rows):
        with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    def test_training_only_preprocessing_and_context_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cohort.csv';self.cohort(p);r=module.compare(p,Path(d)/'report');self.assertTrue(r['participant_separated']);self.assertEqual(len(r['folds']),5);self.assertEqual(sum(f['test_participants'] for f in r['folds']),80);self.assertTrue(np.isfinite(r['overall']['with_context']['mae']));self.assertGreater(r['missing_context']['bp_systolic'],0);self.assertNotIn('risk',r)
    def test_future_availability_and_repeated_id_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cohort.csv';rows=self.cohort(p);rows[0]['feature_available_at']='2020-02-01T00:00:00Z';self.save(p,rows)
            with self.assertRaises(ValueError):module.load(p)
            rows=self.cohort(p);rows[1]['participant_id']=rows[0]['participant_id'];self.save(p,rows)
            with self.assertRaises(ValueError):module.load(p)
    def test_mixed_assays_and_invalid_ranges_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cohort.csv';rows=self.cohort(p);rows[0]['hba1c_assay']='Different assay';self.save(p,rows)
            with self.assertRaises(ValueError):module.load(p)
            rows=self.cohort(p);rows[0]['sleep_hours']=100;self.save(p,rows)
            with self.assertRaises(ValueError):module.load(p)
if __name__=='__main__':unittest.main(verbosity=2)
