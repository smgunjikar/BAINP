# NeuroPulse pilot v0.1

Research software only. This release is a single-recording pilot, not a trained
clinical detector, benchmark winner, real-time acquisition service or validated
NeuroGuard decision engine. Keep this module separate from NeuroSense.

## Paths and environment
- Source: apps/neuropulse/backend/engine.py and backend/replay.html
- Launchers and documentation: apps/neuropulse/
- Local research data/reports: BAINP_DATA/derived/neuropulse, outside Git.
- Use bainp-brain. NumPy and SciPy are required; MNE is needed only for actual
  EEGLAB reading. Do not upgrade existing MRI dependencies automatically.

## Initial workflow
1. Inventory the root containing dataset_description.json and sub-*/eeg.
2. Verify inventory.csv, metadata/version and that data content is materialized
   rather than only DataLad pointers. Supplied derivatives are not mixed with raw.
3. Prepare one raw .set recording (24â€“120 seconds, default 60). Paired external
   .fdt content must exist. The engine preserves source files, hashes input EEG
   and sidecars, and records software/processing provenance.
4. Open the generated replay.html in a browser. Synthetic and authentic sources
   are labelled differently. Playback is a UI replay of precomputed results.
5. Review window_quality.json and features.json before scaling to all subjects.

## Signal methods and limits
EEGLAB import uses MNE; data passed into processing are volts. Source reference
is retained and must be checked in the BIDS sidecar. Causal 0.5â€“30 Hz Butterworth
bandpass, first 10 seconds excluded from spectral summaries. No notch is applied;
line noise assessment and reference comparisons remain follow-up work.

Four-second non-overlapping analysis windows. Welch PSD uses two-second Hann
windows, 50% overlap, constant detrending. Band powers integrate half-open bins
(0.5â€“4, 4â€“8, 8â€“13, 13â€“30 Hz); power units microvolt squared. Relative powers use
0.5â€“30 Hz total. Peak alpha is an unvalidated local-peak candidate exceeding
2x median alpha PSD, not a clinical metric. Spectral entropy is normalized by
log(number of PSD bins). Display-only anti-alias resampling to about 100 Hz.

Any channel >200 microvolt peak-to-peak or <0.1 microvolt SD flags its full
window; BAD annotation overlaps are excluded. These are explicit heuristics,
not validated separation of eye, muscle, movement, or electrode artifacts.
No ICA or repair. Flat data are not silently replaced. No full-recording claim
from a pilot segment. No group labels are used during feature extraction.

## Planned development after pilot verification
- Whole-recording feature extraction with cached immutable configurations.
- Channel-specific quality, line noise, EOG/EMG proxies, reference sensitivity.
- Participant-held-out evaluation, train-fold preprocessing/selection/tuning;
  age/sex/confounding and recording-quality baselines; no window-level leakage.
- Statistical channel covariance/coherence with reference/volume-conduction
  caveats; not anatomical connectivity or causal coupling.
- ERP only with appropriate task markers and a verified timing experiment.
- Independent NeuroGuard integration, uncertainty/abstention and evidence records.
- Live acquisition only after selecting EEG hardware, timestamp transport,
  dropped-sample detection, stateful chunk filtering and device tests.

PADS does not validate EEG models. This EEG cohort cannot support detection of
all brain anomalies, presymptomatic disease or general clinical deployment.

Official sources:
https://github.com/OpenNeuroDatasets/ds004504
https://openneuro.org/datasets/ds004504
https://mne.tools/stable/generated/mne.io.read_raw_eeglab.html
