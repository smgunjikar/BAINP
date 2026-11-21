"""Build a descriptive OASIS-2 longitudinal pair table without imputation."""

import argparse
import csv
import json
import math
from pathlib import Path


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def numeric(value):
    if value is None or str(value).strip() == "":
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite numeric value.")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root", type=Path,
        default=Path.home() / "BAINP_DATA",
    )
    args = parser.parse_args()
    root = args.data_root

    source = root / "derived/oasis2/longitudinal_audit/combined"
    destination = root / "derived/oasis2/visit_pairs"
    visits = read_csv(source / "matched_clinical_sessions.csv")
    pairs = read_csv(source / "candidate_visit_pairs.csv")

    by_session = {}
    for visit in visits:
        session = visit["session"]
        if session in by_session:
            raise ValueError(f"Duplicate session in input: {session}")
        by_session[session] = visit

    fields = ["age", "educ", "ses", "mmse", "cdr", "etiv", "nwbv", "asf"]
    outcome_fields = ["mmse", "cdr", "nwbv"]
    output_rows = []
    seen_pairs = set()

    for pair in pairs:
        earlier_id = pair["earlier_session"]
        later_id = pair["later_session"]
        key = (earlier_id, later_id)
        if key in seen_pairs:
            raise ValueError("Duplicate visit pair.")
        seen_pairs.add(key)

        earlier = by_session[earlier_id]
        later = by_session[later_id]
        subject = pair["subject"]

        if earlier["subject"] != subject or later["subject"] != subject:
            raise ValueError("Participant mismatch within a pair.")

        first_day = numeric(earlier["mr_delay"])
        second_day = numeric(later["mr_delay"])
        if first_day is None or second_day is None:
            raise ValueError("Missing visit timing.")
        days = second_day - first_day
        if days <= 0:
            raise ValueError("Nonpositive follow-up interval.")

        recorded_days = numeric(pair["interval_days"])
        if recorded_days is None or not math.isclose(
            days, recorded_days, abs_tol=1e-6
        ):
            raise ValueError("Interval disagrees with source visit table.")

        result = {
            "subject": subject,
            "earlier_session": earlier_id,
            "later_session": later_id,
            "interval_days": days,
            "interval_years": days / 365.25,
            "pair_status": "CANDIDATE",
            "raw_mri_qc_approved": False,
        }

        for field in fields:
            result[f"earlier_{field}"] = numeric(earlier[field])

        for field in outcome_fields:
            before = numeric(earlier[field])
            after = numeric(later[field])
            result[f"later_{field}"] = after
            result[f"delta_{field}"] = (
                after - before
                if before is not None and after is not None
                else None
            )

        # CDR is retained as an ordinal score; no annualized CDR rate.
        result["mmse_pair_complete"] = (
            result["earlier_mmse"] is not None
            and result["later_mmse"] is not None
        )
        result["cdr_pair_complete"] = (
            result["earlier_cdr"] is not None
            and result["later_cdr"] is not None
        )
        output_rows.append(result)

    if not output_rows:
        raise ValueError("No candidate pairs found.")

    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "oasis2_candidate_visit_pairs.csv"
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "participants": len({row["subject"] for row in output_rows}),
        "candidate_pairs": len(output_rows),
        "complete_mmse_pairs": sum(
            row["mmse_pair_complete"] for row in output_rows
        ),
        "complete_cdr_pairs": sum(
            row["cdr_pair_complete"] for row in output_rows
        ),
        "pairs_missing_earlier_ses": sum(
            row["earlier_ses"] is None for row in output_rows
        ),
        "imputation_performed": False,
        "model_trained": False,
        "raw_mri_qc_approved": False,
        "change_definition": "Later minus earlier; descriptive only.",
        "split_requirement": "Keep every visit of a participant in one split.",
        "feature_warning": (
            "Later values, deltas, and observed follow-up interval must not "
            "automatically become baseline prediction features."
        ),
    }
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("\nVISIT-PAIR TABLE SUMMARY")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"\nOutput: {output_path}")
    print("Source data and MRI QC trackers unchanged.")


if __name__ == "__main__":
    main()