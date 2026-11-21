"""Participant-linked wearable observations. Import only; no autonomous diagnosis.
Uses the existing authenticated session and SQLite transaction boundary.
"""
import json,hashlib,uuid,math
from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,model_validator
from fastapi import APIRouter,Depends,HTTPException
class Observation(BaseModel):
 model_config=ConfigDict(extra='forbid')
 source_id:str=Field(min_length=1,max_length=100)
 metric:Literal['heart_rate','sleep_duration','steps','movement_rms']
 value:float=Field(allow_inf_nan=False,ge=0)
 unit:Literal['bpm','h','count','g']
 timestamp:AwareDatetime
 device:str=Field(min_length=1,max_length=100)
 method:str=Field(min_length=1,max_length=100)
 protocol:str=Field(min_length=1,max_length=100)
 quality:Literal['usable','review','invalid']
 @model_validator(mode='after')
 def units(self):
  if self.unit!={'heart_rate':'bpm','sleep_duration':'h','steps':'count','movement_rms':'g'}[self.metric]:raise ValueError('metric/unit mismatch')
  if self.timestamp>datetime.now(timezone.utc):raise ValueError('future observation')
  return self
class Batch(BaseModel):
 model_config=ConfigDict(extra='forbid')
 consent_confirmed:Literal[True]
 observations:list[Observation]=Field(min_length=1,max_length=1000)
def make_router(store,authenticated):
 r=APIRouter(prefix='/api/neurosense',dependencies=[Depends(authenticated)])
 with store.connect(True) as c:c.execute('CREATE TABLE IF NOT EXISTS sense_observations (participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE, mode TEXT NOT NULL, source_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(participant_id,mode,source_id))')
 def check(c,p,m):
  if not c.execute('SELECT id FROM participants WHERE id=? AND mode=?',(p,m)).fetchone():raise HTTPException(404,'participant_not_found')
 @r.post('/{participant_id}/observations')
 def put(participant_id:uuid.UUID,b:Batch,mode:Literal['active','demo']):
  p=str(participant_id);added=0
  with store.connect(True) as c:
   check(c,p,mode)
   for o in b.observations:
    raw=json.dumps(o.model_dump(mode='json'),sort_keys=True)
    old=c.execute('SELECT payload FROM sense_observations WHERE participant_id=? AND mode=? AND source_id=?',(p,mode,o.source_id)).fetchone()
    if old and old['payload']!=raw:raise HTTPException(409,'source_id_conflict')
    if not old:c.execute('INSERT INTO sense_observations VALUES(?,?,?,?)',(p,mode,o.source_id,raw));added+=1
  return {'added':added,'received':len(b.observations)}
 @r.get('/{participant_id}/observations')
 def get(participant_id:uuid.UUID,mode:Literal['active','demo']):
  with store.connect() as c:
   check(c,str(participant_id),mode)
   items=[json.loads(v['payload']) for v in c.execute('SELECT payload FROM sense_observations WHERE participant_id=? AND mode=?',(str(participant_id),mode))]
  from sense_anomaly import analyze
  items.sort(key=lambda v:v['timestamp']);return {'items':items,'analysis':analyze(items),'interpretation':'descriptive observations; clinical change not established'}
 @r.delete('/{participant_id}/observations')
 def delete(participant_id:uuid.UUID,mode:Literal['active','demo']):
  with store.connect(True) as c:
   check(c,str(participant_id),mode);c.execute('DELETE FROM sense_observations WHERE participant_id=? AND mode=?',(str(participant_id),mode))
  return {'deleted':True}
 return r
