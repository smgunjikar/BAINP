"""Offline operator command for a consistent SQLite snapshot and a restore rehearsal."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory


def verify(connection):
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("INTEGRITY_CHECK_FAILED")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("FOREIGN_KEY_CHECK_FAILED")


def checksum(path):
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(source, output):
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError("SOURCE_NOT_FILE")
    # A new directory is required. Never replace a previous backup or a live database.
    output.mkdir(mode=0o700)
    try:
        target = output/"snapshot.sqlite3"
        with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=10)) as live:
            with closing(sqlite3.connect(target)) as snapshot:
                live.backup(snapshot)
                verify(snapshot)
        # Restore to a temporary file to keep memory use independent of database size.
        with closing(sqlite3.connect(target.resolve().as_uri()+"?mode=ro",uri=True)) as snapshot:
            with TemporaryDirectory(prefix="rehearsal-",dir=output) as scratch:
                with closing(sqlite3.connect(Path(scratch)/"restored.sqlite3")) as rehearsal:
                    snapshot.backup(rehearsal)
                    verify(rehearsal)
        report = {"snapshot":"snapshot.sqlite3","sha256":checksum(target),"restore_rehearsal":"passed",
                  "scope":"SQLite only"}
        (output/"backup-report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        return report
    except Exception:
        shutil.rmtree(output)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(backup(args.source,args.output_dir),indent=2))
