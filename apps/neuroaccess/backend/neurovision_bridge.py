import importlib.util,sys
from pathlib import Path
folder=Path(__file__).resolve().parents[2]/'neurovision/backend'
if 'nv_queue' not in sys.modules:
 spec=importlib.util.spec_from_file_location('nv_queue',folder/'nv_queue.py')
 module=importlib.util.module_from_spec(spec);sys.modules['nv_queue']=module;spec.loader.exec_module(module)
p=folder/'router.py'
spec=importlib.util.spec_from_file_location('_neurovision_router',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
make_router=m.make_router
