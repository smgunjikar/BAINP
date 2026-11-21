# NeuroSim and CareLoop v1

Install NeuroGraph and NeuroGuard first. From the BAINP folder with the
`bainp` Conda environment active, run `Install-NeuroSim-CareLoop.ps1 -Verify`
and restart NeuroAccess. Use the front-page card or visit
`/neurosim?mode=demo` and `/careloop?mode=demo`. The fictional workspace
has no linked participant. Choose a BAINP participant for local active tracking.

NeuroSim matches eligible BBC-BE measurements, NeuroSense observations, and
cognitive observations to curated public discussion topics. It checks scope,
record integrity, quality, source review dates, and NeuroGuard release policy.
The review date is an application policy deadline. The source's population and
link are visible. The scenario explorer compares a fictional baseline and
hypothetical inputs without running a disease or intervention model.

CareLoop stores local concerns and a versioned timeline in the existing
operator database. Explicit case consent is required. Referral, completion,
and outcome events require an operator-supplied external confirmation reference.
A reference records provenance without verifying it with the provider. Cases can
close after an outcome is recorded. Writes are atomic, requests support safe
retry, and stale edits are rejected. Withdrawn cases retain local records but
hide their details and stop sharing. Deleting a linked BAINP participant
cascades to its CareLoop cases. Standalone fictional cases remain separate from
participant-linked data.

Urgent-sign instructions are present in the interface. Selected acute signs
return NeuroGuard escalation and bypass the case queue. An empty checklist does
not rule out an emergency. Outside confirmation and workflow status remain
operator-recorded, and the workspace has no connected provider.

NeuroTwin receives only opted-in, dated outcome and follow-up event markers.
This integration neither sends case notes nor feeds forecast features. Real
clinical deployment would require clinician authentication, independently
approved clinical rules, provider integration, and prospective evaluation.

The optional local model demo reuses the NeuroGraph Ollama planner when
`BAINP_NEUROGRAPH_OLLAMA_MODEL` is configured. Its input is a fictional catalog
of preapproved topic IDs. It cannot write cases or author guidance. Verification
does not require a live model. The engineering checks do not establish clinical
effectiveness or model superiority.
