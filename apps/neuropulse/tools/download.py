"""Materialize the pinned NEMAR mirror of OpenNeuro ds004504."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from pathlib import Path
import re
import shutil
import time
from tempfile import NamedTemporaryFile
import urllib.request

BASE = 'https://data.nemar.org/on004504/v1.0.0/'


def fetch(root, relative):
    path = root / relative
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix='.part', delete=False) as dest:
        temp = Path(dest.name)
    try:
        with urllib.request.urlopen(BASE + relative, timeout=60) as source, temp.open('wb') as dest:
            shutil.copyfileobj(source, dest)
            size = source.headers.get('Content-Length')
        if size is not None and temp.stat().st_size != int(size):
            raise OSError(f'Incomplete download of {relative}')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def recording(root, subject):
    relative = f'{subject}/eeg/{subject}_task-eyesclosed_eeg.set'
    for attempt in range(3):
        try:
            return fetch(root, relative)
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--limit-per-group', type=int, choices=range(5, 24))
    args = parser.parse_args()
    for name in ('participants.tsv', 'dataset_description.json'):
        fetch(args.root, name)
    with (args.root / 'participants.tsv').open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    subjects = [row['participant_id'] for row in rows]
    if len(set(subjects)) != 88 or len(subjects) != 88 or not all(re.fullmatch(r'sub-[0-9]{3}', s) for s in subjects):
        raise ValueError('Unexpected participant manifest.')
    if args.limit_per_group is not None:
        rows.sort(key=lambda row: row['participant_id'])
        subjects = [s for group in ('A', 'F', 'C')
                    for s in [r['participant_id'] for r in rows if r['Group']==group][:args.limit_per_group]]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for subject, _ in zip(subjects, pool.map(
            lambda s: recording(args.root, s), subjects
        )):
            print('Ready', subject, flush=True)


if __name__ == '__main__':
    main()
