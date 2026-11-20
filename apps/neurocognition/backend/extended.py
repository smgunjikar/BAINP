"""Original C07-C12 research prototypes, with explicit confound/review boundaries.
No proprietary item banks, language models, norms or diagnostic interpretation.
"""
import math,random,re,statistics,unicodedata
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from fastapi import HTTPException
from input_records import CaptureFields
TASKS=['C07','C08','C09','C10','C11','C12']
OBJECTS={
 'cup':{'en':['cup','mug'],'ar':['كوب','كاس','فنجان']},
 'book':{'en':['book'],'ar':['كتاب']},
 'key':{'en':['key'],'ar':['مفتاح']},
 'tree':{'en':['tree'],'ar':['شجرة']},
 'fish':{'en':['fish'],'ar':['سمكة','سمك']},
 'house':{'en':['house','home'],'ar':['بيت','منزل']}}
LEXICON={
'en':{'animal':'cat dog horse cow sheep goat lion tiger elephant rabbit mouse rat bird duck chicken camel fish donkey bear wolf deer monkey zebra giraffe fox pig'.split(),'fruit':'apple banana orange pear grape grapes mango peach plum lemon lime melon watermelon strawberry cherry pineapple fig date dates apricot kiwi'.split()},
'ar':{'animal':'قط قطة كلب حصان بقرة خروف ماعز اسد نمر فيل ارنب فار طائر بطة دجاجة جمل سمكة حمار دب ذئب غزال قرد حماروحشي زرافة ثعلب خنزير'.split(),'fruit':'تفاح تفاحة موز موزة برتقال برتقالة كمثرى عنب مانجو خوخ برقوق ليمون شمام بطيخ فراولة كرز اناناس تين تمر مشمش كيوي'.split()}}
def normalize(text):
    text=unicodedata.normalize('NFKC',text).casefold().strip()
    text=''.join(c for c in text if unicodedata.category(c)!='Mn').replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ـ','')
    return ' '.join(re.findall(r'\w+',text,flags=re.UNICODE))
class Presentation(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    cell:int=Field(ge=0,le=8)
    onset_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)
    duration_ms:float=Field(gt=0,le=7200000,allow_inf_nan=False)
class Observation(CaptureFields):
    model_config=ConfigDict(extra='forbid',strict=True)
    index:int=Field(ge=0,le=100)
    stimulus_id:str=Field(max_length=80)
    onset_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)
    duration_ms:float=Field(gt=0,le=7200000,allow_inf_nan=False)
    response:str|list[float]|None=None
    rt_ms:float|None=Field(default=None,ge=0,le=120000,allow_inf_nan=False)
    input:Literal['keyboard','mouse','touch','pen','assistive','unknown']|None=None
    max_frame_gap_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)
    study_duration_ms:float=Field(default=0,ge=0,le=7200000,allow_inf_nan=False)
    presentations:list[Presentation]=Field(default_factory=list,max_length=10)
    @model_validator(mode='after')
    def check(self):
        if isinstance(self.response,str) and len(self.response)>200:raise ValueError('Response too long')
        if isinstance(self.response,list) and (len(self.response)>1000 or any(not math.isfinite(x) for x in self.response)):raise ValueError('Invalid response array')
        if self.rt_ms is not None and self.rt_ms>self.duration_ms:raise ValueError('Latency exceeds duration')
        if self.response is None and (self.rt_ms is not None or self.input is not None):raise ValueError('No-response metadata mismatch')
        if self.response is not None and (self.rt_ms is None or self.input is None):raise ValueError('Response metadata required')
        return self

def definition(task,seed,form,practice=False):
    rng=random.Random(seed+task+('practice' if practice else 'outcome'));trials=[]
    def add(kind,**kw):trials.append(dict(index=len(trials),stimulus_id=f"{'practice-' if practice else ''}{task}-{len(trials):02d}",kind=kind,**kw))
    if task=='C07':
        for span in ([2] if practice else [2,3,4,5]):add('span',sequence=rng.sample(range(9),span),span=span,flash_ms=700,blank_ms=300,limit_ms=15000)
    elif task=='C08':
        for _ in range(2 if practice else 12):
            cells=sorted(rng.sample(range(9),3));rotation=rng.choice([0,90,180,270]);transformed=rotate(cells,rotation)
            foil=sorted(rng.sample(range(9),3))
            while foil==transformed:foil=sorted(rng.sample(range(9),3))
            correct=rng.choice(['left','right'])
            add('spatial',target=cells,rotation=rotation,left=transformed if correct=='left' else foil,right=foil if correct=='left' else transformed,expected=correct,limit_ms=10000)
    elif task=='C09':
        objects=list(OBJECTS);rng.shuffle(objects)
        for name in objects[:1 if practice else 6]:add('naming',object=name,limit_ms=20000)
    elif task=='C10':
        first=rng.choice(['animal','fruit'])
        for i in range(2 if practice else 12):add('category',category=first if i%2==0 else ('fruit' if first=='animal' else 'animal'),limit_ms=10000)
    elif task=='C11':
        hands=['left','right'];rng.shuffle(hands)
        for hand in hands[:1 if practice else 2]:add('tapping',hand=hand,limit_ms=3000 if practice else 10000)
    elif task=='C12':
        items=['month','year','place','condition_change'];rng.shuffle(items)
        for item in items:add('context',item=item,limit_ms=120000)
    return dict(task=task,trials=trials,practice_required=task!='C12',inter_trial_ms=300,
      stimulus_renderer='original-extended-svg-v1',practice=[] if practice or task=='C12' else definition(task,seed,form,True)['trials'])
