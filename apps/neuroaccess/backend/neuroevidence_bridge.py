import importlib.util
from pathlib import Path
import sys

apps = Path(__file__).resolve().parents[2]
modules = {
    'bainp_guard': 'neuroguard/backend/guard.py',
    'bainp_graph': 'neurograph/backend/graph.py',
    'bainp_ng_llm': 'neurograph/backend/llm.py',
    'bainp_ng_router': 'neurograph/backend/router.py',
}
for name, relative in modules.items():
    spec = importlib.util.spec_from_file_location(name, apps / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
make_router = sys.modules['bainp_ng_router'].make_router
guard_forecast = sys.modules['bainp_guard'].guard_forecast
