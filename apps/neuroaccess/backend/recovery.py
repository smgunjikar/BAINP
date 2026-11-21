"""Compatibility loader for the NeuroCognition-owned implementation."""
from pathlib import Path
_source = Path(__file__).resolve().parents[2] / 'neurocognition' / 'backend' / 'recovery.py'
exec(compile(_source.read_bytes(), str(_source), 'exec'), globals(), globals())
