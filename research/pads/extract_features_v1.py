"""NeuroSense PADS features v1.
Trim initial 0.5 s. Split at gaps >30 ms. Interpolate only within
continuous segments to 100 Hz; use nonoverlapping 4-second windows.
Aggregate windows by median within each recording.
Engineering settings are experimental, not clinical thresholds.
"""
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

VERSION = "neurosense-pads-features-v1"
FS = 100
N = 400
CHANNELS = [
    "Time", "Accelerometer_X", "Accelerometer_Y", "Accelerometer_Z",
    "Gyroscope_X", "Gyroscope_Y", "Gyroscope_Z"
]

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def features(x):
    """Per-axis features; acceleration remains g, rotation rad/s."""
    result = {}
    freq = np.fft.rfftfreq(N, 1 / FS)
    taper = np.hanning(N)
    for col, channel in enumerate(CHANNELS[1:]):
        raw = x[:, col]
        centered = raw - raw.mean()
        psd = abs(np.fft.rfft(centered * taper)) ** 2
        psd /= FS * np.sum(taper ** 2)
        psd[1:-1] *= 2
        band = (freq >= 0.5) & (freq < 20)
        power = psd[band]
        total = power.sum()
        probability = power / total if total > 0 else None
        values = {
            "mean": raw.mean(),
            "std": raw.std(),
            "rms_centered": np.sqrt(np.mean(centered ** 2)),
            "iqr": np.percentile(raw, 75) - np.percentile(raw, 25),
            "derivative_rms": np.sqrt(np.mean((np.diff(raw) * FS) ** 2)),
            "peak_hz_0p5_20": (
                freq[band][np.argmax(power)] if total > 0 else None
            ),
            "spectral_entropy": (
                -np.sum(probability[probability > 0] *
                        np.log(probability[probability > 0])) /
                np.log(len(probability)) if probability is not None else None
            )
        }
        for low, high in [(0.5, 3), (3, 7), (7, 12), (12, 20)]:
            mask = (freq >= low) & (freq < high)
            values[f"power_{low}_{high}Hz"] = psd[mask].sum() * FS / N
        for name, value in values.items():
            result[f"{channel}__{name}"] = (
                float(value) if value is not None else None
            )
    return result

def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

def main():
    root = Path.home() / "BAINP_DATA/raw/pads/1.0.0"
    out = Path.home() / "BAINP_DATA/derived/pads" / (
        "features_v1_" +
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    out.mkdir(parents=True)
    results, coverage, provenance = [], [], []
    metadata_files = sorted((root / "movement").glob("observation_*.json"))
    if not metadata_files:
        raise SystemExit("PADS movement metadata not found.")

    for number, metadata in enumerate(metadata_files, 1):
        doc = json.loads(metadata.read_text(encoding="utf-8-sig"))
        provenance.append({
            "file": str(metadata.relative_to(root)),
            "sha256": digest(metadata)
        })
        for task in doc["session"]:
            for record in task["records"]:
                identity = {
                    "participant": str(doc["subject_id"]),
                    "task": task["record_name"],
                    "wrist": record["device_location"]
                }
                row = dict(identity, windows=0, status="ERROR", detail="")
                try:
                    path = (root / "movement" / record["file_name"]).resolve()
                    if not path.is_relative_to((root / "movement").resolve()):
                        raise ValueError("Invalid source path")
                    before = digest(path)
                    a = np.loadtxt(path, delimiter=",", ndmin=2)
                    if digest(path) != before:
                        raise ValueError("Source changed during reading")
                    provenance.append({
                        "file": str(path.relative_to(root)), "sha256": before
                    })
                    if record["channels"] != CHANNELS:
                        raise ValueError("Unexpected channels")
                    if record["units"] != ["s", "g", "g", "g",
                                           "rad/s", "rad/s", "rad/s"]:
                        raise ValueError("Unexpected units")
                    if float(doc["sampling_rate"]) != FS:
                        raise ValueError("Unexpected declared sampling rate")
                    if a.shape != (int(task["rows"]), 7):
                        raise ValueError("Unexpected dimensions")
                    if not np.isfinite(a).all():
                        raise ValueError("Nonfinite signal")
                    if not (np.diff(a[:, 0]) > 0).all():
                        raise ValueError("Invalid timestamps")

                    a = a[a[:, 0] >= a[0, 0] + 0.5]
                    splits = np.flatnonzero(np.diff(a[:, 0]) > 0.03) + 1
                    windows = []
                    for segment in np.split(a, splits):
                        if len(segment) < 2:
                            continue
                        start = float(segment[0, 0])
                        # Require a full 4-second observed span per window.
                        while start + 4 <= segment[-1, 0]:
                            grid = start + np.arange(N) / FS
                            x = np.column_stack([
                                np.interp(grid, segment[:, 0], segment[:, j])
                                for j in range(1, 7)
                            ])
                            windows.append(features(x))
                            start += 4

                    row.update(
                        windows=len(windows),
                        status="FEATURES_READY" if windows else "NO_4S_WINDOW",
                        detail=f"Retained gaps: {len(splits)}"
                    )
                    if windows:
                        aggregate = dict(identity, windows=len(windows))
                        for key in windows[0]:
                            values = [w[key] for w in windows if w[key] is not None]
                            aggregate[key] = (
                                float(np.median(values)) if values else ""
                            )
                        results.append(aggregate)
                except Exception as exc:
                    row["detail"] = str(exc)
                coverage.append(row)
        if number % 25 == 0:
            print(f"Processed {number}/{len(metadata_files)} participants",
                  flush=True)

    write_csv(out / "recording_features.csv", results)
    write_csv(out / "coverage.csv", coverage)
    write_csv(out / "input_hashes.csv", provenance)
    summary = {
        "version": VERSION,
        "participants_in_metadata": len(metadata_files),
        "recordings": len(coverage),
        "status_counts": dict(Counter(r["status"] for r in coverage)),
        "feature_rows": len(results),
        "python": sys.version,
        "numpy": np.__version__,
        "script_sha256": digest(Path(__file__)),
        "configuration": {
            "trim_seconds": 0.5, "split_gap_seconds": 0.03,
            "resample_hz": FS, "window_seconds": 4,
            "aggregation": "median per recording",
            "spectral_method": "Hann periodogram; constant detrending"
        },
        "limitations": [
            "Interpolation and window selection can affect spectra.",
            "No clinical thresholds or diagnosis.",
            "Keep every participant entirely within one evaluation fold.",
            "Assess missing-window patterns before model training."
        ]
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print("REPORT:", out)
    if summary["status_counts"].get("ERROR", 0):
        raise SystemExit(1)

if __name__ == "__main__":
    main()