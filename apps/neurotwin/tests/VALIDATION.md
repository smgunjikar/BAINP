# NeuroTwin X V2 engineering validation

Fifteen isolated API/storage/state tests passed against a temporary BAINP installation:
authentication/CSRF, mode separation, source retries/revisions, unit/quality enforcement,
complete coherent demo profiles, cross-profile EEG access rejection, source updates,
neural covariance validation, inline MRI identity gates, FreeSurfer package/source hashes,
unlinking, cascade deletion, condition grouping, trend abstention and source fingerprints.
No private participant database was used.

Four numerical/research checks passed on invented arrays and cohorts: 10-Hz spectral
recovery with flat/BAD-window rejection; offline candidate evaluation with held-out and
external synthetic participants; independent policy/synthetic-model/hash/population gates;
censoring/competing-death/duplicate handling; and the two FreeSurfer stats table formats
(the candidate/gate checks are one test). These checks do not constitute clinical validation.

JavaScript syntax checks passed. A simulated DOM exercised four workspace cards, tabs,
synthetic anatomy labels, charts, neural source/covariance display, scenario queries,
profile switching, stale-data preservation and evidence export. Surface shaders compiled
and linked in Mesa OpenGL ES 3. The existing MRI volume shader/mask behavior was checked
with an actual offscreen GPU draw, including reproduction of the old byte-1 mask failure.

The installer was applied to the V1 test app and the NeuroVision-upgraded app. Existing
authenticated NeuroVision import-worker and new NeuroTwin endpoints coexist. A second
identical installation changed zero files. The PowerShell wrapper itself has not been run
under Windows. Full browser rendering was unavailable in this environment; target Windows
layout/device/GPU behavior still needs verification.

MNE was unavailable in this build environment. Therefore real EEGLAB/FIF/EDF import was
not exercised; the NumPy/SciPy numerical processing function was tested separately.
No authentic FreeSurfer subject or ADNI progression cohort was processed here. FreeSurfer
package integration was tested using temporary invented anatomy and stats-format fixtures.
The installer contains no deployed trained clinical model or live EEG hardware collector.
