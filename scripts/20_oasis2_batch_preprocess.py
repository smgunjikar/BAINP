"""Sequential experimental OASIS-2 preprocessing. No QC approval or model training.
Default: inventory only. --run --experimental starts CPU processing.
A completed acquisition is reused only if inputs, recipe and all outputs match.
"""
import os
os.environ['ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS'] = '1'
import argparse, csv, hashlib, importlib.metadata, json, re, shutil
import subprocess, sys, time, traceback, uuid
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))


def sources(root, row):
    rel = row['relative_path'].replace('\\', '/')
    require(not re.match(r'^[A-Za-z]:', rel), 'Source must be root-relative')
    p = (root / rel).resolve()
    require(p.is_relative_to(root) and rel.startswith('raw/'), 'Expected source under raw/')
    require(p.suffix.lower() == '.hdr', 'Expected paired NIfTI .hdr source')
    paths = [p, p.with_suffix('.img')]
    require(all(x.is_file() for x in paths), f'Missing header/image: {p}')
    return paths


def fingerprint(root, row):
    return {str(p.relative_to(root)): sha(p) for p in sources(root, row)}


def checked_image(path, reference=None):
    import nibabel as nib
    import numpy as np
    im = nib.load(str(path)); a = im.get_fdata(dtype=np.float32)
    require(np.isfinite(a).all(), f'Nonfinite values: {path}')
    if reference is not None:
        require(im.shape == reference.shape and np.allclose(im.affine, reference.affine, rtol=0, atol=1e-5), f'Geometry mismatch: {path}')
    return im, a


def convert(source, output):
    import nibabel as nib
    import numpy as np
    im = nib.load(str(source)); a = im.get_fdata(dtype=np.float32)
    require(np.isfinite(a).all(), 'Nonfinite source')
    require(im.header.get_xyzt_units()[0] == 'mm', 'Spatial units must be mm')
    require(np.isfinite(im.affine).all() and abs(np.linalg.det(im.affine[:3,:3])) > 0, 'Invalid affine')
    header = im.header.copy(); header.set_data_dtype(np.float32)
    converted = nib.Nifti1Image(a, im.affine, header)
    for form in ('qform', 'sform'):
        getattr(converted, 'set_' + form)(getattr(im, 'get_' + form)(), int(im.header[form + '_code']))
    converted.header.set_slope_inter(1, 0)
    path = output / 'converted_native.nii.gz'; nib.save(converted, path)
    saved, b = checked_image(path, im)
    require(np.array_equal(a, b), 'Conversion changed float32 values')
    require(saved.header.get_xyzt_units() == im.header.get_xyzt_units(), 'Units changed')
    require(np.allclose(saved.header.get_zooms(), im.header.get_zooms()), 'Spacing changed')
    for form in ('qform', 'sform'):
        require(int(saved.header[form+'_code']) == int(im.header[form+'_code']) and np.allclose(getattr(saved,'get_'+form)(), getattr(im,'get_'+form)(), rtol=0, atol=1e-5), 'Transform metadata changed')
    squeezed = nib.squeeze_image(saved)
    require(len(squeezed.shape) == 3, 'Expected 3D or singleton 4D source')
    start = nib.orientations.io_orientation(squeezed.affine)
    target = nib.orientations.axcodes2ornt(('L','A','S'))
    las = squeezed.as_reoriented(nib.orientations.ornt_transform(start, target))
    back = las.as_reoriented(nib.orientations.ornt_transform(target, start))
    require(np.array_equal(back.get_fdata(), squeezed.get_fdata()) and np.allclose(back.affine, squeezed.affine), 'LAS round trip failed')
    nib.save(las, output / 'input_LAS.nii.gz')
    saved_las, values = checked_image(output / 'input_LAS.nii.gz', las)
    require(np.array_equal(values, las.get_fdata(dtype=np.float32)), 'LAS save changed values')
    require(nib.aff2axcodes(saved_las.affine) == ('L','A','S'), 'LAS axis mismatch')
    return saved_las, values


