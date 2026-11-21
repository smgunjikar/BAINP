"""Audit OASIS-2 orientation headers and initialize acquisition QC tracking."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import nibabel as nib
import numpy as np


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def matrix_text(matrix):
    return "" if matrix is None else json.dumps(matrix.tolist())


def valid_affine(matrix):
    return (
        matrix is not None
        and np.all(np.isfinite(matrix))
        and np.linalg.matrix_rank(matrix[:3, :3]) == 3
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root", type=Path,
        default=Path.home() / "BAINP_DATA",
    )
    args = parser.parse_args()
    root = args.data_root.resolve()

    metadata = root / "derived/oasis2/visual_review/all_v2/acquisition_metadata.csv"
    output = root / "derived/oasis2/header_audit"
    output.mkdir(parents=True, exist_ok=True)

    with metadata.open(newline="", encoding="utf-8-sig") as handle:
        acquisitions = list(csv.DictReader(handle))

    if not acquisitions:
        raise ValueError("Acquisition metadata is empty.")

    paths = [row["relative_path"] for row in acquisitions]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate acquisition paths in metadata.")

    audit = []
    tracking = []
    counts = Counter()
    qcodes = Counter()
    scodes = Counter()
    axis_counts = Counter()
    unit_counts = Counter()

    preliminary_notes = {
        "OAS2_0099_MR1":
            "Preliminary montage observation: brightness variation; "
            "full-volume review required.",
        "OAS2_0061_MR3":
            "Preliminary montage observation: grainy appearance; "
            "two acquisitions; full-volume review required.",
    }

    for index, item in enumerate(acquisitions, start=1):
        relative = item["relative_path"].replace("\\", "/")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Acquisition path escapes data root.")

        row = {
            "session": item["session"],
            "filename": item["filename"],
            "relative_path": relative,
            "status": "HEADER_CHECKED",
            "qform_code": "",
            "sform_code": "",
            "selected_affine_source": "",
            "axis_codes_from_header": "",
            "spatial_units": "",
            "qform_sform_close": "",
            "qform": "",
            "sform": "",
            "selected_affine": "",
            "notes": "",
        }

        try:
            image = nib.load(str(path), mmap=False)
            qform, qcode = image.get_qform(coded=True)
            sform, scode = image.get_sform(coded=True)
            qcode, scode = int(qcode), int(scode)

            row["qform_code"] = qcode
            row["sform_code"] = scode
            row["qform"] = matrix_text(qform)
            row["sform"] = matrix_text(sform)
            row["selected_affine"] = matrix_text(image.affine)
            row["spatial_units"] = image.header.get_xyzt_units()[0]

            qcodes[str(qcode)] += 1
            scodes[str(scode)] += 1
            unit_counts[row["spatial_units"]] += 1

            flags = []
            if scode:
                row["selected_affine_source"] = "sform"
            elif qcode:
                row["selected_affine_source"] = "qform"
            else:
                row["selected_affine_source"] = "fallback"
                flags.append("no_coded_qform_or_sform")

            if qcode and not valid_affine(qform):
                flags.append("invalid_coded_qform")
            if scode and not valid_affine(sform):
                flags.append("invalid_coded_sform")

            if qcode and scode:
                close = bool(np.allclose(
                    qform, sform, rtol=1e-5, atol=1e-4
                ))
                row["qform_sform_close"] = close
                if not close:
                    flags.append("qform_sform_differ_review_coordinate_spaces")

            if valid_affine(image.affine):
                codes = nib.aff2axcodes(image.affine)
                row["axis_codes_from_header"] = "".join(
                    code if code is not None else "?" for code in codes
                )
                axis_counts[row["axis_codes_from_header"]] += 1
            else:
                flags.append("invalid_selected_affine")

            if row["spatial_units"] == "unknown":
                flags.append("unknown_spatial_units")

            if flags:
                row["status"] = "REVIEW"
                row["notes"] = ";".join(flags)

        except Exception as exc:
            row["status"] = "ERROR"
            row["notes"] = f"{type(exc).__name__}: {exc}"

        counts[row["status"]] += 1
        audit.append(row)

        tracking.append({
            "session": item["session"],
            "filename": item["filename"],
            "relative_path": relative,
            "header_audit_status": row["status"],
            "visual_qc_status": "NOT_REVIEWED",
            "orientation_status": "UNVERIFIED",
            "preliminary_montage_note":
                preliminary_notes.get(item["session"], ""),
            "reviewer": "",
            "review_date": "",
            "review_notes": "",
            "acquisition_selected": "",
        })

        if index % 100 == 0 or index == len(acquisitions):
            print(f"Headers checked: {index}/{len(acquisitions)}", flush=True)

    write_csv(output / "orientation_headers.csv", list(audit[0]), audit)

    # Existing manual decisions must never be overwritten.
    tracker = output / "acquisition_qc_tracking.csv"
    tracker_created = not tracker.exists()
    if tracker_created:
        write_csv(tracker, list(tracking[0]), tracking)

    summary = {
        "acquisitions": len(acquisitions),
        "sessions": len({row["session"] for row in acquisitions}),
        "header_status_counts": dict(counts),
        "qform_code_counts": dict(qcodes),
        "sform_code_counts": dict(scodes),
        "header_axis_code_counts": dict(axis_counts),
        "spatial_unit_counts": dict(unit_counts),
        "tracker_created": tracker_created,
        "orientation_verified": False,
    }

    with (output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print("\nHEADER AUDIT SUMMARY")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"\nReports: {output}")
    if not tracker_created:
        print("Existing acquisition QC tracker preserved.")
    print("Header axis labels are metadata claims, not verified anatomy.")
    print("Different qform/sform matrices are review flags, not automatic failures.")
    print("Raw files unchanged. No acquisition selected or rejected.")


if __name__ == "__main__":
    main()