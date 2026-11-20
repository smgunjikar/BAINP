"""BAINP 2E–2J + 3A–3G command line research engine.

No commands write to NeuroAccess accounts or existing MRI files; outputs are new JSON.
"""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
from .common import Blocked, read_json, write_json_new, report
from .ledger import Ledger
from . import imaging, twin, prediction


def parser():
    ap=argparse.ArgumentParser(prog='python -m bainp_expansion.cli',description='Research pipelines, not clinical diagnostics')
    sp=ap.add_subparsers(dest='command',required=True)
    def cmd(name,help_,params=()):
        p=sp.add_parser(name,help=help_)
        for opt,required in params:
            p.add_argument('--'+opt.replace('_','-'),required=required)
        return p
    cmd('capabilities','Phase readiness and external dependencies')
    cmd('qc-anatomy','2E verify MRI/native label geometry', [('mri',True),('labels',True),('output',True),('expected_mri_sha',False),('expected_label_sha',False)])
    cmd('register-evidence','2E store read-only Phase2C evidence identity', [('evidence',True),('ledger',True),('submitter',True),('mri',True),('labels',True)])
    cmd('review','2E append reviewer observation (not clinical approval)', [('ledger',True),('scan_id',True),('reviewer',True),('affiliation',True),('decision',True),('note',True)])
    cmd('review-status','2E audit chain and review status', [('ledger',True),('scan_id',True)])
    cmd('freesurfer','2F import genuine FreeSurfer output', [('subject_dir',True),('input_t1',True),('output',True),('input_sha',False)])
    cmd('wmh','2G binary WMH mask quantification, requires actual FLAIR', [('flair',True),('mask',True),('provenance',True),('output',True)])
    cmd('pet','2H PET target/reference SUVR on PET grid', [('pet',True),('roi',True),('reference',True),('metadata',True),('output',True)])
    cmd('register-mri','2H/2I SimpleITK research rigid registration', [('fixed',True),('moving',True),('metadata',True),('output_dir',True)])
    cmd('longitudinal','2I matched-subject validated inputs, descriptive changes', [('baseline',True),('followup',True),('output',True)])
    cmd('connectome','2J graph features from externally derived DWI edge CSV', [('edges',True),('metadata',True),('output',True)])
    cmd('normative','2J descriptive reference comparison', [('observation',True),('reference',True),('output',True)])
    cmd('identity-contract','3A test evidence identity contract; does not write BAINP links', [('identity',True),('output',True)])
    cmd('structural-twin','3B gated structural twin evidence contract', [('evidence',True),('ledger',True),('identity',True),('measurements',True),('output',True)])
    cmd('cognition','3C group comparable cognition observations', [('records',True),('output',True)])
    cmd('eeg','3D Welch EEG on pre-reviewed uV arrays, npy no pickle', [('signals',True),('sampling_hz',True),('metadata',True),('output',True)])
    cmd('context','3E wearable/clinical contract', [('records',True),('output',True)])
    cmd('fusion','3F missingness-aware visits', [('records',True),('output',True)])
    cmd('train','3G exploratory group-disjoint logistic baseline', [('train_csv',True),('features',True),('external_csv',False),('output',True)])
    cmd('scenario','3G hypothetical scores NOT causal claims', [('model',True),('features',True),('output',True)])
    return ap


def run(a):
    c=a.command
    if c=='capabilities':
        from .api import capabilities
        return capabilities()
    if c=='qc-anatomy':return imaging.anatomy_qc(a.mri,a.labels,a.expected_mri_sha,a.expected_label_sha)
    if c=='register-evidence':
        from .common import sha256_file,require
        e=read_json(a.evidence)
        require(sha256_file(a.mri)==e['source_image_sha256'],'SOURCE_MRI_HASH_MISMATCH')
        require(sha256_file(a.labels)==e['atlas_label_sha256'],'LABELS_SHA256_MISMATCH')
        return Ledger(a.ledger).register(e,a.submitter)
    if c=='review':return Ledger(a.ledger).review(a.scan_id,a.reviewer,a.affiliation,a.decision,a.note)
    if c=='review-status':return Ledger(a.ledger).status(a.scan_id)
    if c=='freesurfer':return imaging.structural_from_freesurfer(a.subject_dir,a.input_t1,a.input_sha)
    if c=='wmh':return imaging.wmh_burden(a.flair,a.mask,read_json(a.provenance))
    if c=='pet':return imaging.pet_suvr(a.pet,a.roi,a.reference,read_json(a.metadata))
    if c=='register-mri':return imaging.research_rigid_registration(a.fixed,a.moving,a.output_dir,read_json(a.metadata))
    if c=='longitudinal':return imaging.longitudinal(read_json(a.baseline),read_json(a.followup))
    if c=='connectome':
        with open(a.edges,newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
        return imaging.connectome(rows,read_json(a.metadata))
    if c=='normative':return imaging.normative_z(read_json(a.observation),read_json(a.reference))
    if c=='identity-contract':return twin.identity_link(read_json(a.identity))
    if c=='structural-twin':return twin.structural_twin(read_json(a.evidence),Ledger(a.ledger).status(read_json(a.evidence)['scan_id']),read_json(a.identity),read_json(a.measurements))
    if c=='cognition':return twin.cognitive_trajectory(read_json(a.records))
    if c=='eeg':
        import numpy as np
        return twin.eeg_band_features(np.load(a.signals,allow_pickle=False),float(a.sampling_hz),read_json(a.metadata))
    if c=='context':return twin.behavior_clinical(read_json(a.records))
    if c=='fusion':return twin.assemble_multimodal(read_json(a.records))
    if c=='train':return prediction.train_exploratory(a.train_csv,[s.strip() for s in a.features.split(',')],a.external_csv)
    if c=='scenario':return prediction.explore_scenario(read_json(a.model),read_json(a.features))
    raise Blocked('UNKNOWN_COMMAND')


def main(argv=None):
    ap=parser();a=ap.parse_args(argv)
    try:
        result=run(a)
        if getattr(a,'output',None):
            path=write_json_new(a.output,result)
            print(json.dumps({'state':'OUTPUT_CREATED','path':str(path),'phase':result.get('phase')},indent=2))
        else: print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
        return 0
    except (Blocked,FileExistsError,KeyError,ValueError,OSError) as exc:
        print(json.dumps({'state':'BLOCKED','error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())
