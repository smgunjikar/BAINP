"""BAINP Imaging V5: reproducible research CLI, no clinical claims.

Run from the BAINP project root:
    python -m apps.neurovision.advanced.cli capabilities
    python -m apps.neurovision.advanced.cli --help

Does not make network requests or fetch model weights. Output files are create-only.
"""
from __future__ import annotations
import argparse
import csv
import json
import shutil
from pathlib import Path
import numpy as np
from . import core
from .pipelines import (read_nii, write_json, envelope, no_overwrite, digest, run_freesurfer,
                        resample_discrete_to_source, rigid_registration, external_simnibs_script)


def capabilities():
    import importlib.util
    return {
        'module': 'BAINP_NeuroVision_Advanced_V5',
        'nibabel': bool(importlib.util.find_spec('nibabel')),
        'numpy': bool(importlib.util.find_spec('numpy')),
        'scipy': bool(importlib.util.find_spec('scipy')),
        'simpleitk': bool(importlib.util.find_spec('SimpleITK')),
        'synthseg_native_executable': bool(shutil.which('mri_synthseg')),
        'wmh_synthseg_native_executable': bool(shutil.which('mri_WMHsynthseg')),
        'simnibs_python_executable': bool(shutil.which('simnibs_python')),
        'model_weights_bundled': False,
        'reference_database_bundled': False,
        'clinical_clearance': False,
        'pet_registration': 'SimpleITK rigid research operation; independent QC needed',
        'centiloid': 'no conversion without externally supplied pipeline-specific calibration',
    }


