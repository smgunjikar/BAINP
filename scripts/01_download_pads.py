"""Download and verify PADS 1.0.0 using its official public S3 mirror.

Run with Python 3.11 and boto3. No AWS account or credentials are used.
Default is a size preview; --download performs the transfer.
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import boto3
from botocore import UNSIGNED
from botocore.config import Config

BUCKET = "physionet-open"
PREFIX = "parkinsons-disease-smartwatch/1.0.0/"
SOURCE = "https://physionet.org/content/parkinsons-disease-smartwatch/1.0.0/"


def safe_path(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe source path: {relative}")
    destination = root.joinpath(*path.parts).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside data folder: {relative}")
    return destination


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root = args.data_root.expanduser().resolve()
    if any("onedrive" in part.lower() for part in root.parts):
        raise SystemExit("Choose a data root outside OneDrive.")
    if any((parent / ".git").exists() for parent in [root, *root.parents]):
        raise SystemExit("Choose a data root outside a Git repository.")
    target = root / "raw" / "pads" / "1.0.0"
    client = boto3.client("s3", region_name="us-east-1", config=Config(
        signature_version=UNSIGNED, retries={"max_attempts": 8, "mode": "standard"},
        connect_timeout=30, read_timeout=120))
    objects = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIX):
        objects.extend(obj for obj in page.get("Contents", []) if not obj["Key"].endswith("/"))
    if not objects:
        raise SystemExit("No source files found; nothing downloaded.")
    total = sum(obj["Size"] for obj in objects)
    print(f"Dataset: PADS 1.0.0\nFiles: {len(objects)}\nSize: {total / 1024**3:.2f} GiB")
    print(f"Destination: {target}\nSource: {SOURCE}")
    print("License: CC BY-NC-SA 4.0. Research use; retain attribution and license.")
    if not args.download:
        print("PREVIEW ONLY. Add --download to begin.")
        return
    target.mkdir(parents=True, exist_ok=True)
    remaining = sum(obj["Size"] for obj in objects
                    if not (p := safe_path(target, obj["Key"][len(PREFIX):])).is_file()
                    or p.stat().st_size != obj["Size"])
    if shutil.disk_usage(target).free < remaining + 1024**3:
        raise SystemExit("Insufficient free space: leave at least 1 GiB beyond pending downloads.")
    # Invalidate any previous success record before checking/downloading again.
    report = root / "manifests" / "pads-1.0.0-download.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"status": "in_progress", "source": SOURCE}), encoding="utf-8")
    for index, obj in enumerate(objects, 1):
        relative = obj["Key"][len(PREFIX):]
        destination = safe_path(target, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file() or destination.stat().st_size != obj["Size"]:
            partial = destination.with_name(destination.name + ".part")
            client.download_file(BUCKET, obj["Key"], str(partial))
            if partial.stat().st_size != obj["Size"]:
                raise RuntimeError(f"Size mismatch: {relative}")
            partial.replace(destination)
        if index % 100 == 0 or index == len(objects):
            print(f"Downloaded/size-checked {index}/{len(objects)}", flush=True)
    sums = target / "SHA256SUMS.txt"
    if not sums.is_file():
        raise RuntimeError("Publisher checksum manifest missing; cannot verify completion.")
    verified = 0
    for line in sums.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        relative = relative.lstrip("*")
        if len(expected) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected):
            raise ValueError("Unrecognized checksum entry; stop for inspection.")
        destination = safe_path(target, relative)
        if not destination.is_file():
            raise RuntimeError(f"Checksum-listed file missing: {relative}")
        if sha256(destination) != expected.lower():
            key = PREFIX + destination.relative_to(target).as_posix()
            partial = destination.with_name(destination.name + ".part")
            client.download_file(BUCKET, key, str(partial))
            if sha256(partial) != expected.lower():
                raise RuntimeError(f"Checksum mismatch after retry: {relative}")
            partial.replace(destination)
        verified += 1
        if verified % 500 == 0:
            print(f"SHA-256 verified: {verified}", flush=True)
    if not verified:
        raise RuntimeError("No checksums verified.")
    manifest = {"status": "complete", "dataset": "PADS", "version": "1.0.0",
                "source": SOURCE, "s3_source": f"s3://{BUCKET}/{PREFIX}",
                "license": "CC BY-NC-SA 4.0", "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "destination": str(target), "file_count": len(objects), "bytes": total,
                "publisher_checksums_verified": verified,
                "checksum_manifest_sha256": sha256(sums)}
    report.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"SUCCESS: PADS downloaded; {verified} publisher checksums verified.")
    print(f"Manifest: {report}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Stopped. Rerun the same command to reuse completed files.")
    except Exception as exc:
        raise SystemExit(f"DOWNLOAD FAILED: {exc}\nRerun to retry. No success is recorded until verification passes.")
