"""Curated education and bounded input comparisons for NeuroSim."""

from datetime import date
from hashlib import sha256
import json
import sys

VERSION = "neurosim-education-v1"
WHO = {"title": "WHO dementia risk reduction guidelines, second edition",
       "url": "https://www.who.int/publications/i/item/9789240123557", "review_by": "2027-07-15",
       "population": "Adults without dementia. Applicability requires professional review."}
NIA = {"title": "NIA cognitive health and older adults",
       "url": "https://www.nia.nih.gov/health/cognitive-health-and-older-adults", "review_by": "2027-07-15",
       "population": "General information for older adults."}
TOPICS = {
    "bp": ("Blood pressure context", WHO, "Bring your readings and how they were taken to a qualified professional. Ask how to review your blood pressure in the context of your medical history."),
    "activity": ("Physical activity", WHO, "Discuss activity options that fit your mobility, schedule, and preferences with a qualified professional."),
    "sleep": ("Sleep context", NIA, "Bring a short record of sleep timing and persistent difficulties to a qualified professional for review."),
    "cognition": ("Cognitive observations", NIA, "Bring dated examples of changes in everyday functioning and your assessment observations to a qualified professional."),
}
METRIC_TOPIC = {
    "bp_systolic": "bp", "bp_diastolic": "bp", "activity_minutes": "activity",
    "steps": "activity", "sleep_duration": "sleep", "sleep_efficiency": "sleep",
}
DEFAULT = {"activity_minutes": 210, "sleep_hours": 7, "systolic_mmhg": 130}
UNITS = {"activity_minutes": "min/week", "sleep_hours": "h", "systolic_mmhg": "mmHg"}
PREFERENCES = {
    "mobility": "Ask about options that fit your mobility and available support.",
    "time": "Ask about ways to fit the discussion and any agreed actions into your schedule.",
    "access": "Ask what local, remote, or lower-cost services may be available.",
}


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return sha256(payload.encode()).hexdigest()


def matched_context(snapshot):
    matched = {}
    for row in snapshot.get("records", []):
        raw = row["payload"]
        if row.get("scope") != "context" or raw["quality"] != "usable" or digest(raw) != row.get("sha256"):
            continue
        topic = METRIC_TOPIC.get(raw.get("metric")) if row.get("numeric_eligible") else None
        if raw["kind"] == "sleep_report":
            topic = "sleep"
        if topic:
            matched.setdefault(topic, set()).add("BBC-BE")
    for series in snapshot.get("series", []):
        topic = METRIC_TOPIC.get(series["metric"])
        if topic and any(point["eligible"] and point["id"].startswith("sense:") for point in series["points"]):
            matched.setdefault(topic, set()).add("NeuroSense")
    if any(p.get("status") == "completed" and p.get("flags") == [] for p in snapshot.get("cognitive_points", [])):
        matched["cognition"] = {"NeuroCognition X"}
    return matched


def education(context, preferences, synthetic=False):
    guard = sys.modules.get("bainp_guard")
    selected = []
    for key, (title, source, text) in TOPICS.items():
        if date.today() > date.fromisoformat(source["review_by"]):
            continue
        if key not in context:
            continue
        evidence = {"type": "clinical_guidance", "claim": "guidance", "eligible": True, "statement": text}
        verdict = guard.check_claim("guidance", key, {key: evidence}) if guard else None
        if not verdict or verdict["state"] != "accept":
            continue
        selected.append(dict(id=key, title=title, text=verdict["text"], reference=source,
                             origins=sorted(context[key]), evidence_level="public guidance",
                             policy_version=verdict["policy_version"]))
    return dict(version=VERSION, synthetic=synthetic, topics=selected,
                preferences=[PREFERENCES[key] for key in preferences],
                state="available" if selected else "insufficient_authorized_context_or_policy",
                scope="Education and questions for professional discussion")


def compare(values):
    return {"state": "input_comparison", "version": VERSION,
            "rows": [{"input": key, "unit": UNITS[key], "baseline": DEFAULT[key],
                      "hypothetical": value, "difference": round(value-DEFAULT[key], 2)} for key, value in values.items()],
            "model_executed": False, "risk_estimate": None, "intervention_effect": None}
