"""Create and verify float32 NIfTI derivatives for two review sessions."""

import argparse
import csv
import json
from pathlib import Path

import nibabel as nib
import numpy as np


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify(path, source, values):
    saved = nib.load(str(path), mmap=False)
    restored = saved.get_fdata(dtype=np.float32, caching="unchanged")

    require(saved.shape == source.shape, "Shape changed.")
    require(np.array_equal(restored, values), "Float32 voxel values changed.")
    require(
        np.allclose(saved.affine, source.affine, rtol=0, atol=1e-5),
        "Affine changed.",
    )
    require(
        np.allclose(
            saved.header.get_zooms(), source.header.get_zooms(),
            rtol=0, atol=1e-6,
        ),
        "Voxel spacing changed.",
    )
    require(
        saved.header.get_xyzt_units() == source.header.get_xyzt_units(),
        "Units changed.",
    )
    for form in ("qform", "sform"):
        require(
            int(saved.header[f"{form}_code"])
            == int(source.header[f"{form}_code"]),
            f"{form} code changed.",
        )
        require(
            np.allclose(
                getattr(saved, f"get_{form}")(),
                getattr(source, f"get_{form}")(),
                rtol=0, atol=1e-5,
            ),
            f"{form} matrix changed.",
        )
    require(
        nib.aff2axcodes(saved.affine) == nib.aff2axcodes(source.affine),
        "Header axis codes changed.",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root", type=Path,
        default=Path.home() / "BAINP_DATA",
    )
    args = parser.parse_args()
    root = args.data_root.resolve()
    metadata = root / (
        "derived/oasis2/visual_review/all_v2/acquisition_metadata.csv"
    )
    output = root / "derived/oasis2/conversion_pilot"
    wanted = {"OAS2_0099_MR1": 4, "OAS2_0061_MR3": 2}

    with metadata.open(newline="", encoding="utf-8-sig") as handle:
        rows = [
            row for row in csv.DictReader(handle)
            if row["session"] in wanted
        ]

    for session, expected in wanted.items():
        require(
            sum(row["session"] == session for row in rows) == expected,
            f"Unexpected acquisition count for {session}.",
        )

    output.mkdir(parents=True, exist_ok=True)
    results = []
    targets = set()

    for row in rows:
        source_path = (
            root / row["relative_path"].replace("\\", "/")
        ).resolve()
        require(source_path.is_relative_to(root), "Invalid source path.")
        require(source_path.is_file(), "Source image is missing.")

        folder = output / row["session"]
        folder.mkdir(parents=True, exist_ok=True)
        name = source_path.name.removesuffix(".hdr") + ".nii.gz"
        target = folder / name
        require(target not in targets, "Duplicate output path.")
        targets.add(target)

        source = nib.load(str(source_path), mmap=False)
        values = source.get_fdata(dtype=np.float32, caching="unchanged")
        require(np.all(np.isfinite(values)), "Nonfinite input voxels.")

        if target.exists():
            verify(target, source, values)
            action = "existing_verified"
        else:
            header = source.header.copy()
            header.set_data_dtype(np.float32)

            derivative = nib.Nifti1Image(
                values, source.affine, header=header
            )
            derivative.set_qform(
                source.get_qform(),
                code=int(source.header["qform_code"]),
            )
            derivative.set_sform(
                source.get_sform(),
                code=int(source.header["sform_code"]),
            )
            derivative.header.set_slope_inter(1.0, 0.0)

            temporary = folder / (name + ".partial.nii.gz")
            nib.save(derivative, str(temporary))
            verify(temporary, source, values)
            temporary.replace(target)
            action = "created_verified"

        results.append({
            "session": row["session"],
            "source": str(source_path.relative_to(root)),
            "output": str(target.relative_to(root)),
            "action": action,
            "storage_dtype": "float32",
            "voxel_roundtrip": "exact_against_float32_source",
            "geometry_preserved": True,
            "orientation_verified": False,
            "visual_qc_approved": False,
        })
        print(f"Verified {len(results)}/{len(rows)}", flush=True)
        del values, source

    manifest = output / "conversion_manifest.json"
    manifest.write_text(
        json.dumps({
            "nibabel_version": nib.__version__,
            "numpy_version": np.__version__,
            "operations": "Paired NIfTI to single-file float32 NIfTI",
            "resampling": False,
            "reorientation": False,
            "registration": False,
            "acquisitions": results,
        }, indent=2),
        encoding="utf-8",
    )

    print("\nCONVERSION PILOT SUMMARY")
    print(f"Sessions: {len(wanted)}")
    print(f"Verified acquisitions: {len(results)}")
    print("Voxel round-trip: exact against decoded float32 source")
    print("Shape, spacing, units, affines and transform codes: preserved")
    print("Raw source files: unchanged")
    print("Visual QC and anatomical orientation: still unverified")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()