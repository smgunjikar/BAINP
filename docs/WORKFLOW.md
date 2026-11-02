# Detailed workflow and ownership

## Step 1 — Data origin and consent

Inputs: authorized participant-generated demo task events; separate licensed research datasets. Store `subject_key`, `dataset_release`, `source_type`, `device`, `collected_at`, `task_version`, `units`, `permissions`, `quality_status`. In production, real identity, PII and consent must be isolated from research feature storage.

## Step 2 — Ingestion contracts

- Cognitive: timed trial `{session_id,trial_index,task_version,stimulus,response,response_ms,device,language}`.
- IMU: `{study_id,participant_id,task_id,hand,channel,unit,sampling_hz,timestamp,values}`.
- EEG: `{dataset_id,subject_id,session_id,montage,reference,channel_units,sampling_hz,source_type,artifact_qc}`.
- MRI: `{release,subject_id,scan_id,visit_days,modality,voxel_dimensions,protocol,derived_feature_version}`.
- Clinical context: schema-validated observation, origin, permission, reviewed-by when applicable.

## Step 3 — Quality assurance

Validate legal reuse and version -> duplicate subjects/sessions -> units / missingness -> temporal ordering -> modality QC -> reject/abstain on non-comparable data -> log data provenance. Clinical red flags must not be suppressed by a device quality error.

## Step 4 — Descriptive analyses

Raw scores and distributions first. Longitudinal comparison requires task comparability, repeat reliability, practice effects, missing data patterns and documented confidence intervals. No clinical thresholds until validated.

## Step 5 — AI experiment (research only)

Prespecify target and target population -> split by person and temporal structure -> leakage audit (CDR labels, subject overlap, scanner/site confounding) -> baseline model -> more complex model -> held-out evaluation -> calibration and subgroup checks -> version and model card. Never use research performance as live patient diagnosis.

## Step 6 — Explanation / care workflow

NeuroGraph builds source-backed summary. NeuroGuard may abstain. CareLoop records clinician decision and follow-up. A human can override but must record context. Urgent symptoms must go to appropriate professional/emergency support.

## Step 7 — Quantify value

Hackathon evidence: functional, repeatable software, demo case coverage, model experiments with honest limitations. Post-hackathon: reduction in inappropriate referrals, referral time, assessment quality and other patient/clinician outcomes under formal studies.
