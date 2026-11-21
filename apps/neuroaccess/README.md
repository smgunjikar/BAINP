# BAINP NeuroAccess — fresh local module v1

## What this release implements

A complete local preparation workflow, not the C01–C06 cognitive battery:
1. Local operator login.
2. Separate Active and Demo participant directories.
3. Persistent named adult participant profiles: age, education, language, digital
   familiarity, sensory/motor limitations, aids, interaction and display preferences.
4. Editable profiles with optimistic revision checks; saved check-ins retain their
   original condition snapshots.
5. Authorized-assisted-use acknowledgement. Navigation help and response assistance
   are different recorded conditions; disability alone is not a failure criterion.
6. Two real usability interactions: activate a button, then select a circle.
7. Stored completion/error/input/focus information with verified read-back.
8. Comparisons to the previous completed check-in at creation time. Language,
   input/device, sensory aids, motor limitations, assistance and display changes
   are listed explicitly. The comparison reference is fixed at creation; actual
   observed input differences are added when practice is saved. The final snapshot
   is preserved.
9. Explicit participant deletion cascades to linked check-ins and practice records.
   Identifying audit references are removed; a non-identifying deletion event remains.

## Active versus Demo
Both modes persist locally until explicit deletion. Demo is a separate data
namespace with fictional profile presets, not fake completed tests. Active records
are never returned by Demo-mode endpoints and vice versa. A check-in always belongs
to one participant and one mode. The selected mode and record IDs survive refresh
through the page URL; browser storage contains only the interface language.

Demo buttons create fictional profiles only. The user must complete practice.
Old fixture timelines, C00/C01 pages and databases are not imported into this module.
Legacy application source is archived by the installer, not destroyed.

## Architecture / files
- backend/api.py: strict Pydantic contracts, authentication, persistent SQLite,
  mode isolation, participant CRUD, immutable check-ins, readiness/practice rules,
  stored comparison snapshots, deletion and minimal audit metadata.
- backend/serve_frontend.py: static assets on loopback:3000, same-origin /api proxy
  to loopback:8000, response security headers and old-route redirects.
- web/index.html, style.css: responsive native forms, large controls, contrast,
  keyboard focus, reduced motion, skip link and logical RTL layout.
- web/i18n.js: English/Arabic interface and instruction dictionaries.
- web/app.js: one connected participant/check-in/practice/results flow; safe text-node
  rendering, accessibility preferences, immutable save retries and draft warnings.
- tests/verify_neuroaccess.py: real HTTP/API/SQLite tests using isolated temporary data.
- Start-NeuroAccess.ps1: start, stop, status and verification commands.

The fresh module deliberately uses FastAPI plus a native HTML/CSS/JavaScript frontend,
not the previous patched Next.js application. No Node build or legacy Alembic chain
is required. SQLite is intentional for a single-operator local prototype. This is
not a multi-user institutional deployment; a future PostgreSQL migration must be
explicit and tested rather than silently sharing the legacy schema.

## Storage and retention
Default directory:
  %USERPROFILE%\BAINP_DATA\local\neuroaccess_v1
Files: neuroaccess.sqlite3, SQLite WAL/SHM while open, local_operator_secret.txt,
managed process IDs and local startup logs. Set NEUROACCESS_DATA_DIR before install
and start to choose another location; keep it consistent. Source code is elsewhere.

No expiry job deletes participant records. Browser closing, logout, mode changes,
application restart and code reinstall do not delete saved records. Forgotten login
codes can be redisplayed by starting the app; never publish the code or data folder.

Deletion removes records from the working database and identifying audit links.
It is ordinary database deletion, not guaranteed forensic erasure of SQLite free
pages, filesystem snapshots or manually made copies. No automatic data backups are
created by this module. Exported/manual copies must be managed separately.

A fresh restart means old PostgreSQL participants/results do not appear in the new
UI. The old database is retained unchanged and is not required to run this module.
Raw/derived ADNI, OASIS, EEG and PADS files are not moved or modified.

