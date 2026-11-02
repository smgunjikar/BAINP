# Continuation guide — what to do in the next coding session

**Step 1:** Download/extract v1.1, open root folder in VS Code. Verify Python, Node, npm and Git. Start FastAPI using README commands.

**Step 2:** Confirm http://127.0.0.1:8000/demo works. Complete eight trials, refresh and check saved session. Change a fictional CareLoop status, refresh to confirm SQLite persistence.

**Step 3:** In terminal run `python -m pytest apps/api/tests research/adni/tests -q` (9 tests expected). All should pass. Record output/version.

**Step 4:** Install Next.js dependencies locally under `apps/web`, run `npm run dev`, and check http://localhost:3000. Its actual UI build has **not** been verified in the generation environment because npm dependency installation timed out.

**Step 5:** Initialize Git and push a **private** repo using `docs/GITHUB_SETUP.md`. Verify `git status` excludes `data/raw` and `.env.local` before push.

**Step 6:** Create local folders `data/raw/oasis1` and `data/raw/oasis2`; move authorized source data there. Run the local inventory script and report only aggregate results. Never commit or upload raw data publicly.

**Step 7:** Tell the assistant the exact column names/file formats, Python version, console errors (if any), and which of OASIS-1/2 imaging/table files are present. Use this to build the next verifiable analysis pipeline.

**Coding priorities:** first actual MRI tabular QC and OASIS-2 longitudinal analysis; then PADS movement features; finally EEG replay and scalable domain APIs. No promise that all future roadmap items already run.

**ADNI step:** User reports access to ADNI. See `docs/ADNI_ACQUISITION_AND_QC.md`. Download approved clinical tables directly through IDA to `data/raw/adni/clinical` and run `python research/adni/inventory.py --source data/raw/adni/clinical`. Do not upload participant-level ADNI data.
