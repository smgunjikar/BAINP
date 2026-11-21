from datetime import datetime, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, field_validator

class Provenance(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    source: Literal['synthetic']
    dataset_version: Literal['bainp-synthetic-v1']
    protocol_version: Literal['synthetic-trajectory-v1']
    measurement_method: Literal['deterministic-simulation']
    device_metadata: dict[str, str] = Field(min_length=1)
    recorded_at_utc: AwareDatetime

    @field_validator('recorded_at_utc')
    @classmethod
    def require_utc(cls, value):
        if value.utcoffset() != timedelta(0):
            raise ValueError('UTC timestamp required')
        return value

class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    observation_id: str
    participant_id: str
    encounter_id: str
    metric: Literal['simulated_attention_latency', 'simulated_memory_fraction']
    value: float = Field(allow_inf_nan=False, ge=0)
    unit: Literal['ms', 'fraction']
    provenance: Provenance

    @field_validator('unit')
    @classmethod
    def check_unit(cls, value, info):
        expected = 'ms' if info.data.get('metric') == 'simulated_attention_latency' else 'fraction'
        if value != expected:
            raise ValueError('Metric/unit mismatch')
        return value

    @field_validator('value')
    @classmethod
    def check_value(cls, value, info):
        if info.data.get('metric') == 'simulated_memory_fraction' and value > 1:
            raise ValueError('Fraction must be between zero and one')
        return value
