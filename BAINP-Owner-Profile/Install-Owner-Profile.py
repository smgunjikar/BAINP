"""Install or restore the owner-only profile refresh. Stop the app first."""
import argparse,hashlib,json,shutil
from pathlib import Path
from datetime import datetime

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--project-root',required=True,type=Path)
p.add_argument('--check',action='store_true')
p.add_argument('--restore',type=Path)
a=p.parse_args();root=a.project_root.resolve();package=Path(__file__).resolve().parent
manifest=json.loads((package/'manifest.json').read_text())
if not (root/'apps/neuroaccess/Start-NeuroAccess.ps1').is_file():raise SystemExit('Wrong project root.')
if a.restore:
 backup=a.restore.resolve()
 for name,entry in manifest.items():
  target=root/name;old=backup/name
  if not old.is_file() or digest(old)!=entry['before']:raise SystemExit('Backup mismatch: '+name)
  if not target.is_file() or digest(target)!=entry['after']:raise SystemExit('Changed since installation; refusing restore: '+name)
 if a.check:print('Restore check passed.');raise SystemExit(0)
 for name in manifest:shutil.copy2(backup/name,root/name)
 print('Restored source. Owner preference table is retained; no records deleted.');raise SystemExit(0)
for name,entry in manifest.items():
 target=root/name;payload=package/'payload'/name
 if not target.is_file() or digest(target)!=entry['before']:raise SystemExit('Source differs from uploaded version; no files changed: '+name)
 if digest(payload)!=entry['after']:raise SystemExit('Package integrity mismatch: '+name)
if a.check:print('Compatibility check passed: 3 files.');raise SystemExit(0)
backup=root/'patch_backups'/('owner-profile-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
for name in manifest:
 old=backup/name;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,old)
try:
 for name in manifest:shutil.copy2(package/'payload'/name,root/name)
except Exception:
 for name in manifest:shutil.copy2(backup/name,root/name)
 raise
print('Installed. Restart the app. Sign in again, then open /#/workspace/participants')
print('Source backup:',backup)
print('No participant records were deleted. Public registration remains disabled.')
