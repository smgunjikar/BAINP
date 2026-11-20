# Verification — 15 November 2026

Executed in the supplied Linux Python 3.12 environment against an isolated copy of the source snapshot:

- 88 HTTP checks passed, plus concurrent account isolation, restart persistence, hashed token storage, and append-only audit assertions.
- Tests cover foreign profile/check-in access, admin role restrictions, unknown API denial, demo restrictions, origin/header checks, invalid Host, oversized auth requests, disabling accounts, password changes, recovery code reuse, logout replay, administrative access and test-record deletion.
- DOM interaction tests passed for email/password sign-in, registration validation, admin UI boundary, workspace selection, audit view and account security.
- Both adapted baseline regression tests passed: frontend/proxy/security headers and full application flow (validation, active/demo isolation, concurrency, practice, comparisons, persistence, holds, deletion).
- Installer compatibility, installation, byte-exact source rollback and changed-source refusal passed against the original snapshot.

Not verified: execution on the user's Windows computer, visual rendering in a real browser, all scientific module suites, production hosting, load resilience, independent penetration testing or compliance. The tests provide evidence for the exercised paths, not proof that no vulnerabilities remain.

Reproduce API checks with the existing application dependencies:
`python verify_accounts.py --project-root PATH_TO_PATCHED_PROJECT`

DOM tests require Node and jsdom:
`node verify_ui.cjs`

The package retains its payload directory for the DOM checks. Test account credentials in verification scripts are fixtures only, never installed administrator credentials.
