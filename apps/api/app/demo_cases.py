"""All cases are fictional. Not medical triage advice and not validated as a clinical decision rule."""
CASES=[
 {'id':'stable','title':'Stable observations','acute':False,'functional':False,'comparable':True,'sessions':4,'risks':False,'summary':'Repeated synthetic observations appear relatively consistent.'},
 {'id':'fatigue','title':'Temporary fluctuation','acute':False,'functional':False,'comparable':False,'sessions':3,'risks':False,'summary':'Poor sleep and interruptions reduce comparability.'},
 {'id':'functional','title':'New daily-function concerns','acute':False,'functional':True,'comparable':True,'sessions':4,'risks':False,'summary':'A caregiver reports emerging difficulties with appointments and familiar tasks.'},
 {'id':'vascular','title':'Prevention context','acute':False,'functional':False,'comparable':True,'sessions':4,'risks':True,'summary':'Cognitive measurements are broadly stable; hypertension is reported.'},
 {'id':'device','title':'Device change','acute':False,'functional':False,'comparable':False,'sessions':5,'risks':False,'summary':'Input device and task language changed between visits.'},
 {'id':'acute','title':'Sudden neurological symptoms','acute':True,'functional':False,'comparable':True,'sessions':4,'risks':False,'summary':'Fictional sudden confusion or stroke warning symptoms; emergency guidance takes precedence.'},
 {'id':'sparse','title':'Insufficient baseline','acute':False,'functional':False,'comparable':True,'sessions':1,'risks':False,'summary':'Only one observation exists.'},
]


def interpret_case(case:dict) -> dict:
    if case['acute']:
        status='urgent_guidance'; reason='Acute symptoms override any reassuring device or cognitive measurements.'
    elif case['functional']:
        status='clinical_review'; reason='New functional concerns warrant a professional assessment independent of a score.'
    elif not case['comparable']:
        status='insufficient_evidence'; reason='The observations cannot be fairly compared.'
    elif case['sessions']<2:
        status='baseline_incomplete'; reason='One observation does not establish a longitudinal baseline.'
    elif case['risks']:
        status='prevention_context'; reason='Relevant risk factors do not themselves establish cognitive impairment.'
    else:
        status='descriptive_monitoring'; reason='The available fictional observations allow descriptive reporting only.'
    return {'case_id':case['id'],'status':status,'reason':reason,'research_only':True,'medical_diagnosis':None,
            'disclaimer':'Synthetic demonstration of safety and evidence principles, not a validated medical triage system.'}
