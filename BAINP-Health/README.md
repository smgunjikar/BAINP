# BAINP Vision Eligibility + My Health

Requires BAINP-Accounts, BAINP-Admin-Dashboard and BAINP-Journey-UI versions supplied previously. This incremental patch changes four files. It retains accounts, research records, consent checks and the original assessment protocols.

## Installation
Extract into your project so BAINP-Health/Install-Update.py exists. Save open files in VS Code.

```powershell
Set-Location 'C:\Users\DELL\OneDrive\Desktop\BAINP'
python .\BAINP-Health\Install-Update.py --project-root . --check
```
Only after Compatibility passed:

```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service Stop
python .\BAINP-Health\Install-Update.py --project-root .
```
Only after Installed:

```powershell
& .\apps\neuroaccess\Start-NeuroAccess.ps1 -Service All
Start-Process 'http://127.0.0.1:3000/#/health'
```
Press Ctrl+F5. Sign in with the existing account. My health is also linked from Account & security. Do not bootstrap again. If compatibility fails, stop and share the mismatch rather than copying files manually.

## Vision correction
The old rule refused selection solely for vision_limitation=True. The revised policy allows the unchanged native battery when can_see_and_respond is explicitly yes and the recorded aid is none or glasses, subject to every other existing eligibility rule. Magnifier/other aids and no/unsure ability remain restricted. It does not establish clinical validity, accessibility equivalence, or provide validated alternative tasks. The current catalogue lacks task-specific accessibility mappings; those still require protocol review.

The profile question now explicitly asks whether the person can see instructions/task items and respond with their usual aid. Keep truthful eyesight answers. A condition remains recorded even when ordinary correction makes the interface usable. If you change a profile, the old check-in remains an immutable snapshot; complete preparation for the updated profile before selecting it. If no profile change is needed, open the blocked monitoring session and use Recheck after resolving the issue. No old decisions are silently rewritten.

No blanket removal of other restrictions was made. History permission, assessment permission, current preparation, Guard restrictions, motor/assistance restrictions and acute pathways are unchanged.

## My health
Optional self-reported date of birth, sex, height/weight, pregnancy notes, medications, allergies, conditions and emergency contact. These are independently saved health notes, not imported screenshot values and not a replacement for the cognitive profile. Changes here do not change age used in an existing assessment.

Personal move-goal value and units note are saved. Height/weight remain explicitly cm/kg; unit conversion and goal progress calculation are not implemented. Reminder times can be saved, but no scheduled/background/browser notifications are delivered.

Records use the current authorized workspace database. Ordinary users can only access their own. Administrator workspace access uses the existing reason/password and audit workflow. Concurrent edits produce a conflict rather than silent overwrite. Consent is required to save. Export downloads only these health details, not all BAINP records. Clear erases this record's contents while retaining its revision; backups can retain old data. Self-reported health details are not used to prescribe treatment or calculate clinical risk.

## What is not implemented
See FEATURE-MAP.md for every feature visible in the seven supplied images. Native lock-screen access, automatic emergency calling, crash detection, walking-steadiness detection, Apple/iCloud integrations, measured energy trends, full-data export, subscriptions/gift-card commerce and reliable background notifications are not implemented. They are explicitly labelled unavailable rather than represented by working switches. The application remains a localhost pilot, without new encryption or production certification.

## Verification
Passed: 92 existing API checks plus concurrency, persistence and token/audit assertions; health-data isolation/consent/validation/stale-write/stale-delete/clear tests; policy tests for glasses, unresolved ability, nonstandard aids and missing consent; frontend DOM checks including health form; installer and restore checks.
Not verified: Windows execution, actual browser appearance, clinical validity, all scientific engine suites or native device integrations. Test scripts are included. API checks require existing application dependencies; DOM checks require Node and jsdom.

## Restore
Stop BAINP and run Install-Update.py --project-root . --restore followed by the exact printed backup directory. Changed installed files cause refusal. Restore changes source only; new private health tables remain in each workspace database.
