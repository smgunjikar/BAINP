# BAINP implementation map and release gates

All workstreams are started in one programme; they are not all scientifically complete.
A credible advantage must be measured. No claim that competitors cannot match BAINP
is supported by the available evidence.

| Workstream | Implemented in this package | Next engineering step | Evidence gate |
|---|---|---|---|
| NeuroCognition | Three original tasks, experimental protocols, descriptive server scoring | Complete task catalogue, protected launch tokens, language variants, supported resume and task-specific repeats | Test–retest and alternate-form evaluation; practice/device effects; validity in intended population |
| NeuroAccess | Explicit per-task visual/input usability, navigation-versus-answer assistance, practice | Integrate authoritative participant accommodations with task metadata; hearing-aware routing; supported languages | Accessibility usability study; do not infer visual acuity from a checkbox |
| NeuroQuest | Existing clinical selection untouched | Registry eligibility and stopping rules; match every recommendation to an executable protocol | Compare against fixed battery without unacceptable missed concerns |
| NeuroContinuum | Entry from account-based app | Complete existing onboarding–preparation–assessment–results path; state and consent refresh; no dead ends | Returning users, declines, edits, failed and interrupted runs |
| Guided multimodal / Modality pattern | Structured reading and local audio signal-quality measurements | Consented recordings, prompt versions, transcript alignment, speaker/language checks; separately optional camera module | Acoustic/face feature validity, device/language/subgroup performance; licensed integration or independent model research |
| NeuroSense | Timestamp/unit checks, per-axis movement spectrum | Verified Gear Sport adapter, capture protocol, placement calibration, medication/activity context; curated motor study datasets | Technical measurement validation, labelled clinical reference, participant-held-out and external validation before disease claims |
| NeuroPulse / Beacon pattern | EEG CSV quality and descriptive band features | BIDS/EDF integration, channel/reference/impedance metadata where available, artifact review, acquisition adapters, event synchronization | Independent annotated data and external evaluation before sleep staging, ERP or seizure claims |
| NeuroVision | Existing-label volume quantification, provenance import, guarded arithmetic comparison | Qualified segmentation pipeline, overlay review, scanner/protocol consistency, study identity and timestamps; export adapters | Anatomical ground truth, segmentation/volume error, repeatability and external-site evaluation |
| NeuroTwin | Research history separated from participant trends | Explicit reviewed-observation promotion; comparability groups; missing-data and practice-effect display | No pooling until comparability is supported; distinguish measured values from forecasts |
| NeuroProof / NeuroGraph | Source hashes, protocol versions, exported research records | Reviewed evidence passport; input/output chain, supporting and contradictory sources; reviewer identity | Reproducibility and evidence-link checks; hashes alone are not tamper-proof storage |
| NeuroMimic | No new clinical rules | Structured contributor context and provenance for medication, sleep and other reported conditions | Clinician-reviewed rules and uncertainty; missing laboratory values never become normal/abnormal |
| CareLoop | Existing case system unchanged | Explicit assigned/recommended/requested/delivered/acknowledged/completed states; real delivery adapter and receipts | End-to-end handoff receipt and failure handling; local record must not imply contact |
| NeuroCore / ARENA | New API, numerical and browser tests | Release registry, independent evaluation sets, rollback/incident monitoring | External validation, leakage checks, reproducible evaluations and authorization regression |
| Account security | Reuses existing isolated workspace boundary, admin review and audit | Verified email/phone provider, MFA, hardened deployment, encryption/key management, backup restore and independent review | Threat model and penetration testing; no enterprise-ready claim based on unit tests |

## Imaging implementation strategy

Cortechs.ai NeuroQuant, Combinostics cMRI and Neurophet AQUA/AD/PET are references
for workflows, not public model weights. Choose explicitly between a licensed vendor
integration (requiring access and commercial permission) and independently evaluated
research software. No vendor endpoint or SDK is invented in this release.

Start with 3D T1 regional measurement using a chosen, versioned segmentation pipeline.
Your existing OASIS work can support that research, subject to data-use terms and
participant-level separation. MRI readability and successful rendering do not establish
segmentation accuracy. Do not reuse repeated scans from the same participant across
training and test splits.

FLAIR lesion analysis, T2*GRE/SWI susceptibility findings and PET tracer-dependent
quantification require their actual input sequences and separate pipelines. T1 data
cannot substitute for all of these. Normative percentiles require a suitable, licensed
reference cohort and out-of-sample evaluation. Do not label OASIS alone a universal
reference population. No ARIA treatment-management capability is supplied.

## Movement and Parkinson's

The current deliverable measures oscillation, not disease. A Parkinson's programme
needs defined outcomes, clinical labels, medication state, rest/postural/action tasks,
placement and device checks, confounder handling and external evaluation. Other causes
of shaking cannot be differentiated from an FFT peak alone. Never add a percentage
label until a properly specified and calibrated model has been evaluated.

## Competitor references checked on 16 November 2026

These are manufacturer descriptions except the explicitly linked FDA document.
They establish product descriptions, not head-to-head superiority or reproducible
access to proprietary algorithms.

- Cortechs NeuroQuant: https://www.cortechs.ai/neuroquant/
- FDA NeuroQuant device description / intended use: https://www.accessdata.fda.gov/cdrh_docs/pdf24/k241098.pdf
- Combinostics reports: https://www.combinostics.com/reports/
- Neurophet AQUA: https://www.neurophet.com/en/solutions/aqua?tab=2
- Neurophet AQUA AD: https://www.neurophet.com/en/solutions/aqua-ad?tab=2
- Neurophet SCALE PET: https://www.neurophet.com/en/solutions/scale-pet
- Beacon: https://beacon.bio/life-sciences-products-services
- Modality.AI: https://modality.ai/
- Creyos accessibility: https://creyos.com/blog/accessible-patient-experience
- Creyos health equity: https://creyos.com/blog/cognitive-tests-and-health-equity
- Linus assessments: https://linushealth.com/our-assessments
- neotiv validation: https://neotiv.com/en/validation
- Koneksa: https://www.koneksahealth.com/koneksa-platform/
- Empatica research/clinical distinction: https://www.empatica.com/care/
- Kinesia device validation: https://www.glneurotech.com/products/validated-devices/

The most defensible product target is a lower-burden, accessible, reliable journey
with inspectable measurements and confirmed follow-up. Measure task completion,
measurement repeatability, authorization failures, missing data and actual handoffs
before claiming a competitive advantage.