def process(root, row, folder, hd_bet):
    import numpy as np
    import nibabel as nib
    import SimpleITK as sitk
    import ants
    from scipy.ndimage import label
    start = time.monotonic()
    reference, raw = convert(sources(root, row)[0], folder)
    with (folder / 'hd_bet.log').open('w', encoding='utf-8') as log:
        subprocess.run([hd_bet, '-i', str(folder/'input_LAS.nii.gz'), '-o', str(folder/'brain.nii.gz'), '-device', 'cpu', '--disable_tta', '--save_bet_mask', '--verbose'], stdout=log, stderr=subprocess.STDOUT, check=True)
    mask_path = folder/'brain_bet.nii.gz'
    _, mask_values = checked_image(mask_path, reference)
    _, extracted = checked_image(folder/'brain.nii.gz', reference)
    require(np.isin(mask_values, [0,1]).all(), 'Nonbinary mask')
    mask = mask_values == 1
    require(mask.any() and not mask.all(), 'Empty/full mask')
    require(np.array_equal(extracted, raw * mask), 'Extraction changed masked values')
    components = label(mask)[1]
    edge = any(np.any(np.take(mask, k, axis=ax)) for ax in range(3) for k in (0,-1))
    flags = []
    if components != 1: flags.append('MULTIPLE_MASK_COMPONENTS')
    if edge: flags.append('MASK_TOUCHES_IMAGE_EDGE')
    if row.get('preliminary_montage_note', '').strip(): flags.append('PREEXISTING_MONTAGE_NOTE')
    image = sitk.ReadImage(str(folder/'input_LAS.nii.gz'), sitk.sitkFloat32)
    smask = sitk.ReadImage(str(mask_path), sitk.sitkUInt8)
    n4 = sitk.N4BiasFieldCorrectionImageFilter(); n4.SetNumberOfThreads(4)
    n4.SetMaximumNumberOfIterations([50,50,30,20]); n4.SetConvergenceThreshold(1e-6)
    n4.Execute(sitk.Shrink(image, [2,2,2]), sitk.Shrink(smask, [2,2,2]))
    field = n4.GetLogBiasFieldAsImage(image)
    corrected = image / sitk.Exp(field); brain = sitk.Mask(corrected, smask)
    for name, obj in [('n4_corrected.nii.gz', corrected), ('log_bias_field.nii.gz',field), ('n4_brain_only.nii.gz',brain)]:
        sitk.WriteImage(obj, str(folder/name), True); checked_image(folder/name, reference)
    _, corrected_values = checked_image(folder/'n4_corrected.nii.gz', reference)
    _, brain_values = checked_image(folder/'n4_brain_only.nii.gz', reference)
    require(np.array_equal(brain_values, corrected_values*mask), 'N4 masking mismatch')
    result = ants.atropos(a=ants.image_read(str(folder/'n4_brain_only.nii.gz')), x=ants.image_read(str(mask_path)).clone('unsigned char'), i='Kmeans[3]', m='[0.2,1x1x1]', c='[10,0.0001]')
    ants.image_write(result['segmentation'], str(folder/'candidate_classes.nii.gz'))
    _, labels = checked_image(folder/'candidate_classes.nii.gz', reference)
    require(np.isin(labels,[0,1,2,3]).all() and np.all(labels[~mask]==0) and np.all(labels[mask]>0), 'Invalid class labels')
    require(len(result['probabilityimages']) == 3, 'Expected three probability maps')
    probs = []
    for k, obj in enumerate(result['probabilityimages'],1):
        path = folder/f'class_{k}_probability.nii.gz'; ants.image_write(obj,str(path))
        _, values = checked_image(path,reference); probs.append(values)
    probs = np.stack(probs)
    require(probs.min() >= 0 and probs.max() <= 1 and np.max(abs(probs[:,mask].sum(0)-1)) < 1e-4, 'Invalid probabilities')
    require(np.count_nonzero(probs[:,~mask]) == 0, 'Probabilities outside mask')
    voxel_ml = abs(np.linalg.det(reference.affine[:3,:3]))/1000
    classes = []
    for k in (1,2,3):
        selected = mask & (labels == k); count = int(selected.sum())
        require(count > 0, 'Empty class')
        classes.append({'class_id': k, 'voxels': count, 'candidate_volume_ml': count*voxel_ml, 'mean_corrected_intensity': float(brain_values[selected].mean())})
    require(all(classes[k]['mean_corrected_intensity'] < classes[k+1]['mean_corrected_intensity'] for k in (0,1)), 'Class intensity order unexpected')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    fig, axes = plt.subplots(3,6,figsize=(15,9))
    for axis in range(3):
        occupied = np.where(mask.any(axis=tuple(j for j in range(3) if j!=axis)))[0]
        for panel, index in zip(axes[axis], np.linspace(occupied[0],occupied[-1],6).astype(int)):
            sl = np.take(brain_values,index,axis=axis).T; lab = np.take(labels,index,axis=axis).T
            panel.imshow(sl,origin='lower',cmap='gray',vmin=0,vmax=np.percentile(brain_values[mask],99))
            panel.imshow(np.ma.masked_equal(lab,0),origin='lower',cmap=ListedColormap(['deepskyblue','orange','white']),vmin=1,vmax=3,alpha=.4)
            panel.set_title(f'Voxel axis {axis}: {index}'); panel.axis('off')
    fig.suptitle(row['session']+' '+row['filename']+' | Experimental classes; orientation unverified')
    fig.tight_layout();fig.savefig(folder/'review.png',dpi=110);plt.close(fig)
    fig, axes = plt.subplots(3,6,figsize=(15,9))
    for axis in range(3):
        occupied = np.where(mask.any(axis=tuple(j for j in range(3) if j!=axis)))[0]
        for panel, index in zip(axes[axis], np.linspace(occupied[0],occupied[-1],6).astype(int)):
            sl = np.take(raw,index,axis=axis).T; ms = np.take(mask,index,axis=axis).T
            panel.imshow(sl,origin='lower',cmap='gray',vmin=0,vmax=np.percentile(raw[mask],99))
            if ms.any() and not ms.all(): panel.contour(ms,levels=[.5],colors=['red'],linewidths=.6)
            panel.set_title(f'Voxel axis {axis}: {index}');panel.axis('off')
    fig.suptitle(row['session']+' '+row['filename']+' | Mask review; not approved')
    fig.tight_layout();fig.savefig(folder/'mask_review.png',dpi=110);plt.close(fig)
    return {'classes':classes,'mask_volume_ml':float(mask.sum()*voxel_ml),'mask_components':int(components),'flags':flags,'fraction_max_probability_below_0_8':float((probs[:,mask].max(0)<.8).mean()),'elapsed_seconds':time.monotonic()-start}


