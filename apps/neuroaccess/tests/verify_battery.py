"""Isolated Core API tests and complete NeuroAccess regressions.

Synthetic trial fixtures are not human performance or browser validation.
Server timestamps are aged only inside this isolated test DB to avoid minutes
of waiting; a separate negative test checks the real elapsed-time bound.
"""
import copy,json,sqlite3,sys
from contextlib import closing
from uuid import uuid4
from datetime import datetime,timezone,timedelta
from verify_neuroaccess import NeuroAccessTests,PROFILE,PRACTICE,ROOT
sys.path.insert(0,str(ROOT/'backend'))
from battery import definition,practice_trials,VERSION,ORDER
DEVICE=dict(user_agent='isolated-fixture',width=1200,height=800,pixel_ratio=1.0,pointer='fine',refresh_median_ms=16.7,refresh_max_ms=18.0,timer_resolution_ms=.1)
class BatteryTests(NeuroAccessTests):
    def test_battery(self):
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        pid=str(uuid4());self.request('POST','/participants',dict(id=pid,mode='demo',profile=PROFILE,consent_to_store=True),201)
        def access(acute='no',complete=True):
            cid=str(uuid4());self.request('POST',f'/participants/{pid}/checkins?mode=demo',dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning=acute),201)
            if complete and acute=='no':self.request('PUT',f'/checkins/{cid}/practice?mode=demo',PRACTICE)
            return cid
        def create(cid,expected=201):
            return self.request('POST',f'/ncx/checkins/{cid}/sessions?mode=demo',dict(id=str(uuid4()),device=DEVICE),expected)
        create(access('yes'),409);create(access(complete=False),409)
        cid=access();sid=str(uuid4());body=dict(id=sid,device=DEVICE)
        s=self.request('POST',f'/ncx/checkins/{cid}/sessions?mode=demo',body,201)
        self.assertEqual(s,self.request('POST',f'/ncx/checkins/{cid}/sessions?mode=demo',body,201))
        self.assertIn(s['form'],['A','B']);self.request('GET',f'/ncx/sessions/{sid}?mode=active',status=404)
        create(cid,409)
        self.request('PUT',f'/ncx/sessions/{sid}/tasks/C03/attempts/{uuid4()}/start?mode=demo',{'practice_confirmed':True},409)
        def rows(defs):
            out=[];offset=0.0
            for e in defs:
                response=e['expected'];duration=float(e['limit_ms']) if e['kind'] in ['study','attention'] or response is None else 500.0
                out.append(dict(index=e['index'],stimulus_id=e['stimulus_id'],onset_ms=offset,duration_ms=duration,response=response,rt_ms=500.0 if response else None,input='keyboard' if response else None,max_frame_gap_ms=17.0));offset+=duration+300
            return out
        for task in s['order']:
            d=self.request('GET',f'/ncx/sessions/{sid}/tasks/{task}?mode=demo')
            aid=str(uuid4());path=f'/ncx/sessions/{sid}/tasks/{task}/attempts/{aid}'
            self.request('PUT',path+'/start?mode=demo',{'practice_confirmed':True})
            self.request('PUT',path+'/start?mode=demo',{'practice_confirmed':True})
            self.request('PUT',f'/ncx/sessions/{sid}/tasks/{task}/attempts/{uuid4()}/start?mode=demo',{'practice_confirmed':True},409)
            payload=dict(protocol=VERSION,status='completed',reason='completed',trials=rows(d['trials']),practice_log=rows(d['practice']),reports=[])
            if task=='C06':
                report=dict(source='self',consent=True,authorized=False,answers=[dict(item=i,value='no_change') for i in ['schedule','activities','instructions','routines','concerns']]);payload['reports']=[report]
                bad=copy.deepcopy(payload);bad['reports'][0]['source']='informant';self.request('PUT',path+'/result?mode=demo',bad,422)
            if task=='C01':
                self.request('PUT',path+'/result?mode=demo',payload,422)
                bad=copy.deepcopy(payload);bad['trials'][0]['stimulus_id']='wrong';self.request('PUT',path+'/result?mode=demo',bad,422)
                bad=copy.deepcopy(payload);bad['trials'][0]['duration_ms']=float('nan');self.request('PUT',path+'/result?mode=demo',bad,422)
            # Test fixture only. Production APIs expose no clock bypass.
            with closing(sqlite3.connect(self.fixture_db())) as c:
                stamp=(datetime.now(timezone.utc)-timedelta(minutes=60)).isoformat()
                c.execute('UPDATE nc_attempts SET started_at=? WHERE id=?',(stamp,aid));c.commit()
            saved=self.request('PUT',path+'/result?mode=demo',payload)
            self.assertEqual(saved,self.request('PUT',path+'/result?mode=demo',payload))
            self.assertIsNone(saved['summary']['clinical_score'])
            bad=copy.deepcopy(payload);bad['status']='interrupted';bad['reason']='user_stopped';self.request('PUT',path+'/result?mode=demo',bad,409)
            if task=='C05':
                self.request('PUT',f'/ncx/sessions/{sid}/tasks/C02/attempts/{uuid4()}/start?mode=demo',{'practice_confirmed':True},409)
                with closing(sqlite3.connect(self.fixture_db())) as c:
                    c.execute("UPDATE nc_attempts SET finished_at=? WHERE session_id=? AND task='C01'",((datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),sid));c.commit()
        complete=self.request('GET',f'/ncx/sessions/{sid}?mode=demo');self.assertEqual(complete['status'],'completed');self.assertEqual(len(complete['attempts']),6)
        s2=create(access());self.assertNotEqual(s2['form'],s['form']);self.assertIn('uncalibrated_alternate_form',s2['comparison']['condition_changes'])
        aid=str(uuid4());path=f"/ncx/sessions/{s2['id']}/tasks/C01/attempts/{aid}"
        self.request('PUT',path+'/start?mode=demo',{'practice_confirmed':True})
        self.request('PUT',path+'/result?mode=demo',dict(protocol=VERSION,status='interrupted',reason='window_blur',trials=[],practice_log=[],reports=[]))
        self.request('PUT',f"/ncx/sessions/{s2['id']}/tasks/C03/attempts/{uuid4()}/start?mode=demo",{'practice_confirmed':True},409)
        # Server restart retains completed and interrupted sessions.
        type(self).stop_server();type(self).start_server()
        self.assertEqual(self.request('GET',f'/ncx/sessions/{sid}?mode=demo')['status'],'completed')
        items=self.request('GET',f'/ncx/participants/{pid}/sessions?mode=demo')['items'];self.assertEqual(len(items),2)
        self.request('DELETE',f'/participants/{pid}?mode=demo',dict(confirm_id=pid,revision=1))
        self.request('GET',f'/ncx/sessions/{sid}?mode=demo',status=404)
        with closing(sqlite3.connect(self.fixture_db())) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM nc_attempts').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM nc_sessions').fetchone()[0],0)
        print('PASS: Core sequence, exact retries, server timing bounds, actual delay, form assignment, immutable results, holds, interruptions, restart persistence, mode isolation and deletion',flush=True)
    def test_migration_and_arabic(self):
        self.request('POST','/login',{'email':'test@example.org','password':'local-test-code'})
        pid=str(uuid4());profile={**PROFILE,'language':'ar'}
        self.request('POST','/participants',dict(id=pid,mode='demo',profile=profile,consent_to_store=True),201)
        type(self).stop_server()
        with closing(sqlite3.connect(self.folder/'neuroaccess.sqlite3')) as c:
            c.execute('DROP TABLE nc_attempts');c.execute('DROP TABLE nc_sessions');c.execute('PRAGMA user_version=2');c.commit()
        type(self).start_server()
        self.assertEqual(self.request('GET',f'/participants/{pid}?mode=demo')['profile'],{**profile,'birth_date':None})
        cid=str(uuid4());self.request('POST',f'/participants/{pid}/checkins?mode=demo',dict(id=cid,participant_revision=1,instructions_understood=True,acute_warning='no'),201)
        self.request('PUT',f'/checkins/{cid}/practice?mode=demo',{**PRACTICE,'interface_language':'ar'})
        s=self.request('POST',f'/ncx/checkins/{cid}/sessions?mode=demo',dict(id=str(uuid4()),device=DEVICE),201)
        self.assertEqual(s['profile']['language'],'ar')
        changed={**profile,'input_method':'touch'};self.request('PATCH',f'/participants/{pid}?mode=demo',dict(revision=1,profile=changed))
        self.request('PUT',f"/ncx/sessions/{s['id']}/tasks/C01/attempts/{uuid4()}/start?mode=demo",{'practice_confirmed':True},409)
        self.request('DELETE',f'/participants/{pid}?mode=demo',dict(confirm_id=pid,revision=2))
        print('PASS: additive schema-v2 migration, Arabic identity link and changed-profile start hold',flush=True)
    def test_manifests(self):
        for form in ['A','B']:
            s=dict(seed='test',form=form)
            for task in ORDER:
                d=definition(s,task)
                if task=='C04':
                    for e in d['trials']:
                        expected='left' if (e['target_shape']==e['left_shape'] if e['rule']=='shape' else e['target_fill']==e['left_fill']) else 'right'
                        self.assertEqual(e['expected'],expected)
            learn=definition(s,'C01')['trials'];delayed=definition(s,'C02')['trials']
            self.assertEqual({e['pattern'] for e in learn[:6]},{e['pattern'] for e in delayed if e['expected']=='old'})
            self.assertFalse({e['pattern'] for e in learn if e['expected']=='new'} & {e['pattern'] for e in delayed if e['expected']=='new'})
        print('PASS: original form manifests and server-derived answers',flush=True)
if __name__=='__main__':
    import unittest
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BatteryTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
