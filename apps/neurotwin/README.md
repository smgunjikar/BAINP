# NeuroTwin X V2 — four research workspaces

This upgrade implements an anatomical, cognitive, neural and predictive research
workspace. It includes coherent synthetic control and cognitive-impairment scenarios
covering cognition, wearables, EEG and clinical context. No private research cohort was
trained or evaluated in this build. It does not create a complete biological brain replica,
universal disorder detector or clinically validated prognosis.

## Install and open

Use the existing **bainp** environment for the frontend/API. Run the downloaded
Upgrade-NeuroTwin-X-V2.ps1 from the BAINP repository root. It preserves source data and
existing participant records, adds a home-page card when missing, and backs up changed
code outside Git. Stop/restart only the existing BAINP frontend/API and refresh Ctrl+F5.
Existing NeuroVision/NeuroSense routes are preserved. No new runtime package is needed.

- Home-page NeuroTwin card: selected participant in active or demo mode.
- Full synthetic control: http://127.0.0.1:3000/neurotwin?mode=demo&profile=control
- Full synthetic impairment: http://127.0.0.1:3000/neurotwin?mode=demo&profile=impairment
- Demo Workspace selector: choose either synthetic scenario or existing fictional records.

All views require the existing operator login. Synthetic examples never write participant
observations, never become active source records, and never borrow unrelated ADNI,
OASIS, OpenNeuro or PADS people. The synthetic impairment label is part of the authored
fictional scenario; it is not a disease classification inferred by the engine.

## What is implemented

**3D Brain Twin**: inline linked MRI intensity rendering, supplied scan-derived surfaces,
rotation/zoom/reset/cutaway/mask controls and regional measurement tables. Existing
NeuroVision packages are verified by hash and participant identity. Optional FreeSurfer
packages add real supplied pial surfaces, regional volumes and cortical thickness. This
module does not run recon-all or invent segmentations. Synthetic geometry is explicitly
procedural illustration, not an MRI reconstruction. The numeric synthetic regions are
invented and are not measurements of that procedural geometry.

**Cognitive Twin**: all C01–C12 source task records, everyday-function reports, typed-answer
review counts and numeric histories grouped by exact condition. Flagged/interrupted
records remain visible and excluded from fits. Descriptive daily-median OLS slopes use at
least four eligible days spanning seven days (an engineering threshold, not clinical
validation). Clinical RCI and practice adjustment remain unavailable without calibration.
The synthetic example includes a local-level Kalman filter with explicitly assumed
response-time measurement variance 2500 ms² and process variance 1.5 ms²/day. Its bands are conditional
on those assumptions; no active calibrated state estimator is asserted.

**Neural Twin**: versioned participant-linked EEG record API, bounded waveform payloads,
looped recorded replay, delta/theta/alpha/beta features, alpha-peak candidate, entropy, PSD,
window-quality counts and a channel correlation table derived from supplied covariance.
Neither covariance nor correlation is anatomical connectivity or causal network coupling.
A separate bainp-brain preparation script computes features from supported MNE inputs.
Resting EEG without markers cannot provide ERPs. Actual live device acquisition, clock
synchronization and whole-brain network simulation are not installed by this upgrade.

**Predictive Twin**: an offline, prespecified logistic baseline workflow for a single
24-month outcome, held-out participant evaluation, optional external-cohort evaluation,
bootstrap parameter sampling and a separate deployment gate. Active inference requires
an independently reviewed model, hash-matched approval policy, supported clinical input
protocol/population and same-visit MMSE/age/education. Missing or unsupported inputs,
elapsed forecast horizons and incompatible current clinical state cause abstention.
No active model is installed. A hypothetical query endpoint cannot modify source records.

The synthetic probability uses intentionally invented coefficients; it was not trained on
clinical data. Its target is an invented follow-up event, not dementia. The displayed range
is coefficient sensitivity, NOT a confidence interval. It is an interface/scenario demo.

**Continuous updates / NeuroCore**: source fingerprints and the latest ten of up to 100
stored source-revision events per participant, visible refresh every ten seconds, quality
and availability status, retries on subsequent refresh, and an offline candidate workflow.
No model is retrained or approved by polling. No claimed population drift detector runs
without a model and monitored cohort; active guard checks cohort/range compatibility.
Data are read sequentially, not as synchronized multimodal acquisition.

## Folder separation and persistence

