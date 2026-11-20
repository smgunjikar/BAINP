"""Full coherent multimodal fictional profiles. Never persisted into participant stores."""
import json
from functools import lru_cache
from pathlib import Path
from nt_engine import build
from nt_state import enhance,toy_forecast,local_level
@lru_cache(maxsize=1)
def fixtures():return json.loads(Path(__file__).with_name('demo_fixtures.json').read_text())
def demo_snapshot(profile='control'):
    f=fixtures()[profile]
    states={k:{'state':'synthetic_example','count':n} for k,n in [('NeuroCognition X',8),('NeuroSense',len(f['wearable'])),('NeuroVision',8),('NeuroPulse',8),('Clinical',8)]}
    result=build(f['cognition'],f['wearable'],f['imaging'],f['records'],states,{'participant_id':'fictional-'+profile,'mode':'demo','display_name':'Fictional control scenario' if profile=='control' else 'Fictional cognitive-impairment scenario','profile_revision':1},[])
    score=next(s for s in result['series'] if s['metric']=='C01:correct')['points'][-1]['value']/20*100
    result['forecast']=toy_forecast(score,5 if profile=='impairment' else 0,6.6 if profile=='impairment' else 7.4)
    summaries=[{k:v for k,v in r.items() if k not in ('signal_uv','spectrum','covariance_uv2')} for r in f['neural']]
    result=enhance(result,f['records'],summaries,synthetic=True)
    for series in result['series']:
        if series['source']=='NeuroCognition X' and series['metric'].endswith(':median_correct_rt_ms'):
            series['state_filter']=local_level(series['points'],measurement_variance=2500,process_variance_per_day=1.5)
            series['filter_assumptions']='Illustrative local-level filter: measurement variance 2500 ms²; process variance 1.5 ms²/day. Assumed, not calibrated.'
    result['demo_profile']=profile;result['read_consistency']='All modalities belong to this one invented profile. No cross-dataset person linkage.'
    # brain_body_context_adapter_v1: same authored fictional profile.
    from brainbody_bridge import demo_context
    result['brain_body']=demo_context(profile)
    result['source_states']['BBC-BE']={'state':'synthetic_example','count':result['brain_body']['record_count']}
    # Filter output and scenario selection are included in the content fingerprint.
    from nt_engine import fingerprint
    result['revision']=fingerprint({k:v for k,v in result.items() if k!='revision'})
    return result
