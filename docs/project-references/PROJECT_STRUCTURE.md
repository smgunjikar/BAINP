# BAINP repository map

The Windows checkout is the source of truth. This is an incremental proposal; entries marked planned may not yet exist. Do not move or overwrite current research scripts or the running MRI pipeline.

- `apps/api/app/main.py` — existing FastAPI entry point and health endpoint.
- `apps/api/app/` — planned API routes, schemas and application modules as implementation grows.
- `apps/api/tests/` — backend tests.
- `apps/web/` — planned Next.js/TypeScript participant and clinician interfaces.
- `docs/project-references/` — these original design documents and this map.
- `docs/` — implementation, operational and decision documentation.
- `research/` — separate dataset-specific protocols and analyses: OASIS-2, PADS, LASI-DAD, EEG and others as feasible.
- `scripts/` — existing research scripts; retain existing names and paths.
- `data/manifests/` — permitted metadata and manifests; exclude private datasets and secrets.
- `data/synthetic/` — clearly labelled fictional demonstration data.
- `BAINP_DATA/` outside the checkout — existing raw and derived imaging data.

## Build order

1. Confirm `/health` and API documentation.
2. Define versioned assessment and session contracts; record language, timing, task version, accommodations and quality conditions.
3. Build an accessible synthetic assessment flow and persist observations.
4. Add a timeline, comparability/insufficient-data states and a synthetic CareLoop review.
5. Add separately labelled dataset-specific research demonstrations where access and time allow.

The proposed database, frontend, authentication, safety rules and clinical workflows are not established by the health endpoint. The prototype must not claim diagnostic validity or readiness for real patient data.
