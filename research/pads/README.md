# PADS NeuroSense research track

PADS on PhysioNet includes smartwatch motion data and questionnaire responses from 469 individuals, collected in structured tasks. It is cross-sectional and cannot validate preclinical prediction. Keep `participant_id` grouped across all train/validation/test splits to prevent leakage.

Research steps: local download -> file manifest -> check sensor units/sample rate and tasks -> per-task features -> participant-held-out baseline -> confusion matrix, balanced accuracy, CI -> missing-data/device-robustness experiments. Use `participant_heldout_baseline.py` on a prepared `participant_id,recorded_group,<numeric features>` CSV.

Source: https://physionet.org/content/parkinsons-disease-smartwatch/1.0.0/
