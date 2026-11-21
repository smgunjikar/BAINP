"""NeuroCognition X Core v1: original research tasks, never diagnostic scores.

Server owns sequence, alternate-form assignment, expected answers and summaries.
Browser logs are approximate, client-reported observations, not trusted instruments.
NeuroAccess gate is read only here: no AI or task route may rewrite its controls.
"""
import hashlib,json,random,statistics
import importlib.util,sys
from pathlib import Path
_plus_spec=importlib.util.spec_from_file_location("ncx_plus",Path(__file__).resolve().parents[2]/"neurocognition/backend/plus.py")
_plus=importlib.util.module_from_spec(_plus_spec);sys.modules[_plus_spec.name]=_plus;_plus_spec.loader.exec_module(_plus)
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from recovery import SCHEMA as RECOVERY_SCHEMA, ticket as recovery_ticket, authorization as recovery_authorization
from input_records import CaptureFields,CAPTURE_FIELDS,SCHEMA as INPUT_SCHEMA,review_summary
LEGACY_VERSION='ncx-core-pattern-v1.0.0'
from assignments import VERSION,generate
from extended import TASKS as EXTENDED,Observation,definition as extended_definition,validate as validate_extended,summarize as summarize_extended
TaskId=Literal['C01','C02','C03','C04','C05','C06','C07','C08','C09','C10','C11','C12']
ORDER=['C01','C03','C04','C05','C02','C06']
FIELDS=['language','input_method','device_type','vision_limitation','vision_aid','hearing_limitation','hearing_aid','motor_limitation','assistance','assistance_authorized','can_see_and_respond','text_size','high_contrast','reduced_motion']
SCHEMA='''CREATE TABLE IF NOT EXISTS nc_sessions (
 id TEXT PRIMARY KEY, checkin_id TEXT NOT NULL UNIQUE REFERENCES checkins(id) ON DELETE CASCADE,
 participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE, mode TEXT NOT NULL,
 protocol TEXT NOT NULL, form TEXT NOT NULL, seed TEXT NOT NULL, profile TEXT NOT NULL,
 device TEXT NOT NULL, manifest TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nc_attempts (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES nc_sessions(id) ON DELETE CASCADE,
 task TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
 submitted TEXT, summary TEXT, UNIQUE(session_id,task));
CREATE TABLE IF NOT EXISTS nc_preparations (attempt_id TEXT PRIMARY KEY REFERENCES nc_attempts(id) ON DELETE CASCADE,payload TEXT NOT NULL);'''
def initialize(c):
    c.executescript(SCHEMA+INPUT_SCHEMA+RECOVERY_SCHEMA+_plus.SCHEMA+'''CREATE TABLE IF NOT EXISTS nc_context_reports(id TEXT PRIMARY KEY,participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,mode TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nc_session_closures(session_id TEXT PRIMARY KEY REFERENCES nc_sessions(id) ON DELETE CASCADE,mode TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,missing_tasks TEXT NOT NULL);''')
def now():return datetime.now(timezone.utc).isoformat()
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def elapsed(stamp):return (datetime.now(timezone.utc)-datetime.fromisoformat(stamp)).total_seconds()*1000
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',strict=True)
class Device(Strict):
    user_agent:str=Field(max_length=500)
    width:int=Field(ge=1,le=20000)
    height:int=Field(ge=1,le=20000)
    pixel_ratio:float=Field(gt=0,le=10,allow_inf_nan=False)
    pointer:Literal['fine','coarse','none']
    refresh_median_ms:float=Field(gt=0,le=1000,allow_inf_nan=False)
    refresh_max_ms:float=Field(gt=0,le=60000,allow_inf_nan=False)
    timer_resolution_ms:float=Field(ge=0,le=1000,allow_inf_nan=False)
    @model_validator(mode='after')
    def check(self):
        if self.refresh_max_ms<self.refresh_median_ms:raise ValueError('Invalid refresh diagnostics')
        return self
class NewSession(Strict):
    battery:Literal['quick','core','extended','full']='core'
    daily_followup:bool=False
    motor_ack:bool=False
    auto_advance:bool=True
    @model_validator(mode='after')
    def optional_motor(self):
        if self.battery=='full' and not self.motor_ack:raise ValueError('Explicit optional motor participation acknowledgement required')
        return self
    id:UUID=Field(strict=False)
    device:Device
class Start(Strict):
    # Legacy requests retain their required-practice contract. New UI records an
    # explicit administration policy, without falsely asserting practice passed.
    camera_observation:bool=False
    practice_confirmed:Literal[True]|None=None
    input_capture_version:Literal['input-v2']|None=None
    preparation_policy:Literal['optional-practice-v1']|None=None
    understanding_confirmed:bool=False
    practice_decision:Literal['passed','skipped','not_passed','not_applicable']|None=None
    @model_validator(mode='after')
    def check(self):
        if self.preparation_policy:
            if self.practice_confirmed is not None or not self.understanding_confirmed or self.practice_decision is None:raise ValueError('Explicit understanding and practice decision required')
        elif self.practice_confirmed is not True:raise ValueError('Legacy practice confirmation required')
        return self
    def record(self):
        result=dict(policy=self.preparation_policy or 'required-practice-v1',understanding_confirmed=self.understanding_confirmed if self.preparation_policy else None,practice_decision=self.practice_decision if self.preparation_policy else 'passed',source='explicit_user_decision' if self.preparation_policy else 'legacy_client_contract')
        if self.camera_observation:result['camera_observation']=True
        if self.input_capture_version:result['input_capture_version']=self.input_capture_version
        return result

class Trial(CaptureFields):
    index:int=Field(ge=0,le=100)
    stimulus_id:str=Field(max_length=80)
    onset_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)
    duration_ms:float=Field(gt=0,le=7200000,allow_inf_nan=False)
    response:Literal['left','right','go','same','different','old','new']|None
    rt_ms:float|None=Field(default=None,ge=0,le=60000,allow_inf_nan=False)
    input:Literal['keyboard','mouse','touch','pen','assistive','unknown']|None
    max_frame_gap_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)
    @model_validator(mode='after')
    def check(self):
        if (self.response is None)!=(self.rt_ms is None) or (self.response is None)!=(self.input is None):raise ValueError('Response, latency and input must agree')
        if self.rt_ms is not None and self.rt_ms>self.duration_ms:raise ValueError('Latency exceeds trial duration')
        return self
class Answer(Strict):
    item:Literal['schedule','activities','instructions','routines','concerns']
    value:Literal['no_change','more_difficult','less_difficult','not_applicable','unsure']
