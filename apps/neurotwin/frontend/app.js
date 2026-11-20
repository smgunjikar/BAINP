'use strict';
const $=id=>document.getElementById(id),q=new URLSearchParams(location.search),mode=q.get('mode'),person=q.get('person');
let current=null,busy=false,pending=false,epoch=0,lastRevision='',options=[],brainKey='',neuralKey='',neuralData=null,replaying=false,replayTimer=null,replayOffset=0,renderer=null,volumeRenderer=null;
let profile=mode==='demo'?(q.get('profile')||'control'):'selected';if(!['selected','control','impairment'].includes(profile))profile='control';
const synthetic=()=>mode==='demo'&&profile!=='selected';
const number=v=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat(undefined,{maximumFractionDigits:3}).format(v):'—';
const human=s=>String(s||'unknown').replaceAll('_',' ').toLowerCase();const date=s=>s?(s.length===10?s:new Date(s).toLocaleString()):'Date unrecorded';
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function row(values){const r=el('tr');for(const value of values)r.append(el('td',value));return r}
function empty(id,text){$(id).replaceChildren(el('p',text,'empty'))}
function base(){return 'participants/'+encodeURIComponent(person)}
function sourceURL(path){return path+'?'+new URLSearchParams({mode,person})}
async function api(path,method='GET',body){const r=await fetch('/api/neurotwin/'+path,{cache:'no-store',method,headers:{'Content-Type':'application/json','X-NeuroAccess-Request':'1'},...(body===undefined?{}:{body:JSON.stringify(body)})});let d;try{d=await r.json()}catch{throw Error('The API response is unavailable. Check the BAINP API terminal.')}if(!r.ok)throw Error(r.status===401?'Sign in on the BAINP home page, then refresh.':(typeof d.detail==='string'?human(d.detail):'Invalid or unsupported input')+' ('+r.status+')');return d}
$('home').href=sourceURL('/');$('visionLink').href=sourceURL('/neurovision');$('profileLabel').hidden=mode!=='demo';$('profile').value=profile;
$('profile').onchange=()=>{profile=$('profile').value;epoch++;lastRevision='';brainKey='';neuralKey='';stopReplay();clearBrain();refresh(true)};
function tab(name){for(const b of document.querySelectorAll('[data-tab]')){const active=b.dataset.tab===name;b.setAttribute('aria-pressed',String(active));$(b.dataset.tab).hidden=!active}if(name==='cognitive')renderCognitive();if(name==='neural')drawEEG();}
for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>tab(b.dataset.tab);for(const b of document.querySelectorAll('[data-go]'))b.onclick=()=>{tab(b.dataset.go);window.scrollTo?.({top:0,behavior:'smooth'})};
function svg(tag,attributes={},text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attributes))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e}
function lineChart(id,points,unit,filtered=[]){const g=$(id);g.replaceChildren();const pts=points.filter(p=>p.at&&Number.isFinite(Date.parse(p.at))&&Number.isFinite(p.value));if(!pts.length){g.append(svg('text',{x:50,y:100},'No linked observations available'));return}const box=g.getAttribute('viewBox').split(' ').map(Number),width=box[2],height=box[3],left=75,right=width-30,top=25,bottom=height-38,times=pts.map(p=>Date.parse(p.at)),vals=pts.map(p=>p.value),lo=Math.min(...vals,...filtered.map(p=>p.lower)),hi=Math.max(...vals,...filtered.map(p=>p.upper)),pad=(hi-lo)*.12||Math.abs(lo)*.05||1,min=lo-pad,max=hi+pad,t0=Math.min(...times),span=Math.max(...times)-t0||86400000,x=t=>left+(t-t0)/span*(right-left),y=v=>bottom-(v-min)/(max-min)*(bottom-top);
for(let i=0;i<5;i++){const v=min+(max-min)*i/4,yy=y(v);g.append(svg('line',{x1:left,x2:right,y1:yy,y2:yy,stroke:'#e1e9ef'}),svg('text',{x:left-9,y:yy+4,'text-anchor':'end'},number(v)))}g.append(svg('text',{x:left,y:height-10},new Date(t0).toISOString().slice(0,10)),svg('text',{x:right,y:height-10,'text-anchor':'end'},new Date(Math.max(...times)).toISOString().slice(0,10)),svg('text',{x:left,y:15},unit));
if(filtered.length){const upper=filtered.map(p=>x(Date.parse(p.at))+','+y(p.upper)),lower=filtered.slice().reverse().map(p=>x(Date.parse(p.at))+','+y(p.lower));g.append(svg('polygon',{points:upper.concat(lower).join(' '),fill:'#d5e8f2',opacity:'.65'}),svg('polyline',{points:filtered.map(p=>x(Date.parse(p.at))+','+y(p.value)).join(' '),fill:'none',stroke:'#5b9bbb','stroke-width':2}))}
if(pts.length>1)g.append(svg('polyline',{points:pts.map(p=>x(Date.parse(p.at))+','+y(p.value)).join(' '),stroke:'#326d8d','stroke-width':1.5,fill:'none',opacity:'.65'}));for(const p of pts){const dot=svg('circle',{cx:x(Date.parse(p.at)),cy:y(p.value),r:pts.length>100?2:4,fill:p.eligible===false?'#b38a4c':'#32758f'});dot.append(svg('title',{},date(p.at)+': '+number(p.value)+' '+unit));g.append(dot)}}
function selectOptions(id,items,label,latest=false){const old=$(id).value;$(id).replaceChildren();for(const item of items){const o=el('option',label(item));o.value=item.id||item.record_id;$(id).append(o)}if(items.some(s=>(s.id||s.record_id)===old))$(id).value=old;else if(items.length)$(id).value=items[latest?items.length-1:0].id||items[latest?items.length-1:0].record_id;}
function render(d){current=d;$('mode').textContent=synthetic()?'SYNTHETIC DEMO · INVENTED DATA':mode==='demo'?'DEMO · SELECTED FICTIONAL RECORDS':'ACTIVE · VERIFIED SOURCE RECORDS';$('name').textContent=d.identity.display_name;$('identity').textContent=synthetic()?'One coherent fictional profile across every modality. No real participant or linked research dataset.':'Participant '+d.identity.participant_id+' · profile revision '+d.identity.profile_revision;
$('warning').textContent=synthetic()?'All case labels, anatomy and clinical values are invented. EEG features are computed from synthetic oscillators. Forecast values use an invented simulator and have no clinical meaning.':'Research only. Incompatible conditions remain separate; forecasts require a reviewed supported model. Missing measurements remain missing.';
$('sources').replaceChildren();for(const [source,state] of Object.entries(d.source_states)){const c=el('div',undefined,'source');c.append(el('b',source),el('span',String(state.count||0),'count'),el('span',human(state.state)));$('sources').append(c)}
$('twinCards').replaceChildren();const firstCog=d.series.find(s=>s.source==='NeuroCognition X'&&s.metric==='C01:correct'),neural=d.neural_recordings.at(-1);for(const [title,eyebrow,value,detail,go] of [['3D Brain Twin','STRUCTURE',d.imaging.length+' visits',d.imaging.length?'Linked or synthetic anatomical observations':'Verified MRI required','anatomical'],['Cognitive Twin','PERFORMANCE',d.cognition_sessions+' sessions',firstCog?'Memory, attention and condition-specific history':'Repeated valid assessments needed','cognitive'],['Neural Twin','ELECTRICAL',neural?neural.channels.length+' channels':'Awaiting EEG',neural?neural.pipeline:'No EEG measurement is inferred from a smartwatch','neural'],['Predictive Twin','RESEARCH FORECAST',d.forecast.value==null?'Observed history':number(d.forecast.value*100)+'%',human(d.forecast.state),'predictive']]){const c=el('div',undefined,'twinCard'),b=el('button','↗');b.setAttribute('aria-label','Open '+title);b.onclick=()=>tab(go);c.append(el('p',eyebrow,'eyebrow'),el('h3',title),el('strong',value),el('p',detail),b);$('twinCards').append(c)}
lineChart('overviewChart',firstCog?.points||[],firstCog?.unit||'');$('overviewChartNote').textContent=firstCog?firstCog.label+' · condition '+firstCog.condition+'. Individual task observations; no overall clinical score.':'No cognitive measurements are linked.';
selectOptions('scan',d.imaging,s=>s.metadata.visit+' · '+(s.metadata.date||'undated')+' · '+s.id,true);if(d.imaging.length&&!d.imaging.some(s=>s.id===$('scan').value))$('scan').value=d.imaging.at(-1).id;
selectOptions('metric',d.series.filter(s=>s.source==='NeuroCognition X'),s=>s.label+' · '+s.condition);selectOptions('wearMetric',d.series.filter(s=>s.source==='NeuroSense'),s=>s.label+' · '+s.condition);selectOptions('anatomyMetric',d.series.filter(s=>s.source==='NeuroVision'),s=>s.label+' · '+s.condition);
selectOptions('neuralSelect',d.neural_recordings,s=>date(s.observed_at)+' · '+s.channels.join(', '),true);renderWearable();renderCognitive();renderClinical();renderBrainBodyContext();renderForecast(d.forecast);renderGovernance();loadBrain();loadNeural();}

