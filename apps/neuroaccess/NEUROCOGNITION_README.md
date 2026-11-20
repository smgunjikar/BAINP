# NeuroCognition X research v1.3 — operator and engineering guide

Read INPUT_RESULTS_README.md for the v1.3 recorder, checkpoints, readable answer
tables and audited C09/C10 operator review. Existing submitted answers are preserved.

## Purpose and current scope

Original research implementations of C01–C12 linked to the same persistent
NeuroAccess participant UUID, name, saved check-in and Active/Demo boundary.
These are candidate digital observations, not clinically validated instruments,
MoCA/MMSE/CANTAB/NIH Toolbox equivalents, diagnoses or reliable-change scores.
Comments in `battery.py`, `extended.py`, `cognition.js` and `extended.js` describe
what the code does and the assumptions it makes.

## v1.2 direct start and item-bank update

Per-task cognitive practice is now OPTIONAL in the new UI. Confirm understanding,
then use **Start without practice**. After an unsuccessful practice, you may retry
or choose **Start after unsuccessful practice**. The server stores the explicit
preparation policy and passed/skipped/not-passed status on that attempt. Results
and dashboard groups retain these administration differences. No skipped practice
is fabricated as a pass. NeuroAccess readiness/usability practice remains separate
and required; its safety/condition checks are not bypassed.

This also works for a NOT-YET-STARTED task in an existing v1.0/v1.1 session: its
trial manifest stays unchanged, while the new administration policy is recorded
and flagged `PREPARATION_POLICY_AMENDED`. Already-started or saved attempts cannot
have their preparation policy rewritten. Historical records without this field
are labelled as historical required-policy records; practice status is not inferred.
The old API handshake remains supported for tests/older clients and still enforces
its original practice-pass requirement.

New sessions use `ncx-research-v1.2.0`. Existing sessions keep their recorded items.
Refreshing or reopening a session does not reshuffle it. Trial numbers 1, 2, 3...
are presentation counters, not evidence that the stimulus content is fixed.

| Task | New-session randomization within fixed task parameters |
|---|---|
| C01/C02 | Sample six study patterns from a 48-pattern memory bank per form; reserve disjoint immediate/delayed lures; seeded presentation/probe order |
| C03 | Seeded target placement, fixed 28 respond/12 withhold trials; bounded runs |
| C04 | Seeded cues/features/answer sides with 12 switches, 11 repeats and 12 left/12 right answers |
| C05 | INDEPENDENT 48-pattern binary-grid bank; 12 same/12 different pairs, six 1-bit and six 2-bit distractors; seeded order/pairs |
| C06 | Seeded presentation order of the same five original questions; no new wording or scoring |
| C07 | Seeded span order (same four lengths 2,3,4,5), positions and sequence |
| C08 | Seeded grids/sides; 3 each of four rotation angles and 6 left/6 right answers |
| C09 | Seeded six-object sample from twelve original drawings; separate sun practice item |
| C10 | Seeded cue order, six animal/six fruit prompts; stable dictionary-review rules |
| C11 | Seeded first hand; fixed position and 10-second windows to avoid adding target-location/motor-amplitude changes |
| C12 | Seeded order of the same context questions |

Memory and speed stimulus families are now deliberately disjoint. Earlier versions
used overlapping families, so an intervening C05 exposure could affect C02 answers.
Old data is preserved rather than re-scored; old-protocol C02 completions made by
the updated server carry a legacy-overlap quality flag. No claim of pure delayed
retention should be made from those earlier assignments.

The 48-item banks and new forms are original and UNCALIBRATED. Balanced counts and
seeded generation do not establish equal difficulty, reliability or clinical
validity. A/B forms still have repeated-exposure effects. No daily generation by an
LLM, online training or automatic score/difficulty improvement is enabled.

## Active-mode study entry

Every selected participant now has **Open study / check readiness** and
**Participant dashboard** links in BOTH modes, even before a completed check-in.
The study entry lists saved check-ins and their readiness blockers.

The screenshot supplied during development showed `instructions_understood=false`
and no saved access practice. This is not a missing Active-mode task engine:
that check-in legitimately cannot start cognition. Saved answers are immutable.
Use **Create a new accessibility check-in**, review accurate conditions, confirm
understanding if true, and complete access practice. Do not change factual answers
to get past a warning or accommodation-related hold.

Eligible saved check-in → choose battery → create linked session:

| Choice | Available tasks |
|---|---|
| Core | C01–C06 |
| Extended | C01–C10 |
| Full research | C01–C12; requires explicit optional motor-task acknowledgement |

Existing Core sessions keep their six tasks and original frozen order/manifests.
They are never silently expanded into a different protocol. To run all twelve,
create a NEW eligible accessibility check-in for the same participant and choose
**Full research**. Previous observations stay in the participant's history.

Only fictional records belong in Demo. Active stores entered records. There is one
local operator login, not a multi-tenant clinical system or verified clinician role.

## Connected conduct of the study

