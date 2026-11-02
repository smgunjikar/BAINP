# BrainSignal NEXUS — ADNI acquisition, governance and QC protocol

**Status:** User reports ADNI LONI IDA access. This is a research-only local workflow, not evidence that every study/modality is separately authorized.

## 1. First download — tabular data, not the whole MRI archive

Use the official IDA data selector: `ADNI` -> `Search & Download` -> `Study Files` (or `Download` -> `Study Data`).

| Order | Data | Common examples | Goal |
|---|---|---|---|
| 1 | Dictionary | DATADIC + each table's methodology note | Decode variables, visit and missingness codes |
| 2 | Enrollment/visits | ROSTER, REGISTRY, VISITS | RID–PTID linkage, phases, timing |
| 3 | Diagnosis | DXSUM | Construct outcomes only at eligible dates |
| 4 | Demographics | PTDEMOG | Demographics, education and subgroup context |
| 5 | Cognition/function | MMSE, CDR, ADAS, FAQ where available | Repeated cognitive and functional observations |
| 6 | MRI QC | MRIQC | Select suitable series and image IDs |
| 7 | MRI numeric | UCSFFSX7, study-specific harmonized summaries | Begin quantitative morphology without massive DICOM transfer |
| 8 | Biofluid/PET | Select specific tables after auditing missingness | Test biomarker added value |

ADNI phases use different visit schedules, coding conventions, and overlapping participants. Preserve original filenames and release dates; refer to the dictionary for the version you actually downloaded. Official FAQ notes `-1`, `-4` and other phase-specific missing-value conventions.

## 2. Private local folders

```
data/raw/adni/clinical/   # raw CSV or zipped study tables
 data/raw/adni/mri/       # selected approved DICOM (later)
 data/raw/adni/pet/       # approved PET (later)
 data/derived/adni/       # locally generated outputs; do not publish
```

The repository ignores `data/**` by default except explicitly labeled templates. Keep data on an access-controlled machine and do not upload files/row-level extracts/subject-level derived records to third-party generative-AI platforms, GitHub or cloud services without verified permission under the DUA.

## 3. Cohort design for the first reproducible analysis

- Unit: participant `RID`; each individual can have multiple visits and phases.
- At baseline: define reference date, age, education, baseline cognitive measurements, baseline structural MRI measurement (if available), and optionally contemporaneous biomarkers.
- Follow-up: 12/24/36-month observations when available; use actual visit dates and prespecified windows.
- Primary research question: Do baseline MRI measures add **incremental** information to clinical and demographic baseline measurements for a prespecified later clinical outcome?
- Inference and selection: train/validation/test splits by RID; imputation and scaling learned only on training folds; temporal cutoff fixed in advance.
- Leakage prevention: do not use CDR to predict a label calculated from CDR and do not allow future cognitive/imaging values to leak into baseline features.
- Report: sample flow, missingness, calibration, class balance, AUROC, AUPRC, Brier score, sensitivity/specificity at prechosen operating points, confidence intervals and subgroup checks. Clinical interpretation remains investigational.

## 4. Relationship to other BrainSignal research

ADNI: Alzheimer's/MCI research across cognition, imaging, available fluid markers. OASIS: distinct imaging-focused research. PADS: wrist movement study. OpenNeuro EEG: separate recorded EEG study. Data from unrelated participants are never joined into synthetic multimodal 'real patients'.

## 5. Source of truth

- ADNI access and DUA: https://adni.loni.usc.edu/data-samples/adni-data/
- ADNI data user guide: https://adni.loni.usc.edu/quick-start-guide-asset/getting_started.html
- ADNI FAQ: https://adni.loni.usc.edu/help-faqs/faqs/
- LONI IDA support: https://ida.loni.usc.edu/explore/jsp/support/support.jsp

## 6. First milestone acceptance

Run `python research/adni/inventory.py --source data/raw/adni/clinical` locally on downloaded files. Confirm dictionary, enrollment, DXSUM and at least one cognitive score source. Record accessible date ranges and longitudinal participant counts **locally**. Do not start disease modeling until diagnosis definitions and missingness codes are checked.
