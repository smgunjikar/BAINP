"""Local-only ADNI tabular inventory. Never prints participant-level values.

Accepts CSV/TSV or ZIPs containing CSV/TSV. Reports aggregate row and subject counts,
column names needed for linkage, and whether the scan was truncated.
It performs no download, cross-study joins, diagnosis inference, or AI model upload.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

KEYS = {"RID", "PTID", "VISCODE", "VISCODE2", "EXAMDATE", "VISDATE", "SCANDATE", "IMAGEUID", "LONIIMAGE", "PHC_LONIUID", "COLPROT", "PHASE", "DIAGNOSIS", "DXCHANGE"}
PRIORITIES = {"DATADIC", "ROSTER", "REGISTRY", "VISITS", "DXSUM", "PTDEMOG", "MMSE", "CDR", "ADAS", "FAQ", "MRIQC", "UCSFFSX7", "ADNIMERGE", "ADNIMERGE2"}
SUFFIXES = {".csv", ".tsv"}
MAX_ZIP_MEMBER_BYTES = 500 * 1024 * 1024

@contextmanager
def open_text(path: Path, member: str | None) -> Iterator[TextIO]:
    if member is None:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            yield fh
    else:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(member)
            if info.file_size > MAX_ZIP_MEMBER_BYTES:
                raise ValueError("Skipped oversized ZIP member")
            with archive.open(info, "r") as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="") as fh:
                    yield fh


def sources(folder: Path):
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in SUFFIXES:
            yield path, None
        elif path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    names = sorted(info.filename for info in archive.infolist()
                                   if not info.is_dir() and Path(info.filename).suffix.lower() in SUFFIXES
                                   and info.file_size <= MAX_ZIP_MEMBER_BYTES)
                for name in names:
                    yield path, name
            except zipfile.BadZipFile:
                yield path, "<invalid-zip>"


def inspect(source: Path, member: str | None, max_rows: int):
    label = f"{source.name}::{Path(member).name}" if member else source.name
    if member == "<invalid-zip>":
        return {"file": label, "error": "Not a readable ZIP"}
    try:
        with open_text(source, member) as fh:
            delimiter = "\t" if Path(member or source.name).suffix.lower() == ".tsv" else ","
            reader = csv.DictReader(fh, delimiter=delimiter)
            columns = [c.strip() for c in (reader.fieldnames or []) if c]
            key_columns = sorted({c for c in columns if c.upper() in KEYS})
            lookup = {c.upper(): c for c in columns}
            rid_column = lookup.get("RID") or lookup.get("PTID")
            visit_column = lookup.get("VISCODE2") or lookup.get("VISCODE")
            subjects, pairs = set(), set()
            scanned, duplicates = 0, 0
            for row in reader:
                scanned += 1
                rid = (row.get(rid_column) or "").strip() if rid_column else ""
                visit = (row.get(visit_column) or "").strip() if visit_column else ""
                if rid:
                    subjects.add(rid)
                if rid and visit:
                    pair = (rid, visit)
                    if pair in pairs:
                        duplicates += 1
                    pairs.add(pair)
                if max_rows and scanned >= max_rows:
                    break
        return {"file": label, "rows_scanned": scanned, "scanned_all_rows": max_rows == 0 or scanned < max_rows,
                "columns_total": len(columns), "linkage_columns": key_columns,
                "unique_subjects_in_scanned_rows": len(subjects) if rid_column else None,
                "repeated_subject_visit_keys": duplicates if rid_column and visit_column else None,
                "note": "Repeated keys can be valid; imaging/assessment tables may have multiple rows per visit."}
    except (OSError, UnicodeError, ValueError, csv.Error, zipfile.BadZipFile) as exc:
        return {"file": label, "error": type(exc).__name__}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local aggregate ADNI study-table inventory (never outputs participant identifiers)")
    parser.add_argument("--source", required=True, type=Path, help="Private local folder holding ADNI CSV/TSV files or downloads")
    parser.add_argument("--max-rows", type=int, default=0, help="Optional cap per file; 0 scans all rows")
    parser.add_argument("--output", type=Path, help="Optional local JSON output; keep under data/derived/ (ignored by Git)")
    args = parser.parse_args(argv)
    if not args.source.is_dir():
        parser.error("--source must be an existing directory")
    if args.max_rows < 0:
        parser.error("--max-rows must be >= 0")
    records = [inspect(path, member, args.max_rows) for path, member in sources(args.source)]
    report = {"dataset": "ADNI", "records": records, "files_checked": len(records),
              "recognized_priority_tables": sorted({name for name in PRIORITIES if any(
                  Path((r.get("file") or "").split("::")[-1]).stem.upper().startswith(name)
                  for r in records)}),
              "disclaimer": "Aggregate local schema inventory only. Does not establish clinical prediction accuracy or approved sharing rights."}
    print(json.dumps(report, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

if __name__ == "__main__":
    main()
