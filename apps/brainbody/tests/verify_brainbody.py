"""Isolated BBC-BE integration: temporary participant database, no research data used."""
import copy,json,os,sys,tempfile,unittest
from contextlib import ExitStack
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from local_http import LocalClient, serve
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT.parent/'neuroaccess/backend'))
import brainbody_bridge
from bb_engine import build
from bb_provider import read_context
from api import create_app
PROFILE=dict(display_name='BBC isolated test',age=60,education_years=12,digital_familiarity='medium',language='en',vision_limitation=False,vision_aid='none',hearing_limitation=False,hearing_aid=False,motor_limitation=False,input_method='keyboard',device_type='desktop',text_size='standard',high_contrast=False,reduced_motion=False,assistance='none',assistance_authorized=False,can_see_and_respond='yes')
class Tests(unittest.TestCase):
    def setUp(self):
        resources = ExitStack()
        self.addCleanup(resources.close)
        self.root = Path(resources.enter_context(tempfile.TemporaryDirectory()))
        keys = ('NEUROVISION_DATA_DIR', 'NEUROTWIN_POLICY_FILE', 'NEUROTWIN_ANATOMY_DIR')
        resources.enter_context(patch.dict(os.environ, {key: str(self.root/key) for key in keys}))
        app = create_app(self.root/'db', password='bbc-isolated-test')
        self.store = app.state.store
        self.base_url = resources.enter_context(serve(app))
        self.client = LocalClient(self.base_url)
        self.client.headers['X-NeuroAccess-Request'] = '1'
        self.assertEqual(self.client.post('/api/login',json={'password':'bbc-isolated-test'}).status_code,200)
        self.pid=self.new_person('active');self.other=self.new_person('active');self.demo=self.new_person('demo');self.url='/api/brainbody/participants/'+self.pid
    def new_person(self,mode):
        pid=str(uuid4());r=self.client.post('/api/participants',json=dict(id=pid,mode=mode,profile=PROFILE,consent_to_store=True));self.assertEqual(r.status_code,201);return pid
    def grant(self,scopes=None,pid=None):
        pid=pid or self.pid;url='/api/brainbody/participants/'+pid;old=self.client.get(url+'/consent?mode=active').json()['revision'];r=self.client.put(url+'/consent?mode=active',json=dict(expected_revision=old,scopes=scopes if scopes is not None else ['context','clinical_biomarkers','family_history','genomic_summary','molecular_research'],authorization_reference='Isolated authorization fixture'));self.assertEqual(r.status_code,200,r.text);return r.json()
    def record(self,metric='bp_systolic',value=120,reference='isolated-observation'):
        return dict(revision=1,kind='measurement',observed_at='2025-01-01T09:00:00+00:00',available_at='2025-01-01T09:10:00+00:00',source=dict(kind='self_report',organization='Isolated source',record_reference=reference),identity_verified=True,metric=metric,value=value,unit='mmHg',qualifier='exact',quality='usable',context='Same sitting measurement protocol')
    def lab(self,metric='hba1c',value=5.5):
        r=self.record(metric,value);r.update(unit='%',source=dict(kind='lab_report',organization='Isolated laboratory',record_reference='lab-'+str(uuid4())),assay=dict(name='Test assay',version='v1',laboratory='Test lab',specimen='whole_blood',method='Test method'));return r
    def put(self,payload,rid=None,status=200,pid=None,mode='active'):
        rid=rid or str(uuid4());r=self.client.put('/api/brainbody/participants/'+(pid or self.pid)+'/records/'+rid+'?mode='+mode,json=payload);self.assertEqual(r.status_code,status,r.text);return rid,r
    def snap(self,**params):
        r=self.client.get(self.url,params={'mode':'active',**params});self.assertEqual(r.status_code,200,r.text);return r.json()
    def test_auth_mode_csrf_and_explicit_scope(self):
        anonymous = LocalClient(self.base_url)
        self.assertEqual(anonymous.get('/api/brainbody/dictionary').status_code,401)
        self.assertEqual(self.client.get(self.url+'?mode=demo').status_code,404)
        self.put(self.record(),status=403)
        self.assertEqual(self.client.put(self.url+'/consent?mode=active',headers={'X-NeuroAccess-Request':'0'},json=dict(expected_revision=0,scopes=['context'],authorization_reference='test authorization')).status_code,403)
        self.grant(['context']);self.put(self.record());self.put(self.lab(),status=403)
    def test_strict_units_assays_and_time(self):
        self.grant();r=self.record();r['unit']='mg/dL';self.put(r,status=422)
        r=self.lab();r.pop('assay');self.put(r,status=422)
        r=self.lab();r['assay']['specimen']='plasma';self.put(r,status=422)
        r=self.record();r['available_at']='2024-01-01T09:00:00Z';self.put(r,status=422)
        r=self.record();r['observed_at']='2099-01-01T09:00:00Z';r['available_at']=r['observed_at'];self.put(r,status=422)
        r=self.record();r['observed_at']='2025-01-01T09:00:00';self.put(r,status=422)
    def test_immutable_revisions_retry_and_identity(self):
        self.grant();r=self.record();rid,response=self.put(r);self.assertTrue(self.put(r,rid)[1].json()['unchanged'])
        r['value']=125;self.put(r,rid,status=409);r['revision']=2;self.put(r,rid)
        versions=self.client.get(self.url+'/records/'+rid+'/revisions?mode=active').json()['items'];self.assertEqual([v['payload']['value'] for v in versions],[120,125])
        r['revision']=3;r['metric']='bp_diastolic';self.put(r,rid,status=409)
        self.grant(pid=self.other);self.put(self.record(),rid,status=409,pid=self.other)
        self.put(self.record(),status=409)
    def test_censored_results_are_not_point_values(self):
        self.grant();r=self.lab();r.update(qualifier='less_than',value=3,reference=dict(kind='reference_interval',lower=4,upper=6,unit='%',source='Original test interval',population_context='Test population only',applies_to_participant='yes'))
        self.put(r);d=self.snap();self.assertEqual(d['records'][0]['interval_position'],'NO_POINT_INTERPRETATION');self.assertEqual(d['series'][0]['summary']['usable'],0)
        r=self.lab();r.pop('value');r.update(qualifier='not_reported',absent_reason='Source did not supply a numeric result');self.put(r)
        self.assertTrue(all(s['summary']['usable']==0 for s in self.snap()['series']))
    def test_reference_applicability_and_decision_limit(self):
        self.grant();r=self.lab();r['reference']=dict(kind='reference_interval',upper=5,unit='%',source='Source test reference',population_context='Unverified participant population',applies_to_participant='unknown');rid,_=self.put(r)
        self.assertEqual(self.snap()['records'][0]['interval_position'],'REFERENCE_APPLICABILITY_UNCONFIRMED')
        r['revision']=2;r['reference']['applies_to_participant']='yes';self.put(r,rid);self.assertEqual(self.snap()['records'][0]['interval_position'],'ABOVE_SUPPLIED_INTERVAL')
        r['revision']=3;r['reference']['kind']='decision_limit';self.put(r,rid);self.assertEqual(self.snap()['records'][0]['interval_position'],'CLINICAL_DECISION_LIMIT_REQUIRES_REVIEW')
    def test_assays_units_and_specimens_stay_separate(self):
        self.grant();a=self.lab();self.put(a);b=self.lab();b['assay']['version']='v2';self.put(b);c=self.lab();c['unit']='mmol/mol';c['value']=37;self.put(c)
        streams=self.snap()['series'];self.assertEqual(len(streams),3);self.assertEqual(sorted(s['summary']['latest'] for s in streams),[5.5,5.5,37])
    def test_genomic_consent_disclosure_and_withdrawal(self):
        self.grant(['context']);r=dict(revision=1,kind='professional_genomic_finding',observed_at='2025-01-01T09:00:00Z',available_at='2025-01-01T09:10:00Z',source=dict(kind='professional_report',organization='Test professional',record_reference='gene-1'),identity_verified=True,quality='review',context='Authorized professional context',summary='PRIVATE_GENOMIC_FIXTURE',professional_interpretation_reference='Private professional report',disclosure_authorized=True)
        self.put(r,status=403);self.grant(['context','genomic_summary']);rid,_=self.put(r)
        self.assertNotIn('PRIVATE_GENOMIC_FIXTURE',json.dumps(self.snap()));self.assertIn('PRIVATE_GENOMIC_FIXTURE',json.dumps(self.snap(include_sensitive=True)))
        self.assertEqual(self.client.get(self.url+'/records/'+rid+'/revisions?mode=active').status_code,403)
        self.grant(['context']);self.assertNotIn('PRIVATE_GENOMIC_FIXTURE',json.dumps(self.snap(include_sensitive=True)));self.put(r,rid,status=403)
    def test_family_history_scope_and_extra_genetic_fields(self):
        self.grant(['context']);r=dict(revision=1,kind='family_history',observed_at='2025-01-01T09:00:00Z',available_at='2025-01-01T09:10:00Z',source=dict(kind='self_report',organization='Participant report',record_reference='family-1'),identity_verified=True,quality='usable',context='Consented family history context',summary='Reported family context without relative names',relative_degree='first')
        self.put(r,status=403);self.grant(['context','family_history']);self.put(r);r['raw_vcf']='not accepted';self.put(r,status=422)
    def test_research_identity_not_assigned_to_two_people(self):
        self.grant();self.grant(pid=self.other);r=self.record();r['source'].update(cohort='TEST-COHORT',source_subject='S001');self.put(r);self.put(r,pid=self.other,status=409)
    def test_three_clock_historical_replay_and_current_consent(self):
        self.grant(['context']);r=self.record();rid,_=self.put(r)
        with self.store.connect(True) as c:
            c.execute('UPDATE bb_consents SET known_at=? WHERE participant_id=?',('2024-01-01T00:00:00+00:00',self.pid));c.execute('UPDATE bb_versions SET known_at=? WHERE record_id=?',('2025-01-01T09:30:00+00:00',rid))
        self.assertFalse(self.snap(as_of='2025-01-01T09:20:00Z')['records'])
        self.assertEqual(self.snap(as_of='2025-01-01T09:40:00Z')['records'][0]['payload']['value'],120)
        r['value']=125;r['revision']=2;r['available_at']='2025-01-01T10:15:00Z';self.put(r,rid)
        with self.store.connect(True) as c:c.execute('UPDATE bb_versions SET known_at=? WHERE record_id=? AND revision=2',('2025-01-01T10:30:00+00:00',rid))
        self.assertEqual(self.snap(as_of='2025-01-01T10:00:00Z')['records'][0]['payload']['value'],120)
        self.assertEqual(self.snap(as_of='2025-01-01T10:40:00Z')['records'][0]['payload']['value'],125)
        self.grant([]);self.assertFalse(self.snap(as_of='2025-01-01T10:40:00Z')['records'])
    def test_bp_components_review_excluded_from_summaries(self):
        self.grant();a=self.record(value=80);a['encounter_id']='paired-test';self.put(a);b=self.record('bp_diastolic',120,'isolated-dia');b['encounter_id']='paired-test';self.put(b)
        d=self.snap();self.assertTrue(all(s['summary']['usable']==0 for s in d['series']));self.assertTrue(any(f['code']=='INVERTED_BP_COMPONENTS' for f in d['review_queue']))
    def test_review_does_not_rewrite_measurement(self):
        self.grant();r=self.record();r['quality']='review';rid,_=self.put(r);d=self.snap();f=d['review_queue'][0]
        response=self.client.put(self.url+'/reviews/'+rid+'?mode=active',json=dict(record_revision=1,finding_code=f['code'],status='resolved',note='Source review note; raw measurement remains unchanged'));self.assertEqual(response.status_code,200,response.text)
        d=self.snap();self.assertEqual(d['review_queue'][0]['status'],'resolved');self.assertEqual(d['records'][0]['payload']['value'],120);self.assertEqual(d['series'][0]['summary']['usable'],0)
    def test_questionnaire_requires_external_provenance(self):
        self.grant();r=self.record('questionnaire_total',10);r['unit']='score';self.put(r,status=422)
        r['instrument']=dict(name='Externally administered test',version='authorized-v1',language='en',permission_basis='Documented authorized use reference',administered_by='External administrator');self.put(r)
        self.assertTrue(any(f['code']=='EXTERNAL_INSTRUMENT_CONTEXT' for f in self.snap()['review_queue']))
    def test_oxidative_stress_not_inferred_from_wearable(self):
        self.grant();r=self.lab('f2_isoprostanes',.4);r.update(unit='ng/mL',source=dict(kind='device',organization='Watch',device_id='watch-1',record_reference='watch-marker'));self.put(r,status=422)
        r['source']=dict(kind='research_lab',organization='Test research lab',record_reference='lab-marker');r['assay']['specimen']='urine';self.put(r)
        d=self.snap();self.assertIsNone(d['predictions']['risk']);self.assertTrue(any(f['code']=='EXPERIMENTAL_MOLECULAR_CONTEXT' for f in d['review_queue']))
    def test_deletion_and_participant_cascade(self):
        self.grant();rid,_=self.put(self.record());self.assertEqual(self.client.delete(self.url+'/records/'+rid+'?mode=active&expected_revision=2').status_code,409)
        self.assertEqual(self.client.delete(self.url+'/records/'+rid+'?mode=active&expected_revision=1').status_code,200)
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM bb_versions WHERE record_id=?',(rid,)).fetchone()[0],0)
        self.put(self.record());r=self.client.request('DELETE','/api/participants/'+self.pid+'?mode=active',json=dict(confirm_id=self.pid,revision=1));self.assertEqual(r.status_code,200,r.text)
        with self.store.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM bb_records WHERE participant_id=?',(self.pid,)).fetchone()[0],0);self.assertEqual(c.execute('SELECT count(*) FROM bb_consents WHERE participant_id=?',(self.pid,)).fetchone()[0],0)
    def test_synthetic_profiles_no_active_insertions(self):
        before=self.snap()['revision'];a=self.client.get('/api/brainbody/demo?profile=control').json();b=self.client.get('/api/brainbody/demo?profile=impairment').json();self.assertTrue(a['synthetic']);self.assertEqual(a['identity']['participant_id'],'fictional-control');self.assertNotEqual(a['series'][0]['summary']['latest'],b['series'][0]['summary']['latest']);self.assertEqual(before,self.snap()['revision'])
        self.assertFalse(any(r['payload']['kind']=='professional_genomic_finding' for r in a['records']))
    def test_temporal_alignment_and_no_future_cognition_replay(self):
        self.grant(['context']);r=self.record();known=dict(id='before',payload=r,known_at='2025-01-01T09:20:00Z',sha256='test');late=dict(id='late',payload=r,known_at='2025-01-01T11:00:00Z',sha256='test')
        cog=dict(session_history=[dict(id='session',created_at='2025-01-01T10:00:00Z',status='completed',protocol='test',form='A')],task_series={})
        d=build(dict(mode='active'),dict(scopes=['context']),[known,late],cog);self.assertEqual(len(d['alignments'][0]['known_before_session']),1);self.assertEqual(len(d['alignments'][0]['retrospectively_entered']),1)
        wearable = dict(source_id='legacy', metric='heart_rate', value=65, unit='bpm',
                        timestamp='2025-01-01T09:00:00Z', device='Test wearable', method='test',
                        protocol='test-v1', quality='usable')
        wearable_with_clocks = dict(wearable, source_id='timed', available_at='2025-01-01T09:05:00Z',
                                    known_at='2025-01-01T09:10:00Z')
        d = build(dict(mode='active'), dict(scopes=['context']), [], cog, [wearable, wearable_with_clocks])
        alignment = d['alignments'][0]
        self.assertEqual([p['record_id'] for p in alignment['known_before_session']], ['sense:timed'])
        self.assertEqual([p['record_id'] for p in alignment['availability_unknown']], ['sense:legacy'])
        future=dict(session_history=[dict(id='future',created_at='2099-01-01T10:00:00Z',status='completed',protocol='test',form='A')],task_series={'C03':[dict(session_id='future',created_at='2099-01-01T10:00:00Z',status='completed',condition_group='x',summary={'correct':10})]})
        d=read_context(self.store,self.pid,'active',asof=datetime(2025,1,1,tzinfo=timezone.utc),cognition=future);self.assertFalse(d['alignments']);self.assertFalse(d['cognitive_points'])
    def test_twin_context_refresh_and_sensitive_exclusion(self):
        if not (ROOT.parent/'neurotwin/backend/router.py').exists():self.skipTest('NeuroTwin optional')
        self.grant(['context']);self.put(self.record());r=self.client.get('/api/neurotwin/participants/'+self.pid+'?mode=active');self.assertEqual(r.status_code,200,r.text);a=r.json();self.assertEqual(a['brain_body']['record_count'],1)
        self.grant([]);b=self.client.get('/api/neurotwin/participants/'+self.pid+'?mode=active').json();self.assertEqual(b['brain_body']['record_count'],0);self.assertNotEqual(a['revision'],b['revision'])
    def test_connected_source_counts_follow_consent_identity_and_replay(self):
        if not (ROOT.parent/'neurotwin/backend/router.py').exists():
            self.skipTest('NeuroTwin optional')
        self.grant(['context', 'clinical_biomarkers'])
        with self.store.connect(True) as c:
            c.execute("UPDATE bb_consents SET known_at=? WHERE participant_id=?",
                      ('2024-01-01T00:00:00Z', self.pid))
            for pid, mode, subject in ((self.pid, 'active', 'own'), (self.other, 'active', 'other'),
                                       (self.demo, 'demo', 'demo')):
                c.execute("INSERT INTO nt_imaging_links VALUES (?,?,?,?,?,?,?,?)",
                          (pid, mode, 'cohort', subject, 'scan', 'hash', 'test', '2025-01-01T00:00:00Z'))
                c.execute("INSERT INTO nt_source_records VALUES (?,?,?,?,?,?)",
                          (pid, mode, 'Clinical', subject, 1, '{}'))

        def inventory(**params):
            return {item['id']: item for item in self.snap(**params)['connections']}

        current = inventory()
        self.assertEqual(current['imaging']['state'], 'registered')
        self.assertEqual(current['imaging']['count'], 1)
        self.assertEqual(current['clinical']['count'], 1)
        self.assertIn('view=anatomical', current['imaging']['href'])
        self.assertIn('person='+self.pid, current['imaging']['href'])
        historical = inventory(as_of='2025-01-01T12:00:00Z')
        self.assertEqual(historical['imaging']['state'], 'historical_unavailable')
        self.assertIsNone(historical['clinical']['count'])
        self.grant([])
        withheld = inventory()
        self.assertEqual(withheld['imaging']['state'], 'consent_required')
        self.assertIsNone(withheld['imaging']['count'])
        self.assertIsNone(withheld['clinical']['count'])
        demo = self.client.get('/api/brainbody/demo?profile=impairment').json()
        links = {item['id']: item for item in demo['connections']}
        self.assertIn('profile=impairment', links['twin']['href'])
        self.assertNotIn('person=', links['twin']['href'])
    def test_legacy_wearable_unknown_clocks_not_historical_evidence(self):
        self.grant(['context'])
        with self.store.connect(True) as c:
            c.execute('CREATE TABLE IF NOT EXISTS sense_observations(participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,source_id TEXT,payload TEXT,PRIMARY KEY(participant_id,mode,source_id))')
            payload=dict(source_id='legacy-1',metric='heart_rate',value=65,unit='bpm',timestamp='2025-01-01T09:00:00Z',device='Test wearable',method='test',protocol='test-v1',quality='usable')
            c.execute('INSERT INTO sense_observations VALUES(?,?,?,?)',(self.pid,'active','legacy-1',json.dumps(payload)))
            invalid = dict(payload, source_id='legacy-2', metric='f2_isoprostanes', unit='ng/mL')
            c.execute('INSERT INTO sense_observations VALUES(?,?,?,?)',(self.pid,'active','legacy-2',json.dumps(invalid)))
            c.execute('UPDATE bb_consents SET known_at=? WHERE participant_id=?',('2024-01-01T00:00:00Z',self.pid))
        self.assertEqual([series['metric'] for series in self.snap()['series']], ['heart_rate'])
        past=self.snap(as_of='2025-01-01T10:00:00Z');self.assertFalse(past['series']);self.assertTrue(any('withheld from historical replay' in s for s in past['issues']))
    def test_review_cannot_expose_genomic_contents_without_disclosure(self):
        self.grant(['genomic_summary']);r=dict(revision=1,kind='professional_genomic_finding',observed_at='2025-01-01T09:00:00Z',available_at='2025-01-01T09:10:00Z',source=dict(kind='professional_report',organization='Test professional',record_reference='gene-review'),identity_verified=True,quality='review',context='Authorized professional context',summary='GENOMIC_PRIVATE_REVIEW',professional_interpretation_reference='Professional interpretation reference',disclosure_authorized=True)
        rid,_=self.put(r);code='PROFESSIONAL_GENOMIC_CONTEXT';body=dict(record_revision=1,finding_code=code,status='acknowledged',note='Private professional review note')
        self.assertEqual(self.client.put(self.url+'/reviews/'+rid+'?mode=active',json=body).status_code,409)
        body['include_sensitive']=True;self.assertEqual(self.client.put(self.url+'/reviews/'+rid+'?mode=active',json=body).status_code,200)
        default=json.dumps(self.snap());self.assertNotIn('GENOMIC_PRIVATE_REVIEW',default);self.assertNotIn('Private professional review note',default)
    def test_cross_module_cohort_identity_conflicts_rejected_both_directions(self):
        if not (ROOT.parent/'neurotwin/backend/router.py').exists():self.skipTest('NeuroTwin optional')
        self.grant();r=self.record();r['source'].update(cohort='EXACT-COHORT',source_subject='S1');self.put(r)
        nt=dict(source='Clinical',record_id='clinical-peer-1',source_subject='S1',source_cohort='EXACT-COHORT',revision=1,observed_at='2025-01-01T10:00:00Z',protocol='test-v1',provenance='Isolated cross-module identity test',identity_verified=True,consent_confirmed=True,observations=[dict(metric='clinical_measurement',instrument='MMSE',value=25,unit='score',context='Isolated clinical score fixture',quality='usable')])
        url='/api/neurotwin/participants/'+self.other+'/source-records?mode=active'
        self.assertEqual(self.client.put(url,json=nt).status_code,409)
        nt['source_subject']='S2';nt['record_id']='clinical-peer-2';self.assertEqual(self.client.put(url,json=nt).status_code,200)
        r=self.record(reference='different-source');r['source'].update(cohort='EXACT-COHORT',source_subject='S2');self.put(r,status=409)
if __name__=='__main__':unittest.main(verbosity=2)
