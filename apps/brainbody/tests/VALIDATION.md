# BBC-BE engineering validation

21 isolated API/storage/engine checks passed on temporary invented participant data:
authentication/CSRF, active/demo separation, consent scopes/withdrawal, source identity,
cross-module cohort/subject ownership, immutable amendments/retries, duplicate prevention,
assay/unit/specimen separation,
reference applicability, censored/absent values, three-clock replay, BP component review,
questionnaire provenance, molecular-source restrictions, genomic disclosure and review-note
privacy, legacy-wearable unknown clocks, deletion/cascade behavior, demo isolation and
NeuroTwin source refresh. Test fixtures are not actual patient records.

Three offline synthetic-cohort checks passed for baseline-vs-context evaluation,
training-fold-only preprocessing, future-availability/duplicate-ID rejection, fixed assay
contexts and physical-unit range validation. The reported synthetic errors are not evidence
of clinical accuracy or of improved prediction in an authorized real cohort.

The existing 15 NeuroTwin integration checks also passed after BBC-BE integration.
The installer was checked on a clean NeuroAccess baseline (BBC-BE independent of NeuroTwin)
and on the supplied NeuroTwin/NeuroVision-upgraded app. Authenticated NeuroVision import
worker, NeuroTwin and BBC-BE routes coexist. Repeating an unchanged installation changed
zero files. No private data directory was used in these checks.

JavaScript syntax checks passed for the new UI and patched navigation/Twin files.
A simulated DOM exercised source/assay panels, charts, temporal context, failed-save input
preservation, retry ID stability, escaped HTML reports, synthetic read-only controls and
preservation of the last display with a stale-data warning. This is not a full browser
layout/usability evaluation. Windows PowerShell execution, target browser layout and
real device/lab/EHR integration have not been verified here.

No clinical biomarker validation, prospective evaluation, questionnaire cultural-equivalence
study, regulation certification, real ADNI/OASIS/LASI-DAD analysis or deployed BBC-BE clinical
prediction model is claimed by this software validation.

For v1.1, the 21 core and three research checks passed again on the NeuroAccess and
NeuroTwin V2 fixture. The temporal test covers wearable records with known and unknown
availability. Simulated browser checks covered the session selector, exact session
handoff, unavailable session state, source links and session evidence in the HTML
export. Reapplying the installer changed zero files.

The verification compatibility fix ran all 21 core checks over loopback HTTP
with imports of `httpx`, `httpx2`, and the FastAPI/Starlette test clients blocked.
The installed suite uses the existing Uvicorn runtime, standard-library HTTP,
and temporary storage. This run used a Linux fixture.
