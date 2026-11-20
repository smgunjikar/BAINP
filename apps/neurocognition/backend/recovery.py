"""Explicit native task recovery. Original attempts and check-ins are immutable."""
import json,sys
from fastapi import HTTPException
SCHEMA='''CREATE TABLE IF NOT EXISTS nc_recoveries (
 id TEXT PRIMARY KEY,
 participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,
 workflow_id TEXT NOT NULL REFERENCES ncw_sessions(id) ON DELETE CASCADE,
 checkin_id TEXT NOT NULL UNIQUE REFERENCES checkins(id) ON DELETE CASCADE,
 payload TEXT NOT NULL,created_at TEXT NOT NULL);'''

def ticket(c,cid,mode):
 row=c.execute('SELECT * FROM nc_recoveries WHERE checkin_id=? AND mode=?',(str(cid),mode)).fetchone()
 return dict(row)|{'details':json.loads(row['payload'])} if row else None

def authorization(c,t,allow_prelaunch=False):
 """Revalidate recovery scope at native preparation, start and result boundaries."""
 pid=t['participant_id'];mode=t['mode']
 auth=c.execute('SELECT * FROM ncw_consents WHERE participant_id=? AND mode=?',(pid,mode)).fetchone()
 if not auth or not all(auth[k] for k in ('enabled','history_allowed','assessment_allowed')):
  return ['RECOVERY_CONSENT_REQUIRED']
 s=c.execute('SELECT * FROM ncw_sessions WHERE id=? AND participant_id=? AND mode=?',(t['workflow_id'],pid,mode)).fetchone()
 if not s or s['checkin_id']!=t['checkin_id']:return ['RECOVERY_WORKFLOW_MISMATCH']
 body=json.loads(s['payload'])
 if s['state'] not in (('AUTHORIZED','VALIDATING','AWAITING_ACTION','ASSESSING') if allow_prelaunch else ('ASSESSING',)):
  return ['RECOVERY_WORKFLOW_NOT_ASSESSING']
 if (body.get('safety') or {}).get('state')=='escalate':return ['RECOVERY_SAFETY_RESTRICTION']
 guard=sys.modules.get('bainp_continuum_guard')
 if not guard or not callable(getattr(guard,'evaluate',None)):return ['RECOVERY_GUARD_UNAVAILABLE']
 result=guard.evaluate(dict(participant_id=pid,source_participant_id=pid,mode=mode,source_mode=mode,
  checkin_id=t['checkin_id'],monitoring_consent=True,assessment_consent=True,native_guard_available=bool(sys.modules.get('bainp_guard')),access_reasons=[]))
 if result.get('state')!='workflow_permitted' or 'existing_neurocognition' not in result.get('allowed_actions',[]):return ['RECOVERY_GUARD_HOLD']
 return []
