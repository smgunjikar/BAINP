"""Isolated engineering tests for the policy and persistent local workflow."""

from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from local_http import LocalClient, serve

APPS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APPS/"neuroaccess/backend"))
from api import create_app
from prevention_bridge import for_twin
from bainp_sim import education, matched_context, digest

PROFILE = dict(display_name="Fictional test participant", age=60, education_years=12,
    digital_familiarity="medium", language="en", vision_limitation=False, vision_aid="none",
    hearing_limitation=False, hearing_aid=False, motor_limitation=False, input_method="keyboard",
    device_type="desktop", text_size="standard", high_contrast=False, reduced_motion=False,
    assistance="none", assistance_authorized=False, can_see_and_respond="yes")


class Tests(unittest.TestCase):
    def setUp(self):
        resources = ExitStack()
        self.addCleanup(resources.close)
        tmp = Path(resources.enter_context(tempfile.TemporaryDirectory()))
        resources.enter_context(patch.dict(os.environ, {key: str(tmp/key) for key in (
            "NEUROVISION_DATA_DIR", "NEUROTWIN_MODEL_DIR", "NEUROTWIN_POLICY_FILE", "NEUROTWIN_ANATOMY_DIR")}))
        app = create_app(tmp/"db", password="prevention-fixture")
        self.store = app.state.store
        base = resources.enter_context(serve(app))
        self.anon = LocalClient(base)
        self.anon.headers["X-NeuroAccess-Request"] = "1"
        self.client = LocalClient(base)
        self.client.headers["X-NeuroAccess-Request"] = "1"
        response = self.client.post("/api/login", json={"password":"prevention-fixture"})
        self.assertEqual(response.status_code, 200, response.text)

    def call(self, path, payload=None, status=200):
        method = self.client.get if payload is None else self.client.post
        result = method("/api/prevention/" + path, **({} if payload is None else {"json": payload}))
        self.assertEqual(result.status_code, status, result.text)
        return result.json()

    def add_person(self, mode="active"):
        pid = str(uuid4())
        response = self.client.post("/api/participants", json=dict(
            id=pid, mode=mode, profile=PROFILE, consent_to_store=True))
        self.assertEqual(response.status_code, 201, response.text)
        return pid

    def intake(self, **overrides):
        return dict(case_id=str(uuid4()), category="daily_function", concern="Fictional organization concern",
                    consent=True, signs=[], screening="none_selected", share_with_twin=False) | overrides

    def event(self, key, scope, version, action, **fields):
        status = fields.pop("status", 200)
        body = dict(expected_version=version, operation_id=str(uuid4()), action=action,
                    note="Fictional local workflow record") | fields
        return self.call(f"cases/{key}/events?{scope}", body, status)

    def test_education_uses_reviewed_topics_and_preferences(self):
        report = self.call("education?mode=demo", {"preferences":["access","access"]})
        self.assertTrue(report["synthetic"])
        self.assertEqual({item["id"] for item in report["topics"]}, {"activity","bp","sleep","cognition"})
        self.assertEqual(len(report["preferences"]), 1)
        self.assertTrue(all(item["policy_version"].startswith("neuroguard") for item in report["topics"]))
        with patch("bainp_sim.date") as clock:
            from datetime import date
            clock.today.return_value = date(2030, 1, 1)
            clock.fromisoformat.side_effect = date.fromisoformat
            self.assertEqual(education({"bp":{"test"}},[])["topics"], [])

    def test_context_checks_quality_and_digest(self):
        raw = {"kind":"measurement","metric":"bp_systolic","quality":"usable"}
        good = {"scope":"context","payload":raw,"numeric_eligible":True,"sha256":digest(raw)}
        self.assertEqual(matched_context({"records":[good]}), {"bp":{"BBC-BE"}})
        for changed in [{"sha256":"corrupt"},{"numeric_eligible":False},{"scope":"genomic"}]:
            self.assertEqual(matched_context({"records":[good | changed]}), {})

    def test_scenario_is_input_only(self):
        result = self.call("scenario", {"activity_minutes":240,"sleep_hours":7,"systolic_mmhg":135})
        self.assertEqual([row["difference"] for row in result["rows"]], [30,0,5])
        self.assertFalse(result["model_executed"])
        self.assertIsNone(result["risk_estimate"])
        self.assertIsNone(result["intervention_effect"])
        self.call("scenario", {"activity_minutes":240,"sleep_hours":25,"systolic_mmhg":135}, 422)

    def test_urgent_path_does_not_queue_and_consent_is_required(self):
        response = self.call("cases?mode=demo", self.intake(signs=["speech"], consent=False))
        self.assertEqual(response["safety"]["state"], "escalate")
        self.assertIsNone(response["case"])
        self.call("cases?mode=demo", self.intake(consent=False), 422)
        self.assertEqual(self.call("cases?mode=demo")["cases"], [])
        self.assertEqual(self.anon.get("/api/prevention/cases?mode=demo").status_code, 401)
        warning = self.anon.post("/api/neuro-evidence/urgent", json={"signs":["face"]})
        self.assertEqual(warning.json()["state"], "escalate")

    def test_case_lifecycle_conflicts_and_idempotency(self):
        scope = "mode=demo"
        intake = self.intake()
        key = intake["case_id"]
        self.assertEqual(self.call("cases?"+scope, intake)["case"]["version"], 1)
        self.assertEqual(self.call("cases?"+scope, intake)["case"]["version"], 1)
        self.call("cases?"+scope, intake | {"concern":"Different content"}, 409)
        self.event(key, scope, 1, "close", status=409)
        operation = str(uuid4())
        self.event(key, scope, 1, "request_review", operation_id=operation)
        same = self.event(key, scope, 1, "request_review", operation_id=operation)
        self.assertEqual(same["version"], 2)
        self.event(key, scope, 1, "document_referral", reference="demo ref", status=409)
        self.event(key, scope, 2, "document_referral", status=422)
        self.event(key, scope, 2, "document_referral", reference="fictional referral")
        self.event(key, scope, 3, "plan_followup", status=422)
        self.event(key, scope, 3, "plan_followup", due_on="2027-01-12")
        self.event(key, scope, 4, "confirm_followup", reference="fictional visit")
        self.event(key, scope, 5, "record_outcome", reference="fictional outcome")
        closed = self.event(key, scope, 6, "close")
        self.assertEqual(closed["state"], "closed")
        self.assertEqual([item["version"] for item in closed["history"]], list(range(1,8)))
        self.assertEqual(self.call(f"cases/{key}?{scope}")["version"], 7)

    def test_active_isolation_and_twin_withdrawal(self):
        pid = self.add_person()
        other = self.add_person()
        scope = f"mode=active&person={pid}"
        key = self.call("cases?"+scope, self.intake(share_with_twin=True))["case"]["id"]
        self.call(f"cases/{key}?mode=active&person={other}", status=404)
        self.call(f"cases/{key}?mode=demo", status=404)
        self.event(key, scope, 1, "request_review")
        self.event(key, scope, 2, "plan_followup", due_on="2027-01-12")
        self.event(key, scope, 3, "confirm_followup", reference="external visit")
        self.assertEqual([row["action"] for row in for_twin(self.store,pid,"active")], ["confirm_followup"])
        self.assertEqual(for_twin(self.store,other,"active"), [])
        self.assertEqual(for_twin(self.store,pid,"demo"), [])
        if (APPS/"neurotwin/backend/router.py").is_file():
            result = self.client.get(f"/api/neurotwin/participants/{pid}?mode=active")
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["careloop_markers"], for_twin(self.store,pid,"active"))
        withdrawn = self.event(key, scope, 4, "withdraw", note=None)
        self.assertNotIn("concern", withdrawn)
        self.assertEqual(withdrawn["history"], [])
        self.assertEqual(for_twin(self.store,pid,"active"), [])

    def test_failed_event_write_rolls_back_case_state(self):
        scope = "mode=demo"
        item = self.call("cases?"+scope, self.intake())["case"]
        path = f"cases/{item['id']}/events?{scope}"
        payload = dict(expected_version=1, operation_id=str(uuid4()), action="request_review",
                       note="Fictional workflow record")
        with self.store.connect(True) as connection:
            connection.execute("CREATE TRIGGER simulate_failed_event BEFORE INSERT ON careloop_events "
                               "WHEN NEW.version=2 BEGIN SELECT RAISE(ABORT,'simulated failure'); END")
        self.call(path, payload, 503)
        unchanged = self.call(f"cases/{item['id']}?{scope}")
        self.assertEqual((unchanged["version"], unchanged["state"]), (1, "recorded"))
        self.assertEqual(len(unchanged["history"]), 1)
        with self.store.connect(True) as connection:
            connection.execute("DROP TRIGGER simulate_failed_event")
        self.assertEqual(self.call(path, payload)["version"], 2)

    def test_active_education_honors_bbc_consent(self):
        if not (APPS/"brainbody/backend/provider.py").is_file():
            self.skipTest("BBC-BE unavailable")
        pid = self.add_person()
        scope = f"mode=active&person={pid}"
        endpoint = f"/api/brainbody/participants/{pid}"
        consent = {"expected_revision":0,"scopes":["context"],"authorization_reference":"Fictional consent"}
        self.assertEqual(self.client.put(endpoint+"/consent?mode=active",json=consent).status_code,200)
        record = dict(revision=1,kind="measurement",metric="bp_systolic",value=125,unit="mmHg",qualifier="exact",
            observed_at="2025-01-01T09:00:00Z",available_at="2025-01-01T09:10:00Z",
            source=dict(kind="self_report",organization="Fixture",record_reference="fixture-1"),
            identity_verified=True,quality="usable",context="Fixture protocol")
        response = self.client.put(endpoint+f"/records/{uuid4()}?mode=active",json=record)
        self.assertEqual(response.status_code,200,response.text)
        topic = self.call("education?"+scope,{})["topics"]
        self.assertEqual([item["id"] for item in topic],["bp"])
        self.assertEqual(self.client.put(endpoint+"/consent?mode=active",
            json=consent | {"expected_revision":1,"scopes":[]}).status_code,200)
        self.assertEqual(self.call("education?"+scope,{})["topics"],[])


if __name__ == "__main__":
    unittest.main(verbosity=2)
