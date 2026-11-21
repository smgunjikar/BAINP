"""Consent-aware prevention education and local concern tracking routes."""

from datetime import date
import sys
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from bainp_guard import urgent, URGENT_SOURCES
from bainp_cases import SCHEMA, intake, require_owner, select_case, transition, view_case
from bainp_sim import DEFAULT, compare, education, matched_context

Mode = Literal["active", "demo"]
Signs = Literal["face", "limb", "speech", "vision", "balance", "headache"]
Action = Literal["request_review", "plan_monitoring", "document_referral", "plan_followup",
                 "confirm_followup", "record_outcome", "close", "reopen", "withdraw"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class PreferenceInput(Input):
    preferences: list[Literal["mobility", "time", "access"]] = Field(default_factory=list, max_length=3)


class Scenario(Input):
    activity_minutes: float = Field(strict=True, ge=0, le=10080)
    sleep_hours: float = Field(strict=True, ge=0, le=24)
    systolic_mmhg: float = Field(strict=True, gt=0, le=400)


class CaseInput(Input):
    case_id: UUID
    category: Literal["memory", "daily_function", "sleep", "other"]
    concern: str = Field(min_length=5, max_length=1000)
    screening: Literal["none_selected", "unsure"]
    signs: list[Signs] = Field(max_length=6)
    consent: StrictBool
    share_with_twin: StrictBool = False


class EventInput(Input):
    operation_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    action: Action
    note: str | None = Field(None, min_length=5, max_length=1000)
    reference: str | None = Field(None, min_length=3, max_length=180)
    due_on: date | None = None


def make_router(store, authenticated, cognitive_analytics=None):
    with store.connect() as connection:
        connection.executescript(SCHEMA)
    router = APIRouter(prefix="/api/prevention", dependencies=[Depends(authenticated)])

    def owner(connection, mode, person):
        participant = str(person) if person else None
        require_owner(connection, mode, participant)
        return participant

    def report(mode, person, preferences):
        if mode == "demo" and person is None:
            demo_context = {key: {"Fictional example"} for key in ("bp", "activity", "sleep", "cognition")}
            return education(demo_context, preferences, synthetic=True)
        with store.connect() as connection:
            owner(connection, mode, person)
        provider = sys.modules.get("bb_provider")
        if provider is None:
            return education({}, [])
        try:
            snapshot = provider.read_context(store, person, mode, include_sensitive=False,
                                             cognition_analytics=cognitive_analytics)
        except LookupError:
            raise HTTPException(404, "participant_not_found") from None
        return education(matched_context(snapshot), preferences)

    @router.post("/education")
    def get_education(payload: PreferenceInput, mode: Mode, person: UUID | None = None):
        return report(mode, person, list(dict.fromkeys(payload.preferences)))

    @router.get("/settings")
    def settings():
        planner = sys.modules.get("bainp_ng_llm")
        return {"scenario_baseline": DEFAULT, "model_demo_configured": bool(planner and planner.model_name())}

    @router.post("/scenario")
    def scenario(payload: Scenario):
        return compare(payload.model_dump())

    @router.post("/demo/model-plan")
    def model_plan():
        demo = report("demo", None, [])
        planner = sys.modules.get("bainp_ng_llm")
        if not planner or not demo["topics"]:
            return {"state": "abstain", "reason": "NO_AVAILABLE_DEMO_TOPICS", "claims": []}
        return planner.demo_plan([
            {"id": item["id"], "type": "clinical_guidance", "state": "accept",
             "text": item["text"], "title": item["title"], "reference": item["reference"]}
            for item in demo["topics"]
        ])

    @router.get("/cases")
    def cases(mode: Mode, person: UUID | None = None):
        with store.connect() as connection:
            participant = owner(connection, mode, person)
            rows = connection.execute(
                "SELECT id,state,version,updated_at,due_on FROM careloop_cases "
                "WHERE mode=? AND participant_id IS ? ORDER BY updated_at DESC,id",
                (mode, participant),
            )
            return {"cases": [dict(row) for row in rows]}

    @router.get("/cases/{case_id}")
    def read_case(case_id: UUID, mode: Mode, person: UUID | None = None):
        with store.connect() as connection:
            participant = owner(connection, mode, person)
            return view_case(connection, select_case(connection, mode, participant, str(case_id)))

    @router.post("/cases")
    def create_case(payload: CaseInput, mode: Mode, person: UUID | None = None):
        # Escalation guidance is independent from case consent and storage.
        if payload.signs:
            return {"safety": urgent(payload.signs) | {"sources": URGENT_SOURCES}, "case": None}
        if not payload.consent:
            raise HTTPException(422, "explicit_case_consent_required")
        if mode == "demo" and person is None and payload.share_with_twin:
            raise HTTPException(422, "demo_case_has_no_twin_participant")
        priority = "professional_review_suggested" if payload.screening == "unsure" else "local_followup"
        with store.connect(True) as connection:
            participant = owner(connection, mode, person)
            item = intake(connection, mode, participant, payload.model_dump(mode="json"), priority)
            return {"case": item, "safety": urgent([])}

    @router.post("/cases/{case_id}/events")
    def add_event(case_id: UUID, payload: EventInput, mode: Mode, person: UUID | None = None):
        if payload.action != "withdraw" and not payload.note:
            raise HTTPException(422, "workflow_note_required")
        if payload.action == "withdraw" and (payload.note or payload.reference):
            raise HTTPException(422, "withdrawal_uses_no_case_details")
        with store.connect(True) as connection:
            participant = owner(connection, mode, person)
            item = select_case(connection, mode, participant, str(case_id))
            return transition(connection, item, payload.model_dump(mode="json"))

    return router
