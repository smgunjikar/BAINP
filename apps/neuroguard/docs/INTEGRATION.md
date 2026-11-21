# Trusted integration contract

This is the integration requirement, not a claim that other BAINP engines already implement it.

## Host responsibilities

1. Authenticate the session and resolve actor, workspace and participant on the server. Do not derive ownership from a query string or JSON flag. Administrator access requires an explicit reason and host audit event; administrator status does not bypass safety checks.
2. Supply `GuardStore(connect, authorize, load_context)`. `connect()` returns a fresh SQLite connection to the already authorized workspace database. `authorize(connection, actor, workspace, participant, operation)` validates current host permissions and returns the actual boolean True only if allowed.
3. `load_context(...)` reads current source records in the supplied transaction. It must not accept client attestations for `authorized`, `inputs_verified`, QC approvals, delivered referrals or model approval. The host verifies evidence hashes, revisions, protocol scope, authenticity and current consent before constructing the context.
4. Call `decide` to save a passport. Call `execute` at the actual protected action endpoint, using only the stored decision ID. The service reloads context, checks expiry and fingerprint, and permits a local DB mutation only in the same `BEGIN IMMEDIATE` transaction.
5. All source writers must use the same transactional database, or an equivalent version/locking protocol. A SQLite lock cannot protect a different database or an external sensor stream. Such integration is not implemented here.
6. The operation callback may create a local session/case/outbox record in that transaction. Never make a network call, send a referral, or write uncoordinated external files inside it. Exactly-once external delivery requires provider idempotency and verified acknowledgements; this package does not provide a delivery channel.
7. Exceptions from the loader, authorizer or store stop execution. The host must render a service-unavailable state, never fall back to bypassing the guard. Keep public emergency guidance accessible independently of database availability and assessment consent.
8. An identical idempotency request returns its historical passport; it is not a fresh permit. Every launch still goes through execution-time verification. Replayed committed actions are marked `executed=false, replayed=true`.

## Input shape

See `tests/test_safety_v2.py::context` for a synthetic schema fixture, NOT a production context factory. Required fields include workspace/participant/actor/session/mode/action; input and consent revisions; authorization/service/input verification booleans; reviewed warning state and urgent sign list; consent scope map; task readiness; observation validity timestamps; source references and QC attestations.

`action` is a server-chosen allowlisted action. Unknown actions abstain. For acquisition actions, readiness and appropriate consent are required. For interpretation, required current modality sources and QC checks must all be present. Clinical diagnosis and treatment actions are not supported.

A source reference contains `id`, string `revision`, `workspace_id`, `participant_id`, `mode`, `modality`, `quality`, `protocol`, SHA-256 and explicit checks. Every applicable source must satisfy the contract; do not hide unfavorable sources from the context. Preserve missing/quarantined sources and their reasons.

## Engine connections still required

| Engine | Required connection |
|---|---|
| NeuroAccess | Load verified identity, versioned consent, current accessibility and warning inputs |
| NeuroContinuum / NeuroQuest | Invalidate displayed actions on changed inputs; execute only a freshly verified stored passport |
| NeuroCognition | Guard launch and result interpretation; actual protocol completeness/timing QC |
| NeuroVision / Pulse / Sense / Shadow | Supply modality-specific authoritative QC and consent; guard acquisition/interpretation |
| NeuroTwin / Mimic / Graph | Verify source provenance, units, visit comparability and reviewed model scope |
| CareLoop | Create local review cases transactionally; verify delivery through a real provider before marking delivered |
| NeuroProof | Read logged passports from the same workspace, using authorized reads; do not duplicate personal data |
| NeuroCore / ARENA | Deploy reviewed immutable policy artifacts; run independent regressions; no model-controlled bypass |

## Security and retention

No HTTP API is included, so this library does not implement authentication, TLS, CSRF controls or network isolation. Those remain host responsibilities. Audit triggers block application-level updates/deletes. The hash chain detects some tampering, but an administrator with DB/filesystem access can drop triggers, rewrite the chain or truncate history. Independent audit anchoring/backups and restricted deployment credentials are required for stronger guarantees.

The stored context contains sensitive metadata. Use a minimal context, appropriate workspace file permissions, retention rules and access logging. Append-only records need an explicit governed retention/deletion procedure; none is silently added. Policy release review records are not cryptographic reviewer signatures. Clinical review, localization review, usability tests and operational monitoring remain required before clinical deployment.
