"""Authenticated evidence review and an independent, non-persistent urgent-sign route."""

from datetime import datetime, timezone
import sys
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from bainp_guard import URGENT_SOURCES, check_claim, urgent
from bainp_graph import build
from bainp_ng_llm import demo_plan, model_name

Mode = Literal["active", "demo"]
Claim = Literal["measurement", "comparison", "context", "association", "guidance", "hypothesis",
                "uncertainty", "diagnosis", "causal_effect", "treatment", "clinical_prediction"]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    revision: str = Field(pattern="^[0-9a-f]{64}$")
    claim: Claim
    evidence_id: str | None = Field(None, max_length=80)
    value: float | None = None
    unit: str | None = Field(None, max_length=32)


class Signs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signs: list[Literal["face", "limb", "speech", "vision", "balance", "headache"]] = Field(max_length=6)


class ReviewedExport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str = Field(pattern="^[0-9a-f]{64}$")


def example_snapshot():
    # Purpose-built fictional case shared by the benchmark and interface.
    return dict(
        records=[dict(id="fictional-bp", scope="context", label="Systolic blood pressure", numeric_eligible=True,
                      payload=dict(kind="measurement", revision=1, qualifier="exact", value=132, unit="mmHg",
                                   quality="usable", observed_at="2025-01-02T10:00:00+00:00")),
                 dict(id="fictional-history", scope="context", label="Reported sleep difficulty",
                      payload=dict(kind="condition", revision=1, quality="usable",
                                   observed_at="2025-01-02T10:00:00+00:00"))],
        series=[], cognitive_points=[
            dict(task="C03", metric="correct", status="completed", flags=[], condition_group="fictional-comparable",
                 value=value, session_id=f"fictional-session-{day}", at=f"2025-01-0{day}T11:00:00+00:00")
            for day, value in [(2, 18), (3, 15)]
        ],
        alignments=[dict(known_before_session=[{"label": "Sleep duration"}])],
    )


def make_router(store, authenticated, cognitive_analytics=None):
    router = APIRouter(prefix="/api/neuro-evidence")

    def audit(action, mode, person):
        if person is not None:
            with store.connect(True) as connection:
                connection.execute(
                    "INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)",
                    (action, str(person), mode, datetime.now(timezone.utc).isoformat()),
                )

    def current(mode, person):
        if person is None:
            if mode != "demo":
                raise HTTPException(422, "select_participant_or_demo")
            return build(example_snapshot(), synthetic=True)
        with store.connect() as connection:
            if not connection.execute("SELECT 1 FROM participants WHERE id=? AND mode=?", (str(person), mode)).fetchone():
                raise HTTPException(404, "participant_not_found")
        if "bb_provider" not in sys.modules:
            return build()
        from bb_provider import read_context
        try:
            data = read_context(store, person, mode, include_sensitive=False, cognition_analytics=cognitive_analytics)
        except LookupError:
            raise HTTPException(404, "participant_not_found") from None
        if "bb_connections" in sys.modules:
            from bb_connections import source_inventory
            data["connections"] = source_inventory(store, data)
        return build(data)

    @router.get("/report", dependencies=[Depends(authenticated)])
    def report(mode: Mode, person: UUID | None = None):
        return current(mode, person) | {"demo_model_configured": bool(model_name())}

    @router.post("/evaluate", dependencies=[Depends(authenticated)])
    def evaluate(payload: Proposal, mode: Mode, person: UUID | None = None):
        data = current(mode, person)
        if payload.revision != data["revision"]:
            audit("neuroguard_stale_proposal", mode, person)
            raise HTTPException(409, "evidence_changed_refresh_report")
        nodes = {item["id"]: item for item in data["nodes"]}
        result = check_claim(payload.claim, payload.evidence_id, nodes, payload.value, payload.unit)
        audit("neuroguard_"+result["state"], mode, person)
        return result

    @router.post("/demo/model-plan", dependencies=[Depends(authenticated)])
    def model_plan():
        return demo_plan(current("demo", None)["claims"])

    @router.post("/export", dependencies=[Depends(authenticated)])
    def export(payload: ReviewedExport, mode: Mode, person: UUID | None = None):
        data = current(mode, person)
        if payload.revision != data["revision"]:
            audit("neuroguard_stale_export", mode, person)
            raise HTTPException(409, "evidence_changed_refresh_report")
        sources = {edge["source"] for edge in data["edges"]}
        audit("neuroguard_reviewed_export", mode, person)
        return data | {
            "nodes": [item for item in data["nodes"] if item["id"] in sources],
            "claims": [item for item in data["claims"] if item["state"] == "accept"],
            "export_scope": "Accepted statements and their source evidence",
        }

    @router.post("/urgent")
    def urgent_signs(payload: Signs):
        return urgent(payload.signs) | {"sources": URGENT_SOURCES}

    return router
