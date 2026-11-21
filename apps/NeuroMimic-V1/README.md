# NeuroMimic-V1

Flags explicitly reported or clinician-flagged contributor domains and missing context. It does not independently interpret laboratory values or medications.

Status: separate standalone Python core prototype. Not installed in the Windows BAINP application. No API, frontend, CareLoop delivery, native NeuroGuard adapter, authentication or clinical validation is supplied in this package. Input guard/quality labels are caller assertions, not independently authenticated facts. Do not connect these engines to participant-facing clinical decisions until those adapters and permissions are implemented and tested.

Requires Python 3.10+; standard library only. Run `python -m unittest discover -s NeuroMimic-V1` from the parent folder. Three focused engineering checks passed for this engine. These do not constitute end-to-end or clinical validation.

NeuroMimic and NeuroProof intentionally have separate folders and code. A future integration must map real native contracts rather than assume the illustrative input names already exist. All example IDs are fictional.
