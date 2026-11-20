"""Audit OASIS-2 clinical coverage and consecutive visit intervals."""

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from openpyxl import load_workbook


def clean(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def session_id(value):
    text = str(value or "").strip().upper()
    match = re.fullmatch(r"OAS2_(\d+)_MR(\d+)", text)
    if not match:
        return None
    return f"OAS2_{match.group(1)}_MR{int(match.group(2))}"


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root", type=Path,
        default=Path.home() / "BAINP_DATA",
    )
    args = parser.parse_args()
    root = args.data_root
    inventory = root / "derived/oasis2/inventory/combined_sessions.csv"
    output = root / "derived/oasis2/longitudinal_audit/combined"

    books = [
        p for p in (root / "raw/oasis2/clinical").glob("*.xlsx")
        if not p.name.startswith("~$")
    ]
    if len(books) != 1:
        raise RuntimeError("Expected exactly one OASIS-2 clinical XLSX.")

    with inventory.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if "session" not in (reader.fieldnames or []):
            raise ValueError("Inventory lacks the session column.")
        inventory_list = [session_id(row["session"]) for row in reader]

    if not inventory_list or None in inventory_list:
        raise ValueError("Inventory is empty or contains invalid session IDs.")
    if len(inventory_list) != len(set(inventory_list)):
        raise ValueError("Duplicate session IDs in inventory.")
    available = set(inventory_list)

    # Detect a header row rather than assuming its position.
    workbook = load_workbook(books[0], read_only=True, data_only=True)
    candidates = []
    try:
        for sheet in workbook.worksheets:
            for index, row in enumerate(
                sheet.iter_rows(values_only=True), start=1
            ):
                if index > 30:
                    break
                names = [clean(value) for value in row]
                if "mriid" in names and "mrdelay" in names:
                    if len([n for n in names if n]) != len(
                        set(n for n in names if n)
                    ):
                        raise ValueError("Duplicate normalized workbook headers.")
                    candidates.append((sheet.title, index, names))

        if len(candidates) != 1:
            raise ValueError(
                "Could not uniquely identify headers MRI ID and MR Delay."
            )

        sheet_name, header_row, names = candidates[0]
        positions = {name: i for i, name in enumerate(names) if name}
        fields = ["age", "educ", "ses", "mmse", "cdr", "etiv", "nwbv", "asf"]
        missing_columns = [name for name in fields if name not in positions]
        rows = []
        seen = set()

        for values in workbook[sheet_name].iter_rows(
            min_row=header_row + 1, values_only=True
        ):
            def get(name):
                index = positions.get(name)
                return (
                    values[index]
                    if index is not None and index < len(values)
                    else None
                )

            sid = session_id(get("mriid"))
            if sid not in available:
                continue
            if sid in seen:
                raise ValueError("Duplicate matched MRI ID in clinical workbook.")
            seen.add(sid)

            record = {
                "session": sid,
                "subject": sid.rsplit("_MR", 1)[0],
                "visit": number(get("visit")),
                "mr_delay": number(get("mrdelay")),
            }
            for field in fields:
                record[field] = number(get(field))
            rows.append(record)
    finally:
        workbook.close()

    if seen != available:
        raise ValueError(
            f"{len(available - seen)} inventory sessions lack a clinical row."
        )

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["subject"]].append(row)

    issues = []
    pairs = []
    intervals = []
    eligible_subjects = set()
    nonmonotonic_visit_subjects = 0

    for subject, visits in sorted(grouped.items()):
        # Exclude the whole participant from pairing if time is ambiguous.
        delays = [row["mr_delay"] for row in visits]
        reasons = []
        if any(delay is None for delay in delays):
            reasons.append("missing_or_invalid_mr_delay")
        elif any(delay < 0 for delay in delays):
            reasons.append("negative_mr_delay")
        elif len(set(delays)) != len(delays):
            reasons.append("duplicate_mr_delay")

        if reasons:
            issues.append({
                "subject": subject,
                "reason": ";".join(reasons),
            })
            continue

        ordered = sorted(visits, key=lambda row: row["mr_delay"])
        visit_numbers = [row["visit"] for row in ordered]
        if (
            all(value is not None for value in visit_numbers)
            and any(
                b <= a for a, b in zip(visit_numbers, visit_numbers[1:])
            )
        ):
            nonmonotonic_visit_subjects += 1
            issues.append({
                "subject": subject,
                "reason": "visit_number_order_conflicts_with_mr_delay",
            })
            continue

        for before, after in zip(ordered, ordered[1:]):
            days = after["mr_delay"] - before["mr_delay"]
            pair = {
                "subject": subject,
                "earlier_session": before["session"],
                "later_session": after["session"],
                "interval_days": days,
                "interval_years": round(days / 365.25, 4),
            }
            for field in fields:
                pair[f"{field}_both_present"] = (
                    before[field] is not None and after[field] is not None
                )
            pairs.append(pair)
            intervals.append(days)
            eligible_subjects.add(subject)

    completeness = [
        {
            "field": field,
            "column_present": field in positions,
            "present_numeric": sum(row[field] is not None for row in rows),
            "missing_or_nonnumeric": sum(row[field] is None for row in rows),
        }
        for field in fields
    ]

    # Broad review flags only; no values are automatically corrected.
    range_flags = Counter()
    for row in rows:
        for field, low, high in [
            ("age", 0, 120),
            ("educ", 0, 40),
            ("mmse", 0, 30),
            ("nwbv", 0, 1),
        ]:
            value = row[field]
            if value is not None and not low <= value <= high:
                range_flags[field] += 1
        if row["cdr"] is not None and row["cdr"] not in {0, 0.5, 1, 2, 3}:
            range_flags["cdr"] += 1
        for field in ["etiv", "asf"]:
            if row[field] is not None and row[field] <= 0:
                range_flags[field] += 1

    pair_fields = [
        "subject", "earlier_session", "later_session",
        "interval_days", "interval_years",
    ] + [f"{field}_both_present" for field in fields]

    summary = {
        "matched_sessions": len(rows),
        "matched_participants": len(grouped),
        "participants_with_candidate_pairs": len(eligible_subjects),
        "participants_excluded_from_pairing": len(grouped) - len(eligible_subjects),
        "consecutive_candidate_pairs": len(pairs),
        "visit_order_conflicts": nonmonotonic_visit_subjects,
        "minimum_interval_days": min(intervals) if intervals else None,
        "median_interval_days": median(intervals) if intervals else None,
        "maximum_interval_days": max(intervals) if intervals else None,
        "pairs_with_mmse_at_both_visits": sum(
            pair["mmse_both_present"] for pair in pairs
        ),
        "pairs_with_cdr_at_both_visits": sum(
            pair["cdr_both_present"] for pair in pairs
        ),
        "missing_columns": missing_columns,
        "broad_range_review_flags": dict(range_flags),
        "clinical_completeness": completeness,
    }

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "matched_clinical_sessions.csv", list(rows[0]), rows)
    write_csv(output / "candidate_visit_pairs.csv", pair_fields, pairs)
    write_csv(
        output / "participant_time_issues.csv",
        ["subject", "reason"], issues,
    )
    write_csv(
        output / "clinical_completeness.csv",
        ["field", "column_present", "present_numeric", "missing_or_nonnumeric"],
        completeness,
    )
    with (output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print("\nOASIS-2 COMBINED LONGITUDINAL AUDIT")
    for key, value in summary.items():
        if key != "clinical_completeness":
            print(f"{key}: {value}")

    print("\nCLINICAL COMPLETENESS")
    for row in completeness:
        print(
            f"{row['field']}: "
            f"present={row['present_numeric']}, "
            f"missing/invalid={row['missing_or_nonnumeric']}"
        )

    print(f"\nReports: {output}")
    print("Source files unchanged. No participant values printed.")
    print("Candidate pairs are not yet a validated modeling cohort.")


if __name__ == "__main__":
    main()