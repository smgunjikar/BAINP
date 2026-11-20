# BAINP Admin Dashboard update

Requires the exact installed BAINP-Accounts release. This is an incremental two-file patch, not a replacement app. Existing accounts and records are retained. No new administrator bootstrap is needed.

Extract this ZIP into your BAINP folder so BAINP-Admin-Dashboard/Install-Accounts.py exists. Save open editor files.

```powershell
Set-Location 'C:\Users\DELL\OneDrive\Desktop\BAINP'
python .\BAINP-Admin-Dashboard\Install-Accounts.py --project-root . --check
```

Only after Compatibility passed:

```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service Stop
python .\BAINP-Admin-Dashboard\Install-Accounts.py --project-root .
```

Only after Installed:

```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service All
Start-Process 'http://127.0.0.1:3000/#/admin'
```

Press Ctrl+F5 and sign in with your existing administrator account if prompted. No need to create a participant profile to use Administration.

## Dashboard
- Approved/pending/disabled accounts and valid session count.
- Searchable account activity: creation date, last successful login, valid sessions.
- Latest 50 sign-in/registration events. Unidentified failed attempts are not falsely attributed to users.
- Legacy active and demo test-record counts; separate Test lab link.
- Existing approval, disabling, recovery, archive and reason/password-confirmed workspace access.
- Refresh button reloads current data. No automatic live presence claim.

Approved accounts are not the same as users currently online. Valid sessions must be unexpired and used within 30 minutes. Demo records are profiles in the legacy test workspace, not demo login identities. Lists show up to 500 newest accounts; existing audit list shows 100 recent events.

Each account retains a separate application database. A new user starts with their own profile and journey rather than choosing another person's record. Shared imaging/research-file modules remain admin-only pending storage isolation. This patch does not add verified email/phone delivery, MFA, unlimited scale or production certification. Keep the existing localhost-only deployment.

The dashboard reads account metadata and test-record counts, not private assessment contents. Other-workspace record access still requires administrator password and reason and is logged. Audit storage is application append-only, not tamper-proof against the computer owner.

Rollback: stop BAINP and use --restore with the backup path printed by this installer. Source changes made after installation cause restore to refuse rather than overwrite them. Data is untouched.
