"""Synthetic, isolated verification of all twelve research task pathways.
No clinical or human performance validation is implied by passing these tests.
"""
import copy,json,sqlite3,sys,unittest
from datetime import datetime,timezone,timedelta
from contextlib import closing
from uuid import uuid4
from verify_battery import BatteryTests,DEVICE,VERSION
from verify_neuroaccess import PROFILE,PRACTICE,ROOT
from extended import OBJECTS,LEXICON
class ExtendedTests(BatteryTests):
    def test_extended_full(self):
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        ids=[]
        for mode in ['active','demo']:
            pid=str(uuid4());ids.append((pid,mode));self.request('POST','/participants',dict(id=pid,mode=mode,profile=PROFILE,consent_to_store=True),201)
            cid=str(uuid4());self.request('POST',f'/participants/{pid}/checkins?mode={mode}',dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning='no'),201)
            access=self.request('GET',f'/ncx/participants/{pid}/access?mode={mode}');self.assertIn('complete_neuroaccess_practice',access['items'][0]['reasons'])
            self.request('PUT',f'/checkins/{cid}/practice?mode={mode}',PRACTICE)
            body=dict(id=str(uuid4()),battery='full',motor_ack=False,device=DEVICE)
            self.request('POST',f'/ncx/checkins/{cid}/sessions?mode={mode}',body,422)
            body['motor_ack']=True
            s=self.request('POST',f'/ncx/checkins/{cid}/sessions?mode={mode}',body,201);sid=s['id']
            self.assertEqual(s['order'][0],'C01');self.assertEqual(s['order'][-2:],['C11','C12']);self.assertEqual(set(s['order']),{f'C{i:02d}' for i in range(1,13)})
            self.assertEqual(s['order'][4:6],['C02','C06'])
            for task in s['order']:
                # Core path already exercised by inherited tests. Populate validated
                # fixture rows here only to reach the extended API pathways quickly.
                if task not in ['C07','C08','C09','C10','C11','C12']:
                    with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:
                        stamp=(datetime.now(timezone.utc)-timedelta(minutes=60)).isoformat()
                        c.execute('INSERT INTO nc_attempts VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),sid,task,'completed',stamp,stamp,'{}','{}'));c.commit()
                    continue
                d=self.request('GET',f'/ncx/sessions/{sid}/tasks/{task}?mode={mode}')
                aid=str(uuid4());path=f'/ncx/sessions/{sid}/tasks/{task}/attempts/{aid}'
                self.request('PUT',path+f'/start?mode={mode}',{'practice_confirmed':True})
                def observations(rows):
                    out=[];offset=0.0
                    for e in rows:
                        presentations=[];study=0.0;rt=500.0;duration=500.0
                        if e['kind']=='span':
                            response=[float(x) for x in e['sequence']];study=e['span']*1000.0;rt=study+500;duration=rt
                            presentations=[dict(cell=cell,onset_ms=i*1000.0,duration_ms=700.0) for i,cell in enumerate(e['sequence'])]
                        elif e['kind']=='spatial':response=e['expected']
                        elif e['kind']=='naming':response=OBJECTS[e['object']]['en'][0]
                        elif e['kind']=='category':response=LEXICON['en'][e['category']][0]
                        elif e['kind']=='tapping':response=[100.0,350.0,800.0];duration=float(e['limit_ms']);rt=800.0
                        else:response='no' if e['item']=='condition_change' else {'month':'November','year':'2026','place':'Fictional test room'}[e['item']]
                        out.append(dict(index=e['index'],stimulus_id=e['stimulus_id'],onset_ms=offset,duration_ms=duration,response=response,rt_ms=rt,input='keyboard',max_frame_gap_ms=17.0,presentations=presentations,study_duration_ms=study));offset+=duration+300
                    return out
                payload=dict(protocol=VERSION,status='completed',reason='completed',trials=[],practice_log=[],reports=[],extra_trials=observations(d['trials']),extra_practice_runs=[observations(d['practice'])] if d['practice_required'] else [])
                with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:c.execute('UPDATE nc_attempts SET started_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(minutes=60)).isoformat(),aid));c.commit()
                if task=='C09':payload['extra_trials'][0]['response']='unlisted plausible synonym'
                if task=='C07':
                    bad=copy.deepcopy(payload);bad['extra_trials'][0]['presentations'][0]['cell']=(bad['extra_trials'][0]['presentations'][0]['cell']+1)%9
                    self.request('PUT',path+f'/result?mode={mode}',bad,422)
                if task=='C11':
                    bad=copy.deepcopy(payload);bad['extra_trials'][0]['response']=[100.0,100.0]
                    self.request('PUT',path+f'/result?mode={mode}',bad,422)
                saved=self.request('PUT',path+f'/result?mode={mode}',payload)
                self.assertEqual(saved,self.request('PUT',path+f'/result?mode={mode}',payload))
                self.assertIsNone(saved['summary']['clinical_score'])
                if task=='C09':self.assertEqual(saved['summary']['unmatched_pending_review'],1)
                if task=='C11':self.assertEqual(len(saved['summary']['windows']),2)
            self.assertEqual(self.request('GET',f'/ncx/sessions/{sid}?mode={mode}')['status'],'completed')
            analytics=self.request('GET',f'/ncx/participants/{pid}/analytics?mode={mode}')
            self.assertEqual(analytics['completed_sessions'],1);self.assertEqual(len(analytics['task_series']['C07']),1);self.assertIsNone(analytics['rci'])
            wrong='active' if mode=='demo' else 'demo';self.request('GET',f'/ncx/participants/{pid}/analytics?mode={wrong}',status=404)
        for pid,mode in ids:self.request('DELETE',f'/participants/{pid}?mode={mode}',dict(confirm_id=pid,revision=1))
        print('PASS: Active and Demo all-12-task enrollment, motor opt-in, saved logs, dictionary-review flags, motor observations, dashboards and deletion',flush=True)
    def test_old_core_preserved(self):
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        pid=str(uuid4());self.request('POST','/participants',dict(id=pid,mode='demo',profile=PROFILE,consent_to_store=True),201)
        cid=str(uuid4());self.request('POST',f'/participants/{pid}/checkins?mode=demo',dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning='no'),201)
        self.request('PUT',f'/checkins/{cid}/practice?mode=demo',PRACTICE)
        sid=str(uuid4());aid=str(uuid4());stamp=datetime.now(timezone.utc).isoformat()
        manifest=json.loads((ROOT/'tests'/'core_v1_manifest.json').read_text())
        old=dict(protocol='ncx-core-pattern-v1.0.0',status='interrupted',reason='page_reload',trials=[],practice_log=[],practice_interrupted_runs=[],reports=[])
        with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:
            c.execute('INSERT INTO nc_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,cid,pid,'demo','ncx-core-pattern-v1.0.0','A','legacy-fixture',json.dumps(PROFILE),json.dumps(DEVICE),json.dumps(manifest),stamp))
            c.execute('INSERT INTO nc_attempts VALUES(?,?,?,?,?,?,?,?)',(aid,sid,'C01','interrupted',stamp,stamp,json.dumps(old),json.dumps({'quality_flags':['INTERRUPTED'],'clinical_score':None})));c.commit()
        record=self.request('GET',f'/ncx/sessions/{sid}?mode=demo');self.assertEqual(record['order'],['C01','C03','C04','C05','C02','C06']);self.assertEqual(record['protocol'],'ncx-core-pattern-v1.0.0');self.assertEqual(record['task_manifests'],manifest)
        self.request('PUT',f'/ncx/sessions/{sid}/tasks/C01/attempts/{aid}/result?mode=demo',old)
        self.request('GET',f'/ncx/sessions/{sid}/tasks/C07?mode=demo',status=404)
        self.request('DELETE',f'/participants/{pid}?mode=demo',dict(confirm_id=pid,revision=1))
        print('PASS: frozen v1 Core order/manifests/results and exact historical retries preserved',flush=True)
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExtendedTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
