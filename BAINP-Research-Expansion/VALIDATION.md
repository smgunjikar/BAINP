# Validation performed — 16 November 2026

Tested against an isolated reconstruction of the available BAINP snapshot plus the
previous Accounts, Administration, Journey and Health changes. The user's current
Windows installation was not accessed or modified.

| Check | Result |
|---|---|
| New full-app API tests | PASS: 41 HTTP assertions plus numerical and storage assertions |
| Existing account-security regression | PASS: 88 HTTP checks plus concurrency, persistence, token storage and audit assertions |
| Synthetic movement input | PASS: a 5 Hz signal recovers its expected peak; flat axes flagged |
| Synthetic EEG input | PASS: a 10 Hz input concentrates relative power in the defined alpha band |
| Signal rejection | PASS: incorrect units and non-increasing timestamps rejected |
| Research permissions | PASS: unsigned requests, unauthenticated clients and non-admin accounts denied |
| Workspace and active/demo isolation | PASS: records from another workspace or mode not returned |
| Task finalization | PASS: repeat identical submission returns same result; changed submission rejected |
| MRI numerical tool | PASS: known labelled voxel count × physical voxel volume; missing names and affine mismatch rejected |
| MRI import comparison | PASS: arithmetic difference; cross-workspace and scanner mismatch rejected |
| Persistence | PASS: records survive app recreation |
| Interface DOM execution | PASS: administrator gate, all 3 runners, response payloads, voice consent text, tab navigation and abort submission |
| Installation and rollback | PASS: hash compatibility, install, restore and rejection of changed source |
| Python and JavaScript syntax | PASS |
| Headless browser visual/audio test | NOT RUN TO COMPLETION: Chromium launch blocked by environment socket restriction |
| Windows acceptance / real microphone / watch / EEG hardware | NOT TESTED |
| Clinical performance or regulatory conformity | NOT ESTABLISHED |

DOM timer acceleration tests functional event flow, not timing accuracy. Synthetic
signal tests establish numerical behavior on those signals, not clinical validity.
No generated/synthetic measurements are inserted into real participant records.

Included scripts:
- `python tests/verify_research.py PATH_TO_INSTALLED_BAINP`
- `python tests/verify_mri.py` (requires numpy and nibabel)
- `node tests/verify_dom.cjs` (requires jsdom)
- `python tests/verify_installer.py PATH_TO_BASELINE_PAYLOAD` (development only)
- `tests/browser_server.py` and `tests/verify_browser.cjs` are local development
  fixtures, not services to deploy. The former expects the `research-test` fixture
  layout; the latter requires Playwright and Chromium. The credentials are synthetic
  and exist only in a temporary database. Set CHROMIUM_PATH for another executable.

Suggested Windows acceptance before using any real research data:
1. Sign in as administrator; open Research studio in the intended workspace/mode.
2. Run each task, stop a run, reopen history, and export a record.
3. Use a synthetic motion/EEG file with documented physical units.
4. Allow then stop the microphone; verify the browser recording indicator clears.
5. Change modules during recording and verify capture stops.
6. Sign in as a regular user and confirm Research studio is denied.
7. Confirm existing My Brain Health and participant assessment flows still work.
