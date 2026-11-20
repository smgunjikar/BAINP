"""Audit a proposed follow-up window; no training, imputation, or MRI edits.

Uses only the Python standard library. Run from the BAINP project folder.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def number(row, field):
    value = row[field].strip()
    if not value:
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"Nonfinite {field}")
    return value


def describe(rows):
    cdr = [number(r, 'later_cdr') - number(r, 'earlier_cdr') for r in rows
           if number(r, 'earlier_cdr') is not None and number(r, 'later_cdr') is not None]
    mmse = [r for r in rows if number(r, 'earlier_mmse') is not None
            and number(r, 'later_mmse') is not None]
    days = [number(r, 'interval_days') for r in rows]
    return {
        'pairs': len(rows), 'participants': len({r['subject'] for r in rows}),
        'complete_mmse_pairs': len(mmse), 'complete_cdr_pairs': len(cdr),
        'cdr_increased': sum(v > 0 for v in cdr),
        'cdr_unchanged': sum(v == 0 for v in cdr),
        'cdr_decreased': sum(v < 0 for v in cdr),
        'median_interval_days': median(days) if days else None,
        'missing_earlier_ses': sum(number(r, 'earlier_ses') is None for r in rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path.home() / 'BAINP_DATA')
    parser.add_argument('--input', type=Path, help='Optional explicit pair CSV')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    source = args.input or args.data_root / 'derived/oasis2/visit_pairs/oasis2_candidate_visit_pairs.csv'
    destination = args.output_dir or args.data_root / 'derived/oasis2/target_feasibility'
    with source.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError('Empty input.')
    seen = set()
    for row in rows:
        key = row['earlier_session'], row['later_session']
        if key in seen:
            raise ValueError('Duplicate pair.')
        seen.add(key)
        for session in key:
            if session.rsplit('_', 1)[0] != row['subject']:
                raise ValueError('Participant mismatch.')
        days = number(row, 'interval_days')
        if days is None or days <= 0:
            raise ValueError('Missing or nonpositive interval.')
        for field in ('mmse', 'cdr', 'nwbv'):
            before, after, delta = [number(row, p + field) for p in ('earlier_', 'later_', 'delta_')]
            if before is not None and after is not None:
                if delta is None or not math.isclose(after - before, delta, abs_tol=1e-10):
                    raise ValueError(f'Inconsistent {field} change.')
            elif delta is not None:
                raise ValueError(f'Change present with missing {field}.')

    # Proposed feasibility window, not a clinically validated or preregistered rule.
    lower, upper, target = 18 * 365.25 / 12, 30 * 365.25 / 12, 2 * 365.25
    eligible = [r for r in rows if lower <= number(r, 'interval_days') <= upper]
    # Choose using timing and IDs only, before examining outcomes or completeness.
    selected = {}
    for row in sorted(eligible, key=lambda r: (
        abs(number(r, 'interval_days') - target), r['earlier_session'], r['later_session'])):
        selected.setdefault(row['subject'], row)
    one_per_subject = [selected[k] for k in sorted(selected)]
    report = {
        'status': 'FEASIBILITY_ONLY_NOT_FINAL_COHORT',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'window': {'months_inclusive': [18, 30], 'days_inclusive': [lower, upper],
                   'integer_days_inclusive': [math.ceil(lower), math.floor(upper)]},
        'selection_rule': 'One supplied candidate pair per participant, nearest 730.5 days; ties resolved by session IDs. Selection precedes outcome completeness filtering.',
        'all_pairs': describe(rows),
        'window_all_pairs': describe(eligible),
        'window_one_pair_per_participant': describe(one_per_subject),
        'participants_without_pair_in_window': len({r['subject'] for r in rows} - set(selected)),
        'proposed_analysis': {
            'primary_candidate': 'Later MMSE within 18–30 months, using earlier-visit predictors; evaluate only complete MMSE pairs.',
            'baseline_comparator': 'Predict later MMSE equals earlier MMSE.',
            'secondary_candidate': 'Observed CDR increase, subject to event-count feasibility; not a diagnosis.',
            'evaluation': 'Participant-level five-fold outer cross-validation, fixed seed 42; use identical folds for comparator and model. Any tuning uses participant-level inner folds. Report MAE and RMSE with participant-bootstrap uncertainty from out-of-fold predictions.',
            'preprocessing': 'Fit imputation and scaling inside training folds only; never impute outcomes.',
            'initial_predictors': ['earlier_age', 'earlier_educ', 'earlier_mmse', 'earlier_cdr'],
            'excluded_from_baseline_features': ['subject', 'session IDs', 'later_*', 'delta_*', 'observed interval', 'QC/completeness flags'],
            'limitations': ['Window is approximate, not exact two-year follow-up.', 'Candidate pairs may omit nonadjacent visit combinations.', 'Chosen earlier visit is a prediction landmark, not necessarily the first visit.', 'Selection depends on observed follow-up availability; cohort selection bias must be reported.', 'Outcome distributions have already been inspected; this is exploratory planning, not preregistration.', 'Small single-cohort analysis needs external validation.'],
        },
        'model_trained': False, 'splits_created': False,
        'mri_qc_status': 'UNCHANGED_UNRESOLVED',
    }
    destination.mkdir(parents=True, exist_ok=True)
    # Preserve existing reports if inputs or rules differ.
    path = destination / 'target_feasibility.json'
    text = json.dumps(report, indent=2) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') != text:
        raise FileExistsError(f'Existing report differs; use a new --output-dir: {path}')
    path.write_text(text, encoding='utf-8')
    print('TARGET FEASIBILITY SUMMARY')
    for name in ('all_pairs', 'window_all_pairs', 'window_one_pair_per_participant'):
        print(name + ': ' + json.dumps(report[name]))
    print('Participants without an eligible pair:', report['participants_without_pair_in_window'])
    print('Report:', path)
    print('No training or splits. Source files and MRI QC unchanged.')


if __name__ == '__main__':
    main()
