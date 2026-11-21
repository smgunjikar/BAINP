import importlib.util,sys
from pathlib import Path
apps=Path(__file__).resolve().parents[2]
modules=[('nt_engine','neurotwin/backend/engine.py'),('nt_guard','neuroguard/backend/neurotwin_policy.py'),('nt_monitor','neurocore/backend/neurotwin_monitor.py'),('nt_anatomy','neurotwin/backend/anatomy.py'),('nt_neural_contract','neurotwin/backend/neural_contract.py'),('nt_state','neurotwin/backend/state.py'),('nt_demo','neurotwin/backend/demo.py'),('_nt_router','neurotwin/backend/router.py')]
for name,relative in modules:
    spec=importlib.util.spec_from_file_location(name,apps/relative)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
make_router=sys.modules['_nt_router'].make_router
