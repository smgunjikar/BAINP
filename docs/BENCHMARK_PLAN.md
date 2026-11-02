# NeuroSignal ARENA — planned benchmarks

### A. Synthetic software and safety checks (working subset)

Test data-quality precedence, missing baseline, acute-warning override, functional concern override, care-status persistence and task-validation rules. Success is measured as code conformance to defined scenarios **not** sensitivity to a real disease.

### B. PADS wearable research

Target: documented recorded group in clinical data; determine a prespecified group contrast. 469 subjects with multiple sensor task segments. Split subject IDs before preprocessing or tuning. Stratify subject-level groups as practical. Baseline: standard-feature logistic regression; consider RF/XGBoost only after data audit.

Metrics: participant-level balanced accuracy, group-specific sensitivity/specificity, confusion matrix, uncertainty intervals, calibration if probabilities used. Perform ablations by task or sensor with same held-out split. Report cohort and device-specific limitations.

### C. OASIS MRI research

Target: anatomy, volume, cross-sectional groups, observed within-person change. Do not use CDR as predictor of a CDR-derived outcome. Use coherent time boundaries. Check whether OASIS-1 and OASIS-2 overlap; do not claim independence across releases.

Report QC pass rate, missingness, mixed-effects estimates with uncertainty. No unvalidated 'brain age' or preclinical prediction headlines.

### D. EEG research

Target: already diagnosed groups in ds004504 for exploratory comparisons, not early screening. Preprocess before splitting only using non-learned operations; learned normalization and feature selection on training folds only. Subject-held-out. Screen artifact/site confounds.

### E. Fairness, interpretability and prospective utility

Only claim local population performance when actual representative user data and a proper reference standard exist. Explore completion/comfort and subgroup-specific failure rates during ethically permitted usability testing. Formal diagnostic metrics require clinician-adjudicated outcomes. The research priority is demonstrating when additional sensors add valid information beyond simpler cognitive/functional baselines.
