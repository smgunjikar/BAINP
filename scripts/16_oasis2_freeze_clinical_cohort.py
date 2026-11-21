"""Freeze exploratory MMSE cohort and balanced participant folds (standard library).

No fitting, imputation, MRI loading, or changes to source files.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path

FEATURES = ['earlier_age', 'earlier_educ', 'earlier_mmse', 'earlier_cdr']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(row, key):
    value = row[key].strip()
    if not value:
        return None
    result = float(value)
    require(math.isfinite(result), f'Nonfinite {key}')
    return result


def csv_bytes(fields, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path.home() / 'BAINP_DATA')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--feasibility-report', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    base = args.data_root / 'derived/oasis2'
    source = args.input or base / 'visit_pairs/oasis2_candidate_visit_pairs.csv'
    report_path = args.feasibility_report or base / 'target_feasibility/target_feasibility.json'
    destination = args.output_dir or base / 'clinical_cohort_v1'
    report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    require(digest == report['source_sha256'], 'Input differs from Step 15. Re-run feasibility in a new output directory.')
    require(report['window']['days_inclusive'] == [547.875, 913.125], 'Unexpected follow-up window.')
    with source.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        source_fields = reader.fieldnames
        rows = list(reader)
    require(bool(rows), 'Empty input.')
    seen = set()
    for row in rows:
        pair = (row['earlier_session'], row['later_session'])
        require(pair not in seen, 'Duplicate pair.')
        seen.add(pair)
        require(all(s.rsplit('_', 1)[0] == row['subject'] for s in pair), 'Participant mismatch.')
        days = number(row, 'interval_days')
        require(days is not None and days > 0, 'Invalid follow-up interval.')
        for field in FEATURES + ['later_mmse', 'later_cdr']:
            number(row, field)
        for field in ['mmse', 'cdr', 'nwbv']:
            before, after, delta = [number(row, prefix + field) for prefix in ['earlier_', 'later_', 'delta_']]
            if before is not None and after is not None:
                require(delta is not None and math.isclose(after-before, delta, abs_tol=1e-10), 'Inconsistent score difference.')
            else:
                require(delta is None, 'Delta with missing source score.')
    subjects = sorted({row['subject'] for row in rows})
    require(len(rows) == report['all_pairs']['pairs'] and len(subjects) == report['all_pairs']['participants'], 'Step 15 counts differ.')
    window = [r for r in rows if 547.875 <= number(r, 'interval_days') <= 913.125]
    chosen = {}
    for row in sorted(window, key=lambda r: (abs(number(r, 'interval_days')-730.5), r['earlier_session'], r['later_session'])):
        chosen.setdefault(row['subject'], row)
    selected = [chosen[s] for s in sorted(chosen)]
    # Never select an alternative pair based on outcome availability.
    cohort = [r for r in selected if number(r, 'earlier_mmse') is not None and number(r, 'later_mmse') is not None]
    require(len(selected) == report['window_one_pair_per_participant']['pairs'], 'Selection count differs.')
    require(len(cohort) == report['window_one_pair_per_participant']['complete_mmse_pairs'], 'MMSE count differs.')
    require(len(cohort) >= 5, 'Not enough participants for five folds.')
    # Fixed seeded hash ordering avoids dependence on Python random versions.
    ordered = sorted((r['subject'] for r in cohort), key=lambda s: (hashlib.sha256(('42|' + s).encode()).hexdigest(), s))
    fold = {s: 1 + i % 5 for i, s in enumerate(ordered)}
    require(len(fold) == len(cohort), 'Repeated participant in primary cohort.')
    fold_rows = [{'subject': s, 'outer_fold': fold[s]} for s in sorted(fold)]
    flow = []
    for s in subjects:
        r = chosen.get(s)
        status = 'INCLUDED_MMSE' if s in fold else ('EXCLUDED_MISSING_MMSE' if r else 'NO_CANDIDATE_PAIR_IN_WINDOW')
        flow.append({'subject': s, 'status': status, 'earlier_session': r['earlier_session'] if r else '', 'later_session': r['later_session'] if r else ''})
    feature_rows = [{'subject': r['subject'], **{f: number(r, f) for f in FEATURES}} for r in cohort]
    target_rows = [{'subject': r['subject'], 'later_mmse': number(r, 'later_mmse')} for r in cohort]
    metadata = [{k: r[k] for k in ['subject', 'earlier_session', 'later_session', 'interval_days']} for r in cohort]
    fold_summary = []
    for k in range(1, 6):
        test = {s for s in fold if fold[s] == k}
        train = set(fold) - test
        require(not train.intersection(test) and train | test == set(fold), 'Fold leakage.')
        fold_summary.append({'fold': k, 'train_participants': len(train), 'test_participants': len(test)})
    plan = {
        'status': 'FROZEN_EXPLORATORY_CLINICAL_COHORT_V1',
        'source_sha256': digest,
        'feasibility_report_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'selection_rule': report['selection_rule'],
        'window_days_inclusive': [547.875, 913.125],
        'cohort_flow': dict(Counter(r['status'] for r in flow)),
        'primary_participants': len(cohort),
        'predictors': FEATURES,
        'predictor_missing_counts': {f: sum(number(r, f) is None for r in cohort) for f in FEATURES},
        'outcome': 'later_mmse',
        'fold_method': 'Sort participants by SHA256 of 42|subject, then round-robin into five folds; no outcome stratification.',
        'fold_summary': fold_summary,
        'next_analysis': {
            'comparator': 'Predicted later MMSE = earlier MMSE.',
            'candidate_model': 'Ridge regression with alpha chosen only in inner participant folds.',
            'training_only_preprocessing': 'Median imputation and standardization inside every inner and outer training fold.',
            'primary_metric': 'Out-of-fold MAE; compare paired errors with persistence comparator.',
            'secondary_metric': 'Out-of-fold RMSE.',
            'uncertainty': 'Participant bootstrap of fixed out-of-fold paired predictions; conditional uncertainty, not full model-refitting variability.',
            'forbidden_predictors': ['subject', 'session IDs', 'later_*', 'delta_*', 'observed interval', 'fold assignment', 'QC flags'],
        },
        'limitations': report['proposed_analysis']['limitations'] + [
            'Raw MRI QC remains unresolved. This cohort is clinical-only; it is not approved for MRI modeling.',
            'MMSE is a cognitive score, not an Alzheimer diagnosis.',
            'CDR classification is deferred; the 105 selected pairs contain only 15 increases.',
        ],
        'model_trained': False, 'splits_created': True, 'mri_qc_status': 'UNCHANGED_UNRESOLVED',
    }
    outputs = {
        'selected_window_pairs.csv': csv_bytes(source_fields, selected),
        'clinical_features.csv': csv_bytes(['subject'] + FEATURES, feature_rows),
        'clinical_targets.csv': csv_bytes(['subject', 'later_mmse'], target_rows),
        'pair_metadata.csv': csv_bytes(['subject', 'earlier_session', 'later_session', 'interval_days'], metadata),
        'participant_folds.csv': csv_bytes(['subject', 'outer_fold'], fold_rows),
        'participant_flow.csv': csv_bytes(['subject', 'status', 'earlier_session', 'later_session'], flow),
    }
    plan['output_sha256'] = {name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()}
    outputs['analysis_plan.json'] = (json.dumps(plan, indent=2) + '\n').encode()
    # Check every path before writing any; reruns may only reproduce identical files.
    for name, data in outputs.items():
        path = destination / name
        require(not path.exists() or path.read_bytes() == data, f'Existing output differs: {path}. Choose a new --output-dir.')
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        path = destination / name
        if not path.exists():
            with path.open('xb') as handle:
                handle.write(data)
    print('CLINICAL COHORT SUMMARY')
    print('Window-selected participants:', len(selected))
    print('Primary MMSE participants:', len(cohort))
    print('Participant flow:', plan['cohort_flow'])
    print('Predictor missing counts:', plan['predictor_missing_counts'])
    for row in fold_summary:
        print('Fold:', row)
    print('Output:', destination)
    print('No training. MRI files and QC trackers unchanged.')


if __name__ == '__main__':
    main()
