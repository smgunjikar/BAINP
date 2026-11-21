"""Experimental interaction measurements; transient bounded events, stored aggregates only."""
import math,statistics
VERSION='neuroshadow-features-v1.0.0'
ACTIVITY='shadow-explore-v1'
def extract(events,duration_ms):
    distances=[];speeds=[];gaps=[];clicks=touches=0;previous=None;contacts=[]
    for event in events:
        e=event if isinstance(event,dict) else event.model_dump()
        if e['kind']=='down':
            clicks+=1;touches+=int(e['pointer']=='touch');contacts.append(e['t_ms'])
        if e['kind']=='move':
            if previous and previous['pointer']==e['pointer']:
                dt=e['t_ms']-previous['t_ms'];distance=math.hypot(e['x_bin']-previous['x_bin'],e['y_bin']-previous['y_bin'])/20
                distances.append(distance);gaps.append(dt)
                if dt>0:speeds.append(distance/(dt/1000))
            previous=e
    contact_gaps=[b-a for a,b in zip(contacts,contacts[1:])]
    return dict(median_contact_interval_ms=statistics.median(contact_gaps) if contact_gaps else None,contact_interval_sd_ms=round(statistics.pstdev(contact_gaps),3) if len(contact_gaps)>1 else None,duration_ms=duration_ms,event_count=len(events),move_count=sum((e['kind'] if isinstance(e,dict) else e.kind)=='move' for e in events),
        click_count=clicks,touch_contacts=touches,normalized_path_length=round(sum(distances),6),
        movement_step_sd=round(statistics.pstdev(distances),6) if len(distances)>1 else None,
        median_normalized_speed=round(statistics.median(speeds),6) if speeds else None,
        movement_interval_sd_ms=round(statistics.pstdev(gaps),3) if len(gaps)>1 else None,
        movement_gap_count=sum(g>=1000 for g in gaps),
        pause_definition='Interval >=1000 ms between sampled movement events; not cognitive response time.')
