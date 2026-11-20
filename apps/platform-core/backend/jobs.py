"""SQLite queue for the allowlisted, repeatable ARENA engineering benchmark."""
from datetime import datetime, timezone
import json
import time
from uuid import uuid4

from bainp_arena import execution_sha, protocol_sha, run

LEASE = 120
MAX_ATTEMPTS = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS platform_jobs (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL,
  lease_token TEXT, lease_until REAL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  protocol_sha256 TEXT NOT NULL, execution_sha256 TEXT NOT NULL, result_json TEXT, error_code TEXT
);
CREATE INDEX IF NOT EXISTS platform_jobs_queue ON platform_jobs(state,created_at);
CREATE TABLE IF NOT EXISTS platform_job_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES platform_jobs(id),
  action TEXT NOT NULL, at TEXT NOT NULL
);
"""


class QueueError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def log(connection,key,action,at):
    connection.execute("INSERT INTO platform_job_events(job_id,action,at) VALUES(?,?,?)",(key,action,at))


def row_view(row):
    item = {key:row[key] for key in (
        "id","kind","state","attempts","created_at","updated_at","protocol_sha256","execution_sha256","error_code")}
    item["result"] = json.loads(row["result_json"]) if row["state"] == "completed" else None
    return item


def get(connection,key):
    row = connection.execute("SELECT * FROM platform_jobs WHERE id=?",(key,)).fetchone()
    if row is None:
        raise QueueError("JOB_NOT_FOUND")
    return row


def enqueue(store,key):
    with store.connect(True) as connection:
        old = connection.execute("SELECT * FROM platform_jobs WHERE id=?",(key,)).fetchone()
        if old is not None:
            return row_view(old)
        count = connection.execute("SELECT count(*) FROM platform_jobs WHERE state IN ('queued','running')").fetchone()[0]
        if count >= 100:
            raise QueueError("QUEUE_CAPACITY")
        at = now()
        connection.execute(
            "INSERT INTO platform_jobs(id,kind,state,attempts,created_at,updated_at,protocol_sha256,execution_sha256) "
            "VALUES(?,'engineering_v1','queued',0,?,?,?,?)",(key,at,at,protocol_sha(),execution_sha()),
        )
        log(connection,key,"queued",at)
        return row_view(get(connection,key))


def cancel(store,key):
    with store.connect(True) as connection:
        row = get(connection,key)
        if row["state"] == "cancelled":
            return row_view(row)
        if row["state"] != "queued":
            raise QueueError("ONLY_QUEUED_JOBS_CAN_CANCEL")
        at = now()
        connection.execute("UPDATE platform_jobs SET state='cancelled',updated_at=? WHERE id=?",(at,key))
        log(connection,key,"cancelled",at)
        return row_view(get(connection,key))


def claim(store,key=None):
    clock, at = time.time(), now()
    with store.connect(True) as connection:
        expired = connection.execute(
            "SELECT id,attempts FROM platform_jobs WHERE state='running' AND lease_until<=?",(clock,),
        ).fetchall()
        for row in expired:
            next_state = "queued" if row["attempts"] < MAX_ATTEMPTS else "failed"
            error = "LEASE_RETRIES_EXHAUSTED" if next_state == "failed" else None
            connection.execute(
                "UPDATE platform_jobs SET state=?,error_code=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                (next_state,error,at,row["id"]),
            )
            log(connection,row["id"],"lease_recovered" if error is None else "lease_retries_exhausted",at)
        if key is None:
            selected = connection.execute(
                "SELECT id FROM platform_jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
        else:
            selected = connection.execute("SELECT id FROM platform_jobs WHERE id=? AND state='queued'",(key,)).fetchone()
        if not selected:
            return None
        job_id, token = selected["id"], str(uuid4())
        connection.execute(
            "UPDATE platform_jobs SET state='running',attempts=attempts+1,lease_token=?,lease_until=?,updated_at=? WHERE id=?",
            (token,clock+LEASE,at,job_id),
        )
        log(connection,job_id,"leased",at)
        return dict(id=job_id, token=token, execution=get(connection,job_id)["execution_sha256"])


def finish(store, lease, result=None, error=None):
    with store.connect(True) as connection:
        key, at = lease["id"], now()
        state = "failed" if error else "completed"
        written = connection.execute(
            "UPDATE platform_jobs SET state=?,updated_at=?,result_json=?,error_code=?,lease_token=NULL,lease_until=NULL "
            "WHERE id=? AND state='running' AND lease_token=? AND lease_until>?",
            (state,at,json.dumps(result,allow_nan=False) if result is not None else None,error,key,lease["token"],time.time()),
        )
        if written.rowcount != 1:
            raise QueueError("LEASE_STALE")
        log(connection,key,state,at)
        return row_view(get(connection,key))


def run_job(store,key=None):
    lease = claim(store,key)
    if lease is None:
        return None
    if lease["execution"] != execution_sha():
        return finish(store,lease,error="PROTOCOL_VERSION_CHANGED")
    try:
        report = run()
    except Exception:
        return finish(store,lease,error="BENCHMARK_EXECUTION_FAILED")
    return finish(store,lease,result=report)