## Authorization / security scope
Single local operator code, HttpOnly SameSite cookie with eight-hour expiry,
loopback-only listeners, same-origin proxy, restricted origins and required mutation
header. No credentials are placed in frontend source. Participant data is not encrypted
by this application at rest; use appropriate OS/device controls. This local HTTP
prototype must not be exposed to a public network as a clinical service.

Assisted-use authorization is a recorded participant/operator acknowledgement,
not identity verification of a clinician or proof of institutional authorization.

## What usability outcomes mean
Practice checks interface operation only. Incorrect actions, approximate client
latencies, actual input and focus changes are observations, not cognitive scores.
An observed method differing from the preference is flagged rather than hidden.
Practice uses the saved instruction language; that language is recorded in the
submitted log and checked on the server. It cannot change midway through practice.

Age and education are contextual metadata, not reference norms. Low digital
familiarity receives additional plain-language guidance. All users can adjust text,
contrast and reduced motion; no age-based cutoff claims measurement validity.

No recorded condition changes does not prove clinical comparability. Changed
conditions produce a review flag; they do not diagnose decline. Task-specific
comparability policy belongs to the future cognitive battery.

## Language/accessibility limits
English and Arabic UI/RTL and basic instructions are implemented. Arabic wording
still requires review by intended users and qualified language/accessibility experts.
Neither translation nor this practice has clinical measurement validation. Hindi
is a future localization, not implemented. Accessibility has not been certified.

The two practice interactions have native keyboard/mouse/touch handling and text
alternatives for assistive technology. No audio is required. Assistance is recorded;
a need for help navigating is not confused with help generating a response.

Readiness holds occur for reported/unresolved acute warning, unconfirmed instructions,
unresolved interaction access or unacknowledged assistance authorization. They are
conservative prototype preparation rules, not validated medical triage. The app does
not contact emergency services, diagnose, issue referrals or authorize clinical care.

## Run
Activate bainp, then:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\apps\neuroaccess\Start-NeuroAccess.ps1
It prints the LOCAL OPERATOR LOGIN CODE and starts API + frontend. Open
http://127.0.0.1:3000 and sign in. Managed background logs are in the data directory.

Stop only this module:
  ...\Start-NeuroAccess.ps1 -Service Stop
Check processes:
  ...\Start-NeuroAccess.ps1 -Service Status
Run API/storage tests in isolated temporary data:
  ...\Start-NeuroAccess.ps1 -Service Verify
For separate visible consoles use -Service Api and -Service Web instead of All.
Do not start the old npm/uvicorn application at the same time on ports 3000/8000.

## Manual acceptance flow
1. Sign in; select Demo; create a fictional English profile.
2. Save a new check-in (instructions understood; no acute warning).
3. Activate the practice button; deliberately select triangle once, then circle.
4. Check saved steps=2, incorrect actions=1, actual input and comparison baseline.
5. Reload and restart; verify the same record persists.
6. Edit profile to Arabic and a different input method; save a new check-in.
7. Complete its practice; inspect RTL, stored snapshot and condition differences.
8. Try authorized navigation help; confirm it is recorded without a blanket block.
9. Switch Active/Demo; confirm separation. Delete one demo participant by typing
   DELETE; confirm their check-ins disappear and unrelated records remain.

## Git and project tracking
Commit only apps/neuroaccess source, tests, README, requirements and launcher.
Review git status and git diff before staging. The installer does not commit/push.
Exclude /archive/, /patch-backups/, environment files, Python caches and local data.
If old source was already tracked, moving it creates deletions to review; Git ignore
rules do not remove prior history. Never stage the external data or login secret.

## Next modules (not implemented here)
NeuroCognition X: versioned C01 encoding -> C03 attention -> C04 switching ->
C05 symbol matching -> C02 delayed recognition -> C06 everyday function. Each future
attempt must bind to a saved NeuroAccess condition snapshot, with raw task telemetry,
task-specific access support, quality flags and independently validated interpretation.
NeuroGuard/CareLoop/research are separate future integrations. Do not infer diagnoses,
RCI or dementia probabilities from this fresh preparation workflow.
