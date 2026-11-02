"""Research/demo FastAPI. All endpoints are intentionally under /v1/demo."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import Base, make_engine, make_session_factory
from .models import Participant, AssessmentSession, TaskTrial, CareReview, AuditEvent
from .schemas import AttentionSubmission, CareUpdate
from .demo_cases import CASES, interpret_case

DEMO_ID = 'demo-001'

def create_app(database_url: str | None = None) -> FastAPI:
    if os.getenv('DEMO_ONLY','true').lower()!='true':
        raise RuntimeError('This starter intentionally supports synthetic demonstration mode only.')
    if database_url is None:
        root = Path(__file__).resolve().parents[3]
        db_file = root / 'data' / 'demo.db'
        db_file.parent.mkdir(parents=True, exist_ok=True)
        database_url=os.getenv('BRAIN_SIGNAL_DB_URL',f'sqlite:///{db_file}')
    engine=make_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal=make_session_factory(engine)
    with SessionLocal() as session:
        if session.get(Participant,DEMO_ID) is None:
            session.add(Participant(id=DEMO_ID,display_name='Fictional participant A',synthetic=True))
        for case in CASES:
            if session.get(CareReview, case['id']) is None:
                session.add(CareReview(case_id=case['id'],status='not_started'))
        session.commit()

    app=FastAPI(title='BAINP — Synthetic Research Demo',version='1.0.0')
    app.add_middleware(CORSMiddleware,allow_origins=os.getenv('FRONTEND_ORIGINS','http://localhost:3000').split(','),allow_methods=['GET','POST','PUT'],allow_headers=['Content-Type'])

    def db():
        with SessionLocal() as session: yield session

    @app.get('/demo', include_in_schema=False)
    def standalone_demo():
        return FileResponse(Path(__file__).resolve().parent / 'static' / 'index.html')

    @app.get('/health')
    def health(): return {'status':'ok','demo_only':True,'clinical_use':False}

    @app.get('/v1/demo/cases')
    def list_cases(session:Session=Depends(db)):
        return [{**case, 'interpretation':interpret_case(case),
                 'care_status':session.get(CareReview,case['id']).status} for case in CASES]

    @app.get('/v1/demo/cases/{case_id}')
    def get_case(case_id:str,session:Session=Depends(db)):
        case=next((c for c in CASES if c['id']==case_id),None)
        if case is None: raise HTTPException(404,'No such synthetic case')
        return {**case,'interpretation':interpret_case(case),'care_status':session.get(CareReview,case_id).status}

    @app.put('/v1/demo/cases/{case_id}/care')
    def update_care(case_id:str, payload: CareUpdate, session:Session=Depends(db)):
        row=session.get(CareReview,case_id)
        if row is None: raise HTTPException(404,'No such synthetic case')
        row.status=payload.status
        row.updated_at=datetime.now(timezone.utc)
        session.add(AuditEvent(event_type='demo_care_updated',object_ref=case_id,metadata_json={'status':payload.status}))
        session.commit()
        return {'case_id':case_id,'status':payload.status,'synthetic':True}

    @app.post('/v1/demo/attention',status_code=201)
    def save_attention(payload: AttentionSubmission,session:Session=Depends(db)):
        # Score a toy target-detection task; no cognitive norms, disease score or risk inference.
        trials=sorted(payload.trials,key=lambda x:x.index)
        scores=[t.pressed==(t.stimulus=='A') for t in trials]
        rts=[t.response_ms for t in trials if t.pressed and t.response_ms is not None]
        quality='descriptive_only' if len(rts)>=2 else 'review_quality'
        identifier=str(uuid4())
        row=AssessmentSession(id=identifier,participant_id=payload.participant_id,
            language=payload.language,device=payload.device,correct=sum(scores),total=8,
            quality_status=quality,mean_response_ms=round(sum(rts)/len(rts),1) if rts else None)
        session.add(row)
        for t,correct in zip(trials,scores):
            session.add(TaskTrial(session_id=identifier,position=t.index,stimulus=t.stimulus,
                                  pressed=t.pressed,response_ms=t.response_ms,correct=correct))
        session.add(AuditEvent(event_type='demo_assessment_saved',object_ref=identifier,metadata_json={'task':'attention-target-v0.1'}))
        session.commit()
        return {'session_id':identifier,'correct':sum(scores),'total':8,'mean_response_ms':row.mean_response_ms,
                'quality_status':quality,'clinical_interpretation':None,'synthetic':True}

    @app.get('/v1/demo/timeline')
    def timeline(session:Session=Depends(db)):
        rows=session.scalars(select(AssessmentSession).where(AssessmentSession.participant_id==DEMO_ID).order_by(AssessmentSession.recorded_at)).all()
        return {'participant_id':DEMO_ID,'synthetic':True,'sessions':[
            {'id':r.id,'recorded_at':r.recorded_at.isoformat(),'task_version':r.task_version,
             'correct':r.correct,'total':r.total,'quality_status':r.quality_status,'mean_response_ms':r.mean_response_ms}
            for r in rows]}
    return app

app=create_app()
