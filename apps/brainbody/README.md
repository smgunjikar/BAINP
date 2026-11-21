# BBC-BE — Brain–Body Context & Biomarker Engine v1

A source-aware, consent-aware health-context research module for BAINP. It organizes
cardiovascular, metabolic, sleep/activity, wellbeing, lifestyle, history, biomarker,
family-history and professional genomic context. It does not calculate a neurological
diagnosis, treatment, individual prevention benefit or direct brain oxidative-stress value.

## Installation

Run Install-BBC-BE.ps1 from the existing BAINP root in **bainp**. The existing FastAPI,
Pydantic 2 and stdlib SQLite environment is reused; no new web/runtime dependency is
installed. The installer backs up changed code outside Git, preserves source datasets
and participant databases, adds static asset routes and the participant home-page card.
Restart only the existing BAINP frontend/API, then refresh Ctrl+F5.

Pass `-Verify` to run the integration suite with the existing Uvicorn runtime and
Python's standard-library HTTP client. Tests use a temporary database and a temporary
loopback port. Installation and verification report separate results.

- Home page: select participant → Brain-Body Context & Biomarkers → Open BBC-BE.
- /brain-body?mode=active&person=PARTICIPANT_UUID
- /brain-body?mode=demo&profile=control
- /brain-body?mode=demo&profile=impairment

Demo presets are coherent fictional profiles, not records copied from ADNI, OASIS,
PADS or OpenNeuro. Values, reference intervals, case labels and history are invented.
They never insert into active or selected-demo participant storage. Select an existing
demo participant to save editable fictional records. The preset display is read-only.

Folders:
- apps/brainbody/backend: dictionary, contracts, engine, source reader and authenticated API.
- apps/brainbody/frontend: responsive interface, forms, charts, evidence and review reports.
- apps/brainbody/research: offline baseline-vs-context prediction comparison.
- apps/brainbody/integrations: authorized same-person JSON publisher.
- apps/neuroguard/backend/brainbody_policy.py: independent interpretation boundaries.

## Dashboard and core behavior

Eight system tiles; current observations; separate source/assay/unit histories; aligned
cognition/context panels; observed/available/received timestamps; immutable revision
history; assay and reference details; local review notes; evidence links and a source-to-
statement graph. Export JSON evidence or an escaped standalone HTML review report.
The review workspace uses the existing operator session, not an independently verified
clinician credential. Review notes do not certify clinical validity or change raw values.

Canonical payload hashes track the structured record; they do not authenticate an external
laboratory document or prove an assay is clinically validated. Source identity and permission
assertions must be independently verified by the authorized operator.

The interface preserves form values after a failed save and retries the same pending
record ID, avoiding silent duplicate observations. A successful correction appends a
revision; source identity, record type and metric remain immutable. Duplicate source
records are rejected even if a caller invents a second record UUID. Delete removes all
revisions and review notes for that record. Deleting a NeuroAccess participant cascades
through this module. Other module observations are not deleted by BBC-BE record deletion.

No source data are imputed in the dashboard. Missing and censored results are retained.
Numerical summaries are descriptive; no calibrated clinical change threshold or expected
sampling schedule is assumed. Multiple daily sleep/step summaries are not silently summed.
Blood-pressure components are checked only in the same explicit encounter, time, source,
device/cohort identity and measurement context. Inverted or ambiguous components are
excluded from summaries and queued for source review without invented corrections.

## Consent and sensitive findings

BBC-BE has separate versioned scopes: context, clinical_biomarkers, family_history,
genomic_summary and molecular_research. Base participant storage consent does not
implicitly authorize these. Each write checks its scope inside the SQLite transaction.
Withdrawal removes the scope from current processing/display and from NeuroTwin context;
records stay stored until explicit deletion. Current withdrawal also restricts historical
replay, so an old cutoff cannot bypass it.

