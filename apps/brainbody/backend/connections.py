"""Read-only source inventory for the BBC-BE workspace."""
from urllib.parse import urlencode

from serve_frontend import ASSETS, ROOT


def workspace_links(result):
    identity = result["identity"]
    mode = identity["mode"]
    if result["synthetic"]:
        twin_query = {"mode": "demo", "profile": result["demo_profile"]}
        participant_query = None
    else:
        twin_query = participant_query = {"mode": mode, "person": identity["participant_id"]}
        if mode == "demo":
            twin_query = {**participant_query, "profile": "selected"}

    def path(route, query):
        asset = ASSETS.get(route)
        if asset and (ROOT / asset[0]).is_file():
            return route + "?" + urlencode(query)
        return None

    return {
        "cognition": path("/cognition-dashboard", participant_query) if participant_query else None,
        "wearable": path("/sense-monitor", participant_query) if participant_query else None,
        "twin": path("/neurotwin", twin_query),
        "anatomy": path("/neurotwin", {**twin_query, "view": "anatomical"}),
        "neural": path("/neurotwin", {**twin_query, "view": "neural"}),
        "governance": path("/neurotwin", {**twin_query, "view": "governance"}),
        "imaging_research": path("/neurovision", {"mode": mode}),
    }


def source_inventory(store, result):
    """Count registered records, without retrieving their measurements or payloads."""
    links = workspace_links(result)
    scopes = result["consent"]["scopes"]
    synthetic = result["synthetic"]
    historical = bool(result.get("as_of"))
    wearable_count = sum(
        point["id"].startswith("sense:")
        for series in result["series"] for point in series["points"]
    )

    def card(key, name, state, count=None, unit=None, href=None, research_href=None):
        return dict(id=key, name=name, state=state, count=count, unit=unit,
                    href=href, research_href=research_href)

    def observed_state(scope, count, available=True):
        if synthetic:
            return "synthetic_example"
        if scope not in scopes:
            return "consent_required"
        if count:
            return "available"
        return "empty" if available else "source_unavailable"

    with store.connect() as connection:
        tables = {row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('sense_observations','nt_imaging_links','nt_source_records','nt_neural_records')"
        )}
        owner = (result["identity"]["participant_id"], result["identity"]["mode"])

        def registered(scope, sources):
            installed = any(table in tables for table, _ in sources)
            if synthetic:
                return ("synthetic_in_twin" if links["twin"] else "source_unavailable"), None
            if scope not in scopes:
                return "consent_required", None
            if not installed:
                return "source_unavailable", None
            if historical:
                return "historical_unavailable", None
            count = sum(
                connection.execute(
                    f"SELECT count(*) FROM {table} WHERE participant_id=? AND mode=?" + predicate,
                    owner,
                ).fetchone()[0]
                for table, predicate in sources if table in tables
            )
            return ("registered" if count else "unlinked"), count

        imaging = registered("context", [("nt_imaging_links", "")])
        neural = registered("context", [
            ("nt_neural_records", ""), ("nt_source_records", " AND source='NeuroPulse'"),
        ])
        clinical = registered("clinical_biomarkers", [("nt_source_records", " AND source='Clinical'")])

    def visible_count(scope, count):
        return count if scope in scopes else None

    return [
        card("cognition", "NeuroCognition X",
             observed_state("context", len(result["alignments"]), bool(links["cognition"])),
             visible_count("context", len(result["alignments"])), "sessions", links["cognition"]),
        card("wearable", "NeuroSense",
             observed_state("context", wearable_count, "sense_observations" in tables),
             visible_count("context", wearable_count) if synthetic or "sense_observations" in tables else None,
             "stored observations", links["wearable"]),
        card("imaging", "NeuroVision", *imaging, "registered identity links",
             links["anatomy"], links["imaging_research"]),
        card("neural", "NeuroPulse", *neural, "registered EEG records", links["neural"]),
        card("clinical", "Clinical records", *clinical, "registered source records", links["twin"]),
        card("twin", "NeuroTwin X", "workspace_available" if links["twin"] else "source_unavailable",
             href=links["twin"]),
        card("governance", "NeuroGuard & NeuroCore", "local_review",
             sum(item["status"] == "pending" for item in result["review_queue"]),
             "pending BBC-BE reviews", links["governance"]),
    ]
