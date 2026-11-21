"""Create local OASIS-2 acquisition review sheets; never modify raw images."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np


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
    parser.add_argument(
        "--all", action="store_true",
        help="Create review sheets for every session instead of a sample.",
    )
    args = parser.parse_args()
    root = args.data_root

    grouped = defaultdict(list)
    for part in ("part1", "part2"):
        inventory = root / f"derived/oasis2/inventory/{part}_files.csv"
        source = (root / f"raw/oasis2/extracted/{part}").resolve()

        with inventory.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                relative = row["relative_path"].replace("\\", "/")
                if not relative.lower().endswith(
                    (".hdr", ".hdr.gz", ".nii", ".nii.gz")
                ):
                    continue
                session = row.get("session", "").strip()
                if not session:
                    raise ValueError("Image inventory contains a missing session.")
                path = (source / relative).resolve()
                if not path.is_relative_to(source) or not path.is_file():
                    raise ValueError("Invalid image path in inventory.")
                grouped[session].append((part, path))

    if not grouped:
        raise ValueError("No MRI volumes found.")

    # Deterministic sample: unusual acquisition counts, then spread
    # through the remaining session IDs. No diagnostic labels are used.
    ordered = sorted(grouped)
    unusual = [s for s in ordered if len(grouped[s]) not in (3, 4)]

    if args.all:
        selected = ordered
        mode = "all"
    else:
        selected = list(unusual)
        remaining = [s for s in ordered if s not in selected]
        slots = max(0, min(12, len(ordered)) - len(selected))
        if slots:
            indices = np.linspace(0, len(remaining) - 1, slots, dtype=int)
            selected.extend(remaining[i] for i in indices)
        selected = sorted(set(selected))
        mode = "sample"

    output = root / f"derived/oasis2/visual_review/{mode}"
    output.mkdir(parents=True, exist_ok=True)
    metadata = []
    failures = []
    review_rows = []

    print(f"Sessions selected: {len(selected)}", flush=True)
    print("Creating voxel-axis views; anatomical orientation is unverified.")

    for index, session in enumerate(selected, start=1):
        acquisitions = sorted(grouped[session], key=lambda item: str(item[1]))
        fig, axes = plt.subplots(
            len(acquisitions), 9,
            figsize=(21, 3 * len(acquisitions)),
            squeeze=False,
        )
        session_errors = 0

        for row_index, (part, path) in enumerate(acquisitions):
            panels = axes[row_index]
            for panel in panels:
                panel.axis("off")
            try:
                image = nib.load(str(path), mmap=False)
                data = image.get_fdata(dtype=np.float32, caching="unchanged")

                # Remove only trailing singleton dimensions.
                while data.ndim > 3 and data.shape[-1] == 1:
                    data = data[..., 0]
                if data.ndim != 3:
                    raise ValueError(f"Expected a 3D volume; found {data.shape}")

                zooms = image.header.get_zooms()[:3]
                finite_nonzero = data[np.isfinite(data) & (data != 0)]
                if not finite_nonzero.size:
                    raise ValueError("No finite nonzero voxels.")
                low, high = np.percentile(finite_nonzero, [1, 99])
                if high <= low:
                    low, high = float(data.min()), float(data.max())
                del finite_nonzero

                metadata.append({
                    "session": session,
                    "part": part,
                    "filename": path.name,
                    "relative_path": str(path.relative_to(root)),
                    "image_class": type(image).__name__,
                    "shape": "x".join(map(str, data.shape)),
                    "voxel_sizes": ",".join(map(str, zooms)),
                    "affine_from_reader": json.dumps(image.affine.tolist()),
                    "orientation_verified": False,
                })

                column = 0
                for axis in range(3):
                    for fraction in (0.35, 0.50, 0.65):
                        position = round((data.shape[axis] - 1) * fraction)
                        plane = np.take(data, position, axis=axis)
                        panels[column].imshow(
                            plane.T,
                            cmap="gray",
                            origin="lower",
                            vmin=low,
                            vmax=high,
                            aspect="equal",
                            interpolation="nearest",
                        )
                        panels[column].set_title(
                            f"Voxel axis {axis}, slice {position}", fontsize=8
                        )
                        column += 1

                panels[0].text(
                    0, -0.12,
                    f"{path.name}\nshape={data.shape}; spacing={zooms}",
                    transform=panels[0].transAxes,
                    fontsize=8,
                )
                del data, image

            except Exception as exc:
                session_errors += 1
                failures.append({
                    "session": session,
                    "filename": path.name,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                panels[0].text(
                    0.05, 0.5, "RENDER FAILED\nSee rendering_errors.csv",
                    transform=panels[0].transAxes,
                    color="red", fontsize=9,
                )

        fig.suptitle(
            f"{session} — {len(acquisitions)} acquisitions\n"
            "Voxel-axis inspection only: orientation unverified; "
            "pixel spacing not corrected; per-volume contrast",
            fontsize=12,
        )
        fig.tight_layout(rect=(0, 0.03, 1, 0.93))
        sheet = output / f"{session}_review.png"
        fig.savefig(sheet, dpi=110)
        plt.close(fig)

        review_rows.append({
            "session": session,
            "review_sheet": sheet.name,
            "acquisitions": len(acquisitions),
            "render_errors": session_errors,
            "review_status": "NOT_REVIEWED",
            "reviewer": "",
            "notes": "",
        })
        print(f"Sheets created: {index}/{len(selected)}", flush=True)

    if metadata:
        write_csv(output / "acquisition_metadata.csv",
                  list(metadata[0]), metadata)

    write_csv(
        output / "rendering_errors.csv",
        ["session", "filename", "error"], failures,
    )

    # Preserve manual review entries when the script is rerun.
    review_path = output / "review_tracking.csv"
    if not review_path.exists():
        write_csv(review_path, list(review_rows[0]), review_rows)

    print("\nVISUAL REVIEW GENERATION SUMMARY")
    print(f"Sessions selected: {len(selected)}")
    print(f"Acquisitions rendered: {len(metadata)}")
    print(f"Rendering failures: {len(failures)}")
    print("Shapes:", dict(Counter(row["shape"] for row in metadata)))
    print("Voxel sizes:", dict(Counter(row["voxel_sizes"] for row in metadata)))
    print(f"Output folder: {output}")
    print("Images generated, NOT quality-approved. Raw files unchanged.")


if __name__ == "__main__":
    main()