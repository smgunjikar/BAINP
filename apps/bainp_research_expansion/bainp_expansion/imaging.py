"""NeuroVision 2E–2J research measurements with explicit modality and QC gates.

All outputs are observational; no clinical thresholds, disease diagnoses or model weights.
Image operations require `pip install nibabel scipy numpy` in bainp-brain.
"""
from __future__ import annotations
import csv, io, math, re
from pathlib import Path
import numpy as np
from .common import Blocked, require, measured, sha256_file, utc_timestamp, same_subject, report


def _nib():
    try:
        import nibabel as nib
        return nib
    except ImportError as exc:
        raise Blocked('NIBABEL_NOT_INSTALLED','Install nibabel in the dedicated imaging environment') from exc


def image(path):
    nib=_nib(); p=Path(path)
    sha=sha256_file(p)
    img=nib.load(str(p))
    require(len(img.shape)==3,'IMAGE_MUST_BE_3D')
    affine=np.asarray(img.affine,dtype=float)
    require(np.isfinite(affine).all() and abs(np.linalg.det(affine[:3,:3]))>1e-8,'INVALID_AFFINE')
    return img,sha


def equal_grid(a,b):
    require(a.shape==b.shape and np.allclose(a.affine,b.affine,atol=1e-4,rtol=0),
            'IMAGE_GRID_MISMATCH','Use a separately QC-verified nearest-neighbor resampling procedure')


def volume_ml(img):
    return abs(float(np.linalg.det(img.affine[:3,:3])))/1000.0


def discrete(arr):
    require(np.issubdtype(arr.dtype,np.number) and np.isfinite(arr).all(),'LABEL_NONFINITE_OR_NONTNUMERIC')
    require(np.all(arr>=0) and np.allclose(arr,np.rint(arr),atol=1e-6,rtol=0), 'DISCRETE_NONNEGATIVE_LABELS_REQUIRED')
    return np.rint(arr).astype(np.int64)


def anatomy_qc(mri_path,labels_path,expected_mri_sha=None,expected_label_sha=None):
    m,ms=image(mri_path);s,ss=image(labels_path)
    if expected_mri_sha:require(ms==expected_mri_sha,'SOURCE_MRI_HASH_MISMATCH')
    if expected_label_sha:require(ss==expected_label_sha,'SEGMENTATION_HASH_MISMATCH')
    equal_grid(m,s)
    data=discrete(np.asanyarray(s.dataobj))
    ids,counts=np.unique(data[data!=0],return_counts=True)
    require(len(ids)>0,'NO_ANATOMICAL_LABELS')
    frac=float(np.count_nonzero(data))/int(data.size)
    items=[{'label_id':int(i),'voxels':int(n),'volume_ml':round(int(n)*volume_ml(s),6)} for i,n in zip(ids,counts)]
    return report('2E','GEOMETRY_AND_LABEL_COUNTS_VERIFIED_REVIEW_REQUIRED',{
        'input_mri_sha256':ms,'labels_sha256':ss,'shape':list(map(int,m.shape)),
        'voxel_volume_ml':volume_ml(s),'label_count':len(items),'labeled_fraction':frac,
        'regions':items,'grid_match':True,
        'review_state':'ANATOMICAL_ACCURACY_UNREVIEWED',
        'qc_flags':['NO_AUTOMATED_ANATOMICAL_ACCURACY_CLAIM']},
        ['Geometric consistency is not anatomical validity.','Regions require an atlas label dictionary and independent review.'])


