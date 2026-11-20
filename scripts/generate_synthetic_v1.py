import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5
from pydantic import ValidationError
from shared.schemas.provenance_v1 import Observation

ROOT = Path(__file__).resolve().parents[1]
NS = UUID('f985c6b0-b463-4e1e-93a4-337811174bb7')
def identifier(key):
    return str(uuid5(NS, key))

scenarios = [
    ('Demo Alex', 'practice_variation', 4, 'en'),
    ('Demo Noor', 'scripted_declining_observations', 5, 'ar'),
    ('Demo Sam', 'language_and_input_switch', 4, 'en'),
    ('Demo Amal', 'acute_intake_fixture', 1, 'ar'),
    ('Demo Robin', 'single_baseline', 1, 'en'),
]
people, encounters, observations = [], [], []
for number, (name, scenario, count, language) in enumerate(scenarios, 1):
    pid = identifier(f'person-{number}')
    people.append(dict(id=pid, display_name=name, synthetic=True, scenario=scenario))
    for visit in range(count):
        eid = identifier(f'person-{number}-visit-{visit}')
        switched = number == 3 and visit == 3
        acute = number == 4
        timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=90 * visit)
        encounters.append(dict(
            id=eid, participant_id=pid, visit=visit + 1,
            status='intake_only' if acute else 'simulated_history',
            language='ar' if switched else language,
            input_method='touch' if switched else 'mouse',
            acute_flag_fixture=acute,
            recorded_at_utc=timestamp.isoformat(),
        ))
        if acute:
            continue
        latency = 600 + (60 * visit if number == 2 else -15 * min(visit, 2))
        if switched:
            latency += 200
        memory = max(0.0, 0.9 - (0.12 * visit if number == 2 else 0.0))
        for metric, value, unit in [
            ('simulated_attention_latency', latency, 'ms'),
            ('simulated_memory_fraction', memory, 'fraction'),
        ]:
            observation = Observation(
                observation_id=identifier(f'{eid}-{metric}'), participant_id=pid,
                encounter_id=eid, metric=metric, value=value, unit=unit,
                provenance=dict(
                    source='synthetic', dataset_version='bainp-synthetic-v1',
                    protocol_version='synthetic-trajectory-v1',
                    measurement_method='deterministic-simulation',
                    device_metadata={'input_method': 'touch' if switched else 'mouse',
                                     'device_class': 'simulated-mobile' if switched else 'simulated-desktop'},
                    recorded_at_utc=timestamp,
                ),
            )
            observations.append(observation.model_dump(mode='json'))

# Negative tests must fail; never rely on Python assert for validation.
for field in ['protocol_version', 'device_metadata', 'recorded_at_utc']:
    invalid = json.loads(json.dumps(observations[0]))
    del invalid['provenance'][field]
    try:
        Observation.model_validate(invalid)
    except ValidationError:
        continue
    raise RuntimeError(f'Missing {field} was accepted')
invalid = json.loads(json.dumps(observations[0]))
invalid['unit'] = 'fraction'
try:
    Observation.model_validate(invalid)
except ValidationError:
    pass
else:
    raise RuntimeError('Incorrect unit was accepted')

cohort = dict(
    schema_version='bainp-synthetic-v1', synthetic=True,
    purpose='Scripted demonstration fixtures; not reference norms or clinical validation',
    participants=people, encounters=encounters, observations=observations,
)
if (len(people), len(encounters), len(observations)) != (5, 15, 28):
    raise RuntimeError('Unexpected cohort counts')
output = ROOT / 'data' / 'synthetic' / 'cohort_v1.json'
output.parent.mkdir(parents=True, exist_ok=True)
encoded = (json.dumps(cohort, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
if output.exists() and output.read_bytes() != encoded:
    raise RuntimeError(f'Refusing to replace a different cohort: {output}')
output.write_bytes(encoded)
print('PASS: required provenance fields and metric/unit validation')
print('PASS: 5 fictional participants, 15 encounters, 28 simulated observations')
print('SHA256:', hashlib.sha256(encoded).hexdigest())
print('Output:', output)
