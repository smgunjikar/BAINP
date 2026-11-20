"""NeuroPulse v0.1: auditable EEG pilot features and recorded-signal replay.
No classifier, diagnosis, artifact removal or electrode-contact estimation.
"""
import argparse,csv,hashlib,json,platform
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from scipy import signal
import scipy
from embedded import read_embedded
VERSION='neuropulse-pilot-v0.2'
BANDS={'delta':(.5,4),'theta':(4,8),'alpha':(8,13),'beta':(13,30)}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write_json(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False),encoding='utf-8')
def inventory(root,out):
 rows=[]
 # Root-level BIDS subject directories only; supplied derivatives stay separate.
 for p in sorted(root.glob('sub-*/eeg/*_eeg.set')):
  present=p.is_file();rows.append({'subject':p.parent.parent.name,'recording':str(p.resolve()) if present else str(p),'status':'PRESENT_UNVERIFIED' if present else 'MISSING_CONTENT','bytes':p.stat().st_size if present else 0})
 if not rows:raise ValueError('No raw sub-*/eeg/*_eeg.set files found. Supply the dataset root, not a subject folder.')
 out.mkdir(parents=True,exist_ok=False)
 with (out/'inventory.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 meta={}
 for n in ['dataset_description.json','participants.tsv','participants.json','README','README.md']:
  p=root/n
  if p.is_file():meta[n]=sha(p)
 write_json(out/'inventory_summary.json',{'version':VERSION,'recordings':len(rows),'subjects':len({v['subject'] for v in rows}),'status_counts':{s:sum(r['status']==s for r in rows) for s in {r['status'] for r in rows}},'metadata_hashes':meta,'note':'Presence inventory only. EEG readability and license/provenance require dataset metadata review.'})
 print('REPORT:',out)
def analyze(data,sf,names,excluded=None, *, min_usable_channels=None):
 """data volts, shape channels x samples. Four-second nonoverlapping windows."""
 data=np.asarray(data,dtype=float)
 if data.ndim!=2 or len(names)!=data.shape[0] or not np.isfinite(data).all():raise ValueError('Invalid EEG array')
 if sf<100 or data.shape[1]<int(sf*24):raise ValueError('Need >=24 seconds at >=100 Hz')
 # Causal Butterworth keeps state across the full pilot. Exclude first 10 s
 # from spectral summaries to limit startup transients. Reference unchanged.
 sos=signal.butter(4,[.5,30],btype='bandpass',fs=sf,output='sos')
 filtered=signal.sosfilt(sos,data,axis=-1);size=int(round(4*sf));features=[];qc=[]
 for start in range(int(round(10*sf)),data.shape[1]-size+1,size):
  raw=data[:,start:start+size];x=filtered[:,start:start+size];uv=raw*1e6
  ptp=np.ptp(uv,axis=1);sd=np.std(uv,axis=1)
  flags=[]
  if np.any(ptp>200):flags.append('AMPLITUDE_OVER_200_UV')
  if np.any(sd<.1):flags.append('FLAT_CHANNEL_SD_UNDER_0_1_UV')
  if excluded and any(start/sf<b and (start+size)/sf>a for a,b in excluded):flags.append('BAD_ANNOTATION_OVERLAP')
  qc.append({'start_s':start/sf,'duration_s':4,'flags':flags,'max_ptp_uv':float(max(ptp)),'min_sd_uv':float(min(sd))})
  usable=(ptp<=200)&(sd>=.1)
  if min_usable_channels is None:
   if flags:continue
  elif 'BAD_ANNOTATION_OVERLAP' in flags or np.count_nonzero(usable)<min_usable_channels:
   continue
  f,p=signal.welch(x,fs=sf,window='hann',nperseg=int(round(2*sf)),noverlap=int(round(sf)),detrend='constant',axis=-1,scaling='density')
  df=f[1]-f[0];mask=(f>=.5)&(f<30);total=p[:,mask].sum(axis=1)*df
  for ch,name in enumerate(names):
   if not usable[ch] or total[ch]<=0:continue
   row={'channel':name,'start_s':start/sf,'total_0_5_30_uv2':float(total[ch]*1e12)}
   for band,(a,b) in BANDS.items():
    power=float(p[ch,(f>=a)&(f<b)].sum()*df);row[band+'_uv2']=power*1e12;row[band+'_relative']=power/total[ch]
   pr=p[ch,mask]/p[ch,mask].sum();nz=pr>0;row['normalized_spectral_entropy']=float(-np.sum(pr[nz]*np.log(pr[nz]))/np.log(len(pr)))
   am=(f>=8)&(f<13);af=f[am];ap=p[ch,am];peaks,_=signal.find_peaks(ap)
   peak=max(peaks,key=lambda i:ap[i]) if len(peaks) else None
   row['alpha_peak_candidate_hz']=float(af[peak]) if peak is not None and ap[peak]>2*np.median(ap) else None
   features.append(row)
 return filtered,features,qc

def render(out,data,sf,names,summary,features,quality=None):
 # Anti-alias resampling is display-only. Feature extraction uses original rate.
 from fractions import Fraction
 ratio=Fraction(100/float(sf)).limit_denominator(10000)
 display=signal.resample_poly(data,ratio.numerator,ratio.denominator,axis=-1)*1e6
 actual=sf*ratio.numerator/ratio.denominator
 payload={'source':summary['source'],'names':names,'sf':actual,'signal_uv':np.round(display,3).tolist(),'summary':summary,'features':features}
 if quality is not None:payload['quality']=quality
 write_json(out/'replay.json',payload)
 template=Path(__file__).with_name('replay.html').read_text(encoding='utf-8')
 (out/'replay.html').write_text(template.replace('__PAYLOAD__',json.dumps(payload,allow_nan=False).replace('<','\\u003c')),encoding='utf-8')
def prepare(path,out,seconds,offset):
 if path.suffix.lower()!='.set':raise ValueError('Expected an EEGLAB .set recording')
 inputs={str(p):sha(p) for p in path.parent.iterdir() if p.is_file() and p.suffix.lower() in ['.set','.fdt','.json','.tsv']}
 try:
  import mne
 except ImportError:
  data,sf,names,excluded=read_embedded(path)
  a=int(round(offset*sf));b=a+int(round(seconds*sf))
  data=data[:,a:b].astype(float)*1e-6
  excluded=[(start-a/sf,stop-a/sf) for start,stop in excluded]
  reader='scipy embedded EEGLAB'
 else:
  with mne.io.read_raw_eeglab(path,preload=False,verbose='ERROR') as raw:
   sf=float(raw.info['sfreq']);picks=mne.pick_types(raw.info,eeg=True,exclude=[])
   if not len(picks):raise ValueError('No EEG channels')
   a=int(round(offset*sf));b=min(raw.n_times,a+int(round(seconds*sf)))
   data=raw.get_data(picks=picks,start=a,stop=b);names=[raw.ch_names[i] for i in picks]
   excluded=[(float(on)-raw.first_time-a/sf,float(on)-raw.first_time+max(float(dur),.02)-a/sf) for on,dur,desc in zip(raw.annotations.onset,raw.annotations.duration,raw.annotations.description) if str(desc).lower().startswith(('bad','boundary'))]
   if raw.info['bads']:raise ValueError('Recording marks bad channels; manual review required before this pilot')
  reader=f'MNE {mne.__version__}'
 filtered,features,qc=analyze(data,sf,names,excluded)
 if inputs!={p:sha(Path(p)) for p in inputs}:raise RuntimeError('Source changed during processing')
 out.mkdir(parents=True,exist_ok=False)
 summary={'version':VERSION,'source':'PRERECORDED RESEARCH EEG REPLAY','recording':path.name,'input_hashes':inputs,'script_sha256':sha(Path(__file__)),'sample_hz':sf,'channels':names,'offset_s':offset,'pilot_duration_s':data.shape[1]/sf,'accepted_windows':sum(not w['flags'] for w in qc),'review_windows':sum(bool(w['flags']) for w in qc),'gate':'DESCRIPTIVE_RESEARCH_ONLY' if any(not w['flags'] for w in qc) else 'INSUFFICIENT_EVIDENCE','reference':'unchanged from source; verify EEG sidecar','filter':'causal Butterworth order 4 bandpass 0.5-30 Hz; 10 s warm-up','psd':'Welch Hann 2 s / 50 percent overlap; nonoverlapping 4 s analysis windows','qc':'heuristic amplitude/flatness and BAD annotations, not validated artifact detection','versions':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'reader':reader},'limitations':['Pilot segment only; no whole-recording conclusion.','No ICA or automatic artifact correction. No electrode impedance or true SNR measurement.','Peak alpha candidate requires review; no clinical cutoff.','No ERP: resting-state recordings do not supply a controlled time-locked stimulus experiment.','No diagnosis/classifier/connectivity inference. Reference and volume conduction affect channel relationships.','Replay is precomputed offline; not a tested live acquisition pipeline.']}
 write_json(out/'summary.json',summary);write_json(out/'window_quality.json',qc);write_json(out/'features.json',features)
 render(out,filtered,sf,names,summary,features,qc);print('REPORT:',out)
