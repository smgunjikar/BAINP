import importlib.util,sys
from pathlib import Path
folder=Path(__file__).resolve().parents[2]/'neurovision/backend'
for name,filename in [('nv_queue','nv_queue.py'),('_neurovision_import_api','import_api.py')]:
 spec=importlib.util.spec_from_file_location(name,folder/filename)
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
make_router=sys.modules['_neurovision_import_api'].make_router