Professional genomic content is excluded at the SQL selection boundary by default.
Even with genomic scope, the operator must explicitly request disclosure in the review
view. Revision reads and exports respect that boundary. Exports that include disclosed
genomic summaries ask again within the app. No raw VCF processing, variant interpretation,
APOE-derived risk score, genetic counseling replacement or onset-date prediction exists.
Family-history entries use relationship degree and contextual reports, not relative names.

This is a local shared-operator prototype. Consent/disclosure controls do not substitute
for production role-based access, encryption/key management, audit governance or
institutional genomic privacy controls. Do not expose the loopback services remotely.

## Data dictionary and assay validation

Supported measurements include BP, heart rate, glucose, HbA1c, lipids, sleep duration,
device-estimated sleep efficiency, activity, steps, movement RMS, externally administered
questionnaire totals, amyloid beta 40/42, p-tau181/217, NfL, GFAP, CRP, F2-isoprostanes and
an assay-specific oxidized-nucleic-acid research marker. The dictionary is an allowlist,
not a list of validated clinical interpretations. GET /api/brainbody/dictionary provides
units, sources, scope and assay requirements.

Units remain as reported. No automatic HbA1c IFCC/NGSP conversion, cross-assay pooling,
biomarker positivity cutoff or wearable-to-molecular inference is performed. Assays must
provide name, version, laboratory, method and specimen. HbA1c requires a whole-blood/
RBC-based assay context in this initial dictionary. Creatinine-normalized units require
urine. Device-origin molecular/oxidative results are rejected. Questionnaire totals require
instrument, version, language, administration and permission-basis metadata; no copyrighted
items are reproduced or permission/validity inferred by the software.

A supplied reference interval must have matching units, source and population context.
An interval-position label is withheld unless applicability is confirmed and the source
result is usable and exact. Clinical decision limits are retained for qualified review,
not treated as universal reference intervals. Being inside a supplied interval is explicitly
not a health classification. Values outside supplied quantitation limits require source
review and are excluded from point summaries. < or > bounds, not-detected and not-reported
results are never silently treated as exact numbers or zero.

Longitudinal groups preserve metric/unit, source kind/organization/device/cohort, assay
name/version/specimen/method/laboratory, instrument version/language and comparable
measurement context. Use a stable measurement_context_key for a prespecified repeated
measurement protocol; descriptive free-text context remains available. Without such a
key the context text itself keeps distinct conditions separate.

## Three clocks and historical replay

observed_at: physiologically relevant observation/specimen-collection/report time.
available_at: when that result/report became available from its source.
known_at: when this immutable revision was received by BAINP (server assigned).

observed_at and available_at are timezone-aware and normalized to UTC; future values and
availability preceding observation are rejected. available_at cannot move backwards on
correction. A later correction has a later server-known time, so historical replay retrieves
the version actually known at the cutoff. Current consent is still enforced.

Context windows are explicitly engineering choices, not validated causal windows:
three preceding days for sleep/heart-rate context and 30 days for other point observations.
Reported medical/family history remains dated reported context; medication exposure
requires an explicit effective interval. A history report is not a diagnosis of an active condition. Alignment distinguishes evidence known before session start from retrospectively
entered context. Old NeuroSense records lacking availability/receipt metadata are labelled
unknown, not assumed available to a past model. They are withheld from historical replay.

Historical cognitive points require a verified nc_attempts.finished_at before the cutoff.
Current whole-battery status is not reconstructed as a past status. No future cognitive
outcomes are shown merely because their session start preceded a historical query.
The source-read sequence is eventually consistent, not synchronized multimodal acquisition.

## NeuroTwin and existing sources

The installer optionally patches the supplied NeuroTwin V2 to add a BBC-BE source tile,
a health-context overview section and a link to this workspace. Updates, corrections,
consent changes and deletions change the derived context fingerprint on the next refresh.
The twin receives a bounded nonsensitive summary; genomic contents are not sent there.
Both demo presets refer to the same authored fictional profiles as NeuroTwin when installed.

Cognition is read through the existing NeuroCognition analytics function. Wearables are
read from the existing participant/mode NeuroSense store after context authorization.
BBC-BE does not acquire a new wearable signal or lab test. Neither polling nor context
updates retrain a model. The new context summary does NOT silently change an existing
NeuroTwin forecasting model's inputs, coefficients or clinical logic.

