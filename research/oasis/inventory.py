"""Local-only OASIS inventory: writes counts by extension, never subject-level rows.
Usage: python research/oasis/inventory.py --source data/raw/oasis2
"""
from pathlib import Path
from collections import Counter
import argparse,json
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);args=p.parse_args()
if not args.source.exists():raise SystemExit('Source directory does not exist')
files=[x for x in args.source.rglob('*') if x.is_file()]
counts=Counter('.nii.gz' if x.name.lower().endswith('.nii.gz') else x.suffix.lower() for x in files)
print(json.dumps({'location':'local-only','file_count':len(files),'extension_counts':dict(sorted(counts.items()))},indent=2))
