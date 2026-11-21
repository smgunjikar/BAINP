"""Isolated engineering checks. No cohort or participant data are required."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from local_http import LocalClient, serve

APPS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APPS / "neuroaccess/backend"))
from neuroevidence_bridge import guard_forecast
from bainp_graph import build, cognitive_comparisons
from bainp_guard import check_claim, urgent
from bainp_ng_llm import demo_plan
from bainp_ng_router import example_snapshot
from api import create_app

PROFILE = {
    "display_name": "Isolated evidence test", "age": 60, "education_years": 12, "digital_familiarity": "medium",
    "language": "en", "vision_limitation": False, "vision_aid": "none", "hearing_limitation": False,
    "hearing_aid": False, "motor_limitation": False, "input_method": "keyboard", "device_type": "desktop",
    "text_size": "standard", "high_contrast": False, "reduced_motion": False, "assistance": "none",
    "assistance_authorized": False, "can_see_and_respond": "yes",
}


class PolicyTests(unittest.TestCase):
    def test_claim_matrix(self):
        report = build(example_snapshot(), synthetic=True)
        nodes = {item["id"]: item for item in report["nodes"]}
        measurement = next(item for item in nodes.values() if item.get("value") == 132)
        cases = [
            ("measurement", measurement["id"], 132, "mmHg", "accept"),
            ("measurement", measurement["id"], 150, "mmHg", "block"),
            ("measurement", measurement["id"], 132, "kPa", "block"),
            ("measurement", measurement["id"], float("nan"), "mmHg", "block"),
            ("measurement", "invented", 132, "mmHg", "block"),
            ("measurement", "demo-eeg-quality", None, None, "abstain"),
            ("diagnosis", measurement["id"], None, None, "block"),
            ("guidance", "aric-vascular", None, None, "block"),
            ("association", "aric-vascular", None, None, "accept"),
            ("comparison", None, None, None, "abstain"),
        ]
        for claim, key, value, unit, expected in cases:
            with self.subTest(claim=claim, key=key, value=value, unit=unit):
                self.assertEqual(check_claim(claim, key, nodes, value, unit)["state"], expected)

    def test_cognition_comparability_requires_unflagged_matched_sessions(self):
        points = example_snapshot()["cognitive_points"]
        self.assertEqual(len(cognitive_comparisons(points)), 1)
        for difference in [{"condition_group": "new-device"}, {"flags": ["CLOCK_ERROR"]},
                           {"status": "aborted"}, {"session_id": points[0]["session_id"]}]:
            self.assertFalse(cognitive_comparisons([points[0], points[1] | difference]))

    def test_forecast_output_envelope(self):
        forecast = dict(state="REVIEWED_RESEARCH_ESTIMATE", value=0.4, interval=[0.2, 0.6],
                        horizon_months=24, external_evaluation={"brier": 0.2}, model_version="fixture", reasons=[])
        self.assertEqual(guard_forecast(forecast)["output_guard"]["state"], "accept")
        for difference in [{"interval": [0.7, 0.2]}, {"value": 1.5}, {"external_evaluation": None},
                           {"reasons": ["POPULATION_OUTSIDE_REVIEWED_SCOPE"]}]:
            rejected = guard_forecast(forecast | difference)
            self.assertEqual(rejected["output_guard"]["state"], "block")
            self.assertIsNone(rejected["value"])
            self.assertIsNone(rejected["interval"])

    def test_urgent_rules_ignore_model_state(self):
        for sign in ("face", "limb", "speech", "vision", "balance", "headache"):
            self.assertEqual(urgent([sign])["state"], "escalate")
        self.assertEqual(urgent([])["state"], "abstain")

    def test_local_model_planner_uses_only_approved_claim_ids(self):
        report = build(example_snapshot(), synthetic=True)
        with patch.dict(os.environ, {"BAINP_NEUROGRAPH_OLLAMA_MODEL": "fixture-local"}), patch("bainp_ng_llm.HTTPConnection") as server:
            response = server.return_value.getresponse.return_value
            response.status = 200
            for chosen, expected in [(["claim-who-prevention"], "accept"), (["claim-demo-eeg-quality"], "abstain"),
                                     (["invented"], "abstain")]:
                response.read.return_value = json.dumps(
                    {"done": True, "response": json.dumps({"claim_ids": chosen})}).encode()
                self.assertEqual(demo_plan(report["claims"])["state"], expected)
            server.assert_called_with("127.0.0.1", 11434, timeout=8)
            self.assertNotIn("132 mmHg", server.return_value.request.call_args.args[2])
        with patch.dict(os.environ, {"BAINP_NEUROGRAPH_OLLAMA_MODEL": ""}):
            self.assertEqual(demo_plan(report["claims"])["reason"], "LOCAL_MODEL_NOT_CONFIGURED")


class ApiTests(unittest.TestCase):
    def setUp(self):
        resources = ExitStack()
        self.addCleanup(resources.close)
        temp = Path(resources.enter_context(tempfile.TemporaryDirectory()))
        resources.enter_context(patch.dict(os.environ, {key: str(temp/key) for key in (
            "NEUROVISION_DATA_DIR", "NEUROTWIN_MODEL_DIR", "NEUROTWIN_POLICY_FILE", "NEUROTWIN_ANATOMY_DIR",
        )}))
        app = create_app(temp / "db", password="evidence-fixture")
        self.store = app.state.store
        base = resources.enter_context(serve(app))
        self.anon = LocalClient(base)
        self.anon.headers["X-NeuroAccess-Request"] = "1"
        self.client = LocalClient(base)
        self.client.headers["X-NeuroAccess-Request"] = "1"
        self.assertEqual(self.client.post("/api/login", json={"password": "evidence-fixture"}).status_code, 200)

    def test_auth_and_independent_urgent_api(self):
        root = "/api/neuro-evidence"
        self.assertEqual(self.anon.get(root + "/report?mode=demo").status_code, 401)
        self.assertEqual(self.anon.post(root + "/export?mode=demo", json={"revision": "a"*64}).status_code, 401)
        warning = self.anon.post(root + "/urgent", json={"signs": ["speech"]})
        self.assertEqual(warning.status_code, 200, warning.text)
        self.assertEqual(warning.json()["state"], "escalate")
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM audit_events WHERE action LIKE 'neuroguard_%'").fetchone()[0], 0)

    def test_demo_evaluation_and_filtered_export(self):
        root = "/api/neuro-evidence"
        data = self.client.get(root + "/report?mode=demo").json()
        self.assertTrue(data["synthetic"])
        self.assertEqual(len({item["type"] for item in data["nodes"]}), 6)
        response = self.client.post(root + "/evaluate?mode=demo", json={
            "claim": "diagnosis", "revision": data["revision"], "evidence_id": "unknown-mechanism"})
        self.assertEqual(response.json()["state"], "block")
        stale = self.client.post(root + "/export?mode=demo", json={"revision": "b"*64})
        self.assertEqual(stale.status_code, 409)
        export = self.client.post(root + "/export?mode=demo", json={"revision": data["revision"]}).json()
        self.assertTrue(all(claim["state"] == "accept" for claim in export["claims"]))
        self.assertNotIn("demo-eeg-quality", {node["id"] for node in export["nodes"]})

    def test_twin_scenario_cannot_release_failed_final_envelope(self):
        if not (APPS / "neurotwin/backend/router.py").is_file():
            self.skipTest("Optional NeuroTwin module unavailable")
        pid = str(uuid4())
        create = self.client.post("/api/participants", json={
            "id": pid, "mode": "active", "profile": PROFILE, "consent_to_store": True})
        self.assertEqual(create.status_code, 201, create.text)
        bad_forecast = dict(state="REVIEWED_RESEARCH_ESTIMATE", value=0.94, interval=[0.9, 1.7],
                            horizon_months=24, external_evaluation={"brier": 0.2}, model_version="fixture",
                            reasons=[])
        with patch("nt_guard._research_forecast", return_value=bad_forecast):
            response = self.client.post(f"/api/neurotwin/participants/{pid}/scenario?mode=active", json={"age": 61})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["value"])
        self.assertEqual(response.json()["output_guard"]["state"], "block")

    def test_active_evidence_withdrawal_and_hash_integrity(self):
        if not (APPS / "brainbody/backend/provider.py").is_file():
            self.skipTest("Optional BBC-BE module unavailable")
        pid = str(uuid4())
        create = self.client.post("/api/participants", json={
            "id": pid, "mode": "active", "profile": PROFILE, "consent_to_store": True})
        self.assertEqual(create.status_code, 201, create.text)
        route = f"/api/brainbody/participants/{pid}"
        consent = {"expected_revision": 0, "scopes": ["context"], "authorization_reference": "Isolated test"}
        self.assertEqual(self.client.put(route + "/consent?mode=active", json=consent).status_code, 200)
        record = dict(revision=1, kind="measurement", metric="bp_systolic", value=120, unit="mmHg", qualifier="exact",
                      observed_at="2025-01-01T09:00:00Z", available_at="2025-01-01T09:10:00Z",
                      source=dict(kind="self_report", organization="Fixture", record_reference="fixture-1"),
                      identity_verified=True, quality="usable", context="Fixture protocol")
        rid = str(uuid4())
        stored = self.client.put(route + f"/records/{rid}?mode=active", json=record)
        self.assertEqual(stored.status_code, 200, stored.text)
        query = f"?mode=active&person={pid}"
        url = "/api/neuro-evidence"
        snapshot = self.client.get(url + "/report" + query).json()
        self.assertTrue(any(node.get("value") == 120 for node in snapshot["nodes"]))
        self.assertEqual(self.client.get(url + f"/report?mode=demo&person={pid}").status_code, 404)
        with self.store.connect(True) as connection:
            connection.execute("UPDATE bb_versions SET sha256='changed' WHERE record_id=?", (rid,))
        tampered = self.client.get(url + "/report" + query).json()
        withheld = next(node for node in tampered["nodes"] if node.get("quality") == "source_hash_mismatch")
        self.assertIsNone(withheld["value"])
        self.assertFalse(withheld["eligible"])
        self.assertEqual(self.client.put(route + "/consent?mode=active", json=consent | {
            "expected_revision": 1, "scopes": []}).status_code, 200)
        revoked = self.client.post(url + "/export" + query, json={"revision": tampered["revision"]})
        self.assertEqual(revoked.status_code, 409, revoked.text)
        with self.store.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM audit_events WHERE action='neuroguard_stale_export' AND entity_id=?", (pid,)
            ).fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
