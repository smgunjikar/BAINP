# NeuroAccess — Medical Profile update

## Visible changes
My profile now contains a prominent **Health & Medical ID** row next to Personal details, Accessibility, Display and Assistance. Its editor opens directly in the profile workspace. New registration continues from the first four profile steps into this health step. Optional health fields can be left blank.

Personal details provides date of birth and calculated age. The server derives age on profile saves; the health view derives current age on every load. Existing assessment snapshots are retained. The existing adult prototype age range of 18–110 remains enforced. Date-of-birth profiles use an additive profile field; source-only rollback to older versions may prevent editing them. Reapply this release rather than removing user data.

Health fields include sex, height, weight, blood group, optional Fitzpatrick I–VI / unknown, wheelchair use, pregnancy notes, medication status and details, medications affecting heart rate, allergy status and details, current conditions, emergency contact and additional notes. Fitzpatrick type is self-reported, not inferred from an image and not used as a cognitive-risk score.

## Storage and consent
New health records are keyed to participant ID inside the authenticated workspace database. A second administrator test participant does not inherit the first participant's health data. Saves require explicit optional-health storage consent. Permission policy, timestamp, grant/withdrawal history and revisions are recorded. Stale writes/deletes are rejected. Clearing optional health records withdraws this storage consent; backups and exported copies are not remotely erased.

Previous account-wide health records are preserved separately. Review, intentionally copy compatible fields into a selected participant draft, or clear the old record through the previous-record section. Nothing is silently assigned. Birth date must be entered through Personal details. Profile data and consent changes still follow existing account authorization; no new public access path is added.

## Medication names
Optional online name lookup uses NLM RxNorm getDrugs through the authenticated backend. The user must agree to send the search term. No profile payload is sent to NLM. A chosen result is added to the medication draft and must be confirmed and saved. Manual entry remains possible. This is not an offline national drug database, an exhaustive Indian brand catalogue, prescribing support, dosing advice, an interaction checker or a guarantee of availability. External lookup failure returns a clear error. API response parsing was tested with fixtures, not a live production service.

## Medical ID
The user selects fields and separately confirms file export. All sharing fields default off. A standalone printable HTML card is generated from saved fields, with text safely inserted and a restrictive content security policy. It has no tracking, scripts, remote images or public URL. It is self-reported, not clinically verified. Anyone receiving the file can read it; recipient copies cannot be revoked. It does not call emergency services or appear on a phone lock screen. Use the browser Print command to print or save PDF.

## Export
Confirmed workspace export includes all accessible tables in the current workspace records database, with an explicit scope manifest. It includes available profile, assessment, check-in, workflow, consent and health records. Credentials/security fields are excluded. This does not export other workspace databases, raw files stored elsewhere (e.g. MRI/EEG/wearables), cloud accounts or backup files. Admin users export the currently opened workspace, which may contain multiple test participants. Oversized tables cause failure rather than a silently partial export. Export is logged.

## Early concern capture
Optional questions record memory/thinking changes, onset, daily function, sleep, mood, family history, hearing/vision changes, falls/balance, substance context and notes for a clinician. They do not form a validated screening scale or produce a disease label, risk score, triage clearance or treatment recommendation. Existing NeuroGuard and NeuroQuest checks remain independent. No new cognitive tasks or corrected NeuroQuest repeat execution are claimed.

## Hindi
The previous Hindi interface remains, with additional labels for the new fields, medication search and export controls. Some dynamic status/error text and other engines remain English. Hindi UI does not imply a validated Hindi cognitive assessment protocol.

## Tests and limits
- 34 HTTP checks cover DOB validation, private participant records, consent, stale revisions, allowed values, medication response/offline fixtures, export isolation and clearing.
- Existing account suite: 88 HTTP checks plus concurrent isolation, persistence, token storage and append-only audit assertions.
- Five JavaScript calendar-age cases, new Hindi-label checks, Python compilation and JavaScript module syntax checks.
- Source installer dry-run, install, repeat install and byte-exact source restore against uploaded original, readiness update and Profile-Hindi update.
- No live Windows installation or visual browser verification is claimed. Chromium could not launch in this environment previously. External medication service availability has not been verified from this environment.

## References consulted
- NLM RxNorm getDrugs: https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.getDrugs.html
- NIA cognitive-impairment assessment: https://www.nia.nih.gov/health/health-care-professionals-information/assessing-cognitive-impairment-older-patients
- DermNet Fitzpatrick phototype: https://dermnetnz.org/topics/skin-phototype
