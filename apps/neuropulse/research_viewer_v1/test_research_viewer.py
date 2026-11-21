import csv, json, tempfile, unittest
from pathlib import Path
from research_viewer import load_results

class ViewerTests(unittest.TestCase):
    def sample(self,root):
        r={'subject':'sub-001','status':'DESCRIPTIVE_AVAILABLE','windows_total':2,'windows_retained':1,'windows_excluded':1,'sha256':'a'*64,'clinical_qc_approved':False,'delta_uv2':1,'theta_uv2':2,'alpha_uv2':3,'beta_uv2':4,'error':''}
        (root/'run_summary.json').write_text(json.dumps({'selected':1,'research_only':True,'clinical_qc_approved':False,'results':[r]}))
        with (root/'features.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(r));w.writeheader();w.writerow(r)
        return r
    def test_success(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.sample(p);v=load_results(p);self.assertEqual(v['selected'],1);self.assertEqual(v['results'][0]['alpha_uv2'],3)
    def test_reject_approval(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.sample(p);s=json.loads((p/'run_summary.json').read_text());s['clinical_qc_approved']=True;(p/'run_summary.json').write_text(json.dumps(s))
            with self.assertRaises(ValueError):load_results(p)
    def test_reject_window_mismatch(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);r=self.sample(p);r['windows_retained']=5
            with (p/'features.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(r));w.writeheader();w.writerow(r)
            with self.assertRaises(ValueError):load_results(p)
    def test_reject_nonfinite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);r=self.sample(p);r['alpha_uv2']='nan'
            with (p/'features.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(r));w.writeheader();w.writerow(r)
            with self.assertRaises(ValueError):load_results(p)
if __name__=='__main__':unittest.main()