After verified saving, the app automatically opens the next task's instructions
when that option was selected at enrollment. It does not automatically answer,
start a timed task before the participant is ready, or bypass task practice.
The next instruction screen offers optional practice and requires an understanding confirmation.
C06 separately asks report source/consent. C12 has no scored practice.

Order for NEW sessions:

1. C01 learning.
2. C03, C04 and C05 in seeded randomized order.
3. C02 delayed recognition, never before C01; minimum 120 seconds after completion
   of C01. If needed, a countdown opens C02 instructions when the interval is met.
4. C06 everyday function with the same original questions (seeded display order in v1.2).
5. Extended/Full: C07–C10 in seeded randomized order.
6. Full only: optional C11, then C12 context review.

Old Core protocol: `ncx-core-pattern-v1.0.0`.
Previous protocol: `ncx-research-v1.1.0`. Current new-session protocol: `ncx-research-v1.3.0`.
Each session stores the exact manifest, seed, task order, form, protocol,
accessibility snapshot, device diagnostics and timestamps. Randomization does
not mean every possible task order is scientifically appropriate.

## Twelve original tasks

| Task | What the participant does | Recorded observations / limits |
|---|---|---|
| C01 learning | Six original geometric patterns for 2500 ms each; 12 immediate old/new probes with 5000 ms deadlines | Exposures, hits, false alarms, omissions and RT; pattern learning, not standardized object memory |
| C02 delayed recognition | Twelve probes: six studied patterns and six new lures distinct from the immediate lures | Hits, false alarms, omissions, RT and estimated delay; no delay-adjusted clinical score |
| C03 attention | Respond to circles; withhold for squares; 40 trials (28/12), 1200 ms + 300 ms gap | Correct withholds, omissions, commissions, correct RT distribution |
| C04 switching | Match shape or fill according to the cue; 24 trials, 4000 ms deadline | Choices/errors, repeated/switch-rule RT; switch cost only with ≥3 correct observations in each group |
| C05 speed | Same/different pattern decisions; 24 trials, 3000 ms deadline | Accuracy, errors, omissions and RT |
| C06 function | Five original questions about change in everyday activities | Separate self/informant item responses, consent and authorization attestation; no total scale score |
| C07 working memory | Repeat grid-cell sequences of fixed lengths 2, 3, 4, 5 | Individual cell presentation timing, selected order, position errors, maximum correct presented length; NOT a calibrated adaptive span |
| C08 visuospatial | Match a 3×3 pattern after a cued clockwise rotation; 12 trials | Rotation, options, choices, accuracy and RT; original spatial matching prototype |
| C09 language | Type names for six original object drawings; 20 seconds each | Raw typed answers, exact dictionary matches, omissions and unmatched answers requiring human review |
| C10 category switching | Alternate animal/fruit cues and type a word; 12 trials, 10 seconds each | Raw answers, repetition and dictionary-review information; not a clinical spoken fluency test |
| C11 motor | Tap with the indicated hand for 10 seconds, then the other | Every tap offset, intervals, rate and left-minus-right rate when both windows complete; hand use is self-reported |
| C12 context | Report month, year, place and changed conditions | Context responses only; no orientation diagnosis or location/time accuracy score |

C07 uses 700 ms highlights and 300 ms blanks; its response window starts after
actual presentation. The server verifies recorded cell sequence and exposure.
C08 angles and grids, C09 item order, C10 starting category, C11 hand order and
C12 item order are seeded. C06 wording remains fixed; display order is frozen per v1.2 session.
Task length/difficulty/stopping rules are fixed for a version.

C01 immediate probes themselves add retrieval practice/exposure, so C02 is not
pure retention from a single exposure. EN/AR translations and the original
geometric/object stimuli are uncalibrated and not culturally validated.

## Safe randomization and practice effects

Forms A/B have different original patterns; initial form assignment is derived
from participant UUID, then forms alternate across created sessions. Stimulus
order and task-specific layouts use the session seed. Frozen manifests reproduce
the actual assignment. Forms are NOT calibrated parallel forms; two forms cannot
eliminate learning with repeated daily use.

Past task attempts, same-form attempts and interval since the previous session
are recorded in comparison metadata. These are exposure counts/context, not
estimated practice-effect corrections. Interrupted attempts remain part of the
record because they may have exposed stimuli.

No AI generates fresh assessment content, changes difficulty, changes scoring,
or optimizes stopping rules from one day to the next. Such changes could alter the
measurement construct and confound longitudinal observations. Refinements require
a new immutable version, prespecified evaluation and a calibration/validation study.

## Timing, device and accessibility boundaries

- Client performance-clock timestamps and RAF scheduling are approximate software
  observations. No display photodiode, touch-latency or motor-latency calibration.
- Server checks identity/mode, sequence, finite numeric values, durations, expected
  items, legal responses and elapsed-time plausibility; derives descriptive metrics.
- Raw onset/duration/RT/input, frame gaps, practice logs and interrupted practice
  runs are retained. C07 stores per-cell presentation records; C11 stores each tap.
- Device metadata includes user agent, viewport, pixel ratio, pointer capability,
  initial RAF interval statistics and estimated timer resolution.
