# NeuroContinuum V1 — native BAINP module

This module installs inside the existing BAINP project, served through the existing NeuroAccess API on port 8000 and main-page server on port 3000. It does not require Node.js, a second website or another login.

## Open and use

1. Start BAINP as usual with `apps/neuroaccess/Start-NeuroAccess.ps1 -Service All`.
2. Log in on http://127.0.0.1:3000 . Select the intended Active or Demo participant.
3. Select the new **NeuroContinuum V1** card on the main page.
4. Open **Consent & access**. Record the applicable workflow permissions, including history, assessment and optional local case tracking. These supplement existing storage and source-specific permissions; the operator must establish the authority to record them.
5. Create and complete a NeuroAccess check-in on the main page if none is ready. Its saved profile must still match the participant's current profile.
6. Start or resume a monitoring workflow and choose that check-in. Advance through authorization, source retrieval, workflow safety checks and fixed assessment routing.
7. Open the **existing NeuroCognition X** assessment in its new tab. Device diagnostics, supported tasks, practice, timing, scoring and original quality flags remain inside that module. NeuroContinuum does not manufacture device diagnostics or complete tasks on behalf of the participant.
8. Return to NeuroContinuum and synchronize. Incomplete or interrupted assessments do not become completed measurements. Completed native results go through a final reference-quality gate.
9. Preserve permitted descriptive source references and end the digital session. If explicitly permitted, source-quality concerns create or reuse an actual local CareLoop case. Manage its independent lifecycle in the existing CareLoop page.

The fixed pathway is the initial NeuroQuest policy, not an adaptive or clinically optimized next-task selector. It delegates task availability, order and execution to the existing NeuroCognition module.

## Native integration

| Existing component | Integration |
| --- | --- |
| NeuroAccess | Existing participant/mode identity, profile preferences, storage consent, check-in and access gate |
| NeuroCognition X | Existing router's entry contract, native assessment URL, original saved sessions/attempts/summary flags |
| NeuroTwin X | Participant-scoped stored source references and a descriptive `neurocontinuum` workflow-marker section in native snapshots |
| NeuroGuard | Existing warning-sign guidance and exact-source claim-release checks, plus a separate versioned operational workflow policy in `neuroguard/backend/continuum_policy.py`. None is a clinical task-authorization certificate |
| CareLoop | Existing case intake and state-transition functions within the same SQLite transaction |
| Platform Core | Additive module registry entry |
| NeuroGraph / audit | Source hashes, consent/profile revisions and a per-session local event chain. Existing scientific evidence records are not rewritten |
| Other engines | Existing registered pages appear in the directory; costly processing is never triggered by session initialization |

History retrieval uses the native stored references and the consent-filtered Brain–Body provider when installed. It does **not** call the full predictive Twin snapshot or run a forecast during monitoring initialization. Optional EEG, MRI and wearable records remain distinct source observations; absent modalities are not imputed or paired across unrelated people.

## Workflow and data semantics

Normal path: CREATED → AUTHORIZED → VALIDATING → AWAITING_ACTION → ASSESSING → RECORDING → COMPLETED. Explicit PAUSED, BLOCKED, FAILED and CANCELLED states handle interruptions and restrictions.

Changing workflow scopes blocks open sessions. Resume clears previous routing decisions and revalidates. An expired or changed source profile needs a new check-in; an interrupted native task is never silently restarted or declared complete. Cancel affects the orchestration session, not an already running source assessment; stop that assessment in NeuroCognition if required.

Accepted references are labelled `SOURCE_QC_CLEAR_DESCRIPTIVE_ONLY`, not clinically validated measurements. Original source quality flags remain intact. Flagged attempts are quarantined from accepted reference insertion; the original result stays in NeuroCognition and in the workflow's source evidence. A low/high numerical value alone is not an exclusion policy.

No clinical diagnosis, treatment, disease-prediction model, EEG processing, MRI segmentation or retraining is implemented by this module. Existing research MRI qualifications and eligibility decisions are unchanged. Warning-sign guidance is delegated to the existing NeuroGuard route/function. An urgent path can end a digital session, but it does not contact an emergency service, deliver a referral or automatically create a consented care case. A local CareLoop record is not proof of clinical follow-up.

## Persistence and security

The extension adds `ncw_consents`, `ncw_sessions`, `ncw_events`, `ncw_operations` and `ncw_observation_refs` to the existing BAINP SQLite database. Original tables and database version controls remain intact. Module installation writes source only; its verification uses temporary data directories. Normal application startup applies the additive extension tables.

Requests inherit the existing authenticated operator cookie, same-origin boundary and `X-NeuroAccess-Request` control. Active/demo and participant ownership are checked server-side. A new workflow requires an explicit permission record. Each mutation carries a stable operation UUID; retries reuse it with the identical body. Reused UUIDs with different payloads are rejected. Session versions and `BEGIN IMMEDIATE` serialize conflicting writes. Reference insertion, case creation, event recording and response bookkeeping share a transaction.

The existing participant-deletion operation cascades through extension tables. Consent withdrawal blocks future workflow access and hides retained history/result details in this module; it is not a substitute for the application's explicit deletion process. Access to CareLoop continues to follow that module's own permissions and case lifecycle. The application still uses the existing local operator role; separate authenticated participant and clinician roles are not introduced.

The audit chain detects internal changes relative to its supplied hashes; it is not externally signed or tamper-proof. Production deployment, jurisdiction-specific compliance, independent security/accessibility review, clinical validation, backup recovery and load qualification remain separate work.

## Verification

Run in the existing activated environment:

```powershell
python .\apps\neurocontinuum\tests\verify.py
```

The suite tests real existing API/Guard/CareLoop integration with fictional participants in temporary SQLite databases. Source-completion fixtures arrange native saved task results; they do not validate cognitive scoring, browser timing or human performance. Optional NeuroTwin/Platform Core tests report explicit skips if those modules are absent.

Installation backs up changed source files, rejects unsupported source anchors and customized unmanaged module targets, and restores the prior source when verification fails. Save all VS Code buffers before installing, so a later editor save cannot overwrite the installed patch. No research or Docker process needs to be stopped.

## API contracts

All routes below use `/api/neurocontinuum/v1`, the existing operator session, and `?mode=active` or `?mode=demo` where participant data are involved.

| Method and route | Purpose |
| --- | --- |
| GET `/status` | Adapter availability and installed-module directory |
| GET `/participants/{pid}/workspace` | Preferences, permissions, source references, saved workflows and case status |
| PUT `/participants/{pid}/consent` | Record explicit permission revision with `operation_id` and `expected_revision` |
| POST `/participants/{pid}/sessions` | Start/resume using `operation_id`, `session_id`, `checkin_id` |
| POST `/sessions/{sid}/commands` | `operation_id`, `expected_version`, enumerated action and optional warning-sign list |
| GET `/sessions/{sid}/evidence` | Consent-gated source/evidence export and hash-chain verification |

The request handler never imports arbitrary research scripts or runs shell commands. Only the fixed extension modules load during the existing API factory startup.