def selftest(out):
 sf=250.;t=np.arange(30*250)/sf;data=np.vstack([20e-6*np.sin(2*np.pi*10*t),15e-6*np.sin(2*np.pi*6*t)])
 filtered,features,qc=analyze(data,sf,['Synthetic alpha','Synthetic theta'])
 a=[x for x in features if x['channel']=='Synthetic alpha'];assert a and all(x['alpha_relative']>.9 for x in a)
 assert all(abs(x['alpha_peak_candidate_hz']-10)<.6 for x in a)
 _,f2,q2=analyze(np.zeros_like(data),sf,['A','B']);assert not f2 and all(w['flags'] for w in q2)
 _,f3,q3=analyze(data,sf,['A','B'],[(0,30)]);assert not f3
 out.mkdir(parents=True,exist_ok=False);render(out,filtered,sf,['Synthetic alpha','Synthetic theta'],{'source':'SYNTHETIC ENGINE TEST - NOT EEG FROM A PERSON','gate':'SIMULATION_ONLY','accepted_windows':len(qc),'limitations':['Software check only; not biological validation.']},features)
 print('PASS: spectral recovery, flat-channel rejection, BAD annotation exclusion. DEMO:',out/'replay.html')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['inventory','prepare','selftest']);ap.add_argument('--root',type=Path);ap.add_argument('--recording',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--seconds',type=float,default=60);ap.add_argument('--offset',type=float,default=0);a=ap.parse_args()
 if not 24<=a.seconds<=120 or a.offset<0:ap.error('seconds must be 24..120 and offset >=0')
 if a.action=='inventory':
  if not a.root:ap.error('--root required')
  inventory(a.root,a.out)
 elif a.action=='prepare':
  if not a.recording:ap.error('--recording required')
  prepare(a.recording,a.out,a.seconds,a.offset)
 else:selftest(a.out)
if __name__=='__main__':main()
