"""Original experimental protocols. No clinical scoring or vendor algorithms.
All routes require administrator access; storage uses the existing authorized workspace.
"""
import csv, hashlib, io, json, math, secrets, sqlite3, statistics, time, uuid
from contextlib import contextmanager
from fastapi import HTTPException, Request

VERSION='bainp-research-1.0.0'
TASKS={
 'spatial-sequence':{'title':'Spatial sequence','engine':'NeuroCognition','domain':'Visual sequence recall','duration':'About 2 minutes','instructions':'Watch numbered cells light up. Then select the same cells in the same order. Six trials, lengths 2 through 4.','visual':True},
 'response-control':{'title':'Respond or wait','engine':'NeuroCognition','domain':'Response control','duration':'About 1 minute','instructions':'Select Respond when GO appears. Do not respond when WAIT appears. There are 24 trials.','visual':True},
 'paired-association':{'title':'Symbol–location learning','engine':'NeuroCognition','domain':'Visual associative learning','duration':'About 2 minutes','instructions':'Study four symbols and their numbered locations. Then select the remembered location for each symbol. Two study/test rounds.','visual':True},
}
LIMITATIONS=['Experimental protocol; no clinical norms, disease classifier or validated reliable-change threshold.', 'Browser timings and submitted measurements are not independently attested.', 'These results do not alter NeuroQuest, NeuroGuard or clinical eligibility.']
def fail(message,status=422):raise HTTPException(status,message)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def finite(x,lo,hi,name):
 if type(x) not in (float,int) or not math.isfinite(x) or not lo<=x<=hi:fail('Invalid '+name)
 return x
def text(x,name,maxlen=120):
 if not isinstance(x,str) or not x.strip() or len(x)>maxlen:fail('Required or invalid '+name)
 return x.strip()
def plan(task):
 rng=secrets.SystemRandom()
 if task=='spatial-sequence':return {'sequences':[rng.sample(range(9),n) for n in [2,2,3,3,4,4]]}
 if task=='response-control':
  values=[True]*16+[False]*8;rng.shuffle(values);return {'go':values,'window_ms':1500,'gap_ms':500}
 return {'pairs':rng.sample(range(4),4),'symbols':['★','◆','●','▲'],'queries':[rng.sample(range(4),4) for _ in range(2)]}
def score(task,p,answers):
 if not isinstance(answers,list):fail('Responses must be a list.')
 if task=='spatial-sequence':
  expected=p['sequences']
  if len(answers)!=len(expected) or any(not isinstance(a,list) or len(a)!=len(b) or any(type(v)!=int or v not in range(9) for v in a) for a,b in zip(answers,expected)):fail('Invalid sequence responses.')
  return {'correct_trials':sum(a==b for a,b in zip(answers,expected)),'total_trials':len(expected),'correct_positions':sum(sum(x==y for x,y in zip(a,b)) for a,b in zip(answers,expected))}
 if task=='paired-association':
  expected=[p['pairs'][i] for query in p['queries'] for i in query]
  if len(answers)!=len(expected) or any(type(v)!=int or v not in range(4) for v in answers):fail('Invalid location responses.')
  return {'correct_responses':sum(a==b for a,b in zip(answers,expected)),'total_responses':len(expected),'by_round':[sum(answers[j+i]==expected[j+i] for i in range(4)) for j in (0,4)]}
 if len(answers)!=len(p['go']):fail('All response-control trials are required.')
 for a in answers:
  if a is not None:finite(a,0,p['window_ms'],'response time')
 hits=[a for go,a in zip(p['go'],answers) if go and a is not None]
 return {'go_responses':len(hits),'missed_go':sum(go and a is None for go,a in zip(p['go'],answers)), 'wait_responses':sum(not go and a is not None for go,a in zip(p['go'],answers)), 'median_go_response_ms':statistics.median(hits) if hits else None,'anticipatory_responses_under_100ms':sum(a<100 for a in hits)}

