"""BAINP NeuroPulse P0.3: read-only EEGLAB pilot/batch technical QC.

Independent research utility. No diagnosis, no automatic QC clearance.
Python 3.11; MNE 1.13.x, NumPy 2.x, SciPy 1.15.x.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import mne
import numpy as np
from scipy.signal import welch

VERSION = "p03-set-batch-v1.0.1-jsonfix"
BANDS = {"delta_1_4": (1., 4.), "theta_4_8": (4., 8.),
         "alpha_8_13": (8., 13.), "beta_13_30": (13., 30.)}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_compatible(value):
    """Convert NumPy numeric outputs into strict JSON-compatible native values."""
    if isinstance(value, np.ndarray):
        return json_compatible(value.tolist())
    if isinstance(value, np.generic):
        return json_compatible(value.item())
    if isinstance(value, dict):
        return {str(k): json_compatible(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_compatible(v) for v in value]
    if isinstance(value, (float, int, str, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported report field type: {type(value).__name__}")


def write_new(path: Path, obj: dict) -> None:
    """Create file exclusively; never overwrite a previous result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(json_compatible(obj), indent=2, allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as f:
        f.write(payload)


def band_power(freq: np.ndarray, spectrum: np.ndarray, low: float, high: float) -> float | None:
    mask = (freq >= low) & (freq < high)
    if np.count_nonzero(mask) < 2:
        return None
    return float(np.trapezoid(spectrum[mask], freq[mask]))


def analyze(path: Path, dataset: Path, chunk_seconds: float, verify_hash: bool) -> dict:
    if path.is_symlink():
        raise ValueError("Symlink source refused; resolve DataLad content explicitly")
    initial_stat = path.stat()
    if initial_stat.st_size < 1024:
        raise ValueError("SET file too small to represent EEG payload")
    before = digest(path) if verify_hash else None
    raw = mne.io.read_raw_eeglab(str(path), preload=False, verbose="ERROR")
    sf = float(raw.info["sfreq"])
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    if not (math.isfinite(sf) and sf > 2 and len(picks) > 0 and raw.n_times > 0):
        raise ValueError("Invalid sampling rate, EEG channel count, or samples")
    # Band powers require Nyquist above the beta band upper bound.
    if sf <= 60:
        raise ValueError("Sampling rate insufficient for the defined 1–30 Hz bands")
    block_len = max(1, int(round(chunk_seconds * sf)))
    psd_sum = None
    f_ref = None
    segments = 0
    nonfinite_samples = 0
    channel_max_v = np.zeros(len(picks), dtype=float)
    channel_min_sd_v = np.full(len(picks), np.inf)
    for start in range(0, raw.n_times, block_len):
        stop = min(start + block_len, raw.n_times)
        arr = raw.get_data(picks=picks, start=start, stop=stop)
        if arr.shape[1] < 2 * sf:  # skip final short fragment for PSD, but inspect it for QC
            nonfinite_samples += int((~np.isfinite(arr)).sum())
            if arr.size:
                finite = np.where(np.isfinite(arr), arr, 0.)
                channel_max_v = np.maximum(channel_max_v, np.max(np.abs(finite), axis=1))
            continue
        nonfinite_samples += int((~np.isfinite(arr)).sum())
        finite = np.where(np.isfinite(arr), arr, 0.)
        channel_max_v = np.maximum(channel_max_v, np.max(np.abs(finite), axis=1))
        channel_min_sd_v = np.minimum(channel_min_sd_v, np.std(finite, axis=1))
        if not np.isfinite(arr).all():
            continue
        nperseg = min(int(2 * sf), arr.shape[1])
        freq, pxx = welch(arr, fs=sf, nperseg=nperseg, noverlap=nperseg // 2, axis=-1)
        if f_ref is None:
            f_ref = freq
            psd_sum = np.zeros_like(pxx)
        if len(freq) != len(f_ref) or not np.allclose(freq, f_ref):
            raise ValueError("PSD frequency grid mismatch")
        psd_sum += pxx
        segments += 1
    if segments == 0:
        raise ValueError("No finite >=2-second blocks available for PSD")
    mean_psd = psd_sum / segments
    band_means = {}
    for name, (low, high) in BANDS.items():
        values = [band_power(f_ref, spectrum, low, high) for spectrum in mean_psd]
        band_means[name + "_mean_v2"] = (float(np.mean(values)) if all(v is not None for v in values) else None)
    after_stat = path.stat()
    if (initial_stat.st_size, initial_stat.st_mtime_ns) != (after_stat.st_size, after_stat.st_mtime_ns):
        raise RuntimeError("Source metadata changed during processing")
    after = digest(path) if verify_hash else None
    if verify_hash and before != after:
        raise RuntimeError("Source bytes changed during processing")
    flags = []
    if nonfinite_samples:
        flags.append("NONFINITE_SAMPLES")
    if np.any(channel_max_v > 500e-6):
        flags.append("ABS_AMPLITUDE_OVER_500_UV_REVIEW")
    if np.any(channel_min_sd_v < 0.1e-6):
        flags.append("LOW_30S_VARIABILITY_REVIEW")
    return {
        "schema": VERSION, "created_utc": datetime.now(timezone.utc).isoformat(),
        "research_only": True, "clinical_qc_approved": False,
        "source_relative": str(path.relative_to(dataset)).replace("\\", "/"),
        "source_size_bytes": initial_stat.st_size,
        "source_sha256": before,
        "hash_verified_before_after": bool(verify_hash),
        "sfreq_hz": sf, "duration_s": raw.n_times / sf,
        "eeg_channels": [raw.ch_names[i] for i in picks],
        "eeg_channel_count": len(picks), "n_samples": int(raw.n_times),
        "segments_used": segments, "nonfinite_sample_count": nonfinite_samples,
        "max_abs_amplitude_v_by_channel": channel_max_v.tolist(),
        "minimum_chunk_sd_v_by_channel": [float(v) if math.isfinite(v) else None for v in channel_min_sd_v],
        "bands": band_means, "qc_review_flags": flags,
        "qc_note": "Heuristic research-review flags only; not validated artifact thresholds or clinical clearance. Absolute PSD values reflect original reference and preprocessing.",
        "preprocessing": "No re-reference or filters; MNE reader physical scaling, 2s Welch nperseg with 50% overlap; average of full chunks. Do not compare disease groups without harmonization.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--limit", type=int, default=1, help="1 for pilot; 88 for complete dataset")
    p.add_argument("--chunk-seconds", type=float, default=30.)
    p.add_argument("--no-hash", action="store_true", help="Not recommended; skips source hashing")
    args = p.parse_args()
    dataset = args.dataset.resolve(strict=True)
    out = args.output_dir.resolve()
    if not dataset.is_dir() or args.limit < 1 or not (2 <= args.chunk_seconds <= 120):
        p.error("Invalid dataset, limit, or chunk duration")
    if out == dataset or dataset in out.parents or out in dataset.parents:
        p.error("Output must be outside the raw dataset tree")
    sources = sorted(dataset.glob("sub-*/eeg/*_eeg.set"))
    if not sources:
        p.error("No sub-*/eeg/*_eeg.set files found")
    if args.limit > len(sources):
        p.error(f"Requested {args.limit}; only {len(sources)} found")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + os.urandom(4).hex()
    run_dir = out / ("set_batch_" + run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    summary = {"schema": VERSION, "dataset": str(dataset), "run_dir": str(run_dir),
               "files_discovered": len(sources), "selected": args.limit,
               "sha256_enabled": not args.no_hash, "results": []}
    for source in sources[:args.limit]:
        key = source.parent.parent.name
        dest = run_dir / f"{key}.json"
        try:
            item = analyze(source, dataset, args.chunk_seconds, not args.no_hash)
            write_new(dest, item)
            summary["results"].append({"subject": key, "status": "PROCESSED_REVIEW_REQUIRED", "report": str(dest), "flags": item["qc_review_flags"]})
        except Exception as exc:
            summary["results"].append({"subject": key, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        print(json.dumps(summary["results"][-1]), flush=True)
    write_new(run_dir / "batch_summary.json", summary)
    print("Summary:", run_dir / "batch_summary.json")
    if any(r["status"] == "FAILED" for r in summary["results"]):
        raise SystemExit(2)

if __name__ == "__main__":
    main()
