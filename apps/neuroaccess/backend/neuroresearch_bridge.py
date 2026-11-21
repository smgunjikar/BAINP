"""Lazy bridge from BAINP's authenticated NeuroAccess API to additive research package."""
from pathlib import Path
import sys

RESEARCH_HOME = Path(__file__).resolve().parents[2] / 'bainp_research_expansion'
if not (RESEARCH_HOME / 'bainp_expansion' / 'api.py').is_file():
    raise RuntimeError('BAINP_RESEARCH_EXTENSION_NOT_INSTALLED')
if str(RESEARCH_HOME) not in sys.path:
    sys.path.insert(0, str(RESEARCH_HOME))
from bainp_expansion.api import make_router  # noqa: E402