def reusable(done, inputs, recipe):
    if not done.is_file(): return False
    data = json.loads(done.read_text())
    require(data['input_sha256']==inputs and data['recipe']==recipe, 'Completed inputs/recipe changed; use a NEW output directory')
    for name, digest in data['output_sha256'].items():
        require((done.parent/name).is_file() and sha(done.parent/name)==digest, 'Completed output missing/changed; use a NEW output directory')
    return True


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=Path.home()/'BAINP_DATA')
    ap.add_argument('--output-dir',type=Path)
    ap.add_argument('--run',action='store_true');ap.add_argument('--experimental',action='store_true')
    ap.add_argument('--limit',type=int,default=4,help='Maximum new attempts this invocation; 0 = all remaining')
    a=ap.parse_args(); require(a.limit>=0,'Limit must be nonnegative')
    require(not a.run or a.experimental,'Use --experimental: this queue is not QC approval')
    root=a.data_root.resolve();base=root/'derived/oasis2'
    queue=base/'mri_review_queue_v1/acquisition_review_queue.csv'
    session_queue=base/'mri_review_queue_v1/session_review_queue.csv'
    rows=read_csv(queue);sessions=read_csv(session_queue)
    require(len(rows)==407 and len(sessions)==104,'Expected frozen 407-acquisition/104-session queue')
    expected={r['session']:r['subject'] for r in sessions}
    require(len(expected)==104 and len(set(expected.values()))==104,'Repeated participant/session')
    seen=set()
    for row in rows:
        require(re.fullmatch(r'OAS2_\d{4}_MR\d+',row['session']) is not None,'Invalid session ID')
        require(expected.get(row['session'])==row['subject'],'Queue participant mismatch')
        rel=row['relative_path'].replace('\\','/');require(rel not in seen,'Duplicate acquisition');seen.add(rel)
        sources(root,row)
    counts=Counter(r['session'] for r in rows)
    require(all(counts[r['session']]==int(r['acquisitions_in_tracker']) for r in sessions),'Acquisition count mismatch')
    rows.sort(key=lambda r:(int(r['review_order']),r['relative_path']))
    out=(a.output_dir or base/'experimental_batch_v1').resolve()
    require(out.is_relative_to(base.resolve()) and out!=base.resolve(),'Output must be a subfolder of derived/oasis2')
    out.mkdir(parents=True,exist_ok=True)
    plan={'status':'EXPERIMENTAL_ONLY_NO_QC_APPROVAL','acquisitions':len(rows),'participants':104,'queue_sha256':sha(queue),'session_queue_sha256':sha(session_queue),'visual_status_counts':dict(Counter(r['visual_qc_status'] for r in rows)),'orientation_status_counts':dict(Counter(r['orientation_status'] for r in rows)),'all_source_pairs_present':True,'model_trained':False}
    write_json(out/'preflight.json',plan);print(json.dumps(plan,indent=2),flush=True)
    if not a.run: return
    hd=shutil.which('hd-bet');require(hd,'hd-bet not found in active environment')
    versions={name:importlib.metadata.version(name) for name in ['numpy','nibabel','scipy','SimpleITK','antspyx','hd-bet','torch','matplotlib']}
    require(versions['SimpleITK']=='2.5.7' and versions['antspyx']=='0.6.3','Pilot requires SimpleITK 2.5.7 and antspyx 0.6.3')
    recipe={'script_sha256':sha(Path(__file__)),'versions':versions,'python':sys.version,'hd_bet_executable_sha256':sha(hd),'mode':'CPU_TTA_DISABLED_N4_50_50_30_20_SHRINK2_ATROPOS_KMEANS3'}
    lock=out/'RUNNING.lock'
    try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise RuntimeError('RUNNING.lock exists. Do not run concurrently. Remove ONLY after confirming the previous process has stopped.')
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    results=[];attempted=0;failures=0
    try:
        for row in rows:
            key=row['filename'].replace('.hdr','')+'_'+hashlib.sha256(row['relative_path'].encode()).hexdigest()[:10]
            require(re.fullmatch(r'[A-Za-z0-9_.-]+',key) is not None,'Invalid filename')
            folder=out/row['session']/key;done=folder/'complete.json'
            inputs=fingerprint(root,row)
            if reusable(done,inputs,recipe):
                results.append({'session':row['session'],'acquisition':key,'status':'REUSED'});continue
            if a.limit and attempted>=a.limit: continue
            attempted+=1; print(f'Processing {attempted}: {row["session"]} {row["filename"]}',flush=True)
            folder.parent.mkdir(parents=True,exist_ok=True)
            if folder.exists():
                folder.rename(folder.with_name(key+'_incomplete_'+uuid.uuid4().hex[:8]))
            folder.mkdir()
            try:
                stats=process(root,row,folder,hd)
                require(fingerprint(root,row)==inputs,'Source files changed during processing')
                payload={'status':'PROCESSED_REVIEW_REQUIRED','row_snapshot':row,'recipe':recipe,'input_sha256':inputs,'completed_utc':datetime.now(timezone.utc).isoformat(),'final_qc_approved':False,'orientation_independently_verified':False,'model_eligible':False,**stats}
                payload['output_sha256']={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
                write_json(done,payload)
                results.append({'session':row['session'],'acquisition':key,'status':'PROCESSED_REVIEW_REQUIRED','elapsed_seconds':stats['elapsed_seconds']})
            except Exception as exc:
                failures+=1;(folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
                results.append({'session':row['session'],'acquisition':key,'status':'FAILED','error':str(exc)})
                print('FAILED:',exc,flush=True)
            write_json(out/'last_run.json',{'attempted':attempted,'failures':failures,'results':results})
        write_json(out/'last_run.json',{'attempted':attempted,'failures':failures,'results':results})
        print(f'Finished: {attempted} new attempts; {failures} failures. Output: {out}')
    finally: lock.unlink(missing_ok=True)
    if failures: sys.exit(1)

if __name__=='__main__': main()
