# NeuroSignal ARENA and Platform Core v1

Install NeuroGraph and NeuroGuard first. From the BAINP folder with the
`bainp` Conda environment active, run `Install-ARENA-PlatformCore.ps1 -Verify`
and restart NeuroAccess. The front-page card opens both workspaces.

ARENA runs a fixed fictional NeuroGuard suite. It compares decisions against
shipped expectations and records protocol, evaluator and policy hashes. Results
include a qualification gate for this engineering suite. Release authorization
always remains false. The workspace also includes an aggregate rerun of the
frozen OASIS-2 clinical-only benchmark. It ships without cohort rows, scan files
or participant predictions. The existing NeuroGuard model policy remains the
authority for research model review.

Platform Core uses the current local operator session and SQLite store. It
provides service metrics, installed-source inventory, read-only NeuroTwin
model review status, a durable queue, cancellation of queued jobs and job
event history. A job claims a short lease. The next worker action recovers
expired leases with bounded retries, and stale workers cannot commit a result.
Jobs are processed by the operator buttons. Arbitrary commands, model training
and MRI or EEG processing are outside the web queue. Research evaluation runs
offline through the provided CLI tools. Telemetry is process-local and retains
counts and the latest response time without logging request bodies or paths.

## Offline fixed-horizon evaluation

From the BAINP folder:

```powershell
python .\apps\neurosignal-arena\tools\evaluate_binary.py "C:\Research\locked-bundle" --protocol-sha256 REVIEWER_PIN
```

A runnable fictional bundle is included. Its scores are constructed examples.

```powershell
$bundle = ".\apps\neurosignal-arena\examples\locked_binary"
$pin = (Get-Content (Join-Path $bundle "protocol.sha256") -Raw).Trim()
python .\apps\neurosignal-arena\tools\evaluate_binary.py $bundle --protocol-sha256 $pin
```

The independently reviewed bundle contains `protocol.json` and three CSVs.
Use pseudonymous, crosswalk-verified participant IDs, one row per participant.
Exact CSV headers:

```
split.csv: participant,split,index_at,latest_feature_at,label_available_at,label,group
fit.csv: model,stage,participant
predictions.csv: model,participant,probability
```

In `protocol.json`, set `schema` to `arena-binary-v1`. Include `dataset`,
`dataset_version`, `usage_reference`, `outcome`, integer `horizon_days`,
`evaluation_split` (test or external), ordered `models` entries with
`id`, `threshold` and `artifact_sha256`, and `file_sha256` with the
three filenames and byte hashes. The first model is the reference baseline.
Use the protocol hash pinned by an independent reviewer. Keep the protocol and
held-out outcomes outside model development access. The tool verifies content
integrity against the pin. It cannot establish who accessed the data.

Use timezone-qualified ISO 8601 timestamps. The label availability timestamp
is the earliest time the complete fixed-horizon outcome was ascertainable.
Declare every participant used for model fit, preprocessing and tuning. Fit
and preprocessing belong to training; tuning belongs to validation. Feature
cutoffs and fit declarations need external provenance review. Each model
must supply one probability per selected held-out participant. Training and
test data are never sent to a model by this evaluator.

The report includes AUROC, Brier score, sensitivity, specificity, calibration
bins and conditional paired participant intervals. Sparse subgroup results
are suppressed. Fixed-horizon results require observed binary outcomes.
Survival and censoring need a separate protocol. This CLI writes aggregate
JSON to stdout, omitting participant rows. It does not run a model.

## Reproduce the OASIS-2 result

Use an authorized local copy of the frozen clinical cohort. Verify the hash
of its analysis plan against the bundled aggregate report. The rerun validates
the input hashes in that plan. The research environment needs NumPy, pandas
and scikit-learn. Versions used for the bundled rerun are in the report.

```powershell
python .\apps\neurosignal-arena\tools\reproduce_oasis2.py --cohort-dir "C:\Research\frozen-oasis2" --output-dir "C:\Research\oasis2-rerun"
```

The output directory must be new and private. It includes row-level predictions
and fold audits. The dashboard uses only the separate aggregate summary.

## Backup and recovery rehearsal

Run locally on an authorized host. Choose a protected destination on encrypted
storage with appropriate OS permissions. The output contains application data.

```powershell
python .\apps\platform-core\tools\backup_sqlite.py --source "C:\Private\neuroaccess.sqlite3" --output-dir "C:\Protected\bainp-backup-001"
```

The command requires a new directory, makes an online SQLite snapshot, hashes
it and verifies an isolated restore. It covers SQLite only. The operator
credential, external artifacts, large files and ACLs need separate backup.
No live overwrite occurs.

Production deployment, distinct clinician and researcher roles, PostgreSQL
migration, protected object storage and external worker supervision remain
separate infrastructure work. The suite and the OASIS-2 result are engineering
and exploratory research evidence, respectively. They do not establish
clinical validity or comparative LLM performance.