def parse_freesurfer_stats(path):
    """Accept documented FreeSurfer stats tables; preserve exact source units."""
    raw=Path(path).read_text(encoding='utf-8',errors='replace')
    columns=None; result=[]; measure=[]
    for line in raw.splitlines():
        if line.startswith('# ColHeaders '):
            columns=line[len('# ColHeaders '):].strip().split()
        if line.startswith('# Measure '):
            measure.append(line[10:].strip())
        if line.startswith('#') or not line.strip():continue
        require(columns is not None,'FREESURFER_STATS_MISSING_COLHEADERS')
        cells=line.split()
        require(len(cells)==len(columns),'FREESURFER_STATS_COLUMN_COUNT_MISMATCH',str(path))
        item=dict(zip(columns,cells))
        if 'Volume_mm3' in item:item['Volume_mm3']=measured(float(item['Volume_mm3']),'Volume_mm3',0)
        for metric in ('ThickAvg','SurfArea','GrayVol'):
            if metric in item:item[metric]=measured(float(item[metric]),metric,0)
        result.append(item)
    require(bool(result),'NO_FREESURFER_STATS_ROWS')
    return {'source_sha256':sha256_file(path),'columns':columns,'measure_lines':measure,'rows':result}


def structural_from_freesurfer(subject_directory,reference_t1,reference_sha=None):
    home=Path(subject_directory)
    require(home.is_dir() and not home.is_symlink(),'FREESURFER_SUBJECT_DIR_MISSING')
    src=sha256_file(reference_t1)
    if reference_sha:require(src==reference_sha,'FREESURFER_T1_PROVENANCE_MISMATCH')
    stats={}
    for name in ('aseg.stats','lh.aparc.stats','rh.aparc.stats'):
        p=home/'stats'/name
        require(p.is_file(),'FREESURFER_STATS_REQUIRED',name)
        stats[name]=parse_freesurfer_stats(p)
    # eTIV is a FreeSurfer-reported estimate; never infer it from segmented labels.
    etiv_mm3=None
    for line in stats['aseg.stats']['measure_lines']:
        fields=[x.strip() for x in line.split(',')]
        if len(fields)>=5 and fields[1]=='eTIV' and fields[-1].lower()=='mm^3':
            etiv_mm3=measured(float(fields[-2]),'eTIV',1)
    structural=[]
    for item in stats['aseg.stats']['rows']:
        if 'Volume_mm3' not in item:continue
        ml=item['Volume_mm3']/1000
        region={'region':item.get('StructName',str(item.get('SegId',''))),'volume_ml':ml,
                'etiv_normalized_fraction':(item['Volume_mm3']/etiv_mm3 if etiv_mm3 else None)}
        structural.append(region)
    cortical=[]
    for hemisphere in ('lh','rh'):
        for item in stats[hemisphere+'.aparc.stats']['rows']:
            if 'ThickAvg' not in item or 'SurfArea' not in item:continue
            cortical.append({'hemisphere':hemisphere,'region':item['StructName'],
                            'thickness_mm':item['ThickAvg'],'surface_area_mm2':item['SurfArea']})
    hippocampal={}
    for side in ('lh','rh'):
        candidates=sorted((home/'mri').glob(side+'.hippoSfVolumes-T1*.txt')) if (home/'mri').is_dir() else []
        if candidates:
            hippocampal[side]={'file_sha256':sha256_file(candidates[0]),'raw_rows':candidates[0].read_text(encoding='utf-8').splitlines(),
                               'state':'PRESENT_REQUIRES_SCHEMA_AND_VERSION_REVIEW'}
    return report('2F','FREESURFER_STATS_IMPORTED_REQUIRES_INDEPENDENT_QC',{
        'input_t1_sha256':src,'stats':stats,'etiv_ml':etiv_mm3/1000 if etiv_mm3 else None,
        'regional_volumes':structural,'cortical_surface_measures':cortical,
        'hippocampal_subfields':hippocampal},
        ['No cortical surface reconstruction was executed by this import.',
         'FreeSurfer recon-all logs and inspection of pial/white surfaces are required.',
         'Cortical thickness and hippocampal measurements cannot be inferred from SynthSeg atlas labels alone.',
         'ICV/eTIV normalization is descriptive and not a substitute for normative adjustment.'])


