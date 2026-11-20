"""Additive, authenticated read-only NeuroAccess integration.

Never returns another tenant's research files or creates identity links, reviewer
approvals, clinical forecasts, or unreviewed measurements.
"""
from __future__ import annotations
import importlib.util

PHASES={
 '2E':'local QC geometry and review audit CLI',
 '2F':'external FreeSurfer stats parser',
 '2G':'externally segmented FLAIR WMH quantification',
 '2H':'PET SUVR from reviewed registered masks',
 '2I':'same-subject descriptive matched-visit comparisons',
 '2J':'external DWI graph features and descriptive reference checks',
 '3A':'identity evidence contract; existing BAINP link remains authoritative',
 '3B':'review-gated structural feature contract',
 '3C':'condition-stratified cognition observations',
 '3D':'artifact-reviewed EEG spectral features',
 '3E':'consented wearable/clinical context contracts',
 '3F':'missingness-aware multimodal feature table',
 '3G':'subject-disjoint exploratory prediction with optional external evaluation',
}


def capabilities():
    return {'extension':'BAINP_Integrated_Research_Expansion_0.1.0',
            'research_only':True,'clinical_clearance':False,
            'phases':{k:{'code_present':True,'description':v,'dataset_validated':False,
                          'clinical_ready':False} for k,v in PHASES.items()},
            'dependencies':{'nibabel':importlib.util.find_spec('nibabel') is not None,
                            'SimpleITK':importlib.util.find_spec('SimpleITK') is not None,
                            'scipy':importlib.util.find_spec('scipy') is not None,
                            'sklearn':importlib.util.find_spec('sklearn') is not None},
            'external_requirements':['real WSL FreeSurfer cortical processing','reviewer training and authentication',
                'WMH masks and suitable FLAIR','PET masks and scanner/tracer metadata',
                'multi-visit identity-linked acquisitions','DWI data and validated tractography',
                'EEG data and recorded QC','representative labelled training and independent evaluation cohorts']}


def make_router(store,authenticated):
    from fastapi import APIRouter, Depends, HTTPException
    r=APIRouter(prefix='/api/bainp-research',dependencies=[Depends(authenticated)])
    @r.get('/capabilities')
    def get_capabilities():return capabilities()
    @r.get('/participant/{participant_id}/status')
    def participant_status(participant_id:str,mode:str='active'):
        require_mode=mode in ('active','demo')
        if not require_mode:raise HTTPException(422,'mode_invalid')
        from uuid import UUID
        try:pid=str(UUID(participant_id))
        except ValueError:raise HTTPException(422,'participant_id_invalid')
        with store.connect() as db:
            person=db.execute('SELECT id FROM participants WHERE id=? AND mode=?',(pid,mode)).fetchone()
            if not person:raise HTTPException(404,'participant_not_found')
            table_exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nt_imaging_links'").fetchone()
            linked=db.execute('SELECT COUNT(*) FROM nt_imaging_links WHERE participant_id=? AND mode=?',(pid,mode)).fetchone()[0] if table_exists else 0
        return {'participant_id':pid,'mode':mode,'verified_research_identity_links':linked,
                'identity_links_present':linked>0,
                'personal_twin_available':'UNKNOWN_UNTIL_VERIFIED_IMAGING_AND_QC',
                'research_imaging_preview_is_not_an_identity_link':True,
                'independent_anatomical_acceptance_not_implied':True,
                'research_only':True}
    return r
