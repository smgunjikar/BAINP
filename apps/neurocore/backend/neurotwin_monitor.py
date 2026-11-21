"""NeuroCore source-update monitoring. Model training and approval remain separate."""
import json
from datetime import datetime,timezone

def record_refresh(store,pid,mode,revision,states):
    with store.connect(True) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS nt_refresh_events(
          participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,
          revision TEXT,recorded_at TEXT,states TEXT,PRIMARY KEY(participant_id,mode,revision))''')
        c.execute('INSERT OR IGNORE INTO nt_refresh_events VALUES(?,?,?,?,?)',(pid,mode,revision,datetime.now(timezone.utc).isoformat(),json.dumps(states,sort_keys=True)))
        c.execute('''DELETE FROM nt_refresh_events WHERE participant_id=? AND mode=? AND revision NOT IN
          (SELECT revision FROM nt_refresh_events WHERE participant_id=? AND mode=? ORDER BY recorded_at DESC LIMIT 100)''',(pid,mode,pid,mode))
        return [dict(r) for r in c.execute('SELECT revision,recorded_at FROM nt_refresh_events WHERE participant_id=? AND mode=? ORDER BY recorded_at DESC LIMIT 10',(pid,mode))]

def governance(states,history):
    failed=[s for s,v in states.items() if v['state']=='error']
    return dict(status='SOURCE_REVIEW_NEEDED' if failed else 'MONITORING_SOURCES',failed_sources=failed,
        updates=history,training='OFFLINE_ONLY',deployment='INDEPENDENT_REVIEW_REQUIRED',
        capabilities=[
          ['Source monitoring','Source status, provenance hashes and update history are checked.'],
          ['Recovery','A later refresh retries failed sources. Missing measurements are never generated as repair.'],
          ['Adaptation','Supported modalities and visit schedules are handled; incompatible conditions stay separate.'],
          ['Offline improvement','The candidate-training script evaluates a fixed logistic baseline. It does not deploy it.'],
          ['Input shift checks','A reviewed forecasting model can reject inputs outside its training range or cohort scope. Population drift evaluation needs a monitored cohort.'],
          ['Calibration','Calibration curves and Brier/log-loss are reported offline; model review remains required.'],
          ['Human oversight','No web route can approve a model or rewrite NeuroGuard policy.']])