- English/Arabic instructions and RTL, native controls, stored text size, contrast
  and reduced motion are inherited from the saved NeuroAccess record. Physical
  left/right grids remain row-major even on RTL pages.
- Keyboard choices 1/2 and Space for attention; C07 keys 1–9; C11 Space/Enter or
  pointer/touch tapping. Native controls support some assistive activation, but
  event type does not reliably identify every assistive device.
- A screen-reader narration of visual patterns is not an equivalent visual task.
  No general suitability for all sensory/motor impairments is claimed.
- Language tasks involve typing, literacy, spelling and device/motor speed. Unknown
  dictionary entries are HUMAN REVIEW REQUIRED, never automatically called disease
  errors. Accepted spellings are only a limited transparent lookup list.
- C11 is explicitly a motor/input observation. Its rate is not combined into a
  cognitive health score; true hand use cannot be verified by this browser.
- No automatic device-latency subtraction or sensory/motor correction is applied:
  there is no calibration evidence supporting such corrections.

Engineering flags (100 ms frame gaps, 500 ms presentation overruns, <100 ms response)
are descriptive diagnostics, not validated clinical cutoffs. Browser logs can be
forged, and plausible logs do not prove a participant saw or understood a stimulus.

## Per-participant dashboard

Open `/cognition-dashboard?mode=active|demo&person=PARTICIPANT_UUID` using the link
in NeuroAccess or the study workspace. It shows session counts, complete/interrupted
status, dated history, task-specific raw results, quality flags, and response-time
points where available. The exact numeric values remain accessible in tables/logs.

Filter a task, then a recorded-condition group. Groups include protocol, form,
whole battery order, language/input/device/assistance/accommodation snapshot and
stable device descriptors. Refresh-interval noise is not used to create new groups.
Even exact recorded-condition matches do NOT establish clinical comparability.
No slope, disease risk, normal/abnormal label, reliable change index or claimed
improvement/decline is generated. Different forms and versions are not pooled.

## Recovery and separation of engines

Implemented now: exact retry identities, immutable results, bounded automatic
save retries for temporary/network/server failures, read-back verification,
explicit incomplete/reload recovery and source backups before upgrades.
Available logs stay in memory until saved; a browser crash can lose unsaved trials.
A running attempt after reload must be marked interrupted, never silently replayed.

Not implemented: autonomous source editing, model training, item-bank improvement,
service-wide process watchdogs or self-modifying safety rules. These remain
NeuroCore engineering work. NeuroGuard's full evidence/comparability/abstention
engine is separate and must have independently controlled rules. Existing
NeuroAccess holds are read by cognition; task code cannot overwrite them.

Next project integration order: verify human usability/timing → independent
NeuroGuard quality rules → versioned longitudinal analysis with suitable reference
parameters → clinician CareLoop workflow → broader NeuroCore monitoring/recovery
and research tracks/ARENA. Software stability alone does not authorize clinical
change detection.

## Persistence, deletion and security

SQLite schema v5 adds input checkpoints and response reviews, in addition to nc_preparations with a cascading foreign key to each attempt; existing v3 records are retained. The new version uses stored manifest
metadata and additional validated JSON observations; no reset or PostgreSQL/Alembic migration is required. Existing Core rows retain their frozen protocol and content.

Default working directory:
`%USERPROFILE%\BAINP_DATA\local\neuroaccess_v1`, or the SAME
`NEUROACCESS_DATA_DIR` override used at startup. Use the existing launcher and login.
Mode changes, logout, refresh and process restart do not delete records.
NeuroAccess's explicit participant deletion cascades sessions/trials/reports and
removes identifying check-in audit links. A nonidentifying deletion event remains.

JSON exports, OS/OneDrive backups and external copies require separate management.
Database deletion is not forensic erasure. Source backups contain code, not a copy
of the working participant database. The service is loopback/local-only; it is not
an institutional deployment or verified clinical authorization system.

## Verification and Git

`Start-NeuroAccess.ps1 -Service VerifyCognition` runs `tests/verify_inputs.py`,
including inherited NeuroAccess/Core tests, all-12 pathways for Active and Demo,
strict validation, form/order assignment, holds, immutable retries, historical
Core compatibility, dashboards, persistence and deletion. Tests use synthetic data
and isolated temporary databases/random ports. Some fixtures age test timestamps
or populate prior completed task placeholders to reach later APIs quickly; these
are test arrangements, never production bypass endpoints or human evidence.

Development also runs simulated DOM/RAF checks for all twelve task screens,
progression, preferences, Arabic dashboard and partial-sequence interruption.
These are NOT real-device timing, clinical or usability studies. Windows launcher
execution and human browser acceptance must be checked locally.

Keep in Git: `backend/*.py`, `web/*`, `tests/*.py`, the synthetic `tests/core_v1_manifest.json` and `tests/research_v11_manifest.json` fixtures, launcher, requirements and documentation.
Exclude DB/WAL/SHM, login secrets, process metadata, logs, entered-data exports,
patch-backups, archive, caches and raw research datasets. Installer updates relevant
ignore rules but does not stage, commit or push anything.
