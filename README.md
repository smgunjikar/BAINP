# BAINP

**BAINP — Brain-health research, sensing and clinical-workflow prototype**

> **RESEARCH / SYNTHETIC DEMONSTRATION ONLY**. This starter is not a regulated medical device and cannot diagnose, predict or treat neurological disease. Never enter identifiable patients or real clinical cases in the demo.

## Project status

- **Implemented**: FastAPI API; synthetic demonstration cases; a browser attention task with trial-level recording; local SQLite persistence; CareLoop mock workflow; API tests; ADNI file inventory; OASIS file inventory; exploratory tabular scripts; Next.js frontend source.
- **Planned**: MRI image segmentation, EEG replay/live-device input, actual wearable analysis, longitudinal forecasting, production authentication, population validation and regulated medical claims.
- **Data access**: Use your own authorized local copy of ADNI/OASIS. Never include raw/individual-level licensed data in this repository or upload it to a public AI service. Cohorts must remain scientifically separate unless the protocol and agreements explicitly allow linking.

## Launch locally (Windows PowerShell, VS Code)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
python -m pytest apps/api/tests research/adni/tests -q
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

Open [http://127.0.0.1:8000/demo](http://127.0.0.1:8000/demo), and browse API documentation at `/docs`.

Optional React frontend in another terminal:

```powershell
cd apps/web
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The Next.js build is **not yet verified in this artifact's generation environment**.

## Important documentation

- [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md) — canonical monorepo structure and module descriptions
- [`docs/BAINP_GITHUB.md`](docs/BAINP_GITHUB.md) — **connect to your existing private GitHub `smgunjikar/BAINP`**
- [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) — prior scientific architecture, engine descriptions and boundaries
- [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — data workflow, analysis and interpretation
- [`docs/SENSOR_PARAMETERS.md`](docs/SENSOR_PARAMETERS.md) — EEG, wearables and other signal parameters
- [`docs/DATASETS.md`](docs/DATASETS.md) and [`docs/ADNI_ACQUISITION_AND_QC.md`](docs/ADNI_ACQUISITION_AND_QC.md) — study access and provenance
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — sprint order and long-term research
- [`docs/CLINICAL_SAFETY.md`](docs/CLINICAL_SAFETY.md) — limits and human oversight

## GitHub safety

The **existing private** repo is `https://github.com/smgunjikar/BAINP`. Clone that repository first, then extract the *flat-root* BAINP starter ZIP inside the cloned folder. Do not create a second nested `BAINP` folder or run `git init` inside an already cloned repository. Before pushing, run:

```powershell
git status --short
python scripts/preflight_git.py
```

The preflight checks tracked and staged paths, but cannot guarantee that a file contains no sensitive information; inspect all staged changes yourself. Never push secrets, subject-level research files, MRIs, EEG recordings or clinical exports.
