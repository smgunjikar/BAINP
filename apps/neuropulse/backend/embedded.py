"""Read continuous embedded MATLAB v5 EEGLAB recordings."""
import numpy as np
from scipy.io import loadmat

def read_embedded(path):
    fields = loadmat(path, simplify_cells=True,
                     variable_names=['EEG', 'data', 'srate', 'trials', 'chanlocs', 'event'])
    eeg = fields.get('EEG', fields)
    data = eeg['data']
    sf = float(eeg['srate'])
    names = [channel['labels'] for channel in eeg['chanlocs']]
    if (not isinstance(data, np.ndarray) or data.ndim != 2 or data.shape[0] != len(names)
            or eeg['trials'] != 1 or len(set(names)) != len(names)):
        raise ValueError(f'Expected continuous embedded EEGLAB data for {path.name}.')
    events = eeg.get('event', [])
    if isinstance(events, dict):
        events = [events]
    excluded = []
    for event in events:
        kind = str(event['type']).lower()
        if kind == 'boundary' or kind.startswith('bad'):
            onset = (float(event['latency'])-1)/sf
            duration = float(event.get('duration', 0))/sf
            excluded.append((onset-0.01, onset+max(duration, 0.01)))
    return data, sf, names, excluded
