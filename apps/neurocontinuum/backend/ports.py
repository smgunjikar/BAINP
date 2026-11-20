"""Explicit adapters to already registered BAINP routes and storage contracts.

No HTTP loopback calls, no synthetic active data, no model/EEG/MRI execution.
"""
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from uuid import UUID

from bainp_continuum_engine import digest, reference_quality, person

class Ports:
    def __init__(self, app, store, cognitive_router):
        self.app, self.store = app, store
        self.routes = {getattr(r, 'path', ''): r.endpoint for r in cognitive_router.routes if hasattr(r, 'endpoint')} if cognitive_router else {}

    def access(self, cid, mode):
        endpoint = self.routes.get('/api/ncx/checkins/{cid}')
        if endpoint is None:
            raise RuntimeError('native_cognition_access_contract_unavailable')
        return endpoint(cid=UUID(cid), mode=mode)

    def cognition_url(self, cid, mode):
        return '/cognition?' + urlencode(dict(mode=mode, checkin=cid))

    def guard_ready(self):
        module = sys.modules.get('bainp_guard')
        policy = sys.modules.get('bainp_continuum_guard')
        return bool(module and callable(getattr(module, 'urgent', None)) and callable(getattr(module, 'check_claim', None)) and policy and callable(getattr(policy,'evaluate',None)))

    def workflow_decision(self, context):
        if not self.guard_ready():
            raise RuntimeError('native_workflow_guard_unavailable')
        return sys.modules['bainp_continuum_guard'].evaluate(context)

    def urgent(self, signs):
        if not self.guard_ready():
            raise RuntimeError('native_guard_unavailable')
        module = sys.modules['bainp_guard']
        from bainp_guard import URGENT_SOURCES
        return module.urgent(signs) | {'sources': URGENT_SOURCES}

    def check_claim(self, *args):
        if not self.guard_ready():
            raise RuntimeError('native_guard_unavailable')
        return sys.modules['bainp_guard'].check_claim(*args)

    def cases_ready(self):
        module = sys.modules.get('bainp_cases')
        return bool(module and all(callable(getattr(module, k, None)) for k in ('intake', 'select_case', 'transition')))

    def case_intake(self, *args):
        return sys.modules['bainp_cases'].intake(*args)

    def case_select(self, *args):
        return sys.modules['bainp_cases'].select_case(*args)

    def case_transition(self, *args):
        return sys.modules['bainp_cases'].transition(*args)

    def history(self, pid, mode):
        observations, excluded, sources = [], [], {}
        with self.store.connect() as connection:
            person(connection, pid, mode)
            # Use the existing authoritative stored source data; no predictive Twin snapshot is invoked.
            for row in connection.execute('SELECT a.*,s.protocol,s.form FROM nc_attempts a JOIN nc_sessions s ON s.id=a.session_id WHERE s.participant_id=? AND s.mode=? ORDER BY a.finished_at DESC,a.id LIMIT 200', (str(pid), mode)):
                summary = json.loads(row['summary']) if row['summary'] else None
                item = dict(attempt_id=row['id'], status=row['status'], finished_at=row['finished_at'], summary=summary)
                quality, flags = reference_quality(item)
                reference = dict(source='NeuroCognition X', source_id=row['id'], source_session_id=row['session_id'],
                    participant_id=str(pid), mode=mode, task=row['task'], observed_at=row['finished_at'],
                    protocol=row['protocol'], form=row['form'], quality=quality, flags=flags, source_hash=digest(item), clinical_validation=False)
                (observations if quality != 'QUARANTINED' else excluded).append(reference)
            sources['NeuroCognition X'] = dict(accepted=sum(o['source']=='NeuroCognition X' for o in observations),
                                               quarantined=len(excluded), transport='native source references')
            tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            sources['NeuroTwin X'] = dict(state='native_source_storage_available' if 'nt_source_records' in tables else 'not_installed', inference_executed=False)
            if 'nt_source_records' in tables:
                for row in connection.execute('SELECT source,record_id,revision,payload FROM nt_source_records WHERE participant_id=? AND mode=? ORDER BY source,record_id LIMIT 100', (str(pid), mode)):
                    data = json.loads(row['payload'])
                    if data.get('identity_verified') is not True or data.get('consent_confirmed') is not True:
                        continue
                    qualities = [o.get('quality') for o in data.get('observations', [])]
                    ref = dict(source='NeuroTwin X / '+row['source'], source_id=row['record_id'], revision=row['revision'],
                        participant_id=str(pid), mode=mode, observed_at=data.get('observed_at'),
                        protocol=data.get('protocol'), source_hash=digest(data),
                        quality='SOURCE_DECLARED_USABLE_NOT_CLINICALLY_VALIDATED' if qualities and all(q=='usable' for q in qualities) else 'QUARANTINED', clinical_validation=False)
                    (observations if ref['quality']!='QUARANTINED' else excluded).append(ref)
            # Existing BBC provider applies its own separate scopes; do not widen those permissions.
        provider = sys.modules.get('bb_provider')
        context = None
        if provider:
            context = provider.read_context(self.store, UUID(str(pid)), mode, include_sensitive=False)
            if context.get('identity', {}).get('participant_id') not in (None, str(pid)):
                raise RuntimeError('native_context_identity_mismatch')
            sources['Brain-Body'] = dict(state=context.get('source_status', {}).get('context'), revision=context.get('revision'),
                                         record_count=len(context.get('records', [])))
        return dict(state='SOURCE_REFERENCES_AVAILABLE' if observations else 'NO_QC_CLEAR_HISTORY',
                    observations=observations, excluded=excluded, sources=sources, clinical_comparability=False,
                    explanation='Quality-clear source references remain separated by protocol and form. No clinical trend or multimodal pairing is inferred.')

    def directory(self):
        # The native main-page server, not guessed paths, determines which module pages are actually served.
        try:
            from serve_frontend import ASSETS, ROOT
        except ImportError:
            ASSETS, ROOT = {}, Path('.')
        module = sys.modules.get('bainp_platform_router')
        definitions = getattr(module, 'MODULES', ())
        definitions = list(definitions) + [('NeuroPulse', '/neuropulse', 'neuropulse/backend/engine.py'),
                                         ('NeuroContinuum', '/neurocontinuum', 'neurocontinuum/backend/engine.py')]
        seen, result = set(), []
        apps = Path(__file__).resolve().parents[2]
        for name, route, source in definitions:
            if name in seen:
                if route and route in ASSETS:
                    next(r for r in result if r['name']==name)['url'] = route
                continue
            seen.add(name)
            served = route if route in ASSETS and (ROOT/ASSETS[route][0]).is_file() else None
            result.append(dict(name=name, source_present=(apps/source).is_file(), url=served,
                               state='registered_page' if served else 'source_only' if (apps/source).is_file() else 'unavailable'))
        return result
