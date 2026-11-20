"""Atomic import of the exact reviewed synthetic-v1 fixture; safe identical retries."""
import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps' / 'api'))
from sqlalchemy import text
from app.database import engine
from shared.schemas.provenance_v1 import Observation

EXPECTED = 'c36df21e2285230fd8f564815bb9ecb0883fac728cadf1f8767d454bdcc54ebf'
DATASET = 'bainp-synthetic-v1'

def load_cohort(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise RuntimeError('Cohort checksum differs from reviewed v1. No import attempted.')
    data = json.loads(raw)
    if data['synthetic'] is not True or data['schema_version'] != DATASET:
        raise RuntimeError('Synthetic source/version mismatch')
    people, visits, observations = data['participants'], data['encounters'], data['observations']
    if tuple(map(len, (people, visits, observations))) != (5, 15, 28):
        raise RuntimeError('Unexpected fixture counts')
    def ids(rows, key):
        result = {row[key] for row in rows}
        if len(result) != len(rows):
            raise RuntimeError('Duplicate identifiers in source')
        for value in result:
            if str(UUID(value)) != value:
                raise RuntimeError('Noncanonical UUID')
        return result
    pids = ids(people, 'id')
    ids(visits, 'id'); ids(observations, 'observation_id')
    by_visit = {row['id']: row for row in visits}
    if any(p['synthetic'] is not True for p in people):
        raise RuntimeError('Non-synthetic participant')
    if any(v['participant_id'] not in pids for v in visits):
        raise RuntimeError('Encounter has unknown participant')
    for item in observations:
        Observation.model_validate(item)
        visit = by_visit.get(item['encounter_id'])
        if not visit or visit['participant_id'] != item['participant_id'] or visit['status'] != 'simulated_history':
            raise RuntimeError('Observation identity/status mismatch')
    return data

def store(connection, table, identity, payload, **columns):
    # Table/column names are fixed internal constants, never external input.
    fields = {'id': identity, **columns}
    names = ', '.join([*fields, 'payload'])
    values = ', '.join([':' + key for key in fields] + ['CAST(:payload AS jsonb)'])
    connection.execute(text(f'INSERT INTO {table} ({names}) VALUES ({values}) ON CONFLICT (id) DO NOTHING'),
                       {**fields, 'payload': json.dumps(payload)})
    row = connection.execute(text(f'SELECT * FROM {table} WHERE id = :id'), {'id': identity}).mappings().one()
    if row['payload'] != payload or any(row[key] != value for key, value in fields.items()):
        raise RuntimeError(f'Conflicting immutable record in {table}: {identity}')


def main():
    cohort = load_cohort(ROOT / 'data' / 'synthetic' / 'cohort_v1.json')
    with engine.begin() as connection:
        # Serialize concurrent imports of this fixture across processes.
        connection.execute(text('SELECT pg_advisory_xact_lock(731004007)'))
        release = connection.execute(text('SELECT sha256, payload FROM demo_dataset_releases WHERE id = :id'), {'id': DATASET}).mappings().first()
        if release and (release['sha256'] != EXPECTED or release['payload'] != cohort):
            raise RuntimeError('Dataset release already exists with different contents')
        connection.execute(text('INSERT INTO demo_dataset_releases (id, sha256, payload) VALUES (:id, :sha, CAST(:payload AS jsonb)) ON CONFLICT (id) DO NOTHING'),
                           {'id': DATASET, 'sha': EXPECTED, 'payload': json.dumps(cohort)})
        for person in cohort['participants']:
            store(connection, 'demo_participants', person['id'], person, dataset_id=DATASET)
        for visit in cohort['encounters']:
            store(connection, 'demo_encounters', visit['id'], visit, participant_id=visit['participant_id'], dataset_id=DATASET)
        for item in cohort['observations']:
            store(connection, 'demo_observations', item['observation_id'], item,
                  participant_id=item['participant_id'], encounter_id=item['encounter_id'], dataset_id=DATASET)
        for table, expected in [('demo_participants', 5), ('demo_encounters', 15), ('demo_observations', 28)]:
            count = connection.execute(text(f'SELECT count(*) FROM {table} WHERE dataset_id = :id'), {'id': DATASET}).scalar_one()
            if count != expected:
                raise RuntimeError(f'{table}: expected {expected}, got {count}; transaction rolled back')
    print('PASS: committed synthetic release with matching provenance and identities')
    print('PASS: 5 demo participants, 15 encounters, 28 observations; no duplicate IDs')
    print('Dataset:', DATASET)

if __name__ == '__main__':
    main()
