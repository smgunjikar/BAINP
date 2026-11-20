"""Offline reliability evaluation for one binary research outcome."""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import mean
import sys

FIELDS = {"subject", "split", "measured_at", "outcome_at", "score", "outcome",
          "group", "device", "quality", "review_state", "submitter", "reviewer", "evidence"}
MIN_GROUP = 20


def load(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if len(reader.fieldnames or []) != len(FIELDS) or set(reader.fieldnames or []) != FIELDS:
        raise ValueError("Unexpected CSV columns")
    parts = {"train": [], "test": []}
    seen = set()
    for number, row in enumerate(reader, 2):
        try:
            if None in row or any(not value or not value.strip() for value in row.values()):
                raise ValueError("Missing input")
            if row["subject"] in seen:
                raise ValueError("Duplicate participant")
            if (row["review_state"] != "accepted" or
                    row["submitter"].strip().casefold() == row["reviewer"].strip().casefold()):
                raise ValueError("Independent accepted review required")
            measured, outcome = (datetime.fromisoformat(row[key]) for key in ("measured_at", "outcome_at"))
            if measured.utcoffset() is None or outcome.utcoffset() is None or measured >= outcome:
                raise ValueError("Timezone-aware measurement must precede outcome")
            score = float(row["score"])
            if not math.isfinite(score) or not 0 <= score <= 1 or row["outcome"] not in {"0", "1"}:
                raise ValueError("Invalid score or outcome")
            if row["quality"] not in {"usable", "flagged"}:
                raise ValueError("Invalid quality state")
            parts[row["split"]].append(dict(row, score=score, outcome=int(row["outcome"]),
                                            measured_at=measured, outcome_at=outcome))
            seen.add(row["subject"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid research input on row {number}: {exc}") from None
    if not all(parts.values()):
        raise ValueError("Both train and test are required")
    if max(r["outcome_at"] for r in parts["train"]) >= min(r["measured_at"] for r in parts["test"]):
        raise ValueError("Training outcomes must precede every test measurement")
    return parts


def metrics(y, probabilities):
    from sklearn.metrics import roc_auc_score
    bins = []
    for index in range(5):
        pairs = [(p, outcome) for outcome, p in zip(y, probabilities)
                 if min(4, int(p * 5)) == index]
        bins.append({"bin": index, "n": len(pairs),
                     "mean_probability": mean(p for p, _ in pairs) if pairs else None,
                     "observed_fraction": mean(v for _, v in pairs) if pairs else None})
    positives = sum(y)
    negatives = len(y) - positives
    return {"n": len(y), "brier": mean((p - v)**2 for p, v in zip(probabilities, y)),
            "auroc": roc_auc_score(y, probabilities) if positives and negatives else None,
            "sensitivity_at_0_5": sum(p >= .5 and v == 1 for p, v in zip(probabilities, y))/positives if positives else None,
            "specificity_at_0_5": sum(p < .5 and v == 0 for p, v in zip(probabilities, y))/negatives if negatives else None,
            "calibration": bins}


def evaluate(parts):
    from sklearn.linear_model import LogisticRegression
    from sklearn import __version__

    train, test = parts["train"], parts["test"]
    usable_train = [r for r in train if r["quality"] == "usable"]
    usable_test = [r for r in test if r["quality"] == "usable"]
    y_train = [r["outcome"] for r in usable_train]
    if min(y_train.count(0), y_train.count(1)) < 5 or not usable_test:
        raise ValueError("Need at least five usable training rows per class and usable test rows")
    model = LogisticRegression(solver="lbfgs")
    model.fit([[r["score"]] for r in usable_train], y_train)
    probabilities = model.predict_proba([[r["score"]] for r in usable_test])[:, 1].tolist()
    outcomes = [r["outcome"] for r in usable_test]
    prior = mean(y_train)
    groups = {}
    for group in sorted({r["group"] for r in test}):
        all_group = [r for r in test if r["group"] == group]
        pairs = [(r["outcome"], p) for r, p in zip(usable_test, probabilities) if r["group"] == group]
        groups[group] = ({"state": "insufficient_support"} if len(pairs) < MIN_GROUP or
                         min(sum(v for v, _ in pairs), sum(1-v for v, _ in pairs)) < 5 else
                         {"state": "descriptive", "usable_fraction": len(pairs)/len(all_group),
                          "metrics": metrics(*zip(*pairs))})
    score_shift = mean(r["score"] for r in test) - mean(r["score"] for r in train)
    device_train = {r["device"] for r in train}
    return {
        "release_authorized": False, "scope": "offline research evaluation",
        "sklearn_version": __version__,
        "candidate": {"coefficient": float(model.coef_[0, 0]), "intercept": float(model.intercept_[0]),
                      "held_out": metrics(outcomes, probabilities)},
        "baseline_held_out": metrics(outcomes, [prior] * len(outcomes)),
        "groups": groups,
        "monitoring": {"train_rows": len(train), "test_rows": len(test),
                       "train_flagged": len(train)-len(usable_train), "test_flagged": len(test)-len(usable_test)},
        "drift": {"mean_score_change": score_shift, "unseen_test_devices": len({r["device"] for r in test}-device_train),
                  "mean_shift_flag_at_0_10": abs(score_shift) >= .10,
                  "interpretation": "Descriptive train-to-test comparison. Threshold is a research heuristic."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reviewed_csv", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        raw = args.reviewed_csv.read_bytes()
        report = evaluate(load(raw))
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        content = json.dumps(report, indent=2, allow_nan=False)
        with args.report.open("x", encoding="utf-8") as stream:
            stream.write(content + "\n")
    except (ValueError, OSError) as exc:
        sys.exit(str(exc))
    print("Wrote offline evaluation report:", args.report)


if __name__ == "__main__":
    main()
