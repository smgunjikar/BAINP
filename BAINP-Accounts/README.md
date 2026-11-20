# BAINP Accounts — local multi-user pilot

This update replaces the shared operator code with separate email/password accounts, private databases, administrator review, and a test lab. It is not a production security certification. Keep it on localhost. The existing participant workflow and scientific engines are retained; this package does not complete every proposed BAINP 3.0 feature.

## Install on Windows

1. Save all open editor files. Extract BAINP-Accounts.zip into your BAINP project, so BAINP-Accounts/Install-Accounts.py exists. Do not copy payload files manually.
2. In your existing `(bainp)` PowerShell terminal run:

```powershell
Set-Location 'C:\Users\DELL\OneDrive\Desktop\BAINP'
python .\BAINP-Accounts\Install-Accounts.py --project-root . --check
```

Continue only if it prints `Compatibility passed`. If it reports changed source, stop and share that message; the installer deliberately refuses to overwrite newer fixes.

```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service Stop
python .\BAINP-Accounts\Install-Accounts.py --project-root .
```

Continue only after `Installed` appears. Then create your administrator account:

```powershell
python .\apps\neuroaccess\backend\accounts.py --bootstrap-admin
```

Enter your email, name and a unique password when prompted. Password input is hidden. Use at least 15 characters. If you configured NEUROACCESS_DATA_DIR, use the same environment for bootstrap and launcher. Do not publish your password or recovery codes.

```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service All
Start-Process 'http://127.0.0.1:3000/#/signin'
```

Refresh with Ctrl+F5. Sign in with the new email and password. The old operator code no longer works.

## Accounts and administration

- A person requests an account from the sign-in screen. You approve it in `#/admin`. Registration never grants administrator rights. Email is an identifier, not verified ownership.
- Each account gets its own application database and personal profile. Existing legacy profiles are not automatically assigned to anyone.
- Use a separate browser profile or private window when testing a second account. Tabs in the same browser profile share login cookies.
- In Administration, enter your administrator password and an access reason to open another active user's workspace. Your identity stays administrator; access is logged. Return to your own workspace when finished.
- Account controls approve, disable, enable, archive, or issue recovery codes. Disable/archive revoke sessions. Archive retains data and is NOT permanent erasure.
- Recovery codes are displayed once, expire after 30 minutes, and can be used once. Deliver them privately after checking the person's identity. No email or SMS is sent.
- Account security supports password change, session count, sign-out and sign-out everywhere. Sessions expire after 30 minutes idle or eight hours total. Password changes revoke existing sessions.

## Test lab

Open `#/test-lab` as administrator. Explicitly enter the legacy test workspace with your password and reason. Active and demo tabs remain separate. Create test profiles, open their workspace to edit/use them, or delete records by entering the exact requested DELETE confirmation. Record deletion uses the existing application's cascade behavior; make a backup before deleting records you need.

“Active” means legacy active records; it does not mean disposable. The test lab is not a production-data sandbox. Never use actual participant information for destructive experiments. Other users cannot access this lab. Account archiving is in Administration, not a hidden destructive test action.

## Storage and security boundaries

Default data directory: `%USERPROFILE%\BAINP_DATA\local\neuroaccess_v1` (or NEUROACCESS_DATA_DIR).

- Legacy records remain in the original database.
- Identity and audit: `identity/accounts.sqlite3`.
- Private records: `identity/workspaces/<server-generated-user-id>/records.sqlite3`.
- Passwords use salted scrypt; session/recovery tokens are stored as hashes. Cookies are HttpOnly/SameSite Strict. Local HTTP cookies are not Secure; public deployment requires HTTPS and appropriate cookie/proxy configuration.
- Server-side ownership boundaries, fixed-origin checks, request-header checks, rate limits, and administrator reauthentication are implemented. A user-supplied record ID does not select another user's database.
- Administrator cross-workspace requests and account actions are logged. Audit tables reject application-level update/delete, but an operating-system/database owner can alter files. This is not independently tamper-proof logging.
- Shared imaging/research-file engines are restricted to the administrator's legacy workspace because their external files are not yet partitioned per user. Do not enable them for ordinary accounts without a separate storage-isolation review.
- SQLite files are not encrypted by this patch. Protect the computer, filesystem permissions and backups. Anyone with OS access can reset the administrator offline.
- No MFA/passkeys, SSO, verified email/phone delivery, automated recovery delivery, managed encryption keys, production disaster recovery, regulatory certification, or independent penetration test is supplied. Administrator lists currently show up to 500 accounts; this is not an unlimited-scale service.

Offline administrator recovery, only on the server computer:

```powershell
python .\apps\neuroaccess\backend\accounts.py --reset-admin
```

This revokes administrator sessions and records the reset. Do not expose this command through a web endpoint.

## Validate and restore

The package includes API isolation/security tests and DOM interaction tests. See VALIDATION.md. The installed baseline verifier is adapted to account authentication:

```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service Verify
```

Other older module test scripts may still expect operator-code authentication and require fixture updates. They were not all run.

The installer prints an exact backup directory. To restore source, stop the app and run:

```powershell
python .\BAINP-Accounts\Install-Accounts.py --project-root . --restore 'PASTE_THE_PRINTED_BACKUP_DIRECTORY'
```

Restore refuses if installed source changed afterward. It retains new account databases and restores the old source only. The old operator version is not safe for separate user accounts. Keep it local. No production database migration or deletion is performed during installation.