def save_html(report, path):
    import html
    title = html.escape(str(report.get('operation','BAINP MRI analysis')))
    content = html.escape(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    output = no_overwrite(path)
    output.write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BAINP · Research report</title><style>:root{color-scheme:dark}body{background:#081b23;color:#edf7f5;font:16px/1.6 system-ui,sans-serif;margin:0;padding:28px}main{max-width:1000px;margin:auto}h1{font-size:2rem}h2{color:#92d9cc}header{border-left:5px solid #31cdb2;padding:1.2rem 1.6rem;background:#102c36;border-radius:12px}.tag{color:#ffdb90;font-weight:700}pre{white-space:pre-wrap;word-break:break-word;padding:20px;background:#112833;border:1px solid #446876;border-radius:12px}small{color:#a8c5c6}</style><main><header><small>BAINP · NEUROVISION X / ADVANCED ANALYSIS</small><h1>''' + title + '''</h1><p class="tag">Research output · NOT a clinical interpretation or medical device clearance</p></header><h2>Source evidence and results</h2><pre>''' + content + '''</pre><p>QC, modality suitability, acquisition comparability, calibration and independent specialist review are required for clinical use.</p></main></html>''', encoding='utf-8')
    return output


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('capabilities')
    def out(name):
        x = sub.add_parser(name); x.add_argument('--out', type=Path, required=True);return x
    x=out('anatomy');x.add_argument('--mri', type=Path, required=True);x.add_argument('--labels', type=Path, required=True)
    x=out('mask-qc');x.add_argument('--mri', type=Path, required=True);x.add_argument('--labels', type=Path, required=True)
    x=out('wmh-volume');x.add_argument('--labels', type=Path, required=True);x.add_argument('--wmh-id',type=int,default=77)
    x=out('pet-suvr');x.add_argument('--pet',type=Path,required=True);x.add_argument('--roi',type=Path,required=True);x.add_argument('--reference',type=Path,required=True);x.add_argument('--tracer',required=True);x.add_argument('--calibration',type=Path)
    x=out('compare');x.add_argument('--baseline-labels',type=Path,required=True);x.add_argument('--followup-labels',type=Path,required=True);x.add_argument('--label-id',type=int,required=True);x.add_argument('--confirmed-same-subject',action='store_true')
    x=out('benchmark');x.add_argument('--prediction',type=Path,required=True);x.add_argument('--reference',type=Path,required=True)
    x=out('norms');x.add_argument('--csv',type=Path,required=True);x.add_argument('--region',required=True);x.add_argument('--age',required=True,type=float);x.add_argument('--volume-ml',required=True,type=float);x.add_argument('--group',default='all')
    x=sub.add_parser('register');x.add_argument('--fixed',type=Path,required=True);x.add_argument('--moving',type=Path,required=True);x.add_argument('--out-dir',type=Path,required=True);x.add_argument('--baseline-mask',type=Path);x.add_argument('--followup-mask',type=Path)
    x=sub.add_parser('model');x.add_argument('--model',choices=['synthseg','wmh-synthseg'],required=True);x.add_argument('--source',type=Path,required=True);x.add_argument('--output-labels',type=Path,required=True);x.add_argument('--native-labels',type=Path)
    x=sub.add_parser('tes-run');x.add_argument('--script',type=Path,required=True);x.add_argument('--head-model',type=Path,required=True);x.add_argument('--out-dir',type=Path,required=True);x.add_argument('--i-authorize-local-python-execution',action='store_true')
    x=sub.add_parser('html-report');x.add_argument('--input',type=Path,required=True);x.add_argument('--out',type=Path,required=True)
    x=out('qc-review');x.add_argument('--qc-json',type=Path,required=True);x.add_argument('--reviewer-id',required=True);x.add_argument('--decision',choices=['accept_for_research','reject','needs_correction'],required=True);x.add_argument('--reason',required=True)
    return p


def execute(a):
    if a.cmd == 'capabilities':return {'operation':'capabilities','result':capabilities()}
    if a.cmd == 'html-report':
        report = json.loads(a.input.read_text(encoding='utf-8'))
        print('HTML:',save_html(report,a.out));return None
    if a.cmd == 'model':
        metadata = run_freesurfer(a.model,a.source,a.output_labels)
        if a.native_labels:
            metadata['native'] = resample_discrete_to_source(a.source,a.output_labels,a.native_labels)
        return {'operation':a.cmd,'result':metadata}
    if a.cmd == 'register':
        result = rigid_registration(a.fixed,a.moving,a.out_dir,a.baseline_mask,a.followup_mask)
        write_json(a.out_dir/'registration-report.json',envelope('rigid-registration',{'baseline':a.fixed,'followup':a.moving},result))
        return {'operation':'rigid-registration','result':result}
    if a.cmd == 'tes-run':
        result = external_simnibs_script(a.script,a.head_model,a.out_dir,a.i_authorize_local_python_execution)
        write_json(a.out_dir/'simulation-report.json',envelope('simnibs-specialist-script',{'script':a.script},result))
        return {'operation':'tes-run','result':result}
    if a.cmd=='qc-review':
        if not a.reviewer_id.strip() or len(a.reason.strip())<12:raise ValueError('REVIEWER_AND_ADEQUATE_REASON_REQUIRED')
        src = json.loads(a.qc_json.read_text(encoding='utf-8'))
        result = {'input_report_sha256':digest(a.qc_json),'reviewer_id':a.reviewer_id.strip(),
                  'decision':a.decision,'reason':a.reason.strip(),
                  'clinical_review':False,'regulatory_clearance':False,
                  'technical_notes':src.get('result',{}).get('warnings',[])}
        report=envelope('research-qc-human-attestation',{'qc_report':a.qc_json},result)
        write_json(a.out,report);return report
    if a.cmd=='anatomy':
        if digest(a.mri)==digest(a.labels):raise ValueError('MRI_MUST_NOT_BE_USED_AS_ITS_OWN_LABELMAP')
        mri, im=read_nii(a.mri);labels, lab=read_nii(a.labels)
        core.exact_grid(mri.shape,mri.affine,labels.shape,labels.affine)
        result={'regions':core.region_volumes(lab,mri.affine),
                'technical_qc':core.segmentation_qc(im,lab,mri.affine)}
        sources={'mri':a.mri,'labels':a.labels}
    elif a.cmd=='mask-qc':
        if digest(a.mri)==digest(a.labels):raise ValueError('MRI_MUST_NOT_BE_USED_AS_ITS_OWN_LABELMAP')
        mri,im=read_nii(a.mri);labels,lab=read_nii(a.labels)
        core.exact_grid(mri.shape,mri.affine,labels.shape,labels.affine)
        result=core.segmentation_qc(im,lab,mri.affine);sources={'mri':a.mri,'labels':a.labels}
    elif a.cmd=='wmh-volume':
        img, lab=read_nii(a.labels);core.discrete_labels(lab)
        result=core.lesion_mask_metrics(lab==a.wmh_id,img.affine)
        result['label_id']=a.wmh_id;result['warning']='Assumes upstream output defines this label as WMH; verify exact atlas.'
        sources={'wmh_segmentation':a.labels}
    elif a.cmd=='pet-suvr':
        if len({digest(a.pet),digest(a.roi),digest(a.reference)})!=3:raise ValueError('PET_AND_MASKS_MUST_BE_DISTINCT_FILES')
        p, pet=read_nii(a.pet);r,roi=read_nii(a.roi);ref,reference=read_nii(a.reference)
        core.exact_grid(p.shape,p.affine,r.shape,r.affine);core.exact_grid(p.shape,p.affine,ref.shape,ref.affine)
        result=core.pet_suvr(pet,roi,reference);result['recorded_tracer']=a.tracer
        sources={'pet':a.pet,'roi':a.roi,'reference':a.reference}
        if a.calibration:
            calibration=json.loads(a.calibration.read_text(encoding='utf-8'))
            result['centiloid_calculation']=core.centiloid_from_validated_calibration(result['suvr'],calibration)
            sources['calibration']=a.calibration
    elif a.cmd=='compare':
        if not a.confirmed_same_subject:raise ValueError('IDENTITY_LINKAGE_NOT_CONFIRMED')
        x,base=read_nii(a.baseline_labels);y,follow=read_nii(a.followup_labels)
        result=core.paired_volumes(base,x.affine,follow,y.affine,a.label_id)
        sources={'baseline':a.baseline_labels,'followup':a.followup_labels}
    elif a.cmd=='benchmark':
        p,pred=read_nii(a.prediction);ref,truth=read_nii(a.reference)
        core.exact_grid(p.shape,p.affine,ref.shape,ref.affine)
        aa,bb=core.discrete_labels(pred),core.discrete_labels(truth)
        ids=np.union1d(np.unique(aa),np.unique(bb))
        scores=[{'label_id':int(k),'dice':core.dice(aa==k,bb==k)} for k in ids if k>0]
        result={'per_label':scores,'state':'REFERENCE_LABEL_COMPARISON_ONLY',
                'warning':'Accuracy depends on independently verified reference labels and dataset design.'}
        sources={'prediction':a.prediction,'reference_labels':a.reference}
    elif a.cmd=='norms':
        if a.age<0 or a.age>120 or a.volume_ml<0:raise ValueError('INVALID_AGE_OR_VOLUME')
        from math import erf,sqrt
        with a.csv.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        valid=[]
        for row in rows:
            try:
                if (row['region']==a.region and row['group']==a.group and
                    float(row['age_min'])<=a.age<=float(row['age_max']) and int(row['n'])>=30 and
                    row['synthetic'].lower()=='false' and all(row.get(k) for k in ('source','protocol','reference_version')) and float(row['sd_ml'])>0):
                    valid.append(row)
            except (KeyError,ValueError,TypeError):continue
        if len(valid)!=1: result={'state':'REFERENCE_UNAVAILABLE','z':None,'percentile':None}
        else:
            row=valid[0];z=(a.volume_ml-float(row['mean_ml']))/float(row['sd_ml'])
            result={'state':'DESCRIPTIVE_UNVALIDATED_REFERENCE','z':z,
                    'percentile_under_normality_assumption':50*(1+erf(z/sqrt(2))),
                    'reference':{k:row[k] for k in ('source','protocol','reference_version','n')},
                    'warning':'Cohort comparability and calibration have NOT been established by this calculation.'}
        sources={'reference_csv':a.csv}
    else:raise ValueError('UNKNOWN_COMMAND')
    report=envelope(a.cmd,sources,result)
    write_json(a.out,report)
    return report


def main(argv=None):
    a=parser().parse_args(argv)
    try:
        result=execute(a)
    except (ValueError,RuntimeError,FileNotFoundError,PermissionError,FileExistsError,ImportError,KeyError) as e:
        raise SystemExit('BAINP_V5_ERROR: '+str(e)) from e
    if result is not None:
        print(json.dumps({'operation':result['operation'],'status':'SAVED' if hasattr(a,'out') else 'READY',
                          'result':result['result']},indent=2,allow_nan=False))


if __name__=='__main__':main()
