"""Independent technical-quality policy. No disease thresholds or clinical alerts."""
VERSION='neuroguard-shadow-technical-v1'
def evaluate(features, diagnostics):
    flags=[]
    if features['duration_ms']<10000:flags.append('SHORT_ACTIVITY')
    if features['move_count']<40:flags.append('INSUFFICIENT_MOVEMENT_SAMPLES')
    if diagnostics['frame_count']<30:flags.append('INSUFFICIENT_FRAME_DIAGNOSTICS')
    if diagnostics['hidden_count']:flags.append('ACTIVITY_INTERRUPTED')
    if diagnostics['resize_count']:flags.append('VIEWPORT_CHANGED')
    if diagnostics['frame_count'] and diagnostics['slow_frames']/diagnostics['frame_count']>.1:flags.append('CLIENT_FRAME_INSTABILITY')
    if diagnostics.get('server_duration_mismatch'):flags.append('CLIENT_SERVER_DURATION_MISMATCH')
    return dict(policy=VERSION,state='QUARANTINED' if flags else 'TECHNICAL_QC_CLEAR',flags=flags,
        clinical_validity=False,clinical_alert_allowed=False,
        interpretation='Engineering thresholds only; client-reported timing is not a trusted clinical instrument.')
