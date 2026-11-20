"""Private FreeSurfer package reader with content hashes and bounded mesh validation."""
import hashlib,json,math,os,re
from pathlib import Path
from collections import OrderedDict
_metadata_cache={};_geometry_cache=OrderedDict()

def load_anatomy(digest,geometry=True):
    if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('invalid anatomy hash')
    root=Path(os.environ.get('NEUROTWIN_ANATOMY_DIR',str(Path.home()/'BAINP_DATA/derived/neurotwin/anatomy')))
    p=root/(digest+'.json')
    stat=p.stat();key=(str(p),stat.st_mtime_ns,stat.st_ctime_ns,stat.st_size)
    if not geometry and key in _metadata_cache:return _metadata_cache[key]
    if geometry and key in _geometry_cache:return _geometry_cache[key]
    if stat.st_size>64*1024*1024:raise ValueError('anatomy package too large')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('anatomy integrity mismatch')
    result=json.loads(raw)
    if result.get('schema')!='nt-freesurfer-anatomy-v1' or result.get('synthetic') is not False:raise ValueError('unsupported anatomy schema')
    if not re.fullmatch('[a-f0-9]{24}',result['scan_id']) or not re.fullmatch('[a-f0-9]{64}',result['input_mri_sha256']):raise ValueError('missing source MRI identity')
    for m in result['measurements']:
        if m['unit'] not in ('mL','mm') or not math.isfinite(m['value']) or m['value']<0:raise ValueError('invalid regional measurement')
    for surface in result['surfaces']:
        v=surface['vertices_mm'];f=surface['faces']
        if not 3<=len(v)<=500000 or not 1<=len(f)<=1000000:raise ValueError('surface bounds')
        if any(len(row)!=3 or any(not math.isfinite(x) for x in row) for row in v):raise ValueError('invalid surface vertices')
        if any(len(row)!=3 or any(not isinstance(x,int) or not 0<=x<len(v) for x in row) for row in f):raise ValueError('invalid surface faces')
    summary={k:v for k,v in result.items() if k!='surfaces'}
    summary['surfaces']=[{k:v for k,v in surface.items() if k not in ('vertices_mm','faces')} for surface in result['surfaces']]
    if len(_metadata_cache)>256:_metadata_cache.clear()
    _metadata_cache[key]=summary
    _geometry_cache[key]=result
    while len(_geometry_cache)>2:_geometry_cache.popitem(last=False)
    return result if geometry else summary