- apps/neurotwin/backend: source adapters, identity links, state summaries and caches.
- apps/neurotwin/frontend: interface, MRI ray caster and surface renderer; no CDN required.
- apps/neurotwin/research: offline EEG preparation and progression training.
- apps/neurotwin/integrations: authenticated publisher and FreeSurfer output exporter.
- apps/neurocore/backend/neurotwin_monitor.py: update monitoring, not model approval.
- apps/neuroguard/backend/neurotwin_policy.py: independent forecasting evidence boundary.

Private data remain outside Git. SQLite adds nt_neural_records, nt_anatomical_records and
nt_refresh_events alongside V1 identity/source tables. All are participant-FK cascades.
Unlinking imaging immediately revokes inline anatomy access. Re-registering an anatomical
package for the same scan updates its derived reference; original private packages remain.
Waveforms/meshes are fetched on selection; polling reads summaries. Validated anatomy
metadata is cached by path/size/modification metadata and content hash; large geometry
has a bounded two-package cache. Changed/tampered packages fail closed.

## EEG preparation and publishing

Use **bainp-brain** with existing NumPy, SciPy and MNE. Do not automatically upgrade your
research environment. Supported API interfaces are documented in the source links below.
The script reads at most the first 60 seconds, up to 16 EEG channels excluding MNE bad
channels. It excludes nonfinite/BAD-annotation windows and heuristically flags >200 µV
peak-to-peak or <.1 µV SD. Four-second windows are filtered offline with zero-phase
Butterworth .5–30 Hz. Welch uses two-second Hann windows, 50% overlap and constant
detrending. Features average usable window/channel PSDs; powers integrate half-open
bins. Covariance averages usable window covariance. The replay is ONLY the first
contiguous usable window, resampled to about 128 Hz. Window-edge filtering and QC
thresholds are methodological limitations, not validated artifact separation.

```powershell
conda activate bainp-brain
python .\apps\neurotwin\research\prepare_eeg.py `
  --input "C:\path\authorized-recording.set" `
  --output "$env:USERPROFILE\BAINP_DATA\derived\neurotwin\prepared-eeg.json" `
  --record-id "verified-eeg-visit-001" --source-subject "verified-source-subject" `
  --observed-at "2026-11-01T10:00:00+05:30" --protocol "your-frozen-eeg-protocol-v1"
```

Preparation leaves consent/identity flags false. After independently verifying same-person
identity and authorization, publish to a real selected participant (substitute its UUID):

```powershell
conda activate bainp
python .\apps\neurotwin\integrations\publish_record.py `
  --participant YOUR_PARTICIPANT_UUID --mode active --type neural `
  --record "$env:USERPROFILE\BAINP_DATA\derived\neurotwin\prepared-eeg.json" `
  --identity-and-consent-verified
```

The publisher prompts privately for the existing operator code. It is loopback-only and
uses a session cookie plus the existing CSRF header. No secret is added to frontend code
or a URL. Remote/mobile acquisition requires separately engineered TLS, authorization,
clock transport and device permissions. A record labelled live is not independently
verified hardware by this prototype.

## Genuine regional anatomy

Existing OASIS candidate intensity classes are NOT hippocampal or cortical segmentations.
To display true supplied regional metrics, first produce/review suitable FreeSurfer outputs
in a supported FreeSurfer environment. This importer runs on Windows with nibabel and
reads already existing outputs; it does not install FreeSurfer or run recon-all.

```powershell
conda activate bainp-brain
python .\apps\neurotwin\integrations\prepare_freesurfer.py `
  --subject-dir "C:\path\reviewed-freesurfer-subject" `
  --scan-id VERIFIED_NEUROVISION_SCAN_ID `
  --input-mri-sha256 ORIGINAL_IMAGE_SHA256_FROM_NEUROVISION `
  --freesurfer-version YOUR_ACTUAL_VERSION `
  --review-reference "Your verified source MRI, visit and processing review reference" `
  --identity-and-visit-verified
