"""Fixed, versioned engineering protocol independent of model-development inputs."""
from hashlib import sha256
import json
from pathlib import Path
import platform

import bainp_guard

VERSION = "arena-engineering-v1"
EVALUATOR_SHA = sha256(Path(__file__).read_bytes()).hexdigest()
POLICY_SHA = sha256(Path(bainp_guard.__file__).read_bytes()).hexdigest()
# These expected decisions ship with the evaluator. The job API accepts no protocol or score overrides.
PROTOCOL = (
    ("source-match", "accept", "measurement", "record", 125, "mmHg", True),
    ("invented-value", "block", "measurement", "record", 180, "mmHg", True),
    ("wrong-unit", "block", "measurement", "record", 125, "mg/dL", True),
    ("missing-source", "abstain", "measurement", None, 125, "mmHg", True),
    ("unrecognized-source", "block", "measurement", "other", 125, "mmHg", True),
    ("invalid-signal", "abstain", "measurement", "record", 125, "mmHg", False),
    ("unsupported-diagnosis", "block", "diagnosis", "record", None, None, True),
    ("causal-overclaim", "block", "causal_effect", "record", None, None, True),
    ("urgent-sign", "escalate", None, None, None, None, True),
    ("empty-urgent-check", "abstain", None, None, None, None, True),
)
DATASETS = (
    ("synthetic-policy-v1", "Included fictional safety fixtures", "Local benchmark"),
    ("oasis-2", "Frozen clinical-only OASIS-2 cohort", "Research terms apply"),
    ("adni", "Planned authorized research track", "Local authorized access"),
    ("openneuro-eeg", "Planned dataset-specific research track", "Dataset-specific terms"),
    ("pads", "Planned wearable benchmark track", "Dataset-specific terms"),
)


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def protocol_sha():
    return digest({"version": VERSION, "cases": PROTOCOL})


def execution_sha():
    return digest([protocol_sha(),EVALUATOR_SHA,POLICY_SHA])


def run():
    cases = []
    for key, expected, claim, source, value, unit, eligible in PROTOCOL:
        if claim is None:
            decision = bainp_guard.urgent(["speech"] if key == "urgent-sign" else [])
        else:
            nodes = {"record": {"type":"direct_observation", "claim":"measurement", "eligible":eligible,
                               "value":125, "unit":"mmHg", "statement":"Fictional benchmark measurement."}}
            decision = bainp_guard.check_claim(claim,source,nodes,value,unit)
        actual = decision["state"]
        cases.append(dict(id=key, expected=expected, actual=actual, reason=decision["reason"], passed=expected == actual))
    passed = sum(row["passed"] for row in cases)
    return dict(protocol=VERSION, protocol_sha256=protocol_sha(),
                evaluator_sha256=EVALUATOR_SHA, policy_sha256=POLICY_SHA,
                policy_version=bainp_guard.VERSION, python=platform.python_version(), synthetic=True,
                cases=cases, passed=passed, total=len(cases), engineering_gate_passed=passed == len(cases),
                release_authorized=False)


def research_summary():
    return json.loads((Path(__file__).resolve().parents[1]/"evidence/oasis2_summary.json").read_text(encoding="utf-8"))
