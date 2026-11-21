"""Collect bounded application source only. Review the ZIP before sharing."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

APPS={'neuroaccess','neurocontinuum','neuroquest','neurocognition','neurocognitionx','neurocognition-x','neuroguard','careloop','neurotwin','neuromimic','neuroproof','neurograph'}
SKIP={'node_modules','.git','.venv','venv','__pycache__','data','raw','derived','uploads','downloads','logs','patch_backups','patch-backups','dist','build'}
EXT={'.py','.js','.ts','.tsx','.jsx','.html','.css','.md','.toml'}
NAMES={'requirements.txt','package.json','pyproject.toml','AGENTS.md'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',required=True,type=Path)
    args=p.parse_args();root=args.project_root.resolve()
    if not (root/'apps').is_dir():p.error('Project apps directory not found')
    output=root/'BAINP-Workflow-Source.zip';chosen=[];total=0
    for folder in sorted((root/'apps').iterdir()):
        if not folder.is_dir() or folder.name.lower() not in APPS:continue
        for path in folder.rglob('*'):
            rel=path.relative_to(root)
            if path.is_symlink() or not path.is_file() or any(x.lower() in SKIP or x.startswith('.') for x in rel.parts):continue
            if path.suffix.lower() not in EXT and path.name not in NAMES:continue
            if any(x in path.name.lower() for x in ('secret','credential','token','password','certificate')):continue
            size=path.stat().st_size
            if size>2_000_000:print('Skipped oversized source:',rel);continue
            data=path.read_bytes()
            if b'\x00' in data[:8192]:continue
            total+=len(data)
            if total>40_000_000:raise SystemExit('Source exceeds 40 MB; archive not written')
            chosen.append((rel.as_posix(),data))
    for name in ('AGENTS.md','requirements.txt','pyproject.toml','package.json'):
        path=root/name
        if path.is_file() and not path.is_symlink():chosen.append((name,path.read_bytes()))
    if not chosen:raise SystemExit('No matching source found')
    manifest=[dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in chosen]
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in chosen:archive.writestr(name,data)
        archive.writestr('SOURCE_MANIFEST.json',json.dumps(manifest,indent=2))
    print('Created:',output,'Files:',len(chosen))
    print('Review contents for embedded credentials, private notes or participant fixtures before sharing. This is a source snapshot, not an anonymizer.')

if __name__=='__main__':main()
