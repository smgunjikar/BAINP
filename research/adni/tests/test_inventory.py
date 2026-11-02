"""Synthetic-only tests. Never put restricted ADNI files here."""
import importlib.util
import json
import zipfile
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "inventory.py"
spec = importlib.util.spec_from_file_location("adni_inventory", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_aggregate_counts_without_id_disclosure(tmp_path, capsys):
    (tmp_path / "DXSUM_test.csv").write_text("RID,VISCODE2,DIAGNOSIS\nSECRET_RID_A,bl,1\nSECRET_RID_A,m12,2\nSECRET_RID_B,bl,1\n", encoding="utf-8")
    module.main(["--source", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)
    row = report["records"][0]
    assert row["rows_scanned"] == 3
    assert row["unique_subjects_in_scanned_rows"] == 2
    assert "SECRET_RID" not in json.dumps(report)
    assert "DXSUM" in report["recognized_priority_tables"]


def test_zip_inventory(tmp_path, capsys):
    with zipfile.ZipFile(tmp_path / "tables.zip", "w") as z:
        z.writestr("folder/MMSE_test.csv", "RID,VISCODE2,MMSCORE\nSECRET_RID,bl,28\n")
    module.main(["--source", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)
    assert report["files_checked"] == 1
    assert report["records"][0]["rows_scanned"] == 1
    assert "SECRET_RID" not in json.dumps(report)


def test_limited_scan(tmp_path, capsys):
    (tmp_path / "ROSTER.csv").write_text("RID\nA\nB\nC\n", encoding="utf-8")
    module.main(["--source", str(tmp_path), "--max-rows", "2"])
    row = json.loads(capsys.readouterr().out)["records"][0]
    assert row["rows_scanned"] == 2
    assert not row["scanned_all_rows"]
