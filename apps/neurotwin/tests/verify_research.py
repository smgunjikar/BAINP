"""Numerical checks on invented arrays/cohorts only. Requires bainp-brain research deps."""
import csv,hashlib,importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
prep=module('eeg_prepare_test',ROOT/'research/prepare_eeg.py');train=module('progression_test',ROOT/'research/train_progression.py')
guard=module('test_independent_guard',ROOT.parent/'neuroguard/backend/neurotwin_policy.py')
class ResearchTests(unittest.TestCase):
    def test_spectral_recovery_and_no_clean_window(self):
        sf=128;t=np.arange(sf*12)/sf;data=np.stack([15*np.sin(2*np.pi*10*t),12*np.sin(2*np.pi*10*t+.3)])
        r=prep.process(data,sf,['P3','P4']);self.assertAlmostEqual(r['features']['peak_alpha_frequency'],10,delta=.5)
        self.assertGreater(r['features']['alpha_power'],20*r['features']['theta_power']);self.assertEqual(r['quality'],'usable')
        self.assertTrue(np.allclose(r['covariance_uv2'],np.array(r['covariance_uv2']).T))
        with self.assertRaises(ValueError):prep.process(np.zeros_like(data),sf,['P3','P4'])
        data[:,0]=np.nan;r=prep.process(data,sf,['P3','P4']);self.assertEqual(r['quality'],'review');self.assertEqual(r['usable_windows'],2)
    def cohort(self,path,cohort,n,seed):
        rng=np.random.default_rng(seed);rows=[]
        for i in range(n):
            score=float(rng.uniform(18,29));age=float(rng.uniform(55,85));education=float(rng.integers(5,20));event=rng.random()<1/(1+np.exp(-(-1+.15*(25-score)+.015*(age-65))))
            rows.append(dict(participant_id=cohort+'-'+str(i),cohort=cohort,index_date='2020-01-01',followup_end_date='2023-01-01',event_date='2021-07-01' if event else '',event_name='clinician_recorded_dementia' if event else '',baseline_state='MCI',baseline_mmse=score,age=age,education_years=education,death_date=''))
        with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        return rows
    def test_candidate_evaluation_and_independent_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);a=root/'a.csv';b=root/'b.csv';self.cohort(a,'SYN-A',160,42);self.cohort(b,'SYN-B',80,61)
            m=train.train(a,b,root/'candidate','test-protocol',synthetic=True,bootstraps=35)
            self.assertTrue(m['participant_separated']);self.assertEqual(m['internal_evaluation']['n'],40);self.assertEqual(m['external_evaluation']['n'],80);self.assertEqual(m['status'],'CANDIDATE_NOT_APPROVED')
            previous={k:os.environ.get(k) for k in ('NEUROTWIN_MODEL_DIR','NEUROTWIN_POLICY_FILE')}
            os.environ['NEUROTWIN_MODEL_DIR']=str(root/'models');os.environ['NEUROTWIN_POLICY_FILE']=str(root/'policy.json');(root/'models').mkdir()
            try:
                self.assertIn('INDEPENDENT_MODEL_REVIEW_REQUIRED',guard.checked_model()[1])
                raw=json.dumps(m,allow_nan=False).encode();(root/'models/reviewed_model.json').write_bytes(raw)
                policy=dict(approved=True,reviewer='ISOLATED TEST ONLY',review_reference='Fictional validation fixture',expires_on='2099-01-01',model_sha256=hashlib.sha256(raw).hexdigest(),calibration_reviewed=True,approved_cohorts=m['approved_cohorts']);(root/'policy.json').write_text(json.dumps(policy))
                self.assertIn('SYNTHETIC_MODEL_NOT_ALLOWED',guard.checked_model()[1])
                # Exercise the reviewed-model code path with a fixture, not a scientific approval.
                m['synthetic']=False;raw=json.dumps(m).encode();(root/'models/reviewed_model.json').write_bytes(raw);policy['model_sha256']=hashlib.sha256(raw).hexdigest();(root/'policy.json').write_text(json.dumps(policy))
                model,reasons=guard.checked_model();self.assertEqual(reasons,[]);p,ci=guard.probability(model,[25,65,12]);self.assertTrue(0<=p<=1);self.assertTrue(0<=ci[0]<=ci[1]<=1)
                record=dict(source='Clinical',clinical_state='MCI',source_cohort='SYN-A',protocol='test-protocol',observed_at='2026-01-01T12:00:00+00:00',observations=[dict(metric='clinical_measurement',instrument='MMSE',value=25,quality='usable'),dict(metric='age',value=65,quality='usable'),dict(metric='education_years',value=12,quality='usable')])
                f=guard.forecast([record]);self.assertEqual(f['state'],'REVIEWED_RESEARCH_ESTIMATE')
                record['source_cohort']='UNREVIEWED';self.assertIn('POPULATION_OUTSIDE_REVIEWED_SCOPE',guard.forecast([record])['reasons'])
                (root/'models/reviewed_model.json').write_bytes(raw+b' ');self.assertIn('MODEL_HASH_MISMATCH',guard.checked_model()[1])
            finally:
                for k,v in previous.items():
                    if v is None:os.environ.pop(k,None)
                    else:os.environ[k]=v
    def test_censoring_duplicate_and_competing_death(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'cohort.csv';rows=self.cohort(p,'SYN',40,7)
            rows[0].update(event_date='',event_name='',followup_end_date='2020-07-01');rows[1].update(death_date='2021-01-01',event_date='',event_name='');rows[2].update(event_date='2021-01-01',event_name='clinician_recorded_dementia',death_date='2021-02-01')
            def save():
                with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            save();eligible,excluded=train.read_cohort(p);self.assertEqual(len(eligible),38);self.assertEqual(len(excluded),2)
            rows.append(dict(rows[2]));save()
            with self.assertRaises(ValueError):train.read_cohort(p)
    def test_freesurfer_stats_formats(self):
        parser=module('test_fs_parser',ROOT/'integrations/prepare_freesurfer.py')
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'aseg.stats';a.write_text('# ColHeaders Index SegId NVoxels Volume_mm3 StructName normMean\n1 17 3500 3500.0 Left-Hippocampus 80\n')
            self.assertEqual(parser.parse_stats(a)[0]['Volume_mm3'],'3500.0')
            b=Path(d)/'lh.aparc.stats';b.write_text('# ColHeaders StructName NumVert SurfArea GrayVol ThickAvg ThickStd\nentorhinal 2000 1500 3000 2.50 0.30\n')
            self.assertEqual(parser.parse_stats(b)[0]['ThickAvg'],'2.50')
if __name__=='__main__':unittest.main(verbosity=2)
