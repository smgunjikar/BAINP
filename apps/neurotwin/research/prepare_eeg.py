"""Prepare a bounded EEG source record in bainp-brain; source files stay unchanged.
MNE import -> volts to uV -> QC windows -> Welch/covariance -> display-only resampling.
This code does not identify artifact causes or diagnose a disease.
"""
import argparse,hashlib,json,math
from pathlib import Path

def process(data_uv,sampling_hz,channels):
    import numpy as np
    from scipy.signal import butter,sosfiltfilt,welch,resample_poly
    from fractions import Fraction
    data=np.asarray(data_uv,dtype=float)
    if data.ndim!=2 or len(channels)!=data.shape[0] or not 1<=len(channels)<=16:raise ValueError('1–16 EEG channels required')
    if sampling_hz<64 or sampling_hz>2048 or data.shape[1]/sampling_hz<8:raise ValueError('At least eight seconds at 64–2048 Hz required')
    data=data[:,:int(60*sampling_hz)]
    # Nonfinite annotated intervals are not interpolated or treated as clean.
    width=int(round(4*sampling_hz));good=[];bad=0
    for start in range(0,data.shape[1]-width+1,width):
        window=data[:,start:start+width]
        if not np.isfinite(window).all() or np.any(np.ptp(window,axis=1)>200) or np.any(np.std(window,axis=1)<.1):bad+=1;continue
        # Offline zero-phase filtering per window, including edge effects in provenance.
        filtered=sosfiltfilt(butter(4,[.5,30],btype='bandpass',fs=sampling_hz,output='sos'),window,axis=-1)
        good.append(filtered)
    total=len(good)+bad
    if not good:raise ValueError('No usable four-second windows; do not manufacture EEG features')
    segments=np.stack(good)
    freq,psd=welch(segments,fs=sampling_hz,window='hann',nperseg=int(2*sampling_hz),noverlap=int(sampling_hz),detrend='constant',axis=-1)
    density=np.mean(psd,axis=(0,1));df=freq[1]-freq[0]
    features={name+'_power':float(np.sum(density[(freq>=a)&(freq<b)])*df) for name,a,b in [('delta',.5,4),('theta',4,8),('alpha',8,13),('beta',13,30)]}
    selected=(freq>=.5)&(freq<30);p=density[selected];p=p/p.sum();features['spectral_entropy']=float(-np.sum(p[p>0]*np.log(p[p>0]))/np.log(len(p)))
    alpha=(freq>=8)&(freq<13);fa=freq[alpha];pa=density[alpha];j=int(np.argmax(pa));features['peak_alpha_frequency']=float(fa[j]) if 0<j<len(pa)-1 and pa[j]>2*np.median(pa) else None
    covariance=np.mean([np.atleast_2d(np.cov(w)) for w in good],axis=0)
    # Replay a contiguous usable window, never concatenate separated windows as continuous EEG.
    ratio=Fraction(128/sampling_hz).limit_denominator(10000);replay=resample_poly(good[0],ratio.numerator,ratio.denominator,axis=-1)
    return dict(channels=channels,processing_sampling_hz=float(sampling_hz),sampling_hz=float(sampling_hz*ratio.numerator/ratio.denominator),signal_uv=np.round(replay,4).tolist(),
       features=features,spectrum={'frequencies':freq[selected].tolist(),'density_uv2_hz':density[selected].tolist()},
       covariance_uv2=covariance.tolist(),quality='usable' if bad==0 else 'review',
       quality_flags=[] if bad==0 else ['HEURISTIC_WINDOW_EXCLUSIONS'],usable_windows=len(good),total_windows=total)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    for name in ('record-id','source-subject','observed-at','protocol'):p.add_argument('--'+name,required=True)
    a=p.parse_args();import mne
    raw=mne.io.read_raw(a.input,preload=True,verbose='ERROR');picks=mne.pick_types(raw.info,eeg=True,exclude='bads')[:16]
    if not len(picks):raise ValueError('No EEG channels identified; review channel types')
    data=raw.get_data(picks=picks,start=0,stop=min(raw.n_times,int(60*raw.info['sfreq'])),reject_by_annotation='NaN')*1e6
    output=process(data,raw.info['sfreq'],[raw.ch_names[i] for i in picks])
    source_files={p.resolve() for p in [a.input,*[Path(f) for f in raw.filenames if f]]}
    paired=a.input.with_suffix('.fdt')
    if paired.is_file():source_files.add(paired.resolve())
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_files)}
    output['source_files_sha256']=hashes
    output.update(record_id=a.record_id,source_subject=a.source_subject,observed_at=a.observed_at,revision=1,
       source_kind='recorded_research_eeg',synthetic=False,identity_verified=False,consent_confirmed=False,
       protocol=a.protocol,pipeline='nt-eeg-window-welch-v1',source_sha256=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
       provenance='MNE import; 4s window QC; 0.5–30Hz zero-phase window filter; mean Welch PSD; covariance; first usable window replay. Identity and consent must be verified before publishing.')
    # Preparing a file does not assert actual consent. Publishing requires explicit flags.
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(output,allow_nan=False),encoding='utf-8')
    print('Prepared EEG contract:',a.output)
if __name__=='__main__':main()
