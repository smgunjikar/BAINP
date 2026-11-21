"""Authenticated BBC-BE storage, consent, immutable revisions and local review queue."""
import json,sqlite3
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import AwareDatetime
from bb_models import Record,Consent,Review
from bb_provider import SCHEMA,consent_at,read_context
from bb_engine import canonical,digest,stamp
from bb_identity import conflicting_owner
from bb_dictionary import VERSION,METRICS,REPORTS,SYSTEMS
from bb_connections import source_inventory
Mode=Literal['active','demo']
def now():return datetime.now(timezone.utc).isoformat()
def make_router(store,authenticated,cognitive_analytics=None):
    with store.connect(True) as c:
        c.executescript(SCHEMA)
        # Additive migration for an earlier local development build, never a data reset.
        if 'scope' not in {row['name'] for row in c.execute('PRAGMA table_info(bb_records)')}:
            c.execute('ALTER TABLE bb_records ADD COLUMN scope TEXT')
            from bb_engine import scope
            for old in c.execute('SELECT r.id,v.payload FROM bb_records r JOIN bb_versions v ON v.record_id=r.id WHERE v.revision=(SELECT MAX(x.revision) FROM bb_versions x WHERE x.record_id=r.id)'):
                c.execute('UPDATE bb_records SET scope=? WHERE id=?',(scope(json.loads(old['payload'])),old['id']))
    r=APIRouter(prefix='/api/brainbody',dependencies=[Depends(authenticated)])
    def person(c,pid,mode):
        if not c.execute('SELECT id FROM participants WHERE id=? AND mode=?',(str(pid),mode)).fetchone():raise HTTPException(404,'participant_not_found')
    def audit(c,action,pid,mode):c.execute('INSERT INTO audit_events(action,entity_id,mode,recorded_at) VALUES(?,?,?,?)',(action,str(pid),mode,now()))
    @r.get('/dictionary')
    def dictionary():return dict(version=VERSION,metrics=METRICS,reports=REPORTS,systems=SYSTEMS,scopes=['context','clinical_biomarkers','family_history','genomic_summary','molecular_research'])
    @r.get('/demo')
    def demo(profile:Literal['control','impairment']='control',include_sensitive:bool=False):
        from bb_demo import demo_snapshot
        return with_connections(demo_snapshot(profile,include_sensitive))

    def with_connections(result):
        result['connections'] = source_inventory(store, result)
        result['revision'] = digest({key: value for key, value in result.items() if key != 'revision'})
        return result
    @r.get('/participants/{pid}/consent')
    def get_consent(pid:UUID,mode:Mode):
        with store.connect() as c:person(c,pid,mode);return consent_at(c,pid,mode)
    @r.put('/participants/{pid}/consent')
    def put_consent(pid:UUID,mode:Mode,payload:Consent):
        with store.connect(True) as c:
            person(c,pid,mode);current=consent_at(c,pid,mode)
            if current['revision']!=payload.expected_revision:raise HTTPException(409,'consent_revision_changed_reload')
            revision=current['revision']+1
            c.execute('INSERT INTO bb_consents VALUES(?,?,?,?,?,?)',(str(pid),mode,revision,canonical(sorted(payload.scopes)),payload.authorization_reference,now()))
            audit(c,'bbc_consent_updated',pid,mode)
            return consent_at(c,pid,mode)
    @r.put('/participants/{pid}/records/{rid}')
    def put_record(pid:UUID,rid:UUID,mode:Mode,payload:Record):
        data=payload.model_dump(mode='json',exclude_none=True);raw=canonical(data);source=data['source']
        key=digest([source['kind'],source['organization'],source['record_reference'],data['kind'],data.get('metric')])
        with store.connect(True) as c:
            person(c,pid,mode);consent=consent_at(c,pid,mode)
            if payload.scope() not in consent['scopes']:raise HTTPException(403,'separate_scope_authorization_required')
            if source.get('cohort'):
                if conflicting_owner(c,pid,mode,source['cohort'],source['source_subject']):raise HTTPException(409,'source_identity_conflicts_with_existing_twin_link')
                link=c.execute('SELECT participant_id FROM bb_identity_links WHERE mode=? AND cohort=? AND source_subject=?',(mode,source['cohort'],source['source_subject'])).fetchone()
                if link and link['participant_id']!=str(pid):raise HTTPException(409,'research_identity_already_linked_to_another_person')
            old=c.execute('SELECT * FROM bb_records WHERE id=?',(str(rid),)).fetchone()
            if old:
                if old['participant_id']!=str(pid) or old['mode']!=mode:raise HTTPException(409,'record_identity_conflict')
                version=c.execute('SELECT * FROM bb_versions WHERE record_id=? ORDER BY revision DESC LIMIT 1',(str(rid),)).fetchone()
                if version['payload']==raw:return dict(stored=True,unchanged=True,revision=version['revision'])
                prior=json.loads(version['payload'])
                if old['source_key']!=key or prior['source'].get('cohort')!=source.get('cohort') or prior['source'].get('source_subject')!=source.get('source_subject'):raise HTTPException(409,'immutable_record_source_or_kind_changed')
                if payload.revision!=version['revision']+1:raise HTTPException(409,'record_revision_conflict')
                if stamp(data['available_at'])<stamp(prior['available_at']):raise HTTPException(409,'correction_availability_cannot_move_backwards')
            else:
                if payload.revision!=1:raise HTTPException(409,'first_revision_must_be_one')
                duplicate=c.execute('SELECT id FROM bb_records WHERE participant_id=? AND mode=? AND source_key=?',(str(pid),mode,key)).fetchone()
                if duplicate:raise HTTPException(409,'source_record_already_exists_use_original_id')
                c.execute('INSERT INTO bb_records(id,participant_id,mode,source_key,scope) VALUES(?,?,?,?,?)',(str(rid),str(pid),mode,key,payload.scope()))
            if source.get('cohort'):c.execute('INSERT OR IGNORE INTO bb_identity_links VALUES(?,?,?,?)',(str(pid),mode,source['cohort'],source['source_subject']))
            c.execute('INSERT INTO bb_versions VALUES(?,?,?,?,?)',(str(rid),payload.revision,raw,now(),digest(data)))
            audit(c,'bbc_record_updated',pid,mode)
        return dict(stored=True,revision=payload.revision,id=str(rid))
    @r.get('/participants/{pid}/records/{rid}/revisions')
    def revisions(pid:UUID,rid:UUID,mode:Mode,include_sensitive:bool=False):
        with store.connect() as c:
            person(c,pid,mode);record=c.execute('SELECT * FROM bb_records WHERE id=? AND participant_id=? AND mode=?',(str(rid),str(pid),mode)).fetchone()
            if not record:raise HTTPException(404,'record_not_found')
            scopes=consent_at(c,pid,mode)['scopes'];result=[]
            if record['scope'] not in scopes or record['scope']=='genomic_summary' and not include_sensitive:raise HTTPException(403,'record_scope_or_disclosure_not_authorized')
            from bb_engine import scope
            for row in c.execute('SELECT * FROM bb_versions WHERE record_id=? ORDER BY revision',(str(rid),)):
                data=json.loads(row['payload']);needed=scope(data)
                if needed not in scopes or (needed=='genomic_summary' and not include_sensitive):raise HTTPException(403,'record_scope_or_disclosure_not_authorized')
                result.append(dict(revision=row['revision'],known_at=row['known_at'],sha256=row['sha256'],payload=data))
            return {'items':result}
    @r.delete('/participants/{pid}/records/{rid}')
    def delete_record(pid:UUID,rid:UUID,mode:Mode,expected_revision:int=Query(ge=1)):
        with store.connect(True) as c:
            person(c,pid,mode);row=c.execute('SELECT r.id,MAX(v.revision) AS revision FROM bb_records r JOIN bb_versions v ON v.record_id=r.id WHERE r.id=? AND r.participant_id=? AND r.mode=? GROUP BY r.id',(str(rid),str(pid),mode)).fetchone()
            if not row:raise HTTPException(404,'record_not_found')
            if row['revision']!=expected_revision:raise HTTPException(409,'record_revision_changed_reload')
            c.execute('DELETE FROM bb_records WHERE id=?',(str(rid),));audit(c,'bbc_record_deleted',pid,mode)
        return {'deleted':True,'all_record_revisions_deleted':True}
    @r.put('/participants/{pid}/reviews/{rid}')
    def review(pid:UUID,rid:UUID,mode:Mode,payload:Review):
        try:snapshot=read_context(store,pid,mode,include_sensitive=payload.include_sensitive,cognition_analytics=cognitive_analytics)
        except LookupError:raise HTTPException(404,'participant_not_found')
        finding=next((x for x in snapshot['review_queue'] if x['record_id']==str(rid) and x['revision']==payload.record_revision and x['code']==payload.finding_code),None)
        if finding is None:raise HTTPException(409,'current_finding_not_found_reload')
        with store.connect(True) as c:
            person(c,pid,mode)
            current=c.execute('SELECT MAX(revision) AS revision FROM bb_versions WHERE record_id=?',(str(rid),)).fetchone()
            if current['revision']!=payload.record_revision:raise HTTPException(409,'record_revision_changed_reload')
            c.execute('INSERT INTO bb_reviews VALUES(?,?,?,?,?,?) ON CONFLICT(record_id,revision,finding_code) DO UPDATE SET status=excluded.status,note=excluded.note,known_at=excluded.known_at',(str(rid),payload.record_revision,payload.finding_code,payload.status,payload.note,now()))
            audit(c,'bbc_review_updated',pid,mode)
        return {'recorded':True,'note':'Review status does not change source measurements or certify clinical validity.'}
    @r.get('/participants/{pid}')
    def snapshot(pid:UUID,mode:Mode,as_of:AwareDatetime|None=None,include_sensitive:bool=False):
        if as_of and as_of>datetime.now(timezone.utc):raise HTTPException(422,'future_cutoff_not_supported')
        try:result=read_context(store,pid,mode,as_of,include_sensitive,cognition_analytics=cognitive_analytics)
        except LookupError:raise HTTPException(404,'participant_not_found')
        with_connections(result)
        result['checked_at']=now();return result
    return r
