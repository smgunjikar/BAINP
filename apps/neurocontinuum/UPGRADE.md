# NeuroContinuum continuity update — 16 November 2026

## Scope and baseline
Built against the neurocontinuum.zip uploaded in this conversation. This is an incremental engineering update, not completion of every feature in the BAINP masterplan. All installed writes are inside apps/neurocontinuum. The host authentication, scientific engines and databases are not replaced.

## Implemented changes from the uploaded version
- The main monitoring dashboard now reads the existing server next-action endpoint and displays one prominent recommendation. Clicking it fetches a fresh decision, including current consent and the existing assessment safety checks.
- Saved assessment URLs are no longer directly exposed as executable dashboard links. Participant assessment buttons also refresh eligibility before navigating. The assessment service remains responsible for authorization at execution time.
- Monitoring preparation selection lists only completed check-ins matching the current profile revision. No eligible preparation produces a clear explanation and a working preparation link, not an empty select. The backend continues to enforce all check-in gates.
- Participant home/onboarding runs at /neurocontinuum?experience=participant using the existing /neurocontinuum.js and /neurocontinuum.css assets. No new host asset registrations or import dependencies are required.
- The participant API is mounted once at /api/neurocontinuum/v1/participant-home, under the host account middleware's existing NeuroContinuum namespace. The old standalone /api/participant-home/v1 namespace is no longer registered by this implementation. External clients of that old API must update.
- Onboarding storage, version checks, explicit none/deferred accessibility answers, native consent checks and ordered mandatory steps are retained. Participant login delegates to /#/signin; it no longer offers a misleading operator-code login.
- The dashboard and participant experience share cream surfaces, peach highlights, dark buttons, readable controls, responsive layouts and focus styles. CSS is scoped per experience. Decorative visuals use CSS, with no remote image dependencies.
- A timeline shows actual saved workflow updates and CareLoop case updates. It is not a medical measurement trend or an immutable event log.
- CareLoop cases are hidden from both workspace responses when workflow consent or case-tracking permission is absent. A case is explicitly distinguished from confirmed external delivery.
- Session-history links select the requested session. The sole available profile is selected automatically in the main dashboard. Only profiles returned by the host API are used.
- Pending mutations are no longer restored from a global browser-storage key after changing accounts. In-page retry preserves the operation ID. A full reload retrieves canonical server state; it does not replay a cached mutation automatically.
- Build script compiles both local experiences into the existing served assets using the Python standard library. No npm install is required to run the app.

## What is preserved
The native session state machine, idempotency rules, optimistic concurrency, scoring, NeuroQuest task selection, NeuroGuard safety authority, source-quality checks and evidence export are preserved. Original source measurements and user records are not rewritten. The existing onboarding table is initialized if missing.

## Integration boundaries and remaining work
| Requirement | Status / remaining dependency |
|---|---|
| Private accounts, administrator access and demo isolation | Host services enforce these; regression tested against the available account-enabled host snapshot, not a complete audit of the user's installed host. |
| First page and sign-in redesign | Outside this folder; this update delegates to existing host sign-in. |
| Automatic return from completed cognitive task | The available cognition.js hard-codes return to the main #/journey route. Changing that callback requires an external NeuroCognition/NeuroAccess edit. Return to NeuroContinuum manually to synchronize results in this folder-only update. |
| Vision accommodation eligibility | Actual policy lives in NeuroQuest/NeuroAccess. This update does not bypass it or remove a genuine limitation. Corrected eyesight versus unsupported task accommodations requires review in those engines. |
| New validated cognitive tasks / Micro, Core, Extended selection | Existing registered capabilities only; task protocols and registry changes belong to NeuroCognition/NeuroQuest. |
| MRI segmentation, EEG interpretation, movement disease detection, speech analysis | Not implemented by this orchestration update. Require engine-specific implementation, data, licensing where relevant, and scientific validation. |
| Combined clinical timeline and comparable longitudinal change | Current timeline is workflow/case metadata only. Modality contracts, quality and comparability remain separate work. |
| NeuroProof Evidence Passport | Existing workflow evidence export retained; no new certification or signed archive claimed. |
| Care delivery, appointments, reminders | No provider or messaging integration added; no fabricated appointment dates. |
| Caregiver access / interoperable clinical records | Requires delegated authorization and external integration contracts. |
| Safety holds | Retained; no automatic clearing of historical safety holds. A reviewed resolution lifecycle is still needed before changing that policy. |

## Verification performed
- 26 existing workflow integration tests passed against a reconstructed older host and temporary fictional records.
- 17 new account/onboarding HTTP assertions passed against the available account-enabled host: unauthorized access, cross-account access, demo access, duplicate intent, stale write, mandatory order and explicit none.
- Existing account regression suite: 88 HTTP checks plus concurrent isolation, persistence, token-storage and audit assertions passed.
- Five JSDOM behavior scenarios passed: empty preparation, current completed selection, changed consent before launch, host login, participant rendering. Bundled CSS parsed without errors.
- Real loopback host HTTP asset test passed for both experiences and all injected/script/style assets.
- JavaScript syntax checks passed.
- These are engineering tests with synthetic data. Windows execution, browser layout/accessibility with assistive technologies, real-device behavior and clinical validity are NOT established by them.

## Build and tests
`python apps/neurocontinuum/build_frontend.py` rebuilds the two generated frontend assets after editing workspace.js/workspace.css or participant/home.js/home.css.

On the account-enabled installation: `python apps/neurocontinuum/tests/verify_continuity.py` and `python apps/neurocontinuum/tests/verify_assets.py`. Tests use temporary records. The original tests/verify.py uses the older operator-login contract; use it only with that compatible test host.

The optional DOM test requires jsdom supplied in JSDOM_PATH or installed in the test environment. It is not a runtime dependency.
