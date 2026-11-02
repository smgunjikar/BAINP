# Sprint 01 — Working foundation

**Timebox:** 31 Oct–3 Nov 2026. **Goal:** reproducible full-stack app in VS Code, version-controlled and verified.

## Acceptance criteria

- [x] Git-ready monorepo and private-data `.gitignore`.
- [x] Synthetic-only typed FastAPI with SQLite persistence.
- [x] Seven fictional evidence/safety scenarios and deterministic response logic.
- [x] Experimental eight-trial attention task with stored raw trials and session history.
- [x] CareLoop status persistence and audit event model.
- [x] Back-end unit tests (6 API tests; verify in your own environment).
- [ ] npm dependencies installed and browser UI tested in your local VS Code environment.
- [ ] Private GitHub repo actually created and pushed by user/connected GitHub app.
- [ ] OASIS data inventory on user's local files; source files not yet supplied here.
- [ ] Professional clinical review of any warning/triage content before use outside synthetic demo.

## Implementation order for next sessions

1. Confirm local setup and API response.
2. Confirm Next.js browser test passes and re-open a saved session.
3. Inventory real authorized OASIS 1/2 files locally.
4. Expand task design, model trial-level QC and alternate-form comparability.
5. Add proper migrations (Alembic) and controlled synthetic account roles.
6. Implement OASIS-2 descriptive cohort table and QC plots without raw data disclosure.
7. Acquire and preprocess PADS for participant-held-out pilot experiment.
8. Add EEG replay source with provenance before physical-device acquisition.

## Demo success criteria

End-to-end: browser trial -> POST validation -> SQLite trial rows -> session history; fictional case -> deterministic status -> saved care follow-up, with audit log generated. This is **engineering** evidence, not clinical accuracy.
