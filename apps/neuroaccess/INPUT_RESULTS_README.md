# Input recording and readable results — v1.3

## What was wrong

The previous general summary table requested a generic `correct` field for all
tasks. C09/C10 used dictionary-match/review counts instead, so the table displayed
a dash. This did not by itself prove a storage failure. The previous recorder did,
however, discard unsubmitted text at a timeout. Some visual stimulus cards were
not clickable even though users could reasonably try to choose them. C08 button
activation also did not reliably distinguish keyboard from pointer input.

## What this update changes

- C03's large stimulus and C04/C08's answer cards accept responses directly.
- Pointer choices are captured on pointer-down. The following click is suppressed;
  first-valid-response rules stay explicit. Key repeats and additional/late input
  attempts can be inspected without inflating scored responses.
- Text inputs preserve the entered draft as well as the submitted answer. Explicit
  Submit/Enter is supported. Composition-aware handling avoids submitting an IME
  candidate while it is still composing.
- At a text deadline, nonblank, non-composing text entered before the deadline is
  committed with `deadline_commit` and a quality note. Its RT is the deadline;
  edit events show when text changed. Late edits do not become valid responses.
- An interruption preserves an unsubmitted draft without converting it into an
  answer. C07 response buttons remain unavailable during presentation; selected
  cell numbers are shown during recall. C11 continues to record each tap.
- Completed trials are checkpointed to the local server. Typed drafts are debounced
  at 500 ms. Checkpoints are revisioned; stale writes cannot overwrite newer ones.
  They are separate from final, immutable results. On reload, recovery can mark an
  interrupted task using its saved prefix and typed draft, without replaying it.
- Final results still require server validation and read-back. Checkpoint requests
  are asynchronous; they do not pause the task. Their overhead must be included in
  real-device timing evaluation. No calibrated display/input timing is claimed.

Checkpoints are not a guarantee against all loss: the latest edits can precede the
next checkpoint, offline saves can fail, and closing a browser can abandon pending
requests. Keep the page open until final saving succeeds. Existing text discarded
by an older recorder cannot be reconstructed. C06 reports are stored when their
complete consented submission is saved; they are not continuously checkpointed.

## Readable reports

Open the EXISTING saved study. You do not need to repeat it to inspect its answers.
Each task now has **Recorded responses and timing** containing presented items,
expected responses where applicable, the participant's recorded answer, outcome,
rounded display timing, input method and submission mode. Raw numeric precision
remains in the technical JSON export. Default reports do not show JSON blocks.

C09/C10 show accepted dictionary/operator answers, reviewed/different-listed-item
answers, pending review, missing submitted answers and preserved drafts. Unknown
spellings are not automatically called wrong. A different listed object's name
may be identified as a mismatch, with human override available. The dictionary is
limited and unvalidated; no linguistic disease score is generated.

For saved C09/C10 answers, expand **Operator answer review** and choose Accepted,
Incorrect or Uncertain. This adds an immutable, revisioned judgement with optional
note. A subsequent review appends a new revision. Raw responses and their original
automatic summary are NOT edited. The review is a local operator attestation, not
verified clinician assessment or a CareLoop clinical decision. Unsubmitted drafts
cannot be rated as submitted answers.

Other tasks use appropriate observations: correct sequences for C07, rotation
choices for C08, report items for C06/C12, and per-hand tap windows for C11. Reaction
times display at one decimal place. Saved-record details show protocol, form,
timestamps, preparation and checkpoint information in a readable layout. Expanded
input audits list accepted, ignored, timeout, edit-length and submission events.
They do not record login keystrokes or globally log keyboard content. JSON export
remains an explicitly technical option for research and debugging.

## Persistence and compatibility

SQLite schema v5 adds `nc_input_checkpoints` and `nc_response_reviews`, both deleted
with their parent attempt/participant. No working records are reset. Old saved
answers can immediately use the readable report. Old protocol definitions and
submitted data remain frozen. New sessions use `ncx-research-v1.3.0`; pending tasks
from older sessions can use the new recorder with its implementation version in
preparation metadata. Already-running tasks should be finished/saved before an
upgrade; they cannot be silently replayed afterward.

Active and Demo boundaries, authentication, NeuroAccess readiness, optional task
practice, fixed task parameters and held-session behavior remain enforced. No
self-changing scoring, diagnostic inference or clinical-validity claim is added.

## Verification and Git

`Start-NeuroAccess.ps1 -Service VerifyCognition` runs `tests/verify_inputs.py` with
isolated fictional data. It includes exact typed-answer storage, three-match /
three-reviewed-incorrect fixtures, checkpoint persistence after restart, stale
revision protection, review immutability, draft recovery, mode isolation, deletion
and the inherited NeuroAccess/all-task/randomization regression checks.

Development additionally uses simulated DOM/RAF tests for direct/failed-practice
starts, all tasks, touch double-count prevention, typing/deadline commits, IME
composition, readable/escaped reports and Arabic dashboard. Those do not establish
real-browser hardware timing, clinical reliability or usability in the intended
population. Windows launcher execution still requires local acceptance.

Keep new source (`backend/input_records.py`, `web/results.js`), updated source,
tests and documentation in Git. Exclude working DB/WAL/SHM, secrets, process files,
logs, entered-data exports, checkpoint data, reviews, archives/source backups and
raw research datasets. Source backups contain code, not a copy of the participant
DB. Exported files and OS/OneDrive backups require separate deletion/management.
