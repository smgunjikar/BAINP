# BAINP Journey and Shared UI update

Requires the BAINP-Accounts version of app.js. Compatible with or without the separate Admin Dashboard update, which this patch does not modify. Four source files change. No database or authentication changes.

## Install
Extract into the BAINP folder so BAINP-Journey-UI/Install-Update.py exists. Save editor files first.

```powershell
Set-Location 'C:\Users\DELL\OneDrive\Desktop\BAINP'
python .\BAINP-Journey-UI\Install-Update.py --project-root . --check
```
Only after Compatibility passed:
```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service Stop
python .\BAINP-Journey-UI\Install-Update.py --project-root .
```
Only after Installed:
```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service All
Start-Process 'http://127.0.0.1:3000/#/journey'
```
Press Ctrl+F5. Use the existing email/password login. Do not bootstrap again. If compatibility fails, share the mismatch; do not force-copy files over a newer version.

## Fixed flow
Overview → Open monitoring session → My Brain Health → permissions → accessibility conditions/practice → recommended workflow action.

In the technical NeuroContinuum screen, a missing check-in now offers Complete preparation instead of an empty selector. It opens the accessibility step with the participant and mode in the URL. Explicit participant selection is loaded through the existing authorized API. Unauthorized IDs are still rejected by the backend.

Complete current conditions and interface practice where permitted. A No answer to acute-warning questions is not itself a completed practice. Saved safety restrictions and consent remain authoritative; the patch does not bypass them. When preparation is complete, use Recommended step to continue the monitoring workflow.

The technical engine screen remains available. Its existing-checkin selection and server-side validation remain unchanged. This patch does not automatically declare old or incomplete check-ins usable.

## Visual changes
Shared cream/peach/black navigation styling, readable management text, consistent rounded buttons/cards/dialogs, responsive guided steps, clearer account navigation, and removal of duplicated navigation on the root journey. Cognitive task stimulus styling is intentionally excluded. This is a shared UI consistency pass, not a redesign of every scientific engine or completion of every BAINP feature.

## Validation
Passed JavaScript syntax checks; DOM checks for empty-checkin recovery, participant-preserving preparation links, shared-navigation compatibility and consent prerequisite; overview routing assertions; installer/restore tests in an isolated project copy.

Not verified: real-browser visual rendering, Windows installation, or a complete human assessment journey. Existing backend scientific/auth logic is unchanged. After installing, test profile → permissions → conditions → practice → recommended workflow on your local computer and report any error text without credentials.

## Restore
Stop the app and run the same installer with --restore followed by the exact printed backup path. Changed files cause refusal rather than overwriting later edits. Original source is backed up; database rows are not modified by this update.
