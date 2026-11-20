"""Independent offline evaluation of locked, fixed-horizon binary predictions."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timedelta
from hashlib import sha256
from io import StringIO
import json
import math
from pathlib import Path
import random
import re
import sys

VERSION = "arena-binary-v1"
FILES = {
    "split.csv": ("participant", "split", "index_at", "latest_feature_at", "label_available_at", "label", "group"),
    "fit.csv": ("model", "stage", "participant"),
    "predictions.csv": ("model", "participant", "probability"),
}
SPLITS = {"train", "validation", "test", "external"}
PROTOCOL_FIELDS = {"schema", "dataset", "dataset_version", "usage_reference", "outcome", "horizon_days",
                   "evaluation_split", "models", "file_sha256"}
HEX = re.compile("[0-9a-f]{64}")
TOKEN = re.compile("[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,79}")


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def read_bytes(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit+1)
    require(len(data) <= limit, "FILE_SIZE_LIMIT")
    return data


def load_table(root, name, hashes):
    raw = read_bytes(root/name, 16*1024*1024)
    require(sha256(raw).hexdigest() == hashes.get(name), "TABLE_HASH_MISMATCH: " + name)
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""))
    require(tuple(reader.fieldnames or ()) == FILES[name], "TABLE_COLUMNS_INVALID: " + name)
    for row in reader:
        require(None not in row and all(value is not None for value in row.values()), "CSV_ROW_INVALID")
        yield row


def timestamp(text):
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        require(value.utcoffset() is not None, "TIMEZONE_REQUIRED")
        return value
    except (OverflowError, ValueError):
        raise Invalid("TIMESTAMP_INVALID") from None


def probability(value):
    try:
        require(not isinstance(value, bool), "PROBABILITY_INVALID")
        parsed = float(value)
    except (TypeError, ValueError):
        raise Invalid("PROBABILITY_INVALID") from None
    require(math.isfinite(parsed) and 0 <= parsed <= 1, "PROBABILITY_INVALID")
    return parsed


def locked_data(root, expected_hash):
    raw = read_bytes(root/"protocol.json", 64*1024)
    require(HEX.fullmatch(expected_hash or "") and sha256(raw).hexdigest() == expected_hash, "PROTOCOL_HASH_MISMATCH")
    policy = json.loads(raw)
    require(isinstance(policy, dict) and set(policy) == PROTOCOL_FIELDS, "PROTOCOL_FIELDS_INVALID")
    require(policy["schema"] == VERSION and policy["evaluation_split"] in ("test", "external"), "PROTOCOL_SCOPE_INVALID")
    require(all(isinstance(policy[k], str) and TOKEN.fullmatch(policy[k])
                for k in ("dataset","dataset_version","usage_reference","outcome")), "PROTOCOL_METADATA_INVALID")
    days = policy["horizon_days"]
    require(type(days) is int and 1 <= days <= 3650, "HORIZON_INVALID")
    models = policy["models"]
    require(isinstance(models, list) and 1 <= len(models) <= 6, "MODEL_COUNT_INVALID")
    thresholds = {}
    for model in models:
        require(isinstance(model, dict) and set(model) == {"id","threshold","artifact_sha256"}, "MODEL_FIELDS_INVALID")
        name = model["id"]
        require(isinstance(name, str) and TOKEN.fullmatch(name) and name not in thresholds, "MODEL_ID_INVALID")
        require(isinstance(model["artifact_sha256"],str) and HEX.fullmatch(model["artifact_sha256"]), "ARTIFACT_HASH_INVALID")
        thresholds[name] = probability(model["threshold"])

    hashes = policy["file_sha256"]
    require(isinstance(hashes, dict) and set(hashes) == set(FILES), "FILE_MANIFEST_INVALID")
    people = {}
    for row in load_table(root,"split.csv",hashes):
        pid = row["participant"]
        require(TOKEN.fullmatch(pid) and pid not in people, "PARTICIPANT_DUPLICATE_OR_INVALID")
        require(row["split"] in SPLITS and row["label"] in ("0","1"), "SPLIT_OR_LABEL_INVALID")
        index = timestamp(row["index_at"])
        require(timestamp(row["latest_feature_at"]) <= index, "FUTURE_FEATURE")
        require(timestamp(row["label_available_at"]) >= index + timedelta(days=days), "HORIZON_LABEL_NOT_COMPLETE")
        require(not row["group"] or TOKEN.fullmatch(row["group"]), "GROUP_INVALID")
        people[pid] = row
    selected = {pid for pid,row in people.items() if row["split"] == policy["evaluation_split"]}
    require(2 <= len(selected) <= 10000, "EVALUATION_SIZE_INVALID")

    stages = defaultdict(set)
    used = set()
    for row in load_table(root,"fit.csv",hashes):
        name, stage, pid = row["model"], row["stage"], row["participant"]
        require(name in thresholds and pid in people and stage in ("fit","preprocess","tune"), "FIT_MANIFEST_INVALID")
        expected = "validation" if stage == "tune" else "train"
        require(people[pid]["split"] == expected, "FIT_OR_TUNING_SPLIT_VIOLATION")
        require((name,stage,pid) not in used, "FIT_MANIFEST_DUPLICATE")
        used.add((name,stage,pid))
        stages[name].add(stage)
    require(all({"fit","preprocess"} <= stages[name] for name in thresholds), "FIT_AND_PREPROCESS_PROVENANCE_REQUIRED")

    scores = {name:{} for name in thresholds}
    for row in load_table(root,"predictions.csv",hashes):
        name,pid = row["model"],row["participant"]
        require(name in scores and pid in selected and pid not in scores[name], "PREDICTION_SCOPE_OR_DUPLICATE")
        scores[name][pid] = probability(row["probability"])
    require(all(set(items) == selected for items in scores.values()), "MISSING_HELD_OUT_PREDICTIONS")
    ids = sorted(selected)
    labels = [int(people[pid]["label"]) for pid in ids]
    require(set(labels) == {0,1}, "BOTH_OUTCOMES_REQUIRED")
    groups = [people[pid]["group"] for pid in ids]
    return policy, thresholds, labels, groups, {name:[values[pid] for pid in ids] for name,values in scores.items()}


def metrics(labels, scores, threshold):
    positive = sum(labels)
    negative = len(labels) - positive
    tp = sum(y == 1 and p >= threshold for y,p in zip(labels,scores))
    tn = sum(y == 0 and p < threshold for y,p in zip(labels,scores))
    ranked = sorted(zip(scores,labels))
    start = 0
    total = 0.0
    while start < len(ranked):
        end = start + 1
        while end < len(ranked) and ranked[end][0] == ranked[start][0]:
            end += 1
        total += (start + 1 + end) / 2 * sum(y for _,y in ranked[start:end])
        start = end
    return {
        "auroc": (total - positive*(positive+1)/2)/(positive*negative),
        "brier": sum((y-p)**2 for y,p in zip(labels,scores))/len(labels),
        "sensitivity": tp/positive, "specificity": tn/negative,
    }


def calibration(labels, scores):
    bins = defaultdict(list)
    for y,p in zip(labels,scores):
        bins[min(9,int(p*10))].append((y,p))
    return [dict(bin=i, n=len(rows), mean_probability=sum(p for _,p in rows)/len(rows),
                 observed_frequency=sum(y for y,_ in rows)/len(rows)) for i,rows in sorted(bins.items()) if len(rows) >= 5]


def interval(samples):
    samples = sorted(samples)
    return [samples[int(.025*(len(samples)-1))],samples[math.ceil(.975*(len(samples)-1))]]


def evaluate(root, expected_hash, draws=300, seed=42):
    require(type(draws) is int and 100 <= draws <= 2000, "BOOTSTRAP_COUNT_INVALID")
    protocol, thresholds, labels, groups, predictions = locked_data(root,expected_hash)
    result = {name:dict(metrics=metrics(labels,scores,thresholds[name]),calibration=calibration(labels,scores))
              for name,scores in predictions.items()}
    paired = {name:defaultdict(list) for name in predictions}
    samples = {name:defaultdict(list) for name in predictions}
    group_rows = defaultdict(list)
    for i,group in enumerate(groups):
        if group:
            group_rows[group].append(i)
    for name,scores in predictions.items():
        result[name]["subgroups"] = {
            group: {"n":len(indexes),"metrics":metrics([labels[i] for i in indexes],
                [scores[i] for i in indexes],thresholds[name])}
            for group,indexes in group_rows.items() if len(indexes) >= 20
            and 5 <= sum(labels[i] for i in indexes) <= len(indexes)-5
        }
    rng = random.Random(seed)
    baseline = next(iter(predictions))
    by_class = [[i for i,y in enumerate(labels) if y == label] for label in (0,1)]
    for _ in range(draws):
        indexes = [i for group in by_class for i in rng.choices(group,k=len(group))]
        boot_labels = [labels[i] for i in indexes]
        boot_metrics = {name:metrics(boot_labels,[scores[i] for i in indexes],thresholds[name])
                        for name,scores in predictions.items()}
        for name,values in boot_metrics.items():
            for metric,value in values.items():
                samples[name][metric].append(value)
                if name != baseline:
                    paired[name][metric].append(value-boot_metrics[baseline][metric])
    for name,entry in result.items():
        entry["conditional_95_intervals"] = {key:interval(values) for key,values in samples[name].items()}
        entry["paired_delta_vs_baseline_95_intervals"] = {key:interval(values) for key,values in paired[name].items()}
    return dict(protocol=protocol, protocol_sha256=expected_hash, evaluator=VERSION,
                evaluator_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                n=len(labels), positive=sum(labels), reference_model=baseline, models=result,
                bootstrap={"draws":draws,"seed":seed,"method":"paired participant bootstrap stratified by outcome"},
                limitations=["Intervals are conditional on the submitted fixed predictions.",
                    "Manifest checks depend on verified participant identity and honest feature-time and fit provenance.",
                    "Repeat access to held-out data and external independence require reviewer controls.",
                    "Small subgroups and calibration bins with fewer than 5 records are omitted.",
                    "This fixed-horizon evaluator does not handle censoring or authorize release."],
                release_authorized=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(evaluate(args.bundle,args.protocol_sha256),indent=2,allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError, OverflowError, csv.Error) as error:
        code = str(error) if isinstance(error,Invalid) else "MALFORMED_OR_UNREADABLE_BUNDLE"
        print("Evaluation blocked: " + code, file=sys.stderr)
        sys.exit(2)
