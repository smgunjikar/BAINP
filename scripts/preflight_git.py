"""Refuse common accidental commits of sensitive data and model/scan files.

Checks file *paths only*, not content. Must still review `git diff --cached`.
"""
from __future__ import annotations
import fnmatch
from pathlib import PurePosixPath
import subprocess
import sys

BLOCKED_SUFFIXES = (
    '.nii', '.nii.gz', '.hdr', '.img', '.dcm', '.edf', '.fif',
    '.mat', '.set', '.vhdr', '.eeg', '.npy', '.npz', '.parquet',
    '.pt', '.pth', '.joblib', '.pkl', '.sqlite', '.db'
)

def staged_paths():
    result = subprocess.run(['git', 'diff', '--cached', '--name-only', '-z'],
                            capture_output=True, check=True)
    return [b.decode('utf-8', 'replace').replace('\\', '/')
            for b in result.stdout.split(b'\0') if b]

def is_forbidden(name: str) -> bool:
    s = name.lower().lstrip('./')
    parts = PurePosixPath(s).parts
    if s.startswith('data/') and not (
        s.startswith('data/synthetic/') or s.startswith('data/manifests/')
        or s == 'data/readme.md'
    ):
        return True
    if 'private' in parts or 'secrets' in parts:
        return True
    if any(s.endswith(x) for x in BLOCKED_SUFFIXES):
        return True
    base = PurePosixPath(s).name
    if base == '.env' or (base.startswith('.env.') and not base.endswith('.example')):
        return True
    return False

if __name__ == '__main__':
    try:
        paths=staged_paths()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('No Git index found; run this inside your cloned Git repository.')
        sys.exit(2)
    bad=[p for p in paths if is_forbidden(p)]
    if bad:
        print('BLOCKED: potentially restricted/sensitive files staged:')
        for p in bad: print('  -',p)
        sys.exit(1)
    print(f'Preflight: {len(paths)} staged files pass path-based checks.')
    print('IMPORTANT: inspect contents for real identifiers or secrets before committing.')
