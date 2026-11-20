"""Seeded v1.2 assignments: variable items, fixed versioned task parameters.

No online learning, ability estimation, changing difficulty, or daily score tuning.
C01/C02 share a reserved memory sample. C05 uses a disjoint visual family.
"""
import hashlib,json,random
from extended import definition as extended_definition,OBJECTS
VERSION='ncx-research-v1.3.0'
POLICY='seeded-item-bank-v2'
NAMING_BANK=['cup','book','key','tree','fish','house','ball','umbrella','clock','car','bottle','flower']
ADDITIONAL={
 'ball':{'en':['ball'],'ar':['كرة']},'umbrella':{'en':['umbrella'],'ar':['مظلة','شمسية']},
 'clock':{'en':['clock'],'ar':['ساعة']},'car':{'en':['car','automobile'],'ar':['سيارة']},
 'bottle':{'en':['bottle'],'ar':['زجاجة','قارورة']},'flower':{'en':['flower'],'ar':['زهرة','وردة']},
 'sun':{'en':['sun'],'ar':['شمس']}}
OBJECTS.update(ADDITIONAL)
def shuffled_bounded(rng,items,max_run=4):
    for _ in range(1024):
        result=list(items);rng.shuffle(result);run=0;last=object();ok=True
        for x in result:
            run=run+1 if x==last else 1;last=x
            if run>max_run:ok=False;break
        if ok:return result
    raise RuntimeError('Unable to assign bounded trial sequence')
def memory(seed,form):
    ids=[f'M2{form}-{i}' for i in range(48)];random.Random(seed+'memory-reservation').shuffle(ids)
    return ids[:6],ids[6:12],ids[12:18]
def generate(seed,form,task,practice):
    rng=random.Random(seed+task+'items-v2');trials=[]
    def add(kind,**kw):trials.append(dict(index=len(trials),stimulus_id=f'{task}-{len(trials):02d}',kind=kind,**kw))
    if task in ['C01','C02']:
        old,immediate,delayed=memory(seed,form)
        if task=='C01':
            for item in old:add('study',pattern=item,limit_ms=2500,expected=None)
        probes=[(p,'old') for p in old]+[(p,'new') for p in (immediate if task=='C01' else delayed)];rng.shuffle(probes)
        for p,answer in probes:add('recognition',pattern=p,limit_ms=5000,expected=answer)
    elif task=='C03':
        for target in shuffled_bounded(rng,[True]*28+[False]*12,4):add('attention',target=target,limit_ms=1200,expected='go' if target else None)
    elif task=='C04':
        transitions=shuffled_bounded(rng,[True]*12+[False]*11,3);sides=shuffled_bounded(rng,['left']*12+['right']*12,4);rule=rng.choice(['shape','fill'])
        for i,side in enumerate(sides):
            if i and transitions[i-1]:rule='shape' if rule=='fill' else 'fill'
            shape=rng.randrange(2);fill=rng.randrange(2);left=side=='left'
            target_shape=shape if (left if rule=='shape' else not left) else 1-shape
            target_fill=fill if (left if rule=='fill' else not left) else 1-fill
            add('switch',rule=rule,target_shape=target_shape,target_fill=target_fill,left_shape=shape,left_fill=fill,limit_ms=4000,expected=side,rule_switched=None if i==0 else transitions[i-1])
    elif task=='C05':
        items=[];same_ids=rng.sample(range(1,49),12)
        for x in same_ids:items.append((x,x,0))
        used=set()
        for distance in [1]*6+[2]*6:
            candidates=[(a,b) for a in range(1,49) for b in range(a+1,49) if (a^b).bit_count()==distance and (a,b) not in used]
            a,b=rng.choice(candidates);used.add((a,b))
            if rng.choice([True,False]):a,b=b,a
            items.append((a,b,distance))
        rng.shuffle(items)
        for a,b,distance in items:add('match',a=f'S2{form}-{a}',b=f'S2{form}-{b}',limit_ms=3000,expected='same' if a==b else 'different',distractor_bit_distance=distance)
    elif task in ['C07','C08','C09','C10','C11','C12']:
        d=extended_definition(task,seed,form)
        if task=='C07':rng.shuffle(d['trials'])
        elif task=='C08':
            angles=[0,90,180,270]*3;rng.shuffle(angles);sides=['left']*6+['right']*6;rng.shuffle(sides)
            from extended import rotate
            for e,angle,side in zip(d['trials'],angles,sides):
                transformed=rotate(e['target'],angle);foil=sorted(rng.sample(range(9),3))
                while foil==transformed:foil=sorted(rng.sample(range(9),3))
                e.update(rotation=angle,left=transformed if side=='left' else foil,right=foil if side=='left' else transformed,expected=side)
        elif task=='C09':
            d['trials']=[dict(kind='naming',object=obj,limit_ms=20000) for obj in rng.sample(NAMING_BANK,6)]
            d['practice']=[dict(index=0,stimulus_id='practice-C09-00',kind='naming',object='sun',limit_ms=20000)]
        elif task=='C10':
            categories=shuffled_bounded(rng,['animal']*6+['fruit']*6,3)
            for i,(e,category) in enumerate(zip(d['trials'],categories)):e.update(category=category,category_switched=None if i==0 else category!=categories[i-1])
        for i,e in enumerate(d['trials']):e.update(index=i,stimulus_id=f'{task}-{i:02d}')
        d.update(protocol=VERSION,form=form)
        return fingerprint(d)
    d=dict(task=task,trials=trials,protocol=VERSION,form=form,inter_trial_ms=300 if task=='C03' else 150,practice_required=task in ['C01','C02','C03','C04','C05'],practice=practice,stimulus_renderer='original-pattern-svg-v2')
    if task=='C06':
        order=['schedule','activities','instructions','routines','concerns'];rng.shuffle(order);d['report_item_order']=order
    return fingerprint(d)
def fingerprint(d):
    d['assignment_policy']=POLICY
    d['assignment_fingerprint']=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return d
