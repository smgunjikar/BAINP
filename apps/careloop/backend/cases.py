"""CareLoop persistence and auditable local state transitions."""

from datetime import datetime, timezone
import json

from fastapi import HTTPException

from bainp_sim import digest

SCHEMA = """
CREATE TABLE IF NOT EXISTS careloop_cases (
  id TEXT PRIMARY KEY,
  participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('active','demo')),
  category TEXT NOT NULL,
  concern TEXT NOT NULL,
  priority TEXT NOT NULL,
  state TEXT NOT NULL,
  version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  due_on TEXT,
  share_with_twin INTEGER NOT NULL CHECK(share_with_twin IN (0,1)),
  intake_digest TEXT NOT NULL,
  CHECK(mode='demo' OR participant_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS careloop_subject ON careloop_cases(participant_id, mode, updated_at);
CREATE TABLE IF NOT EXISTS careloop_events (
  case_id TEXT NOT NULL REFERENCES careloop_cases(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  operation_id TEXT NOT NULL,
  request_digest TEXT NOT NULL,
  action TEXT NOT NULL,
  state TEXT NOT NULL,
  note TEXT,
  reference TEXT,
  due_on TEXT,
  at TEXT NOT NULL,
  PRIMARY KEY(case_id, version),
  UNIQUE(case_id, operation_id)
);
"""
ACTIONS = {
    "request_review": "review_requested",
    "plan_monitoring": "monitoring_planned",
    "document_referral": "referral_documented",
    "plan_followup": "followup_planned",
    "confirm_followup": "followup_completed",
    "record_outcome": "outcome_recorded",
    "close": "closed",
    "reopen": "review_requested",
    "withdraw": "withdrawn",
}
ALLOWED = {
    "recorded": ("request_review", "plan_monitoring"),
    "review_requested": ("document_referral", "plan_monitoring", "plan_followup"),
    "monitoring_planned": ("plan_followup", "request_review"),
    "referral_documented": ("plan_followup", "request_review"),
    "followup_planned": ("confirm_followup", "plan_followup"),
    "followup_completed": ("record_outcome", "plan_followup"),
    "outcome_recorded": ("close", "plan_followup"),
    "closed": ("reopen",),
    "withdrawn": (),
}
REFERENCE_ACTIONS = {"document_referral", "confirm_followup", "record_outcome"}
DUE_ACTIONS = {"plan_monitoring", "plan_followup"}


def now():
    return datetime.now(timezone.utc).isoformat()


def require_owner(connection, mode, participant):
    if participant is None:
        if mode == "active":
            raise HTTPException(422, "select_participant")
    elif not connection.execute("SELECT 1 FROM participants WHERE id=? AND mode=?", (participant, mode)).fetchone():
        raise HTTPException(404, "participant_not_found")


def select_case(connection, mode, participant, key):
    item = connection.execute(
        "SELECT * FROM careloop_cases WHERE id=? AND mode=? AND participant_id IS ?",
        (key, mode, participant),
    ).fetchone()
    if item is None:
        raise HTTPException(404, "case_not_found")
    return item


def view_case(connection, item):
    public = {field: item[field] for field in ("id", "mode", "state", "version", "updated_at")}
    if item["state"] == "withdrawn":
        return public | {"actions": [], "history": []}
    public.update({field: item[field] for field in ("category", "concern", "priority", "created_at", "due_on")})
    public["share_with_twin"] = bool(item["share_with_twin"])
    public["actions"] = [*ALLOWED[item["state"]], "withdraw"]
    public["history"] = [dict(row) for row in connection.execute(
        "SELECT version,action,state,note,reference,due_on,at FROM careloop_events WHERE case_id=? ORDER BY version",
        (item["id"],),
    )]
    return public


def intake(connection, mode, participant, payload, priority):
    key = payload["case_id"]
    request_digest = digest(payload)
    previous = connection.execute("SELECT * FROM careloop_cases WHERE id=?", (key,)).fetchone()
    if previous:
        if previous["participant_id"] != participant or previous["mode"] != mode or previous["intake_digest"] != request_digest:
            raise HTTPException(409, "case_key_conflict")
        return view_case(connection, previous)
    at = now()
    connection.execute(
        "INSERT INTO careloop_cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (key, participant, mode, payload["category"], payload["concern"], priority,
         "recorded", 1, at, at, None, int(payload["share_with_twin"]), request_digest),
    )
    connection.execute(
        "INSERT INTO careloop_events VALUES(?,?,?,?,?,?,?,?,?,?)",
        (key, 1, key, request_digest, "intake", "recorded", None, None, None, at),
    )
    return view_case(connection, select_case(connection, mode, participant, key))


def transition(connection, item, payload):
    key = item["id"]
    request_digest = digest(payload)
    prior = connection.execute(
        "SELECT request_digest FROM careloop_events WHERE case_id=? AND operation_id=?",
        (key, payload["operation_id"]),
    ).fetchone()
    if prior:
        if prior["request_digest"] != request_digest:
            raise HTTPException(409, "operation_key_conflict")
        return view_case(connection, item)
    if payload["expected_version"] != item["version"]:
        raise HTTPException(409, "case_changed_refresh")
    action = payload["action"]
    if action not in ALLOWED[item["state"]] and not (action == "withdraw" and item["state"] != "withdrawn"):
        raise HTTPException(409, "transition_not_allowed")
    if action in REFERENCE_ACTIONS and not payload["reference"]:
        raise HTTPException(422, "external_confirmation_reference_required")
    if action in DUE_ACTIONS and not payload["due_on"]:
        raise HTTPException(422, "followup_date_required")
    if action not in DUE_ACTIONS and payload["due_on"] is not None:
        raise HTTPException(422, "date_only_for_planning_actions")
    state = ACTIONS[action]
    version = item["version"]+1
    at = now()
    due = payload["due_on"] if action in DUE_ACTIONS else (None if action in {"confirm_followup", "close", "withdraw"} else item["due_on"])
    connection.execute(
        "UPDATE careloop_cases SET state=?,version=?,updated_at=?,due_on=? WHERE id=?",
        (state, version, at, due, key),
    )
    connection.execute(
        "INSERT INTO careloop_events VALUES(?,?,?,?,?,?,?,?,?,?)",
        (key, version, payload["operation_id"], request_digest, action, state,
         payload["note"], payload["reference"], due, at),
    )
    return view_case(connection, connection.execute("SELECT * FROM careloop_cases WHERE id=?", (key,)).fetchone())


def for_twin(store, participant, mode):
    """Share opt-in workflow markers, without notes or predictive inputs."""
    with store.connect() as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='careloop_cases'").fetchone():
            return []
        rows = connection.execute(
            "SELECT e.action,e.at FROM careloop_events e JOIN careloop_cases c ON c.id=e.case_id "
            "WHERE c.participant_id=? AND c.mode=? AND c.share_with_twin=1 AND c.state<>'withdrawn' "
            "AND e.action IN ('confirm_followup','record_outcome') ORDER BY e.at DESC,e.case_id,e.version DESC LIMIT 20",
            (str(participant), mode),
        )
        return [dict(row) for row in rows]