def signal_features(kind,raw,meta):
 try:import numpy as np
 except ImportError:fail('Signal analysis requires numpy in the bainp environment.',503)
 raw=text(raw,'CSV',700000)
 if not isinstance(meta,dict):fail('Metadata required.')
 for field in ('device','protocol','placement' if kind=='motion' else 'reference'):text(meta.get(field),field)
 units='m/s2' if kind=='motion' else 'uV'
 if meta.get('units')!=units:fail('Use physical units '+units+'; no automatic unit conversion is performed.')
 try:
  reader=csv.reader(io.StringIO(raw));header=next(reader)
  if kind=='motion' and header!=['t','ax','ay','az']:fail('Motion columns must be t,ax,ay,az.')
  if kind=='eeg' and (len(header)<2 or len(header)>17 or header[0]!='t' or len(set(header))!=len(header)):fail('EEG requires t and 1–16 uniquely named channels.')
  rows=list(reader)
  if not 64<=len(rows)<=20000:fail('Use 64–20000 samples.')
  if any(len(row)!=len(header) for row in rows):fail('CSV row width mismatch.')
  values=np.asarray(rows,dtype=float)
 except (ValueError,StopIteration):fail('CSV must contain a header and numeric samples.')
 if not np.isfinite(values).all():fail('Missing or non-finite samples are not accepted.')
 t=values[:,0];dt=np.diff(t)
 if np.any(dt<=0):fail('Timestamps must strictly increase in seconds.')
 step=float(np.median(dt));fs=1/step;duration=float(t[-1]-t[0]);jitter=float(np.max(np.abs(dt-step))/step)
 if duration<10:fail('At least 10 seconds of data are required.')
 if not (25<=fs<=1000 if kind=='motion' else 80<=fs<=2000):fail('Unsupported sample rate for this analysis.')
 if jitter>0.05:fail('Irregular timestamps or gaps exceed the 5% engineering tolerance; repair acquisition, not values.')
 y=values[:,1:];maxabs=float(np.max(np.abs(y)))
 if maxabs>(1000 if kind=='motion' else 100000):fail('Values exceed the import sanity range. Verify units.')
 # Per-axis/channel centering avoids gravity dominating the movement spectrum.
 y=y-y.mean(axis=0);window=np.hanning(len(y));freq=np.fft.rfftfreq(len(y),step)
 psd=np.abs(np.fft.rfft(y*window[:,None],axis=0))**2/(fs*np.sum(window**2))
 psd[1:-1]*=2
 bands={'oscillation_3_12_hz':(3,12)} if kind=='motion' else {'delta':(.5,4),'theta':(4,8),'alpha':(8,13),'beta':(13,30)}
 features=[]
 for i,name in enumerate(header[1:]):
  total=float(psd[(freq>=.5)&(freq<=min(30,fs/2)),i].sum());item={'channel':name,'centered_rms':float(np.sqrt(np.mean(y[:,i]**2))), 'relative_power':{key:float(psd[(freq>=a)&(freq<b),i].sum()/total) if total>0 else None for key,(a,b) in bands.items()}}
  mask=(freq>=3)&(freq<=12);item['peak_3_12_hz']=float(freq[mask][np.argmax(psd[mask,i])]) if kind=='motion' and total>0 else None
  features.append(item)
 flags=['FLAT_CHANNEL'] if any(x['centered_rms']<1e-9 for x in features) else []
 return {'kind':kind,'sample_hz':fs,'duration_s':duration,'samples':len(y),'max_interval_deviation_fraction':jitter,'units':units,'features':features,'quality_flags':flags,'quality_status':'needs_review' if flags else 'technical_checks_passed_not_clinical_validation','metadata':{k:meta[k] for k in ('device','protocol','units', 'placement' if kind=='motion' else 'reference')},'input_sha256':hashlib.sha256(raw.encode()).hexdigest(),'method':'mean-centred full-record Hann periodogram; relative power denominator 0.5–30 Hz or Nyquist','limitations':LIMITATIONS+(['Oscillation frequency does not identify Parkinson’s disease, essential tremor or another diagnosis. Motion, placement and device properties can confound these features.'] if kind=='motion' else ['No sleep staging, seizure detection, artifact correction, ERP, disease classification or Beacon model is provided.'])}

