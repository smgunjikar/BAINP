import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'neurosense/backend/sense_store.py'
spec=importlib.util.spec_from_file_location('_neurosense_sense_store',p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
make_router=m.make_router