def rotate(cells,degrees):
    output=[]
    for cell in cells:
        r,c=divmod(cell,3)
        for _ in range(degrees//90):r,c=c,2-r
        output.append(3*r+c)
    return sorted(output)
def validate(actual,expected,complete,language,practice=False):
    if len(actual)>len(expected) or complete and len(actual)!=len(expected):raise HTTPException(422,'extended_trial_count')
    end=0
    for a,e in zip(actual,expected):
        if a.index!=e['index'] or a.stimulus_id!=e['stimulus_id'] or a.onset_ms<end:raise HTTPException(422,'extended_trial_sequence')
        end=a.onset_ms+a.duration_ms
        if e['kind']=='span':
            study_end=0
            if len(a.presentations)>len(e['sequence']):raise HTTPException(422,'extra_span_presentations')
            for seen,cell in zip(a.presentations,e['sequence']):
                if seen.cell!=cell or seen.onset_ms<study_end:raise HTTPException(422,'invalid_span_presentations')
                study_end=seen.onset_ms+seen.duration_ms
            if a.study_duration_ms> a.duration_ms or study_end>a.study_duration_ms:raise HTTPException(422,'invalid_span_study_duration')
            if complete and (len(a.presentations)!=e['span'] or any(x.duration_ms<e['flash_ms'] for x in a.presentations) or a.study_duration_ms<e['span']*1000):raise HTTPException(422,'incomplete_span_presentation')
        elif a.study_duration_ms or a.presentations:raise HTTPException(422,'unexpected_study_presentations')
        if a.capture_version=='input-v2' and a.termination=='deadline_commit' and (not isinstance(a.response,str) or a.draft_response is None or a.response!=a.draft_response.strip()):raise HTTPException(422,'invalid_deadline_commit')
        if any(ev.at_ms>a.duration_ms+1 for ev in a.response_events):raise HTTPException(422,'input_event_after_trial')
        if a.response is None:
            if complete and a.duration_ms<e['limit_ms']+(a.study_duration_ms if e['kind']=='span' else 0):raise HTTPException(422,'extended_timeout_too_short')
            if practice and complete:raise HTTPException(422,'extended_practice_required')
            continue
        if a.rt_ms>e['limit_ms']+(a.study_duration_ms if e['kind']=='span' else 0):raise HTTPException(422,'extended_response_after_deadline')
        kind=e['kind']
        if kind=='span':
            if not isinstance(a.response,list) or len(a.response)>e['span'] or any(x!=int(x) or not 0<=x<9 for x in a.response):raise HTTPException(422,'invalid_spatial_sequence')
            if a.rt_ms<a.study_duration_ms:raise HTTPException(422,'response_before_sequence_finished')
            if practice and complete and a.response!=e['sequence']:raise HTTPException(422,'span_practice_not_passed')
        elif kind=='spatial':
            if a.response not in ['left','right']:raise HTTPException(422,'invalid_spatial_choice')
            if practice and complete and a.response!=e['expected']:raise HTTPException(422,'spatial_practice_not_passed')
        elif kind=='tapping':
            if not isinstance(a.response,list) or any(not 0<=x<=e['limit_ms'] for x in a.response) or any(y<=x for x,y in zip(a.response,a.response[1:])):raise HTTPException(422,'invalid_tap_times')
            if complete and a.duration_ms<e['limit_ms']:raise HTTPException(422,'tapping_window_too_short')
            if practice and complete and len(a.response)<2:raise HTTPException(422,'tapping_practice_not_passed')
        else:
            if not isinstance(a.response,str) or not a.response.strip():raise HTTPException(422,'text_response_required')
            if kind=='context' and e['item']=='condition_change' and a.response not in ['no','yes','unsure']:raise HTTPException(422,'invalid_context_response')
            # Naming/semantic validity is NOT inferred from a limited dictionary.
            # Practice confirms the operator can enter text, not clinical correctness.
    return end

def summarize(actual,expected,language,task,status):
    out=dict(trials_recorded=len(actual),clinical_score=None,measurement_method='client_performance_clock_original_research_task',quality_flags=[],units={'timing':'ms','counts':'count'},interpretation='descriptive_only_no_validated_norms')
    if status!='completed':out['quality_flags'].append('INTERRUPTED')
    focus_affected={a.index for a in actual if any(ev.kind=='focus_loss' for ev in a.response_events)}
    if focus_affected:
        out['quality_flags'].append('FOCUS_LOSS_AFFECTED_TIMING')
        out['focus_affected_trial_indices']=sorted(focus_affected)
        out['interpretation']='descriptive_quality_limited_not_diagnosis'
    if any(a.max_frame_gap_ms>100 for a in actual):out['quality_flags'].append('FRAME_GAP_OVER_100_MS')
    out['observed_inputs']=sorted({a.input for a in actual if a.input})
    out['typed_drafts_preserved']=sum(bool(a.draft_response) for a in actual)
    out['deadline_commits']=sum(a.termination=='deadline_commit' for a in actual)
    if out['deadline_commits']:out['quality_flags'].append('ANSWER_AUTOCOMMITTED_AT_DEADLINE')
    if task=='C07':
        correct=[(a,e) for a,e in zip(actual,expected) if a.response==e['sequence']]
        out.update(correct_sequences=len(correct),max_presented_span=max([e['span'] for e in expected[:len(actual)]],default=None),max_correct_span=max([e['span'] for a,e in correct],default=None),position_errors=sum(sum(x!=y for x,y in zip(a.response or [],e['sequence']))+abs(len(a.response or [])-e['span']) for a,e in zip(actual,expected)))
        out['quality_flags'].append('FIXED_SPAN_SAMPLE_NOT_ADAPTIVE_CAPACITY_ESTIMATE')
    elif task=='C08':out.update(correct=sum(a.response==e['expected'] for a,e in zip(actual,expected)),response_trials=len(actual),omissions=sum(a.response is None and a.duration_ms>=e['limit_ms'] for a,e in zip(actual,expected)))
    elif task in ['C09','C10']:
        items=[];seen=set()
        for a,e in zip(actual,expected):
            n=normalize(a.response or '');candidates=OBJECTS[e['object']][language] if task=='C09' else LEXICON[language][e['category']]
            match=n in {normalize(x) for x in candidates}
            other=any(n in {normalize(x) for x in aliases[language]} for key,aliases in OBJECTS.items() if key!=e['object']) if task=='C09' else any(n in {normalize(x) for x in words} for key,words in LEXICON[language].items() if key!=e['category'])
            repeated=bool(n and n in seen);seen.add(n)
            items.append(dict(index=a.index,raw_response=a.response,expected_item=e.get('object',e.get('category')),accepted_examples=list(candidates),normalized=n,recognized_other_item=bool(n and other and not match),exact_lexicon_match=match,repeated=repeated,review='no_response' if not n else 'exact_dictionary_match_not_clinical_verification' if match else 'different_listed_item' if other else 'human_review_required'))
        out.update(items=items,exact_lexicon_matches=sum(x['exact_lexicon_match'] for x in items),repetitions=sum(x['repeated'] for x in items),unmatched_pending_review=sum(x['review']=='human_review_required' for x in items),omissions=sum(not x['normalized'] for x in items))
        out['quality_flags']+=['TYPED_LANGUAGE_MOTOR_AND_LITERACY_CONFOUND','LIMITED_LEXICON_REQUIRES_HUMAN_REVIEW']
    elif task=='C11':
        windows=[]
        for a,e in zip(actual,expected):
            taps=a.response or [];intervals=[y-x for x,y in zip(taps,taps[1:])]
            windows.append(dict(hand=e['hand'],taps=len(taps),window_ms=a.duration_ms,rate_per_second=None if a.index in focus_affected else len(taps)/(a.duration_ms/1000),median_interval_ms=None if a.index in focus_affected else statistics.median(intervals) if intervals else None,interval_sample_sd_ms=None if a.index in focus_affected else statistics.stdev(intervals) if len(intervals)>1 else None,complete_window=a.duration_ms>=e['limit_ms'] and a.index not in focus_affected))
        out.update(windows=windows,lateral_difference=None)
        if len(windows)==2 and all(x['complete_window'] for x in windows):
            byhand={x['hand']:x for x in windows};out['lateral_difference']=dict(left_minus_right_taps_per_second=byhand['left']['rate_per_second']-byhand['right']['rate_per_second'])
        out['quality_flags'].append('INPUT_DEVICE_AND_MOTOR_OBSERVATION_NOT_COGNITIVE_SCORE')
    elif task=='C12':
        out['context']={e['item']:a.response for a,e in zip(actual,expected)}
        if out['context'].get('condition_change')!='no':out['quality_flags'].append('CONDITIONS_CHANGED_OR_UNCERTAIN')
        out['orientation_accuracy']=None;out['quality_flags'].append('CONTEXT_SELF_REPORT_NO_LOCATION_OR_TIME_NORM_SCORING')
    rts=[a.rt_ms for a in actual if a.index not in focus_affected and a.rt_ms is not None and a.response is not None]
    out['median_response_rt_ms']=statistics.median(rts) if rts else None
    return out
