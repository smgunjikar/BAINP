# Verification results — 16 November 2026

- 41 unittest cases passed in the build environment and in a separately installed temporary project.
- Includes concurrent execution retries, decision-level idempotency, cross-actor scope denial, changed-context rejection, rollback, append-only enforcement and hash-chain tamper detection.
- All seven previously supported research claim types retained their valid-input behavior; existing urgent guidance text retained.
- Installer dry-run, install, repeat install, restore dry-run and exact byte-for-byte source restore passed against the uploaded source snapshot.
- A modified local guard.py was rejected before installation, preserving the local edit.
- No test modified the user's Windows installation or production data.
- No full-app route/UI, live emergency response, sensor/MRI/EEG QC, independent clinical policy review or clinical validation was performed. The acceptance table describes those dependencies.

Run: `python apps/neuroguard/tests/test_safety_v2.py`

## V2.0.1 Windows test cleanup repair

The user Windows run reported nine tearDown errors (WinError 32), not assertion failures. Python SQLite connection context managers commit/roll back but do not close connections. Test-owned connections now close explicitly in finally blocks. Every store test also tracks connections and asserts none are left open before temporary-directory removal. GuardStore already closes its own connections; production policy/storage code is unchanged.

The corrected 41-test suite passes on Linux with connection-leak assertions enabled. Windows execution remains to be verified by the user. Installer accepts both the uploaded original and V2 source hashes.
