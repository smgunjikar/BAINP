import importlib.util,sys
from pathlib import Path
apps=Path(__file__).resolve().parents[2]
modules=[('bb_dictionary','brainbody/backend/dictionary.py'),('bb_policy','neuroguard/backend/brainbody_policy.py'),('bb_models','brainbody/backend/models.py'),('bb_identity','brainbody/backend/identity.py'),('bb_engine','brainbody/backend/engine.py'),('bb_provider','brainbody/backend/provider.py'),('bb_demo','brainbody/backend/demo.py'),('bb_connections','brainbody/backend/connections.py'),('_bb_router','brainbody/backend/router.py')]
for name,relative in modules:
    spec=importlib.util.spec_from_file_location(name,apps/relative)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
make_router=sys.modules['_bb_router'].make_router
for_twin=sys.modules['bb_provider'].for_twin
demo_context=sys.modules['bb_demo'].demo_context
