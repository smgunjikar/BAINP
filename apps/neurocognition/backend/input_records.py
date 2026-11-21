"""Input audit types and human-review display support; never rewrites raw answers."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
class InputEvent(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    kind:Literal['accepted','duplicate','late','key_repeat','draft_changed','paste','submitted','timeout','interrupted','cell_selected','tap','composition_start','composition_end','focus_loss']
    at_ms:float=Field(ge=0,le=7200000,allow_inf_nan=False)
    input:Literal['keyboard','mouse','touch','pen','assistive','unknown']
    action:str=Field(default='',max_length=60)
class CaptureFields(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    capture_version:Literal['input-v2']|None=None
    response_events:list[InputEvent]=Field(default_factory=list,max_length=1000)
    draft_response:str|None=Field(default=None,max_length=200)
    termination:Literal['answered','timeout','interrupted','exposure_end','deadline_commit']|None=None
CAPTURE_FIELDS=['capture_version','response_events','draft_response','termination']
SCHEMA='''CREATE TABLE IF NOT EXISTS nc_input_checkpoints (
 attempt_id TEXT PRIMARY KEY REFERENCES nc_attempts(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL,payload TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nc_response_reviews (
 id TEXT PRIMARY KEY,attempt_id TEXT NOT NULL REFERENCES nc_attempts(id) ON DELETE CASCADE,
 item_index INTEGER NOT NULL,decision TEXT NOT NULL,note TEXT NOT NULL,
 revision INTEGER NOT NULL,recorded_at TEXT NOT NULL,
 UNIQUE(attempt_id,item_index,revision));'''
def review_summary(submitted,summary,reviews):
    rows=submitted.get('extra_trials',[]);latest={r['item_index']:r for r in reviews}
    auto={r['index']:r for r in summary.get('items',[])}
    result=dict(accepted=0,incorrect=0,uncertain=0,pending_review=0,no_submitted_answer=0,unsubmitted_drafts=0)
    for item in rows:
        i=item['index'];value=item.get('response');r=latest.get(i)
        if value is None:
            result['no_submitted_answer']+=1
            if item.get('draft_response'):result['unsubmitted_drafts']+=1
        elif r:result[{'accepted':'accepted','incorrect':'incorrect','uncertain':'uncertain'}[r['decision']]]+=1
        elif auto.get(i,{}).get('exact_lexicon_match'):result['accepted']+=1
        elif auto.get(i,{}).get('recognized_other_item'):result['incorrect']+=1
        else:result['pending_review']+=1
    return result
