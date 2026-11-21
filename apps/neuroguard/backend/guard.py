"""Independent, deterministic release rules for supported research claims."""

import math

VERSION = "neuroguard-research-v1.1"
URGENT_SIGNS = {
    "face": "Sudden facial droop or numbness",
    "limb": "Sudden weakness or numbness on one side",
    "speech": "Sudden trouble speaking or understanding speech",
    "vision": "Sudden trouble seeing",
    "balance": "Sudden trouble walking or loss of balance",
    "headache": "Sudden severe headache with no known cause",
}
URGENT_GUIDANCE = (
    "Call your local emergency number now. In India, call 112. "
    "Seek emergency help even if the symptoms have resolved."
)
URGENT_SOURCES = [
    {"label": "CDC stroke warning signs", "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    {"label": "India Emergency Response Support System", "url": "https://112.gov.in/"},
]
TYPE_BY_CLAIM = {
    "measurement": "direct_observation",
    "comparison": "direct_observation",
    "context": "clinical_context",
    "association": "research_association",
    "guidance": "clinical_guidance",
    "hypothesis": "hypothesis",
    "uncertainty": "unknown",
}
FORBIDDEN = {"diagnosis", "causal_effect", "treatment", "clinical_prediction"}


def finite(value):
    if type(value) not in (float, int):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def decision(state, code, text, evidence_ids=()):
    return {"state": state, "reason": code, "text": text, "evidence_ids": list(evidence_ids),
            "policy_version": VERSION}


def check_claim(claim, evidence_id, nodes, value=None, unit=None):
    if not isinstance(claim,str) or claim not in TYPE_BY_CLAIM:
        return decision("block", "OUTSIDE_REPORT_SCOPE", "This claim type is outside the supported research report scope.")
    if claim in FORBIDDEN:
        return decision("block", "OUTSIDE_REPORT_SCOPE",
                        "This report cannot release a diagnosis, treatment instruction, causal claim or clinical prediction.")
    if not evidence_id or evidence_id not in nodes:
        return decision("abstain" if not evidence_id else "block",
                        "EVIDENCE_MISSING" if not evidence_id else "EVIDENCE_NOT_IN_CURRENT_SNAPSHOT",
                        "A current, authorized source is required for this claim.")
    node = nodes[evidence_id]
    if not isinstance(node,dict) or any(key not in node for key in ('type','claim','eligible','statement')):
        return decision("abstain", "EVIDENCE_MALFORMED", "The source record does not meet the evidence contract.")
    if TYPE_BY_CLAIM.get(claim) != node["type"] or claim != node["claim"]:
        return decision("block", "EVIDENCE_TYPE_MISMATCH", "The evidence does not support this type of claim.")
    if node["eligible"] is not True:
        return decision("abstain", "SOURCE_QUALITY_OR_TIMING", "Source quality or timing does not support releasing this claim.", [evidence_id])
    if claim == "measurement":
        if not finite(value) or value != node.get("value") or unit != node.get("unit"):
            return decision("block", "MEASUREMENT_DOES_NOT_MATCH_SOURCE", "The proposed value and unit must exactly match the current source.", [evidence_id])
    elif value is not None or unit is not None:
        return decision("block", "UNEXPECTED_MEASUREMENT", "This evidence type does not support a numeric claim.", [evidence_id])
    return decision("accept", "VERIFIED_REPORT_TEMPLATE", node["statement"], [evidence_id])


def urgent(signs):
    if signs:
        return decision("escalate", "REPORTED_SUDDEN_WARNING_SIGN", URGENT_GUIDANCE)
    return decision("abstain", "NO_SELECTED_WARNING_SIGN",
                    "No warning sign was selected. This checklist cannot rule out a medical emergency.")


def guard_forecast(result):
    """Check the final research-forecast envelope after existing model approval and OOD checks."""
    value, interval = result.get("value"), result.get("interval")
    if value is None and interval is None and result.get("state") != "REVIEWED_RESEARCH_ESTIMATE":
        return result
    valid = (
        result.get("state") == "REVIEWED_RESEARCH_ESTIMATE"
        and not result.get("reasons") and result.get("horizon_months") == 24
        and bool(result.get("external_evaluation")) and bool(result.get("model_version"))
        and finite(value) and 0 <= value <= 1
        and isinstance(interval, (list, tuple)) and len(interval) == 2
        and all(finite(bound) for bound in interval)
        and 0 <= interval[0] <= interval[1] <= 1
    )
    if valid:
        return result | {"output_guard": {"state": "accept", "policy_version": VERSION}}
    return {
        "state": "UNAVAILABLE_NO_VALIDATED_MODEL", "value": None, "interval": None,
        "horizon_months": 24, "target": "Clinician-recorded dementia after a baseline MCI assessment",
        "reasons": ["NEUROGUARD_OUTPUT_REJECTED"],
        "interpretation": "The forecast failed the final research output checks.",
        "output_guard": {"state": "block", "policy_version": VERSION},
    }
