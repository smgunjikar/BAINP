"""Version-checked installation. Stop BAINP before install or restore."""
import argparse,hashlib,json,shutil
from pathlib import Path
from datetime import datetime

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project-root',type=Path,required=True);p.add_argument('--check',action='store_true');p.add_argument('--restore',type=Path);args=p.parse_args()
root=args.project_root.resolve();package=Path(__file__).resolve().parent;manifest=json.loads((package/'manifest.json').read_text())
if not (root/'apps/neuroaccess/Start-NeuroAccess.ps1').is_file():raise SystemExit('Wrong project folder.')
if args.restore:
 backup=args.restore.resolve();record=json.loads((backup/'restore.json').read_text())
 for name,old_hash in record.items():
  if name not in manifest:raise SystemExit('Unexpected backup file.')
  target=root/name
  if not target.is_file() or sha(target)!=manifest[name]['after']:raise SystemExit('Changed since install; restore stopped: '+name)
  if old_hash is not None and (not (backup/name).is_file() or sha(backup/name)!=old_hash):raise SystemExit('Backup mismatch: '+name)
 if args.check:print('Restore check passed.');raise SystemExit(0)
 for name,old_hash in record.items():
  if old_hash is None:(root/name).unlink()
  else:shutil.copy2(backup/name,root/name)
 print('Source restored. Account databases remain on disk. Do not expose the old operator version to users.');raise SystemExit(0)
record={}
for name,entry in manifest.items():
 target=root/name;payload=package/'payload'/name
 if not payload.is_file() or sha(payload)!=entry['after']:raise SystemExit('Package integrity mismatch: '+name)
 actual=sha(target) if target.is_file() else None
 if actual not in entry['before']:raise SystemExit('Source differs from supported snapshot. No files changed: '+name)
 record[name]=actual
# Confirm the installed Python can run the password KDF before changing files.
hashlib.scrypt(b'compatibility-check',salt=b'0123456789abcdef',n=131072,r=8,p=1,maxmem=268435456)
if args.check:print('Compatibility passed:',len(manifest),'files.');raise SystemExit(0)
backup=root/'patch_backups'/('research-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'));backup.mkdir(parents=True)
for name,old_hash in record.items():
 if old_hash is not None:
  (backup/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,backup/name)
(backup/'restore.json').write_text(json.dumps(record,indent=2))
try:
 for name in manifest:
  (root/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(package/'payload'/name,root/name)
except Exception:
 for name,old_hash in record.items():
  if old_hash is not None:shutil.copy2(backup/name,root/name)
  elif (root/name).is_file():(root/name).unlink()
 raise
print('Installed BAINP Research Studio. Restart BAINP and open /#/research-lab as administrator.')
print('Backup:',backup)
print('Research records use the existing authorized workspace. No database files were changed by this installer.')