function renderBrainBodyContext(){const d=current.brain_body;const url=synthetic()?'/brain-body?mode=demo&profile='+profile:sourceURL('/brain-body');$('brainBodyLink').href=url;$('brainBodyContext').replaceChildren();if(!d){$('brainBodyContext').append(el('p','No BBC-BE source is connected.'));return}$('brainBodyContext').append(el('p',d.interpretation),el('p',d.record_count+' authorized source records; '+d.pending_reviews+' pending source/context reviews.'));for(const issue of d.issues||[])$('brainBodyContext').append(el('p',issue));for(const m of d.latest.slice(0,6))$('brainBodyContext').append(el('p',m.label+': '+(m.qualifier==='exact'?number(m.value):human(m.qualifier))+' '+m.unit+' · '+date(m.observed_at)+' · '+m.source));}
function renderWearable(){const streams=current.series.filter(s=>s.source==='NeuroSense');$('wearableCards').replaceChildren();for(const [key,label,unit] of [['heart_rate','Heart rate','bpm'],['sleep_duration','Sleep duration','h'],['steps','Daily activity','steps'],['movement_rms','Movement RMS','g']]){const candidates=streams.filter(s=>s.metric===key).flatMap(s=>s.points).sort((a,b)=>a.at.localeCompare(b.at)),latest=candidates.at(-1),c=el('div',undefined,'miniMetric');c.append(el('b',label),el('strong',latest?number(latest.value)+' '+unit:'—'),el('span',latest?date(latest.at)+(latest.flags.length?' · quality review':''):'No observations'));$('wearableCards').append(c)}const s=streams.find(s=>s.id===$('wearMetric').value);lineChart('wearChart',s?.points||[],s?.unit||'');$('wearNote').textContent=s?'Same device, method, protocol and unit. '+s.coverage.observed_days+' observed days; expected schedule unknown. Live connection is not established by these stored records.':'No wearable observations linked.'}
function renderCognitive(){if(!current)return;const s=current.series.find(s=>s.id===$('metric').value);lineChart('cognitiveChart',s?.points||[],s?.unit||'',s?.state_filter||[]);$('domains').replaceChildren();for(const domain of current.domains){const c=el('div',undefined,'domain');c.append(el('b',domain.id+' · '+domain.label),el('span',domain.sessions+' saved task records'));$('domains').append(c)}$('points').replaceChildren();if(s){const f=s.estimate;$('fit').textContent=f.state==='EXPLORATORY_DESCRIPTIVE_FIT'?'Descriptive slope: '+number(f.slope_per_30_days)+' '+s.unit+' per 30 days. Residual spread: '+number(f.residual_sd)+' '+s.unit+'. '+f.caveat:'No fitted trend: '+human(f.state)+'. Quality flags and conditions may prevent fitting.';$('filterNote').textContent=s.filter_assumptions||(synthetic()?'Select a response-time series to inspect the assumed-variance illustrative filter. No calibrated clinical reliable-change or practice correction is demonstrated.':'No calibrated state filter, reliable-change index or practice-effect correction is installed for this active series.');$('coverage').textContent=s.total+' observations; '+s.eligible+' eligible for fitting. '+s.coverage.observed_days+' recorded days. Missingness percentages require an expected schedule.';for(const p of s.points)$('points').append(row([date(p.at),number(p.value)+' '+s.unit,p.eligible?'Eligible':'Excluded',p.flags.map(human).join('; ')||'No source flags']))}else{$('fit').textContent='No linked numeric cognitive series.';$('filterNote').textContent='';$('coverage').textContent=''}
$('cognitiveRecords').replaceChildren();for(const r of current.cognitive_records.slice().sort((a,b)=>b.at.localeCompare(a.at)).slice(0,60)){const detail=el('details');detail.append(el('summary',r.task+' · '+date(r.at)+' · '+human(r.status)));const sm=r.summary;detail.append(el('p',r.protocol+' · form '+r.form+' · condition '+r.condition_group));if(sm.reports)for(const report of sm.reports){detail.append(el('b',human(report.source)+' report'));for(const answer of report.answers||[])detail.append(el('p',human(answer.item)+': '+Object.entries(answer).filter(([k])=>k!=='item').map(([k,v])=>human(k)+' '+v).join('; ')))}if(sm.context)for(const [k,v] of Object.entries(sm.context))detail.append(el('p',human(k)+': '+v));if(r.reviewed_counts)for(const [k,v] of Object.entries(r.reviewed_counts))detail.append(el('p',human(k)+': '+number(v)+' (dictionary/reviewer record; not clinical validation)'));for(const [k,v] of Object.entries(sm))if(typeof v==='number')detail.append(el('p',human(k)+': '+number(v)));detail.append(el('p','Quality: '+((sm.quality_flags||[]).map(human).join('; ')||'no source flags')));$('cognitiveRecords').append(detail)}if(!current.cognitive_records.length)empty('cognitiveRecords','No task records available.')}
function renderClinical(){$('clinical').replaceChildren();const records=current.clinical_records.slice().sort((a,b)=>a.observed_at.localeCompare(b.observed_at)),r=records.at(-1);if(r){$('clinical').append(el('b',(synthetic()?'Invented clinical context: ':'Recorded clinical state: ')+human(r.clinical_state)),el('p',date(r.observed_at)+' · '+r.provenance));for(const o of r.observations)$('clinical').append(el('p',(o.instrument||human(o.metric))+': '+number(o.value)+' '+o.unit+' · '+o.context))}else empty('clinical','No verified clinical observations linked.');$('timeline').replaceChildren();for(const e of current.timeline.slice(0,12)){const c=el('div',undefined,'event');c.append(el('time',date(e.at)),el('b',e.title),el('p',e.source+' · '+human(e.status)));if(e.href&&!synthetic()){const a=el('a','Open source record');a.href=e.href;c.append(a)}$('timeline').append(c)}}
function clearBrain(){renderer?.set([]);volumeRenderer?.clear();$('brainEmpty').hidden=false;$('brainBadge').textContent='';}
async function loadBrain(){const token=epoch,scan=current?.imaging.find(s=>s.id===$('scan').value);if(!scan){clearBrain();lineChart('anatomyChart',[],'');$('anatomyChartNote').textContent='No anatomical history linked.';$('brainStatus').textContent='No identity-verified MRI is available.';$('anatomyMeasurements').replaceChildren(row(['No supported regional measurements','—','—','Verified source pipeline required']));$('anatomyNote').textContent='Hippocampal volumes and cortical thickness require reviewed anatomical processing. An intensity-class label is not a named brain structure.';return}const regional=(current.regional_anatomy||[]).filter(r=>r.scan_id===scan.id),key=[profile,scan.id,scan.package_sha256,$('brainView').value,regional.map(r=>r.package_sha256).join(',')].join(':');if(key===brainKey){renderAnatomyMeasurements(scan,regional);return}brainKey=key;clearBrain();$('brainEmpty').hidden=true;$('brainStatus').textContent='Loading linked anatomy…';try{if(synthetic()){$('brainMask').disabled=true;$('brainMask').checked=false;$('threshold').disabled=true;$('clip').disabled=true;const kind=$('brainView').value;renderer??=new TwinSurface($('brain'));$('brain').hidden=false;$('volume').hidden=true;renderer.set(illustrativeBrain(['hippocampi','ventricles'].includes(kind)?kind:'cortex',Number(scan.metadata.visit.slice(1))-1,profile));$('brainBadge').textContent='PROCEDURAL ILLUSTRATION · NOT AN MRI';$('brainStatus').textContent=renderer.g?'Drag to rotate · scroll to zoom · keyboard arrows and +/−. Geometry and regional values are invented.':'WebGL2 unavailable. Invented regional measurements remain available.';}else{const pack=await api(base()+'/anatomy/'+encodeURIComponent(scan.id)+'?mode='+mode);if(token!==epoch||key!==brainKey)return;if($('brainView').value==='intensity'){$('threshold').disabled=false;$('clip').disabled=false;volumeRenderer??=new MRITextureVolume($('volume'),text=>$('brainStatus').textContent=text);$('brain').hidden=true;$('volume').hidden=false;volumeRenderer.setPackage(pack);$('brainMask').checked=volumeRenderer.hasMask===true;$('brainMask').disabled=!volumeRenderer.hasMask;}else{$('brainMask').disabled=true;$('threshold').disabled=true;$('clip').disabled=true;let surfaces=pack.surfaces||[];if(regional.length){const fs=await api(base()+'/anatomical-records/'+regional.at(-1).package_sha256+'?mode='+mode);if(token!==epoch||key!==brainKey)return;surfaces=fs.surfaces}$('volume').hidden=true;$('brain').hidden=false;renderer??=new TwinSurface($('brain'));renderer.set(surfaces);$('brainStatus').textContent=surfaces.length?'Supplied scan-derived surfaces · drag/scroll or use keyboard to explore. No new reconstruction is generated by this viewer.':'No surfaces supplied for this scan. Use MRI intensity.';}$('brainBadge').textContent=regional.length?'VERIFIED LINKED MRI / SUPPLIED FREESURFER':'VERIFIED LINKED MRI · '+scan.id;}}catch(e){if(token===epoch){clearBrain();$('brainStatus').textContent=e.message;brainKey=''}}renderAnatomyMeasurements(scan,regional);}
function renderAnatomyMeasurements(scan,regional){$('anatomyMeasurements').replaceChildren();for(const m of scan.metadata.measurements||[])$('anatomyMeasurements').append(row([m.name,number(m.volume_ml),'mL',m.status||'Native-grid source measurement']));if(synthetic())$('anatomyMeasurements').append(row(['Illustrative mean cortical thickness',number(scan.metadata.cortical_thickness_mm),'mm','INVENTED; not measured from a cortical surface']));for(const r of regional)for(const m of r.measurements)$('anatomyMeasurements').append(row([m.name,number(m.value),m.unit,m.basis]));$('anatomyNote').textContent=synthetic()?'The 3D brain and every regional value are invented. These are not real MRI reconstructions, disease norms or results of segmentation.':regional.length?'Regional measurements and pial surfaces were supplied from FreeSurfer outputs linked to this source MRI. FreeSurfer segmentation-grid volumes differ from original native-grid voxel counting.':'Source-native measurements are shown as named by the processing pipeline. Hippocampal volume and cortical thickness are unavailable unless an anatomical package is supplied.';const s=current.series.find(s=>s.id===$('anatomyMetric').value);lineChart('anatomyChart',s?.points||[],s?.unit||'');$('anatomyChartNote').textContent=s?'Descriptive same-condition history. A line is not longitudinal registration or an atrophy diagnosis.':'No comparable anatomical history available.';}
function updateBrainOptions(){const old=$('brainView').value;$('brainView').replaceChildren();for(const [value,label] of synthetic()?[['cortex','Illustrative cortex'],['hippocampi','Illustrative hippocampi'],['ventricles','Illustrative ventricles']]:[['intensity','Linked MRI intensity'],['surfaces','Supplied scan-derived surfaces']]){const o=el('option',label);o.value=value;$('brainView').append(o)}if([...$('brainView').children].some(o=>o.value===old))$('brainView').value=old;else $('brainView').value=synthetic()?'cortex':'intensity';}
$('scan').onchange=()=>{brainKey='';loadBrain()};$('brainView').onchange=()=>{brainKey='';loadBrain()};$('resetBrain').onclick=()=>{renderer?.reset();if(volumeRenderer){volumeRenderer.rx=.2;volumeRenderer.ry=.3;volumeRenderer.zoom=1;volumeRenderer.draw()}};for(const id of ['threshold','clip','brainMask'])$(id).oninput=()=>{if(!volumeRenderer)return;volumeRenderer.threshold=Number($('threshold').value);volumeRenderer.clipping=Number($('clip').value);volumeRenderer.masked=$('brainMask').checked;volumeRenderer.draw()};$('anatomyMetric').onchange=()=>{const scan=current.imaging.find(s=>s.id===$('scan').value);if(scan)renderAnatomyMeasurements(scan,(current.regional_anatomy||[]).filter(r=>r.scan_id===scan.id))};$('metric').onchange=renderCognitive;$('wearMetric').onchange=renderWearable;
function stopReplay(){replaying=false;clearInterval(replayTimer);replayTimer=null;$('replay').textContent='Replay recorded segment';}
async function loadNeural(){const record=current?.neural_recordings.find(r=>r.record_id===$('neuralSelect').value);if(!record){stopReplay();neuralData=null;$('neuralSource').textContent='No verified EEG recording linked. Neural dynamics are unavailable.';drawEEG();$('bands').replaceChildren();$('spectrum').replaceChildren();empty('connectivity','Channel covariance not supplied.');empty('neuralMetrics','No spectral features.');$('neuralQuality').replaceChildren();return}const key=[profile,record.record_id,record.revision].join(':'),token=epoch;if(key===neuralKey)return;neuralKey=key;stopReplay();neuralData=null;drawEEG();$('bands').replaceChildren();$('spectrum').replaceChildren();$('neuralMetrics').replaceChildren();$('neuralQuality').replaceChildren();empty('connectivity','Loading the selected recording.');$('neuralSource').textContent='Loading selected EEG recording…';try{const data=await api(synthetic()?'demo-neural/'+encodeURIComponent(record.record_id)+'?profile='+profile:base()+'/neural-records/'+encodeURIComponent(record.record_id)+'?mode='+mode);if(token!==epoch||key!==neuralKey)return;neuralData=data;replayOffset=0;$('neuralSource').textContent=(data.synthetic?'SYNTHETIC OSCILLATORS · ':'RECORDED EEG · ')+data.provenance+' · '+data.pipeline;drawEEG();renderNeuralFeatures();}catch(e){if(token===epoch){neuralData=null;$('neuralSource').textContent=e.message;neuralKey='';drawEEG()}}}
function drawEEG(){const c=$('eeg'),g=c.getContext('2d');g.fillStyle='#0d1824';g.fillRect(0,0,c.width,c.height);if(!neuralData){g.fillStyle='#829bad';g.fillText('No recorded EEG available',30,50);return}const d=neuralData,width=c.width-100,height=c.height/d.channels.length,samples=d.signal_uv[0].length,view=Math.min(samples,Math.round(d.sampling_hz*4));const scale=height/100;for(let ch=0;ch<d.channels.length;ch++){const cy=(ch+.5)*height;g.strokeStyle='#1b3444';g.beginPath();g.moveTo(80,cy);g.lineTo(c.width-20,cy);g.stroke();g.fillStyle='#9dbcca';g.font='13px system-ui';g.fillText(d.channels[ch],15,cy+4);g.strokeStyle=['#7dbbca','#a7c4b1','#9baed2','#d3b28b'][ch%4];g.lineWidth=1.3;g.beginPath();for(let i=0;i<view;i++){const index=(Math.floor(replayOffset)+i)%samples,x=80+i/(view-1)*width,y=cy-d.signal_uv[ch][index]*scale;i&&index!==0?g.lineTo(x,y):g.moveTo(x,y)}g.stroke()}$('replayStatus').textContent=(replaying?'Looped recorded replay — not live':'Paused recorded segment')+' · '+number(samples/d.sampling_hz)+' s · '+number(d.sampling_hz)+' display Hz · '+d.channels.length+' channels · 100 µV per channel lane';}
$('neuralSelect').onchange=()=>{neuralKey='';loadNeural()};$('replay').onclick=()=>{if(!neuralData)return;if(replaying){stopReplay();drawEEG();return}replaying=true;$('replay').textContent='Pause replay';replayTimer=setInterval(()=>{if(document.hidden)return;replayOffset=(replayOffset+neuralData.sampling_hz/10)%neuralData.signal_uv[0].length;drawEEG()},100)};
function renderNeuralFeatures(){const d=neuralData,f=d.features,bands=[['delta',f.delta_power],['theta',f.theta_power],['alpha',f.alpha_power],['beta',f.beta_power]],total=bands.reduce((s,b)=>s+b[1],0);$('bands').replaceChildren();bands.forEach(([name,value],i)=>{const height=total?value/total*155:0,x=45+i*115;$('bands').append(svg('rect',{x,y:185-height,width:60,height,rx:4,fill:['#96b6ca','#7fa7bf','#3c7e9b','#9ab4ac'][i]}),svg('text',{x:x+30,y:205,'text-anchor':'middle'},name),svg('text',{x:x+30,y:175-height,'text-anchor':'middle'},number(value)+' µV²'))});$('neuralMetrics').replaceChildren(el('p','Candidate peak alpha: '+number(f.peak_alpha_frequency)+' Hz'),el('p','Normalized spectral entropy: '+number(f.spectral_entropy)));$('neuralQuality').replaceChildren(el('p','Quality: '+human(d.quality)+' · '+d.usable_windows+'/'+d.total_windows+' usable analysis windows. '+(d.quality_flags||[]).map(human).join('; ')),el('p','Features are supplied by the versioned processing pipeline. The displayed segment may cover only one usable window. No ERP is inferred without event markers.'));
if(d.spectrum){const g=$('spectrum');g.replaceChildren();const max=Math.max(...d.spectrum.density_uv2_hz)||1,points=d.spectrum.frequencies.map((f,i)=>(60+f/30*900)+','+(220-d.spectrum.density_uv2_hz[i]/max*180));g.append(svg('polyline',{points:points.join(' '),fill:'none',stroke:'#3d7c99','stroke-width':2}),svg('text',{x:60,y:250},'0.5 Hz'),svg('text',{x:920,y:250},'30 Hz'),svg('text',{x:60,y:22},'Power spectral density · µV²/Hz'))}else empty('spectrum','PSD not supplied.');
$('connectivity').replaceChildren();const cov=d.covariance_uv2;if(cov){const table=el('table'),head=el('tr');head.append(el('th',''));for(const c of d.channels)head.append(el('th',c));table.append(head);cov.forEach((values,i)=>{const r=el('tr');r.append(el('th',d.channels[i]));values.forEach((v,j)=>{const denominator=Math.sqrt(cov[i][i]*cov[j][j]),correlation=denominator?v/denominator:null;r.append(el('td',number(correlation)))});table.append(r)});$('connectivity').append(table)}else empty('connectivity','Covariance not supplied; no connections are invented.');}
function renderForecast(f){$('scenarioResult').textContent='';$('forecastState').textContent=f.value==null?'OBSERVATIONAL RESEARCH · NOT A FORECAST':human(f.state);$('forecastValue').textContent=f.value==null?'Recorded observations':number(f.value*100)+'%';$('forecastTarget').textContent=f.target+' · '+(f.horizon_months||24)+' months';$('forecastInterval').textContent=f.interval?number(f.interval[0]*100)+'%–'+number(f.interval[1]*100)+'% · '+f.interval_type:'No supported probability or uncertainty interval.';$('forecastEvidence').replaceChildren();if(f.external_evaluation){$('forecastEvidence').append(el('p','External evaluation: '+f.external_evaluation.n+' participants · AUROC '+number(f.external_evaluation.roc_auc)+' · Brier '+number(f.external_evaluation.brier)),el('p','Baseline: '+date(f.baseline_date)))}for(const text of [f.model_version?'Model: '+f.model_version:'No reviewed model is available.',...(f.reasons||[]).map(human)])$('forecastEvidence').append(el('p',text));$('forecastDisclaimer').textContent=f.interpretation||f.reason||'No supported forecast.';$('scenarioDemo').hidden=!synthetic();$('scenarioActive').hidden=synthetic()||f.state==='REVIEWED_RESEARCH_ESTIMATE';$('scenarioReal').hidden=synthetic()||f.state!=='REVIEWED_RESEARCH_ESTIMATE';$('realScenarioResult').textContent='';if(f.features){$('realMMSE').value=f.features.baseline_mmse;$('realAge').value=f.features.age;$('realEducation').value=f.features.education_years;}$('programmes').replaceChildren();for(const values of [['Longitudinal cognition','ADNI / OASIS','Historical trajectories implemented; mixed-effects modelling needs a specified cohort analysis'],['24-month MCI progression','Authorized linked clinical follow-up','Fixed-horizon logistic candidate trainer, censoring exclusions, held-out and optional external evaluation; no private model trained here'],['Structural change','Matched MRI visits','Source-native history and supplied FreeSurfer measurements; no new longitudinal registration'],['Parkinsonian movement','PADS','Separate movement-research evaluation, not prognosis'],['EEG characteristics','OpenNeuro / linked EEG','Signal features and covariance; no universal disease classifier'],['Multimodal progression','Genuinely linked participants','Not trained from unrelated cohort fusion']])$('programmes').append(row(values));}
for(const name of ['Score','Sleep'])$('scenario'+name).oninput=()=>$('scenario'+name+'Value').textContent=$('scenario'+name).value;$('runScenario').onclick=async()=>{try{const f=await api('demo-scenario?'+new URLSearchParams({profile,score:$('scenarioScore').value,sleep:$('scenarioSleep').value}),'POST');$('scenarioResult').textContent='Synthetic baseline: '+number(current.forecast.value*100)+'%; hypothetical simulator query: '+number(f.value*100)+'%. Invented coefficients; no disease probability or causal interpretation. Observed records were not changed.'}catch(e){$('scenarioResult').textContent=e.message}};
$('runRealScenario').onclick=async()=>{try{const f=await api(base()+'/scenario?mode='+mode,'POST',{baseline_mmse:Number($('realMMSE').value),age:Number($('realAge').value),education_years:Number($('realEducation').value)});$('realScenarioResult').textContent=f.value==null?'Query rejected: '+f.reasons.map(human).join('; '):'Hypothetical research estimate: '+number(f.value*100)+'%. This is an association-based model query, not an intervention effect. Source records were not changed.'}catch(e){$('realScenarioResult').textContent=e.message}};
function renderGovernance(){const d=current;renderCareLoopMarkers(d);$('coreStatus').replaceChildren(el('p','Status: '+human(d.governance.status)+' · training: '+human(d.governance.training)+' · deployment: '+human(d.governance.deployment)));$('coreCapabilities').replaceChildren();for(const c of d.governance.capabilities)$('coreCapabilities').append(row(c));$('updates').replaceChildren();for(const u of d.governance.updates)$('updates').append(el('p',date(u.recorded_at)+' · source revision '+u.revision.slice(0,16)));if(!d.governance.updates.length)empty('updates',synthetic()?'Synthetic snapshots are not stored in participant audit history.':'No prior source revisions.');$('functions').replaceChildren();for(const f of d.functions){const c=el('div',undefined,'function');c.append(el('b',f.id+' · '+f.name),el('p',human(f.state)),el('p',f.detail));$('functions').append(c)}$('roadmap').replaceChildren();for(const r of d.roadmap)$('roadmap').append(row(r));$('evidence').replaceChildren();for(const text of ['Engine: '+d.version,'Snapshot SHA-256: '+d.revision,d.read_consistency,...d.guard.notes,...d.issues])$('evidence').append(el('p',text));$('links').replaceChildren();for(const link of d.links){const c=el('div',undefined,'link');c.append(el('b',link.cohort+' / '+link.subject),el('p','Verified '+date(link.verified_at)+' · '+link.note));const b=el('button','Remove link','secondary');b.onclick=async()=>{if(!confirm('Remove this identity link? Source MRI packages remain unchanged.'))return;try{await api(base()+'/imaging-links?'+new URLSearchParams({mode,cohort:link.cohort,subject:link.subject}),'DELETE');await refresh(true)}catch(e){$('linkStatus').textContent=e.message}};c.append(b);$('links').append(c)}$('linkForm').hidden=synthetic();}
$('loadOptions').onclick=async()=>{try{const d=await api(base()+'/imaging-options?mode='+mode);options=d.items;$('linkScan').replaceChildren();for(const s of options){const o=el('option',s.cohort+' / '+s.subject+' / '+s.visit);o.value=s.id;$('linkScan').append(o)}$('linkStatus').textContent=options.length?'Verify the same person and source identity independently.':'No prepared imaging in this mode.'}catch(e){$('linkStatus').textContent=e.message}};
$('saveLink').onclick=async()=>{try{const scan=options.find(s=>s.id===$('linkScan').value);if(!scan||!$('verifyIdentity').checked||$('linkNote').value.trim().length<15)throw Error('Select an identity, record the verification reference and confirm the same person.');await api(base()+'/imaging-links?mode='+mode,'POST',{scan_id:scan.id,expected_sha256:scan.package_sha256,identity_verified:true,note:$('linkNote').value.trim()});$('verifyIdentity').checked=false;$('linkNote').value='';$('linkStatus').textContent='Verified identity saved.';await refresh(true)}catch(e){$('linkStatus').textContent=e.message}};
async function refresh(force=false){if(busy){pending=force;return}if(document.hidden&&!force)return;busy=true;const token=epoch;try{if(!['active','demo'].includes(mode)||(!synthetic()&&!person))throw Error('Open NeuroTwin X from a selected participant, or use a synthetic demo profile.');const d=await api(synthetic()?'demo-example?profile='+profile:base()+'?mode='+mode);if(token!==epoch)return;if(d.revision!==lastRevision||force){updateBrainOptions();render(d);lastRevision=d.revision}$('updated').textContent='Checked '+new Date().toLocaleTimeString();$('status').textContent=synthetic()?'Synthetic coherent profile · no participant records modified.':'Source refresh every 10 seconds while visible. Device acquisition and model training are separate.'}catch(e){if(token===epoch){$('status').textContent=e.message;$('updated').textContent='Refresh failed · displayed records may be stale';}}finally{busy=false;if(pending||token!==epoch){pending=false;refresh(true)}}}
$('refresh').onclick=()=>refresh(true);$('export').onclick=()=>{if(!current)return;const url=URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download='neurotwin-'+(synthetic()?'synthetic-'+profile:mode)+'-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});const initialBBCView = q.get('view');
if (['anatomical','neural','governance'].includes(initialBBCView)) {
  document.querySelector('[data-tab='+initialBBCView+']')?.click();
}
refresh();setInterval(()=>refresh(),10000);

function linkNeuroEvidence() {
  const destination = document.getElementById('neuroEvidenceLink');
  if (!destination) return;
  const params = new URLSearchParams({mode:'demo'});
  if (person && !synthetic()) {
    params.set('mode', mode);
    params.set('person', person);
  }
  destination.href = '/neurograph?' + params;
}
document.getElementById('profile')?.addEventListener('change', linkNeuroEvidence);
linkNeuroEvidence();

function renderCareLoopMarkers(data) {
  const list = document.getElementById('careloopMarkers');
  const link = document.getElementById('openCareLoop');
  if (!list || !link) return;
  const query = synthetic() ? new URLSearchParams({mode:'demo'}) : new URLSearchParams({mode,person});
  link.href = '/careloop?' + query;
  const markers = data.careloop_markers || [];
  const labels = {confirm_followup:'Outside follow-up completion recorded',record_outcome:'Outside outcome recorded'};
  list.replaceChildren(...(markers.length ? markers.map(marker =>
    el('li',labels[marker.action]+' · '+date(marker.at))) : [el('li','No shared follow-up markers.')]));
}

;/* BAINP_NEUROTWIN_PULSE_LINK_EMBEDDED_V11 */
'use strict';
/* BAINP NeuroTwin <-> NeuroPulse research explorer. Read-only, no participant linkage. */
(() => {
  const mode = new URLSearchParams(location.search).get('mode');
  const person = new URLSearchParams(location.search).get('person');
  const neural = document.getElementById('neural');
  const predictive = document.getElementById('predictive');
  if (!neural || !predictive) return;
  const make = (tag, text, className) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = String(text);
    if (className) n.className = className;
    return n;
  };
  const el = id => document.getElementById(id);
  const numeric = x => (typeof x === 'number' && Number.isFinite(x)) ? x.toLocaleString(undefined,{maximumFractionDigits:3}) : 'Not available';
  const researchAPI = '/api/neuropulse/intelligence/v3';
  let key = '', cohort = null, chosen = '', seq = 0;

  // The original Neural Twin is the participant-linked panel and remains untouched.
  // The extra section below is for unrelated research cohorts, never patient data.
  const research = make('section', undefined, 'nt-link-section');
  research.id = 'ntPulseResearch';
  research.innerHTML = `
    <div class="nt-link-heading"><div><p class="nt-link-eyebrow">NEUROPULSE X · INDEPENDENT EEG RESEARCH</p>
    <h2>Research EEG Explorer</h2><p>Actual source-linked OpenNeuro recordings, viewed separately from the selected BAINP participant. Research recordings are <strong>not</strong> automatically Neural Twin measurements.</p></div>
    <a href="/neuropulse?mode=active" class="nt-link-nav">Open NeuroPulse</a></div>
    <form id="ntPulseForm" class="nt-link-controls" autocomplete="off">
      <label for="ntPulseKey">Authorized research key</label>
      <input id="ntPulseKey" type="password" autocomplete="off" placeholder="Enter local NeuroPulse research key" aria-describedby="ntPulseKeyInfo" required>
      <button type="submit">Load research cohort</button>
      <p class="nt-link-help" id="ntPulseKeyInfo">Requires your signed-in NeuroAccess session and existing NeuroPulse research authorization. Key stays in memory only; no account privileges are changed.</p>
    </form>
    <p id="ntPulseStatus" class="nt-link-status" role="status" aria-live="polite">Research data has not been loaded.</p>
    <div id="ntPulseResults" hidden>
      <div id="ntPulseSummary" class="nt-link-summary"></div>
      <div class="nt-link-controls"><label for="ntPulseSubject">Research subject</label><select id="ntPulseSubject"></select>
      <label for="ntPulseStart">Start (seconds)</label><input id="ntPulseStart" type="number" min="0" max="3600" value="0" step="5">
      <button type="button" id="ntPulseView">Inspect recording</button></div>
      <p id="ntPulseDetailStatus" class="nt-link-status" role="status" aria-live="polite"></p>
      <div id="ntPulseDetail" hidden>
        <div id="ntPulseInfo" class="nt-link-summary"></div>
        <h3>Recorded EEG segment · channel traces</h3>
        <canvas id="ntPulseWave" width="1100" height="340" role="img" aria-label="Recorded EEG channels and time axes"></canvas>
        <p class="nt-link-help" id="ntPulseWaveNote">Raw, read-only segment; channel amplitudes scaled for display, not corrected or classified.</p>
        <h3>Power spectral density · Welch research estimate</h3>
        <svg id="ntPulsePSD" viewBox="0 0 1100 270" role="img" aria-label="EEG PSD, source-derived"></svg>
        <p class="nt-link-help" id="ntPulsePSDNote">No calculated PSD loaded.</p>
        <h3>Quality, provenance and review evidence</h3><div id="ntPulseEvidence" class="nt-link-evidence"></div>
        <details><summary>Review excluded intervals and processing annotations</summary><div id="ntPulseEvents"></div></details>
        <p class="nt-link-warning">NeuroGuard/QC review is required. No diagnostic claims, predictive seizure labels, or participant identity association are made.</p>
      </div>
      <p class="nt-link-help">If waveform access is unavailable, the cohort summaries can still load. The full raw recording must be present locally and authorized.</p>
    </div>`;
  /* BAINP_NEUROTWIN_NATIVE_EEG_V3_START */
  // A single Neural Twin workspace: one view of research records, another of
  // *verified participant-linked* records. Never populate participant sources
  // from a cohort whose identity association has not been verified.
  const participantEEG = neural.firstElementChild;
  if (!participantEEG || participantEEG.querySelector('#eeg') === null) {
    throw new Error('Expected original participant Neural Twin panel is missing');
  }
  const modeSwitch = make('div', undefined, 'nt-eeg-mode-switch');
  modeSwitch.setAttribute('role', 'group');
  modeSwitch.setAttribute('aria-label', 'Neural Twin EEG data source');
  const researchModeButton = make('button', 'Research EEG · real recordings');
  const participantModeButton = make('button', 'Participant EEG · verified links');
  researchModeButton.type = participantModeButton.type = 'button';
  const context = make('p', 'Research EEG uses separate OpenNeuro participants. It does not belong to, or change, the current BAINP participant.', 'nt-eeg-context');
  const researchArea = make('div', undefined, 'nt-eeg-research-area');
  researchArea.append(research);
  const chooseSource = (selection) => {
    const isResearch = selection === 'research';
    researchArea.hidden = !isResearch;
    participantEEG.hidden = isResearch;
    researchModeButton.setAttribute('aria-pressed', String(isResearch));
    participantModeButton.setAttribute('aria-pressed', String(!isResearch));
    researchModeButton.classList.toggle('nt-eeg-current', isResearch);
    participantModeButton.classList.toggle('nt-eeg-current', !isResearch);
    context.textContent = isResearch
      ? 'Independent research EEG · actual recordings and quality evidence. Identity linkage to this BAINP participant is NOT verified.'
      : 'Participant EEG · only recordings explicitly linked to this BAINP participant. Independent research recordings are never substituted.';
  };
  researchModeButton.addEventListener('click', () => chooseSource('research'));
  participantModeButton.addEventListener('click', () => chooseSource('participant'));
  modeSwitch.append(researchModeButton, participantModeButton);
  neural.prepend(context);
  neural.prepend(modeSwitch);
  neural.append(researchArea);
  chooseSource('research');
  /* BAINP_NEUROTWIN_NATIVE_EEG_V3_END */
  // Scoped styles; no global design changes.
  const eegStyle = document.createElement('style');
  eegStyle.textContent = "\n/* BAINP_NEUROTWIN_NATIVE_EEG_V3_CSS */\n.nt-eeg-mode-switch{display:flex;flex-wrap:wrap;gap:.65rem;margin:.2rem 0 1rem}\n.nt-eeg-mode-switch button{border:1px solid #8cbfc3;border-radius:.7rem;background:#f1faf9;color:#14545c;font:inherit;font-weight:650;padding:.75rem 1rem;cursor:pointer}\n.nt-eeg-mode-switch button.nt-eeg-current{background:#096f78;color:white;border-color:#096f78}\n.nt-eeg-mode-switch button:focus-visible{outline:3px solid #ffbc45;outline-offset:2px}\n.nt-eeg-context{margin:.4rem 0 1rem;padding:.85rem 1rem;background:#eaf5f4;border-left:3px solid #137b86;color:#244956}\n.nt-eeg-research-area[hidden],#neural>section[hidden]{display:none!important}\n.nt-eeg-research-area .nt-link-section{margin:0}\n";
  document.head.append(eegStyle);

  // Research entry point on the original Twin overview, without changing source counts.
  const sourcebar = el('sources');
  if (sourcebar) {
    const callout = make('div',undefined,'nt-link-callout');
    const title = make('span','EEG research cohort is separate from your participant-linked Neural Twin.');
    const b = make('button','Explore research EEG'); b.type='button';
    b.addEventListener('click',()=>{document.querySelector('[data-tab="neural"]')?.click();research.scrollIntoView({behavior:'smooth',block:'start'});});
    callout.append(title,b);sourcebar.insertAdjacentElement('afterend',callout);
  }
  const status = el('ntPulseStatus');
  function humanError(http, detail) {
    if (http === 401) return 'Sign into NeuroAccess, then reload the research cohort (HTTP 401).';
    if (http === 403) return 'Research authorization rejected (HTTP 403). Check your authorized research key and operator access; do not disable permissions.';
    if (http === 503) return 'NeuroPulse service or research run is not configured (HTTP 503). Check source paths, API status and service logs.';
    return `Research API HTTP ${http}: ${typeof detail === 'string' ? detail : 'Unavailable'}`;
  }
  async function call(path) {
    const r=await fetch(researchAPI+path,{method:'GET',cache:'no-store',credentials:'same-origin',headers:{'X-BAINP-Research-Key':key,'X-NeuroAccess-Request':'1'}});
    let data;
    try { data=await r.json(); } catch { throw Error(`NeuroPulse returned a non-JSON response (HTTP ${r.status}).`); }
    if (!r.ok) throw Error(humanError(r.status,data?.detail));
    return data;
  }
  el('ntPulseForm').addEventListener('submit',async ev=>{
    ev.preventDefault();
    const candidate=el('ntPulseKey').value.trim();
    el('ntPulseKey').value='';
    if (!/^[A-Fa-f0-9]{64}$/.test(candidate)) {status.textContent='Enter your actual authorized 64-character hexadecimal NeuroPulse research key.';return;}
    key=candidate; status.textContent='Loading the live research index…';
    el('ntPulseResults').hidden=true;el('ntPulseDetail').hidden=true;
    try {
      const data=await call('/overview');
      if (!Array.isArray(data.subject_records)) throw Error('API did not provide a subject index.');
      cohort=data;const records=data.subject_records;
      el('ntPulseSubject').replaceChildren();
      for(const r of records){
        const opt=make('option',`${r.subject} · ${r.status} · ${r.windows_retained}/${r.windows_total} windows`);
        opt.value=r.subject;el('ntPulseSubject').append(opt);
      }
      el('ntPulseSummary').replaceChildren();
      for(const [name,count] of [['Recordings',data.total],['Descriptive available',data.counts?.DESCRIPTIVE_AVAILABLE],['Insufficient windows',data.counts?.INSUFFICIENT_WINDOWS],['Failed',data.counts?.FAILED]]){
        const metric=make('div',undefined,'nt-link-metric');metric.append(make('strong',numeric(count)),make('span',name));el('ntPulseSummary').append(metric);
      }
      const note=make('p',`Source run: ${data.source_run||'Not reported'} · Research only · No verified link to this BAINP participant.`);
      note.className='nt-link-help';el('ntPulseSummary').append(note);
      el('ntPulseResults').hidden=false;
      status.textContent=`Loaded ${data.total} real research recording summaries. These do not alter personal Neural Twin data.`;
      if(records.length) await show(records[0].subject);
    } catch(e) { key='';cohort=null;status.textContent=e.message; }
  });
  el('ntPulseView').addEventListener('click',()=>show(el('ntPulseSubject').value));
  el('ntPulseSubject').addEventListener('change',()=>show(el('ntPulseSubject').value));

  function drawWave(d){
    const c=el('ntPulseWave'),g=c.getContext('2d');g.clearRect(0,0,c.width,c.height);
    g.fillStyle='#091b29';g.fillRect(0,0,c.width,c.height);
    const signals=d.signals_uv,t=d.time_s;
    if(!Array.isArray(signals)||!signals.length||!Array.isArray(t)||t.length<2){throw Error('Waveform schema unavailable');}
    const left=92,right=c.width-20,plotW=right-left,laneH=(c.height-16)/signals.length;
    const all=signals.flat().filter(Number.isFinite);const peak=Math.max(10,...all.map(Math.abs));const gain=(laneH*.37)/peak;
    for(let k=0;k<signals.length;k++){
      const laneY=8+laneH*(k+.5),signal=signals[k];
      g.strokeStyle='#31556a';g.beginPath();g.moveTo(left,laneY);g.lineTo(right,laneY);g.stroke();
      g.font='15px system-ui';g.fillStyle='#d1e7f2';g.fillText(String(d.channels?.[k]||'EEG '+(k+1)).slice(0,12),8,laneY+4);
      g.strokeStyle=['#66dbcf','#a4b2ef','#f8cc90','#90d1ac'][k%4];g.lineWidth=1.3;g.beginPath();
      const n=Math.min(signal.length,t.length);for(let i=0;i<n;i++){
        const x=left+(t[i]-t[0])/(t[n-1]-t[0]||1)*plotW,y=laneY-(Number(signal[i])||0)*gain;
        if(i===0)g.moveTo(x,y);else g.lineTo(x,y);
      }g.stroke();
    }
    el('ntPulseWaveNote').textContent=`Recorded ${numeric(t[0])}–${numeric(t[t.length-1])} s · ${signals.length} channels · sampling ${numeric(d.sampling_hz)} Hz · display-only downsampling · display gain ±${numeric(peak)} µV (shared channels). No filtering or artifact correction applied.`;
  }
  function drawPSD(d){
    const root=el('ntPulsePSD');root.replaceChildren();
    const svg=(tag,attrs,text)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs||{}))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=String(text);return n;};
    const f=d.frequency_hz,psds=d.psd_uv2_per_hz;
    if(!Array.isArray(f)||f.length<2||!Array.isArray(psds)||!psds.length) throw Error('PSD schema unavailable');
    const valid=psds.flat().filter(x=>typeof x==='number'&&Number.isFinite(x)&&x>=0);
    const ymax=Math.max(.0001,...valid),xmin=f[0],xmax=f[f.length-1],left=76,right=1060,top=24,bottom=225;
    root.append(svg('line',{x1:left,y1:bottom,x2:right,y2:bottom,stroke:'#b1c4cf'}),svg('text',{x:80,y:16,fill:'#264b60'},'Welch PSD · µV²/Hz'),svg('text',{x:right-120,y:255,fill:'#42657a'},'Frequency (Hz)'));
    for (let k=0;k<psds.length;k++){
      const v=psds[k],points=f.map((x,i)=>{
        const yy=Math.max(0,Number(v[i])||0);return `${left+(x-xmin)/(xmax-xmin||1)*(right-left)},${bottom-yy/ymax*(bottom-top)}`;
      }).join(' ');
      root.append(svg('polyline',{points,fill:'none',stroke:['#008d80','#6074bc','#c18a42','#398ba9'][k%4],'stroke-width':'2'}));
    }
    el('ntPulsePSDNote').textContent=`Actual ${psds.length} channels · ${d.method||'Welch'} · frequencies ${numeric(xmin)}–${numeric(xmax)} Hz · exploratory and requires quality review. This PSD is not a validated disease biomarker.`;
  }
  function kv(root,key,value){const div=make('div',undefined,'nt-link-kv');div.append(make('span',key),make('strong',value));root.append(div);}
  async function show(subject){
    if(!key||!cohort)return;
    if(!/^sub-\d{3}$/.test(subject)) return;
    chosen=subject;const my=++seq;const target=el('ntPulseDetailStatus');target.textContent=`Loading ${subject} source and quality evidence…`;
    el('ntPulseDetail').hidden=false;
    const info=el('ntPulseInfo'),ev=el('ntPulseEvidence'),events=el('ntPulseEvents');
    info.replaceChildren();ev.replaceChildren();events.replaceChildren();
    const wctx=el('ntPulseWave').getContext('2d');wctx.fillStyle='#091b29';wctx.fillRect(0,0,1100,340);
    el('ntPulsePSD').replaceChildren();el('ntPulseWaveNote').textContent='Loading waveform…';el('ntPulsePSDNote').textContent='Loading PSD…';
    const start=Math.max(0,Number(el('ntPulseStart').value)||0);
    const queries=[
      ['/subjects/'+subject, 'metadata'],
      ['/subjects/'+subject+'/evidence','evidence'],
      ['/subjects/'+subject+'/waveform?'+new URLSearchParams({start_s:String(start),duration_s:'5',channels:'4',max_points:'900'}),'waveform'],
      ['/subjects/'+subject+'/spectrum?'+new URLSearchParams({start_s:String(start),duration_s:'10',channels:'4'}),'spectrum'],
      ['/subjects/'+subject+'/events','events'],
    ];
    const responses=await Promise.all(queries.map(async([path,type])=>{try{return {type,data:await call(path)};}catch(e){return {type,error:e.message};}}));
    if(my!==seq)return;
    const found=Object.fromEntries(responses.map(r=>[r.type,r]));
    const m=found.metadata?.data;const e=found.evidence?.data;
    kv(info,'Research subject',subject);
    if(m){kv(info,'Processing status',m.row?.status||'Unavailable');kv(info,'Channels',numeric(m.channels?.length));kv(info,'Duration',numeric(m.duration_s)+' s');kv(info,'Retained windows',`${numeric(m.row?.windows_retained)}/${numeric(m.row?.windows_total)}`);}
    else kv(info,'Metadata',found.metadata?.error||'Unavailable');
    if(e){
      kv(ev,'Source SHA-256',e.source_sha256||'Not recorded');kv(ev,'Research evidence digest',e.evidence_sha256||'Not provided');
      kv(ev,'Processing version',e.processing_schema||'Not supplied');kv(ev,'Review status',e.quality||'REVIEW_REQUIRED');
      kv(ev,'NeuroGuard',String(e.neuroguard?.state||'unavailable'));
      kv(ev,'Clinical release',e.clinical_release===true?'Reported by source':'Not authorized');
      kv(ev,'Participant linkage','UNVERIFIED · never inferred');
      const cautions=make('p',(e.limitations||[]).slice(0,4).join(' · '),'nt-link-help');ev.append(cautions);
    } else kv(ev,'Evidence',found.evidence?.error||'Unavailable');
    if(found.waveform.data){try{drawWave(found.waveform.data)}catch(x){el('ntPulseWaveNote').textContent=x.message;}}
    else el('ntPulseWaveNote').textContent=found.waveform.error||'Waveform not available.';
    if(found.spectrum.data){try{drawPSD(found.spectrum.data)}catch(x){el('ntPulsePSDNote').textContent=x.message;}}
    else el('ntPulsePSDNote').textContent=found.spectrum.error||'PSD not available.';
    const ann=found.events?.data?.annotations;
    if(Array.isArray(ann)&&ann.length){const list=make('ul');for(const item of ann.slice(0,60))list.append(make('li',JSON.stringify(item)));events.append(list);}else events.append(make('p',found.events.error||'No processing exclusion intervals reported. No seizure detection performed.'));
    target.textContent=`${subject} · source-linked research only · reviewed participant linkage absent`;
  }

  // Predictive Twin remains model-gated. Show historical, actually recorded data
  // without inventing future disease probabilities or extrapolating EEG cohorts.
  const history=make('section',undefined,'nt-link-section');history.id='ntObservedHistory';
  history.innerHTML=`<div class="nt-link-heading"><div><p class="nt-link-eyebrow">OBSERVED DATA · NOT A FORECAST</p><h2>What the longitudinal record actually shows</h2><p>Recorded assessment measurements and quality eligibility. Descriptive change is not an estimated risk of disease, a causal treatment effect or a future trajectory.</p></div><button id="ntHistoryRefresh" type="button">Refresh observations</button></div>
    <p id="ntHistoryStatus" class="nt-link-status" role="status">Open this panel to load available participant records.</p>
    <div id="ntHistoryResults" hidden><div id="ntHistorySummary" class="nt-link-summary"></div>
      <label for="ntHistoryMetric">Observed assessment series</label><select id="ntHistoryMetric"></select>
      <svg id="ntHistoryChart" viewBox="0 0 1000 260" role="img" aria-label="Recorded assessment values over time"></svg>
      <div id="ntHistoryTable" class="nt-link-observations"></div><p class="nt-link-warning">Future disease probability: not calculated without a reviewed, applicable model. EEG data from unrelated research subjects are not predictors for this participant.</p></div>`;
  predictive.append(history);
  const hStatus=el('ntHistoryStatus');let last=null;
  async function loadHistory(){
    if(mode!=='active'||!person){hStatus.textContent='Select an active, authorized participant to view actual recorded history. This section does not use fictional profiles.';return;}
    if(!/^[a-f0-9-]{36}$/i.test(person)){hStatus.textContent='Invalid participant identifier; no data loaded.';return;}
    hStatus.textContent='Loading participant-specific recorded history…';
    try{
      const r=await fetch('/api/neurotwin/participants/'+encodeURIComponent(person)+'?mode=active',{credentials:'same-origin',cache:'no-store',headers:{'X-NeuroAccess-Request':'1'}});
      const data=await r.json();if(!r.ok)throw Error(humanError(r.status,data.detail));last=data;
      const series=(data.series||[]).filter(s=>s.source==='NeuroCognition X'&&Array.isArray(s.points)&&s.points.some(p=>p.eligible!==false&&Number.isFinite(p.value)&&Number.isFinite(Date.parse(p.at))));
      const select=el('ntHistoryMetric');select.replaceChildren();
      for(const [index,s] of series.entries()){const option=make('option',s.id||s.metric||'Assessment '+(index+1));option.value=String(index);select.append(option);}
      el('ntHistoryResults').hidden=false;
      const summary=el('ntHistorySummary');summary.replaceChildren();
      const clinical=make('div',undefined,'nt-link-metric');clinical.append(make('strong',numeric(data.states?.['NeuroCognition X']?.count)),make('span','Cognitive sessions'));summary.append(clinical);
      const usable=make('div',undefined,'nt-link-metric');usable.append(make('strong',String(series.length)),make('span','Recorded assessment series'));summary.append(usable);
      const forecast=make('div',undefined,'nt-link-metric');forecast.append(make('strong',data.forecast?.state==='REVIEWED_RESEARCH_ESTIMATE'?'Reviewed model response':'Not available'),make('span','Future risk estimate'));summary.append(forecast);
      if(series.length){select.onchange=()=>drawHistory(series[Number(select.value)]);drawHistory(series[0]);hStatus.textContent='Showing available historical assessments from the original NeuroTwin source.';}
      else {el('ntHistoryChart').replaceChildren();el('ntHistoryTable').replaceChildren(make('p','No eligible recorded assessment values are available for a trajectory.'));hStatus.textContent='Participant context loaded. Historical series are currently insufficient.';}
    }catch(e){hStatus.textContent=e.message;el('ntHistoryResults').hidden=true;}
  }
  function drawHistory(s){
    if(!s)return;const all=(s.points||[]).filter(p=>p.eligible!==false&&Number.isFinite(p.value)&&Number.isFinite(Date.parse(p.at))).sort((a,b)=>Date.parse(a.at)-Date.parse(b.at));
    const chart=el('ntHistoryChart'),table=el('ntHistoryTable');chart.replaceChildren();table.replaceChildren();
    const svg=(tag,a,t)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(a||{}))n.setAttribute(k,String(v));if(t!==undefined)n.textContent=String(t);return n;};
    if(!all.length){table.append(make('p','No eligible observations.'));return;}
    const vals=all.map(p=>p.value),times=all.map(p=>Date.parse(p.at));
    let lo=Math.min(...vals),hi=Math.max(...vals),t0=Math.min(...times),t1=Math.max(...times);
    const pad=Math.max(0.01,(hi-lo)*.12);lo-=pad;hi+=pad;
    const x=t=>75+(t-t0)/(t1-t0||1)*885,y=v=>216-(v-lo)/(hi-lo)*173;
    for(let j=0;j<4;j++){const yy=216-j*50;chart.append(svg('line',{x1:75,y1:yy,x2:965,y2:yy,stroke:'#d3e1e5'}));}
    if(all.length>1)chart.append(svg('polyline',{points:all.map(p=>`${x(Date.parse(p.at))},${y(p.value)}`).join(' '),stroke:'#007c83','stroke-width':3,fill:'none'}));
    for(const p of all){const dot=svg('circle',{cx:x(Date.parse(p.at)),cy:y(p.value),r:5,fill:'#007c83'});dot.append(svg('title',{},`${p.at}: ${numeric(p.value)} ${s.unit||''}`));chart.append(dot);}
    chart.append(svg('text',{x:70,y:244,fill:'#395e69'},new Date(t0).toISOString().slice(0,10)),svg('text',{x:950,y:244,'text-anchor':'end',fill:'#395e69'},new Date(t1).toISOString().slice(0,10)));
    const days=(t1-t0)/86400000,delta=all.at(-1).value-all[0].value;
    table.append(make('p',`${all.length} eligible observations · ${numeric(days)} days of observed history · First ${numeric(all[0].value)} ${s.unit||''} → last ${numeric(all.at(-1).value)} ${s.unit||''} · observed change ${delta>=0?'+':''}${numeric(delta)} ${s.unit||''}.`));
    if(s.estimate?.state==='EXPLORATORY_DESCRIPTIVE_FIT'&&Number.isFinite(s.estimate.slope_per_30_days))table.append(make('p',`Source-reported descriptive slope: ${numeric(s.estimate.slope_per_30_days)} ${s.unit||''} per 30 days. ${s.estimate.caveat||'Exploratory only.'}`));
    else table.append(make('p','No supported fitted trend for this measurement.'));}
  el('ntHistoryRefresh').addEventListener('click',loadHistory);
  document.querySelector('[data-tab="predictive"]')?.addEventListener('click',loadHistory);
  if(!document.getElementById('predictive')?.hidden)loadHistory();
})();


