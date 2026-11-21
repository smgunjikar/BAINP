"""Transactional safety passports in the host workspace SQLite database.

No global participant DB, HTTP endpoints, credentials or automatic role grants.
Host supplies authenticated identity, ownership checks and authoritative context.
Callbacks must never perform network or irreversible external operations.
"""
import json
from contextlib import contextmanager
from datetime import datetime, timezone
try:
    from .safety_v2 import canonical, digest, evaluate, verify_execution, VERSION
except ImportError:
    from safety_v2 import canonical, digest, evaluate, verify_execution, VERSION

class GuardError(RuntimeError): pass
class AccessDenied(GuardError): pass
class Conflict(GuardError): pass

class GuardStore:
    def __init__(self, connect, authorize, load_context):
        self.connect, self.authorize, self.load_context = connect, authorize, load_context

    @contextmanager
    def transaction(self):
        con = self.connect()
        try:
            if con.in_transaction: raise GuardError('A fresh host connection is required')
            con.execute('BEGIN IMMEDIATE')
            con.execute('CREATE TABLE IF NOT EXISTS ng_v2_decisions(id TEXT PRIMARY KEY, workspace TEXT NOT NULL, participant TEXT NOT NULL, actor TEXT NOT NULL, request_key TEXT NOT NULL, context_hash TEXT NOT NULL, context TEXT NOT NULL, passport TEXT NOT NULL, UNIQUE(workspace,actor,request_key))')
            con.execute('CREATE TABLE IF NOT EXISTS ng_v2_executions(workspace TEXT NOT NULL, actor TEXT NOT NULL, request_key TEXT NOT NULL, decision_id TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(workspace,actor,request_key), UNIQUE(workspace,actor,decision_id))')
            con.execute('CREATE TABLE IF NOT EXISTS ng_v2_events(seq INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, participant TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)')
            for table in ('ng_v2_decisions', 'ng_v2_executions', 'ng_v2_events'):
                for operation in ('UPDATE', 'DELETE'):
                    con.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'NeuroGuard records are append-only'); END")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally: con.close()

    def check(self, con, actor, workspace, participant, operation):
        if not all(isinstance(x,str) and 0<len(x)<=200 for x in (actor,workspace,participant)): raise AccessDenied('Authenticated scope required')
        # Callback must check server session, role, workspace and participant ownership.
        if self.authorize(con, actor, workspace, participant, operation) is not True:
            raise AccessDenied('Participant access denied')

    def context(self, con, actor, workspace, participant, action):
        c = self.load_context(con, actor, workspace, participant, action)
        if not isinstance(c,dict) or any(c.get(k)!=v for k,v in dict(actor_id=actor,workspace_id=workspace,participant_id=participant,action=action).items()):
            raise AccessDenied('Server context scope mismatch')
        if c.get('authorized') is not True: raise AccessDenied('Server authorization unavailable')
        return c

    @staticmethod
    def key(value):
        if not isinstance(value,str) or not 1<=len(value)<=200: raise ValueError('Idempotency key required (1..200 characters)')

    @staticmethod
    def event(con, actor, workspace, participant, payload):
        prior=con.execute('SELECT event_hash FROM ng_v2_events WHERE workspace=? ORDER BY seq DESC LIMIT 1',(workspace,)).fetchone()
        previous=prior[0] if prior else '0'*64
        event=dict(actor=actor,workspace=workspace,participant=participant,payload=payload)
        con.execute('INSERT INTO ng_v2_events(workspace,participant,actor,payload,previous_hash,event_hash) VALUES(?,?,?,?,?,?)',
                    (workspace,participant,actor,canonical(payload),previous,digest(dict(previous=previous,event=event))))

    def decide(self, actor, workspace, participant, action, request_key, *, now=None):
        self.key(request_key)
        with self.transaction() as con:
            self.check(con,actor,workspace,participant,'evaluate')
            c=self.context(con,actor,workspace,participant,action)
            h=digest(c)
            row=con.execute('SELECT context_hash,passport FROM ng_v2_decisions WHERE workspace=? AND actor=? AND request_key=?',(workspace,actor,request_key)).fetchone()
            if row:
                if row[0]!=h: raise Conflict('Idempotency key already used with different inputs')
                return json.loads(row[1])  # Immutable historical decision; execution still rechecks.
            d=evaluate(c,now=now)
            con.execute('INSERT INTO ng_v2_decisions VALUES(?,?,?,?,?,?,?,?)',(d['decision_id'],workspace,participant,actor,request_key,h,canonical(c),canonical(d)))
            self.event(con,actor,workspace,participant,dict(kind='decision',decision=d,context_sha256=h))
            return d

    def read(self, actor, workspace, participant, decision_id):
        with self.transaction() as con:
            self.check(con,actor,workspace,participant,'read_safety')
            row=con.execute('SELECT passport FROM ng_v2_decisions WHERE id=? AND workspace=? AND participant=?',(decision_id,workspace,participant)).fetchone()
            if not row: raise AccessDenied('Decision unavailable in this scope')
            self.event(con,actor,workspace,participant,dict(kind='read',decision_id=decision_id,at=datetime.now(timezone.utc).isoformat()))
            return json.loads(row[0])

    def execute(self, actor, workspace, participant, decision_id, request_key, operation, *, now=None):
        """Operation(con, passport) writes LOCAL action/outbox in the SAME transaction.

Return JSON-serializable data. On callback failure, every write rolls back.
Only the authenticated host chooses operation; never accept executable user input.
"""
        self.key(request_key)
        with self.transaction() as con:
            self.check(con,actor,workspace,participant,'execute')
            row=con.execute('SELECT passport FROM ng_v2_decisions WHERE id=? AND workspace=? AND participant=? AND actor=?',(decision_id,workspace,participant,actor)).fetchone()
            if not row: raise AccessDenied('Decision unavailable in this scope')
            old=json.loads(row[0])
            prior=con.execute('SELECT decision_id,result FROM ng_v2_executions WHERE workspace=? AND actor=? AND (request_key=? OR decision_id=?) ORDER BY CASE WHEN request_key=? THEN 0 ELSE 1 END LIMIT 1',(workspace,actor,request_key,decision_id,request_key)).fetchone()
            if prior:
                if prior[0]!=decision_id: raise Conflict('Execution key already used for another decision')
                return dict(replayed=True, result=json.loads(prior[1]), executed=False)
            c=self.context(con,actor,workspace,participant,old['action'])
            check=verify_execution(old,c,now=now)
            self.event(con,actor,workspace,participant,dict(kind='execution_check',original_decision_id=decision_id,decision=check))
            if check['status']!='PERMIT': return dict(executed=False,replayed=False,decision=check)
            result=operation(con,check)
            encoded=canonical(result)
            con.execute('INSERT INTO ng_v2_executions VALUES(?,?,?,?,?)',(workspace,actor,request_key,decision_id,encoded))
            self.event(con,actor,workspace,participant,dict(kind='executed',decision_id=decision_id,result_sha256=digest(result)))
            return dict(executed=True,replayed=False,result=result)


def verify_audit_chain(con, workspace):
    """Offline integrity check; not protection against a DB administrator rewriting history."""
    previous='0'*64
    for row in con.execute('SELECT workspace,participant,actor,payload,previous_hash,event_hash FROM ng_v2_events WHERE workspace=? ORDER BY seq',(workspace,)):
        w,p,a,raw,prior,current=row
        if prior!=previous or current!=digest(dict(previous=previous,event=dict(workspace=w,participant=p,actor=a,payload=json.loads(raw)))): return False
        previous=current
    return True
