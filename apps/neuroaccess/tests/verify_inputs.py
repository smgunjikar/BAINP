"""Raw-answer persistence, checkpoints, append-only review, and recording regression.
These tests use fictional responses in isolated storage, never operator records.
"""
import copy,json,sqlite3,unittest
from uuid import uuid4
from contextlib import closing
from datetime import datetime,timezone,timedelta
from verify_direct import DirectTests
from verify_battery import DEVICE,VERSION
from verify_neuroaccess import PROFILE,PRACTICE
from extended import OBJECTS
class InputTests(DirectTests):
    def language_attempt(self):
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        pid=str(uuid4());self.request('POST','/participants',dict(id=pid,mode='demo',profile=PROFILE,consent_to_store=True),201)
        cid=str(uuid4());self.request('POST',f'/participants/{pid}/checkins?mode=demo',dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning='no'),201)
        self.request('PUT',f'/checkins/{cid}/practice?mode=demo',PRACTICE)
        s=self.request('POST',f'/ncx/checkins/{cid}/sessions?mode=demo',dict(id=str(uuid4()),device=DEVICE,battery='full',motor_ack=True),201)
        # Isolated fixture arrangement to reach C09 without running all prior tasks.
        with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:
            for task in s['order'][:s['order'].index('C09')]:
                c.execute('INSERT INTO nc_attempts VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),s['id'],task,'completed',s['created_at'],s['created_at'],'{}','{}'))
            c.commit()
        aid=str(uuid4());path=f"/ncx/sessions/{s['id']}/tasks/C09/attempts/{aid}"
        self.request('PUT',path+'/start?mode=demo',dict(preparation_policy='optional-practice-v1',understanding_confirmed=True,practice_decision='skipped',input_capture_version='input-v2'))
        with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:c.execute('UPDATE nc_attempts SET started_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat(),aid));c.commit()
        return pid,s,aid,path
    def logs(self,d):
        records=[]
        for i,e in enumerate(d['trials']):
            answer=OBJECTS[e['object']]['en'][0] if i<3 else f'unlisted answer {i}'
            records.append(dict(index=i,stimulus_id=e['stimulus_id'],onset_ms=i*800.0,duration_ms=500.0,response=answer,rt_ms=400.0,input='keyboard',max_frame_gap_ms=17.0,study_duration_ms=0.0,presentations=[],capture_version='input-v2',response_events=[dict(kind='submitted',at_ms=400.0,input='keyboard',action='explicit')],draft_response=answer,termination='answered'))
        return records
    def test_inputs_and_reviews(self):
        pid,s,aid,path=self.language_attempt();logs=self.logs(s['task_manifests']['C09'])
        logs[-1].update(duration_ms=20000.0,rt_ms=20000.0,termination='deadline_commit',response_events=[dict(kind='submitted',at_ms=20000.0,input='keyboard',action='deadline_commit')])
        cp=dict(protocol=VERSION,revision=1,trials=[],extra_trials=logs[:2],current_draft=None)
        self.request('PUT',path+'/checkpoint?mode=demo',cp);self.request('PUT',path+'/checkpoint?mode=demo',cp)
        changed=copy.deepcopy(cp);changed['extra_trials'][0]['response']='different';changed['extra_trials'][0]['draft_response']='different';self.request('PUT',path+'/checkpoint?mode=demo',changed,409)
        type(self).stop_server();type(self).start_server()
        read=self.request('GET',f"/ncx/sessions/{s['id']}?mode=demo");a=next(a for a in read['attempts'] if a['id']==aid)
        self.assertEqual(a['checkpoint']['saved_trials'],2);self.assertEqual(a['checkpoint']['payload']['extra_trials'][0]['response'],logs[0]['response'])
        cp['revision']=2;cp['extra_trials']=logs
        self.request('PUT',path+'/checkpoint?mode=demo',cp)
        body=dict(protocol=VERSION,status='completed',reason='completed',trials=[],practice_log=[],reports=[],extra_trials=logs,extra_practice_runs=[])
        saved=self.request('PUT',path+'/result?mode=demo',body);self.assertIn('ANSWER_AUTOCOMMITTED_AT_DEADLINE',saved['summary']['quality_flags']);self.assertEqual(saved['reviewed_counts']['accepted'],3);self.assertEqual(saved['reviewed_counts']['pending_review'],3)
        self.assertEqual(saved['submitted']['extra_trials'],logs)
        self.request('PUT',path+'/result?mode=demo',body)
        for i in [3,4,5]:
            rid=str(uuid4());review=dict(item_index=i,expected_revision=0,decision='incorrect',note='Operator reviewed the recorded response')
            r=self.request('PUT',path+f'/reviews/{rid}?mode=demo',review);self.assertEqual(r,self.request('PUT',path+f'/reviews/{rid}?mode=demo',review))
            self.request('PUT',path+f'/reviews/{uuid4()}?mode=demo',review,409)
        read=self.request('GET',f"/ncx/sessions/{s['id']}?mode=demo");a=next(x for x in read['attempts'] if x['id']==aid)
        self.assertEqual(a['reviewed_counts']['accepted'],3);self.assertEqual(a['reviewed_counts']['incorrect'],3);self.assertEqual(a['reviewed_counts']['pending_review'],0)
        self.assertEqual(a['submitted']['extra_trials'],logs);self.assertEqual(len(a['reviews']),3)
        self.request('GET',f"/ncx/sessions/{s['id']}?mode=active",status=404)
        self.request('DELETE',f'/participants/{pid}?mode=demo',dict(confirm_id=pid,revision=1))
        with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM nc_input_checkpoints').fetchone()[0],0);self.assertEqual(c.execute('SELECT count(*) FROM nc_response_reviews').fetchone()[0],0)
        print('PASS: six exact raw answers, 3 dictionary matches + 3 reviewed incorrect, persisted checkpoints/restart, immutable reviews and deletion',flush=True)
    def test_preserved_draft(self):
        pid,s,aid,path=self.language_attempt();logs=self.logs(s['task_manifests']['C09']);draft=copy.deepcopy(logs[0]);draft.update(response=None,rt_ms=None,input=None,termination='interrupted',draft_response='unfinished exact text',response_events=[])
        cp=dict(protocol=VERSION,revision=1,trials=[],extra_trials=[],current_draft=draft)
        self.request('PUT',path+'/checkpoint?mode=demo',cp)
        a=next(a for a in self.request('GET',f"/ncx/sessions/{s['id']}?mode=demo")['attempts'] if a['id']==aid)
        self.assertEqual(a['checkpoint']['payload']['current_draft']['draft_response'],'unfinished exact text')
        body=dict(protocol=VERSION,status='interrupted',reason='page_reload',trials=[],practice_log=[],reports=[],extra_trials=[draft],extra_practice_runs=[])
        saved=self.request('PUT',path+'/result?mode=demo',body);self.assertIsNone(saved['submitted']['extra_trials'][0]['response']);self.assertEqual(saved['reviewed_counts']['unsubmitted_drafts'],1)
        self.request('PUT',path+f'/reviews/{uuid4()}?mode=demo',dict(item_index=0,expected_revision=0,decision='accepted'),422)
        self.request('DELETE',f'/participants/{pid}?mode=demo',dict(confirm_id=pid,revision=1))
        print('PASS: unsubmitted draft survives checkpoint/recovery without becoming a scored answer',flush=True)
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InputTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
