# BAINP Research Expansion — 1.0.0

This is a tested source update, not a deployed change to your Windows installation.
It starts the requested expansion across cognition, access, voice, movement, EEG,
imaging and evidence. It does not complete the full competitor roadmap.

## Included, working functionality

- Administrator-only **Research studio**, accessible from the app sidebar and account navigation at `/#/research-lab`.
- Three original experimental NeuroCognition protocols: spatial sequence recall,
  respond-or-wait, and symbol–location learning. Instructions, practice controls,
  task-specific access confirmation, explicit storage consent, stop handling,
  versioned plans, server-calculated descriptive metrics and duplicate-finalization protection.
- A vision condition or glasses alone does not block these new protocols. They require
  confirmation that the actual stimuli and response controls are usable. This does
  not certify an accommodation or change existing NeuroGuard decisions.
- Guided reading with local microphone signal-level capture (duration, RMS, clipping).
  Raw voice is never sent to the server. The user reviews features before saving.
  Capture stops on tab/route navigation. No video capture or transcription.
- NeuroSense research analysis of regular accelerometer CSV samples: per-axis RMS,
  3–12 Hz oscillation peaks and relative spectral power, with timing/units checks.
- NeuroPulse research analysis of EEG CSV samples: per-channel descriptive band
  power, flat-channel flags, acquisition/reference metadata and input hash.
- A local NIfTI regional-volume tool for **existing anatomical label maps**, plus
  an authenticated JSON importer and metadata-gated descriptive comparison.
- Workspace and active/demo separation, immutable-through-API research records,
  authenticated history, JSON evidence export and audit events.
- Consistent cream/peach/black responsive research pages; cognitive stimulus styling
  is fixed by the new protocol rather than inherited from arbitrary theme settings.

These protocols are independent original implementations of general task families.
They do not reproduce licensed Creyos/CANTAB tests, scoring, norms or algorithms.
The six-trial sequence task and other forms are prototypes, not psychometrically
validated instruments. Their randomization does not establish alternate-form equivalence.

## Deliberate boundary

New records live in the already authorized account workspace, but **are not linked
or automatically promoted to participant assessments, NeuroTwin clinical series,
NeuroQuest recommendations or CareLoop cases**. The studio requires an administrator.
Existing participant flows continue to use their existing permissions and rules.
This protects participants while protocols undergo independent evaluation.

No Parkinson's/Alzheimer's classifier, seizure detector, sleep-stage model, facial
biomarker model, MRI segmentation model, vendor SDK or medical device certification
is included. Oscillatory motion is not a Parkinson's diagnosis. EEG features are not
Beacon-equivalent biomarkers. Regional volumes are not a diagnosis or normative score.
The local installation remains a research prototype, not an enterprise-security certification.

## Install on Windows

Prerequisite: the account-based app with **BAINP-Health** update applied. This installer
checks exact source hashes and refuses to overwrite a different version. Do not bypass
that check. No databases are packaged, overwritten or migrated by the installer.

1. Extract this ZIP so the folder is `C:\Users\DELL\OneDrive\Desktop\BAINP\BAINP-Research-Expansion`.
2. In the BAINP VS Code PowerShell terminal:

```powershell
conda activate bainp
Set-Location 'C:\Users\DELL\OneDrive\Desktop\BAINP'
python .\BAINP-Research-Expansion\Install-Research.py --project-root . --check
```

3. If compatibility passes, stop the existing BAINP backend and frontend using their
   existing terminal controls. Then install:

```powershell
python .\BAINP-Research-Expansion\Install-Research.py --project-root .
& '.\apps\neuroaccess\Start-NeuroAccess.ps1' -Service All
```

4. Sign in with your existing administrator account and open:
   `http://127.0.0.1:3000/#/research-lab`
   If cached scripts persist, hard-refresh once.

Signal analysis needs NumPy in the backend's environment. The separate MRI tool also
needs NiBabel. Use your existing installed imaging environment when possible. If missing:

```powershell
python -m pip install numpy nibabel
```

No third-party accounts or paid vendor integrations are configured.
For rollback, use the backup path printed during installation:

```powershell
python .\BAINP-Research-Expansion\Install-Research.py --project-root . --restore 'EXACT_BACKUP_PATH' --check
python .\BAINP-Research-Expansion\Install-Research.py --project-root . --restore 'EXACT_BACKUP_PATH'
```

Rollback restores source only; saved research records remain in the workspace database.

## Data formats

Movement CSV: `t,ax,ay,az`; seconds and m/s²; regular sampling 25–1000 Hz;
10 seconds minimum; 64–20000 samples; 700 KB frontend limit.
EEG CSV: `t,C3,C4` (your actual unique channel names); seconds and microvolts;
80–2000 Hz; up to 16 channels; same sample/size limits. Do not rename arbitrary sensor
values to EEG channels or change unit labels without converting the actual data.
The engineering jitter tolerance is 5%; this is not a clinically validated threshold.

MRI: run `tools/regional_mri.py --help`. Supply the source image, a same-grid
anatomical segmentation, and that segmentation producer's true label dictionary.
Input files are only read. Output is created exclusively; an existing output is not
silently overwritten. Millimetre units and aligned affines are required. Review
anatomical labels on the source scan outside this studio before interpreting volumes.
The comparison has no participant identity check, date-based annualization or atrophy
inference; it reports arithmetic differences only and says so in its output.

## Operational limits

- English-only new protocols. No translated-form equivalence is claimed.
- Task plans are retained, but task resumption is not implemented. An unfinished run
  stays started; start a new run. Stop records an aborted result when connectivity permits.
- Browser measurements are client-supplied, not remotely attested. Timings depend on
  hardware, browser scheduling, input device and tab visibility.
- History retains start and result records separately, pages 50 at a time, and exports
  individual JSON records. No delete or retention-job API is supplied in this release.
- JSON hashes aid reproducibility; they are not a digital signature or protection
  against someone with direct filesystem write access.
- Raw voice stays local. Raw CSV is sent to the local backend for analysis and discarded;
  features, metadata, source hash and provenance are retained.
- Protected admin review of another workspace still uses existing reason/password/audit
  controls. This update does not create new cross-account access permissions.
- No real headset, smartwatch, microphone hardware, patient MRI or Windows installation
  was validated here. Read VALIDATION.md for actual test scope.
