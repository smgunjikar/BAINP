# BAINP implementation tracking — NeuroCognition research v1.3

Implemented in this update:
- Active and Demo always-visible study readiness links and participant dashboards.
- Core (C01–C06), Extended (C01–C10), Full (C01–C12, optional motor opt-in).
- Original C07 span, C08 spatial matching, C09 typed naming, C10 typed category
  switching, C11 motor tapping and C12 context tasks with raw observations.
- Constrained seeded task/item randomization, frozen manifests, version/form/
  exposure/interval tracking and automatic next-instruction progression.
- Descriptive per-person analytics grouped by recorded conditions; no disease,
  normality, reliable-change or improvement/decline classification.
- Bounded exact save retries, read-back verification and interruption recovery.
- Existing Core protocol/order/data preserved; persistent mode isolation/deletion.

Software checks: isolated HTTP/storage tests and simulated DOM/RAF flows. Human
usability, target-device timing, EN/AR equivalence, test–retest, form calibration,
practice-effect estimation and clinical validation remain unperformed.

Next independent work: NeuroGuard quality/abstention rules; appropriate longitudinal
reference models; clinician CareLoop; broader NeuroCore monitoring/recovery; research
tracks and ARENA. No autonomous task/scoring/safety modification is enabled.

Git: keep source/tests/synthetic fixtures/docs. Exclude entered records, exports,
secrets, databases, runtime logs, source backups/archives and raw research data.

Direct-start update: optional task practice, explicit understanding, persistent
preparation-policy audit, skipped/unsuccessful flags, recorded v1.1 administration
amendments and schema-v4 preparation deletion cascade. New item generator samples
larger defined banks and keeps memory/speed stimulus families disjoint. Content
assignments are tested across 100 seeds. Difficulty/scoring do not self-modify.

Input/results release: clickable stimulus/choice cards; pointer-down and duplicate
protection; composition-aware typed capture; explicit deadline commits and retained
unsubmitted drafts; revisioned local checkpoints; human-readable answer/timing/
provenance tables and append-only operator response reviews. Raw saved answers are
not changed. New schema v5 cascades checkpoints and reviews on participant deletion.
