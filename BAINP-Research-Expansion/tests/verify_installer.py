import tempfile,subprocess,sys,json,hashlib
from pathlib import Path
package=Path(__file__).resolve().parents[1];baseline=Path(sys.argv[1]).resolve()
manifest=json.loads((package/'manifest.json').read_text())
with tempfile.TemporaryDirectory() as d:
 root=Path(d);start=root/'apps/neuroaccess/Start-NeuroAccess.ps1';start.parent.mkdir(parents=True);start.write_text('# test marker')
 for name in manifest:
  source=baseline/name
  if source.exists():
   dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
 command=[sys.executable,str(package/'Install-Research.py'),'--project-root',str(root)]
 subprocess.run(command+['--check'],check=True,capture_output=True)
 subprocess.run(command,check=True,capture_output=True)
 for name,row in manifest.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==row['after']
 backup=next((root/'patch_backups').iterdir());subprocess.run(command+['--restore',str(backup),'--check'],check=True,capture_output=True);subprocess.run(command+['--restore',str(backup)],check=True,capture_output=True)
 for name,row in manifest.items():assert (hashlib.sha256((root/name).read_bytes()).hexdigest() if (root/name).exists() else None) in row['before']
 changed=root/'apps/neuroaccess/web/app.js';changed.write_text('NEWER USER CHANGE');r=subprocess.run(command,capture_output=True);assert r.returncode!=0 and changed.read_text()=='NEWER USER CHANGE'
print('PASS compatibility, install, rollback and refusal to overwrite changed source.')