class Report(Strict):
    source:Literal['self','informant']
    consent:Literal[True]
    authorized:bool
    answers:list[Answer]=Field(min_length=5,max_length=5)
class Result(Strict):
    protocol:Literal['ncx-core-pattern-v1.0.0','ncx-research-v1.1.0','ncx-research-v1.2.0','ncx-research-v1.3.0']
    status:Literal['completed','interrupted']
    reason:Literal['completed','user_stopped','window_blur','tab_hidden','page_reload','camera_unavailable']
    trials:list[Trial]=Field(max_length=100)
    reports:list[Report]=Field(default_factory=list,max_length=2)
    practice_log:list[Trial]=Field(max_length=100)
    practice_interrupted_runs:list[list[Trial]]=Field(default_factory=list,max_length=50)
    extra_trials:list[Observation]=Field(default_factory=list,max_length=100)
    extra_practice_runs:list[list[Observation]]=Field(default_factory=list,max_length=25)
    @model_validator(mode='after')
    def check(self):
        if (self.status=='completed')!=(self.reason=='completed'):raise ValueError('Status/reason mismatch')
        if any(len(run)>20 for run in self.extra_practice_runs):raise ValueError('Extended practice run too long')
        if any(len(run)>2 for run in self.practice_interrupted_runs):raise ValueError('Practice interruption too long')
        return self

class Checkpoint(Strict):
    revision:int=Field(ge=1,le=100000)
    protocol:Literal['ncx-core-pattern-v1.0.0','ncx-research-v1.1.0','ncx-research-v1.2.0','ncx-research-v1.3.0']
    trials:list[Trial]=Field(default_factory=list,max_length=100)
    extra_trials:list[Observation]=Field(default_factory=list,max_length=100)
    current_draft:Observation|None=None
class ResponseReview(Strict):
    item_index:int=Field(ge=0,le=99)
    expected_revision:int=Field(ge=0,le=100000)
    decision:Literal['accepted','incorrect','uncertain']
    note:str=Field(default='',max_length=300)

def patterns(form):
    # Original geometric patterns: uncalibrated forms, not object naming tests.
    return [f'{form}-{i}' for i in range(18)]
def definition(s,task):
    if 'manifest' in s.keys():
        saved=json.loads(s['manifest'])
        if task not in saved:raise HTTPException(404,'task_not_in_this_battery')
        return saved[task]
    return generate(s['seed'],s['form'],task,practice_trials(task))

def practice_trials(task):
    # Distinct non-study patterns avoid teaching test answers during practice.
    if task in ['C01','C02']:return [dict(index=0,stimulus_id='practice-0',kind='recognition',pattern='P-0',expected='old',limit_ms=60000),dict(index=1,stimulus_id='practice-1',kind='recognition',pattern='P-1',expected='new',limit_ms=60000)]
    if task=='C03':return [dict(index=i,stimulus_id=f'practice-{i}',kind='attention',target=i==0,expected='go' if i==0 else None,limit_ms=2000) for i in range(2)]
    if task=='C04':return [dict(index=i,stimulus_id=f'practice-{i}',kind='switch',rule='shape' if i==0 else 'fill',target_shape=0,target_fill=1,left_shape=0,left_fill=0,expected='left' if i==0 else 'right',limit_ms=60000) for i in range(2)]
    if task=='C05':return [dict(index=i,stimulus_id=f'practice-{i}',kind='match',a='P-2',b='P-2' if i==0 else 'P-3',expected='same' if i==0 else 'different',limit_ms=60000) for i in range(2)]
    return []

def validate_trials(actual,expected,complete):
    if len(actual)>len(expected) or (complete and len(actual)!=len(expected)):raise HTTPException(422,'trial_count_mismatch')
    end=0
    for a,e in zip(actual,expected):
        if a.index!=e['index'] or a.stimulus_id!=e['stimulus_id'] or a.onset_ms<end:raise HTTPException(422,'trial_sequence_mismatch')
        end=a.onset_ms+a.duration_ms
        if any(ev.at_ms>a.duration_ms+1 for ev in a.response_events):raise HTTPException(422,'input_event_after_trial')
        if e['kind']=='study':
            if a.response is not None:raise HTTPException(422,'study_has_response')
            if complete and a.duration_ms<e['limit_ms']:raise HTTPException(422,'exposure_too_short')
        else:
            options={'recognition':['old','new'],'attention':['go'],'switch':['left','right'],'match':['same','different']}[e['kind']]
            if a.response is not None and a.response not in options:raise HTTPException(422,'invalid_response_for_task')
            if a.rt_ms is not None and a.rt_ms>e['limit_ms']:raise HTTPException(422,'response_after_deadline')
            # The last interrupted trial may end before its response deadline.
            if a.response is None and a.duration_ms<e['limit_ms'] and (complete or a is not actual[-1]):raise HTTPException(422,'timeout_too_short')
    return end

