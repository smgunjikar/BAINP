# NeuroVision: OASIS MRI research

OASIS-1 and OASIS-2 currently accessible to project owner. OASIS-3/4 access reported; verify authorized releases and files locally. Follow the specific releases' documentation and research-use conditions. Do not combine OASIS-1/2/3 indiscriminately; check potential cohort overlap and official OASIS FAQ. No subject-level files or derived metrics in git.

**Start:** `python research/oasis/inventory.py --source data/raw/oasis2`

**Tabular descriptives:** `python -m pip install pandas` then `python research/oasis/oasis2_descriptive.py --input "path/to/authorized_oasis2.csv"`

Studies:
- OASIS-1: cross-sectional structural imaging and covariates; investigate processing and site/bias limitations.
- OASIS-2: true within-subject longitudinal MRI and clinical changes; model visit ordering and irregular intervals; protect against CDR definition leakage.
- OASIS-3 and OASIS-4: inspect authorized releases and file inventory before creating import contracts.

Future pipeline: NIfTI/Analyze conversion -> structural QC -> FastSurfer/SynthSeg -> derived quantitative regions -> mixed-effects models -> research viewer with segmentation QC and limitations.
