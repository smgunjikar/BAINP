"""Authenticated local operations and the independent ARENA workspace."""
from collections import Counter
from pathlib import Path
import sys
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from bainp_arena import DATASETS, VERSION, protocol_sha, research_summary
from bainp_jobs import SCHEMA, QueueError, cancel, enqueue, get, row_view, run_job

MODULES = (
    # neuroshadow_native_registry_v1
    ("NeuroShadow", "/neuroshadow", "neuroshadow/backend/engine.py"),
    # neuroquest_native_registry_v1
    ("NeuroQuest", "/neuroquest", "neuroquest/backend/engine.py"),
    # neurocontinuum_native_registry_v1
    ("NeuroContinuum", "/neurocontinuum", "neurocontinuum/backend/engine.py"),
    ("NeuroAccess", "/", "neuroaccess/backend/api.py"),
    ("NeuroCognition X", "/cognition-dashboard", "neuroaccess/backend/battery.py"),
    ("NeuroVision", "/neurovision", "neurovision/backend/router.py"),
    ("NeuroPulse", None, "neuropulse/backend/engine.py"),
    ("NeuroSense", "/sense-monitor", "neuroaccess/backend/sense_store.py"),
    ("NeuroTwin X", "/neurotwin", "neurotwin/backend/router.py"),
    ("Brain–Body", "/brain-body", "brainbody/backend/provider.py"),
    ("NeuroCore", None, "neurocore/backend/neurotwin_monitor.py"),
    ("NeuroGraph", "/neurograph", "neurograph/backend/router.py"),
    ("NeuroGuard", "/neuroguard", "neuroguard/backend/guard.py"),
    ("NeuroSim", "/neurosim", "neurosim/backend/router.py"),
    ("CareLoop", "/careloop", "careloop/backend/cases.py"),
)


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID
    kind: Literal["engineering_v1"]


def model_registry():
    guard = sys.modules.get("nt_guard")
    if guard is None or not hasattr(guard,"checked_model"):
        return {"module":"NeuroTwin X","state":"adapter_not_loaded","version":None,"reasons":[]}
    try:
        model, reasons = guard.checked_model()
        return {"module":"NeuroTwin X","state":"reviewed_research_artifact" if model else "unavailable",
                "version":str(model.get("model_version","unknown"))[:100] if model else None,
                "reasons":[reason for reason in reasons if isinstance(reason,str) and reason.isupper()][:15]}
    except Exception:
        return {"module":"NeuroTwin X","state":"unavailable","version":None,"reasons":["REGISTRY_READ_FAILED"]}


def mount(app, store, authenticated):
    with store.connect() as connection:
        connection.executescript(SCHEMA)
    router = APIRouter(prefix="/api/platform/v1",dependencies=[Depends(authenticated)])
    counts, lock, started = Counter(), Lock(), monotonic()
    timing = {"last_ms":None}

    @app.middleware("http")
    async def telemetry(request, call_next):
        start = monotonic()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            with lock:
                counts[f"{status//100}xx"] += 1
                timing["last_ms"] = round((monotonic()-start)*1000,2)

    @router.get("/status")
    def status():
        with store.connect() as connection:
            connection.execute("SELECT 1").fetchone()
            jobs = dict(connection.execute("SELECT state,count(*) FROM platform_jobs GROUP BY state").fetchall())
        with lock:
            counters = dict(counts)
            last_ms = timing["last_ms"]
        apps = Path(__file__).resolve().parents[2]
        from serve_frontend import ASSETS, ROOT
        modules = []
        for name, route, asset in MODULES:
            served = route if route in ASSETS and (ROOT/ASSETS[route][0]).is_file() else None
            modules.append({"name":name,"source_present":(apps/asset).is_file(),"local_route":served})
        return {"status":"operational","storage":"local SQLite","identity":"existing BAINP operator",
                "uptime_seconds":round(monotonic()-started,1),"requests":counters,
                "last_request_ms":last_ms,"jobs":jobs,"modules":modules,"model_registry":model_registry()}

    @router.get("/arena")
    def catalog():
        return {"protocol":VERSION,"protocol_sha256":protocol_sha(),
                "datasets":[dict(id=key,scope=scope,permission=permission) for key,scope,permission in DATASETS],
                "oasis2":research_summary(),"release_authorized":False}

    def job_error(error):
        return HTTPException(404 if str(error) == "JOB_NOT_FOUND" else 409,str(error))

    @router.get("/jobs")
    def list_jobs():
        with store.connect() as connection:
            items = connection.execute("SELECT * FROM platform_jobs ORDER BY created_at DESC,id LIMIT 30")
            return {"jobs":[row_view(row) for row in items]}

    @router.get("/jobs/{job_id}")
    def job(job_id: UUID):
        key = str(job_id)
        try:
            with store.connect() as connection:
                data = row_view(get(connection,key))
                data["events"] = [dict(row) for row in connection.execute(
                    "SELECT action,at FROM platform_job_events WHERE job_id=? ORDER BY seq",(key,))]
            return data
        except QueueError as error:
            raise job_error(error) from None

    @router.post("/jobs")
    def create(payload: JobInput):
        try:
            return enqueue(store,str(payload.job_id))
        except QueueError as error:
            raise job_error(error) from None

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: UUID):
        try:
            return cancel(store,str(job_id))
        except QueueError as error:
            raise job_error(error) from None

    @router.post("/jobs/{job_id}/run")
    def execute(job_id: UUID):
        key = str(job_id)
        try:
            with store.connect() as connection:
                get(connection,key)
            return run_job(store,key) or job(job_id)
        except QueueError as error:
            raise job_error(error) from None

    @router.post("/worker/run-next")
    def worker():
        try:
            return {"job":run_job(store)}
        except QueueError as error:
            raise job_error(error) from None

    app.include_router(router)