def summary(payload,task,expected,profile,device,delay):
    ts=payload.trials;responses=[x for x,e in zip(ts,expected) if e['kind']!='study'];pairs=[(x,e) for x,e in zip(ts,expected) if e['kind']!='study' and (x.response is not None or x.duration_ms>=e['limit_ms'])]
    focus_affected={x.index for x in ts if any(ev.kind=='focus_loss' for ev in x.response_events)}
    good=[x.rt_ms for x,e in pairs if e['expected'] is not None and x.response==e['expected'] and x.index not in focus_affected]
    out=dict(trials_recorded=len(ts),response_trials=len(responses),correct=sum(x.response==e['expected'] for x,e in pairs),
      omissions=sum(x.response is None and e['expected'] is not None for x,e in pairs),
      commissions=sum(x.response is not None and e['expected'] is None for x,e in pairs),
      incorrect_responses=sum(x.response is not None and x.response!=e['expected'] for x,e in pairs),
      median_correct_rt_ms=statistics.median(good) if good else None,rt_sample_sd_ms=statistics.stdev(good) if len(good)>1 else None,
      rt_n=len(good),clinical_score=None,quality_flags=[],units={'rt':'ms','delay':'ms','counts':'count'})
    if task in ['C01','C02']:
        out.update(hits=sum(x.response=='old' and e['expected']=='old' for x,e in pairs),false_alarms=sum(x.response=='old' and e['expected']=='new' for x,e in pairs),recognition_delay_ms=delay if task=='C02' else None)
    if task=='C04':
        switch=[];repeat=[]
        for i,(x,e) in enumerate(zip(ts,expected)):
            if i and x.index not in focus_affected and x.response==e['expected']:(switch if e['rule']!=expected[i-1]['rule'] else repeat).append(x.rt_ms)
        out.update(switch_correct_n=len(switch),repeat_correct_n=len(repeat),switch_cost_ms=statistics.median(switch)-statistics.median(repeat) if len(switch)>=3 and len(repeat)>=3 else None)
    inputs=sorted({x.input for x in ts if x.input});out['observed_inputs']=inputs
    if inputs and inputs!=[profile['input_method']]:out['quality_flags'].append('OBSERVED_INPUT_DIFFERS_OR_MIXED')
    if focus_affected:
        out['quality_flags'].append('FOCUS_LOSS_AFFECTED_TIMING')
        out['focus_affected_trial_indices']=sorted(focus_affected)
        out['interpretation']='research_measurements_with_unreliable_focus_affected_trials'
    if any(x.max_frame_gap_ms>100 for x in ts):out['quality_flags'].append('FRAME_GAP_OVER_100_MS')
    if any(x.duration_ms>e['limit_ms']+500 for x,e in zip(ts,expected)):out['quality_flags'].append('PRESENTATION_OVERRUN')
    if profile['assistance']=='responses':out['quality_flags'].append('RESPONSES_ASSISTED')
    if device['refresh_max_ms']>100:out['quality_flags'].append('DEVICE_FRAME_INSTABILITY')
    if device['width']<600 or device['height']<400:out['quality_flags'].append('SMALL_VIEWPORT')
    if payload.status!='completed':out['quality_flags'].append('INTERRUPTED')
    if payload.reason=='camera_unavailable':out['quality_flags'].append('CAMERA_CAPTURE_INTERRUPTED')
    if payload.reason=='page_reload':out['quality_flags'].append('RECOVERED_WITHOUT_FULL_TRIAL_LOG')
    if any(x.rt_ms is not None and x.rt_ms<100 for x in ts):out['quality_flags'].append('RESPONSE_UNDER_100_MS')
    out['input_events_recorded']=sum(len(x.response_events) for x in ts)
    out['ignored_input_events']=sum(ev.kind in ['duplicate','late','key_repeat'] for x in ts for ev in x.response_events)
    if out['ignored_input_events']:out['quality_flags'].append('ADDITIONAL_INPUT_ATTEMPTS_IGNORED')
    out['unscored_partial_response_trials']=len(responses)-len(pairs)
    out['practice_trials_recorded']=len(payload.practice_log)+sum(len(run) for run in payload.practice_interrupted_runs)
    out['measurement_method']='client_performance_clock_raf_with_server_plausibility_checks'
    out['hardware_latency_calibrated']=False
    out['interpretation']='descriptive_quality_limited_not_diagnosis' if focus_affected else 'descriptive_research_observations_not_diagnosis'
    return out

def vision_label_only_change(before, after):
    """A history label is not a change in demonstrated interaction ability."""
    return (isinstance(before.get('vision_limitation'), bool)
            and isinstance(after.get('vision_limitation'), bool)
            and before.get('can_see_and_respond') == after.get('can_see_and_respond') == 'yes'
            and before.get('vision_aid') == after.get('vision_aid')
            and after.get('vision_aid') in ('none', 'glasses'))

def readiness_profile_changed(before, after):
    return any(before.get(k) != after.get(k) for k in FIELDS
               if not (k == 'vision_limitation' and vision_label_only_change(before, after)))

def session_order(s):return json.loads(s['manifest']).get('_meta',{}).get('order',ORDER)
def session_battery(s):return json.loads(s['manifest']).get('_meta',{}).get('battery','core')

CONCERN_DOMAINS=('mental_health','adhd','autism','substance_use','brain_injury','daily_function','sleep','other')
class ContextReport(Strict):
    id:UUID=Field(strict=False)
    consent:Literal[True]
    domain:Literal['mental_health','adhd','autism','substance_use','brain_injury','daily_function','sleep','other']
    impact:Literal['none','some','substantial','prefer_not_to_say']
    change:Literal['new','ongoing','improving','unknown']
    note:str=Field(default='',max_length=1000)

