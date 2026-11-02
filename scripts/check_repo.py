"""Verify expected repository skeleton and ignored research-data paths."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
required=['README.md','docs/BLUEPRINT.md','docs/VS_CODE_SETUP.md', 'apps/api/app/main.py','apps/api/tests/test_api.py','apps/web/src/app/page.tsx','research/oasis/inventory.py','research/pads/participant_heldout_baseline.py','research/eeg/README.md','.gitignore']
missing=[x for x in required if not (root/x).is_file()]
print('Skeleton:', 'OK' if not missing else f'Missing: {missing}')
assert not missing