```

It reads aseg.stats, lh/rh.aparc.stats and lh/rh.pial. Volumes convert mm³ to mL; thickness
remains mm. Surface coordinates remain FreeSurfer surface RAS. They are displayed as
surfaces, not silently overlaid in scanner RAS. FreeSurfer segmentation-grid volumes are
not relabelled as original native-grid voxel measurements. The output folder defaults to
BAINP_DATA/derived/neurotwin/anatomy (or NEUROTWIN_ANATOMY_DIR). The printed registration
JSON can be published with publish_record.py --type anatomy after verifying consent and
linking the same MRI identity in NeuroTwin. The image SHA must match the linked scan.
Regional histories are descriptive and excluded from fitted atrophy claims until matched
longitudinal processing/comparability has been established.

## Offline progression research

Use bainp-brain with existing NumPy and scikit-learn. Required CSV fields:

participant_id, cohort, index_date, followup_end_date, event_date, event_name,
baseline_state, baseline_mmse, age, education_years; optional death_date.

One baseline per globally resolved participant ID. Baseline state must be clinician-recorded
MCI. Event name must be clinician_recorded_dementia; dates must be ordered and observed.
Negatives require full 24-month event-free follow-up. Early censoring and competing deaths
are excluded, with counts/reasons retained. That complete-case selection can bias results;
this is NOT a survival model. Aliased identities require resolution by the data owner.
No NeuroCognition prototype score is substituted for MMSE.

```powershell
conda activate bainp-brain
python .\apps\neurotwin\research\train_progression.py `
  --cohort "C:\path\authorized-baseline-cohort.csv" `
  --external "C:\path\independent-external-cohort.csv" `
  --clinical-protocol "your-verified-mmse-protocol-v1" `
  --output "$env:USERPROFILE\BAINP_DATA\derived\neurotwin\candidates\logistic-v1"
```

A 75/25 participant split is fixed before scaling/model fitting. The exported model remains
the training-subset model; held-out/external participants are not included by a final refit.
No hyperparameter search or performance-based model selection is performed. It reports
AUROC, balanced accuracy, Brier score, log loss and calibration curves. Brier alone is not
a calibration proof. At least 40 eligible participants and ten per class are engineering
workflow bounds, not evidence of adequate scientific power. Bootstrap fits resample training
participants and provide conditional parameter-sampling uncertainty; they do not cover all
transport/model/outcome uncertainty. External evaluation is not automatic clinical approval.

No approval file is created by training. NeuroGuard reads a separately reviewed policy
from BAINP_DATA/local/neuroguard/neurotwin_policy.json (NEUROTWIN_POLICY_FILE override).
It requires an approved model SHA, reviewer/reference, expiration, calibration review and
matching approved cohort scope. Model bytes must be BAINP_DATA/derived/neurotwin/models/
reviewed_model.json (NEUROTWIN_MODEL_DIR override). The shipped policy example is disabled.
No web route can edit policy, train models or approve deployment. This application-level
separation is not OS process isolation; production hardening remains separate work.

## Authenticated API additions

All V1 NeuroTwin routes remain. New routes inherit operator authentication and mode/UUID
matching. Mutations require X-NeuroAccess-Request: 1.

- PUT /api/neurotwin/participants/{UUID}/neural-records?mode=active|demo
- GET /api/neurotwin/participants/{UUID}/neural-records/{record_id}?mode=...
- DELETE same neural-record route
- GET /api/neurotwin/participants/{UUID}/anatomy/{linked_scan_id}?mode=...
- PUT /api/neurotwin/participants/{UUID}/anatomical-records?mode=...
  body: package_sha256, identity_verified=true, consent_confirmed=true
- GET /api/neurotwin/participants/{UUID}/anatomical-records/{sha256}?mode=...
- POST /api/neurotwin/participants/{UUID}/scenario?mode=...
  body: optional hypothetical baseline_mmse, age, education_years (at least one)
- GET /api/neurotwin/demo-example?profile=control|impairment
- GET /api/neurotwin/demo-neural/{record_id}?profile=control|impairment
- POST /api/neurotwin/demo-scenario?profile=...&score=...&sleep=...

Clinical source-record observations may identify instrument (e.g. MMSE), age and
education_years (unit years). A Clinical record may include clinical_state and source_cohort.
These fields are operator/integration assertions, not diagnoses inferred by NeuroTwin.
Neural contracts enforce channel/sample bounds, finite values, quality consistency,
spectral frequency bounds and positive-semidefinite channel covariance. Exact retries
are idempotent, revisions increment by one, and source identity cannot change on revision.

## Validation and scientific boundaries

Run tests/verify_neurotwin.py in bainp (FastAPI TestClient also needs httpx).
Run tests/verify_research.py in bainp-brain for scientific dependency tests.
All supplied checks use temporary synthetic data. See tests/VALIDATION.md for actual results.
Windows PowerShell and full browser layout must be verified on the target machine.
No prospective clinical, cultural-equivalence or disease-model validation is asserted.

Authoritative method references:
- https://freesurfer.net/fswiki/LongitudinalProcessing
- https://adni.loni.usc.edu/quick-start-guide-asset/MRI_tables.html
- https://mne.tools/stable/generated/mne.io.read_raw.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
- https://mne.tools/mne-connectivity/stable/generated/mne_connectivity.spectral_connectivity_epochs.html
- https://scikit-learn.org/stable/modules/calibration.html
