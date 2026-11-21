"""Build source-typed evidence and deterministic release statements."""

from hashlib import sha256
import json
from collections import defaultdict
from datetime import datetime

from bainp_guard import VERSION, check_claim, finite


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def stamp(value):
    try:
        time = datetime.fromisoformat(value)
        return time if time.utcoffset() is not None else None
    except (TypeError, ValueError):
        return None


def node(key, kind, claim, title, statement, source, *, eligible=True, **details):
    return dict(id=key, type=kind, claim=claim, title=title, statement=statement,
                source=source, eligible=eligible, **details)


def references():
    return [
        node("aric-vascular", "research_association", "association", "Vascular risk in the ARIC cohort",
             "ARIC reported associations between midlife vascular risk factors and later dementia incidence at a population level.",
             "Gottesman et al., 2017", url="https://pubmed.ncbi.nlm.nih.gov/28783817/"),
        node("who-prevention", "clinical_guidance", "guidance", "Population prevention guidance",
             "WHO provides guidance on risk reduction for adults without dementia. Review applicable health behaviors and conditions with a qualified professional.",
             "WHO dementia risk reduction guidelines, second edition",
             url="https://www.who.int/publications/i/item/9789240123557"),
        node("unknown-mechanism", "unknown", "uncertainty", "Underlying mechanism",
             "The available observations do not establish an underlying disease mechanism or an individual diagnosis.",
             "NeuroGuard scope"),
    ]


def cognitive_comparisons(points):
    groups = defaultdict(list)
    for point in points:
        when = stamp(point.get("at"))
        if (point.get("metric") == "correct" and point.get("status") == "completed"
                and point.get("flags") == [] and point.get("condition_group") and when
                and point.get("session_id") and finite(point.get("value"))):
            groups[point["task"], point["condition_group"]].append((when, point))
    evidence = []
    for (task, group), rows in groups.items():
        rows.sort(key=lambda row: row[0])
        # A repeated or conflicting session entry invalidates this comparison.
        if len(rows) < 2 or len({p["session_id"] for _, p in rows}) != len(rows):
            continue
        (old_time, old), (new_time, new) = rows[-2:]
        if old_time >= new_time:
            continue
        key = "comparison-" + fingerprint([task, group, old, new])[:24]
        text = (f"{task} recorded {old['value']:g} correct responses in the first session and {new['value']:g} in the second "
                "between two completed sessions in the same recorded condition group. This is a descriptive comparison.")
        evidence.append(node(key, "direct_observation", "comparison", "Recorded cognitive task comparison",
                             text, "NeuroCognition X", source_ids=[old["session_id"], new["session_id"]],
                             observed_at=new["at"], condition_group=group))
    return evidence[:10]


def build(snapshot=None, synthetic=False):
    nodes = references()
    coverage = []
    if snapshot:
        coverage = [{k: item.get(k) for k in ("id", "name", "state", "count", "href")}
                    for item in snapshot.get("connections", [])]
        records = [
            record for record in snapshot["records"]
            if record.get("scope") not in ("genomic_summary", "family_history", "molecular_research")
        ]
        records.sort(key=lambda record: stamp(record["payload"]["observed_at"]), reverse=True)
        for record in records[:30]:
            raw = record["payload"]
            key = "bbc-" + fingerprint([record["id"], record.get("sha256"), raw["revision"]])[:24]
            integrity_ok = synthetic or record.get("sha256") == fingerprint(raw)
            if raw["kind"] == "measurement":
                value, unit = raw.get("value"), raw.get("unit")
                exact = raw["qualifier"] == "exact" and finite(value)
                eligible = exact and record["numeric_eligible"] and integrity_ok
                statement = f"{record['label']}: {value:g} {unit} as recorded." if eligible else (
                    f"{record['label']} was withheld by source or quality checks.")
                nodes.append(node(key, "direct_observation", "measurement", record["label"], statement,
                                  "BBC-BE", eligible=eligible,
                                  source_ids=[record["id"]], observed_at=raw["observed_at"],
                                  value=value if eligible else None, unit=unit,
                                  quality=raw["quality"] if integrity_ok else "source_hash_mismatch",
                                  source_revision=raw["revision"]))
            else:
                statement = (f"An authorized {record['label'].lower()} record is available for source review."
                             if not raw.get("needs_review") else "A concern was recorded. Review the original report with a qualified professional.")
                nodes.append(node(key, "clinical_context", "context", record["label"],
                                  statement, "BBC-BE", eligible=raw["quality"] in ("usable", "review") and integrity_ok,
                                  source_ids=[record["id"]], observed_at=raw["observed_at"]))
        for series in snapshot["series"]:
            wearable = [p for p in series["points"] if p["id"].startswith("sense:")]
            if not wearable:
                continue
            point = wearable[-1]
            key = "wear-" + fingerprint([series["id"], point])[:24]
            eligible = point["eligible"] and finite(point["value"])
            text = (f"{series['label']}: {point['value']:g} {series['unit']} as stored by NeuroSense."
                    if eligible else f"{series['label']} was withheld by source or quality checks.")
            nodes.append(node(key, "direct_observation", "measurement", series["label"], text,
                              "NeuroSense", value=point["value"] if eligible else None, unit=series["unit"], eligible=eligible,
                              source_ids=[point["id"]], observed_at=point["at"], known_at=point.get("known_at")))
        nodes.extend(cognitive_comparisons(snapshot["cognitive_points"]))
        sleep_timing = any(
            item["label"] == "Sleep duration"
            for session in snapshot["alignments"] for item in session["known_before_session"]
        )
        if sleep_timing:
            nodes.append(node("sleep-timing-question", "hypothesis", "hypothesis", "Research question",
                              "Could sleep timing or testing conditions explain some variation in recorded performance? Review comparable sessions and confirm source timing.",
                              "BBC-BE timing context"))
    if synthetic:
        nodes.append(node("demo-eeg-quality", "direct_observation", "measurement", "Fictional EEG feature",
                          "The fictional EEG feature is withheld because of a signal-quality flag.",
                          "Fictional NeuroPulse fixture", eligible=False, quality="review"))
    indexed = {item["id"]: item for item in nodes}
    claims = []
    edges = []
    for key, item in indexed.items():
        claim = check_claim(item["claim"], key, indexed, item.get("value") if item["claim"] == "measurement" else None,
                            item.get("unit") if item["claim"] == "measurement" else None)
        claims.append(claim | {"id": "claim-" + key, "type": item["type"]})
        if claim["state"] == "accept":
            edges.append({"source": key, "target": "claim-" + key, "relation": "supports"})
    result = dict(policy_version=VERSION, synthetic=synthetic, nodes=nodes, claims=claims, edges=edges,
                  coverage=coverage, participant_context_available=bool(snapshot),
                  inference_scope="Descriptive research evidence", limits=[
                      "Research sources apply to their studied populations. Registered MRI and EEG links show inventory only.",
                      "Source comparability does not establish clinical decline, causation, diagnosis, or treatment benefit.",
                      "Reference sources are curated. No open-web text can authorize a participant claim.",
                  ])
    result["revision"] = fingerprint(result)
    return result
