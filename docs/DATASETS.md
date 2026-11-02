# Dataset access and scientific boundaries

| Source | Access in this project | Modality | Study permitted now? | Main limitation |
|---|---|---|---|---|
| OASIS-1 | User-accessible | Structural T1 MRI, clinical covariates | Local approved analysis | Cross-sectional, research-use restrictions |
| OASIS-2 | User-accessible | Repeated structural MRI, clinical variables | Local approved analysis | Small conversion subgroup; avoid outcome leakage |
| OASIS-3 | User reports access; verify dataset-specific permission | Longitudinal MRI, PET, clinical | Research-only if approved scope covers analysis | Image/clinical visit matching |
| OASIS-4 | User reports access; verify dataset-specific permission | Distinct clinical/imaging cohort | Research-only if approved scope covers analysis | Release-specific dictionary |
| PADS (PhysioNet) | Open access | Wrist accelerometry/gyroscope + clinical groups | After local acquisition | Not presymptomatic detection; split by person |
| OpenNeuro ds004504 | Public research | Resting EEG | After local acquisition | Cross-sectional diagnosed cases; small |
| ADNI | User reports ADNI access via LONI IDA; modality rights require DUA review | MRI/PET, biomarkers, cognition | Local approved analysis only | Access agreement, longitudinal missingness |
| LASI-DAD | Pending | India cognition, functional, health context | NO | Restricted access and adaptation |

Before analysis, record release, DOI, license and restrictions, checksum, source URL, acquisition date, column dictionary, cohort selection and allowable publication rules. Neither raw nor subject-level derived data belongs in the public GitHub repository. Official OASIS FAQ warns against combining OASIS-1/2/3, whereas OASIS-4 is distinct but still requires justification for any pooling.

Sources:
- https://sites.wustl.edu/oasisbrains/home/oasis-resources-and-faq/
- https://physionet.org/content/parkinsons-disease-smartwatch/1.0.0/
- https://openneuro.org/datasets/ds004504

## First ADNI acquisition and local QC

See [ADNI acquisition and QC protocol](ADNI_ACQUISITION_AND_QC.md). The local-only inventory tool lives in `research/adni/inventory.py`.