def wmh_burden(flair_path,wmh_mask_path,segmentation_provenance:dict):
    require(segmentation_provenance.get('model_name') and segmentation_provenance.get('model_version') and
            segmentation_provenance.get('independent_segmentation_qc') is True,
            'WMH_MODEL_AND_QC_PROVENANCE_REQUIRED')
    f,fh=image(flair_path);m,mh=image(wmh_mask_path);equal_grid(f,m)
    arr=discrete(np.asanyarray(m.dataobj))
    require(np.isin(arr,[0,1]).all(),'WMH_BINARY_MASK_REQUIRED')
    from scipy import ndimage
    connectivity=np.ones((3,3,3),dtype=np.int8)
    _,components=ndimage.label(arr>0,structure=connectivity)
    n=int(np.count_nonzero(arr)); v=volume_ml(m)
    return report('2G','WMH_MASK_QUANTIFIED_REQUIRES_EXTERNAL_VALIDATION',{
        'flair_sha256':fh,'mask_sha256':mh,'model':segmentation_provenance,
        'wmh_voxels':n,'wmh_volume_ml':round(n*v,6),'26_connected_components':int(components)},
        ['Requires appropriate FLAIR acquisition and validated WMH model.','Binary WMH mask cannot diagnose stroke, MS or dementia.',
         'Inter-scan and inter-rater accuracy must be established independently.'])


def pet_suvr(pet_path,roi_mask_path,reference_mask_path,metadata):
    for key in ('tracer','uptake_window_minutes','pet_value_type','reference_region','registration_qc_reference'):
        require(metadata.get(key),'PET_METADATA_MISSING',key)
    window=metadata['uptake_window_minutes']
    require(isinstance(window,list) and len(window)==2 and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in window)
            and 0<=window[0]<window[1]<=360,'INVALID_PET_UPTAKE_WINDOW')
    require(metadata['pet_value_type'] in ('SUV','activity_concentration','relative_activity'),
            'PET_UNSUPPORTED_QUANTIFICATION_TYPE')
    p,ph=image(pet_path);r,rh=image(roi_mask_path);b,bh=image(reference_mask_path)
    equal_grid(p,r);equal_grid(p,b)
    values=np.asanyarray(p.dataobj,dtype=np.float64)
    roi=discrete(np.asanyarray(r.dataobj))>0;ref=discrete(np.asanyarray(b.dataobj))>0
    require(int(np.count_nonzero(roi))>0 and int(np.count_nonzero(ref))>0,'PET_EMPTY_MASK')
    require(not np.any(roi & ref),'PET_REFERENCE_AND_TARGET_OVERLAP')
    require(np.isfinite(values[roi|ref]).all(),'NONFINITE_PET_VOXELS')
    reference=float(np.mean(values[ref]));target=float(np.mean(values[roi]))
    require(reference>0,'INVALID_PET_REFERENCE_MEAN')
    return report('2H','RESEARCH_SUVR_COMPUTED_NOT_CENTILOID',{
        'pet_sha256':ph,'roi_mask_sha256':rh,'reference_mask_sha256':bh,
        'roi_mean':target,'reference_mean':reference,'suvr':target/reference,
        'roi_voxels':int(roi.sum()),'reference_voxels':int(ref.sum()),'metadata':metadata},
        ['SUVR depends on tracer, uptake window, reference, motion and registration.','No Centiloid conversion or pathology diagnosis is performed.'])


