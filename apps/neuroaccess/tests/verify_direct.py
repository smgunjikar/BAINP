"""Direct-start preparation audit and seeded item-assignment regression tests.
All performance data below are synthetic fixtures in isolated SQLite databases.
"""
import copy,json,sqlite3,unittest
from uuid import uuid4
from datetime import datetime,timezone,timedelta
from contextlib import closing
from verify_extended import ExtendedTests
from verify_battery import DEVICE,VERSION
from verify_neuroaccess import PROFILE,PRACTICE,ROOT
from assignments import generate
from battery import practice_trials
class DirectTests(ExtendedTests):
    def test_direct_start(self):
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        pid=str(uuid4());self.request('POST','/participants',dict(id=pid,mode='active',profile=PROFILE,consent_to_store=True),201)
        def check(acute='no'):
            cid=str(uuid4());self.request('POST',f'/participants/{pid}/checkins?mode=active',dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning=acute),201)
            if acute=='no':self.request('PUT',f'/checkins/{cid}/practice?mode=active',PRACTICE)
            return cid
        held=check('yes');self.request('POST',f'/ncx/checkins/{held}/sessions?mode=active',dict(id=str(uuid4()),device=DEVICE),409)
        cid=check();s=self.request('POST',f'/ncx/checkins/{cid}/sessions?mode=active',dict(id=str(uuid4()),device=DEVICE),201);sid=s['id']
        def rows(defs):
            logs=[];onset=0.0
            for e in defs:
                response=e['expected'];duration=float(e['limit_ms']) if e['kind'] in ['study','attention'] or response is None else 500.0
                logs.append(dict(index=e['index'],stimulus_id=e['stimulus_id'],onset_ms=onset,duration_ms=duration,response=response,rt_ms=500.0 if response else None,input='keyboard' if response else None,max_frame_gap_ms=17.0));onset+=duration+300
            return logs
        for task in s['order']:
            d=self.request('GET',f'/ncx/sessions/{sid}/tasks/{task}?mode=active');aid=str(uuid4());path=f'/ncx/sessions/{sid}/tasks/{task}/attempts/{aid}'
            decision='not_applicable' if task=='C06' else 'not_passed' if task=='C05' else 'skipped'
            prep=dict(preparation_policy='optional-practice-v1',understanding_confirmed=True,practice_decision=decision)
            self.request('PUT',path+'/start?mode=active',{**prep,'understanding_confirmed':False},422)
            self.request('PUT',path+'/start?mode=active',prep);self.request('PUT',path+'/start?mode=active',prep)
            self.request('PUT',path+'/start?mode=active',{**prep,'practice_decision':'passed'},409 if task!='C06' else 422)
            payload=dict(protocol=VERSION,status='completed',reason='completed',trials=rows(d['trials']),practice_log=[],reports=[])
            if task=='C05':
                payload['practice_log']=rows(d['practice']);payload['practice_log'][0]['response']='different'
            if task=='C06':payload['reports']=[dict(source='self',consent=True,authorized=False,answers=[dict(item=i,value='no_change') for i in ['schedule','activities','instructions','routines','concerns']])]
            with closing(sqlite3.connect(self.fixture_db())) as c:
                c.execute('UPDATE nc_attempts SET started_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(minutes=60)).isoformat(),aid));c.commit()
            saved=self.request('PUT',path+'/result?mode=active',payload)
            if task!='C06':self.assertIn('PRACTICE_NOT_PASSED' if task=='C05' else 'PRACTICE_SKIPPED',saved['summary']['quality_flags'])
            self.assertEqual(saved['preparation']['practice_decision'],decision)
            if task=='C01':
                with closing(sqlite3.connect(self.fixture_db())) as c:c.execute('UPDATE nc_attempts SET finished_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),aid));c.commit()
        self.assertEqual(self.request('GET',f'/ncx/sessions/{sid}?mode=active')['status'],'completed')
        self.request('DELETE',f'/participants/{pid}?mode=active',dict(confirm_id=pid,revision=1))
        with closing(sqlite3.connect(self.fixture_db())) as c:self.assertEqual(c.execute('SELECT count(*) FROM nc_preparations').fetchone()[0],0)
        print('PASS: explicit direct starts, failed-practice continuation, prep immutability, flags, mandatory understanding, holds and deletion',flush=True)
    def test_pending_v11_direct_start(self):
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        pid=str(uuid4());self.request('POST','/participants',dict(id=pid,mode='demo',profile=PROFILE,consent_to_store=True),201)
        cid=str(uuid4());self.request('POST',f'/participants/{pid}/checkins?mode=demo',dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning='no'),201)
        self.request('PUT',f'/checkins/{cid}/practice?mode=demo',PRACTICE)
        sid=str(uuid4());stamp=datetime.now(timezone.utc).isoformat();manifest=json.loads((ROOT/'tests'/'research_v11_manifest.json').read_text())
        with closing(sqlite3.connect(self.fixture_db())) as c:
            c.execute('INSERT INTO nc_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,cid,pid,'demo','ncx-research-v1.1.0','A','v11-frozen',json.dumps(PROFILE),json.dumps(DEVICE),json.dumps(manifest),stamp))
            c.execute('INSERT INTO nc_attempts VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),sid,'C01','completed',stamp,stamp,'{}','{}'));c.commit()
        aid=str(uuid4());path=f'/ncx/sessions/{sid}/tasks/C03/attempts/{aid}'
        prep=dict(preparation_policy='optional-practice-v1',understanding_confirmed=True,practice_decision='skipped')
        self.request('PUT',path+'/start?mode=demo',prep)
        logs=[];offset=0.0
        for e in manifest['C03']['trials']:
            response=e['expected'];logs.append(dict(index=e['index'],stimulus_id=e['stimulus_id'],onset_ms=offset,duration_ms=1200.0,response=response,rt_ms=500.0 if response else None,input='keyboard' if response else None,max_frame_gap_ms=17.0));offset+=1500
        with closing(sqlite3.connect(self.fixture_db())) as c:c.execute('UPDATE nc_attempts SET started_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),aid));c.commit()
        saved=self.request('PUT',path+'/result?mode=demo',dict(protocol='ncx-research-v1.1.0',status='completed',reason='completed',trials=logs,practice_log=[],reports=[]))
        self.assertIn('PREPARATION_POLICY_AMENDED',saved['summary']['quality_flags']);self.assertIn('PRACTICE_SKIPPED',saved['summary']['quality_flags'])
        record=self.request('GET',f'/ncx/sessions/{sid}?mode=demo');self.assertEqual(record['task_manifests'],manifest)
        self.request('DELETE',f'/participants/{pid}?mode=demo',dict(confirm_id=pid,revision=1))
        print('PASS: existing v1.1 pending task can start directly with recorded administration amendment; original items stay frozen',flush=True)
    def test_random_item_assignments(self):
        signatures={t:set() for t in [f'C{i:02d}' for i in range(1,13)]}
        for i in range(100):
            defs={t:generate(str(i),'A',t,practice_trials(t)) for t in signatures}
            for t,d in defs.items():
                self.assertEqual(d,generate(str(i),'A',t,practice_trials(t)))
                signatures[t].add(d['assignment_fingerprint'])
            study={e['pattern'] for e in defs['C01']['trials'][:6]}
            self.assertEqual(study,{e['pattern'] for e in defs['C02']['trials'] if e['expected']=='old'})
            memory={e['pattern'] for t in ['C01','C02'] for e in defs[t]['trials']}
            speed={e[k] for e in defs['C05']['trials'] for k in ['a','b']};self.assertFalse(memory&speed)
            attention=[e['target'] for e in defs['C03']['trials']];self.assertEqual(sum(attention),28)
            self.assertFalse(any(len(set(attention[j:j+5]))==1 for j in range(36)))
            switching=defs['C04']['trials'];self.assertEqual(sum(bool(e['rule_switched']) for e in switching),12)
            self.assertEqual(sum(e['expected']=='left' for e in switching),12)
            speed=defs['C05']['trials'];self.assertEqual(sum(e['expected']=='same' for e in speed),12)
            self.assertEqual(sum(e['distractor_bit_distance']==1 for e in speed),6)
            self.assertEqual(sum(e['distractor_bit_distance']==2 for e in speed),6)
            self.assertEqual(sorted(e['span'] for e in defs['C07']['trials']),[2,3,4,5])
            self.assertEqual(len({e['object'] for e in defs['C09']['trials']}),6)
        for task,values in signatures.items():self.assertGreater(len(values),1,task)
        # Content samples actually change, rather than hashing only a different seed.
        self.assertNotEqual({x['pattern'] for x in generate('a','A','C01',[])['trials'][:6]},{x['pattern'] for x in generate('b','A','C01',[])['trials'][:6]})
        print('PASS: 100 seeds; all task assignments vary reproducibly; memory/speed disjoint; quotas and switch/match balance preserved',flush=True)
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DirectTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
