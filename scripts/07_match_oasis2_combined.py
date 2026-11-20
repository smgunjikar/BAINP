"""Match OASIS-2 Combined dataset MRI sessions to the clinical workbook."""

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook


SESSION_PATTERN = re.compile(r"^OAS2_(\d+)_MR(\d+)$", re.IGNORECASE)


def normalize_session(value):
    text = str(value or "").strip().upper()
    match = SESSION_PATTERN.fullmatch(text)
    if not match:
        return None
    return f"OAS2_{match.group(1)}_MR{int(match.group(2))}"


def subject_from_session(session):
    return session.rsplit("_MR", 1)[0]


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path.home() / "BAINP_DATA",
    )
    args = parser.parse_args()
    root = args.data_root.resolve()

    inventory = (
        root / "derived/oasis2/inventory/combined_sessions.csv"
    )
    clinical_folder = root / "raw/oasis2/clinical"
    output = root / "derived/oasis2/clinical_match_combined"

    if not inventory.is_file():
        raise FileNotFoundError(f"Session inventory missing: {inventory}")

    workbooks = sorted(
        p for p in clinical_folder.glob("*.xlsx")
        if not p.name.startswith("~$")
    )
    if len(workbooks) != 1:
        raise RuntimeError(
            f"Expected one clinical XLSX; found {len(workbooks)}. "
            "Keep the intended OASIS-2 workbook in the clinical folder."
        )
    workbook_path = workbooks[0]

    # Read the existing extraction inventory.
    inventory_ids = []
    with inventory.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = {
            name.strip().lower(): name
            for name in (reader.fieldnames or [])
        }
        if "session" not in columns:
            raise ValueError("Inventory must contain a 'session' column.")

        for row_number, row in enumerate(reader, start=2):
            session = normalize_session(row[columns["session"]])
            if session is None:
                raise ValueError(
                    f"Invalid session identifier at inventory row {row_number}."
                )
            inventory_ids.append(session)

    if not inventory_ids:
        raise ValueError("Session inventory is empty.")

    inventory_counts = Counter(inventory_ids)
    available = set(inventory_ids)

    # Discover the MRI-ID column from its values, rather than assuming
    # an exact spreadsheet header or sheet name.
    workbook = load_workbook(
        workbook_path, read_only=True, data_only=True
    )
    candidates = []

    try:
        for sheet in workbook.worksheets:
            per_column = {}
            for row in sheet.iter_rows(values_only=True):
                for column_index, value in enumerate(row):
                    session = normalize_session(value)
                    if session:
                        per_column.setdefault(column_index, []).append(session)

            for column_index, ids in per_column.items():
                candidates.append({
                    "sheet": sheet.title,
                    "column": column_index + 1,
                    "ids": ids,
                    "unique_count": len(set(ids)),
                })
    finally:
        workbook.close()

    if not candidates:
        raise ValueError(
            "No OASIS-2 MRI session identifiers found in the workbook."
        )

    candidates.sort(key=lambda item: item["unique_count"], reverse=True)
    best = candidates[0]

    if (
        len(candidates) > 1
        and candidates[1]["unique_count"] == best["unique_count"]
    ):
        raise ValueError(
            "Multiple equally plausible MRI-ID columns found. "
            "The workbook layout needs inspection before matching."
        )

    clinical_counts = Counter(best["ids"])
    clinical = set(clinical_counts)
    matched = available & clinical
    unmatched_inventory = available - clinical
    absent_from_part1 = clinical - available

    clinical_subjects = sorted({
        subject_from_session(session) for session in clinical
    })
    clinical_visits = Counter(
        subject_from_session(session) for session in clinical
    )
    matched_visits = Counter(
        subject_from_session(session) for session in matched
    )

    participant_rows = []
    for subject in clinical_subjects:
        total = clinical_visits[subject]
        present = matched_visits[subject]
        participant_rows.append({
            "subject": subject,
            "clinical_sessions": total,
            "combined_matched_sessions": present,
            "clinical_sessions_absent_from_part1": total - present,
            "at_least_two_combined_sessions": present >= 2,
            "additional_sessions_to_reach_two": (
                max(0, 2 - present) if total >= 2 else ""
            ),
        })

    session_rows = []
    for session in sorted(available | clinical):
        in_inventory = session in available
        in_clinical = session in clinical
        if in_inventory and in_clinical:
            status = "matched"
        elif in_inventory:
            status = "inventory_only"
        else:
            status = "clinical_only_absent_from_part1"

        session_rows.append({
            "session": session,
            "subject": subject_from_session(session),
            "in_combined_inventory": in_inventory,
            "in_clinical_workbook": in_clinical,
            "status": status,
            "clinical_rows_for_session": clinical_counts[session],
        })

    missing_rows = [
        {
            "session": session,
            "subject": subject_from_session(session),
            "combined_matched_sessions_for_subject":
                matched_visits[subject_from_session(session)],
        }
        for session in sorted(absent_from_part1)
    ]

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "clinical_workbook": str(workbook_path),
        "clinical_sheet": best["sheet"],
        "clinical_mri_id_column_number": best["column"],
        "combined_inventory": str(inventory),
        "inventory_rows": len(inventory_ids),
        "inventory_unique_sessions": len(available),
        "inventory_duplicate_session_ids": sum(
            count > 1 for count in inventory_counts.values()
        ),
        "clinical_unique_sessions": len(clinical),
        "clinical_unique_participants": len(clinical_subjects),
        "clinical_duplicate_session_ids": sum(
            count > 1 for count in clinical_counts.values()
        ),
        "matched_sessions": len(matched),
        "inventory_sessions_without_clinical_match": len(unmatched_inventory),
        "clinical_sessions_absent_from_part1": len(absent_from_part1),
        "participants_with_zero_matched_sessions": sum(
            matched_visits[s] == 0 for s in clinical_subjects
        ),
        "participants_with_one_matched_session": sum(
            matched_visits[s] == 1 for s in clinical_subjects
        ),
        "participants_with_at_least_two_matched_sessions": sum(
            matched_visits[s] >= 2 for s in clinical_subjects
        ),
        "participants_with_at_least_three_matched_sessions": sum(
            matched_visits[s] >= 3 for s in clinical_subjects
        ),
        "participants_with_all_clinical_sessions_in_part1": sum(
            matched_visits[s] == clinical_visits[s]
            for s in clinical_subjects
        ),
    }

    output.mkdir(parents=True, exist_ok=True)

    write_csv(
        output / "combined_session_match.csv",
        list(session_rows[0]),
        session_rows,
    )
    write_csv(
        output / "combined_participant_coverage.csv",
        list(participant_rows[0]),
        participant_rows,
    )
    write_csv(
        output / "clinical_sessions_absent_from_part1.csv",
        ["session", "subject", "combined_matched_sessions_for_subject"],
        missing_rows,
    )
    with (output / "combined_match_summary.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(summary, handle, indent=2)

    print("\nOASIS-2 COMBINED: CLINICAL SESSION MATCH")
    print("Source files unchanged. No participant values printed.\n")
    for key, value in summary.items():
        if isinstance(value, int):
            print(f"{key}: {value:,}")

    if unmatched_inventory:
        print("\nREVIEW: Some extracted sessions have no clinical match.")
    if summary["clinical_duplicate_session_ids"]:
        print("REVIEW: Duplicate clinical MRI IDs require review before joins.")

    print(f"\nReports saved to: {output}")
    print(
        "\nTwo matched sessions establish candidate longitudinal coverage only."
        "\nVisit timing, clinical completeness, MRI readability and image quality"
        "\nstill require validation. Missing sessions are not yet confirmed"
        "\nto be available in the extracted dataset."
    )


if __name__ == "__main__":
    main()