def longitudinal(baseline,followup):
    same_subject(baseline,followup)
    require(not baseline.get('synthetic_example') and not followup.get('synthetic_example'),
            'SYNTHETIC_DEMONSTRATION_NOT_ELIGIBLE_FOR_REAL_LONGITUDINAL_ANALYSIS')
    for field in ('measurement_pipeline','pipeline_version','acquisition_protocol','modality'):
        require(baseline.get(field) and baseline[field]==followup.get(field), 'INCOMPARABLE_LONGITUDINAL_PIPELINE',field)
    require(baseline.get('modality')=='T1w','LONGITUDINAL_T1W_ONLY')
    require(baseline.get('research_qc')=='ACCEPTED' and followup.get('research_qc')=='ACCEPTED',
            'INDEPENDENT_QC_ACCEPTANCE_REQUIRED')
    require(baseline.get('source_sha256')!=followup.get('source_sha256'), 'SAME_MRI_REUSED_AS_FOLLOWUP')
    b=utc_timestamp(baseline['acquired_at']);f=utc_timestamp(followup['acquired_at'])
    days=(f-b).total_seconds()/86400
    require(days>=30,'FOLLOWUP_INTERVAL_TOO_SHORT_OR_REVERSED')
    first=baseline.get('measurements_ml',{});next_=followup.get('measurements_ml',{})
    require(isinstance(first,dict) and isinstance(next_,dict),'MISSING_LONGITUDINAL_MEASUREMENTS')
    aligned=sorted(set(first)&set(next_))
    require(bool(aligned),'NO_MATCHED_REGION_MEASUREMENTS')
    rows=[]
    for region in aligned:
        bv=measured(first[region],region,0.000001);fv=measured(next_[region],region,0.000001)
        rows.append({'region':region,'baseline_ml':bv,'followup_ml':fv,'delta_ml':fv-bv,
                     'percent_change':100*(fv-bv)/bv,'annualized_percent_change':100*(fv-bv)/bv*365.2425/days})
    return report('2I','DESCRIPTIVE_MATCHED_VISIT_DIFFERENCE_QC_REQUIRED',{
        'cohort':baseline['cohort'],'subject':baseline['subject'],'interval_days':days,'regions':rows},
        ['Not unbiased longitudinal image registration or a validated atrophy rate.',
         'Requires harmonized acquisition, QC, repeatability and independent validation.',
         'Temporal change is not a disease diagnosis or treatment effect.'])


def connectome(edge_rows,metadata):
    require(metadata.get('modality')=='dwi' and metadata.get('tractography_pipeline') and
            metadata.get('pipeline_version') and metadata.get('source_dwi_sha256') and
            metadata.get('qc_state')=='ACCEPTED', 'DWI_TRACTOGRAPHY_PROVENANCE_REQUIRED')
    from .common import checksum
    checksum(metadata['source_dwi_sha256'])
    names=set();weights={}
    for row in edge_rows:
        a,b=str(row['source']),str(row['target']);require(a!=b,'SELF_EDGE_NOT_SUPPORTED')
        w=measured(row['weight'],'edge_weight',0)
        require(a and b,'INVALID_CONNECTOME_NODE')
        key=tuple(sorted((a,b)))
        require(key not in weights,'DUPLICATE_CONNECTOME_EDGE')
        weights[key]=w;names.update((a,b))
    n=len(names);require(n>=2,'CONNECTOME_TOO_SMALL')
    degree={name:0 for name in names};strength={name:0.0 for name in names}
    for (a,b),w in weights.items():
        if w>0:
            degree[a]+=1;degree[b]+=1;strength[a]+=w;strength[b]+=w
    return report('2J','EXTERNAL_DWI_CONNECTOME_FEATURES_IMPORT',{
        'nodes':n,'edges_positive':sum(w>0 for w in weights.values()),
        'edge_density':2*sum(w>0 for w in weights.values())/(n*(n-1)),
        'weighted_strength':strength,'degree':degree,'provenance':metadata},
        ['The supplied edges are not produced from MRI T1 intensity.','Node definitions and tractography bias require independent review.',
         'This describes structural network edges, not functional or causal brain connectivity.'])


def normative_z(observation,reference):
    require(reference.get('calibration_qc')=='ACCEPTED' and reference.get('reference_database_sha256'),
            'NORMATIVE_REFERENCE_UNVALIDATED')
    for k in ('feature','unit','scanner_site','age_band','pipeline_version'):
        require(observation.get(k)==reference.get(k) and observation.get(k) is not None,
                'NORMATIVE_REFERENCE_STRATUM_MISMATCH',k)
    sd=measured(reference['sd'],'reference_sd',0)
    require(sd>0,'REFERENCE_SD_ZERO');require(int(reference['n'])>=30,'REFERENCE_SAMPLE_TOO_SMALL')
    value=measured(observation['value'],'observation');mu=measured(reference['mean'],'reference_mean')
    return report('2J','DESCRIPTIVE_REFERENCE_Z_NOT_DIAGNOSTIC',{
        'z':(value-mu)/sd,'n_reference':int(reference['n']),'reference_sha256':reference['reference_database_sha256'],
        'matched_stratum':{k:observation[k] for k in ('feature','unit','scanner_site','age_band','pipeline_version')}},
        ['Reference distribution calibration, selection bias and external validation remain necessary.',
         'This z-score does not establish neurodegenerative pathology.'])