/* BAINP_NEUROTWIN_EEG_OVERVIEW_STATUS_V1 */
/* BAINP NeuroTwin EEG status: display-only, no participant linkage. */
(() => {
  'use strict';
  const observerText = 'Loaded 88 real research recording summaries';
  let scheduled = false;
  function update() {
    scheduled = false;
    const cards = document.querySelectorAll('.twinCard');
    const card = [...cards].find(c => c.querySelector('h3')?.textContent.trim() === 'Neural Twin');
    if (!card) return;
    const metric = card.querySelector('strong');
    if (!metric) return;
    // Do not interfere if verified participant EEG exists.
    if (!/^Awaiting (?:participant )?EEG$/i.test(metric.textContent.trim())) return;
    if (metric.textContent !== 'Awaiting participant EEG') metric.textContent = 'Awaiting participant EEG';
    const available = document.body.textContent.includes(observerText);
    let note = card.querySelector('[data-bainp-research-eeg-status]');
    if (!note) {
      note = document.createElement('p');
      note.dataset.bainpResearchEegStatus = 'true';
      note.style.cssText = 'font-size:.84rem;line-height:1.5;color:#146773;margin:.4rem 0 0';
      const detail = metric.nextElementSibling;
      if (detail) detail.insertAdjacentElement('afterend', note);
      else metric.insertAdjacentElement('afterend', note);
    }
    const label = available
      ? 'Independent NeuroPulse research: 88 recordings loaded. Not linked to this participant.'
      : 'Independent research EEG can be explored in Neural Twin; no verified personal recording.';
    if (note.textContent !== label) note.textContent = label;
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(update);
  }
  const observer = new MutationObserver(schedule);
  const start = () => {
    observer.observe(document.body, {subtree:true, childList:true, characterData:true});
    schedule();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
