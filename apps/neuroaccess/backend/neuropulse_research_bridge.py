"""Read-only, explicitly authorized local research EEG API (no patient mapping)."""
from __future__ import annotations
import csv
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException

SCHEMA = 'bainp-neuropulse-research-bridge-v1'
SUBJECT = re.compile(r'^sub-\d{3}$')
BANDS = ('delta_uv2', 'theta_uv2', 'alpha_uv2', 'beta_uv2')


def _authorize(secret: str | None):
    configured = os.getenv('BAINP_NEUROPULSE_RESEARCH_KEY', '')
    if len(configured) < 24 or not secret or not hmac.compare_digest(configured, secret):
        raise HTTPException(status_code=403, detail='research_authorization_required')


def _run_dir() -> Path:
    value = os.getenv('BAINP_NEUROPULSE_MAIN_RUN', '')
    if not value:
        raise HTTPException(status_code=503, detail='research_run_not_configured')
    run = Path(value).resolve()
    if not run.is_dir() or not (run/'features.csv').is_file() or not (run/'run_summary.json').is_file():
        raise HTTPException(status_code=503, detail='research_run_missing')
    return run


def _rows(run: Path):
    with (run/'features.csv').open('r', encoding='utf-8-sig', newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)>10000 or len({r.get('subject') for r in rows})!=len(rows):
        raise HTTPException(503,'invalid_research_index')
    result=[]
    for row in rows:
        sub=row.get('subject','')
        if not SUBJECT.fullmatch(sub):
            raise HTTPException(503,'invalid_research_subject')
        state=row.get('status','')
        if state not in ('DESCRIPTIVE_AVAILABLE','INSUFFICIENT_WINDOWS','FAILED'):
            raise HTTPException(503,'invalid_research_status')
        def number(key):
            x=row.get(key,'')
            return float(x) if x not in ('',None) and x.lower() not in ('nan','inf','-inf') else None
        result.append({'subject':sub,'status':state,
          'windows_total':int(row['windows_total']),
          'windows_retained':int(row['windows_retained']),
          'windows_excluded':int(row['windows_excluded']),
          'features':{b:number(b) if state=='DESCRIPTIVE_AVAILABLE' else None for b in BANDS},
          'source_sha256':row.get('sha256',''),
          'clinical_qc_approved':False})
    return result


def _details(run:Path,sub:str,row:dict):
    path=run/(sub+'.json')
    if not path.is_file():
        raise HTTPException(503,'research_detail_missing')
    try:
        with path.open(encoding='utf-8') as f:record=json.load(f)
    except (OSError,ValueError):
        raise HTTPException(503,'research_detail_invalid')
    if record.get('subject')!=sub or record.get('sha256')!=row['source_sha256'] or record.get('source_unchanged') is not True:
        raise HTTPException(503,'research_provenance_mismatch')
    return {
      'schema':SCHEMA,'subject':sub,'status':row['status'],
      'recording_condition':'eyes-closed resting EEG (source file naming; verify protocol metadata)',
      'sampling_hz':record.get('sampling_hz'),
      'duration_s':record.get('duration_s'),
      'channels':record.get('eeg_channels',[]),
      'window_seconds':record.get('window_seconds'),
      'amplitude_review_threshold_uv':record.get('amplitude_review_threshold_uv'),
      'excluded_intervals':record.get('excluded_intervals',[]),
      'windows_total':row['windows_total'],'windows_retained':row['windows_retained'],
      'windows_excluded':row['windows_excluded'],
      'features':row['features'],
      'neuroguard':{'state':'RESEARCH_ONLY_REVIEW_REQUIRED','clinical_release':False,
         'reason':'Unvalidated thresholded EEG features are not a clinical biomarker or diagnosis.'},
      'neuroproof':{'source_sha256':row['source_sha256'],'source_unchanged':True,
         'processing_schema':record.get('schema'),'research_only':True,
         'clinical_qc_approved':False,'patient_identity_linkage':'PROHIBITED_UNVERIFIED'},
      'limitations':record.get('important_limitations',[]),
      'neurotwin_eligibility':False,
      'clinical_qc_approved':False,
    }


def make_router(authenticated):
    router=APIRouter(prefix='/api/neuropulse/research/v1',dependencies=[Depends(authenticated)])

    @router.get('/subjects')
    def subjects(x_bainp_research_key: str | None = Header(default=None)):
        _authorize(x_bainp_research_key)
        run=_run_dir(); rows=_rows(run)
        counts={s:sum(r['status']==s for r in rows) for s in ('DESCRIPTIVE_AVAILABLE','INSUFFICIENT_WINDOWS','FAILED')}
        return {'schema':SCHEMA,'research_only':True,'clinical_qc_approved':False,
           'patient_identity_linkage':'PROHIBITED_UNVERIFIED',
           'neuroguard':'REVIEW_REQUIRED_NOT_CLINICAL',
           'neuroproof':'SOURCE_HASHES_AND_PROCESSING_VERSIONS_AVAILABLE',
           'source_run':run.name,'counts':counts,'subjects':rows}

    @router.get('/subjects/{sub}')
    def subject(sub:str,x_bainp_research_key: str | None = Header(default=None)):
        _authorize(x_bainp_research_key)
        if not SUBJECT.fullmatch(sub):raise HTTPException(404,'subject_not_found')
        run=_run_dir();row=next((r for r in _rows(run) if r['subject']==sub),None)
        if row is None:raise HTTPException(404,'subject_not_found')
        return _details(run,sub,row)
    return router
