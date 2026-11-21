"""Bounded authenticated EEG display/feature contract; no live acquisition claim."""
import math
from datetime import datetime,timezone
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,model_validator
from typing import Literal
class Spectrum(BaseModel):
    model_config=ConfigDict(extra='forbid')
    frequencies:list[float]=Field(min_length=2,max_length=1025)
    density_uv2_hz:list[float]=Field(min_length=2,max_length=1025)
    @model_validator(mode='after')
    def valid(self):
        if len(self.frequencies)!=len(self.density_uv2_hz):raise ValueError('spectrum length mismatch')
        if any(not math.isfinite(x) or x<0 for x in self.frequencies+self.density_uv2_hz):raise ValueError('invalid spectrum')
        if any(b<=a for a,b in zip(self.frequencies,self.frequencies[1:])):raise ValueError('frequency bins not increasing')
        return self
class Features(BaseModel):
    model_config=ConfigDict(extra='forbid')
    delta_power:float=Field(ge=0,allow_inf_nan=False)
    theta_power:float=Field(ge=0,allow_inf_nan=False)
    alpha_power:float=Field(ge=0,allow_inf_nan=False)
    beta_power:float=Field(ge=0,allow_inf_nan=False)
    peak_alpha_frequency:float|None=Field(default=None,ge=8,le=13,allow_inf_nan=False)
    spectral_entropy:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
class NeuralRecord(BaseModel):
    model_config=ConfigDict(extra='forbid')
    record_id:str=Field(pattern=r'^[A-Za-z0-9_.:-]{1,100}$')
    source_subject:str=Field(min_length=1,max_length=100)
    revision:int=Field(ge=1)
    observed_at:AwareDatetime
    source_kind:Literal['recorded_research_eeg','recorded_participant_eeg','live_device_segment']
    synthetic:Literal[False]=False
    identity_verified:Literal[True]
    consent_confirmed:Literal[True]
    protocol:str=Field(min_length=1,max_length=100)
    provenance:str=Field(min_length=10,max_length=500)
    pipeline:str=Field(min_length=1,max_length=100)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    source_files_sha256:dict[str,str]=Field(default_factory=dict,max_length=32)
    channels:list[str]=Field(min_length=1,max_length=16)
    processing_sampling_hz:float|None=Field(default=None,ge=32,le=8192,allow_inf_nan=False)
    sampling_hz:float=Field(ge=32,le=512,allow_inf_nan=False)
    signal_uv:list[list[float]]=Field(min_length=1,max_length=16)
    features:Features
    spectrum:Spectrum|None=None
    covariance_uv2:list[list[float]]|None=None
    quality:Literal['usable','review','invalid']
    quality_flags:list[str]=Field(default_factory=list,max_length=30)
    usable_windows:int=Field(ge=0)
    total_windows:int=Field(ge=1)
    @model_validator(mode='after')
    def valid(self):
        if any(len(k)>160 or '/' in k or '\\' in k or not __import__('re').fullmatch('[a-f0-9]{64}',v) for k,v in self.source_files_sha256.items()):raise ValueError('invalid source file hashes')
        if self.observed_at>datetime.now(timezone.utc):raise ValueError('future recording')
        self.observed_at=self.observed_at.astimezone(timezone.utc)
        if len(set(self.channels))!=len(self.channels) or any(not 1<=len(c)<=30 for c in self.channels):raise ValueError('invalid channels')
        if len(self.signal_uv)!=len(self.channels):raise ValueError('channel count mismatch')
        n=len(self.signal_uv[0]);count=len(self.channels)
        if not 2<=n<=30720 or n*count>100000 or any(len(row)!=n for row in self.signal_uv):raise ValueError('signal bounds/length mismatch')
        if any(not math.isfinite(x) or abs(x)>100000 for row in self.signal_uv for x in row):raise ValueError('invalid signal amplitude')
        if self.usable_windows>self.total_windows or (self.quality=='usable' and self.usable_windows==0):raise ValueError('invalid quality windows')
        if self.quality=='usable' and (self.quality_flags or self.usable_windows!=self.total_windows):raise ValueError('usable quality contradicts window QC')
        if self.spectrum and self.spectrum.frequencies[-1]>(self.processing_sampling_hz or self.sampling_hz)/2:raise ValueError('spectrum exceeds processing Nyquist')
        if self.covariance_uv2 is not None:
            c=self.covariance_uv2
            if len(c)!=count or any(len(row)!=count for row in c):raise ValueError('covariance channel mismatch')
            if any(not math.isfinite(x) for row in c for x in row) or any(c[i][i]<0 for i in range(count)):raise ValueError('invalid covariance')
            if any(abs(c[i][j]-c[j][i])>1e-6*max(1,abs(c[i][j])) for i in range(count) for j in range(count)):raise ValueError('asymmetric covariance')
            # Small-channel PSD check without adding NumPy to the web environment.
            tolerance=1e-6*max(1,max(c[i][i] for i in range(count)));factor=[[0.]*count for _ in range(count)]
            for i in range(count):
                for j in range(i+1):
                    residual=c[i][j]-sum(factor[i][k]*factor[j][k] for k in range(j))
                    if i==j:
                        if residual < -tolerance:raise ValueError('covariance is not positive semidefinite')
                        factor[i][j]=math.sqrt(max(0,residual))
                    elif factor[j][j]>math.sqrt(tolerance)*1e-3:factor[i][j]=residual/factor[j][j]
                    elif abs(residual)>tolerance:raise ValueError('inconsistent zero-variance covariance')
        return self
