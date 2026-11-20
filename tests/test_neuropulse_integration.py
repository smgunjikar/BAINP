import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from neuropulse_research_bridge import make_router

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.run=Path(self.tmp.name)
        with (self.run/'features.csv').open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=['subject','status','windows_total','windows_retained','windows_excluded','sha256','delta_uv2','theta_uv2','alpha_uv2','beta_uv2'])
            w.writeheader();w.writerow(dict(subject='sub-001',status='DESCRIPTIVE_AVAILABLE',windows_total='5',windows_retained='3',windows_excluded='2',sha256='ab'*32,delta_uv2='10',theta_uv2='5',alpha_uv2='2',beta_uv2='1'))
        (self.run/'run_summary.json').write_text('{}')
        (self.run/'sub-001.json').write_text(json.dumps({'subject':'sub-001','sha256':'ab'*32,'source_unchanged':True,'sampling_hz':500,'excluded_intervals':[],'schema':'test'}))
        self.env=patch.dict(os.environ,{'BAINP_NEUROPULSE_MAIN_RUN':str(self.run),'BAINP_NEUROPULSE_RESEARCH_KEY':'x'*32});self.env.start()
        app=FastAPI()
        def auth():return 'operator'
        app.include_router(make_router(auth))
        self.client=TestClient(app)
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_requires_secondary_key(self):
        self.assertEqual(self.client.get('/api/neuropulse/research/v1/subjects').status_code,403)
    def test_status_and_subject(self):
        headers={'X-BAINP-Research-Key':'x'*32}
        r=self.client.get('/api/neuropulse/research/v1/subjects',headers=headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['counts']['DESCRIPTIVE_AVAILABLE'],1)
        d=self.client.get('/api/neuropulse/research/v1/subjects/sub-001',headers=headers)
        self.assertEqual(d.status_code,200)
        self.assertFalse(d.json()['clinical_qc_approved'])
        self.assertFalse(d.json()['neurotwin_eligibility'])
    def test_path_traversal_rejected(self):
        r=self.client.get('/api/neuropulse/research/v1/subjects/evil',headers={'X-BAINP-Research-Key':'x'*32})
        self.assertEqual(r.status_code,404)
    def test_provenance_mismatch_closed(self):
        doc=json.loads((self.run/'sub-001.json').read_text());doc['sha256']='wrong'
        (self.run/'sub-001.json').write_text(json.dumps(doc))
        r=self.client.get('/api/neuropulse/research/v1/subjects/sub-001',headers={'X-BAINP-Research-Key':'x'*32})
        self.assertEqual(r.status_code,503)

if __name__=='__main__':unittest.main()
