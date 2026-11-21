# NeuroQuest native V1

A deterministic assessment navigator inside the existing BAINP Python/FastAPI/SQLite application. Native assets are served on the existing port 3000; API routes mount under `/api/neuroquest/v1` on the existing backend. No new service, dependency installation, external AI call or research pipeline is introduced.

## Installation

Save all VS Code buffers. Activate conda environment `bainp`. Install NeuroContinuum Native V1 successfully first. Stop the existing NeuroAccess services, then run `python Install-NeuroQuest-Native-V1.py <existing BAINP project root>`. The installer rejects unsupported insertion anchors, backs up changed source files under `%USERPROFILE%/BAINP_DATA/patch_backups/neuroquest`, and runs temporary-data verification. It restores changed source files if those checks fail. It does not replace participant databases. Restart the existing NeuroAccess services and choose **NeuroQuest V1** from the main page.

## Use

Select the existing participant and a saved NeuroAccess check-in. Current workflow consent is managed in NeuroContinuum. Record current concerns and any domain clarification or corrected quality issue; select an acute sign only if actually reported. Evaluate the next action, inspect its evidence, then continue through NeuroContinuum. The engine re-evaluates current permissions, profile, access gates and source records at workflow selection; it never executes a cached recommendation blindly. Functional concerns remain in the last recorded intent until the operator explicitly updates them. Professional review remains accessible from the page regardless of task results. Cases are local tracking records, not delivered referrals.

The current native catalogue supports predefined batteries. Core task IDs and protocol are read from the installed `battery` module; server-seeded task ordering, diagnostics, preparation, device checks, scoring and alternate-form assignment remain with NeuroCognition. NeuroQuest does not force the participant to execute a specific task or silently skip tasks. Native UI choices remain authoritative.

## Rules and limits

| Action | Implemented behavior |
|---|---|
| Baseline | Offer the current native core research battery when no complete same-protocol source-QC-clear battery exists |
| Repeat | Identify latest quarantined task references, require quality correction, withhold automatic launch because native isolated repeat execution is absent |
| Targeted | Record the requested domain; abstain from execution until comparable-change evidence and an authorized isolated-task protocol exist |
| Monitor | Avoid an immediate repeat after a complete current-protocol battery and explicit current concern check, within a 24-hour engineering cooldown |
| Professional review | Functional concerns take priority over digital result interpretation; link to CareLoop; NC creates/reuses a case only with case-tracking permission |
| Urgent guidance | Existing NeuroGuard escalation takes precedence; no assessment launch, emergency dispatch or automatic referral |
| Abstain | Missing consent, source history, catalogue, access clearance or supported accommodations prevents an executable recommendation |

A 24-hour cooldown is a disclosed engineering policy, not a validated clinical interval. NeuroQuest cannot establish stability, cognitive decline, reliable change, disease risk or clinical suitability. Raw numerical score differences and passive telemetry do not trigger diagnoses or targeted execution. Full batteries from separate sessions are not assembled into one baseline. Different protocols are not silently pooled. Forms and administration conditions remain separate evidence; their clinical comparability is not established. Old quality failures superseded by newer results are evaluated using latest task source references.

Motor/vision limitations, unaccommodated hearing limitations and assisted administration require review because the source registry lacks validated alternative mappings. This conservative prototype is not an accessibility certification. Native interface languages en/ar are available, but translation validity is not established. Participant preferences and native access holds remain binding.

## Persistence and provenance

`nq_decisions` is additive in the existing database, participant-linked with deletion cascades. It stores an immutable recommendation payload, source references, complete selector input context, policy version and SHA-256. This is local integrity checking, not signed/tamper-proof evidence or a new NeuroGraph scientific evidence record. NC events link decision IDs and hashes to workflow transitions. Scope withdrawal hides stored history in this UI; old operation replays cannot recover withdrawn permission records. No separate clinician authentication roles are introduced.

All endpoints inherit existing authenticated operator, same-origin and request-header checks. Operation UUIDs use the existing transactional replay store; conflicting payload reuse is rejected. NC selection and decision insertion share the existing workflow write transaction. No separate patient diagnosis or autonomous agent is present.

## Verification

Run `python apps/neuroquest/tests/verify.py` then `python apps/neurocontinuum/tests/verify.py`. The selector suite includes pure deterministic checks and real native API/Guard/CareLoop integration in disposable fictional databases. Source-result arrangements are fixtures, not evidence of valid human cognitive performance. Tests are independent scripts; no new NeuroSignal ARENA benchmark registration or clinical certification is claimed.

Optional NeuroShadow, NeuroMimic and NeuroProof contracts were not supplied or verified and are not invented. Existing NeuroTwin participant-linked source references are read through the existing NC adapter without predictive snapshot execution. No load benchmark, zero-latency guarantee, clinical validation or comparison against industry products has been established.

Do not rerun the older NeuroContinuum installer after this extension: its original engine/bridge payload predates this hook. Use a coordinated update to preserve both modules. Unsupported local source layouts fail before writes and require source-specific adaptation.

## V1.1 repair

Urgent and functional-review decisions can be recorded without a saved check-in and without calling routine cognition, registry or history services. Urgent guidance comes from the existing native NeuroGuard module. A recorded urgent decision blocks every open participant/mode NeuroContinuum workflow, removes its routine recommendation and records a safety event in the same database transaction. It does not remotely stop an independently open native cognitive task or contact any service. NeuroGuard remains available from navigation even if recording permission is unavailable.

The page keeps the chosen check-in after refresh/evaluation, separates urgent guidance visually, removes routine-continuation links for urgent decisions, and presents readable evidence facts. Raw JSON is available only through an explicit download button. Client requests time out after 15 seconds; uncertain writes retain the original operation ID for a retry with the same inputs. Permission/validation errors discard stale pending IDs for a new attempt. No latency guarantee is claimed.
