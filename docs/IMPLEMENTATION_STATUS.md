# BAINP implementation tracker

Update statuses only after the stated verification succeeds.

| Component | Status | Evidence / remaining gate |
|---|---|---|
| Synthetic provenance contract v1 | Verified locally | Required-field and metric/unit checks passed |
| Synthetic cohort generator v1 | Verified locally | Repeated identical SHA-256; 5 participants, 15 encounters, 28 observations |
| Participant repair and naming | Verification pending | Run participant-flow installer verification |
| Synthetic PostgreSQL import | Pending | Confirm migration head, add schema, import twice and verify no duplicates |
| Dataset registry | Initial inventory | Research versions, permissions and artifact QC still require review |
| C00 intake and safety bypass | Pending | Implement and test before task execution |
| C01-C06 battery | Pending | Current attention practice does not constitute the complete battery |
| NeuroGuard comparability rules | Pending | Versioned rules and adverse-scenario tests required |
| Longitudinal interpretation | Pending | Reference parameters required for RCI interpretation |
| Evidence cards and CareLoop | Pending | Auditable review transitions required |
| Research integrations | Pending | Dataset-specific provenance, evaluation and release checks required |
| Clean deployment | Pending | Verify in an isolated disposable Compose project |

## GitHub policy

Commit application source, migrations, tests, schemas, documentation,
dependency manifests/lockfiles, and reviewed synthetic fixtures.

Exclude secrets, local environment files, raw research data, participant-level
research derivatives, model weights, local processing outputs, dependency
directories, build outputs, and patch backups.

An ignore rule does not remove files already committed.
Do not use git add . before reviewing git status and the staged diff.
Do not push until staged contents have been reviewed.

Keep the existing BAINP_DATA location while OASIS processing is running.