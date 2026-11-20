# NeuroPulse research workspace

Open **NeuroPulse EEG** on the BAINP home page. Active mode plays a CC0 public
EEG excerpt or a replay JSON selected locally in the browser. Demo mode uses
generated waveforms. Active playback is prerecorded. Research results describe
cohorts and are kept separate from individual records.

## Local download and benchmark

Use the existing bainp-brain environment with Python 3.11+, NumPy, SciPy and
scikit-learn. MNE is optional for embedded MATLAB v5 EEGLAB input and required
for other EEGLAB variants. Leave raw data and local reports outside Git.

```powershell
conda activate bainp-brain
$raw = Join-Path $env:USERPROFILE 'BAINP_DATA\research\on004504-v1.0.0'
$run = Join-Path $env:USERPROFILE ('BAINP_DATA\derived\neuropulse\run-' + [guid]::NewGuid())
python .\apps\neuropulse\tools\download.py $raw
if ($LASTEXITCODE -ne 0) { throw 'EEG download failed. See the error above and rerun to resume.' }
python .\apps\neuropulse\tools\train.py $raw (Join-Path $run 'benchmark.json')
if ($LASTEXITCODE -ne 0) { throw 'EEG benchmark failed. See the error above.' }
$set = Join-Path $raw 'sub-002\eeg\sub-002_task-eyesclosed_eeg.set'
python .\apps\neuropulse\backend\engine.py prepare --recording $set --seconds 32 --out (Join-Path $run 'replay')
```

For a bounded run, pass `--limit-per-group 10` to both download and train.
The download uses the NEMAR CC0 mirror v1.0.0, derived from OpenNeuro
ds004504 v1.0.9. It downloads participants and dataset metadata and the raw
embedded .set recordings. Allow several GB for the full download. The cached
recordings remain local. Use the matching replay.json in the Active viewer.

The baseline uses the first 60 seconds, excludes a 10-second filter warmup
and uses 4-second windows. Heuristic per-channel amplitude and flatness
checks retain windows with at least ten usable channels. Three windows are
required per participant. The viewer retains the pilot's stricter
all-channel rule. Participant-level spectral medians feed a fixed logistic
model with fold-local scaling. Five participant-stratified folds compare
against the majority baseline. QC was revised after an initial dry run
showed the strict viewer policy excluded entire groups. Results are
exploratory. QC exclusion, recording protocol, age, and site may confound
the result. This run does not establish external generalization.

## Independent dataset tracks

| Track | Source and scope |
| --- | --- |
| AD / FTD / control | [NEMAR on004504](https://nemar.org/dataset/on004504). Implemented download, benchmark and replay. |
| Parkinson’s disease | [OpenNeuro ds002778 v1.0.5](https://openneuro.org/datasets/ds002778/versions/1.0.5). Download from the snapshot. Keep medication visits from each person in one fold. |
| Clinical abnormality | [Temple TUAB](https://isip.piconepress.com/projects/nedc/html/tuh_eeg/index.shtml). Requires access approval. Clinical normal/abnormal labels define a separate task. |
| Depression | [Mumtaz Figshare deposit](https://doi.org/10.6084/m9.figshare.4244171.v2), [NEMAR BIDS version](https://nemar.org/dataset/nm000114). Match resting conditions and group by participant. |
| Schizophrenia | [RepOD resting-state EEG](https://doi.org/10.18150/repod.0107441). Evaluate ERP separately using a task dataset with verified event markers. |

The four additional tracks have separate access and format requirements. This
release does not fit or pool them. It does not contain a live device adapter.

## Faster model research

Compare a frozen EEG encoder with a small linear probe against this baseline
on identical participant splits. [MIT SeqCLR](https://www.media.mit.edu/publications/contrastive-representation-learning-for-electroencephalogram-classification/)
and [EEGPT](https://proceedings.neurips.cc/paper_files/paper/2024/hash/4540d267eeec4e5dbd9dae9448f0b739-Abstract-Conference.html)
are relevant EEG representation methods. Before evaluating weights, verify
license, pretraining-cohort overlap, channel mapping, and sample-rate rules.
If overlap cannot be ruled out, evaluate on a genuinely independent cohort.
GPU acceleration is optional for the baseline. No NVIDIA or MIT checkpoint
is bundled.
