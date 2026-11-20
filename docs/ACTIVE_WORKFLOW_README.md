# BAINP active workflow repair v1

## Why the repeated blocking happened
The screenshot intake and encoding URLs referred to different assessment IDs.
The newer saved intake selected motor assistance; the older encoding URL referred
to an acute-warning intake. Both were held by the current C00 policy. Adding more
links without an active-session coordinator made navigation confusing.

## Pages
- /active: select participant and assessment, see gate, open the next available task.
- /results?id=UUID: inspect the same session's stored C00/C01 records and timing table.
- /demo: existing read-only fictional longitudinal histories. These are generated
  fixtures, not results of completing the active battery.
- /assessment: redirects to /active, preserving query parameters. The old workspace
  source is backed up; its unresolved AssessmentPractice render path is retired.
- /intake and /encoding: retain saved-record protections and gain active/results links.

The explicit supported-demo button creates a NEW fictional participant, assessment
and preset intake. It does not alter held records, create exposure logs, or disable
server gating. Its exact conditions are shown before the required acknowledgement.
An interrupted attempt still requires a new assessment; it is not converted to a pass.

## Module responsibilities
NeuroAccess: consent, language/input/accommodation capture, instructions and entry
conditions. C00 is its prototype intake. Arabic translation, touch task adaptation,
calibrated device timing and fully accessible alternatives are not implemented.

NeuroCognition X: executes task protocols and stores raw observations. Planned order:
C01 encoding -> C03 attention -> C04 rule switching -> C05 symbol matching ->
C02 delayed recognition -> C06 everyday function. C02 numbering denotes task identity,
not execution order.

C00: records conditions and computes explicit demo allow/hold reasons.
C01: presents eight English words and saves client-reported exposure logs. It does
not ask for recall or score memory; C02 will test recognition after intervening tasks.
C03: planned go/no-go attention responses, omissions and commissions.
C04: planned rule switching with repeat/switch trial accuracy and response times.
C05: planned symbol matching throughput and accuracy.
C02: planned target/lure recognition with actual encoding-to-recognition delay.
C06: planned structured everyday-function self-report, separate from objective tasks.
Only C00/C01 are connected. Separate practice is not completed C03 core assessment.

## Files / Git targets
app/workspace.py: read-only summary/list endpoints. No new migration.
web/src/app/workspace/WorkspaceClient.tsx: active and results coordinator.
web/src/app/active/page.tsx, results/page.tsx: route wrappers.
assessment/page.tsx: legacy route redirect.
intake/page.tsx, encoding/page.tsx, demo/page.tsx: navigation additions.
tests/verify_workspace.py: local HTTP verification with labeled test fixtures.
This README, WORKFLOW_REPAIR_STATUS.md and verification receipt belong in docs.
Exclude patch-backups, environment files, dependencies and dataset derivatives.

## Verification scope
Installer: syntax, API registration and frontend production build.
-Verify: database-backed HTTP identity/gate checks; creates synthetic test records.
Manual: create a supported synthetic demo -> Start C01 -> keep window focused
for ~24 seconds -> completed, 8 entries -> open saved results for SAME ID.
No complete-battery score, clinical diagnosis, RCI or clinician referral is available.
