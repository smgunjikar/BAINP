'use strict';
(() => {
  const root=document.getElementById('np-main-research');
  if(!root || new URLSearchParams(location.search).get('mode')==='demo') return;
  root.hidden=false;
  const keyInput=document.getElementById('np-research-key');
  const connect=document.getElementById('np-connect');
  const message=document.getElementById('np-research-status');
  const table=document.getElementById('np-research-table');
  const detail=document.getElementById('np-research-detail');
  const cohort=document.getElementById('np-cohort-data');
  const find=document.getElementById('np-subject-search');
  const filter=document.getElementById('np-status-filter');
  const endpoint='/api/neuropulse/intelligence/v3';
  let secret='',rows=[],chosen=null;
  const make=(tag,value,cls)=>{const el=document.createElement(tag);if(value!==undefined)el.textContent=String(value);if(cls)el.className=cls;return el;};
  const fmt=v=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(2):'Not available';
  const append=(parent,tag,text,cls)=>{const el=make(tag,text,cls);parent.append(el);return el;};
  async function get(path){
    const res=await fetch(endpoint+path,{credentials:'same-origin',cache:'no-store',headers:{'X-BAINP-Research-Key':secret}});
    if(!res.ok){let reason='';try{reason=(await res.json()).detail||'';}catch{}
      throw new Error(`API ${res.status}: ${reason||'Request failed'}. Check backend restart, sign-in and research key.`);}
    return await res.json();
  }
  const tabs=append(detail,'div',undefined,'np-intel-tabs');
  const panel=append(detail,'div',undefined,'np-intel-panel');
  const available=['Overview','Waveforms','Spectrum','Annotations','Evidence','ARENA','Processing','Connections'];
  let active='Overview';
  function draw(canvas,x,series,xlabel){
    const dpr=Math.min(2,window.devicePixelRatio||1),w=760,h=270;
    canvas.width=w*dpr;canvas.height=h*dpr;canvas.style.width='100%';canvas.style.height='270px';
    const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
    ctx.fillStyle='#0e2638';ctx.fillRect(0,0,w,h);
    ctx.strokeStyle='#31526a';ctx.lineWidth=1;
    for(let i=0;i<=5;i++){const y=25+i*42;ctx.beginPath();ctx.moveTo(46,y);ctx.lineTo(746,y);ctx.stroke();}
    const flat=series.flat().filter(Number.isFinite);
    if(!flat.length){ctx.fillStyle='#fff';ctx.fillText('No valid signal',80,80);return;}
    const max=Math.max(...flat),min=Math.min(...flat),spread=Math.max(1e-6,max-min);
    for(let i=0;i<series.length;i++){
      ctx.beginPath();ctx.strokeStyle=['#66e0d3','#e6bc65','#85aff9','#fa9b97','#c5a7f7','#cde986','#a3cde4','#edaaed'][i%8];ctx.lineWidth=1.25;
      for(let j=0;j<series[i].length;j++){
        const px=48+(j/Math.max(1,series[i].length-1))*695;
        const py=236-((series[i][j]-min)/spread)*194;
        if(j===0)ctx.moveTo(px,py);else ctx.lineTo(px,py);
      }ctx.stroke();
    }
    ctx.fillStyle='#d4eaf5';ctx.font='12px system-ui';ctx.fillText(xlabel,52,259);
    ctx.fillText(max.toFixed(2),4,31);ctx.fillText(min.toFixed(2),4,230);
  }
  function button(text,click){const b=make('button',text,'np-action');b.type='button';b.addEventListener('click',click);return b;}
  function field(label,type='number',value='0',step='1'){const wrap=make('label');append(wrap,'span',label);const input=make('input');input.type=type;input.value=value;input.step=step;wrap.append(input);return [wrap,input];}
  function setTabs(){tabs.replaceChildren();for(const name of available){const b=button(name,()=>{active=name;setTabs();render().catch(showError);});b.classList.toggle('active',name===active);tabs.append(b);}}
  function showError(error){panel.replaceChildren(append(make('div'), 'p',error.message,'np-error'));}
  function paragraph(v){append(panel,'p',v);}
  function pre(v){const el=append(panel,'pre',JSON.stringify(v,null,2));el.className='np-intel-json';}
  async function render(){panel.replaceChildren();if(!chosen){paragraph('Select a subject from the cohort table.');return;}
    const sub=chosen,subject=await get('/subjects/'+encodeURIComponent(sub));
    append(panel,'h3',sub+' · '+active);
    if(active==='Overview'){
      const r=subject.row;paragraph(`${r.status} · ${r.windows_retained}/${r.windows_total} windows retained · ${subject.sampling_hz} Hz`);
      const t=append(panel,'table');const h=append(t,'tr');['Band','Power (µV²)'].forEach(v=>append(h,'th',v));
      Object.entries(r.features).forEach(([name,value])=>{const tr=append(t,'tr');append(tr,'td',name);append(tr,'td',fmt(value));});
      paragraph('Quality: '+subject.quality_decision.state+' / '+subject.quality_decision.reason+' · No clinical release.');
      paragraph('EEG participant linkage to patient records is not verified.');
    }else if(active==='Waveforms'||active==='Spectrum'){
      paragraph('Research inspection of raw source segment. These curves are NOT the QC-approved cohort spectral features.');
      const bar=append(panel,'div',undefined,'np-intel-controls');const [lw,start]=field('Start (seconds)','number','0','1');bar.append(lw);
      const [ld,duration]=field('Duration (4–10 s)','number',active==='Spectrum'?'10':'5','1');bar.append(ld);
      const [lc,channels]=field('Channels (1–8)','number','4','1');bar.append(lc);
      const plot=append(panel,'canvas');plot.className='np-intel-canvas';
      const legend=append(panel,'p','Press Load segment.','np-muted');
      bar.append(button('Load segment',async()=>{
        try{
          legend.textContent='Loading bounded signal segment…';
          const q=new URLSearchParams({start_s:String(Number(start.value)),duration_s:String(Number(duration.value)),channels:String(Number(channels.value))});
          const type=active==='Waveforms'?'waveform':'spectrum';const r=await get(`/subjects/${encodeURIComponent(sub)}/${type}?${q}`);
          draw(plot,type==='waveform'?r.time_s:r.frequency_hz,type==='waveform'?r.signals_uv:r.psd_uv2_per_hz,type==='waveform'?'Time (s) / µV':'Frequency (Hz) / µV²/Hz');
          legend.textContent=r.channels.join(', ')+' · '+(r.method||r.signal_processing||'')+' · Research-only';
        }catch(e){legend.textContent=e.message;}
      }));
    }else if(active==='Annotations'){
      const r=await get('/subjects/'+encodeURIComponent(sub)+'/events');paragraph('Processing exclusions only; no seizure labels or AI detections.');
      paragraph(`${r.annotations.length} excluded windows/intervals`);const ul=append(panel,'ul');for(const item of r.annotations.slice(0,100))append(ul,'li',`${item.start_s}–${item.end_s}s: ${item.reason}`);
    }else if(active==='Evidence'){
      paragraph('NeuroGuard deterministic decision: '+subject.quality_decision.state+' ('+subject.quality_decision.reason+')');
      paragraph('Invoked live policy: '+String(subject.quality_decision.live_policy_invoked));
      paragraph('Live NeuroGuard restriction and read-only NeuroProof-compatible research evidence. No native patient passport.');pre(await get('/subjects/'+encodeURIComponent(sub)+'/evidence'));
    }else if(active==='ARENA'){
      paragraph('Exploratory cross-sectional feature comparison, not ML validation or disease progression.');
      const controls=append(panel,'div',undefined,'np-intel-controls');const label=append(controls,'label','Compare to:');const sel=append(label,'select');
      rows.filter(v=>v.subject!==sub&&v.status==='DESCRIPTIVE_AVAILABLE').forEach(row=>{const opt=append(sel,'option',row.subject);opt.value=row.subject;});
      const result=append(panel,'div');controls.append(button('Compare research features',async()=>{
        try{const r=await get('/arena/compare?a='+encodeURIComponent(sub)+'&b='+encodeURIComponent(sel.value));result.replaceChildren(make('pre',JSON.stringify(r,null,2),'np-intel-json'));}
        catch(e){result.textContent=e.message;}
      }));
    }else if(active==='Processing'){
      paragraph('Completed offline processing is observable; no unverified NeuroCore job starts or retries.');pre(await get('/processing'));
    }else if(active==='Connections'){
      paragraph('Current actual connection states (unavailable links are not simulated).');pre(await get('/connections'));
    }
  }
  function select(sub){chosen=sub;active='Overview';setTabs();render().catch(showError);}
  function tableRows(){table.replaceChildren();const h=append(table,'tr');['Subject','Status','Windows','Alpha µV²','Inspect'].forEach(v=>append(h,'th',v));let count=0;
    for(const r of rows){if(!r.subject.toLowerCase().includes(find.value.trim().toLowerCase()))continue;
      if(filter.value!=='all'&&filter.value!==r.status)continue;count++;
      const tr=append(table,'tr');[r.subject,r.status,`${r.windows_retained}/${r.windows_total}`,fmt(r.features.alpha_uv2)].forEach(v=>append(tr,'td',v));
      const td=append(tr,'td');td.append(button('Inspect',()=>select(r.subject)));
    }
    document.getElementById('np-result-count').textContent=`${count} of ${rows.length} subjects displayed`;
  }
  find.addEventListener('input',tableRows);filter.addEventListener('change',tableRows);
  connect.addEventListener('click',async()=>{
    secret=keyInput.value.trim();keyInput.value='';if(!secret){message.textContent='Enter a research access key.';return;}
    message.textContent='Loading authenticated cohort…';
    try{
      const response=await get('/overview');rows=response.subject_records;
      cohort.hidden=false;message.textContent=`Live API: ${response.total} recordings · ${response.counts.DESCRIPTIVE_AVAILABLE} descriptive · ${response.counts.INSUFFICIENT_WINDOWS} insufficient · research only`;
      const stat=document.querySelectorAll('.np-stat-row strong');
      if(stat.length===4){stat[0].textContent=String(response.total);stat[1].textContent=String(response.counts.DESCRIPTIVE_AVAILABLE);stat[2].textContent=String(response.counts.INSUFFICIENT_WINDOWS);stat[3].textContent='0';}
      tableRows();select(rows[0]?.subject||'');
    }catch(e){secret='';cohort.hidden=true;message.textContent=e.message;}
  });
})();
