"""Engineering verification using isolated SQLite databases and fictional prediction inputs."""
from contextlib import ExitStack, closing
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from local_http import LocalClient, serve

APPS = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(APPS/"neuroaccess/backend"),str(APPS/"neurosignal-arena/tools"),str(APPS/"platform-core/tools")]
from api import create_app
import arena_platform_bridge
from bainp_jobs import claim, enqueue, finish, QueueError, run_job
from evaluate_binary import evaluate, FILES, Invalid
from backup_sqlite import backup


class ApiTests(unittest.TestCase):
    def setUp(self):
        resources = ExitStack()
        self.addCleanup(resources.close)
        temp = Path(resources.enter_context(tempfile.TemporaryDirectory()))
        resources.enter_context(patch.dict(os.environ,{key:str(temp/key) for key in (
            "NEUROVISION_DATA_DIR","NEUROTWIN_MODEL_DIR","NEUROTWIN_POLICY_FILE","NEUROTWIN_ANATOMY_DIR")}))
        app = create_app(temp/"db",password="fictional-operator")
        self.store = app.state.store
        base = resources.enter_context(serve(app))
        self.anon = LocalClient(base)
        self.anon.headers["X-NeuroAccess-Request"] = "1"
        self.client = LocalClient(base)
        self.client.headers["X-NeuroAccess-Request"] = "1"
        self.assertEqual(self.client.post("/api/login",json={"password":"fictional-operator"}).status_code,200)

    def call(self,path,payload=None,status=200):
        endpoint = "/api/platform/v1/"+path
        response = self.client.get(endpoint) if payload is None else self.client.post(endpoint,json=payload)
        self.assertEqual(response.status_code,status,response.text)
        return response.json()

    def test_operator_authentication_and_status(self):
        self.assertEqual(self.anon.get("/api/platform/v1/status").status_code,401)
        self.assertEqual(self.anon.post("/api/platform/v1/jobs",json={"kind":"engineering_v1","job_id":str(uuid4())}).status_code,401)
        status = self.call("status")
        self.assertEqual(status["storage"],"local SQLite")
        self.assertTrue(status["requests"])
        self.assertIn("state",status["model_registry"])
        self.assertEqual(self.call("arena")["oasis2"]["participants"],104)

    def test_persistent_job_and_audit(self):
        key = str(uuid4())
        payload = {"job_id":key,"kind":"engineering_v1"}
        for _ in range(2):
            self.assertEqual(self.call("jobs",payload)["state"],"queued")
        self.call("jobs",payload|{"protocol_sha256":"override"},422)
        self.call("jobs",payload|{"kind":"shell"},422)
        result = self.call("jobs/"+key+"/run",{})
        self.assertEqual(result["state"],"completed")
        self.assertEqual(result["result"]["passed"],10)
        self.assertTrue(result["result"]["engineering_gate_passed"])
        self.assertFalse(result["result"]["release_authorized"])
        self.assertEqual(self.call("jobs/"+key+"/run",{})["attempts"],1)
        self.assertEqual([event["action"] for event in self.call("jobs/"+key)["events"]],["queued","leased","completed"])
        self.call("jobs/"+key+"/cancel",{},409)

    def test_failed_engineering_policy_cannot_authorize_release(self):
        key = str(uuid4())
        self.call("jobs",{"job_id":key,"kind":"engineering_v1"})
        with patch("bainp_guard.urgent",return_value={"state":"accept","reason":"FICTIONAL_FAILURE"}):
            result = self.call("jobs/"+key+"/run",{})["result"]
        self.assertFalse(result["engineering_gate_passed"])
        self.assertEqual(result["passed"],8)
        self.assertFalse(result["release_authorized"])

    def test_expired_lease_recovery_and_stale_worker_rejected(self):
        key = str(uuid4())
        enqueue(self.store,key)
        first = claim(self.store,key)
        self.assertIsNone(claim(self.store,key))
        with self.store.connect(True) as connection:
            connection.execute("UPDATE platform_jobs SET lease_until=0 WHERE id=?",(key,))
        second = claim(self.store,key)
        self.assertNotEqual(first["token"],second["token"])
        with self.assertRaisesRegex(QueueError,"LEASE_STALE"):
            finish(self.store,first,result={"forged":True})
        with self.store.connect(True) as connection:
            connection.execute("UPDATE platform_jobs SET lease_until=0 WHERE id=?",(key,))
        self.assertIsNone(claim(self.store,key))
        state = self.call("jobs/"+key)
        self.assertEqual((state["state"],state["error_code"]),("failed","LEASE_RETRIES_EXHAUSTED"))
        self.assertIsNone(state["result"])

    def test_changed_evaluator_cannot_run_existing_job(self):
        key = str(uuid4())
        enqueue(self.store,key)
        with patch("bainp_jobs.execution_sha",return_value="different"):
            item = run_job(self.store,key)
        self.assertEqual(item["state"],"failed")
        self.assertEqual(item["error_code"],"PROTOCOL_VERSION_CHANGED")


