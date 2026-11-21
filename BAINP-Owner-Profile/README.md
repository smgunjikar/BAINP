# BAINP owner profile refresh — 14 November 2026

This is an update to the uploaded 195-file snapshot, not a replacement homepage.

## Install
Save all open VS Code files first. Extract this folder into the BAINP project root, naming it BAINP-Owner-Profile. In PowerShell at the project root:

```powershell
python .\BAINP-Owner-Profile\Install-Owner-Profile.py --project-root . --check
if ($LASTEXITCODE -ne 0) { throw "Source changed. Stop and share the error." }
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service Stop
python .\BAINP-Owner-Profile\Install-Owner-Profile.py --project-root .
if ($LASTEXITCODE -ne 0) { throw "Installation stopped. Share the error." }
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service All
```
Open http://127.0.0.1:3000/#/workspace/participants and press Ctrl+F5. Sign in with your local operator code. Choose your existing profile once; this does not delete other records or imply separate user accounts.

## Changes
- Personal profile overview and contextual editors, warm cream/peach surfaces, black rounded buttons, responsive layout, existing locally embedded illustrative photograph.
- Four-step new-profile form with Back/Continue and explicit storage consent on the final step. Unsubmitted setup is a browser-memory draft; closing/reloading discards it. Saved profile preferences persist in SQLite.
- Personal/accessibility/display/assistance sections; consent link goes to existing granular permissions workflow.
- Persistent owner profile selection for each active/demo mode. Existing test records remain under Owner controls. Normal toolbar no longer offers a mode switch.
- Random server-held eight-hour session tokens. Logout revokes the token; new sign-in revokes prior owner session; API restart requires sign-in again.
- Existing unchanged-save fix remains. Real changes still update the profile revision and may require a fresh readiness check. No bypass of consent/safety validation.

## Boundaries
Owner-only local testing is implemented. Email/password accounts, public registration, multi-user record ownership, administrator delegation, email recovery and production deployment are NOT implemented. Do not expose this server to a network. Use the existing launcher, which binds to loopback. Cookie Secure remains false for localhost HTTP. The existing local operator credential remains unchanged. The previously exposed code should be rotated before network deployment; do not share it.

No new personal or medical fields were added without a defined need. The public homepage, scientific engines, historical records and existing consent policies are unchanged. There is no claim of clinical effectiveness or production security certification.

## Rollback
Stop the app. Use the exact backup directory printed by the installer:

```powershell
python .\BAINP-Owner-Profile\Install-Owner-Profile.py --project-root . --restore "FULL_BACKUP_DIRECTORY"
```
Restart the app. Restore refuses if files changed after installation. It restores three source files only; the owner_preferences table is harmless and remains in the database. No records are deleted.

## Verification
See VALIDATION.md. Installer verifies SHA-256 of every target before writing and backs up originals. Do not bypass a source mismatch: upload a fresh snapshot instead.
