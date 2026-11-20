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
  neural.append(research);
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
