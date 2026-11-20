import importlib.util
from pathlib import Path
import sys
import neuroevidence_bridge

apps = Path(__file__).resolve().parents[2]
for name, relative in (
    ('bainp_sim', 'neurosim/backend/sim.py'),
    ('bainp_cases', 'careloop/backend/cases.py'),
    ('bainp_prevention_router', 'neurosim/backend/router.py'),
    ('bainp_careloop_v2', 'careloop/backend/router.py'),
):
    spec = importlib.util.spec_from_file_location(name, apps / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
def make_router(store, authenticated, cognitive_analytics=None):
    from fastapi import APIRouter
    router = APIRouter()
    router.include_router(sys.modules['bainp_prevention_router'].make_router(store, authenticated, cognitive_analytics))
    router.include_router(sys.modules['bainp_careloop_v2'].make_router(store, authenticated))
    return router
for_twin = sys.modules['bainp_cases'].for_twin
