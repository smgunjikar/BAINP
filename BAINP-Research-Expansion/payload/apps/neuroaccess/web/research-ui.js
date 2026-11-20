/* Original research protocols. No proprietary assets or clinical scoring. */
export function researchScreen({api,h}){
 document.body.className='account-shell research-shell';
 document.querySelectorAll('body > nav').forEach(n=>n.hidden=true);
 if(!document.getElementById('research-style'))document.head.append(h('link',{id:'research-style',rel:'stylesheet',href:'/research-ui.css'}));
 const mode=new URLSearchParams(location.search).get('mode')==='demo'?'demo':'active';
 const call=(path,method='GET',body)=>api('/research-lab/'+path+(path.includes('?')?'&':'?')+'mode='+mode,method,body);
 const root=h('main',{id:'main',class:'research-page'}),status=h('p',{role:'status','aria-live':'polite'}),content=h('section',{});
 document.getElementById('app').replaceChildren(root);
 let cancelled=false,epoch=0,stopAudio=()=>{},stopTask=async()=>{};const controller=new AbortController();
 window.addEventListener('hashchange',()=>{cancelled=true;epoch++;stopAudio();void stopTask();controller.abort();},{once:true});
 const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)).then(()=>{if(cancelled||!root.isConnected)throw Error('Run interrupted.');});
 const run=async(fn,b)=>{if(b)b.disabled=true;status.textContent='Working…';try{await fn();status.textContent='';}catch(e){if(root.isConnected)status.textContent=e.message;}finally{if(b)b.disabled=false;}};
 const button=(label,fn)=>{const b=h('button',{type:'button',onClick:()=>void run(fn,b)},label);return b;};
 const label=(name,type='text',value='')=>{const input=h('input',{type,value,id:'r-'+crypto.randomUUID()});return {input,node:h('label',{for:input.id},name,input)};};
 const tick=(name)=>{const x=label(name,'checkbox');x.input.removeAttribute('value');return x;};
 const showResult=(r)=>{content.replaceChildren(h('h2',{},'Measurement saved'),h('p',{},'This is an experimental research record, not a clinical result.'),h('pre',{},JSON.stringify(r,null,2)),button('Back to research tasks',()=>tasks()),button('Open measurement history',()=>history()));};
 const header=()=>root.append(h('nav',{'aria-label':'Research navigation'},h('a',{href:'#/journey'},'← My Brain Health'),h('a',{href:'#/admin'},'Administration'),h('a',{href:'#/security'},'Account security')),h('header',{class:'research-hero'},h('p',{class:'eyebrow'},'BAINP / RESEARCH STUDIO'),h('h1',{},'Measure carefully.\nUnderstand more.'),h('p',{},'Original cognitive tasks and guided multimodal measurements, with source and quality in view.'),h('span',{class:'badge'},'Administrator research · '+mode+' records')),h('p',{class:'research-notice'},'Experimental measurements only. These records are separate from participant assessments and do not trigger diagnosis, treatment or NeuroQuest recommendations.'),status);
 let catalogue;
 async function tasks(){
  cancelled=false;content.replaceChildren(h('h2',{},'Explore cognitive tasks'),h('p',{},'Three original protocols inspired by common task families. Their scores are not interchangeable with Creyos, CANTAB, neotiv or other commercial tests.'));
  const grid=h('div',{class:'research-grid'});for(const [id,t] of Object.entries(catalogue.tasks))grid.append(h('article',{},h('span',{class:'eyebrow'},t.domain),h('h3',{},t.title),h('p',{},t.instructions),h('p',{},t.duration),button('Prepare task',()=>prepare(id,t))));content.append(grid);
 }
 async function prepare(id,t){
  const see=tick('I can see the numbers, symbols and instructions with my usual glasses or correction.'),respond=tick('I can select the response controls.'),urgent=tick('I have no current urgent concern requiring care.'),consent=tick('I agree to save this experimental run in the selected research workspace.'),practice=tick('I tried the practice controls and understand the task.');
  const assistance=h('select',{'aria-label':'Assistance'},h('option',{value:'none'},'No assistance'),h('option',{value:'navigation'},'Navigation help only'),h('option',{value:'answers'},'Help answering the task'));
  const practiceArea=h('section',{class:'practice'},h('h3',{},'Untimed practice'),h('p',{},id==='response-control'?'For GO, select Respond. For WAIT, do nothing. This example does not record a score.':'Practice selecting the numbered cells. Practice responses are not stored.'));
  if(id==='response-control')practiceArea.append(h('strong',{},'GO'),button('Respond',async()=>{practiceArea.append(h('p',{},'Response received. In the task, do not respond to WAIT.'));}));
  else {const grid=h('div',{class:'task-grid'});for(let i=0;i<(id==='spatial-sequence'?9:4);i++)grid.append(button(String(i+1),async()=>{practiceArea.querySelector('.example')?.remove();practiceArea.append(h('p',{class:'example'},'You selected '+(i+1)));}));practiceArea.append(grid);}
  content.replaceChildren(h('h2',{},t.title),h('p',{},t.instructions),h('p',{},'A reported eyesight condition alone is not a failure. If the display is not usable, stop and review accessibility. This is not a vision or hearing test.'),see.node,respond.node,h('label',{},'Assistance',assistance),urgent.node,practiceArea,practice.node,consent.node,button('Start experimental task',async()=>{
   if(!practice.input.checked)throw Error('Complete and confirm the practice first.');
   const start=await call('start','POST',{task:id,consent:consent.input.checked,access:{can_perceive:see.input.checked,can_respond:respond.input.checked,assistance:assistance.value,urgent_concern:!urgent.input.checked}});
   await play(start);
  }),button('Back',()=>tasks()));
 }
 async function play(start){
  cancelled=false;const myEpoch=++epoch;const pause=async(ms)=>{await wait(ms);if(epoch!==myEpoch)throw Error('Run interrupted.');};let hidden=0;const onHidden=()=>{if(document.hidden)hidden++;};document.addEventListener('visibilitychange',onHidden);
  const stage=h('section',{class:'task-stage'}),progress=h('p',{role:'status','aria-live':'polite'}),abort=button('Stop this run',async()=>{cancelled=true;await finish([],true);});
  content.replaceChildren(h('h2',{},catalogue.tasks[start.task].title),progress,stage,abort);
  let finalized=false;
  async function finish(answers,aborted=false){
   if(finalized)return;finalized=true;document.removeEventListener('visibilitychange',onHidden);
   const payload={state:aborted?'aborted':'completed',answers,hidden_count:hidden,consent:true};
   try{const result=await call('complete/'+start.id,'POST',payload);if(root.isConnected&&epoch===myEpoch)showResult(result);}catch(e){if(root.isConnected&&epoch===myEpoch)content.replaceChildren(h('h2',{},'Result not saved'),h('p',{},e.message),button('Retry saving this result',async()=>{finalized=false;await finish(answers,aborted);}));}
  }
  stopTask=()=>finish([],true);
  try{
   const answers=[];
   if(start.task==='spatial-sequence'){
    for(const [n,sequence] of start.plan.sequences.entries()){
     progress.textContent='Trial '+(n+1)+' of 6 · Watch';stage.replaceChildren();let resolveAnswer;const result=new Promise(resolve=>resolveAnswer=resolve);const chosen=[];
     const grid=h('div',{class:'task-grid'});const cells=Array.from({length:9},(_,i)=>{const b=h('button',{type:'button',disabled:true,'aria-label':'Cell '+(i+1)},String(i+1));b.addEventListener('click',()=>{if(cancelled)return;chosen.push(i);progress.textContent='Selected '+chosen.length+' of '+sequence.length;if(chosen.length===sequence.length){cells.forEach(c=>c.disabled=true);resolveAnswer(chosen);}});grid.append(b);return b;});stage.append(grid);await pause(700);
     for(const cell of sequence){cells[cell].classList.add('lit');await pause(650);cells[cell].classList.remove('lit');await pause(250);}
     progress.textContent='Repeat the sequence';cells.forEach(b=>b.disabled=false);const a=await result;if(cancelled)return;answers.push(a);await pause(500);
    }
   }else if(start.task==='response-control'){
    for(const [n,go] of start.plan.go.entries()){
     progress.textContent='Trial '+(n+1)+' of '+start.plan.go.length;stage.replaceChildren(h('div',{class:'stimulus'},go?'GO':'WAIT'));let response=null;const t=performance.now();const b=h('button',{type:'button',onClick:()=>{if(response===null){response=performance.now()-t;b.disabled=true;}}},'Respond');stage.append(b);await pause(start.plan.window_ms);b.disabled=true;answers.push(response);stage.replaceChildren(h('div',{class:'stimulus'},'+'));await pause(start.plan.gap_ms);
    }
   }else{
    for(let round=0;round<2;round++){
     progress.textContent='Round '+(round+1)+' of 2 · Study these locations';const grid=h('div',{class:'task-grid four'});
     for(let location=0;location<4;location++)grid.append(h('div',{class:'study-cell'},String(location+1)+' · '+start.plan.symbols[start.plan.pairs.indexOf(location)]));stage.replaceChildren(grid);await pause(8000);
     for(const symbol of start.plan.queries[round]){
      progress.textContent='Where was this symbol?';let resolveAnswer;const result=new Promise(resolve=>resolveAnswer=resolve);const choices=h('div',{class:'task-grid four'});for(let i=0;i<4;i++)choices.append(h('button',{type:'button',onClick:()=>{choices.querySelectorAll('button').forEach(x=>x.disabled=true);resolveAnswer(i);}},String(i+1)));
      stage.replaceChildren(h('div',{class:'stimulus'},start.plan.symbols[symbol]),choices);const a=await result;if(cancelled)return;answers.push(a);
     }
    }
   }
   await finish(answers);
  }catch(e){document.removeEventListener('visibilitychange',onHidden);if(root.isConnected&&!cancelled)status.textContent=e.message;}
 }
 async function voice(){
  const consent=tick('I consent to local microphone capture and saving signal-level measurements. Audio is not uploaded.');
  const prompt='Today I am taking part in a research activity. I will speak at a comfortable pace and stop whenever I choose.';
  const meter=h('progress',{max:1,value:0,'aria-label':'Microphone level'}),info=h('p',{role:'status','aria-live':'polite'},'Microphone is off.'),saveArea=h('div');let busy=false;
  content.replaceChildren(h('h2',{},'Guided voice check'),h('p',{},'Read the passage below for up to 15 seconds. We measure duration, signal level and clipping only. This is not speech recognition or a neurological assessment.'),h('blockquote',{},prompt),consent.node,meter,info,button('Start microphone',async()=>{
   if(busy)throw Error('A capture is already running.');if(!consent.input.checked)throw Error('Consent is required.');if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone capture requires a supported browser on localhost or HTTPS.');
   busy=true;saveArea.replaceChildren();let stream,ctx;try{
    stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
    if(!root.isConnected||!content.contains(info)){stream.getTracks().forEach(t=>t.stop());return;}
    ctx=new AudioContext();await ctx.audioWorklet.addModule('/research-audio.js');await ctx.resume();if(!root.isConnected||!content.contains(info)){stream.getTracks().forEach(t=>t.stop());await ctx.close();return;}const source=ctx.createMediaStreamSource(stream),processor=new AudioWorkletNode(ctx,'research-level'),mute=ctx.createGain();mute.gain.value=0;source.connect(processor);processor.connect(mute);mute.connect(ctx.destination);
    let samples=0,sum=0,clipped=0,done=false;const begin=performance.now();
    const finish=()=>{if(done)return;done=true;clearTimeout(timer);processor.disconnect();source.disconnect();stream.getTracks().forEach(t=>t.stop());const sampleHz=ctx.sampleRate;void ctx.close();busy=false;meter.value=0;info.textContent='Microphone is off. Review and save the measurements if you wish.';
     if(samples&&content.contains(saveArea)){const data={duration_s:samples/sampleHz,sample_hz:sampleHz,rms:Math.sqrt(sum/samples),clipping_fraction:clipped/samples};saveArea.replaceChildren(h('pre',{},JSON.stringify(data,null,2)),button('Save measurements',async()=>{if(!consent.input.checked)throw Error('Storage consent is required.');showResult(await call('import/voice','POST',{consent:true,data}));}),button('Discard',async()=>{saveArea.replaceChildren();}));}
    };
    const timer=setTimeout(finish,15000);stopAudio=finish;
    processor.port.onmessage=e=>{const data=e.data;sum+=data.energy;samples+=data.samples;clipped+=data.clipped;meter.value=Math.min(1,Math.sqrt(data.energy/data.samples)*5);info.textContent='Recording locally · '+Math.floor((performance.now()-begin)/1000)+' / 15 seconds';};
   }catch(e){stream?.getTracks().forEach(t=>t.stop());if(ctx)void ctx.close();busy=false;throw e;}
  }),button('Stop microphone',async()=>stopAudio()),saveArea,h('p',{class:'research-notice'},'Camera analysis, transcription, language biomarkers and disease inference are not implemented. The microphone is released on navigation. Browser processing may vary with device and audio settings.'));
 }
 async function importer(kind){
  const imaging=kind==='imaging',motion=kind==='motion';const file=label(imaging?'Regional MRI JSON':'Signal CSV','file');file.input.accept=imaging?'.json':'.csv';const consent=tick('I authorize saving these measurements in the selected research workspace.');const device=label('Device / acquisition system'),protocol=label('Acquisition protocol and version'),placement=label(motion?'Sensor placement and side':'EEG reference');
  content.replaceChildren(h('h2',{},imaging?'Regional MRI review':motion?'Movement signal review':'EEG signal review'),h('p',{},imaging?'Import the JSON generated by the supplied regional MRI tool using existing anatomical labels. No segmentation model or vendor integration is included.':motion?'Upload accelerometer samples in m/s². Oscillation features describe movement; they cannot establish Parkinson’s disease or distinguish causes of shaking.':'Upload EEG channels in microvolts. This computes descriptive spectral features, not sleep stages or diagnoses.'),h('p',{},imaging?'Source hashes, atlas and pipeline versions accompany every measurement.':motion?'CSV header: t,ax,ay,az · t in seconds · regular sampling ≥25 Hz · at least 10 seconds.':'CSV header: t,Fp1,Fp2 (or your channel names) · t in seconds · regular sampling ≥80 Hz · at least 10 seconds.'),file.node);
  if(!imaging)content.append(device.node,protocol.node,placement.node);content.append(consent.node,button('Analyze and save',async()=>{
   if(!consent.input.checked)throw Error('Storage consent is required.');const selected=file.input.files[0];if(!selected)throw Error('Select a file.');if(selected.size>700000)throw Error('Use a file smaller than 700 KB.');const raw=await selected.text();const body={consent:true};if(imaging)body.data=JSON.parse(raw);else{body.csv=raw;body.metadata={device:device.input.value,protocol:protocol.input.value,units:motion?'m/s2':'uV',[motion?'placement':'reference']:placement.input.value};}showResult(await call('import/'+kind,'POST',body));
  }),h('p',{class:'research-notice'},imaging?'Imported values remain unverified until an anatomical review outside this studio. No normative percentile, brain age, WMH, microbleed or PET model runs here.':'Engineering checks reject gaps and invalid values. Passing them is not clinical validation. Imported samples are analyzed on your local BAINP backend; only features and the input hash are stored.'));
 }
 async function history(){
  content.replaceChildren(h('h2',{},'Measurement history'),h('p',{},'Only this authorized workspace and record mode are shown. Research records are not automatically attached to a participant or pooled with clinical results.'));
  const list=h('div',{class:'research-grid'});let offset=0;const load=async()=>{const result=await call('records?offset='+offset);for(const r of result.items){list.append(h('article',{},h('span',{class:'eyebrow'},r.kind||r.task||'Research'),h('h3',{},r.task||r.kind||'Measurement'),h('p',{},new Date(r.created*1000).toLocaleString()),h('p',{},r.state||r.quality_status||'Recorded'),button('Inspect evidence',async()=>showResult(r)),button('Export JSON',async()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));h('a',{href:url,download:'bainp-research-'+r.id+'.json'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);})));}offset+=50;more.hidden=!result.has_more;};const more=button('Load more',load);content.append(list,more);await load();
  const a=label('First regional MRI record ID'),b=label('Second regional MRI record ID');content.append(h('h3',{},'Compare imported regional measurements'),h('p',{},'For the same participant only. Matching scanner, acquisition and pipeline metadata is required; participant identity and anatomy still require review.'),a.node,b.node,button('Compare',async()=>showResult(await call('compare?first='+encodeURIComponent(a.input.value)+'&second='+encodeURIComponent(b.input.value)))));
 }
 void run(async()=>{
  header();const me=await api('/session');if(me.role!=='admin')throw Error('Research studio is administrator-only while these protocols are experimental.');catalogue=await call('catalogue');if(!root.isConnected)return;
  root.append(h('p',{},'Workspace: '+me.workspace+(me.review_reason?' · Logged administrator review: '+me.review_reason:'')));
  const tabs=h('nav',{'aria-label':'Research modules',class:'research-tabs'});for(const [title,fn]of [['Cognitive tasks',tasks],['Voice',voice],['Movement',()=>importer('motion')],['EEG',()=>importer('eeg')],['MRI',()=>importer('imaging')],['History & evidence',history]])tabs.append(button(title,async()=>{cancelled=true;epoch++;stopAudio();await stopTask();stopTask=async()=>{};await fn();}));root.append(tabs,content);await tasks();
 });
}