class OfflineTests(unittest.TestCase):
    def fixture(self,root,violation=None):
        split = [
            ("a","train","2024-01-01T00:00:00Z","2024-01-01T00:00:00Z","2025-02-01T00:00:00Z","0",""),
            ("b","validation","2024-01-01T00:00:00Z","2024-01-01T00:00:00Z","2025-02-01T00:00:00Z","1",""),
            ("c","test","2025-03-01T00:00:00Z","2025-03-01T00:00:00Z","2026-04-01T00:00:00Z","0","small"),
            ("d","test","2025-03-01T00:00:00Z","2025-03-01T00:00:00Z","2026-04-01T00:00:00Z","1","small"),
        ]
        fit = [("baseline","fit","a"),("baseline","preprocess","a"),("baseline","tune","b"),
               ("candidate","fit","a"),("candidate","preprocess","a")]
        preds = [("baseline","c","0.5"),("baseline","d","0.5"),("candidate","c","0.2"),("candidate","d","0.8")]
        if violation == "overlap":
            split.append(("a",*split[2][1:]))
        if violation == "future":
            split[2] = (*split[2][:3],"2025-03-02T00:00:00Z",*split[2][4:])
        if violation == "preprocess":
            fit[1] = ("baseline","preprocess","c")
        if violation == "missing":
            preds.pop()
        hashes = {}
        for name,rows in zip(FILES,(split,fit,preds)):
            with (root/name).open("w",encoding="utf-8",newline="") as stream:
                writer=csv.writer(stream)
                writer.writerow(FILES[name])
                writer.writerows(rows)
            hashes[name]=sha256((root/name).read_bytes()).hexdigest()
        manifest = dict(schema="arena-binary-v1",dataset="fictional",dataset_version="1",
                        usage_reference="fixture",outcome="fictional-fixed-horizon",horizon_days=365,
                        evaluation_split="test",models=[dict(id=name,threshold=.5,artifact_sha256="a"*64)
                            for name in ("baseline","candidate")],file_sha256=hashes)
        path=root/"protocol.json"
        path.write_text(json.dumps(manifest),encoding="utf-8")
        return sha256(path.read_bytes()).hexdigest()

    def test_locked_binary_metrics_and_small_group_suppression(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            checksum=self.fixture(root)
            report=evaluate(root,checksum,draws=100)
            self.assertEqual(report["models"]["baseline"]["metrics"]["auroc"],.5)
            self.assertEqual(report["models"]["candidate"]["metrics"]["auroc"],1)
            self.assertAlmostEqual(report["models"]["candidate"]["metrics"]["brier"],.04)
            self.assertEqual(report["models"]["candidate"]["subgroups"],{})
            self.assertEqual(report["models"]["candidate"]["calibration"],[])
            self.assertFalse(report["release_authorized"])
            self.assertEqual(report["models"]["candidate"]["paired_delta_vs_baseline_95_intervals"]["auroc"],[.5,.5])
            with self.assertRaisesRegex(Invalid,"PROTOCOL_HASH_MISMATCH"):
                evaluate(root,"a"*64,draws=100)
            with (root/"predictions.csv").open("a",encoding="utf-8") as stream:
                stream.write("tamper")
            with self.assertRaisesRegex(Invalid,"TABLE_HASH_MISMATCH"):
                evaluate(root,checksum,draws=100)

    def test_leakage_and_incomplete_predictions_block_before_metrics(self):
        cases={"overlap":"PARTICIPANT_DUPLICATE","future":"FUTURE_FEATURE",
               "preprocess":"FIT_OR_TUNING_SPLIT","missing":"MISSING_HELD_OUT"}
        for violation,reason in cases.items():
            with self.subTest(violation=violation), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                checksum=self.fixture(root,violation)
                with self.assertRaisesRegex(Invalid,reason):
                    evaluate(root,checksum,draws=100)

    def test_sqlite_backup_includes_committed_wal_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with closing(sqlite3.connect(root/"live.sqlite3")) as live:
                live.execute("PRAGMA journal_mode=WAL")
                live.execute("CREATE TABLE sample(id INTEGER)")
                live.execute("INSERT INTO sample VALUES(42)")
                live.commit()
                result=backup(root/"live.sqlite3",root/"protected-backup")
                self.assertEqual(result["restore_rehearsal"],"passed")
                with closing(sqlite3.connect(root/"protected-backup/snapshot.sqlite3")) as snapshot:
                    self.assertEqual(snapshot.execute("SELECT id FROM sample").fetchall(),[(42,)])
                with self.assertRaises(FileExistsError):
                    backup(root/"live.sqlite3",root/"protected-backup")


if __name__ == "__main__":
    unittest.main(verbosity=2)
