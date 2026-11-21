# NeuroPulse X V3 P0 — Research operator guide (native BAINP)

## Operating contract

`python -m neuropulse_p0.cli COMMAND` from `BAINP` root with `conda activate bainp`.
All original EEG files reside in private `$HOME/BAINP_DATA/raw` and are read-only.
Derived outputs belong under `$HOME/BAINP_DATA/derived/neuropulse_v3`.
Neither EEG source files nor participant-identifiable data should go into Git.

## P0.1 — Audit live source (read-only)

```powershell
$root = 'C:\Users\DELL\OneDrive\Desktop\BAINP'
$derived = Join-Path $HOME 'BAINP_DATA\derived\neuropulse_v3'
Set-Location $root
python -m neuropulse_p0.cli audit-project --project-root $root --output "$derived\PROJECT_AUDIT.json"
```

The P0 audit checks known `apps/*` candidate directories and reports them; it
**does not claim full source discovery**, deployment integration, or valid APIs.
If your actual EEG backend is in a different module location, inspect the
repository tree before drafting a patch.

## P0.2 — EEG file inventory and hashes

```powershell
python -m neuropulse_p0.cli inventory --data-root (Join-Path $HOME 'BAINP_DATA\raw') --sha256 --output "$derived\EDF_INVENTORY.json"
```

Discovery supports `.edf`, `.bdf`, `.vhdr`, `.set`, `.fif` file extensions.
Processing in this P0 version supports **EDF only**. File names such as `S001R01.edf`
and `S001R02.edf` are dataset-specific, and eye-condition hints are unverified
until reconciled with approved dataset metadata. Inventorying an EDF is not
validating it.

## P0.3 — Analyze an approved EDF window

```powershell
$edf = '<ACTUAL_FULL_PATH_TO_S001R01.edf>'
$out = Join-Path $derived 'reports'
python -m neuropulse_p0.cli process-edf --edf $edf --dataset physionet_eegmmidb_v1 --subject S001 --condition eyes_open --duration-sec 60 --output-dir $out --data-use-authorized
```

Supply the correct real path and independently check the dataset license first.
For `S001R02.edf`, change the condition to `eyes_closed`.
Source SHA-256 is recorded; add `--expected-sha256 <HASH>` to enforce an inventory
hash match. For another EDF, set dataset, subject and condition from its own
source metadata, not assumptions.

Outputs: raw EEG channel count and sample rate, first-window read, nonclinical
amplitude/flatness heuristics, Welch PSD band powers in microvolts squared,
record provenance, and explicit restrictions. No automatic QC pass.

## P0.4 — CHB-MIT external annotations

```powershell
$chb = '<ACTUAL_FULL_PATH_TO_chb01_03.edf>'
$summary = '<ACTUAL_FULL_PATH_TO_chb01-summary.txt>'
python -m neuropulse_p0.cli process-edf --edf $chb --dataset chbmit_v1 --subject chb01 --condition clinical_continuous --start-sec 2980 --duration-sec 80 --chb-summary $summary --output-dir $out --data-use-authorized
```

Reference annotations are read from human-supplied summary data. This is **not
seizure detection**. The summary should be obtained from the same verified
CHB-MIT release as the EDF. Label file integrity is tracked separately.

## Descriptive same-subject comparison (not disease progression)

```powershell
python -m neuropulse_p0.cli compare-baselines --eyes-open-report '<PATH_TO_EO_JSON>' --eyes-closed-report '<PATH_TO_EC_JSON>' --output "$derived\S001_EO_EC.json"
```

Requires same dataset subject, matching channel names and sampling frequency.
The ratio describes different eye conditions. It must NOT be called a longitudinal
brain-health change or clinical deterioration.

## Boundaries and next integration gate

This is a research P0 CLI in the same repository and `bainp` environment. It
**is not yet reachable through the NeuroContinuum/NeuroQuest UI** and does not
produce patient-facing clinical recommendations. Before creating frontend/API
integration, gather the existing routes, Pydantic models, database schemas,
NeuroGuard logic, authentication/consent implementation, and test coverage.

Do not modify the live app by inserting guessed import paths. Map and test the
real data contract first. Keep research EEG subjects separate from patient IDs.
