"""Export existing reviewed FreeSurfer outputs; does not run segmentation/recon-all.
Surface coordinates remain FreeSurfer surface RAS, not native scanner RAS.
Requires nibabel in bainp-brain. Keep output private and outside Git.
"""
import argparse,hashlib,json,os
from pathlib import Path

def parse_stats(path):
    columns=None;rows=[]
    for line in path.read_text().splitlines():
        if line.startswith('# ColHeaders '):columns=line.split()[2:]
        elif line and not line.startswith('#'):
            values=line.split()
            if columns and len(values)>=len(columns):rows.append(dict(zip(columns,values)))
    if not rows:raise ValueError('No stats table in '+str(path))
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--subject-dir',type=Path,required=True)
    p.add_argument('--scan-id',required=True);p.add_argument('--input-mri-sha256',required=True)
    p.add_argument('--freesurfer-version',required=True);p.add_argument('--review-reference',required=True);p.add_argument('--identity-and-visit-verified',action='store_true');a=p.parse_args()
    if not a.identity_and_visit_verified:raise ValueError('Verify source MRI identity, visit and FreeSurfer processing before export')
    import nibabel as nib
    root=a.subject_dir;measurements=[];surfaces=[];hashes={}
    for filename in ('stats/aseg.stats','stats/lh.aparc.stats','stats/rh.aparc.stats'):
        path=root/filename;hashes[filename]=hashlib.sha256(path.read_bytes()).hexdigest()
        for row in parse_stats(path):
            if 'Volume_mm3' in row:
                measurements.append(dict(id='aseg:'+row['StructName'],name=row['StructName'],value=float(row['Volume_mm3'])/1000,unit='mL',basis='FreeSurfer segmentation grid; not original native-grid voxel counting'))
            elif 'ThickAvg' in row:
                hemi=filename.split('/')[1][:2]
                measurements.append(dict(id=hemi+':'+row['StructName']+':thickness',name=hemi+' '+row['StructName']+' thickness',value=float(row['ThickAvg']),unit='mm',basis='FreeSurfer cortical surface thickness'))
    for hemi in ('lh','rh'):
        path=root/'surf'/(hemi+'.pial');v,f=nib.freesurfer.io.read_geometry(path);hashes['surf/'+hemi+'.pial']=hashlib.sha256(path.read_bytes()).hexdigest()
        surfaces.append(dict(id=hemi,name=hemi+' pial surface',vertices_mm=v.round(4).tolist(),faces=f.tolist(),coordinate_space='FreeSurfer surface RAS'))
    package=dict(schema='nt-freesurfer-anatomy-v1',scan_id=a.scan_id,input_mri_sha256=a.input_mri_sha256,review_reference=a.review_reference,freesurfer_version=a.freesurfer_version,measurements=measurements,surfaces=surfaces,source_hashes=hashes,synthetic=False,interpretation='Anatomical measurements from supplied FreeSurfer outputs; no disease inference or automatic longitudinal validity.')
    raw=json.dumps(package,separators=(',',':'),allow_nan=False).encode();digest=hashlib.sha256(raw).hexdigest()
    folder=Path(os.environ.get('NEUROTWIN_ANATOMY_DIR',str(Path.home()/'BAINP_DATA/derived/neurotwin/anatomy')));folder.mkdir(parents=True,exist_ok=True);(folder/(digest+'.json')).write_bytes(raw)
    (folder/(digest+'.registration.json')).write_text(json.dumps({'package_sha256':digest,'identity_verified':False,'consent_confirmed':False}))
    print('Prepared private anatomy package SHA-256:',digest)
    print('Registration request:',folder/(digest+'.registration.json'))
    print('Register this hash for the verified participant using the anatomical-records API. No participant link was created automatically.')
if __name__=='__main__':main()
