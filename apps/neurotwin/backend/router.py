"""Authenticated participant-specific NeuroTwin adapters and identity registry.
Same database, operator session, CSRF header and participant deletion boundary as BAINP.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from nt_engine import build, canonical
from nt_state import enhance,toy_forecast
from nt_guard import forecast
from nt_neural_contract import NeuralRecord
from nt_monitor import record_refresh,governance
from nt_anatomy import load_anatomy

Mode=Literal['active','demo']
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Link(Strict):
    scan_id:str=Field(pattern=r'^[0-9a-f]{24}$')
    expected_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    identity_verified:Literal[True]
    note:str=Field(min_length=15,max_length=500)
class Scenario(Strict):
    baseline_mmse:float|None=Field(default=None,ge=0,le=30,allow_inf_nan=False)
    age:float|None=Field(default=None,ge=18,le=110,allow_inf_nan=False)
    education_years:float|None=Field(default=None,ge=0,le=40,allow_inf_nan=False)
    @model_validator(mode='after')
    def valid(self):
        if all(x is None for x in (self.baseline_mmse,self.age,self.education_years)):raise ValueError('one hypothetical input required')
        return self
class AnatomyRegistration(Strict):
    package_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    identity_verified:Literal[True]
    consent_confirmed:Literal[True]
class Measure(Strict):
    metric:Literal['delta_power','theta_power','alpha_power','beta_power','peak_alpha_frequency','spectral_entropy','clinical_measurement','age','education_years']
    value:float=Field(allow_inf_nan=False)
    unit:Literal['uV2','Hz','normalized','score','years']
    instrument:str|None=Field(default=None,max_length=80)
    context:str=Field(min_length=1,max_length=160)
    quality:Literal['usable','review','invalid']
    @model_validator(mode='after')
    def check_units(self):
        unit='uV2' if self.metric.endswith('_power') else {'peak_alpha_frequency':'Hz','spectral_entropy':'normalized','clinical_measurement':'score','age':'years','education_years':'years'}[self.metric]
        if self.unit!=unit:raise ValueError('metric/unit mismatch')
        if self.metric!='clinical_measurement' and self.value<0:raise ValueError('negative signal metric')
        if self.metric=='spectral_entropy' and self.value>1:raise ValueError('normalized entropy exceeds one')
        return self
class SourceRecord(Strict):
    source:Literal['NeuroPulse','Clinical']
    record_id:str=Field(pattern=r'^[A-Za-z0-9_.:-]{1,100}$')
    source_subject:str=Field(min_length=1,max_length=100)
    revision:int=Field(ge=1)
    observed_at:AwareDatetime
    protocol:str=Field(min_length=1,max_length=100)
    provenance:str=Field(min_length=10,max_length=500)
    identity_verified:Literal[True]
    consent_confirmed:Literal[True]
    clinical_state:Literal['MCI','clinician_recorded_dementia','control','other','unknown']|None=None
    source_cohort:str|None=Field(default=None,max_length=100)
    observations:list[Measure]=Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def valid(self):
        if self.observed_at>datetime.now(timezone.utc):raise ValueError('future observation')
        self.observed_at=self.observed_at.astimezone(timezone.utc)
        if any((o.metric in ('clinical_measurement','age','education_years'))!=(self.source=='Clinical') for o in self.observations):raise ValueError('source/metric mismatch')
        if len({(o.metric,o.context) for o in self.observations})!=len(self.observations):raise ValueError('duplicate metric/context')
        return self

SCHEMA='''CREATE TABLE IF NOT EXISTS nt_imaging_links(
 participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,cohort TEXT NOT NULL,subject TEXT NOT NULL,
 anchor_id TEXT NOT NULL,anchor_sha256 TEXT NOT NULL,note TEXT NOT NULL,verified_at TEXT NOT NULL,
 PRIMARY KEY(mode,cohort,subject));
CREATE TABLE IF NOT EXISTS nt_source_records(
 participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,source TEXT NOT NULL,record_id TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,
 PRIMARY KEY(mode,source,record_id));'''

def make_router(store,authenticated,cognition_analytics=None):
    router=APIRouter(prefix='/api/neurotwin',dependencies=[Depends(authenticated)])
    with store.connect(True) as c:c.executescript(SCHEMA)
    with store.connect(True) as c:c.execute('''CREATE TABLE IF NOT EXISTS nt_neural_records(
        participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,record_id TEXT,
        revision INTEGER,payload TEXT,PRIMARY KEY(mode,record_id))''')
    with store.connect(True) as c:
        columns={r['name'] for r in c.execute('PRAGMA table_info(nt_neural_records)')}
        if 'summary' not in columns:c.execute('ALTER TABLE nt_neural_records ADD COLUMN summary TEXT')
        c.execute("UPDATE nt_neural_records SET summary=json_remove(payload,'$.signal_uv','$.spectrum','$.covariance_uv2') WHERE summary IS NULL")
    with store.connect(True) as c:c.execute('''CREATE TABLE IF NOT EXISTS nt_anatomical_records(participant_id TEXT REFERENCES participants(id) ON DELETE CASCADE,mode TEXT,package_sha256 TEXT,scan_id TEXT,PRIMARY KEY(mode,package_sha256))''')
    cache={}
    def person(c,pid,mode):
        row=c.execute('SELECT * FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone()
        if not row:raise HTTPException(404,'participant_not_found')
        return row
    def catalog(mode):
        # Derive tenant from authenticated account context; never from URL person/cohort.
        from accounts import require_identity
        from nv_queue import storage_root
        root=storage_root(require_identity(),mode)
        path=root/'catalog.json'
        if not path.is_file():return root,[]
        rows=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows,list):raise ValueError('invalid imaging catalog')
        return root,[r for r in rows if bool(r.get('synthetic'))==(mode=='demo')]
    def metadata(root,entry):
        identifier=entry['id']
        if not re.fullmatch(r'[0-9a-f]{24}',identifier):raise ValueError('invalid scan id')
        path=root/(identifier+'.json');stat=path.stat()
        key=(str(path),stat.st_mtime_ns,stat.st_ctime_ns,stat.st_size,entry['package_sha256'])
        if key not in cache:
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=entry['package_sha256']:raise ValueError('imaging package hash mismatch')
            m=json.loads(raw)['metadata']
            if bool(m.get('synthetic'))!=bool(entry.get('synthetic')):raise ValueError('imaging mode mismatch')
            if any(m.get(k)!=entry.get(k) for k in ('cohort','subject')):raise ValueError('imaging identity mismatch')
            if len(cache)>256:cache.clear()
            cache[key]=m
        return cache[key]
    @router.get('/demo-example')
    def example(profile:Literal['control','impairment']='control'):
        from nt_demo import demo_snapshot
        return demo_snapshot(profile)
    @router.get('/demo-neural/{record_id}')
    def demo_neural(record_id:str,profile:Literal['control','impairment']='control'):
        from nt_demo import fixtures
        record=next((r for r in fixtures()[profile]['neural'] if r['record_id']==record_id),None)
        if not record:raise HTTPException(404,'recording_not_found')
        return record
    @router.post('/demo-scenario')
    def demo_scenario(profile:Literal['control','impairment']='control',score:float=Query(default=75,ge=0,le=100),sleep:float=Query(default=7,ge=0,le=24)):
        return toy_forecast(score,5 if profile=='impairment' else 0,sleep)
    @router.get('/participants/{pid}/anatomy/{scan_id}')
    def anatomy(pid:UUID,scan_id:str,mode:Mode):
        with store.connect() as c:
            person(c,pid,mode)
            links=[dict(r) for r in c.execute('SELECT * FROM nt_imaging_links WHERE participant_id=? AND mode=?',(str(pid),mode))]
        try:
            root,entries=catalog(mode)
            entry=next((r for r in entries if r['id']==scan_id and any(x['cohort']==r.get('cohort') and x['subject']==r.get('subject') for x in links)),None)
            if not entry:raise HTTPException(404,'verified_linked_scan_not_found')
            metadata(root,entry)
            raw=(root/(scan_id+'.json')).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=entry['package_sha256']:raise ValueError('hash changed')
            return json.loads(raw)
        except (OSError,ValueError,KeyError):raise HTTPException(503,'imaging_package_unavailable')
    @router.put('/participants/{pid}/neural-records')
    def put_neural(pid:UUID,mode:Mode,payload:NeuralRecord):
        data=payload.model_dump(mode='json');raw=canonical(data);summary=canonical({k:v for k,v in data.items() if k not in ('signal_uv','spectrum','covariance_uv2')})
        with store.connect(True) as c:
            person(c,pid,mode)
            for linked in c.execute("SELECT participant_id,payload FROM nt_source_records WHERE mode=? AND source='NeuroPulse'",(mode,)):
                if linked['participant_id']!=str(pid) and json.loads(linked['payload'])['source_subject']==payload.source_subject:raise HTTPException(409,'neural_subject_identity_conflict')
            old=c.execute('SELECT * FROM nt_neural_records WHERE mode=? AND record_id=?',(mode,payload.record_id)).fetchone()
            if old:
                if old['participant_id']!=str(pid):raise HTTPException(409,'neural_identity_conflict')
                if json.loads(old['payload'])['source_subject']!=payload.source_subject:raise HTTPException(409,'neural_subject_changed')
                if old['payload']==raw:return {'stored':True,'unchanged':True}
                if payload.revision!=old['revision']+1:raise HTTPException(409,'neural_revision_conflict')
                c.execute('UPDATE nt_neural_records SET revision=?,payload=?,summary=? WHERE mode=? AND record_id=?',(payload.revision,raw,summary,mode,payload.record_id))
            else:
                if payload.revision!=1:raise HTTPException(409,'first_revision_must_be_one')
                for r in c.execute('SELECT participant_id,payload FROM nt_neural_records WHERE mode=?',(mode,)):
                    if r['participant_id']!=str(pid) and json.loads(r['payload'])['source_subject']==payload.source_subject:raise HTTPException(409,'neural_subject_identity_conflict')
                c.execute('INSERT INTO nt_neural_records VALUES(?,?,?,?,?,?)',(str(pid),mode,payload.record_id,payload.revision,raw,summary))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('neurotwin_neural_update',str(pid),mode,datetime.now(timezone.utc).isoformat()))
        return {'stored':True,'revision':payload.revision}
    @router.get('/participants/{pid}/neural-records/{record_id}')
    def get_neural(pid:UUID,mode:Mode,record_id:str):
        with store.connect() as c:
            person(c,pid,mode)
            r=c.execute('SELECT payload FROM nt_neural_records WHERE participant_id=? AND mode=? AND record_id=?',(str(pid),mode,record_id)).fetchone()
        if not r:raise HTTPException(404,'recording_not_found')
        return json.loads(r['payload'])
    @router.delete('/participants/{pid}/neural-records/{record_id}')
    def delete_neural(pid:UUID,mode:Mode,record_id:str):
        with store.connect(True) as c:
            person(c,pid,mode);c.execute('DELETE FROM nt_neural_records WHERE participant_id=? AND mode=? AND record_id=?',(str(pid),mode,record_id))
        return {'deleted':True}
    @router.put('/participants/{pid}/anatomical-records')
    def register_anatomy(pid:UUID,mode:Mode,payload:AnatomyRegistration):
        try:pack=load_anatomy(payload.package_sha256)
        except (OSError,ValueError,KeyError,TypeError):raise HTTPException(422,'invalid_prepared_anatomy_package')
        scan=anatomy(pid,pack['scan_id'],mode)
        if scan['metadata'].get('source_sha256',{}).get('image')!=pack['input_mri_sha256']:raise HTTPException(409,'anatomy_source_mri_hash_differs')
        with store.connect(True) as c:
            person(c,pid,mode)
            old=c.execute('SELECT participant_id FROM nt_anatomical_records WHERE mode=? AND package_sha256=?',(mode,payload.package_sha256)).fetchone()
            if old and old['participant_id']!=str(pid):raise HTTPException(409,'anatomy_identity_conflict')
            c.execute('DELETE FROM nt_anatomical_records WHERE participant_id=? AND mode=? AND scan_id=?',(str(pid),mode,pack['scan_id']))
            c.execute('INSERT OR IGNORE INTO nt_anatomical_records VALUES(?,?,?,?)',(str(pid),mode,payload.package_sha256,pack['scan_id']))
        return {'registered':True}
    @router.get('/participants/{pid}/anatomical-records/{digest}')
    def get_anatomy(pid:UUID,mode:Mode,digest:str):
        with store.connect() as c:
            person(c,pid,mode)
            r=c.execute('SELECT * FROM nt_anatomical_records WHERE participant_id=? AND mode=? AND package_sha256=?',(str(pid),mode,digest)).fetchone()
        if not r:raise HTTPException(404,'anatomy_not_found')
        # Revalidate the identity link on every access; unlinking MRI revokes access.
        anatomy(pid,r['scan_id'],mode)
        try:return load_anatomy(digest)
        except (OSError,ValueError,KeyError,TypeError):raise HTTPException(503,'anatomy_package_unavailable')
    @router.post('/participants/{pid}/scenario')
    def scenario(pid:UUID,mode:Mode,payload:Scenario):
        with store.connect() as c:
            person(c,pid,mode)
            records=[json.loads(r['payload']) for r in c.execute("SELECT payload FROM nt_source_records WHERE participant_id=? AND mode=? AND source='Clinical'",(str(pid),mode))]
        return forecast(records,payload.model_dump(exclude_none=True))
    @router.get('/participants/{pid}/imaging-options')
    def options(pid:UUID,mode:Mode):
        with store.connect() as c:person(c,pid,mode)
        try:
            _,entries=catalog(mode)
            return {'items':[{k:r.get(k) for k in ('id','cohort','subject','visit','date','modality','package_sha256','synthetic')} for r in entries]}
        except (OSError,ValueError,KeyError):raise HTTPException(503,'imaging_catalog_unavailable')
    @router.post('/participants/{pid}/imaging-links')
    def link(pid:UUID,mode:Mode,payload:Link):
        try:
            root,entries=catalog(mode)
            entry=next((r for r in entries if r['id']==payload.scan_id),None)
            if not entry:raise HTTPException(404,'scan_not_found')
            if entry['package_sha256']!=payload.expected_sha256:raise HTTPException(409,'catalog_changed_reload')
            m=metadata(root,entry)
            if not m.get('cohort') or not m.get('subject'):raise HTTPException(422,'source_identity_missing')
        except (OSError,ValueError,KeyError):raise HTTPException(503,'imaging_package_unavailable')
        with store.connect(True) as c:
            person(c,pid,mode)
            # bb_cross_identity_guard_v1: exact cohort namespace, no alias guessing.
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='bb_identity_links'").fetchone():
                bb_link=c.execute('SELECT participant_id FROM bb_identity_links WHERE mode=? AND cohort=? AND source_subject=?',(mode,m['cohort'],m['subject'])).fetchone()
                if bb_link and bb_link['participant_id']!=str(pid):raise HTTPException(409,'source_identity_conflicts_with_brainbody')
            old=c.execute('SELECT * FROM nt_imaging_links WHERE mode=? AND cohort=? AND subject=?',(mode,m['cohort'],m['subject'])).fetchone()
            if old:
                if old['participant_id']!=str(pid):raise HTTPException(409,'source_subject_already_linked_to_another_participant')
                return {'linked':True,'already_linked':True}
            c.execute('INSERT INTO nt_imaging_links VALUES(?,?,?,?,?,?,?,?)',
                (str(pid),mode,m['cohort'],m['subject'],payload.scan_id,payload.expected_sha256,payload.note,datetime.now(timezone.utc).isoformat()))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('neurotwin_identity_link',str(pid),mode,datetime.now(timezone.utc).isoformat()))
        return {'linked':True}
    @router.delete('/participants/{pid}/imaging-links')
    def unlink(pid:UUID,mode:Mode,cohort:str,subject:str):
        with store.connect(True) as c:
            person(c,pid,mode)
            c.execute('DELETE FROM nt_imaging_links WHERE participant_id=? AND mode=? AND cohort=? AND subject=?',(str(pid),mode,cohort,subject))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('neurotwin_identity_unlink',str(pid),mode,datetime.now(timezone.utc).isoformat()))
        return {'unlinked':True}
    @router.put('/participants/{pid}/source-records')
    def ingest(pid:UUID,mode:Mode,payload:SourceRecord):
        data=payload.model_dump(mode='json',exclude_none=True);raw=canonical(data)
        with store.connect(True) as c:
            person(c,pid,mode)
            if payload.source=='NeuroPulse':
                for linked in c.execute('SELECT participant_id,payload FROM nt_neural_records WHERE mode=?',(mode,)):
                    if linked['participant_id']!=str(pid) and json.loads(linked['payload'])['source_subject']==payload.source_subject:raise HTTPException(409,'source_subject_identity_conflict')
            if payload.source_cohort and c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='bb_identity_links'").fetchone():
                bb_link=c.execute('SELECT participant_id FROM bb_identity_links WHERE mode=? AND cohort=? AND source_subject=?',(mode,payload.source_cohort,payload.source_subject)).fetchone()
                if bb_link and bb_link['participant_id']!=str(pid):raise HTTPException(409,'source_identity_conflicts_with_brainbody')
            old=c.execute('SELECT * FROM nt_source_records WHERE mode=? AND source=? AND record_id=?',(mode,payload.source,payload.record_id)).fetchone()
            if old:
                if old['participant_id']!=str(pid):raise HTTPException(409,'source_record_identity_conflict')
                prior=json.loads(old['payload'])
                if prior['source_subject']!=payload.source_subject:raise HTTPException(409,'source_subject_changed')
                if old['payload']==raw:return {'stored':True,'unchanged':True}
                if payload.revision!=old['revision']+1:raise HTTPException(409,'source_revision_conflict')
                c.execute('UPDATE nt_source_records SET revision=?,payload=? WHERE mode=? AND source=? AND record_id=?',(payload.revision,raw,mode,payload.source,payload.record_id))
            else:
                if payload.revision!=1:raise HTTPException(409,'first_revision_must_be_one')
                # A source's participant identifier cannot belong to two local people.
                for r in c.execute('SELECT participant_id,payload FROM nt_source_records WHERE mode=? AND source=?',(mode,payload.source)):
                    if r['participant_id']!=str(pid) and json.loads(r['payload'])['source_subject']==payload.source_subject:raise HTTPException(409,'source_subject_identity_conflict')
                c.execute('INSERT INTO nt_source_records VALUES(?,?,?,?,?,?)',(str(pid),mode,payload.source,payload.record_id,payload.revision,raw))
            c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',('neurotwin_source_update',str(pid),mode,datetime.now(timezone.utc).isoformat()))
        return {'stored':True,'revision':payload.revision}
    @router.delete('/participants/{pid}/source-records/{record_id}')
    def delete_record(pid:UUID,mode:Mode,record_id:str,source:Literal['NeuroPulse','Clinical']):
        with store.connect(True) as c:
            person(c,pid,mode)
            c.execute('DELETE FROM nt_source_records WHERE participant_id=? AND mode=? AND source=? AND record_id=?',(str(pid),mode,source,record_id))
        return {'deleted':True}
    @router.get('/participants/{pid}')
    def snapshot(pid:UUID,mode:Mode):
        started=datetime.now(timezone.utc).isoformat();states={};wear=[];images=[];neural=[]
        with store.connect() as c:
            p=person(c,pid,mode)
            identity={'participant_id':str(pid),'mode':mode,'display_name':json.loads(p['profile'])['display_name'],'profile_revision':p['revision']}
            links=[dict(r) for r in c.execute('SELECT * FROM nt_imaging_links WHERE participant_id=? AND mode=? ORDER BY cohort,subject',(str(pid),mode))]
            forwarded=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM nt_source_records WHERE participant_id=? AND mode=? ORDER BY source,record_id',(str(pid),mode))]
            neural=[json.loads(r['payload']) for r in c.execute('SELECT summary AS payload FROM nt_neural_records WHERE participant_id=? AND mode=? ORDER BY record_id',(str(pid),mode))]
            neural.sort(key=lambda r:r['observed_at'])
            for r in neural:
                forwarded.append(dict(source='NeuroPulse',record_id=r['record_id'],source_subject=r['source_subject'],revision=r['revision'],observed_at=r['observed_at'],protocol=r['protocol'],provenance=r['provenance'],observations=[dict(metric=k,value=v,unit='Hz' if k=='peak_alpha_frequency' else 'normalized' if k=='spectral_entropy' else 'uV2',context=r['pipeline'],quality=r['quality']) for k,v in r['features'].items() if v is not None]))
            installed=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sense_observations'").fetchone()
            if installed:
                try:
                    wear=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM sense_observations WHERE participant_id=? AND mode=? ORDER BY source_id',(str(pid),mode))]
                    states['NeuroSense']={'state':'available' if wear else 'empty','count':len(wear),'transport':'stored observations; no connection implied'}
                except (ValueError,KeyError):states['NeuroSense']={'state':'error','count':0}
            else:states['NeuroSense']={'state':'adapter_not_installed','count':0}
        cog={}
        if cognition_analytics:
            try:
                cog=cognition_analytics(pid=pid,mode=mode)
                states['NeuroCognition X']={'state':'available' if cog['total_sessions'] else 'empty','count':cog['total_sessions']}
            except HTTPException:raise
            except (ValueError,KeyError,TypeError):states['NeuroCognition X']={'state':'error','count':0}
        else:states['NeuroCognition X']={'state':'adapter_not_installed','count':0}
        try:
            root,entries=catalog(mode)
            for entry in entries:
                if any(x['cohort']==entry.get('cohort') and x['subject']==entry.get('subject') for x in links):
                    m=json.loads(canonical(metadata(root,entry)))
                    # Read-only QC notes are strictly scoped to the same tenant/scan ID.
                    review_path=root/'review_events'/(entry['id']+'.jsonl')
                    if review_path.is_file():
                        try:
                            if review_path.stat().st_size>1024*1024:raise ValueError('review_log_too_large')
                            lines=review_path.read_text(encoding='utf-8').splitlines()
                            notes=[json.loads(line) for line in lines if line]
                            last=notes[-1] if notes else None
                            if last and last.get('scan_id')==entry['id'] and last.get('disposition') in ('NEEDS_REVIEW','REJECTED'):
                                m['phase2b_review_status']=last['disposition']
                                m['review']=last['disposition']
                        except (OSError,ValueError,KeyError):
                            m['phase2b_review_status']='REVIEW_AUDIT_UNAVAILABLE'
                            m['review']='NEEDS_REVIEW'
                    images.append({'id':entry['id'],'package_sha256':entry['package_sha256'],'metadata':m})
            states['NeuroVision']={'state':'available' if images else ('linked_source_missing' if links else 'identity_link_required'),'count':len(images)}
        except (OSError,ValueError,KeyError):
            images=[];states['NeuroVision']={'state':'error','count':0}
        images.sort(key=lambda r:(r['metadata'].get('date') or '',r['id']))
        for source in ('NeuroPulse','Clinical'):
            n=sum(r['source']==source for r in forwarded)
            states[source]={'state':'available' if n else 'no_linked_source_records','count':n,'transport':'versioned source-record API; acquisition adapter must publish updates'}
        result=build(cog,wear,images,forwarded,states,identity,links)
        result['imaging_qc']=[{'scan_id':image['id'], 'research_review':image['metadata'].get('phase2b_review_status',image['metadata'].get('review','UNRECORDED')), 'atlas_labels_present':bool(image['metadata'].get('source_sha256',{}).get('labels')), 'longitudinal_eligible':False, 'explanation':'No validated comparable longitudinal structural MRI series established.'} for image in images]
        summaries=[{k:v for k,v in r.items() if k not in ('signal_uv','spectrum','covariance_uv2')} for r in neural]
        regional=[]
        with store.connect() as c:
            prepared=[dict(r) for r in c.execute('SELECT * FROM nt_anatomical_records WHERE participant_id=? AND mode=?',(str(pid),mode))]
        for entry in prepared:
            scan=next((i for i in images if i['id']==entry['scan_id']),None)
            if scan is None:continue
            try:
                pack=load_anatomy(entry['package_sha256'],geometry=False)
                if scan['metadata'].get('source_sha256',{}).get('image')!=pack['input_mri_sha256']:raise ValueError('source changed')
                regional.append(dict(package_sha256=entry['package_sha256'],scan_id=entry['scan_id'],measurements=pack['measurements'],surfaces=[{k:v for k,v in item.items() if k not in ('vertices_mm','faces')} for item in pack['surfaces']],review_reference=pack['review_reference'],freesurfer_version=pack.get('freesurfer_version','unrecorded')))
            except (OSError,ValueError,KeyError,TypeError):result['issues'].append('A supplied anatomical package failed verification; it was excluded.')
        result['regional_anatomy']=regional
        # brain_body_context_adapter_v1: consent-filtered and nonsensitive.
        from brainbody_bridge import for_twin
        result['brain_body']=for_twin(store,pid,mode,cognition=cog)
        states['BBC-BE']={'state':'available' if result['brain_body']['record_count'] else 'no_authorized_context','count':result['brain_body']['record_count']}
        result=enhance(result,forwarded,summaries)
        from prevention_bridge import for_twin as careloop_for_twin
        result['careloop_markers']=careloop_for_twin(store,pid,mode)
        result['revision']=hashlib.sha256(canonical([result['revision'],result['careloop_markers']]).encode()).hexdigest()
        history=record_refresh(store,str(pid),mode,result['revision'],states)
        result['governance']=governance(states,history)
        # neurocontinuum_workflow_history_v1: descriptive state markers, no model execution.
        from neurocontinuum_bridge import for_twin as continuum_for_twin
        result['neurocontinuum'] = continuum_for_twin(store, str(pid), mode)
        result.update(read_started_at=started,read_finished_at=datetime.now(timezone.utc).isoformat(),
                      refresh_seconds=10,read_consistency='Sources read sequentially; this is not a synchronized multimodal acquisition.')
        return result
    return router
