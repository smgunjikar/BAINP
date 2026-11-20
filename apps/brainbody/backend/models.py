"""Strict participant-linked context contracts. No raw VCF/genotype interpretation."""
import math
from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,model_validator
from bb_dictionary import METRICS,REPORTS,SCOPES
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Source(Strict):
    kind:Literal['self_report','clinician_entry','lab_report','research_lab','professional_report','device']
    organization:str=Field(min_length=1,max_length=120)
    record_reference:str=Field(min_length=1,max_length=160)
    device_id:str|None=Field(default=None,max_length=100)
    cohort:str|None=Field(default=None,max_length=100)
    source_subject:str|None=Field(default=None,max_length=100)
    @model_validator(mode='after')
    def valid(self):
        if bool(self.cohort)!=bool(self.source_subject):raise ValueError('cohort and source_subject must be supplied together')
        if self.kind=='device' and not self.device_id:raise ValueError('device identifier required')
        return self
class Assay(Strict):
    name:str=Field(min_length=1,max_length=160)
    version:str=Field(min_length=1,max_length=80)
    laboratory:str=Field(min_length=1,max_length=160)
    specimen:Literal['serum','plasma','csf','whole_blood','urine','saliva','interstitial_fluid','other']
    method:str=Field(min_length=1,max_length=160)
    lower_quantitation_limit:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    upper_quantitation_limit:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    @model_validator(mode='after')
    def valid(self):
        if self.lower_quantitation_limit is not None and self.upper_quantitation_limit is not None and self.lower_quantitation_limit>self.upper_quantitation_limit:raise ValueError('inverted quantitation limits')
        return self
class Reference(Strict):
    kind:Literal['reference_interval','decision_limit']
    lower:float|None=Field(default=None,allow_inf_nan=False)
    upper:float|None=Field(default=None,allow_inf_nan=False)
    unit:str=Field(min_length=1,max_length=40)
    source:str=Field(min_length=5,max_length=250)
    population_context:str=Field(min_length=5,max_length=250)
    applies_to_participant:Literal['yes','no','unknown']
    @model_validator(mode='after')
    def valid(self):
        if self.lower is None and self.upper is None:raise ValueError('one interval boundary required')
        if self.lower is not None and self.upper is not None and self.lower>self.upper:raise ValueError('inverted reference interval')
        return self
class Instrument(Strict):
    name:str=Field(min_length=1,max_length=100)
    version:str=Field(min_length=1,max_length=100)
    language:str=Field(min_length=2,max_length=50)
    permission_basis:str=Field(min_length=10,max_length=300)
    administered_by:str=Field(min_length=1,max_length=100)
