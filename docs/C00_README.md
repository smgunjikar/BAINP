# C00 pre-flight v1: what this code does

Purpose: save fictional session conditions and compute a deterministic gate before
future core assessment tasks. It does not implement C01, clinical triage, referrals,
Arabic task translation, calibrated latency checks, or an emergency service.

Files:
- app/c00_rules.py: strict intake contract and pure rule evaluation.
- app/c00.py: immutable PUT, read-back GET, and GET task-entry verdict.
- migrations/versions/0008_assessment_intakes.py: adds one intake row per assessment.
- web/src/app/intake/page.tsx: collects answers, verifies persistence, displays gate.
- tests/verify_c00.py: pure rules plus database-backed HTTP verification.

Rules (demonstration policy c00-gate-v1):
1. Acute warning YES -> PROFESSIONAL_REVIEW_REQUIRED and no task entry.
2. Unknown acute warning or unresolved instructions/input -> abstain.
3. Arabic, touch, assistance, and unimplemented visual adaptations -> hold.
4. Otherwise -> SUITABLE_FOR_DEMO_TASK_ENTRY, not medical clearance.

The existing separate attention practice is unchanged and does not satisfy C00.
Future C01/task-start endpoints MUST enforce the gate server-side, in the same
transaction as creating a task attempt, and recheck consent/session status.
GET task-entry alone does not provide a durable authorization token.

Persistence: one immutable intake per assessment. Same-payload retry is accepted;
changed answers return 409. New conditions require a new assessment. A failed save
can be retried on the same page. Consent must remain granted. No real health data
should be entered into this unauthenticated local prototype.

Verification: run the PowerShell installer with -Verify after restarting services.
It creates clearly named synthetic test participants/sessions. Check /intake?id=...
manually as well. Record successful output in the implementation tracker.

Git targets: all listed source files, main.py router registration, assessment/page.tsx
intake link, and this README. Exclude patch-backups and local environment files.
