import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import create_app

def client():return TestClient(create_app('sqlite:///:memory:'))

def test_health():
    r=client().get('/health'); assert r.status_code==200 and r.json()['demo_only'] is True

def test_safety_precedence():
    cases=client().get('/v1/demo/cases').json()
    statuses={x['id']:x['interpretation']['status'] for x in cases}
    assert statuses['acute']=='urgent_guidance'
    assert statuses['functional']=='clinical_review'
    assert statuses['device']=='insufficient_evidence'
    assert statuses['sparse']=='baseline_incomplete'
    assert statuses['vascular']=='prevention_context'

def test_attention_persists():
    c=client()
    trials=[{'index':i,'stimulus':'A' if i%2==0 else 'B','pressed':i%2==0,'response_ms':350 if i%2==0 else None} for i in range(8)]
    r=c.post('/v1/demo/attention',json={'trials':trials})
    assert r.status_code==201,r.text
    assert r.json()['correct']==8 and r.json()['clinical_interpretation'] is None
    timeline=c.get('/v1/demo/timeline').json()['sessions']
    assert len(timeline)==1 and timeline[0]['correct']==8

def test_invalid_trials_rejected():
    c=client(); trials=[{'index':0,'stimulus':'A','pressed':True,'response_ms':100}]*8
    assert c.post('/v1/demo/attention',json={'trials':trials}).status_code==422

def test_care_demo_audit():
    c=client()
    r=c.put('/v1/demo/cases/functional/care',json={'status':'review_pending'})
    assert r.status_code==200
    assert c.get('/v1/demo/cases/functional').json()['care_status']=='review_pending'
    assert c.put('/v1/demo/cases/functional/care',json={'status':'diagnosed'}).status_code==422

def test_standalone_demo():
    r=client().get("/demo")
    assert r.status_code == 200 and "BAINP" in r.text
