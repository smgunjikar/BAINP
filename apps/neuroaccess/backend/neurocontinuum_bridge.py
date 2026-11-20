"""Load only the explicit installed NeuroContinuum extension, outside request handling."""
import importlib.util
from pathlib import Path
import sys

apps = Path(__file__).resolve().parents[2]
for name, relative in (
    ('bainp_continuum_engine','neurocontinuum/backend/engine.py'),
    ('bainp_continuum_guard','neuroguard/backend/continuum_policy.py'),
    ('bainp_continuum_ports','neurocontinuum/backend/ports.py'),
    ('bainp_continuum_router','neurocontinuum/backend/router.py'),
):
    spec = importlib.util.spec_from_file_location(name, apps/relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
mount = sys.modules['bainp_continuum_router'].mount
for_twin = sys.modules['bainp_continuum_engine'].summary_for_twin

# neuroquest_native_mount_v1
_original_mount = mount
def mount(app, store, authenticated, cognitive_router):
    global _quest_auth
    _quest_auth = authenticated
    _original_mount(app,store,authenticated,cognitive_router)
    for name, relative in [('bainp_quest_engine','neuroquest/backend/engine.py'),('bainp_quest_router','neuroquest/backend/router.py')]:
        spec=importlib.util.spec_from_file_location(name,apps/relative)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    sys.modules['bainp_quest_router'].mount(app)

# neuroshadow_native_mount_v1
_shadow_previous_mount=mount
_shadow_previous_twin=for_twin
def mount(app,store,authenticated,cognitive_router):
    _shadow_previous_mount(app,store,authenticated,cognitive_router)
    for name,relative in [('bainp_shadow_engine','neuroshadow/backend/engine.py'),('bainp_shadow_guard','neuroguard/backend/shadow_policy.py'),('bainp_shadow_router','neuroshadow/backend/router.py')]:
        spec=importlib.util.spec_from_file_location(name,apps/relative)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    sys.modules['bainp_shadow_router'].mount(app)
def for_twin(store,pid,mode):
    result=_shadow_previous_twin(store,pid,mode)
    if result.get('state')=='workflow_history_available':
        with store.connect() as c:result['neuroshadow']=sys.modules['bainp_shadow_router'].context(c,pid,mode)
    return result

# mimic_proof_native_v1
_mp_previous_mount=mount
def mount(app,store,authenticated,cognitive_router):
    _mp_previous_mount(app,store,authenticated,cognitive_router)
    for name,relative in [('bainp_mimic_router','neuromimic/backend/router.py'),('bainp_proof_router','neuroproof/backend/router.py')]:
        spec=importlib.util.spec_from_file_location(name,apps/relative)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        module.mount(app)