def research_rigid_registration(fixed_path,moving_path,output_dir,metadata):
    """2H/2I actual rigid alignment with SimpleITK; QC/clinical inference remain blocked.

    A PET/MRI or T1/T1 transform is an engineering registration, not validation of
    PET quantification, anatomical segmentation comparability or tissue atrophy.
    """
    from .common import write_json_new
    import shutil
    try:
        import SimpleITK as sitk
    except ImportError as exc:
        raise Blocked('SIMPLEITK_NOT_INSTALLED') from exc
    require(metadata.get('case_id') and metadata.get('registration_purpose') in ('PET_TO_T1','FOLLOWUP_T1_TO_BASELINE_T1') and
            metadata.get('user_authorized_research_processing') is True,
            'REGISTRATION_METADATA_REQUIRED')
    fixed_sha=sha256_file(fixed_path);moving_sha=sha256_file(moving_path)
    require(fixed_sha!=moving_sha,'IDENTICAL_IMAGES_CANNOT_ESTABLISH_FOLLOWUP')
    out=Path(output_dir)
    require(not out.exists(),'REGISTRATION_OUTPUT_ALREADY_EXISTS')
    # Read and validate BEFORE creating output directory; never overwrite sources.
    fixed=sitk.ReadImage(str(fixed_path));moving=sitk.ReadImage(str(moving_path))
    require(fixed.GetDimension()==3 and moving.GetDimension()==3,'THREE_DIMENSIONAL_IMAGES_REQUIRED')
    require(all(n>0 for n in fixed.GetSize()) and all(n>0 for n in moving.GetSize()),'INVALID_IMAGE_DIMENSIONS')
    init=sitk.CenteredTransformInitializer(fixed,moving,sitk.Euler3DTransform(),
                                         sitk.CenteredTransformInitializerFilter.GEOMETRY)
    registration=sitk.ImageRegistrationMethod()
    registration.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)
    registration.SetMetricSamplingStrategy(registration.RANDOM)
    registration.SetMetricSamplingPercentage(0.15,seed=42)
    registration.SetInterpolator(sitk.sitkLinear)
    registration.SetOptimizerAsGradientDescent(learningRate=1.0,numberOfIterations=100,
                                             convergenceMinimumValue=1e-6,convergenceWindowSize=10)
    registration.SetOptimizerScalesFromPhysicalShift()
    registration.SetInitialTransform(init,inPlace=False)
    transform=registration.Execute(sitk.Cast(fixed,sitk.sitkFloat32),sitk.Cast(moving,sitk.sitkFloat32))
    warped=sitk.Resample(moving,fixed,transform,sitk.sitkLinear,0.0,moving.GetPixelID())
    out.mkdir(parents=True,exist_ok=False)
    try:
        sitk.WriteTransform(transform,str(out/'rigid.tfm'))
        sitk.WriteImage(warped,str(out/'moving_registered.nii.gz'))
        output=report('2H' if metadata['registration_purpose']=='PET_TO_T1' else '2I',
            'RIGID_RESEARCH_REGISTRATION_REQUIRES_VISUAL_QC',{
            'fixed_image_sha256':fixed_sha,'moving_image_sha256':moving_sha,
            'transform_sha256':sha256_file(out/'rigid.tfm'),
            'registered_image_sha256':sha256_file(out/'moving_registered.nii.gz'),
            'metric_value':float(registration.GetMetricValue()),
            'stop_condition':registration.GetOptimizerStopConditionDescription(),
            'metadata':metadata},
            ['Rigid alignment alone cannot validate PET SUVR or longitudinal tissue-loss measurement.',
             'Human visual inspection of registered anatomy is required.'])
        write_json_new(out/'registration_qc.json',output)
    except BaseException:
        # No untracked partial output; only this fresh directory is affected.
        shutil.rmtree(out)
        raise
    return output
