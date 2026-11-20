"""Read OASIS-2 MRI volumes without modifying source files."""

import argparse
import csv
import gc
import json
import re
import warnings
from collections import Counter
from pathlib import Path

import nibabel as nib
import numpy as np


def check_image(path, source):
    result = {
        "relative_path": str(path.relative_to(source)),
        "session": "",
        "status": "PASS",
        "shape": "",
        "voxel_sizes": "",
        "image_class": "",
        "nonfinite_voxels": "",
        "minimum": "",
        "maximum": "",
        "warnings": "",
        "details": "",
    }

    match = re.search(r"OAS2_\d+_MR\d+", str(path), re.IGNORECASE)
    if match:
        result["session"] = match.group().upper()

    flags = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            image = nib.load(str(path), mmap=False)
            result["image_class"] = type(image).__name__
            result["shape"] = "x".join(map(str, image.shape))

            zooms = image.header.get_zooms()[:3]
            result["voxel_sizes"] = ",".join(map(str, zooms))

            if len(image.shape) < 3 or any(n <= 0 for n in image.shape):
                flags.append("invalid_or_nonvolumetric_shape")

            if (
                len(zooms) != 3
                or not np.all(np.isfinite(zooms))
                or any(z <= 0 for z in zooms)
            ):
                flags.append("invalid_voxel_sizes")

            # Forces reading the full voxel payload, one image at a time.
            data = image.get_fdata(dtype=np.float32, caching="unchanged")
            finite = np.isfinite(data)
            nonfinite = int(data.size - np.count_nonzero(finite))
            result["nonfinite_voxels"] = nonfinite

            if nonfinite:
                flags.append("nonfinite_voxels")

            if data.size == 0:
                flags.append("empty_array")
            elif np.any(finite):
                values = data[finite]
                low = float(values.min())
                high = float(values.max())
                result["minimum"] = low
                result["maximum"] = high
                if low == high:
                    flags.append("constant_volume")
                del values
            else:
                flags.append("no_finite_voxels")

            result["warnings"] = " | ".join(
                sorted({str(item.message) for item in caught})
            )
            if caught:
                flags.append("reader_warning")

            del data, finite, image

        if flags:
            result["status"] = "REVIEW"
            result["details"] = ";".join(flags)

    except Exception as exc:
        result["status"] = "FAIL"
        result["details"] = f"{type(exc).__name__}: {exc}"

    gc.collect()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root", type=Path,
        default=Path.home() / "BAINP_DATA"
    )
    args = parser.parse_args()

    source = args.data_root / "raw/oasis2/extracted/part2"
    output = args.data_root / "derived/oasis2/mri_validation/part2"

    if not source.is_dir():
        raise FileNotFoundError(f"Extraction folder missing: {source}")

    all_files = sorted(p for p in source.rglob("*") if p.is_file())

    # Read each IMG/HDR pair once through its header.
    images = [
        p for p in all_files
        if p.name.lower().endswith(
            (".hdr", ".hdr.gz", ".nii", ".nii.gz")
        )
    ]
    if not images:
        raise RuntimeError("No supported MRI headers or NIfTI files found.")

    # Track compressed files not covered by the image reader.
    other_gzip = [
        str(p.relative_to(source))
        for p in all_files
        if p.name.lower().endswith(".gz")
        and not p.name.lower().endswith(
            (".hdr.gz", ".img.gz", ".nii.gz")
        )
    ]

    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "image_readability.csv"
    statuses = Counter()
    sessions = set()
    flagged_sessions = set()

    print(f"Image volumes to check: {len(images):,}")
    print("Reading source files only. This may take several minutes.")

    with report_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = None
        for index, path in enumerate(images, start=1):
            result = check_image(path, source)
            if writer is None:
                writer = csv.DictWriter(handle, fieldnames=list(result))
                writer.writeheader()
            writer.writerow(result)
            handle.flush()

            statuses[result["status"]] += 1
            if result["session"]:
                sessions.add(result["session"])
                if result["status"] != "PASS":
                    flagged_sessions.add(result["session"])

            if index % 25 == 0 or index == len(images):
                print(
                    f"Checked {index:,}/{len(images):,} | "
                    f"PASS={statuses['PASS']} "
                    f"REVIEW={statuses['REVIEW']} "
                    f"FAIL={statuses['FAIL']}",
                    flush=True,
                )

    summary = {
        "volumes_checked": len(images),
        "pass": statuses["PASS"],
        "review": statuses["REVIEW"],
        "fail": statuses["FAIL"],
        "recognized_sessions": len(sessions),
        "sessions_with_review_or_failure": len(flagged_sessions),
        "other_gzip_files": other_gzip,
        "numpy_version": np.__version__,
        "nibabel_version": nib.__version__,
        "scope": "Technical readability only; not visual or scientific QC.",
    }

    with (output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print("\nFINAL SUMMARY")
    for key in (
        "volumes_checked", "pass", "review", "fail",
        "recognized_sessions", "sessions_with_review_or_failure",
    ):
        print(f"{key}: {summary[key]:,}")

    print(f"Other gzip files requiring identification: {len(other_gzip)}")
    for name in other_gzip:
        print(f"  {name}")

    print(f"\nDetailed report: {report_path}")
    print(f"Summary: {output / 'summary.json'}")
    print("Source files unchanged.")
    print("PASS does not establish correct orientation or image quality.")


if __name__ == "__main__":
    main()