# Validation

Executed against the uploaded snapshot in an isolated Linux test environment, 14 November 2026.

- Python compilation and JavaScript module syntax: passed.
- Custom API integration checks using the complete mounted app: unauthorized access, incorrect password, active/demo selection isolation, persistent profile choice, unchanged-save revision preservation, real-edit revision increment, logout invalidation, new-login invalidation and restart persistence passed.
- jsdom interaction checks: overview, editor opening, boolean true/false retention, four-step setup and final consent visibility passed.
- Installer compatibility check against the exact uploaded source passed.
- Installation into a disposable project and byte-for-byte rollback passed.
- Original frontend proxy regression passed.
- Original full-flow regression first failed because it expected a session cookie to survive a server restart. The test was adapted in the disposable test copy to require 401 after restart, then reauthenticate before checking persistence. The adapted full-flow regression passed, including restart persistence, profile concurrency, practice, safety holds and deletion behavior. Production source tests are not overwritten by the installer.

These checks do not establish production security, clinical effectiveness or multi-user isolation. Browser rendering, Windows installation and manual keyboard/screen-reader acceptance still require local verification. No screenshot-based visual QA is claimed. The update uses the existing embedded app photograph, not the exact still-life illustration in the concept.

Optional test dependencies: FastAPI and its compatible test client dependencies for verify_owner.py; Node.js and jsdom for verify_ui.cjs. Use an isolated environment rather than changing the app's pinned dependencies just to run checks.
