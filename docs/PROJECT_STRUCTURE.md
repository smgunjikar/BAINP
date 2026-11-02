# BAINP — Project structure and module registry

## Repository ownership and boundaries

`BAINP` is the top-level GitHub repository. Keep **one** VS Code workspace, with a web client, API, research experiments, data registry, documentation and tests. Existing internal engine names from the BrainSignal NEXUS planning discussions are preserved for scientific continuity.

| Directory | Purpose | Status |
|---|---|---|
| `apps/web` | Next.js patient/research/clinician UI | Starter source; dependency install pending verification |
| `apps/api` | FastAPI demo endpoints, assessment persistence, synthetic care cases | Verified in local tests |
| `research/adni` | Multimodal ADNI cohort and table inventory | Aggregate inventory script available |
| `research/oasis` | NeuroVision MRI and longitudinal image research | Inventory + descriptive script available |
| `research/pads` | NeuroSense motor/wearable study | Grouped-model baseline script available |
| `research/eeg` | NeuroPulse EEG recording analysis | Planned |
| `research/neuropulse` | Live or replayed neural stream integration | Planned |
| `research/neurotwin` | Experimental person-time state and uncertainty | Planned |
| `research/neurograph` | Versioned evidence connections | Planned |
| `research/neurosim` | Evidence-informed preventive scenarios | Planned |
| `research/arena` | Held-out evaluation, safety cases and fairness | Planned |
| `research/speech` | Language/acoustic biomarker work | Future research |
| `research/retina` | OCT and eye signals | Future research |
| `research/fnirs` | Optical neural-hemodynamic research | Future research |
| `research/biofluids` | Clinical biomarker associations | Future research |
| `research/genomics` | Authorized genetic context with specific consent | Future research |
| `research/brainbody_atlas` | Cross-modal biological links and temporal studies | Future research |
| `data/raw` | User-held licensed files (ADNI, OASIS, etc.) | Local only / ignored by Git |
| `data/synthetic` | Synthetic examples safe for source control | Fixture workspace |
| `data/manifests` | Non-identifying dataset-level inventories | Documented manifests only |
| `docs` | Specifications, safety, acquisition, dev instructions | Versioned |
| `.github/workflows` | Test automation on push/PR | Backend tests configured |
| `.vscode` | Editor configuration | Starter configured |

## Immediate engineering milestones

1. Clone `smgunjikar/BAINP`, extract project contents at repo root, push initial scaffold.
2. Run the FastAPI demo and 9 automated tests locally.
3. Use `research/adni/inventory.py` on locally authorized tabular files, and `research/oasis/inventory.py` on OASIS directories.
4. Improve the frontend and consent/access workflow before any live participant input.
5. Evaluate longitudinal and imaging research with no patient-level artifacts in Git.

## Clinical boundary

The current software is a *research and synthetic demo*, not validated medical software. The API is not production-authenticated. Never expose it to actual patients or real clinical identifiers. Experimental models, MRIs and consumer wearable signals are **not** a diagnosis of Alzheimer's, Parkinson's or any other condition.
