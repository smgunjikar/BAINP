# NeuroShadow Native V1

Opt-in experimental digital-interaction measurements in the existing BAINP Python/FastAPI/SQLite application. Requires native NeuroContinuum and NeuroQuest V1.1. Uses the existing operator login, origin/request controls, ports 3000/8000 and participant/mode identity. No new dependencies, disease model, diagnostic threshold or external telemetry endpoint.

## Install and use

Save all VS Code buffers. Stop existing NeuroAccess services. Run `python Install-NeuroShadow-Native-V1.py <existing BAINP root>` using activated conda environment `bainp`. Tests run with temporary fictional databases; failures restore changed source files. Source backups are under `%USERPROFILE%/BAINP_DATA/patch_backups/neuroshadow`. Restart existing services and select **NeuroShadow V1** on the main page. Do not rerun older NC/Quest installers over these shared integration files without a coordinated update.

Select participant and mode. Read and explicitly save NeuroShadow permission; sharing descriptive context with NeuroQuest and NeuroTwin is a separate optional scope. Both default off. Choose the actual pointer type, start recording, use the marked activity board naturally, then save aggregates or discard. There are no correct answers or cognitive scores. The collector is not attached to other BAINP pages. Adding future activity surfaces requires an explicit registration and privacy/measurement verification; the code must never be injected across unrelated pages.

## Capture and privacy

Pointer move/down/up listeners attach only to `data-neuroshadow-activity="shadow-explore-v1"`. The collector rejects input/textarea/select/contenteditable targets, other pointer types and non-primary pointers. It does not listen to keyboard, text input, clipboard, screenshots, window titles, browser history or page URLs. Touch uses Pointer Events and browser defaults; this version does not classify semantic gestures. Only a single marked activity surface is supported.

Transient events carry elapsed time quantized to 50 ms and relative position rounded to a 20-step grid. Movement sampling is capped near 20 Hz, total events at 2,400, and activity duration at two minutes. Mouse contacts/touch contacts and sampled movement statistics are distinct; gaps in movement are not cognitive response latencies. No page text, tile label or click-target identity is transmitted. Coarse viewport, pixel-ratio bucket, pointer type, reduced-motion preference and profile revision form condition metadata; exact user agent and hardware fingerprint are not collected.

Events remain in memory until an explicit save. They are transiently sent to the existing local backend, which validates and extracts aggregate features, then stores no event array or raw coordinates. Request bodies are not added to application audit records. Existing server/deployment logging must not be configured to record request bodies. This implementation does not encrypt the existing local SQLite database or independently audit OS/browser memory and infrastructure logs.

Capture stops when the page is hidden, viewport changes or duration/event budget is reached. Page unload clears local events; incomplete server sessions can be explicitly discarded on return. Collection permission is rechecked every five seconds during active capture and server-side on every upload. Revoking/changing permission invalidates open collections immediately on the server; another tab may hold a local buffer until its next permission check. Failed permission checks stop local capture and clear samples. Disable-and-save hides retained history but is not data deletion. Existing participant deletion cascades through all Shadow tables. Aggregates, consent history and audit markers otherwise follow local database retention; no automatic retention purge is claimed.

## Features and quality

Server recomputation yields movement event count, contact count, touch contacts, normalized path length, movement-step variability, median normalized movement speed, variability of sampled movement intervals, movement-gap count, and contact timing summaries. Units are normalized activity coordinates and milliseconds, not physical motion, neurological latency or calibrated motor performance. All event timing/frame diagnostics remain client reported and can be forged by a modified client; plausibility checks do not make the browser a trusted clinical instrument.

The separate `apps/neuroguard/backend/shadow_policy.py` applies disclosed engineering checks: at least 10 seconds, 40 movement samples, 30 frame samples, no hidden-page interruption or viewport resize, at most 10% observed frames above 100 ms, and plausible client/server duration. The result is `TECHNICAL_QC_CLEAR` or `QUARANTINED`. These are not validated clinical reliability thresholds. Quality-clear features are not standalone digital biomarkers of Alzheimer's disease or cognitive decline.

## Longitudinal and module integration

Within-person comparisons require matching feature/activity version, coarse device condition hash and current profile revision. Different conditions are displayed as unpaired. Two matching quality-clear sessions yield arithmetic differences only; no stability, decline, clinical comparability, reliable-change index, causal interpretation or alert is inferred. Fatigue, familiarity, medications, motor ability and unmeasured context can confound even matching device conditions. Sampling gaps may reflect inactivity or leaving the board rather than cognitive hesitation.

NeuroQuest receives a currently permission-gated source reference, technical status and explicit `selection_influence="NONE_V1"`. Passive data cannot authorize a task, override Guard, trigger a diagnosis or create a clinical case. Feature values are not duplicated into Quest decisions. Sharing withdrawal stops new context availability; previously authorized decision records can retain their provenance reference under the original workflow's history permissions.

The existing NeuroTwin workflow-marker integration additionally includes permitted descriptive Shadow context. It does not call a prediction model, mix participants or write fabricated multimodal source observations. NeuroContinuum remains the workflow authority. CareLoop remains accessible independently of participation in this research feature.

## Persistence and interfaces

Additive tables: `ns_consents`, `ns_sessions`, `ns_events`, participant deletion cascades enabled. Existing schemas and database version are preserved. Operation UUIDs use the existing transactional replay store with request hashes, not raw input bodies. Finish operations write aggregate summary, hash and audit marker together. Permission revision, participant/mode, profile revision and open-session state are checked before accepting a buffer. An unavailable independent technical policy fails without recording success. Fifty server sessions per participant/mode/day and one open collection bound accidental session churn.

Under `/api/neuroshadow/v1`:

| Route | Method | Purpose |
|---|---|---|
| `/participants/{pid}` | GET | Permission-gated aggregate history and descriptive comparisons |
| `/participants/{pid}/consent` | GET / PUT | Read / explicitly record collection and sharing scope |
| `/participants/{pid}/sessions` | POST | Start permitted designated collection |
| `/participants/{pid}/sessions/{sid}/finish` | POST | Validate transient samples and persist aggregates |
| `/participants/{pid}/sessions/{sid}/discard` | POST | Close an unfinished collection without features |

Run `python apps/neuroshadow/tests/verify.py`. The suite tests engineering behavior in disposable fictional data and does not validate clinical biomarkers, client timing, privacy compliance, accessibility conformance or deployment security. No independent ARENA certification or zero-latency guarantee is claimed.