def make_router(store,authenticated):
    r=APIRouter(prefix='/api/ncx',dependencies=[Depends(authenticated)])
    def checkin(c,cid,mode):
        row=c.execute('SELECT c.*,p.profile AS current_profile FROM checkins c JOIN participants p ON p.id=c.participant_id WHERE c.id=? AND c.mode=?',(str(cid),mode)).fetchone()
        if not row:raise HTTPException(404,'checkin_not_found')
        return row
    def gate(row):
        p=json.loads(row['profile']);current=json.loads(row['current_profile']);reasons=[]
        if not json.loads(row['gate'])['practice_allowed']:reasons.append('neuroaccess_hold')
        if row['status']!='completed' or not row['practice']:reasons.append('complete_neuroaccess_practice')
        if readiness_profile_changed(p,current):reasons.append('profile_changed_create_new_checkin')
        return reasons
    def require_recovery(c,row):
        t=recovery_ticket(c,row['id'],row['mode'])
        if t:
            reasons=recovery_authorization(c,t)
            if reasons:raise HTTPException(409,','.join(reasons))
        return t
    def session(c,sid,mode):
        row=c.execute('SELECT * FROM nc_sessions WHERE id=? AND mode=?',(str(sid),mode)).fetchone()
        if not row:raise HTTPException(404,'session_not_found')
        return row
    def prep(c,aid):
        row=c.execute('SELECT payload FROM nc_preparations WHERE attempt_id=?',(aid,)).fetchone()
        return json.loads(row['payload']) if row else dict(policy='required-practice-v1',practice_decision='not_recorded',source='historical_required_contract',understanding_confirmed=None)
    def attempt(a,c):
        submitted=json.loads(a['submitted']) if a['submitted'] else None;sm=json.loads(a['summary']) if a['summary'] else None
        reviews=[dict(x) for x in c.execute('SELECT * FROM nc_response_reviews WHERE attempt_id=? ORDER BY item_index,revision',(a['id'],))]
        checkpoint=c.execute('SELECT * FROM nc_input_checkpoints WHERE attempt_id=?',(a['id'],)).fetchone()
        cp=None
        if checkpoint:
            value=json.loads(checkpoint['payload']);cp=dict(revision=checkpoint['revision'],updated_at=checkpoint['updated_at'],saved_trials=len(value['trials'])+len(value['extra_trials']),payload=value if not submitted else None)
        return dict(a) | {'preparation':prep(c,a['id']),'submitted':submitted,'summary':sm,'reviews':reviews,'checkpoint':cp,'reviewed_counts':review_summary(submitted,sm or {},reviews) if submitted and a['task'] in ['C09','C10'] else None}

    def annotate(sm,preparation,protocol):
        sm['preparation']=preparation
        if preparation.get('camera_observation'):sm['quality_flags'].append('CAMERA_PROCESSING_MAY_AFFECT_BROWSER_TIMING')
        if preparation.get('input_capture_version')=='input-v2' and protocol!=VERSION:sm['quality_flags'].append('INPUT_CAPTURE_IMPLEMENTATION_CHANGED')
        if preparation['policy']=='optional-practice-v1':
            if protocol in [LEGACY_VERSION,'ncx-research-v1.1.0']:sm['quality_flags'].append('PREPARATION_POLICY_AMENDED')
            if preparation['practice_decision']=='skipped':sm['quality_flags'].append('PRACTICE_SKIPPED')
            if preparation['practice_decision']=='not_passed':sm['quality_flags'].append('PRACTICE_NOT_PASSED')
        return sm

    def view(c,s):
        attempts=[attempt(a,c) for a in c.execute('SELECT * FROM nc_attempts WHERE session_id=? ORDER BY started_at,id',(s['id'],))]
        by={a['task']:a for a in attempts};next_task=next((t for t in session_order(s) if t not in by or by[t]['status']!='completed'),None)
        blocked=next_task in by and by[next_task]['status']=='interrupted' if next_task else False
        closure=c.execute('SELECT * FROM nc_session_closures WHERE session_id=?',(s['id'],)).fetchone()
        missing_tasks=[t for t in session_order(s) if t not in by or by[t]['status']!='completed']
        previous=c.execute('SELECT * FROM nc_sessions WHERE participant_id=? AND mode=? AND id!=? AND created_at<? ORDER BY created_at DESC,id DESC LIMIT 1',(s['participant_id'],s['mode'],s['id'],s['created_at'])).fetchone()
        comparison=dict(reference_session_id=previous['id'] if previous else None,interval_since_previous_hours=(datetime.fromisoformat(s['created_at'])-datetime.fromisoformat(previous['created_at'])).total_seconds()/3600 if previous else None,condition_changes=[],clinical_comparability_established=False,form_equivalence_established=False,practice_effect_adjustment=None,rci=None)
        if previous:
            p0=json.loads(previous['profile']);p1=json.loads(s['profile'])
            comparison['condition_changes']=[k for k in FIELDS if p0[k]!=p1[k]]
            if previous['form']!=s['form']:comparison['condition_changes'].append('uncalibrated_alternate_form')
            if previous['protocol']!=s['protocol']:comparison['condition_changes'].append('protocol')
            if session_order(previous)!=session_order(s):comparison['condition_changes'].append('task_order')
            if session_battery(previous)!=session_battery(s):comparison['condition_changes'].append('battery')
        previous_attempts=c.execute('SELECT count(*) FROM nc_attempts a JOIN nc_sessions n ON n.id=a.session_id WHERE n.participant_id=? AND n.id!=? AND n.created_at<?',(s['participant_id'],s['id'],s['created_at'])).fetchone()[0]
        previous_form_attempts=c.execute('SELECT count(*) FROM nc_attempts a JOIN nc_sessions n ON n.id=a.session_id WHERE n.participant_id=? AND n.id!=? AND n.form=? AND n.created_at<?',(s['participant_id'],s['id'],s['form'],s['created_at'])).fetchone()[0]
        comparison['administration_amendments']=[dict(task=a['task'],**a['preparation']) for a in attempts if a['preparation']['policy']=='optional-practice-v1']
        comparison['previous_task_attempts']=previous_attempts;comparison['previous_same_form_task_attempts']=previous_form_attempts
        memory=by.get('C01')
        ready_in=max(0,120000-elapsed(memory['finished_at'])) if memory and memory['finished_at'] else None
        return dict(auto_advance=json.loads(s['manifest']).get('_meta',{}).get('auto_advance',True),recognition_ready_in_ms=ready_in,id=s['id'],checkin_id=s['checkin_id'],participant_id=s['participant_id'],mode=s['mode'],protocol=s['protocol'],form=s['form'],profile=json.loads(s['profile']),device=json.loads(s['device']),created_at=s['created_at'],attempts=attempts,next_task=None if closure else next_task,status='completed' if closure else 'interrupted' if blocked else 'completed' if next_task is None else 'in_progress',result_completeness='partial' if closure else 'complete' if next_task is None else 'in_progress',missing_tasks=missing_tasks,closure=dict(closure) if closure else None,comparison=comparison,eligibility_reasons=gate(checkin(c,s['checkin_id'],s['mode'])),clinical_validation='not_established',battery=session_battery(s),order=session_order(s),extended_tasks='available_in_new_extended_or_full_sessions',task_manifests={t:definition(s,t) for t in session_order(s)},scoring_version=s['protocol'],language_validation='translation_not_clinically_validated')
    @r.get('/checkins/{cid}')
    def entry(cid:UUID,mode:Literal['active','demo']):
        with store.connect() as c:
            row=checkin(c,cid,mode);s=c.execute('SELECT * FROM nc_sessions WHERE checkin_id=?',(str(cid),)).fetchone()
            return dict(checkin_id=str(cid),participant_id=row['participant_id'],profile=json.loads(row['current_profile']),reasons=gate(row),session=view(c,s) if s else None)
    @r.post('/checkins/{cid}/sessions',status_code=201)
    def create(cid:UUID,mode:Literal['active','demo'],payload:NewSession):
        with store.connect(True) as c:
            row=checkin(c,cid,mode)
            if payload.daily_followup or payload.battery=='quick':
                holds=_plus.automatic_holds(c,row['participant_id'],mode)
                if holds:raise HTTPException(409,','.join(holds))
            recovery=require_recovery(c,row);existing=c.execute('SELECT * FROM nc_sessions WHERE checkin_id=?',(str(cid),)).fetchone()
            if existing:
                if existing['id']!=str(payload.id) or json.loads(existing['device'])!=payload.device.model_dump() or session_battery(existing)!=payload.battery:raise HTTPException(409,'session_already_exists')
                return view(c,existing)
            if payload.battery=='quick':
                proposal=daily_plan(c,row['participant_id'],mode)
                if not proposal['executable'] or proposal['battery']!='quick' or proposal['checkin_id']!=str(cid):raise HTTPException(409,'fresh_quick_plan_required')
            reasons=gate(row)
            if reasons:raise HTTPException(409,','.join(reasons))
            if c.execute('SELECT 1 FROM nc_sessions WHERE id=?',(str(payload.id),)).fetchone():raise HTTPException(409,'idempotency_conflict')
            n=c.execute('SELECT count(*) FROM nc_sessions WHERE participant_id=?',(row['participant_id'],)).fetchone()[0]
            base=int(hashlib.sha256(row['participant_id'].encode()).hexdigest()[:8],16)%2
            form='A' if (n+base)%2==0 else 'B'
            seed=hashlib.sha256(str(payload.id).encode()).hexdigest()
            middle=['C03','C04','C05'];random.Random(seed+'order').shuffle(middle)
            order=['C03','C05','C06'] if payload.battery=='quick' else ['C01']+middle+['C02','C06']
            if payload.battery in ['extended','full']:
                extra=['C07','C08','C09','C10'];random.Random(seed+'extended-order').shuffle(extra);order+=extra
            if payload.battery=='full':order+=['C11','C12']
            if recovery:
                order=recovery['details']['order']
                if payload.battery!='core':raise HTTPException(422,'recovery_uses_explicit_task_order')
            manifest_dict={t:definition({'seed':seed,'form':form},t) for t in order}
            manifest_dict['_meta']=dict(order=order,battery=payload.battery,protocol=VERSION,motor_ack=payload.motor_ack,auto_advance=payload.auto_advance,randomization='seeded-item-bank-v2',forms_equivalent=False,daily_followup=payload.daily_followup or payload.battery=='quick')
            if payload.daily_followup or payload.battery=='quick':
                latest_context=c.execute("SELECT id,sha256 FROM ncx3_records WHERE participant_id=? AND mode=? AND kind='daily' ORDER BY created_at DESC,id DESC LIMIT 1",(row['participant_id'],mode)).fetchone()
                manifest_dict['_meta']['daily_context_reference']=dict(latest_context)
                manifest_dict['_meta']['daily_policy']='ncx-connected-research-3.1.0'
            if recovery:manifest_dict['_meta']['recovery']=dict(id=recovery['id'],source_attempts=recovery['details']['source_attempts'],correction=recovery['details']['correction'],interpretation='research_recovery_not_equivalent_repeat')
            manifest=dump(manifest_dict)
            c.execute('INSERT INTO nc_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(str(payload.id),str(cid),row['participant_id'],mode,VERSION,form,seed,row['current_profile'],dump(payload.device.model_dump()),manifest,now()))
            return view(c,session(c,payload.id,mode))
    @r.post('/sessions/{sid}/tasks/{task}/attempts/{aid}/abandon')
    def abandon_attempt(sid:UUID,task:TaskId,aid:UUID,mode:Literal['active','demo']):
        # Escape hatch when a client cannot submit valid trial timing. The original
        # server checkpoint remains untouched but is not promoted to a valid score.
        with store.connect(True) as c:
            s=session(c,sid,mode)
            a=c.execute('SELECT * FROM nc_attempts WHERE id=? AND session_id=? AND task=?',
                (str(aid),str(sid),task)).fetchone()
            if not a:raise HTTPException(404,'attempt_not_found')
            if a['submitted']:
                return attempt(a,c)
            if a['status']!='running':raise HTTPException(409,'attempt_not_running')
            abandoned=Result(protocol=s['protocol'],status='interrupted',reason='user_stopped',
                trials=[],reports=[],practice_log=[],extra_trials=[],extra_practice_runs=[]).model_dump(mode='json')
            evidence=dict(trials_recorded=0,clinical_score=None,
                quality_flags=['INTERRUPTED','UNVALIDATED_CHECKPOINT_RETAINED'],
                interpretation='incomplete_record_not_valid_for_cognitive_scoring')
            c.execute('UPDATE nc_attempts SET status=?,finished_at=?,submitted=?,summary=? WHERE id=?',
                ('interrupted',now(),dump(abandoned),dump(evidence),str(aid)))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',
                ('ncx_abandon_unvalidated_attempt',s['checkin_id'],mode,now()))
            return attempt(c.execute('SELECT * FROM nc_attempts WHERE id=?',(str(aid),)).fetchone(),c)
    @r.post('/sessions/{sid}/finish-available')
    def finish_available(sid:UUID,mode:Literal['active','demo']):
        with store.connect(True) as c:
            s=session(c,sid,mode)
            if c.execute('SELECT 1 FROM nc_session_closures WHERE session_id=?',(str(sid),)).fetchone():
                return view(c,s)
            attempts=c.execute('SELECT status FROM nc_attempts WHERE session_id=?',(str(sid),)).fetchall()
            if any(a['status']=='running' for a in attempts):raise HTTPException(409,'running_attempt_must_be_saved_first')
            state=view(c,s)
            if not state['missing_tasks']:return state
            c.execute('INSERT INTO nc_session_closures VALUES(?,?,?,?,?)',(str(sid),mode,'participant_requested_finish_with_available',now(),dump(state['missing_tasks'])))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('ncx_finish_available',s['checkin_id'],mode,now()))
            return view(c,s)
    @r.get('/sessions/{sid}')
    def get(sid:UUID,mode:Literal['active','demo']):
        with store.connect() as c:return view(c,session(c,sid,mode))
    @r.get('/participants/{pid}/sessions')
    def history(pid:UUID,mode:Literal['active','demo']):
        with store.connect() as c:
            if not c.execute('SELECT id FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone():raise HTTPException(404,'participant_not_found')
            return dict(items=[view(c,s) for s in c.execute('SELECT * FROM nc_sessions WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC',(str(pid),mode))])
    @r.get('/participants/{pid}/access')
    def access_directory(pid:UUID,mode:Literal['active','demo']):
        with store.connect() as c:
            p=c.execute('SELECT * FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone()
            if not p:raise HTTPException(404,'participant_not_found')
            items=[]
            for row in c.execute('SELECT id,created_at,status FROM checkins WHERE participant_id=? AND mode=? ORDER BY created_at DESC,id DESC',(str(pid),mode)):
                row=dict(row);full=checkin(c,row['id'],mode);row['reasons']=gate(full);row['practice_completed']=bool(full['practice']);items.append(row)
            return dict(participant_id=str(pid),profile=json.loads(p['profile']),items=items)
    @r.get('/participants/{pid}/analytics')
    def analytics(pid:UUID,mode:Literal['active','demo']):
        with store.connect() as c:
            person=c.execute('SELECT * FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone()
            if not person:raise HTTPException(404,'participant_not_found')
            sessions=[view(c,s) for s in c.execute('SELECT * FROM nc_sessions WHERE participant_id=? AND mode=? ORDER BY created_at,id',(str(pid),mode))]
            series={t:[] for t in ORDER+EXTENDED}
            for s in sessions:
                for a in s['attempts']:
                    sm=a['summary'] or {}
                    series[a['task']].append(dict(session_id=s['id'],created_at=s['created_at'],protocol=s['protocol'],form=s['form'],order=s['order'],battery=s['battery'],status=a['status'],summary=sm,reviewed_counts=a.get('reviewed_counts'),language=s['profile']['language'],input_method=s['profile']['input_method'],device_type=s['profile']['device_type'],assistance=s['profile']['assistance'],condition_group=hashlib.sha256(dump({'protocol':s['protocol'],'preparation':a['preparation'],'form':s['form'],'order':s['order'],'profile':{k:s['profile'][k] for k in FIELDS},'device':{k:s['device'][k] for k in ['user_agent','width','height','pixel_ratio','pointer']}}).encode()).hexdigest()[:12],condition_changes=s['comparison']['condition_changes']))
            return dict(participant_id=str(pid),mode=mode,display_name=json.loads(person['profile'])['display_name'],profile=json.loads(person['profile']),total_sessions=len(sessions),completed_sessions=sum(s['status']=='completed' for s in sessions),interrupted_sessions=sum(s['status']=='interrupted' for s in sessions),session_history=[{k:s[k] for k in ['id','checkin_id','created_at','protocol','form','battery','status','comparison','order']} for s in sessions],task_series=series,clinical_score=None,rci=None,practice_effect_estimate=None,clinical_comparability_established=False,interpretation='descriptive_history_only_not_improvement_or_decline')
    @r.get('/sessions/{sid}/tasks/{task}')
    def task_definition(sid:UUID,task:TaskId,mode:Literal['active','demo']):
        with store.connect() as c:
            s=session(c,sid,mode);require_recovery(c,checkin(c,s['checkin_id'],mode));return definition(s,task)|{'minimum_delay_ms':120000 if task=='C02' else None}
    @r.put('/sessions/{sid}/tasks/{task}/attempts/{aid}/start')
    def start(sid:UUID,task:TaskId,aid:UUID,mode:Literal['active','demo'],payload:Start):
        with store.connect(True) as c:
            s=session(c,sid,mode);require_recovery(c,checkin(c,s['checkin_id'],mode));
            if c.execute('SELECT 1 FROM nc_session_closures WHERE session_id=?',(str(sid),)).fetchone():raise HTTPException(409,'visit_already_closed')
            d=definition(s,task);preparation=payload.record()
            if preparation['policy']=='optional-practice-v1' and ((not d['practice_required'])!=(preparation['practice_decision']=='not_applicable')):raise HTTPException(422,'practice_decision_not_applicable_to_task')
            old=c.execute('SELECT * FROM nc_attempts WHERE session_id=? AND task=?',(str(sid),task)).fetchone()
            if old:
                if old['id']!=str(aid):raise HTTPException(409,'attempt_exists')
                stored=c.execute('SELECT payload FROM nc_preparations WHERE attempt_id=?',(str(aid),)).fetchone()
                if stored and json.loads(stored['payload'])!=preparation:raise HTTPException(409,'preparation_immutable')
                if not stored and preparation['policy']!='required-practice-v1':raise HTTPException(409,'existing_attempt_uses_legacy_preparation')
                return attempt(old,c)
            if json.loads(s['manifest']).get('_meta',{}).get('daily_followup'):
                holds=_plus.automatic_holds(c,s['participant_id'],mode)
                if holds:raise HTTPException(409,','.join(holds))
            if gate(checkin(c,s['checkin_id'],mode)):raise HTTPException(409,'neuroaccess_conditions_changed_or_hold')
            state=view(c,s)
            if state['next_task']!=task or state['status']=='interrupted':raise HTTPException(409,'task_order_or_interruption')
            if task=='C02':
                a=c.execute("SELECT * FROM nc_attempts WHERE session_id=? AND task='C01'",(str(sid),)).fetchone()
                # Conservative minimum measured from END of C01, after immediate probes.
                if elapsed(a['finished_at'])<120000:raise HTTPException(409,'recognition_delay_not_reached')
            if c.execute('SELECT 1 FROM nc_attempts WHERE id=?',(str(aid),)).fetchone():raise HTTPException(409,'idempotency_conflict')
            c.execute("INSERT INTO nc_attempts VALUES(?,?,?,'running',?,NULL,NULL,NULL)",(str(aid),str(sid),task,now()))
            c.execute('INSERT INTO nc_preparations VALUES(?,?)',(str(aid),dump(preparation)))
            return attempt(c.execute('SELECT * FROM nc_attempts WHERE id=?',(str(aid),)).fetchone(),c)
    @r.put('/sessions/{sid}/tasks/{task}/attempts/{aid}/checkpoint')
    def checkpoint(sid:UUID,task:TaskId,aid:UUID,mode:Literal['active','demo'],payload:Checkpoint):
        with store.connect(True) as c:
            s=session(c,sid,mode);require_recovery(c,checkin(c,s['checkin_id'],mode));a=c.execute('SELECT * FROM nc_attempts WHERE id=? AND session_id=? AND task=?',(str(aid),str(sid),task)).fetchone()
            if not a:raise HTTPException(404,'attempt_not_found')
            if payload.protocol!=s['protocol']:raise HTTPException(422,'protocol_mismatch')
            if a['submitted']:return dict(finalized=True,revision=payload.revision)
            d=definition(s,task)
            if task in EXTENDED:
                if payload.trials:raise HTTPException(422,'checkpoint_task_mismatch')
                end=validate_extended(payload.extra_trials,d['trials'],False,json.loads(s['profile'])['language']);count=len(payload.extra_trials)
            else:
                if payload.extra_trials or payload.current_draft:raise HTTPException(422,'checkpoint_task_mismatch')
                end=validate_trials(payload.trials,d['trials'],False);count=len(payload.trials)
            if payload.current_draft:
                draft=payload.current_draft
                if count>=len(d['trials']) or d['trials'][count]['kind'] not in ['naming','category','context'] or draft.index!=count or draft.stimulus_id!=d['trials'][count]['stimulus_id'] or draft.response is not None or draft.capture_version!='input-v2':raise HTTPException(422,'invalid_draft_checkpoint')
                validate_extended(payload.extra_trials+[draft],d['trials'],False,json.loads(s['profile'])['language']);end=max(end,draft.onset_ms+draft.duration_ms)
            if end>elapsed(a['started_at'])+1000:raise HTTPException(422,'checkpoint_timing_exceeds_elapsed')
            normalized=dump(payload.model_dump(mode='json'));old=c.execute('SELECT * FROM nc_input_checkpoints WHERE attempt_id=?',(str(aid),)).fetchone()
            if old and old['revision']>payload.revision:return dict(finalized=False,stale=True,revision=old['revision'])
            if old and old['revision']==payload.revision:
                if old['payload']!=normalized:raise HTTPException(409,'checkpoint_revision_conflict')
                return dict(finalized=False,revision=old['revision'],saved_trials=count)
            c.execute('INSERT INTO nc_input_checkpoints VALUES(?,?,?,?) ON CONFLICT(attempt_id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload,updated_at=excluded.updated_at',(str(aid),payload.revision,normalized,now()))
            return dict(finalized=False,revision=payload.revision,saved_trials=count)
    @r.put('/sessions/{sid}/tasks/{task}/attempts/{aid}/reviews/{rid}')
    def review_response(sid:UUID,task:TaskId,aid:UUID,rid:UUID,mode:Literal['active','demo'],payload:ResponseReview):
        with store.connect(True) as c:
            s=session(c,sid,mode);require_recovery(c,checkin(c,s['checkin_id'],mode));a=c.execute('SELECT * FROM nc_attempts WHERE id=? AND session_id=? AND task=?',(str(aid),str(sid),task)).fetchone()
            if not a:raise HTTPException(404,'attempt_not_found')
            if task not in ['C09','C10'] or not a['submitted']:raise HTTPException(409,'review_requires_saved_language_response')
            rows=json.loads(a['submitted']).get('extra_trials',[])
            if payload.item_index>=len(rows) or not isinstance(rows[payload.item_index]['response'],str):raise HTTPException(422,'no_submitted_answer_to_review')
            old=c.execute('SELECT * FROM nc_response_reviews WHERE id=?',(str(rid),)).fetchone()
            if old:
                if old['attempt_id']!=str(aid) or old['item_index']!=payload.item_index or old['decision']!=payload.decision or old['note']!=payload.note or old['revision']!=payload.expected_revision+1:raise HTTPException(409,'review_id_conflict')
                return dict(old)
            latest=c.execute('SELECT max(revision) FROM nc_response_reviews WHERE attempt_id=? AND item_index=?',(str(aid),payload.item_index)).fetchone()[0] or 0
            if latest!=payload.expected_revision:raise HTTPException(409,'review_revision_conflict_reload')
            c.execute('INSERT INTO nc_response_reviews VALUES(?,?,?,?,?,?,?)',(str(rid),str(aid),payload.item_index,payload.decision,payload.note,latest+1,now()))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('response_operator_review',s['checkin_id'],mode,now()))
            return dict(c.execute('SELECT * FROM nc_response_reviews WHERE id=?',(str(rid),)).fetchone())
    @r.put('/sessions/{sid}/tasks/{task}/attempts/{aid}/result')
    def finish(sid:UUID,task:TaskId,aid:UUID,mode:Literal['active','demo'],payload:Result):
        with store.connect(True) as c:
            s=session(c,sid,mode);require_recovery(c,checkin(c,s['checkin_id'],mode));a=c.execute('SELECT * FROM nc_attempts WHERE id=? AND session_id=? AND task=?',(str(aid),str(sid),task)).fetchone()
            if not a:raise HTTPException(404,'attempt_not_found')
            preparation=prep(c,str(aid));require_pass=preparation['policy']=='required-practice-v1' or preparation['practice_decision']=='passed'
            if payload.protocol!=s['protocol']:raise HTTPException(422,'protocol_mismatch')
            norm=payload.model_dump(mode='json')
            for field in ['trials','practice_log','extra_trials']:
                for item,model in zip(norm[field],getattr(payload,field)):
                    for key in CAPTURE_FIELDS:
                        if key not in model.model_fields_set:item.pop(key,None)
            for field in ['extra_practice_runs','practice_interrupted_runs']:
                for run,models in zip(norm[field],getattr(payload,field)):
                    for item,model in zip(run,models):
                        for key in CAPTURE_FIELDS:
                            if key not in model.model_fields_set:item.pop(key,None)
            if s['protocol']==LEGACY_VERSION:
                for field in ['extra_trials','extra_practice_runs']:norm.pop(field,None)
            if a['submitted']:
                if json.loads(a['submitted'])!=norm:raise HTTPException(409,'result_immutable')
                return attempt(a,c)
            if task in EXTENDED:
                if payload.trials or payload.reports or payload.practice_log or payload.practice_interrupted_runs:raise HTTPException(422,'extended_task_payload_mismatch')
                d=definition(s,task);end=validate_extended(payload.extra_trials,d['trials'],payload.status=='completed',json.loads(s['profile'])['language'])
                if end>elapsed(a['started_at'])+1000:raise HTTPException(422,'client_timing_exceeds_server_elapsed')
                for run in payload.extra_practice_runs:validate_extended(run,d['practice'],False,json.loads(s['profile'])['language'])
                if payload.status=='completed' and d['practice_required'] and require_pass:
                    if not payload.extra_practice_runs:raise HTTPException(422,'extended_practice_required')
                    validate_extended(payload.extra_practice_runs[-1],d['practice'],True,json.loads(s['profile'])['language'],practice=True)
                sm=summarize_extended(payload.extra_trials,d['trials'],json.loads(s['profile'])['language'],task,payload.status)
                annotate(sm,preparation,s['protocol'])
                p=json.loads(s['profile'])
                if p['assistance']=='responses':sm['quality_flags'].append('RESPONSES_ASSISTED')
                if sm['observed_inputs'] and sm['observed_inputs']!=[p['input_method']]:sm['quality_flags'].append('OBSERVED_INPUT_DIFFERS_OR_MIXED')
                if gate(checkin(c,s['checkin_id'],mode)):sm['quality_flags'].append('CURRENT_ACCESS_CONDITIONS_CHANGED')
                if payload.reason=='page_reload':sm['quality_flags'].append('RECOVERED_WITHOUT_FULL_TRIAL_LOG')
                sm['practice_runs_recorded']=len(payload.extra_practice_runs)
                c.execute('UPDATE nc_attempts SET status=?,finished_at=?,submitted=?,summary=? WHERE id=?',(payload.status,now(),dump(norm),dump(sm),str(aid)))
                c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('ncx_'+task+'_'+payload.status,s['checkin_id'],mode,now()))
                return attempt(c.execute('SELECT * FROM nc_attempts WHERE id=?',(str(aid),)).fetchone(),c)
            if payload.extra_trials or payload.extra_practice_runs:raise HTTPException(422,'core_task_payload_mismatch')
            for run in payload.practice_interrupted_runs:validate_trials(run,definition(s,task)['practice'],False)
            expected=definition(s,task)['trials'];end=validate_trials(payload.trials,expected,payload.status=='completed')
            if end>elapsed(a['started_at'])+1000:raise HTTPException(422,'client_timing_exceeds_server_elapsed')
            if task!='C06':
                if payload.reports:raise HTTPException(422,'reports_only_for_C06')
                if payload.status=='completed':
                    practice=definition(s,task)['practice']
                    if payload.practice_log and len(payload.practice_log)%len(practice):raise HTTPException(422,'incomplete_practice_log')
                    for offset in range(0,len(payload.practice_log),len(practice)):
                        validate_trials(payload.practice_log[offset:offset+len(practice)],practice,True)
                    if require_pass and (not payload.practice_log or any(x.response!=e['expected'] for x,e in zip(payload.practice_log[-len(practice):],practice))):raise HTTPException(422,'practice_not_passed')
            else:
                if payload.trials or payload.practice_log:raise HTTPException(422,'C06_uses_reports')
                if payload.status=='completed' and not payload.reports:raise HTTPException(422,'report_required')
                sources=[x.source for x in payload.reports]
                if len(set(sources))!=len(sources):raise HTTPException(422,'duplicate_report_source')
                for report in payload.reports:
                    if report.source=='informant' and not report.authorized:raise HTTPException(422,'informant_authorization_required')
                    if {x.item for x in report.answers}!={'schedule','activities','instructions','routines','concerns'}:raise HTTPException(422,'incomplete_report')
            delay=None
            if task=='C02':
                memory=c.execute("SELECT * FROM nc_attempts WHERE session_id=? AND task='C01'",(str(sid),)).fetchone()
                # Exact last study offset plus observed end-to-end server wall time.
                first=json.loads(memory['submitted'])['trials'];study_end=max(x['onset_ms']+x['duration_ms'] for x in first[:6])
                delay=(datetime.fromisoformat(a['started_at'])-datetime.fromisoformat(memory['started_at'])).total_seconds()*1000-study_end
            clock_issue=delay is not None and delay<0
            sm=summary(payload,task,expected,json.loads(s['profile']),json.loads(s['device']),None if clock_issue else delay)
            annotate(sm,preparation,s['protocol'])
            if task=='C02' and s['protocol'] in [LEGACY_VERSION,'ncx-research-v1.1.0']:sm['quality_flags'].append('LEGACY_MEMORY_SPEED_STIMULUS_OVERLAP_POSSIBLE')
            if clock_issue:sm['quality_flags'].append('SERVER_CLOCK_MAPPING_INCONSISTENT')
            if task=='C06':sm['reports']=norm['reports']
            if gate(checkin(c,s['checkin_id'],mode)):sm['quality_flags'].append('CURRENT_ACCESS_CONDITIONS_CHANGED')
            c.execute('UPDATE nc_attempts SET status=?,finished_at=?,submitted=?,summary=? WHERE id=?',(payload.status,now(),dump(norm),dump(sm),str(aid)))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('ncx_'+task+'_'+payload.status,s['checkin_id'],mode,now()))
            return attempt(c.execute('SELECT * FROM nc_attempts WHERE id=?',(str(aid),)).fetchone(),c)
    @r.get('/participants/{pid}/context')
    def context_history(pid:UUID,mode:Literal['active','demo']):
        with store.connect() as c:
            if not c.execute('SELECT id FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone():raise HTTPException(404,'participant_not_found')
            rows=c.execute('SELECT payload FROM nc_context_reports WHERE participant_id=? AND mode=? ORDER BY created_at DESC LIMIT 100',(str(pid),mode)).fetchall()
            return dict(items=[json.loads(x['payload']) for x in rows],domains=CONCERN_DOMAINS,clinical_validation=False)
    @r.post('/participants/{pid}/context')
    def context_save(pid:UUID,mode:Literal['active','demo'],payload:ContextReport):
        with store.connect(True) as c:
            if not c.execute('SELECT id FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone():raise HTTPException(404,'participant_not_found')
            body=payload.model_dump(mode='json');old=c.execute('SELECT * FROM nc_context_reports WHERE id=?',(str(payload.id),)).fetchone()
            if old:
                if old['participant_id']!=str(pid) or old['mode']!=mode or json.loads(old['payload'])['report']!=body:raise HTTPException(409,'report_id_conflict')
                return json.loads(old['payload'])
            value=dict(report=body,created_at=now(),classification='SELF_REPORTED',instrument='bainp-context-intake-v1',clinical_validation=False,interpretation='Concern recorded; no diagnosis or screening score generated.')
            c.execute('INSERT INTO nc_context_reports VALUES(?,?,?,?,?)',(str(payload.id),str(pid),mode,value['created_at'],dump(value)))
            return value
    @r.delete('/participants/{pid}/context/{rid}')
    def context_delete(pid:UUID,rid:UUID,mode:Literal['active','demo']):
        with store.connect(True) as c:
            row=c.execute('SELECT id FROM nc_context_reports WHERE id=? AND participant_id=? AND mode=?',(str(rid),str(pid),mode)).fetchone()
            if not row:raise HTTPException(404,'report_not_found')
            c.execute('DELETE FROM nc_context_reports WHERE id=?',(str(rid),))
            return dict(deleted=True)
    hub,daily_plan=_plus.make_router(store,authenticated,analytics,checkin,gate)
    r.include_router(hub)
    @r.post('/hub/{pid}/launch',status_code=201)
    def launch_daily(pid:UUID,mode:Literal['active','demo'],payload:NewSession):
        with store.connect() as c:
            _plus_person=c.execute('SELECT id FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone()
            if not _plus_person:raise HTTPException(404,'participant_not_found')
            existing=c.execute('SELECT * FROM nc_sessions WHERE id=? AND participant_id=? AND mode=?',(str(payload.id),str(pid),mode)).fetchone()
            if existing:
                # Native create checks exact retry body and current preparation on subsequent starts.
                cid=existing['checkin_id']
            else:
                proposal=daily_plan(c,pid,mode)
                if not proposal['executable'] or proposal['battery']!=payload.battery:raise HTTPException(409,proposal['reason'] or 'daily_plan_changed')
                cid=proposal['checkin_id']
        payload=payload.model_copy(update={'daily_followup':True})
        return create(UUID(cid),mode,payload)
    return r
