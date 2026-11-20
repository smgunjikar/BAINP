# BAINP offline reliability runner
Extract into the BAINP project root. In the bainp environment with scikit-learn installed, run:

    python apps/neuroreliability/research.py reviewed.csv reliability-report.json

Use a pseudonymized CSV for one predefined binary outcome and a single score available before that outcome. Freeze the split before evaluation and record the eligibility and outcome definition separately. Dates must include UTC offsets. Required headers:

    subject,split,measured_at,outcome_at,score,outcome,group,device,quality,review_state,submitter,reviewer,evidence

One row per subject. Split is train or test. Score is 0–1 and outcome is 0 or 1. Quality is usable or flagged. Supply accepted reviewed records with distinct submitter and reviewer identifiers and an evidence reference. These fields record review assertions. Source verification and reviewer authentication belong upstream. Use predefined non-identifying group categories.

The candidate is a one-feature logistic model compared with a training-prevalence baseline on the later test cohort. The report contains aggregate quality counts, calibration bins, discrimination, descriptive group results, and score/device shift. It has no clinical release authority. Evaluation assumes a single frozen test run. It has no authenticated review workflow, live monitoring integration, service failover, or prospective validation.
