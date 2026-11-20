# NeuroGraph and NeuroGuard v1

Install from the BAINP repository in the active `bainp` Conda environment with
`Install-NeuroGraph-NeuroGuard.ps1 -Verify`. Restart NeuroAccess, then open the
new card on the BAINP front page. The evidence demo is fictional. Select an active
participant to use authorized BBC-BE sources.

## Implemented controls

| Stage | Control |
| --- | --- |
| Read evidence | Match participant and mode. Apply BBC-BE consent. Recheck BBC-BE record digests. Omit sensitive genomic, family and experimental molecular categories from this report. |
| Check suitability | Honor stored quality and eligibility. Compare only completed, unflagged cognitive observations in the same recorded condition group with distinct sessions. |
| Release report | Require an allowed claim type and current evidence. Match exact numeric values and units. Apply the final NeuroTwin research forecast envelope check when the supported Twin policy is installed. |
| Export | Require login and a fresh report revision. Export accepted claims and their source evidence only. Audit participant export and claim decisions without recording candidate values. |
| Urgent signs | Show the emergency instructions directly on the webpage. The independent structured endpoint needs neither a model nor a participant identity. No symptom history is stored by this workspace. |

The graph separates direct observations, clinical context, research associations,
clinical guidance, hypotheses and unknowns. Curated references are fixed in code.
MRI and EEG coverage describes registered sources. Their image and signal quality
remain with their processing modules. A matching digest checks local consistency,
not source authenticity or the validity of an assay. Same-condition comparisons
do not establish clinical decline. Browser evidence is a read-time snapshot.
Refresh for later changes. An export checks the revision again at request time.

The optional Ollama planner calls loopback port 11434. Set
`BAINP_NEUROGRAPH_OLLAMA_MODEL` to the tag of an installed local model before
starting BAINP. Only a fixed fictional catalog of claim IDs and evidence types is
sent. The response may select accepted IDs. It cannot provide report prose,
values or medical actions. A disabled or failed model leaves the deterministic
workspace available. No live model or comparative model quality is certified.

The installation adds an independent research report gate and augments the existing
NeuroTwin forecast gate. It does not interpose on every legacy endpoint. Independent
modality validators, external cohort evaluation, drift and subgroup monitoring,
clinical deployment authorization and operating-system access controls remain
separate work. The local operator login is not a clinical role or study-level
access policy. Keep restricted cohort data subject to its data-use agreements.

The verification suite runs isolated policy scenarios and HTTP integration checks
against a temporary database. It is an engineering benchmark, not clinical
validation. The optional model transport is mocked during verification.