class Record(Strict):
    revision:int=Field(ge=1)
    kind:Literal['measurement','condition','medication','sleep_report','lifestyle_report','family_history','professional_genomic_finding','wellbeing_report']
    observed_at:AwareDatetime
    available_at:AwareDatetime
    source:Source
    identity_verified:Literal[True]
    metric:str|None=Field(default=None,max_length=80)
    value:float|None=Field(default=None,allow_inf_nan=False)
    unit:str|None=Field(default=None,max_length=40)
    qualifier:Literal['exact','less_than','greater_than','not_detected','not_reported']='exact'
    absent_reason:str|None=Field(default=None,max_length=250)
    quality:Literal['usable','review','invalid']
    context:str=Field(min_length=5,max_length=500)
    assay:Assay|None=None
    reference:Reference|None=None
    instrument:Instrument|None=None
    measurement_context_key:str|None=Field(default=None,min_length=3,max_length=160)
    encounter_id:str|None=Field(default=None,max_length=100)
    effective_start:AwareDatetime|None=None
    effective_end:AwareDatetime|None=None
    summary:str|None=Field(default=None,max_length=800)
    relative_degree:Literal['first','second','unknown']|None=None
    professional_interpretation_reference:str|None=Field(default=None,max_length=250)
    disclosure_authorized:bool=False
    needs_review:bool=False
    @model_validator(mode='after')
    def valid(self):
        now=datetime.now(timezone.utc)
        if self.observed_at>now or self.available_at>now:raise ValueError('future observations/results are not available evidence')
        if self.available_at<self.observed_at:raise ValueError('result cannot precede the observation/collection time')
        self.observed_at=self.observed_at.astimezone(timezone.utc);self.available_at=self.available_at.astimezone(timezone.utc)
        if self.effective_start:self.effective_start=self.effective_start.astimezone(timezone.utc)
        if self.effective_end:self.effective_end=self.effective_end.astimezone(timezone.utc)
        if self.effective_start and self.effective_start>self.observed_at:raise ValueError('future effective start is not an observed history event')
        if self.effective_end and (not self.effective_start or self.effective_end<self.effective_start):raise ValueError('invalid effective interval')
        if self.kind=='measurement':
            if self.metric not in METRICS:raise ValueError('unsupported metric')
            d=METRICS[self.metric]
            if self.unit not in d['units']:raise ValueError('metric/unit mismatch; units are not silently converted')
            if self.source.kind not in d['origins']:raise ValueError('unsupported source for this metric')
            if self.qualifier in ('exact','less_than','greater_than') and self.value is None:raise ValueError('numeric value/bound required')
            if self.qualifier in ('not_detected','not_reported') and (self.value is not None or not self.absent_reason):raise ValueError('nonquantitative result requires an absent reason and no numeric value')
            if self.value is not None and self.value<0:raise ValueError('negative value not supported for this metric')
            if self.reference and self.reference.unit!=self.unit:raise ValueError('reference unit mismatch')
            if d['assay_required'] and not self.assay:raise ValueError('assay, method, specimen and laboratory required')
            if self.metric=='hba1c' and self.assay and self.assay.specimen!='whole_blood':raise ValueError('HbA1c requires a whole-blood/RBC-based assay context in this dictionary')
            if self.assay and self.unit=='ng/mg creatinine' and self.assay.specimen!='urine':raise ValueError('creatinine-normalized unit requires urine specimen')
            if not d['assay_required'] and self.assay:raise ValueError('assay fields are not applicable to this metric')
            if self.metric=='questionnaire_total' and not self.instrument:raise ValueError('questionnaire provenance and permission basis required')
            if self.metric!='questionnaire_total' and self.instrument:raise ValueError('instrument applies only to questionnaire totals')
            if self.summary is not None or self.relative_degree is not None:raise ValueError('report fields are not measurement values')
        else:
            if not self.summary or not self.summary.strip():raise ValueError('report summary required')
            if any(v is not None for v in (self.metric,self.value,self.unit,self.assay,self.reference,self.instrument)):raise ValueError('report must not contain numeric measurement fields')
            if self.qualifier!='exact':raise ValueError('qualifier applies to measurements only')
            if self.kind=='family_history' and self.relative_degree is None:raise ValueError('relative degree required; do not enter relative names')
            if self.kind!='family_history' and self.relative_degree is not None:raise ValueError('relative degree applies only to family history')
            if self.kind=='professional_genomic_finding' and (self.source.kind!='professional_report' or not self.professional_interpretation_reference or not self.disclosure_authorized):raise ValueError('professional interpretation and authorized disclosure required')
        return self
    def scope(self):return METRICS[self.metric]['scope'] if self.kind=='measurement' else REPORTS[self.kind]['scope']
class Consent(Strict):
    expected_revision:int=Field(ge=0)
    scopes:list[str]=Field(max_length=5)
    authorization_reference:str=Field(min_length=10,max_length=300)
    @model_validator(mode='after')
    def valid(self):
        if len(set(self.scopes))!=len(self.scopes) or not set(self.scopes)<=SCOPES:raise ValueError('invalid/duplicate consent scope')
        return self
class Review(Strict):
    include_sensitive:bool=False
    record_revision:int=Field(ge=1)
    finding_code:str=Field(min_length=1,max_length=100)
    status:Literal['pending','acknowledged','resolved']
    note:str=Field(min_length=5,max_length=500)