If installing BBC-BE before NeuroTwin, it works independently; rerun the installer after
installing the supplied NeuroTwin V2 to add the adapter. Reinstalling an older NeuroTwin
package later may replace its patched files; rerun BBC-BE integration afterward. Unknown
integration anchors fail before mutation instead of guessing at a user's edited code.

## Authenticated APIs

All routes require the existing operator cookie. Mutations require
X-NeuroAccess-Request: 1. Mode and participant UUID matching are enforced.

- GET /api/brainbody/dictionary
- GET /api/brainbody/participants/{UUID}?mode=active|demo
  Optional as_of=timezone-aware timestamp; include_sensitive=false by default.
- GET/PUT /api/brainbody/participants/{UUID}/consent?mode=...
  PUT: expected_revision, scopes[], authorization_reference.
- PUT /api/brainbody/participants/{UUID}/records/{record_UUID}?mode=...
  Strict Record payload; first revision 1; exact retries idempotent; corrections +1.
- GET /api/brainbody/participants/{UUID}/records/{record_UUID}/revisions?mode=...
  Optional include_sensitive; separate genomic authorization still required.
- DELETE same record route with expected_revision=...
- PUT /api/brainbody/participants/{UUID}/reviews/{record_UUID}?mode=...
  record_revision, finding_code, status, note, optional include_sensitive=false.
- GET /api/brainbody/demo?profile=control|impairment&include_sensitive=false

Private SQLite tables: bb_consents, bb_records, bb_versions, bb_identity_links, bb_reviews.
Identity links bind a cohort/source-subject to only one local participant in a mode. Exact
cohort/subject contradictions with NeuroTwin imaging or clinical source links are rejected
in both directions. Source reads also withhold contradictory records rather than assigning
another person’s measurement. Aliases still require independent human/source verification. There
is no auto-linking by name or pooling unrelated study participants into one person.

## API input example

A separately authorized, same-person measured observation (values below illustrate the
contract; they are not supplied patient data):

```json
{
  "revision": 1,
  "kind": "measurement",
  "observed_at": "2026-11-01T09:00:00+05:30",
  "available_at": "2026-11-01T09:01:00+05:30",
  "source": {"kind": "self_report", "organization": "Participant report", "record_reference": "unique-observation-001"},
  "identity_verified": true,
  "metric": "bp_systolic",
  "value": 120,
  "unit": "mmHg",
  "qualifier": "exact",
  "quality": "review",
  "context": "Reported seated measurement; verify original method and cuff",
  "measurement_context_key": "reported-seated-bp-protocol-v1"
}
```

For authorized structured integrations, prepare a JSON list of {id: UUID, payload: Record}.
After recording scopes in the interface:

```powershell
conda activate bainp
python .\apps\brainbody\integrations\publish_context.py `
  --participant YOUR_VERIFIED_PARTICIPANT_UUID --mode active `
  --input "C:\path\authorized-context-records.json" --same-person-verified
```

The script prompts for the operator code without echo and never grants consent. Requests
are sequential; if part of a batch is rejected, prior accepted records remain and exact
retries keep the same IDs/revisions. Source identity must be verified independently.

## Offline research comparison / NeuroSignal ARENA foundation

Use the existing **bainp-brain** environment with NumPy and scikit-learn; do not automatically
upgrade other research dependencies. compare_context.py evaluates a prespecified Ridge
baseline against baseline-plus-context for 12-month cognitive-score change. It requires
one globally resolved baseline per person, one cohort and fixed instrument/assay/source
contexts. The code cannot verify aliases or source identities on its own.

Required CSV columns:
cohort, participant_id, index_time, feature_available_at, target_time,
cognitive_instrument, cognitive_version, bp_context, hba1c_assay, hba1c_specimen,
sleep_source, baseline_score, target_score, age, education_years,
bp_systolic, hba1c_percent, sleep_hours. Optional subgroup.

