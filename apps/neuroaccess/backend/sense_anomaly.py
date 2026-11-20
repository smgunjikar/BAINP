import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'neurosense/backend/sense_anomaly.py'
spec=importlib.util.spec_from_file_location('_neurosense_sense_anomaly',p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
analyze=m.analyze
