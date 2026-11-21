# Acceptance coverage and remaining work

The 14 supplied scenarios are requirements, not all-application passes. The included tests exercise policy and local storage behavior; production adapters are not covered.

| Requirement | Included coverage | Remaining dependency |
|---|---|---|
| Acute warning supersedes recommendation | New V2 urgent precedence and execution reload test | Actual host warning source and every launch endpoint |
| Stale decision rejected | Context/revision fingerprint and expiry tests | Host source writers and consistent transactions |
| Consent withdrawal blocks collection | Per-modality consent tests | Current consent retrieval at each endpoint |
| Cross-user access denied | GuardStore authorization callback/scope tests | Real session and role integration |
| Incomplete cognition restricted | Protocol/timing/device attestation contract tests | Real task QC implementation |
| Unapproved MRI segmentation restricted | Required segmentation review test | Actual imaging review workflow |
| Missing EEG/wearable not normal | Missing quality test | Actual sensor completeness checks |
| Unsupported disease prediction abstains | Unsupported action and model QC tests | Clinical validation is not supplied |
| Functional concern triggers review | Review precedence test | Profile source integration and clinical policy review |
| Local case not delivered referral | Required verified-delivery attestation test | Real communication/delivery receipts |
| Duplicate submissions deduplicated | Concurrent retries, same/different key, rollback tests | Host transactional case/session creation |
| Service unavailable stops actions | Invalid context and loader failure tests | Host must not bypass guard on exception |
| Decisions reconstructable | Stored snapshots, policy/revisions, chain/read audit tests | Retention, external integrity anchoring |
| Reviewed policy passes regression | Offline artifact hash/review-manifest verifier tests | Actual reviewer, independent suite and deployment approval |

## NG-01 to NG-20 scope

NG-01–10: core policy/storage primitives implemented; application-wide authority still depends on the integrations in INTEGRATION.md.
NG-11–15: required model/QC/comparability/source metadata contracts implemented; independent source validators, scientific benchmarks and NeuroProof UI integration remain.
NG-16: local transactional retry/failure behavior implemented; distributed operation not provided.
NG-17: no bypass/exception endpoint; clinical exception governance remains unimplemented.
NG-18: synthetic regression suite provided; independent ARENA, subgroup and human-factors validation remains.
NG-19–20: audit primitives provided; incident surveillance and multi-institution governance are not implemented.

## Hazard register (not a completed clinical risk assessment)

| Hazard | Software control | Residual risk / required validation |
|---|---|---|
| New warning ignored by old page | Stored permission recheck, urgent precedence | Unintegrated endpoint may bypass it; endpoint inventory and end-to-end tests required |
| Incorrect self-report | Explicit unknown/unavailable states | Cannot detect every emergency; clinical and language review required |
| False approved flags | Server-only contract and source hashes | Bad adapter can still supply false attestations; adapter audit required |
| Concurrent stale launch | Same-database transaction | Other databases or external systems require coordination |
| Missing measurement interpreted as normal | Explicit source quality and absent-source reasons | Source adapter completeness must be verified |
| Repeated referral/assessment | Decision-level idempotency and local transaction | External delivery needs provider acknowledgement/idempotency |
| Audit manipulation | Append-only triggers and hash chain | DB owner can rewrite; independent archival anchoring required |
| Overrestriction of disability | Task compatibility rather than disability veto | Supported accommodations require assessment-specific validation |

Clinical guidance reference checked 16 November 2026: CDC stroke signs and symptoms, https://www.cdc.gov/stroke/signs-symptoms/ . The public guidance text advises seeking emergency help; it does not diagnose stroke or claim emergency services have been contacted. Hindi strings are draft translations requiring clinical/localization review before clinical use.