feature_available_at must be the latest actual source-availability time of ALL input
features, at or before index_time. The researcher must verify that declaration against
authorized source records. This retrospective cohort comparison is not a claim that BAINP
had ingested that cohort at the historical index. Targets must be observed approximately
12 months later (335–395 days), not fabricated future outcomes. Explicit input units are
mmHg, HbA1c % and sleep hours; there is no silent conversion.

```powershell
conda activate bainp-brain
python .\apps\brainbody\research\compare_context.py `
  --input "C:\path\authorized-prespecified-cohort.csv" `
  --output "$env:USERPROFILE\BAINP_DATA\derived\brainbody\context-comparison-v1"
```

Five-fold participant-separated evaluation uses identical folds for both models. Median
imputation and scaling fit training folds only. Ridge alpha=1 is prespecified, with no
performance-driven selection. Outputs include MAE, RMSE, paired error differences,
missing-context counts and supplied-subgroup summaries (estimates suppressed below ten
members). A descriptive participant bootstrap is conditional on the OOF predictions and
does not capture all fold/model/transport uncertainty. At least 30 participants is an
engineering workflow bound, not a scientific power calculation.

More context is not assumed to improve performance. No disease probability, probability
calibration, causal effect, clinical fairness certification, external validation or deployment
approval follows from this comparison. No private ADNI/OASIS/LASI-DAD cohort was analysed
by this installer. Survival, genomic and mechanistic oxidative-stress modeling remain
separate research programmes requiring appropriate data, governance and validation.

## Verification and boundaries

Default engineering checks: python apps/brainbody/tests/verify_brainbody.py in bainp
(FastAPI TestClient also needs httpx). Numerical checks: tests/verify_research.py in
bainp-brain. Tests use temporary invented data and do not touch participant records.
See tests/VALIDATION.md for the actual checks performed and remaining target-platform
verification. No unit test is a clinical validation or evidence of superiority over health apps.

Evidence sources checked 6 November 2026:
- https://www.who.int/news-room/fact-sheets/detail/dementia
- https://www.nia.nih.gov/health/biomarkers-dementia-detection-and-research
- https://hl7.org/fhir/observation-definitions.html

FHIR concepts inform timing/reference semantics; this is not a certified FHIR/clinical EHR
implementation. Questionnaire permissions, applicable regulation and institutional clinical
access are not certified by this research prototype.

## Session review workflow in v1.1

In demo mode, open the fictional BBC-BE scenario directly from the BAINP home page.
For participant records, follow **Review brain–body context for this session** from
NeuroCognition results. Health and lifestyle authorization is required to load the
participant's cognitive sessions. The session selector shows authorized sessions for
the selected person and evidence cutoff. Each session groups observations by what
BAINP knew before session start, what became available or was entered later, and
wearable records with unknown availability. The review includes recorded cognitive
observations, source and assay metadata, quality notes, and contextual discussion
questions with source links. The local HTML review export includes the selected
session and the full set of visible health-context observations.

## Connected BAINP workspaces

The BBC-BE source panel distinguishes an available observation stream, a missing
authorization, an empty source, and a registered NeuroTwin source link. Authorized
NeuroCognition sessions and NeuroSense observations feed BBC-BE directly.
NeuroVision identity links, NeuroPulse EEG records, and Clinical source records
are read as counts from NeuroTwin's same-participant, same-mode registrations.
MRI and EEG content stays in the source workspace. Registered counts do not prove
that a scan or recording package is available. Current registrations are withheld
from historical BBC-BE replay. The research imaging viewer is a cohort workspace
and receives the mode only.

The panel links to the corresponding anatomical, neural and governance views in
NeuroTwin. Supported NeuroCognition, NeuroSense and NeuroVision pages provide a
return link. Feature links are exposed only when the associated frontend is
registered and its asset exists. The fictional BBC-BE profile carries into
NeuroTwin's matching fictional profile. NeuroGuard findings remain visible in the
BBC-BE review workspace, and NeuroCore model governance remains in NeuroTwin.
