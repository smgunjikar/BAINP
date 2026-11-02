# EEG NeuroPulse research track

Initial study: OpenNeuro ds004504, 88 participants with resting EEG in disease and healthy groups. This is cross-sectional diagnosed-condition research, not evidence of presymptomatic detection. No model is clinically usable without further validation.

Proposed processing: BIDS validation -> MNE import -> sensor and reference checks -> bad channels + artifact QC -> eyes-closed comparable segments -> bandpower/relative power and basic complexity measures -> subject-held-out classification research -> uncertainty/calibration -> external cohort if available.

For future streaming, maintain a separate `source=recorded_replay|physical_device` flag and avoid claiming file replay is real device acquisition. See https://mne.tools/stable/ and https://mne.tools/mne-lsl/stable/ .
