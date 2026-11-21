"""Small validated, reproducible, file-safe utilities shared by research modules."""
from __future__ import annotations
import hashlib, json, math, os, re, tempfile
from datetime import datetime, timezone
from pathlib import Path

IDENT = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,95}$')
SHA = re.compile(r'^[a-f0-9]{64}$')

class Blocked(ValueError):
    """A scientific, provenance, safety or data eligibility gate was not met."""
    def __init__(self, code: str, explanation: str = ''):
        self.code = code
        super().__init__(code + (': ' + explanation if explanation else ''))


def require(condition: bool, code: str, explanation: str = ''):
    if not condition:
        raise Blocked(code, explanation)


def identifier(value: str, label: str = 'identifier') -> str:
    require(isinstance(value, str) and bool(IDENT.fullmatch(value)), 'INVALID_IDENTIFIER', label)
    return value


def checksum(value: str):
    require(isinstance(value, str) and bool(SHA.fullmatch(value)), 'INVALID_SHA256')
    return value


def sha256_file(path: str | Path, max_size: int = 2 * 1024**3) -> str:
    p = Path(path)
    require(p.is_file() and not p.is_symlink(), 'SOURCE_FILE_UNAVAILABLE_OR_SYMLINK', str(p))
    require(p.stat().st_size <= max_size, 'SOURCE_EXCEEDS_AUDIT_FILE_LIMIT', str(p))
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canon(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest_json(value) -> str:
    return hashlib.sha256(canon(value).encode('utf-8')).hexdigest()


def read_json(path: str | Path, max_bytes: int = 20 * 1024 * 1024):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= max_bytes,
            'JSON_FILE_UNAVAILABLE_OR_TOO_LARGE', str(path))
    return json.loads(p.read_text(encoding='utf-8'))


def write_json_new(path: str | Path, data):
    """Write a new file only; never replace an existing scientific artifact."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(p), flags, 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
    except BaseException:
        p.unlink(missing_ok=True)
        raise
    return p


def measured(value, name: str, minimum: float | None = None) -> float:
    require(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value),
            'INVALID_MEASUREMENT', name)
    v = float(value)
    if minimum is not None:
        require(v >= minimum, 'NEGATIVE_OR_OUT_OF_RANGE', name)
    return v


def utc_timestamp(text: str):
    require(isinstance(text, str), 'INVALID_TIMESTAMP')
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as exc:
        raise Blocked('INVALID_TIMESTAMP', text) from exc
    require(dt.tzinfo is not None, 'TIMEZONE_REQUIRED')
    dt = dt.astimezone(timezone.utc)
    require(dt <= datetime.now(timezone.utc), 'FUTURE_OBSERVATION')
    return dt


def same_subject(first: dict, second: dict):
    for field in ('cohort', 'subject'):
        require(first.get(field) and first.get(field) == second.get(field),
                'CROSS_SUBJECT_OR_COHORT_COMPARISON_BLOCKED', field)


def report(phase: str, state: str, facts: dict, limits: list[str]):
    return {'schema': 'BAINP_RESEARCH_EXPANSION_V1', 'phase': phase, 'state': state,
            'facts': facts, 'limitations': limits,
            'clinical_clearance': False, 'diagnostic_inference': False}
