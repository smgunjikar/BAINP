'use strict';
const $ = id => document.getElementById(id);
const demo = new URLSearchParams(location.search).get('mode') === 'demo';
const bands = [['Delta','delta_relative'],['Theta','theta_relative'],['Alpha','alpha_relative'],['Beta','beta_relative']];
const flagNames = {
  AMPLITUDE_OVER_200_UV: 'High peak-to-peak amplitude',
  FLAT_CHANNEL_SD_UNDER_0_1_UV: 'Flat channel',
  BAD_ANNOTATION_OVERLAP: 'Source annotation overlaps window'
};
let catalog = [], recording, duration, position, scale, frame, previous, revision = 0;
let playing = false;
$('source').textContent = demo
  ? 'Synthetic lab · Generated signals for exploring rhythms and quality flags.'
  : 'Research replay · Prerecorded EEG excerpts displayed as waveforms. No audio track.';
document.querySelector(demo ? 'a[href$="mode=demo"]' : 'a[href$="mode=active"]').setAttribute('aria-current','page');
$('import').hidden = demo;
$('research').hidden = demo;

function node(tag, value) {
  const el = document.createElement(tag);
  el.textContent = value;
  return el;
}
function validate(data) {
  const gates = demo ? ['SIMULATION_ONLY'] : ['DESCRIPTIVE_RESEARCH_ONLY','INSUFFICIENT_EVIDENCE'];
  if (!gates.includes(data?.summary?.gate) ||
      (!demo && data.source !== 'PRERECORDED RESEARCH EEG REPLAY') ||
      !Array.isArray(data.names) || !data.names.length || data.names.length > 256 ||
      !data.names.every(n => typeof n === 'string') ||
      !Number.isFinite(data.sf) || data.sf < 1 || data.sf > 200 ||
      !Array.isArray(data.signal_uv) || data.signal_uv.length !== data.names.length ||
      !data.signal_uv.every(a => Array.isArray(a) && a.length > 0 && a.length <= 24000 &&
        a.length === data.signal_uv[0].length && a.every(Number.isFinite)) ||
      !Array.isArray(data.features) || !data.features.every(f => typeof f?.channel === 'string')) {
    throw new Error('Choose a compatible NeuroPulse replay JSON.');
  }
}
function draw() {
  $('clock').textContent = `${position.toFixed(1)} / ${duration.toFixed(1)} s`;
  $('seek').value = position;
  const g = $('wave').getContext('2d');
  if (!g) return;
  const {width:w,height:h} = $('wave');
  const data = recording.signal_uv[Number($('channel').value)];
  const span = Math.min(5,duration);
  const start = Math.max(0,Math.min(position-span, duration-span));
  const end = Math.min(data.length,Math.ceil((start+span)*recording.sf));
  g.clearRect(0,0,w,h);
  for (let i=0;i<=5;i++) {
    const x = Math.min(w-2, i*w/5);
    g.strokeStyle = '#294554';
    g.beginPath(); g.moveTo(x,0); g.lineTo(x,h); g.stroke();
    if (i<5) {
      g.fillStyle = '#b9cdd7'; g.font = '18px system-ui';
      g.fillText(`${(start+i*span/5).toFixed(1)} s`,x+5,h-8);
    }
  }
  g.strokeStyle = '#294554';
  g.beginPath(); g.moveTo(0,h/2); g.lineTo(w,h/2); g.stroke();
  g.strokeStyle = '#8bf0dd'; g.lineWidth = 2;
  g.beginPath();
  const first = Math.ceil(start*recording.sf);
  for(let i=first;i<end;i++) {
    const x = (i/recording.sf-start)*w/span;
    const y = h/2 - data[i]/scale*(h/2-26);
    if(i===first) g.moveTo(x,y); else g.lineTo(x,y);
  }
  g.stroke();
  const cursor = Math.min(w-2,(position-start)*w/span);
  g.strokeStyle = '#ffd789';
  g.beginPath(); g.moveTo(cursor,0); g.lineTo(cursor,h); g.stroke();
}
function setPlaying(value) {
  playing = value;
  $('play').textContent = value ? 'Pause replay' : 'Play replay';
  cancelAnimationFrame(frame);
  previous = undefined;
  if (value) frame = requestAnimationFrame(tick);
}
function tick(now) {
  if (!playing) return;
  const elapsed = previous === undefined ? 0 : Math.min(.25,(now-previous)/1000);
  previous = now;
  position = Math.min(duration, position + elapsed*Number($('speed').value));
  draw();
  if(position >= duration) setPlaying(false);
  else frame = requestAnimationFrame(tick);
}
function median(values) {
  values.sort((a,b)=>a-b);
  return values.length ? (values[Math.floor((values.length-1)/2)] + values[Math.floor(values.length/2)])/2 : null;
}
function channel() {
  const index = Number($('channel').value);
  const values = recording.signal_uv[index];
  scale = Math.max(10,Math.ceil(values.reduce((max,v)=>Math.max(max,Math.abs(v)),0)/10)*10);
  $('scale').textContent = `${recording.names[index]} · ±${scale} µV · Display rate ${recording.sf.toFixed(1)} Hz · Yellow line marks replay position.`;
  const features = recording.features.filter(f=>f.channel===recording.names[index]);
  $('features').replaceChildren();
  if (!features.length) $('features').append(node('p','No spectral observations are available for this channel.'));
  for (const [name,key] of [...bands,['Alpha peak candidate','alpha_peak_candidate_hz'],['Spectral entropy','normalized_spectral_entropy']]) {
    if (!features.length) break;
    const value = median(features.map(f=>f[key]).filter(Number.isFinite));
    const relative = key.endsWith('_relative');
    const label = value === null ? 'Unavailable' : relative ? `${(100*value).toFixed(1)}%` : `${value.toFixed(2)}${key.endsWith('_hz') ? ' Hz' : ''}`;
    const row = node('div','');
    row.className = 'metric';
    row.append(node('span',name),node('strong',label));
    if (relative && value !== null && value>=0 && value<=1) {
      const meter = node('meter',label); meter.min=0; meter.max=1; meter.value=value; meter.setAttribute('aria-label',name); row.append(meter);
    }
    $('features').append(row);
  }
  draw();
}
function evidence(local) {
  const s = recording.summary;
  const count = v => Number.isSafeInteger(v) && v>=0 ? String(v) : 'Unavailable';
  const heading = demo ? 'Synthetic quality exercise' : s.gate==='INSUFFICIENT_EVIDENCE' ? 'Insufficient usable signal' : 'Descriptive research excerpt';
  const q = $('quality');
  q.replaceChildren(node('strong',heading),node('p',`${count(s.accepted_windows)} accepted windows · ${count(s.review_windows)} flagged windows`),
    node('p',local ? 'Quality and provenance are reported by the selected file.' : 'Quality checks flag amplitude, flat channels and source annotations.'));
  if (Array.isArray(recording.quality)) {
    const flagged = recording.quality.filter(w=>Number.isFinite(w?.start_s)&&Number.isFinite(w.duration_s)&&Array.isArray(w.flags)&&w.flags.length);
    if (flagged.length) {
      const list = node('ul','');
      for (const w of flagged.slice(0,30)) {
        const row = node('li','');
        const jump = node('button',`${w.start_s.toFixed(1)}–${(w.start_s+w.duration_s).toFixed(1)} s · ${w.flags.map(f=>Object.hasOwn(flagNames,f)?flagNames[f]:'Other quality flag').join(', ')}`);
        jump.type = 'button';
        jump.onclick = () => {
          setPlaying(false);
          position = Math.max(0,Math.min(duration,w.start_s));
          draw();
          $('seek').focus();
        };
        row.append(jump);
        list.append(row);
      }
      q.append(list);
    }
  }
  const provenance = $('provenance');
  provenance.replaceChildren();
  const rows = [['Source',s.citation ?? (demo ? 'Deterministically generated for the synthetic lab' : s.recording)],
    ['Original sample rate',Number.isFinite(s.sample_hz)?`${s.sample_hz} Hz`:null],['Filter',s.filter],['Spectral method',s.psd],['Processing version',s.version]];
  for (const [name,value] of rows) if (typeof value === 'string') provenance.append(node('dt',name),node('dd',value));
  if (!demo) provenance.append(node('dt','Interpretation'),node('dd','Excerpt-level measurements are for research review. Clinical interpretation requires independent evidence.'));
}
function show(data,title,local=false) {
  validate(data);
  setPlaying(false);
  recording=data;
  duration=data.signal_uv[0].length/data.sf;
  position=0;
  $('seek').max=duration;
  $('title').textContent=title;
  $('channel').replaceChildren(...data.names.map((name,i)=>new Option(name,i)));
  $('viewer').hidden=false;
  evidence(local);
  channel();
  $('status').textContent=local?'Local replay ready. The file stays in this browser.':'Replay ready. Press Play or drag the timeline.';
}
$('play').onclick=()=>{
  if(!playing && position>=duration) position=0;
  setPlaying(!playing);
  draw();
};
$('reset').onclick=()=>{setPlaying(false); position=0; draw();};
$('seek').oninput=()=>{setPlaying(false);position=Number($('seek').value);draw();};
$('channel').onchange=channel;
$('recording').onchange=()=>{
  ++revision;
  $('file').value='';
  const entry=catalog[Number($('recording').value)];
  if (entry) show(entry.data,entry.title);
};
$('file').onchange=async ()=>{
  const file=$('file').files[0];
  if(!file) return;
  const current=++revision;
  setPlaying(false);
  $('status').textContent='Reading local replay…';
  try {
    if(file.size>32*1024*1024) throw new Error('Replay exceeds the 32 MiB limit.');
    const data=JSON.parse(await file.text());
    if(current!==revision) return;
    show(data,file.name,true);
    $('recording').selectedIndex=-1;
  } catch(error) {
    if(current===revision) $('status').textContent=`Could not open file. ${error.message}`;
  }
};
async function get(path) {
  const response=await fetch(path);
  if(!response.ok) throw new Error('The requested data could not load.');
  return response.json();
}
get(demo?'/neuropulse-demo.json':'/neuropulse-research-example.json').then(items=>{
  for(const item of items) validate(item.data);
  catalog=items;
  $('recording').replaceChildren(...items.map((item,i)=>new Option(item.title,i)));
  $('recording').disabled=false;
  if(revision===0) show(items[0].data,items[0].title);
  else $('recording').selectedIndex=-1;
}).catch(error=>{
  if(revision===0) $('status').textContent=`Recordings unavailable. ${error.message}`;
});
if (!demo) get('/neuropulse-benchmark.json').then(r=>{
  $('benchmark').textContent=`OpenNeuro ds004504 · ${r.included} of ${r.considered} participants met benchmark quality rules. Five-fold participant-level cross-validation yielded ${(100*r.spectral).toFixed(1)}% balanced accuracy for spectral logistic regression and ${(100*r.majority).toFixed(1)}% for the majority baseline. Internal cohort evaluation.`;
}).catch(error=>{$('benchmark').textContent=error.message;});
