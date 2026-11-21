"""Deterministic adult screening scoring. Scores support review, not diagnosis.

ASRS source: Harvard NCS, scoring update 28 February 2024.
PHQ/GAD severity conventions require the official full instrument administration.
This module does not contain or license questionnaire wording.
"""
from dataclasses import dataclass
@dataclass(frozen=True)
class Instrument:
    count:int
    maximum:int
    bands:tuple
REGISTRY={
 'PHQ9':Instrument(9,3,((5,'mild'),(10,'moderate'),(15,'moderately_severe'),(20,'severe'))),
 'GAD7':Instrument(7,3,((5,'mild'),(10,'moderate'),(15,'severe'))),
 'ASRS6_2024':Instrument(6,4,((10,'high_negative'),(14,'low_positive'),(18,'high_positive'))),
}
def score(instrument,answers,age):
 if instrument not in REGISTRY:raise ValueError('Unsupported instrument')
 if type(age) is not int or age<18:raise ValueError('Adult pathway requires age 18 or older')
 rule=REGISTRY[instrument]
 if not isinstance(answers,list) or len(answers)!=rule.count:raise ValueError('Complete ordered responses required')
 if any(type(x) is not int or x<0 or x>rule.maximum for x in answers):raise ValueError('Invalid response; missing is not zero')
 total=sum(answers);band='low_negative' if instrument=='ASRS6_2024' else 'minimal'
 for threshold,label in rule.bands:
  if total>=threshold:band=label
 return dict(instrument=instrument,total=total,band=band,clinical_diagnosis=False,
   immediate_human_safety_review=instrument=='PHQ9' and answers[8]>0,
   version='nc-screening-scoring-1',limitation='Requires exact official instrument, response timeframe, language and complete administration; not a diagnosis.')
def daily_plan(*,eligible_tasks,completed_today,burden_limit,guard_permitted):
 """Select only from upstream-authorized tasks; no new execution permission."""
 if not guard_permitted:return dict(tasks=[],reason='CURRENT_SAFETY_PERMISSION_REQUIRED')
 if type(burden_limit) is not int or not 0<=burden_limit<=12:raise ValueError('Invalid burden limit')
 if not isinstance(eligible_tasks,list) or any(t not in {'C01','C02','C03','C04','C05','C06','C07','C08','C09','C10','C11','C12'} for t in eligible_tasks):raise ValueError('Unknown eligible task')
 # Memory pair must be orchestrated by its full protocol, never isolated here.
 tasks=[t for t in dict.fromkeys(eligible_tasks) if t not in completed_today and t not in ('C01','C02')][:burden_limit]
 return dict(tasks=tasks,reason='PROPOSED_FROM_AUTHORIZED_SET',execution_requires_reauthorization=True)
