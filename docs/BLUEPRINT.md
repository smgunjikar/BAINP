# Master Blueprint — BrainSignal NEXUS

Version: 1.0 | 31 Oct 2026 | Hackathon submission target: 20 Nov 2026

## North star

Recognize potentially meaningful changes in cognitive/functional health earlier, compare observations under known conditions, integrate relevant consented physical/metabolic/sleep/wellbeing/family/genomic context, explain uncertainty and support appropriate qualified clinical action. It is a *signal-to-care* platform, not an Alzheimer's detector or general disease prediction device.

## Two distinct operating contexts

### DEMO/CLINICAL-WORKFLOW CONCEPT (synthetic-only today)

```
Fictional participant -> consent-design -> age/language/accessibility context
  -> experimental digital cognitive tasks + function reports
  -> stored versioned observations
  -> NeuroGuard (acute symptoms take precedence; technical QC; abstention)
  -> descriptive longitudinal changes + context
  -> evidence-labeled explanation -> human review -> care action/status
```

Raw imaging and EEG outputs NEVER drive automatic care routing in the prototype.

### SCIENTIFIC RESEARCH TRACKS (separate actual cohorts)

```
OASIS-1 [authorized] --> MRI QC & anatomy --> cross-sectional structural analysis
OASIS-2 [authorized] --> MRI + tabular QC --> longitudinal structural/clinical research
PADS [public]       --> IMU QC -> task features --> participant-held-out condition classification
EEG ds004504        --> BIDS/MNE -> spectral features/QC --> held-out disease-group comparison
OASIS-3/4 [pending] --> no ingestion until verified permissions and data dictionaries
```

No synthetic fusion of unrelated participant records presented as a real individual. A common software dashboard may render independently labeled studies.

## 10 product engines

| Engine | Ingestion | Main algorithms | Output | Prototype state |
|---|---|---|---|---|
| NeuroCognition | Task trial events, functional answers | Transparent scores, repeatability checks | Task logs and descriptive history | One working 8-trial demo task |
| NeuroAccess | Language, device, literacy, hearing/vision accommodations | Comprehension checks and version comparability | Assessment accessibility flags | English interface only |
| NeuroSense | PADS IMU, optional future watch/ring | Signal cleaning, motion features, grouped ML | Research motor pattern features | Existing grouped baseline script |
| NeuroPulse | EEG/ear-EEG; future ECG/PPG/fNIRS | EEG artifact removal, PSD, event-related responses | Research neural features; future streams | Protocol only |
| NeuroVision | OASIS MRI and derived tabular measures | Scan QC, segmentation, registration, descriptive analysis | Anatomical measurements & changes | Local inventory and tabular summary |
| NeuroTwin | Matched within-person longitudinal data | Mixed effects, change-point modeling, predictive intervals | Experimental state/history | Planned, no trained model |
| NeuroGuard | Source quality, context and warning information | Deterministic precedence and abstention | Evidence status, human-review flags | Synthetic rule demonstration |
| NeuroGraph | Vetted evidence, provenance, recorded facts | Typed relations, provenance retrieval | Evidence summary / known unknowns | Planned |
| NeuroSim | Prevention guidelines and known context | Educational decision support | Plain-language actions | Planned |
| CareLoop | Clinician-reviewed concerns, appointments | Status workflow, audit | Appropriate follow-up tracking | Synthetic care status working |

## Foundational entities / intended schema

Participants -> consent grants -> assessment sessions -> raw task trials -> derived observations -> QC events -> longitudinal analysis/version -> evidence passport -> care review -> action tasks -> audit.

Research datasets have a **separate** provenance manifest and permitted-use boundary. Only aggregate research outputs can flow into public demonstrations if license/approval permits and disclosure risk is checked. Never store identifiable records in the prototype DB.

## OASIS study programme

1. OASIS-1: cross-sectional brain morphology, education/age covariates and scan reliability. No prospective prediction claims.
2. OASIS-2: session ordering, yearly change in MRI-derived measures, clinical trajectories, subject-level split and no CDR definition leakage.
3. Scan quality: preserve scanner protocol, slice thickness, site, preprocessing software/version, image QC; compare longitudinal changes only after compatible registration.
4. Models: transparent covariate-adjusted statistical baselines before deep learning. OASIS-2 has too few converters for a strong standalone clinical conversion classifier.
5. Authorized OASIS-3/4 access is not assumed. Review official FAQ before combination; OASIS-1/2/3 overlap issues.

## Wearable PADS study programme

- Source: two wrist devices, movement tasks, accelerometer/gyroscope, clinical groups; 100 Hz on described task recordings. Cross-sectional groups, not at-home presymptomatic longitudinal outcomes.
- Participant grouping in all splits (even if multiple movement tasks per participant).
- Metrics: balanced accuracy, sensitivity/specificity for prespecified class contrasts, confusion matrix, calibration, 95% confidence intervals, missingness, alternate-device robustness.
- Never interpret a motion classification as a diagnosis without independent clinical validation.

## EEG NeuroPulse programme

- Import OpenNeuro ds004504 (eyes closed; case/control cross-sectional dataset) with BIDS/MNE; check montage/reference/artifact and channel quality; compute spectral features and subject-held-out baselines.
- Streaming contract: source type (real hardware vs replay), timebase, montage, sample rate, units, channel QC, electrode/reference configuration, timestamp jitter, artifact burden.
- Future ear-EEG and fNIRS are research extensions; cannot infer oxidative stress from ordinary EEG.

## Prevention and safety

- No universal combined 'neurological disorder probability'. Risk factors are not measured cognitive decline; observed changes are not diagnosis.
- Report separately: (a) recorded facts, (b) reproducible descriptive changes, (c) research associations, (d) uncertain hypotheses, (e) clinical assessment needs.
- Urgent symptom guidance overrides any reassuring sensor number. Actual triage logic requires clinician governance and validation; current code is a synthetic demonstrator.
- Family-history/genomic data are optional and tightly access-controlled in future product; no automatic genetic predictions.
- No LLM-directed emergency triage or autonomous medical recommendations.

## Regulatory/security trajectory

Before real patient data: threat model, independent security review, privacy notices, informed consent, data retention/deletion, professional authentication, role-based authorization, encryption, audit, monitoring, lawful data processing, regulated-software evaluation and clinical study governance. Start with synthetic-only demonstration so no person is exposed to experimental outputs.

## Proposed performance evaluation

- Engineering: API tests, unit tests, CI, persistence, response-time distribution, schema migration and attack tests.
- Cognitive measurement: task completion, practice effects and prospective reliability with permission/ethics; not clinical utility yet.
- Research algorithms: participant/site-held-out metrics, confidence intervals, calibration, robustness and failure analysis.
- Clinical outcomes (future): independently adjudicated meaningful change, sensitivity/specificity, false-referral burden, time to care and disparities in language/age/education groups.

## Roadmap

Hackathon: deploy synthetic full-stack workflow and credible independent OASIS/PADS/EEG analyses (as time and access allow). Future: longitudinal cohorts, wearables live interface, clinical pilot, regulated deployments, research-grade probabilistic NeuroTwin, ethically approved federated collaboration and optional oxidative-stress biomarker R&D **only after** chemical specificity and clinical relevance have been established.
