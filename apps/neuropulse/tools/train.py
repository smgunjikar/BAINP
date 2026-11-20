"""Fast within-cohort EEG research baseline. One row per participant."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import analyze
from embedded import read_embedded

BANDS = ('delta', 'theta', 'alpha', 'beta')


def evaluate(x, y):
    labels, counts = np.unique(y, return_counts=True)
    if len(labels) < 2 or min(counts) < 5:
        raise ValueError('At least five usable participants per class are required.')
    folds = StratifiedKFold(5, shuffle=True, random_state=42)
    results = {}
    for name, model in [
        ('majority', DummyClassifier(strategy='most_frequent')),
        ('spectral_logistic', make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))),
    ]:
        predictions = cross_val_predict(model, x, y, cv=folds)
        results[name] = {
            'balanced_accuracy': balanced_accuracy_score(y, predictions),
            'confusion_matrix': confusion_matrix(y, predictions, labels=labels).tolist(),
        }
    return {'labels': labels.tolist(), 'counts': counts.tolist(), 'results': results}


def extract(root, limit_per_group=None):

    with (root / 'participants.tsv').open(encoding='utf-8-sig') as stream:
        participants = list(csv.DictReader(stream, delimiter='\t'))
    identifiers = [row['participant_id'] for row in participants]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate participants.')
    x, y, audit = [], [], []
    montage = None
    if limit_per_group is not None:
        # Fixed, outcome-independent ordering within each supplied class.
        participants = sorted(participants, key=lambda row: row['participant_id'])
        participants = [row for group in ('A', 'F', 'C')
                        for row in [p for p in participants if p['Group'] == group][:limit_per_group]]
    for row in participants:
        subject, group = row['participant_id'], row['Group']
        if group not in {'A', 'F', 'C'}:
            raise ValueError(f'Unexpected cohort label {group!r}')
        files = sorted((root / subject / 'eeg').glob('*_task-eyesclosed_eeg.set'))
        if len(files) != 1:
            raise ValueError(f'Expected one materialized eyes-closed recording for {subject}.')
        path = files[0]
        data, sf, names, excluded = read_embedded(path)
        if montage is None:
            montage = set(names)
        if set(names) != montage:
            raise ValueError(f'Montage differs for {subject}.')
        _, features, _ = analyze(data[:, :round(60*sf)].astype(float)*1e-6,
                                 sf, names, excluded, min_usable_channels=10)
        usable = len({f['start_s'] for f in features}) >= 3
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        audit.append({'participant': subject, 'included': usable, 'feature_rows': len(features),
                      'source_sha256': digest})
        if usable:
            x.append([float(np.median([f[band+'_relative'] for f in features])) for band in BANDS])
            y.append(group)
    if set(y) != {'A', 'F', 'C'}:
        raise ValueError('All three cohort groups must survive quality filtering.')
    return x, y, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('report', type=Path)
    parser.add_argument('--limit-per-group', type=int, choices=range(5, 24))
    args = parser.parse_args()
    x, y, audit = extract(args.dataset, args.limit_per_group)
    report = evaluate(x, y)
    report.update(dataset='OpenNeuro ds004504', validation='5-fold participant-stratified internal CV',
                  segment_seconds=60, features=list(BANDS), participants=audit,
                  quality_policy='At least 10 usable channels per window and three usable windows per participant.',
                  metadata_sha256=hashlib.sha256((args.dataset/'participants.tsv').read_bytes()).hexdigest(),
                  intended_use='Cohort research only. No clinical inference or external validation.')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print('Wrote research report', args.report)


if __name__ == '__main__':
    main()
