# V2.0.1 repair

Fixes Windows-only temporary database cleanup failures in the test suite. All test connections are explicitly closed; connection-leak assertions run before cleanup. No safety checks are disabled. This cumulative installer accepts original uploaded source or the previously delivered V2 package. Production backend behavior is unchanged.

# NeuroGuard V2 backend upgrade — 16 November 2026

Target: `BAINP/apps/neuroguard` only. Python 3.10+ (3.11 recommended). Standard library only.
Based on the five Python source files in the user's neuroguard.zip. No clinical review or medical-device certification has been performed.

## What becomes active after installation and BAINP restart

- The existing Continuum adapter requires real boolean consents and availability, instead of accepting truthy strings such as `"false"`.
- If its caller supplies urgent signs or a professional-review requirement, the adapter withholds its existing workflow action.
- It explicitly identifies its limited legacy enforcement scope; it does not claim to be a V2 execution authorization.
- The existing research claim gate rejects unknown claim types, malformed evidence and non-boolean eligibility.
- Existing supported claim and workflow result structures are retained.

## New backend capabilities included

- `backend/safety_v2.py`: deterministic action-specific decisions, versioned Safety Passport, English/Hindi explanations, expiry, source/input/consent fingerprints, public emergency guidance text and execution-time re-evaluation.
- `backend/safety_store.py`: host-owned SQLite transaction integration, authorization callbacks, stored decision retrieval, logged reads, append-only audit records, hash-chain verification, atomic local action commit and idempotent execution including concurrent retries.
- `backend/policy_release.py`: offline verification of release review references, policy/test artifact hashes and expiry. A manifest is evidence metadata, not proof of reviewer identity or clinical approval.
- `tests/test_safety_v2.py`: 41 automated policy/storage tests using synthetic fixtures.
- This update does not open an HTTP port, introduce a public API, change accounts, or create a second participant database.

## Previous version versus this package

| Previous uploaded code | Upgrade |
|---|---|
| Five separate policy modules | Existing modules retained; shared V2 decision/storage contract added |
| Basic workflow identity/consent gate | Strict booleans and optional urgent/review precedence in the legacy adapter |
| No shared expiring action contract | Per-action passport with expiry, input/consent revisions and policy hash context |
| No NeuroGuard decision store | Transactional store usable in the existing authorized workspace database |
| No general execution replay protection | One committed operation per decision; repeated keys or concurrent retries replay saved output |
| Research claim checks | Unknown and malformed source claims now rejected |
| No V2 multimodal contract | Modality-specific required QC attestations; missing data preserved as missing |
| No supplied tests | 41 synthetic tests plus installer and legacy compatibility checks |

## Important boundary: installation is not whole-app activation

The uploaded folder has no HTTP router or frontend. No new website page appears from this backend package alone. Existing host bridges load `guard.py` and `continuum_policy.py`; those changes activate on restart. The new V2 library must be invoked by authenticated execution routes. It is not automatically injected into unrelated engines, and does not silently monkey-patch them.

The inspected legacy Continuum caller passes participant/mode, consent, availability and access holds, but does not supply all V2 safety inputs. This package therefore does not claim to fix every cross-page emergency bypass, wire medical-profile concerns into safety decisions, or unblock a NeuroQuest `QUALITY_CORRECTION_REQUIRED` decision. Those require host integration and actual source QC review.

QC fields are attestations loaded from authoritative engine records. NeuroGuard does not itself segment MRI, analyze EEG, determine sensor calibration, clinically validate cognitive tasks or train a disease model. Passing a QC contract does not establish clinical validity.

A recorded vision limitation is not a blanket veto in V2. The host must establish compatibility for the particular task, including supported accommodations; never set compatibility true merely because practice was completed.

## Installation and rollback

Use the supplied installer with `--project-root PATH --check`, then stop BAINP, install and restart. The installer accepts the uploaded source hashes (or this exact installed update) and refuses unrelated newer edits. Backups are stored inside `apps/neuroguard/.continuity-backups/`. It does not edit databases.

Rollback: stop services; run `python Install-NeuroGuard.py --project-root PATH --restore BACKUP_PATH --check`, then repeat without `--check`; restart. Restore refuses files changed since installation. Restoring source does not erase audit records created later by an integrated host.

## Verify

From BAINP root:

```powershell
python .\apps\neuroguard\tests\test_safety_v2.py
```

These tests are software checks on synthetic data, not clinical validation, clinical policy approval, Windows UI acceptance, or whole-application penetration testing.
