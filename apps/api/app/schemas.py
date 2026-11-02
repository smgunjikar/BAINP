from typing import Literal
from pydantic import BaseModel, Field, model_validator

class TaskTrialInput(BaseModel):
    index: int = Field(ge=0,le=7)
    stimulus: Literal['A','B','C']
    pressed: bool
    response_ms: float | None = Field(default=None,ge=0,le=30000)

class AttentionSubmission(BaseModel):
    participant_id: Literal['demo-001'] = 'demo-001'
    language: Literal['en'] = 'en'
    device: Literal['browser'] = 'browser'
    trials: list[TaskTrialInput] = Field(min_length=8,max_length=8)
    @model_validator(mode='after')
    def unique_indexes(self):
        if sorted(t.index for t in self.trials) != list(range(8)):
            raise ValueError('Exactly one trial for each index 0..7 is required')
        return self

class CareUpdate(BaseModel):
    status: Literal['not_started','review_pending','reviewed','follow_up_planned','closed_demo']