def imaging_import(data):
 if not isinstance(data,dict) or data.get('schema')!='bainp-regional-volumes-v1':fail('Use the supplied regional MRI tool output.')
 for field in ('atlas','pipeline','pipeline_version','acquisition_protocol','scanner') :text(data.get(field),field)
 for field in ('image_sha256','labels_sha256'):
  value=data.get(field)
  if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):fail('Invalid source hash.')
 regions=data.get('regions')
 if not isinstance(regions,list) or not 1<=len(regions)<=1000:fail('Expected 1–1000 labelled regions.')
 seen=set();out=[]
 for r in regions:
  label=r.get('label')
  if type(label)!=int or label<=0 or label in seen:fail('Invalid or duplicate region label.')
  seen.add(label);out.append({'label':label,'name':text(r.get('name'),'region name'),'volume_mm3':finite(r.get('volume_mm3'),0,5000000,'volume')})
 return {k:data[k] for k in ('schema','atlas','pipeline','pipeline_version','acquisition_protocol','scanner','image_sha256','labels_sha256')} | {'regions':out,'kind':'imaging','quality_status':'imported_requires_anatomical_review','quality_flags':['NOT_ANATOMICALLY_VERIFIED'],'limitations':LIMITATIONS+['Imported atlas labels must be reviewed over the source scan. No segmentation model, normative percentile, cortical thickness, WMH or PET inference is supplied.']}

