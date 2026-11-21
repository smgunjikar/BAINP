"""Account-isolated NeuroVision storage. Identifiers come from signed-in server sessions.
No query string, participant ID or user-entered cohort selects the filesystem tenant.
"""
import json,os,re,secrets
from pathlib import Path
_UUID=re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
def root():
 return Path(os.environ.get('NEUROVISION_DATA_DIR',str(Path.home()/'BAINP_DATA/derived/neurovision/v1')))
def storage_root(principal, mode='active'):
 # Web-only dependency: the MRI worker imports this module but never calls storage_root.
 from fastapi import HTTPException
 if not isinstance(principal,dict) or not principal.get('user_id'):
  raise HTTPException(401,'Sign in to continue.')
 if mode=='demo':return root()  # Access to catalog is restricted to synthetic entries.
 if mode!='active':raise HTTPException(422,'Unsupported imaging mode.')
 # Preserve the existing local administrator/legacy research catalog.
 if principal.get('role')=='admin' and principal.get('target') in (None,'legacy'):
  return root()
 tenant=principal.get('target') or principal['user_id']
 if not isinstance(tenant,str) or not _UUID.fullmatch(tenant):
  raise HTTPException(403,'Invalid account workspace identifier.')
 return root()/'workspaces'/tenant
def jobs(base=None):return (Path(base) if base is not None else root())/'import_jobs'
def save(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
 try:tmp.write_text(json.dumps(value,allow_nan=False),encoding='utf-8');os.replace(tmp,path)
 finally:tmp.unlink(missing_ok=True)
