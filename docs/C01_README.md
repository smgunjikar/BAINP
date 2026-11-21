# C01 encoding demo v1

What it does:
- Reads C00 intake and checks the gate again inside the start transaction.
- Presents eight fixed English words for at least 3000 browser-measured ms each.
- Saves one exposure attempt per assessment with an immutable intake snapshot.
- Stores sequence IDs, onset offsets and durations, completion/interruption reason,
  server start/finish timestamps, and protocol version.
- Verifies read-back; failed saves retry the same attempt and result.
- Prevents automatic replay after refresh. Mark abandoned running attempts interrupted.

What it does not do:
- It does not score memory, test recognition, administer an immediate orientation
  check, or finish the full assessment battery. No clinical interpretation exists.
- Browser timing and focus signals are client-reported; they do not prove actual
  display exposure, attention, literacy, device calibration or tamper resistance.
- The fixed word list is a demonstration list, not a validated cultural adaptation.
- No Arabic, assisted or touch task support is enabled by this implementation.
- Completing C01 does not make a longitudinal score available.

Files and responsibilities:
- app/c01.py: task definition, validation, gate enforcement, start/result/read routes.
- migration 0009: c01_attempts storage, one attempt per assessment.
- web/src/app/encoding/page.tsx: timed presentation and interruption/save workflow.
- tests/verify_c01.py: gate, retry, sequence, interruption and storage checks.

Start uses C00 as the source of conditions, not legacy separate practice conditions.
It updates assessment status to in_progress without claiming completion.
C01 cannot be repeated in a session. A new assessment is required for another run.
A refresh before an unsaved result is persisted loses its client log; the prior
attempt can only be recorded as interrupted, not resumed or reconstructed.

Future work:
C03 attention -> C04 switching -> C05 symbol matching -> C02 recognition -> C06
function report. Actual delay must be measured; these tasks do not yet exist as a
connected core battery. C02 must require completed C01 and use this stimulus version.

Git targets: app/c01.py, migration 0009, tests/verify_c01.py, main.py registration,
web/src/app/encoding/page.tsx, the C00 link, and this README. Do not commit backups.
Verification creates synthetic test records and waits about 24 seconds for completion.
