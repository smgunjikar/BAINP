"""Separate local, append-only audit and research-release ledger.

Not a substitute for authenticated reviewer identity or a controlled clinical QMS.
"""
from __future__ import annotations
import sqlite3, json, hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .common import Blocked, canon, checksum, digest_json, identifier, require

DDL = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS packages (
  package_id TEXT PRIMARY KEY, cohort TEXT NOT NULL, subject TEXT NOT NULL,
  visit TEXT NOT NULL, package_sha256 TEXT NOT NULL, source_sha256 TEXT NOT NULL,
  labels_sha256 TEXT NOT NULL, submitter TEXT NOT NULL, qc_status TEXT NOT NULL,
  evidence TEXT NOT NULL, evidence_sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
  event_id TEXT PRIMARY KEY, package_id TEXT NOT NULL REFERENCES packages(package_id),
  reviewer TEXT NOT NULL, reviewer_affiliation TEXT NOT NULL, decision TEXT NOT NULL,
  note TEXT NOT NULL, previous_sha256 TEXT NOT NULL, event_sha256 TEXT NOT NULL,
  recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_decisions_package ON decisions(package_id, recorded_at);
'''

class Ledger:
    def __init__(self, location):
        self.location=Path(location)
        self.location.parent.mkdir(parents=True,exist_ok=True)
        with self._db() as db:db.executescript(DDL)
    @contextmanager
    def _db(self):
        db=sqlite3.connect(str(self.location),timeout=20,isolation_level=None)
        try:
            db.row_factory=sqlite3.Row
            db.execute('PRAGMA busy_timeout=20000')
            db.execute('PRAGMA foreign_keys=ON')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
    def register(self,evidence:dict,submitter:str):
        require(evidence.get('schema')=='BAINP_PHASE2C_QC_EVIDENCE_V1','PHASE2C_EVIDENCE_REQUIRED')
        require(evidence.get('package_integrity')=='SHA256_VERIFIED','PACKAGE_NOT_VERIFIED')
        require(evidence.get('retained_input',{}).get('state')=='SOURCE_SHA256_VERIFIED','RETAINED_MRI_NOT_VERIFIED')
        labels=evidence['retained_input'].get('labels',{}).get('state')
        require(labels in ('UPLOADED_AND_PACKAGED_LABEL_SHA256_VERIFIED','ORIGINAL_AND_RESAMPLED_LABEL_SHA256_VERIFIED'), 'RETAINED_LABELS_NOT_VERIFIED')
        require(evidence.get('atlas_measurements',{}).get('state')=='ARITHMETIC_CONSISTENT_NOT_ANATOMICAL_QC','MEASUREMENT_ARITHMETIC_NOT_VERIFIED')
        require(evidence.get('review',{}).get('status') not in ('REJECTED',), 'REJECTED_PACKAGE')
        package_id=identifier(evidence['scan_id'],'scan_id')
        for k in ('research_cohort','research_subject','research_visit'):
            identifier(evidence[k],k)
        for key in ('package_sha256','source_image_sha256','atlas_label_sha256'):
            checksum(evidence[key])
        submitter=identifier(submitter,'submitter')
        row=(package_id,evidence['research_cohort'],evidence['research_subject'],
             evidence['research_visit'],evidence['package_sha256'],evidence['source_image_sha256'],
             evidence['atlas_label_sha256'],submitter,evidence['review']['status'],
             canon(evidence),digest_json(evidence),datetime.now(timezone.utc).isoformat())
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT evidence_sha256 FROM packages WHERE package_id=?',(package_id,)).fetchone()
            if old:
                require(old['evidence_sha256']==row[-2], 'PACKAGE_ID_CONFLICT_OR_EVIDENCE_CHANGED')
                db.commit()
                return {'registered':True,'unchanged':True,'package_id':package_id}
            db.execute('INSERT INTO packages VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',row)
            db.commit()
        return {'registered':True,'unchanged':False,'package_id':package_id}
    def status(self,package_id):
        with self._db() as db:
            row=db.execute('SELECT * FROM packages WHERE package_id=?',(package_id,)).fetchone()
            require(row is not None,'UNKNOWN_PACKAGE')
            events=[dict(x) for x in db.execute('SELECT * FROM decisions WHERE package_id=? ORDER BY rowid',(package_id,))]
        self._verify_chain(events)
        state='RESEARCH_REVIEW_REQUESTED' if row['qc_status']=='NEEDS_REVIEW' else 'ANATOMICAL_REVIEW_REQUIRED'
        if events:
            v=events[-1]['decision']
            state={'accepted':'RESEARCH_REVIEWED_NOT_CLINICALLY_APPROVED','rejected':'REJECTED','needs_review':'NEEDS_REVIEW'}[v]
        return {'package_id':package_id,'state':state,'source_sha256':row['source_sha256'],
                'labels_sha256':row['labels_sha256'],'research_subject':row['subject'],
                'research_cohort':row['cohort'],'review_count':len(events),
                'independent_anatomical_review_documented':bool(events and events[-1]['decision']=='accepted'),
                'independent_reviewer_identity_authenticated':False,
                'clinical_approval':False}
    @staticmethod
    def _verify_chain(events):
        prev='0'*64
        for e in events:
            payload={k:e[k] for k in ('event_id','package_id','reviewer','reviewer_affiliation','decision','note','recorded_at')}
            require(e['previous_sha256']==prev and e['event_sha256']==digest_json({'prev':prev,'event':payload}),
                    'REVIEW_AUDIT_INTEGRITY_FAILURE')
            prev=e['event_sha256']
    def review(self,package_id,reviewer,affiliation,decision,note):
        reviewer=identifier(reviewer,'reviewer')
        require(decision in ('accepted','rejected','needs_review'),'REVIEW_DECISION_INVALID')
        require(isinstance(note,str) and 30 <= len(note.strip()) <= 2000,'REVIEW_NOTE_REQUIRED')
        require(isinstance(affiliation,str) and 3 <= len(affiliation.strip()) <= 160,'REVIEWER_AFFILIATION_REQUIRED')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            pack=db.execute('SELECT submitter,qc_status FROM packages WHERE package_id=?',(package_id,)).fetchone()
            require(pack is not None,'UNKNOWN_PACKAGE')
            require(reviewer != pack['submitter'],'SELF_REVIEW_FORBIDDEN')
            events=[dict(e) for e in db.execute('SELECT * FROM decisions WHERE package_id=? ORDER BY rowid',(package_id,))]
            self._verify_chain(events)
            if events and events[-1]['decision']=='rejected':raise Blocked('REJECTED_REQUIRES_NEW_VERSION')
            prev=events[-1]['event_sha256'] if events else '0'*64
            import uuid
            event={'event_id':str(uuid.uuid4()),'package_id':package_id,'reviewer':reviewer,
                   'reviewer_affiliation':affiliation,'decision':decision,'note':note.strip(),
                   'recorded_at':datetime.now(timezone.utc).isoformat()}
            h=digest_json({'prev':prev,'event':event})
            db.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?,?)',
                (event['event_id'],package_id,reviewer,affiliation,decision,event['note'],prev,h,event['recorded_at']))
            db.commit()
        return self.status(package_id)
