# NeuroQuest V2 — folder-only upgrade

16 November 2026. Installs only inside `BAINP/apps/neuroquest` against the uploaded neuroquest.zip. Existing BAINP NeuroAccess/NeuroContinuum/NeuroGuard bridges and account-enabled host are required. Python 3.10+; use the existing bainp environment and dependencies. No new package dependencies, accounts, public ports or separate databases are added.

## Changes from v1.2.0

| Uploaded behavior | V2 behavior |
|---|---|
| Latest saved recommendation presented as current | Server compares fresh context and expiry; UI labels historical decisions and hides continuation links |
| Idempotent retry checks only consent revision | Rejects superseded, expired and context-changed recommendations with HTTP 409 |
| No expiry | Five-minute operational decision lifetime; expiry removes UI continuation affordance |
| Editing warning/concern fields leaves old action visible | Form changes immediately replace old recommendation; selected warning shows immediate guidance text |
| Generic quality-correction explanation | Source IDs, task IDs and supplied QC flags are visible and exported |
| History ordering relied on caller | Explicit latest-first sorting; outdated-protocol quarantines do not automatically force current-protocol repeats |
| Anything except QUARANTINED could count as clear | Only recognized clear states count; unknown quality causes abstention |
| Complete session grouped only by session ID | Form is also kept separate; different forms are not combined to claim completion |
| Implicit memory order | Rejects a core registry placing C02 before C01 or omitting C01 |
| Workflow state alone accepted | Explicit Guard action scope respected when supplied |
| No participant pause input | Pause returns a non-executable monitoring recommendation |
| Scattered decision metadata | Structured Decision Passport with revisions, policy, source IDs, hashes and expiry |
| Dark green research page | Cream/peach/charcoal styling aligned with the main BAINP direction |
| Test login used old operator API | Integration tests use an isolated administrator account and explicitly selected legacy synthetic workspace |

Saved historical evidence is retained unchanged. Existing records lacking V2 freshness fields are historical and require re-evaluation. The existing schema is reused; no database migration is performed by the installer.

## What becomes visible

Open the existing `/neuroquest` page with the participant and mode query parameters preserved, then Ctrl+F5. You should see updated styling, a pause checkbox, current/historical status, expiry and expanded quality details. NeuroContinuum calls the updated selector through its existing bridge, but its own page layout is not changed by this folder-only installer.

A recommendation is a proposal, not an execution permit. NeuroContinuum still recomputes its decision at the workflow step. This update uses the existing independent NeuroGuard bridge and does not claim to integrate every route with the new NeuroGuard V2 GuardStore API.

## Why some recommendations remain non-executable

The uploaded registry explicitly reports `single_task_execution=False`. Targeted tasks and isolated quality repeats remain non-executable. This update does not fabricate a launch URL or automatically substitute a full battery for a targeted repeat. Correcting an earlier technical issue alone cannot create a missing task-execution capability.

A vision condition with usual correction and confirmed ability to see/respond is not by itself an exclusion under the current selector. Unsupported administration conditions still require review. Interface translation is not clinical validation of a task language; adding Hindi to the main profile does not establish a validated Hindi cognitive battery.

## Scope of the requested roadmap

| Requested capability | Delivery / remaining work |
|---|---|
| Current recommendation, lifecycle, history, explanation | Implemented within NeuroQuest |
| Urgent precedence and functional review | Existing behavior retained; stale retries blocked and frontend invalidated on input changes |
| Decision Passport | Implemented in existing stored decision payload and JSON export; NeuroProof display integration remains external |
| Task registry | Reads actual battery version/order; lists dependencies and unavailable pathways; no invented executables |
| Quality correction | Detailed source flags and conservative non-executable recovery; isolated task execution requires NeuroCognition changes |
| Core selection / cooldown | Existing native Core battery and explicitly engineering-only 24-hour cooldown retained |
| Burden management | Explicit participant pause added; no unsupported duration or information-gain claims |
| Micro / Extended adaptive sequencing | Not activated: reviewed executable pathway definitions and validated stopping rules are not supplied |
| Alternate-form / practice-effect correction | Form mixing prevented; equivalence and correction models remain unvalidated |
| Clinical references, diagnoses, predictions | Not implemented or inferred from digital scores |
| Clinical override and outcome dashboard | Not implemented; requires authenticated clinical roles, governance and outcome definitions |
| NeuroSense / Shadow / MRI / EEG adaptive influence | No new clinical selection influence; requires evidence, consent and validated use cases |
| Automatic learning / advanced adaptive policies | Not deployed; requires offline evaluation and prospective governance |
| Full cross-engine execution protection | Requires endpoint integration and independent end-to-end verification beyond this folder |

## Verification

- 22 standalone synthetic policy/lifecycle tests passed.
- 29 tests passed in the local account-enabled integration host: 13 original pure tests and 16 HTTP integration tests. These include stale retry rejection, currentness, permission withdrawal, mode isolation, urgent workflow blocking, idempotency and CareLoop local-case workflow.
- Python compilation and JavaScript syntax checks passed.
- Installer dry-run, installation, repeated installation, exact source rollback and rejection of a newer local edit were verified.
- No Windows browser visual acceptance or clinical validation is claimed. The user's live installed host can contain differences from the available integration fixture.

Standalone test: `python apps/neuroquest/tests/test_v2.py`
Integration test, with the account-enabled host and existing NeuroContinuum test helpers present: `python apps/neuroquest/tests/verify.py`. It creates only temporary fictional data. Do not point test fixtures at a real participant database.

## Install and rollback

Use `Install-NeuroQuest.py --project-root PATH --check`, run standalone tests, stop BAINP, install, then restart. The installer checks uploaded source hashes and refuses to overwrite unknown local edits. It prints a source backup path within `apps/neuroquest/.continuity-backups`.

To restore: stop BAINP, run the installer with `--project-root PATH --restore BACKUP_PATH --check`, repeat without `--check`, then restart. Source rollback does not delete saved decisions or other user data. Newer edits cause restore to refuse overwrite.
