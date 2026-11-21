import importlib.util
from pathlib import Path
import sys
import neuroevidence_bridge

apps = Path(__file__).resolve().parents[2]
for name, relative in (
    ('bainp_arena','neurosignal-arena/backend/arena.py'),
    ('bainp_jobs','platform-core/backend/jobs.py'),
    ('bainp_platform_router','platform-core/backend/router.py'),
):
    spec = importlib.util.spec_from_file_location(name, apps/relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
mount = sys.modules['bainp_platform_router'].mount