def mount_research_lab(app,accounts,identity):
 def actor(mode):
  p=identity()
  if p['role']!='admin':fail('Experimental studio is administrator-only.',403)
  if mode not in ('active','demo'):fail('Invalid record mode.')
  return p
 @contextmanager
 def db(mode):
  p=actor(mode);c=sqlite3.connect(accounts.workspace(p));c.row_factory=sqlite3.Row
  c.execute('CREATE TABLE IF NOT EXISTS research_runs(id TEXT PRIMARY KEY,mode TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL)')
  try:yield c;c.commit()
  except Exception:c.rollback();raise
  finally:c.close()
 async def body(req):
  chunks=[];length=0
  async for chunk in req.stream():
   length+=len(chunk)
   if length>1000000:fail('Maximum research request is 1 MB.',413)
   chunks.append(chunk)
  try:
   value=json.loads(b''.join(chunks),parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
   if not isinstance(value,dict):raise ValueError()
   return value
  except (ValueError,UnicodeError):fail('Invalid JSON object.')
 def get(c,rid,mode):
  row=c.execute('SELECT payload FROM research_runs WHERE id=? AND mode=?',(rid,mode)).fetchone()
  if not row:fail('Record not found.',404)
  return json.loads(row[0])
 def insert(c,mode,kind,payload):
  rid=str(uuid.uuid4());payload=dict(payload,id=rid,kind=kind,version=VERSION,created=time.time(),mode=mode,actor=identity()['user_id'],workspace=identity()['target'] or identity()['user_id'],clinical_use=False,participant_linkage='none; isolated workspace research record')
  payload['record_sha256']=digest(payload)
  c.execute('INSERT INTO research_runs VALUES(?,?,?,?,?)',(rid,mode,kind,canonical(payload),payload['created']))
  accounts.audit(identity()['user_id'],'research_record_created',payload['workspace'],kind+' '+rid)
  return payload
 @app.get('/api/research-lab/catalogue')
 def catalogue(mode:str='active'):
  actor(mode);return {'version':VERSION,'tasks':TASKS,'limitations':LIMITATIONS,'role':'administrator_only','clinical_integration':False}
 @app.get('/api/research-lab/records')
 def records(mode:str='active',offset:int=0):
  if offset<0:fail('Invalid offset.')
  with db(mode) as c:rows=c.execute('SELECT payload FROM research_runs WHERE mode=? ORDER BY created DESC LIMIT 51 OFFSET ?',(mode,offset)).fetchall()
  return {'items':[json.loads(r[0]) for r in rows[:50]],'has_more':len(rows)>50}
 @app.post('/api/research-lab/start')
 async def start(req:Request,mode:str='active'):
  actor(mode);b=await body(req);task=b.get('task')
  if task not in TASKS:fail('Unknown task.')
  if b.get('consent') is not True:fail('Explicit experimental storage consent is required.')
  access=b.get('access',{})
  if not isinstance(access,dict) or access.get('can_perceive') is not True or access.get('can_respond') is not True:fail('Confirm that the task display and response method are usable. Glasses alone are not a restriction.')
  if set(access)-{'can_perceive','can_respond','assistance','urgent_concern'}:fail('Unknown access field.')
  if access.get('assistance') not in ('none','navigation'):fail('Answer assistance is unsupported by these task protocols.')
  if access.get('urgent_concern') is not False:fail('Routine research tasks require no current urgent concern. Return to the guided safety pathway.')
  with db(mode) as c:return insert(c,mode,'task_started',{'task':task,'protocol':task+'-v1','state':'started','consent':True,'access':access,'plan':plan(task),'limitations':LIMITATIONS})
 @app.post('/api/research-lab/complete/{rid}')
 async def complete(rid:str,req:Request,mode:str='active'):
  actor(mode);b=await body(req)
  with db(mode) as c:
   c.execute('BEGIN IMMEDIATE');start=get(c,rid,mode)
   if start.get('state')!='started':fail('Not a task start.')
   results=c.execute("SELECT payload FROM research_runs WHERE mode=? AND kind='task_result'",(mode,)).fetchall()
   for row in results:
    old=json.loads(row[0])
    if old['start_id']==rid:
     if old['submission_sha256']!=digest(b):fail('Task already has a different final submission.',409)
     return old
   if b.get('consent') is not True:fail('Result storage consent required.')
   if b.get('state') not in ('completed','aborted'):fail('Invalid completion state.')
   elapsed=time.time()-start['created']
   if elapsed>3600:fail('Task expired; start a fresh run.',409)
   hidden=b.get('hidden_count',0)
   if type(hidden)!=int or not 0<=hidden<=10000:fail('Invalid interruption count.')
   result=score(start['task'],start['plan'],b.get('answers')) if b['state']=='completed' else {}
   return insert(c,mode,'task_result',{'start_id':rid,'task':start['task'],'protocol':start['protocol'],'state':b['state'],'elapsed_wall_seconds':elapsed,'answers':b.get('answers',[]) if b['state']=='completed' else [],'metrics':result,'submission_sha256':digest(b),'quality_flags':(['TAB_HIDDEN'] if hidden else [])+(['INTERRUPTED'] if b['state']=='aborted' else []),'limitations':LIMITATIONS,'consent':True})
 @app.post('/api/research-lab/import/{kind}')
 async def import_record(kind:str,req:Request,mode:str='active'):
  actor(mode);b=await body(req)
  if b.get('consent') is not True:fail('Explicit storage consent required.')
  if kind in ('motion','eeg'):result=signal_features(kind,b.get('csv'),b.get('metadata'))
  elif kind=='imaging':result=imaging_import(b.get('data'))
  elif kind=='voice':
   v=b.get('data',{})
   if not isinstance(v,dict):fail('Invalid voice measurements.')
   result={'kind':'voice','protocol':'guided-reading-v1','duration_s':finite(v.get('duration_s'),1,60,'duration'),'rms':finite(v.get('rms'),0,1,'RMS'),'clipping_fraction':finite(v.get('clipping_fraction'),0,1,'clipping fraction'),'sample_hz':finite(v.get('sample_hz'),8000,192000,'sample rate'),'quality_status':'browser_measured_requires_review','limitations':LIMITATIONS+['Local microphone signal level only. No transcription, speech disorder classification, facial analysis or Modality.AI model. Raw audio is not uploaded.']}
  else:fail('Unknown import kind.')
  with db(mode) as c:return insert(c,mode,kind,dict(result,consent=True))
 @app.get('/api/research-lab/compare')
 def compare(first:str,second:str,mode:str='active'):
  with db(mode) as c:a=get(c,first,mode);b=get(c,second,mode)
  if first==second:fail('Choose distinct records.')
  if a.get('kind')!='imaging' or b.get('kind')!='imaging':fail('This comparison accepts regional MRI imports only.')
  keys=('atlas','pipeline','pipeline_version','acquisition_protocol','scanner')
  if any(a[k]!=b[k] for k in keys):fail('Acquisition or pipeline mismatch; no automatic comparison.')
  ar={r['label']:r for r in a['regions']};br={r['label']:r for r in b['regions']}
  if ar.keys()!=br.keys() or any(ar[k]['name']!=br[k]['name'] for k in ar):fail('Region definitions differ.')
  return {'first':first,'second':second,'state':'unverified_descriptive_difference','regions':[{'name':ar[k]['name'],'difference_mm3':br[k]['volume_mm3']-ar[k]['volume_mm3']} for k in ar],'limitations':['Participant linkage and anatomical accuracy are not verified. A numerical difference is not established atrophy or disease progression. No annualization, norms or clinical interpretation.']}
