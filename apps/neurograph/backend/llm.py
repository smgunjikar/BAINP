"""Optional loopback Ollama planner for fictional demonstrations only."""

from http.client import HTTPConnection, HTTPException
import json
import os
import re
from threading import Lock

_LOCK = Lock()


def model_name():
    name = os.environ.get("BAINP_NEUROGRAPH_OLLAMA_MODEL", "").strip()
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,100}", name) and "cloud" not in name.lower():
        return name
    return None


def demo_plan(claims):
    model = model_name()
    if not model:
        return {"state": "abstain", "reason": "LOCAL_MODEL_NOT_CONFIGURED", "claims": []}
    if not _LOCK.acquire(blocking=False):
        return {"state": "abstain", "reason": "LOCAL_MODEL_BUSY", "claims": []}
    approved = {item["id"]: item for item in claims if item["state"] == "accept"}
    # No real participant context, prompts, identifiers or values enter this adapter.
    catalog = [{"id": key, "type": item["type"]} for key, item in approved.items()]
    schema = {"type": "object", "properties": {"claim_ids": {
        "type": "array", "minItems": 1, "maxItems": 4,
        "items": {"type": "string", "enum": list(approved)},
    }}, "required": ["claim_ids"], "additionalProperties": False}
    request = {"model": model, "stream": False, "format": schema,
               "options": {"temperature": 0, "num_predict": 256},
               "prompt": "Select up to four distinct claim IDs for a fictional evidence demonstration. "
                         "Prefer a mix of observation and uncertainty. Return JSON only. Catalog: " + json.dumps(catalog)}
    connection = HTTPConnection("127.0.0.1", 11434, timeout=8)
    try:
        connection.request("POST", "/api/generate", json.dumps(request), {"Content-Type": "application/json"})
        response = connection.getresponse()
        data = response.read(65537)
        if response.status != 200 or len(data) > 65536:
            raise ValueError("model response unavailable")
        envelope = json.loads(data)
        if envelope.get("done") is not True:
            raise ValueError("incomplete model response")
        plan = json.loads(envelope["response"])
        ids = plan["claim_ids"]
        if (set(plan) != {"claim_ids"} or not isinstance(ids, list) or not 1 <= len(ids) <= 4
                or not all(isinstance(key, str) and key in approved for key in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("invalid claim selection")
        return {"state": "accept", "reason": "LOCAL_PLAN_VERIFIED", "claims": [approved[key] for key in ids]}
    except (OSError, HTTPException, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return {"state": "abstain", "reason": "LOCAL_PLAN_UNAVAILABLE_OR_REJECTED", "claims": []}
    finally:
        connection.close()
        _LOCK.release()
