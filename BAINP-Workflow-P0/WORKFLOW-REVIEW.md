# BAINP participant journey implementation review

Grounding: user-supplied flowcharts and screenshots, and earlier local source snapshots.
No current live application audit was possible here. The Windows working tree may differ.

## Product contract
1. Participant creation leads to persistent setup, then NeuroContinuum participant home.
2. Completed setup steps remain editable. No, yes, unanswered, and deferred must remain distinct.
3. Core consent declined leads to limited home with support/privacy; optional declines remain off.
4. NeuroQuest selects an action from the actual task registry: baseline, supported targeted task,
   monitoring, pending review, or an explained restriction. An engine name is not a participant navigation requirement.
5. Task readiness is checked before launch and again at the authoritative backend boundary.
6. Pause resumes only where the actual task protocol permits. Interrupted timed tasks need an explained restart path.
7. Completion, validity, and accepted history are separate states. Invalid measurements stay visible as such
   but do not silently enter valid longitudinal summaries or trigger an endless full-battery retry.
8. Results return to home with one next action. Pending CareLoop cases show their actual status.
9. Role routing uses authenticated server permissions. A role dropdown cannot grant clinician/researcher access.

## Issues identified in earlier source
- NeuroAccess profile PATCH increments revision even for identical saves.
- NeuroContinuum access_reasons rejects any participant revision mismatch or profile inequality.
- Workflow configure increments consent revision and blocks every open session even for identical permission saves.
- NeuroQuest explicitly abstains for vision/motor limitations, unsupported hearing conditions, and assistance
  because the registered battery has no validated alternative. Removing that check is not a UX fix.
- Journey policy requires completed check-in matching current profile revision and returns a generic review
  for BLOCKED/FAILED. Frontend recovery links have previously bounced between home and workflow.

The included installer fixes ONLY identical saves. It preserves actual permission-change revalidation,
optimistic concurrency, operation replay, and all existing access gates. It does not solve real profile edits yet.

## Change-impact rules for the full patch
| Change | Required behavior |
|---|---|
| Identical profile or consent save | No revision/state reset; return persisted result |
| Display name | Update label; preserve preparation and task evidence |
| Language, input method, device, visual presentation, assistance, relevant background | Recompute only affected task/protocol eligibility; preserve setup answers/history |
| Core consent withdrawal | Prevent affected future execution immediately; follow retention/deletion settings |
| Optional scope withdrawal | Stop that scope; refresh only recommendations depending on it |
| Missing mandatory answer | Ask for that answer with a direct destination and return context |
| No validated accessible task | Explain availability; offer support/monitoring or authorized review, never remove real limitation |
| CareLoop case saved | Display recorded status; do not imply a clinician was contacted or assessment was cleared |

Implement task-specific dependency fingerprints rather than a global profile revision as the sole invalidation key.
Historical check-in snapshots remain immutable. Do not rewrite their profiles/revisions to make old evidence pass.
Actual changes during a timed assessment follow that task's interruption policy and preserve provenance.

## Corrections to the visual examples
- The home example shows 3/5 setup steps alongside Start assessment. In production, show setup action until
  mandatory prerequisites are met. Onboarding progress and assessment progress are separate counts.
- Ready to begin must have an explicit Open My Brain Health action; do not copy the disabled final Continue.
- Review later is a saved deferred answer, not equivalent to no accommodation and not automatic task eligibility.
- The consent mockup only illustrates NeuroShadow. The real form must include explicit core assessment consent,
  independent optional scopes, policy/version and saved timestamps. Defaults must never imply acceptance.
- Avoid a generic green check on deferred accessibility that implies resolved task compatibility.
- Initial-concern and safety failures need concrete recovery, not just links between two dashboards.
- A clinical concern routes to the existing safety/review process; NeuroMimic/Proof are explanatory inputs,
  not authority to diagnose, clear a restriction, or contact a professional.
- History permission must not be casually made a universal condition for first assessment. Inspect the actual
  duplicate/burden policy and available task evidence before changing this current NeuroQuest rule.

## Implementation sequence and acceptance
P0: unchanged-save fix and current source verification; participant creation route.
P1: server-persisted setup answers and granular consent; restore after refresh, login and Back.
P2: one backend decision presented by both home and workflow; readable participant shell matching references.
P3: actual task registry launch, scoped revalidation, supported resume/restart paths.
P4: completion -> quality -> history -> results -> home, idempotent callbacks.
P5: pending CareLoop review/status, relevant context and evidence in the same journey.
P6: scenario A/B/C plus no-op saves, name edits, true eligibility changes, consent withdrawal,
    stale tabs, concurrent writes, failed/paused tasks, zero eligible tasks, duplicate callbacks,
    optional permissions declined, refresh on each setup screen and role authorization.

## How to use this delivery
1. Run the source collector against the Windows project and review its ZIP before sharing.
2. Optional narrow fix: run installer with --check then without --check; it rejects unknown source snippets
   before writes, backs up both files, and rolls back files if a write fails. Restart backend.
3. For rollback stop backend, restore both saved files from the printed backup, then restart.
4. Keep watch integration paused under the existing reminder.

Validation: targeted tests use earlier source snapshots and temporary SQLite data. They are not proof of
Windows installation, the actual production transaction wrapper, or end-to-end clinical workflow behavior.
