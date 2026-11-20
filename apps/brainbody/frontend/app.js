'use strict';
const $=id=>document.getElementById(id),q=new URLSearchParams(location.search),mode=q.get('mode'),person=q.get('person');let profile=mode==='demo'?(q.get('profile')||(person?'selected':'control')):'selected';if(!['selected','control','impairment'].includes(profile)||(mode==='demo'&&!person&&profile==='selected'))profile='control';
let dictionary=null,current=null,busy=false,pending=false,epoch=0,lastRevision='',asOf=null,editing=null,pendingId=null,oldTimes={};const synthetic=()=>mode==='demo'&&profile!=='selected';
const number=v=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat(undefined,{maximumFractionDigits:3}).format(v):'—',human=s=>String(s||'unknown').replaceAll('_',' ').toLowerCase(),date=s=>s?new Date(s).toLocaleString():'Unknown';
const scopes={context:['Health & lifestyle context','Physical health, sleep, activity, medication and wellbeing reports'],clinical_biomarkers:['Clinical assays','Authorized clinical laboratory and biomarker results'],family_history:['Family history','Consented contextual history without relative names'],genomic_summary:['Professional genomic summaries','Separate consent plus explicit disclosure required'],molecular_research:['Experimental molecular research','Assay-specific peripheral oxidative-stress measurements']};
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}function row(values){const r=el('tr');for(const value of values)r.append(el('td',value));return r}function empty(id,text){$(id).replaceChildren(el('p',text,'empty'))}function base(){return 'participants/'+encodeURIComponent(person)}function sourceURL(path){return path+'?'+new URLSearchParams({mode,...(person?{person}:{})})}function localTime(iso){const d=new Date(iso);return new Date(d-d.getTimezoneOffset()*60000).toISOString().slice(0,19)}function iso(id){return new Date($(id).value).toISOString()}function optionalNumber(id){return $(id).value===''?undefined:Number($(id).value)}function nonempty(id){return $(id).value.trim()||undefined}
async function api(path,method='GET',body){const r=await fetch('/api/brainbody/'+path,{cache:'no-store',method,headers:{'Content-Type':'application/json','X-NeuroAccess-Request':'1'},...(body===undefined?{}:{body:JSON.stringify(body)})});let d;try{d=await r.json()}catch{throw Error('API unavailable; check the BAINP API terminal.')}if(!r.ok){const detail=typeof d.detail==='string'?human(d.detail):Array.isArray(d.detail)?d.detail.map(e=>e.msg).join('; '):'Unsupported input';const error=Error(r.status===401?'Sign in on BAINP, then refresh.':detail+' ('+r.status+')');error.status=r.status;throw error}return d}
$('home').href=sourceURL('/');$('twinLink').hidden=true;$('profileLabel').hidden=mode!=='demo';if (!person && mode==='demo') $('profile').querySelector('option[value=selected]')?.remove();$('profile').value=profile;const initial=new Date().toISOString();for(const id of ['observedAt','availableAt'])$(id).value=localTime(initial);
const needsParticipant = !synthetic() && !person;
$('chooseParticipant').hidden = !needsParticipant;
$('chooseParticipantLink').href = '/?'+new URLSearchParams({mode:mode==='demo'?'demo':'active'});
if (needsParticipant) {
  $('name').textContent = 'No participant selected';
  $('refresh').disabled = true;
}
$('export').disabled = true;
$('report').disabled = true;
let selectedSession = q.get('session') || null;

function resetSnapshot() {
  epoch++;
  current = null;
  lastRevision = '';
  $('snapshotWorkspace').hidden = true;
  $('export').disabled = true;
  $('report').disabled = true;
}

function tab(name){for(const b of document.querySelectorAll('[data-tab]')){const active=b.dataset.tab===name;b.setAttribute('aria-pressed',String(active));$(b.dataset.tab).hidden=!active}$('sessionWorkspace').hidden=name!=='timeline';if(name==='timeline')drawAligned()}
for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>tab(b.dataset.tab);for(const b of document.querySelectorAll('[data-go]'))b.onclick=()=>tab(b.dataset.go);
if (['timeline','review','privacy'].includes(q.get('view'))) tab(q.get('view'));
$('profile').onchange=()=>{profile=$('profile').value;selectedSession=null;$('showSensitive').checked=false;asOf=null;$('asOf').value='';editing=null;pendingId=null;resetSnapshot();refresh(true)};
for(const [key,[label,description]] of Object.entries(scopes)){const c=el('div',undefined,'scope'),l=el('label',undefined,'check'),input=el('input');input.type='checkbox';input.id='scope-'+key;l.append(input,el('span',label));c.append(l,el('small',description));$('consentScopes').append(c)}
function options(id,values,label,selected){$(id).replaceChildren();for(const value of values){const o=el('option',label(value));o.value=typeof value==='string'?value:value.id;$(id).append(o)}if(selected!==undefined&&values.some(v=>(typeof v==='string'?v:v.id)===selected))$(id).value=selected;else if(values.length)$(id).value=typeof values[0]==='string'?values[0]:values[0].id;}
function formChanged(){if(!dictionary)return;const numeric=$('kind').value==='measurement',metric=dictionary.metrics[$('entryMetric').value],kind=$('kind').value;for(const id of ['numericFields','metricLabel','referenceFields'])$(id).hidden=!numeric;$('reportFields').hidden=numeric;$('assayFields').hidden=!numeric||!metric?.assay_required;$('instrumentFields').hidden=!numeric||$('entryMetric').value!=='questionnaire_total';$('relativeLabel').hidden=kind!=='family_history';$('professionalLabel').hidden=$('disclosureLabel').hidden=kind!=='professional_genomic_finding';const oldSource=$('sourceKind').value,origins=numeric?metric.origins:kind==='professional_genomic_finding'?['professional_report']:['self_report','clinician_entry','professional_report'];options('sourceKind',origins,human,oldSource);if(numeric){const oldUnit=$('unit').value;options('unit',metric.units,v=>v,oldUnit)}$('deviceLabel').hidden=$('sourceKind').value!=='device';$('referenceDetails').hidden=!$('hasReference').checked;const absent=['not_detected','not_reported'].includes($('qualifier').value);$('value').disabled=absent;}
$('kind').onchange=$('entryMetric').onchange=formChanged;$('sourceKind').onchange=()=>$('deviceLabel').hidden=$('sourceKind').value!=='device';$('hasReference').onchange=()=>$('referenceDetails').hidden=!$('hasReference').checked;$('qualifier').onchange=formChanged;
function svg(tag,attrs={},text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e}
function chart(id,points,unit,extent){const g=$(id);g.replaceChildren();const all=points.filter(p=>p.qualifier!=='less_than'&&p.qualifier!=='greater_than'&&p.qualifier!=='not_detected'&&p.qualifier!=='not_reported'&&p.at&&Number.isFinite(Date.parse(p.at))&&typeof p.value==='number');if(!all.length){g.append(svg('text',{x:50,y:100},'No exact point observations available'));return}const [,,width,height]=g.getAttribute('viewBox').split(' ').map(Number),min=all.reduce((m,p)=>Math.min(m,p.value),Infinity),max=all.reduce((m,p)=>Math.max(m,p.value),-Infinity),pad=(max-min)*.12||Math.abs(min)*.05||1,t0=extent?.[0]??all.reduce((m,p)=>Math.min(m,Date.parse(p.at)),Infinity),last=extent?.[1]??all.reduce((m,p)=>Math.max(m,Date.parse(p.at)),-Infinity),span=last-t0||86400000,x=t=>75+(t-t0)/span*(width-110),y=v=>height-40-(v-min+pad)/(max-min+2*pad)*(height-70);for(let i=0;i<5;i++){const v=min-pad+(max-min+2*pad)*i/4,yy=y(v);g.append(svg('line',{x1:75,x2:width-35,y1:yy,y2:yy,stroke:'#e3ebec'}),svg('text',{x:65,y:yy+4,'text-anchor':'end'},number(v)))}g.append(svg('text',{x:75,y:16},unit),svg('text',{x:75,y:height-10},new Date(t0).toISOString().slice(0,10)),svg('text',{x:width-35,y:height-10,'text-anchor':'end'},new Date(last).toISOString().slice(0,10)));const step=Math.max(1,Math.ceil(all.length/1200)),drawn=all.filter((p,i)=>i%step===0||i===all.length-1);for(const p of drawn){const dot=svg('circle',{cx:x(Date.parse(p.at)),cy:y(p.value),r:drawn.length>150?2:4,fill:p.eligible===false?'#b49a68':'#3c8088'});dot.append(svg('title',{},date(p.at)+': '+number(p.value)+' '+unit));g.append(dot)}if(step>1)g.append(svg('text',{x:width-35,y:18,'text-anchor':'end'},'Sampled chart; full records remain in evidence export'))}
function resultText(r){if(r.kind!=='measurement')return r.summary;if(r.qualifier==='not_detected'||r.qualifier==='not_reported')return human(r.qualifier)+' · '+r.absent_reason;return(r.qualifier==='less_than'?'< ':r.qualifier==='greater_than'?'> ':'')+number(r.value)+' '+r.unit}
function render(d){current=d;renderConnections(d);$('snapshotWorkspace').hidden=false;$('export').disabled=false;$('report').disabled=false;const twin=d.connections?.find(c=>c.id==='twin');$('twinLink').hidden=!twin?.href;if(twin?.href)$('twinLink').href=twin.href;$('mode').textContent=synthetic()?'SYNTHETIC DEMO · INVENTED VALUES':mode==='demo'?'DEMO · FICTIONAL RECORDS':'ACTIVE · AUTHORIZED CONTEXT';$('name').textContent=d.identity.display_name;$('identity').textContent=synthetic()?'One coherent fictional profile. No real clinical assay or genetic finding.':'Participant '+d.identity.participant_id;$('boundary').textContent=synthetic()?'All demo values, reference intervals, history and case labels are invented. Co-occurrence does not establish a cause or a clinical interpretation.':'Research context. Source intervals, device estimates and reported concerns are retained without a neurological diagnosis or treatment recommendation.';
$('systems').replaceChildren();for(const s of d.systems){const c=el('div',undefined,'system');c.append(el('b',s.label),el('strong',String(s.records)),el('span',s.streams+' distinct numeric streams'));$('systems').append(c)}$('metrics').replaceChildren();for(const s of d.series.slice(0,8)){const p=s.points.at(-1),c=el('div',undefined,'metric');c.append(el('b',s.label),el('strong',p.qualifier==='exact'?number(p.value)+' '+s.unit:p.qualifier==='less_than'?'< '+number(p.value)+' '+s.unit:p.qualifier==='greater_than'?'> '+number(p.value)+' '+s.unit:human(p.qualifier)),el('span',date(p.at)+' · '+s.source.kind+(p.eligible===false?' · excluded from summaries':'')));$('metrics').append(c)}if(!d.series.length)empty('metrics',d.consent.scopes.length?'No numeric observations in the authorized scopes. Reported context, if present, appears under evidence quality.':'Authorization required to display participant observations.');
$('quality').replaceChildren();for(const [label,value] of [['Authorized source records',d.records.length],['Pending source/context reviews',d.review_queue.filter(r=>r.status==='pending').length],['Cognitive sessions with timing context',d.alignments.length],['Disease risk / causal effect','Not calculated']]){const c=el('div',undefined,'qualityRow');c.append(el('span',label),el('b',String(value)));$('quality').append(c)}$('reports').replaceChildren();for(const r of d.records.filter(r=>r.payload.kind!=='measurement'&&r.payload.kind!=='professional_genomic_finding').slice(-5)){const c=el('div',undefined,'recordNote');c.append(el('b',r.label),el('p',r.payload.summary),el('p',date(r.payload.observed_at)+' · '+r.payload.source.kind));$('reports').append(c)}
const selected=$('metric').value;options('metric',d.series,s=>s.label+' · '+s.unit+' · '+s.id.slice(0,8),selected);renderTrend();const cognitiveGroups=new Map;for(const p of d.cognitive_points){const key=[p.task,p.metric,p.condition_group].join(':');if(!cognitiveGroups.has(key))cognitiveGroups.set(key,{id:key,label:p.task+' · '+human(p.metric)+' · '+p.condition_group})}options('cognitiveMetric',[...cognitiveGroups.values()],p=>p.label,$('cognitiveMetric').value);drawAligned();renderRecords();renderBiomarkers();renderReview();renderPrivacy();renderAlignments();renderSessionSelector();}
const connectionStates = {
  consent_required: 'Authorization required',
  source_unavailable: 'Source adapter unavailable',
  empty: 'No eligible records',
  unlinked: 'No participant link or record registered',
  registered: 'Registered in NeuroTwin',
  available: 'Available in BBC-BE',
  synthetic_example: 'Fictional BBC-BE example',
  synthetic_in_twin: 'Fictional examples in NeuroTwin',
  historical_unavailable: 'Current inventory withheld in replay',
  workspace_available: 'Workspace available',
  local_review: 'Review workspace'
};

const connectionNotes = {
  cognition: 'Session history and timing context.',
  wearable: 'Stored measurements. Live device status belongs in NeuroSense.',
  imaging: 'Participant links are registered in NeuroTwin. Scan availability is checked there.',
  neural: 'EEG replay and summary records are managed in NeuroTwin.',
  clinical: 'Versioned source records in NeuroTwin. BBC-BE assays have a separate evidence view.',
  twin: 'The twin receives authorized descriptive context from BBC-BE.',
  governance: 'Inspect source checks in BBC-BE and model governance in NeuroTwin.'
};

function openConnectionPanel(name) {
  tab(name);
  $(name).scrollIntoView?.({block:'start'});
}

function renderConnections(data) {
  const list = $('sourceCards');
  list.replaceChildren();
  for (const item of data.connections || []) {
    const card = el('article', undefined, 'sourceCard');
    card.append(el('h3', item.name), el('strong', connectionStates[item.state] || human(item.state)));
    if (item.count != null) card.append(el('p', item.count+' '+item.unit, 'sourceCount'));
    card.append(el('p', connectionNotes[item.id], 'caption'));
    const actions = el('div', undefined, 'sourceActions');
    if (item.state === 'consent_required') {
      const action = el('button', 'Manage authorization', 'secondary');
      action.onclick = () => openConnectionPanel('privacy');
      actions.append(action);
    }
    const targets = [];
    if (item.href) targets.push([item.href, asOf ? 'Open current source workspace' : item.id === 'imaging' ? 'Open anatomical twin' : item.id === 'neural' ? 'Open neural twin' : 'Open workspace']);
    if (item.research_href) targets.push([item.research_href, 'Open research viewer']);
    for (const [href,label] of targets) {
      const link = el('a',label);
      link.href = href;
      actions.append(link);
    }
    if (item.id === 'governance' || item.id === 'clinical') {
      const action = el('button', item.id === 'governance' ? 'Open BBC-BE review' : 'Open assay evidence', 'secondary');
      action.onclick = () => openConnectionPanel(item.id === 'governance' ? 'review' : 'biomarkers');
      actions.append(action);
    }
    card.append(actions);
    list.append(card);
  }

  const next = $('contextNext');
  next.hidden = data.synthetic || Boolean(asOf) || data.records.length > 0;
  $('contextNextText').textContent = data.consent.scopes.length
    ? 'Authorization is recorded. Add a verified observation or inspect available source modules.'
    : 'Authorize the relevant scopes to see this participant’s available records and link status.';
  $('contextNextAction').textContent = data.consent.scopes.length ? 'Record an observation' : 'Manage authorization';
  $('contextNextAction').onclick = () => openConnectionPanel(data.consent.scopes.length ? 'entry' : 'privacy');
}

function renderTrend(){const s=current.series.find(s=>s.id===$('metric').value);chart('contextChart',s?.points||[],s?.unit||'');$('metricContext').textContent=s?(s.assay?[s.assay.name,s.assay.version,s.assay.specimen,s.assay.laboratory].join(' · '):s.source.organization):'';$('trend').textContent=s?s.summary.usable+' eligible / '+s.summary.total+' records · '+s.summary.observed_days+' observed UTC days. Descriptive first-to-last daily-median difference: '+number(s.summary.descriptive_first_last_change)+' '+s.unit+'. Amber points are excluded from summaries. No clinical change threshold or expected sampling schedule is established.':'No numeric measurements. Missing values are not filled.';}
function drawAligned(){if(!current)return;const s=current.series.find(s=>s.id===$('metric').value),key=$('cognitiveMetric').value,points=current.cognitive_points.filter(p=>[p.task,p.metric,p.condition_group].join(':')===key).map(p=>({...p,eligible:p.status==='completed'&&!p.flags.length})),times=[...(s?.points||[]),...points].map(p=>Date.parse(p.at)).filter(Number.isFinite),extent=times.length?[times.reduce((a,b)=>Math.min(a,b)),times.reduce((a,b)=>Math.max(a,b))]:undefined;chart('alignedContext',s?.points||[],s?.unit||'',extent);chart('cognitiveChart',points,points[0]?.metric==='median_correct_rt_ms'?'ms':'count',extent);$('alignmentNote').textContent='Common UTC date axis; separate measurement units. Amber points are source-flagged. No correlation, cause or neurological change is inferred.';}
$('metric').onchange=()=>{renderTrend();drawAligned()};$('cognitiveMetric').onchange=drawAligned;
function renderAlignments(){$('alignments').replaceChildren();for(const a of current.alignments.slice().reverse().slice(0,30)){const detail=el('details');detail.append(el('summary',date(a.session_start)+' · '+a.known_before_session.length+' known-before / '+a.retrospectively_entered.length+' retrospective / '+a.availability_unknown.length+' availability-unknown'),el('p',a.protocol+' · form '+a.form+' · '+human(a.status)),el('p',a.interpretation));for(const [title,list] of [['Known before session',a.known_before_session],['Retrospectively entered / became available later',a.retrospectively_entered],['Legacy wearable availability not established',a.availability_unknown]]){detail.append(el('b',title));for(const p of list.slice(0,12))detail.append(el('p',p.label+' · '+date(p.observed_at)+' · '+p.record_id));if(list.length>12)detail.append(el('p',(list.length-12)+' more records in the evidence export.'))}$('alignments').append(detail)}if(!current.alignments.length)empty('alignments','No authorized cognitive sessions available for context linkage.');}
const sessionBuckets = [
  ['Known before session', 'known_before_session'],
  ['Available or entered after session start', 'retrospectively_entered'],
  ['Wearable availability unknown', 'availability_unknown']
];

const followUpTopics = [
  {title:'Blood-pressure context', metrics:['bp_systolic','bp_diastolic'], evidence:'WHO-PREVENTION',
    question:'How were these readings collected, and how do they compare with prior readings reviewed by the care team?'},
  {title:'Metabolic context', metrics:['hba1c','glucose','ldl_cholesterol','hdl_cholesterol','total_cholesterol','triglycerides'], evidence:'WHO-PREVENTION',
    question:'Do the specimen, assay and collection conditions support comparing these results with earlier measurements?'},
  {title:'Activity and lifestyle context', metrics:['steps','activity_minutes'], kinds:['lifestyle_report'], evidence:'WHO-PREVENTION',
    question:'Were the recorded activity and lifestyle observations typical for this participant during this period?'},
  {title:'Sleep and medication context', metrics:['sleep_duration','sleep_efficiency'], kinds:['sleep_report','medication'], evidence:'NIA-COGNITIVE-HEALTH',
    question:'What did the participant report about sleep and medication around this session, and what needs confirmation?'}
];

function renderSessionSelector() {
  const sessions = [...current.alignments].sort((a,b) => Date.parse(b.session_start) - Date.parse(a.session_start));
  if (selectedSession === null) selectedSession = sessions[0]?.session_id ?? null;
  options('sessionSelect', [
    {id:'', label:'Select a cognitive session'},
    ...sessions.map(s => ({id:s.session_id, label:date(s.session_start)+' · '+human(s.status)}))
  ], s => s.label, selectedSession);
  $('sessionSelect').disabled = !sessions.length;
  renderSessionReview();
}

function renderSessionReview() {
  const target = $('sessionReview');
  const source = $('cognitiveSource');
  const session = current.alignments.find(a => a.session_id === selectedSession);
  target.replaceChildren();
  source.hidden = !session || synthetic();
  source.removeAttribute('href');
  if (!session) {
    target.append(el('p', !current.consent.scopes.includes('context')
      ? 'Authorize health and lifestyle context to load cognitive sessions for this participant.'
      : selectedSession
      ? 'This session is unavailable for the selected participant or evidence cutoff.'
      : 'Choose a cognitive session to review its associated observations.', 'empty'));
    return;
  }
  if (!synthetic()) source.href = '/cognition-results?'+new URLSearchParams({mode,session:session.session_id});
  target.append(el('p', date(session.session_start)+' · '+session.protocol+' · form '+session.form+' · '+human(session.status)));
  target.append(el('p', session.interpretation, 'caption'));
  const cognitive = current.cognitive_points.filter(p => p.session_id === session.session_id);
  const observations = el('details');
  observations.append(el('summary', 'Recorded cognitive observations ('+cognitive.length+')'));
  for (const p of cognitive) {
    observations.append(el('p', p.task+' · '+human(p.metric)+' '+number(p.value)
      +' · '+human(p.status)+' · '+(p.flags.length ? p.flags.map(human).join(', ') : 'No recorded quality flags')));
  }
  if (!cognitive.length) observations.append(el('p', 'No numeric cognitive observations available for this session.'));
  target.append(observations);
  const records = new Map(current.records.map(record => [record.id, record]));
  const linkedRecords = new Map();
  const legacyPoints = new Map();
  for (const stream of current.series) {
    for (const point of stream.points) {
      if (point.id.startsWith('sense:')) legacyPoints.set(point.id, {stream,point});
    }
  }
  for (const [title,key] of sessionBuckets) {
    const items = session[key];
    const detail = el('details');
    detail.open = Boolean(items.length);
    detail.append(el('summary', title+' ('+items.length+')'));
    if (!items.length) detail.append(el('p', 'No visible observations in this category.', 'caption'));
    for (const item of items) {
      const record = records.get(item.record_id);
      const legacy = legacyPoints.get(item.record_id);
      const p = record?.payload;
      const value = p ? resultText(p) : legacy ? number(legacy.point.value)+' '+legacy.stream.unit : 'Source value unavailable';
      const origin = p ? p.source.kind+' / '+p.source.organization+' / '+p.source.record_reference
        : legacy ? legacy.stream.source.organization+' / '+legacy.stream.source.device_id+' / '+item.record_id : item.record_id;
      const entry = el('div', undefined, 'sessionObservation');
      entry.append(el('b', item.label+' · '+value), el('p', origin));
      if (p?.assay) entry.append(el('p', [p.assay.name,p.assay.version,p.assay.specimen,p.assay.method,p.assay.laboratory].join(' · ')));
      entry.append(el('p', 'Observed '+date(item.observed_at)+' · Available '+date(p?.available_at ?? legacy?.point.available_at)
        +' · Received '+date(record?.known_at ?? legacy?.point.known_at), 'caption'));
      if (legacy) entry.append(el('p', legacy.point.eligible ? 'Usable wearable observation' : 'Wearable observation requires source review','caption'));
      if (p) {
        entry.append(el('p', 'Source quality: '+human(p.quality)+' · Record '+record.id+' · Revision '+p.revision,'caption'));
        for (const finding of record.findings) entry.append(el('p', finding.text, 'caption'));
        linkedRecords.set(record.id, record);
      }
      detail.append(entry);
    }
    target.append(detail);
  }
  const followUp = el('div');
  followUp.append(el('h3','Questions for follow-up'));
  for (const topic of followUpTopics) {
    const relevant = [...linkedRecords.values()].filter(({payload:p,numeric_eligible}) => (
      (numeric_eligible && topic.metrics.includes(p.metric)) ||
      (p.quality === 'usable' && topic.kinds?.includes(p.kind))
    ));
    const evidence = current.evidence.find(item => item.id === topic.evidence);
    if (!relevant.length || !evidence) continue;
    const link = el('a',evidence.title);
    link.href = evidence.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    const card = el('div',undefined,'evidenceCard');
    card.append(el('b',topic.title),el('p',topic.question),
      el('p','Source observations: '+[...new Set(relevant.map(r=>r.label))].join(', '),'caption'),link);
    followUp.append(card);
  }
  if (followUp.children.length === 1) followUp.append(el('p','No eligible linked observations for the discussion topics.'));
  target.append(followUp);
}

$('sessionSelect').onchange = () => {
  selectedSession = $('sessionSelect').value;
  renderSessionReview();
};

function renderRecords(){$('recordTable').replaceChildren();for(const r of current.records.slice().sort((a,b)=>Date.parse(b.payload.observed_at)-Date.parse(a.payload.observed_at)).slice(0,100)){const p=r.payload,t=row([r.label,resultText(p),p.source.kind+' / '+p.source.organization+(p.assay?' / '+p.assay.name+' '+p.assay.version:''),'Observed: '+date(p.observed_at)+'; available: '+date(p.available_at)+'; received: '+date(r.known_at),(r.interval_position?human(r.interval_position)+'; ':'')+human(p.quality)+(r.findings.length?' · '+r.findings.map(f=>human(f.code)).join('; '):'')]);const controls=el('td');if(!synthetic()&&!asOf){const edit=el('button','Amend','secondary');edit.onclick=()=>editRecord(r);const history=el('button','Revisions','secondary');history.onclick=async()=>{try{const data=await api(base()+'/records/'+r.id+'/revisions?'+new URLSearchParams({mode,include_sensitive:$('showSensitive').checked})),detail=el('details');detail.open=true;detail.append(el('summary','Immutable source revision history'));for(const item of data.items)detail.append(el('p','Revision '+item.revision+' · received '+date(item.known_at)+' · '+resultText(item.payload)+' · SHA '+item.sha256));controls.append(detail)}catch(e){$('status').textContent=e.message}};const del=el('button','Delete','danger');del.onclick=async()=>{if(!confirm('Delete this BBC-BE record and all its revisions? Other module records remain.'))return;try{await api(base()+'/records/'+r.id+'?'+new URLSearchParams({mode,expected_revision:p.revision}),'DELETE');await refresh(true)}catch(e){$('status').textContent=e.message}};controls.append(edit,history,del)}else controls.append(el('span','Read-only'));t.append(controls);$('recordTable').append(t)}if(!current.records.length)$('recordTable').append(row(['No authorized records','—','—','—','—']));}
function renderBiomarkers(){$('assayTable').replaceChildren();for(const r of current.records.filter(r=>r.payload.assay)){const p=r.payload,a=p.assay;$('assayTable').append(row([r.label,resultText(p),a.specimen+' / '+a.method,a.name+' '+a.version+' / '+a.laboratory,r.findings.map(n=>n.text).join('; ')||human(r.interval_position)]))}if(!$('assayTable').children.length)$('assayTable').append(row(['No authorized assay results','—','—','—','No assay or reference value is invented']));$('family').replaceChildren();for(const r of current.records.filter(r=>r.payload.kind==='family_history'))$('family').append(el('p',r.payload.relative_degree+' degree · '+r.payload.summary));if(!$('family').children.length)empty('family','No authorized family-history report.');$('genomics').replaceChildren();for(const r of current.records.filter(r=>r.payload.kind==='professional_genomic_finding'))$('genomics').append(el('p',r.payload.summary),el('p','Professional reference: '+r.payload.professional_interpretation_reference));if(!$('genomics').children.length)empty('genomics',current.genomic_content_withheld?'Professional genomic contents are withheld until explicit authorized disclosure.':'No separately authorized professional genomic summary in this view.');}
function renderReview(){$('reviewQueue').replaceChildren();for(const f of current.review_queue.slice(0,80)){const c=el('div',undefined,'finding');c.append(el('b',f.label+' · '+human(f.code)),el('p',f.text),el('p','Record '+f.record_id+' · revision '+f.revision+' · '+human(f.status)));if(f.note)c.append(el('p','Review note: '+f.note));if(!synthetic()&&!asOf){const select=el('select');for(const status of ['pending','acknowledged','resolved']){const o=el('option',human(status));o.value=status;select.append(o)}select.value=f.status;const note=el('textarea');note.rows=2;note.maxLength=500;note.setAttribute('aria-label','Review note for '+f.label);note.value=f.note||'';const button=el('button','Save review note','secondary');button.onclick=async()=>{try{if(note.value.trim().length<5)throw Error('Add a review note of at least five characters.');await api(base()+'/reviews/'+f.record_id+'?mode='+mode,'PUT',{record_revision:f.revision,finding_code:f.code,status:select.value,note:note.value.trim(),include_sensitive:$('showSensitive').checked});await refresh(true)}catch(e){$('status').textContent=e.message}};c.append(select,note,button)}$('reviewQueue').append(c)}if(!current.review_queue.length)empty('reviewQueue','No current generated source-review findings. This does not certify clinical health.');$('evidence').replaceChildren();for(const e of current.evidence){const c=el('div',undefined,'evidenceCard'),a=el('a',e.title);a.href=e.url;a.target='_blank';a.rel='noopener noreferrer';c.append(a,el('p',e.text));$('evidence').append(c)}$('graph').replaceChildren();const map=new Map(current.graph.nodes.map(n=>[n.id,n]));for(const e of current.graph.edges)$('graph').append(row([e.source,map.get(e.target)?.label||e.target,human(e.relationship)]));$('roadmap').replaceChildren();for(const r of current.roadmap)$('roadmap').append(row(r));}
function renderPrivacy(){for(const key of Object.keys(scopes))$('scope-'+key).checked=current.consent.scopes.includes(key);$('saveConsent').disabled=synthetic()||!!asOf;$('saveRecord').disabled=synthetic()||!!asOf;$('entryMode').textContent=synthetic()?'Synthetic presets are read-only. Select an existing demo participant to save fictional records; active data are never populated from this example.':asOf?'Historical evidence replay is read-only. Return to current evidence to record or amend context.':'Authorization is checked for each scope. Results, units, source references and assay metadata are preserved.';$('consentInfo').replaceChildren(el('p','Authorization revision: '+current.consent.revision),el('p','Recorded: '+date(current.consent.known_at)),el('p',current.consent.authorization_reference||'No BBC-BE authorization is recorded.'));$('boundaries').replaceChildren();for(const text of current.boundaries)$('boundaries').append(el('li',text));$('snapshotHash').textContent='Engine '+current.version+' · snapshot SHA-256 '+current.revision;$('cutoffNote').textContent=asOf?'Historical local-knowledge cutoff: '+date(asOf):'Current authorized evidence.';}
$('showSensitive').onchange=()=>{resetSnapshot();refresh(true)};$('applyCutoff').onclick=()=>{try{if(synthetic())throw Error('Historical local-knowledge replay applies to stored participant records.');if(!$('asOf').value)throw Error('Choose a cutoff.');asOf=iso('asOf');resetSnapshot();refresh(true)}catch(e){$('cutoffNote').textContent=e.message}};$('clearCutoff').onclick=()=>{asOf=null;$('asOf').value='';resetSnapshot();refresh(true)};
$('consentForm').onsubmit=async e=>{e.preventDefault();try{if(synthetic()||asOf)return;await api(base()+'/consent?mode='+mode,'PUT',{expected_revision:current.consent.revision,scopes:Object.keys(scopes).filter(s=>$('scope-'+s).checked),authorization_reference:$('authorizationReference').value.trim()});$('consentStatus').textContent='Authorization scopes saved.';$('authorizationReference').value='';resetSnapshot();await refresh(true)}catch(error){$('consentStatus').textContent=error.message}};
function buildPayload(){const kind=$('kind').value,metric=$('entryMetric').value,numeric=kind==='measurement';const source={kind:$('sourceKind').value,organization:$('organization').value.trim(),record_reference:$('sourceReference').value.trim(),...($('sourceKind').value==='device'?{device_id:nonempty('deviceId')}:{}),...(nonempty('cohort')||nonempty('sourceSubject')?{cohort:nonempty('cohort'),source_subject:nonempty('sourceSubject')}:{})};const observation=oldTimes.observedLocal===$('observedAt').value?oldTimes.observed:iso('observedAt'),available=oldTimes.availableLocal===$('availableAt').value?oldTimes.available:iso('availableAt');const body={revision:editing?editing.payload.revision+1:1,kind,observed_at:observation,available_at:available,source,identity_verified:$('identityVerified').checked,quality:$('sourceQuality').value,context:$('context').value.trim(),needs_review:$('needsReview').checked};if(numeric){body.metric=metric;if(nonempty('comparisonContext'))body.measurement_context_key=nonempty('comparisonContext');body.unit=$('unit').value;body.qualifier=$('qualifier').value;if(['not_detected','not_reported'].includes(body.qualifier))body.absent_reason=$('absentReason').value.trim();else{if($('value').value==='')throw Error('Enter the exact value or reported bound.');body.value=Number($('value').value)}if(dictionary.metrics[metric].assay_required)body.assay={name:$('assayName').value.trim(),version:$('assayVersion').value.trim(),laboratory:$('laboratory').value.trim(),specimen:$('specimen').value,method:$('assayMethod').value.trim(),lower_quantitation_limit:optionalNumber('loqLow'),upper_quantitation_limit:optionalNumber('loqHigh')};if(metric==='questionnaire_total')body.instrument={name:$('instrumentName').value.trim(),version:$('instrumentVersion').value.trim(),language:$('instrumentLanguage').value.trim(),permission_basis:$('permissionBasis').value.trim(),administered_by:$('instrumentBy').value.trim()};if($('hasReference').checked)body.reference={kind:$('referenceKind').value,lower:optionalNumber('referenceLow'),upper:optionalNumber('referenceHigh'),unit:body.unit,source:$('referenceSource').value.trim(),population_context:$('referencePopulation').value.trim(),applies_to_participant:$('referenceApplies').value};if(nonempty('encounter'))body.encounter_id=nonempty('encounter')}else{body.summary=$('summary').value.trim();if($('effectiveStart').value)body.effective_start=iso('effectiveStart');if($('effectiveEnd').value)body.effective_end=iso('effectiveEnd');if(kind==='family_history')body.relative_degree=$('relativeDegree').value;if(kind==='professional_genomic_finding'){body.professional_interpretation_reference=$('professionalReference').value.trim();body.disclosure_authorized=$('disclosureAuthorized').checked}}return body;}
$('recordForm').onsubmit=async e=>{e.preventDefault();try{if(synthetic()||asOf)return;const body=buildPayload();pendingId??=editing?.id||crypto.randomUUID();$('saveRecord').disabled=true;const result=await api(base()+'/records/'+pendingId+'?mode='+mode,'PUT',body);$('saveStatus').textContent='Saved revision '+result.revision+'. Source data remain stored until deleted.';editing=null;pendingId=null;oldTimes={};$('cancelEdit').hidden=true;$('saveRecord').textContent='Save verified record';for(const id of ['kind','entryMetric','sourceKind','organization','sourceReference','cohort','sourceSubject'])$(id).disabled=false;$('identityVerified').checked=false;await refresh(true)}catch(error){$('saveStatus').textContent=error.message+' Values are retained. If a previous request may have succeeded, refresh and use Amend for a correction.'}finally{$('saveRecord').disabled=synthetic()||!!asOf}};
function editRecord(record){editing=record;pendingId=record.id;const p=record.payload;tab('entry');$('kind').value=p.kind;if(p.metric)$('entryMetric').value=p.metric;formChanged();const set=(id,value)=>$(id).value=value??'';set('sourceKind',p.source.kind);set('unit',p.unit);set('organization',p.source.organization);set('sourceReference',p.source.record_reference);set('deviceId',p.source.device_id);set('cohort',p.source.cohort);set('sourceSubject',p.source.source_subject);set('observedAt',localTime(p.observed_at));set('availableAt',localTime(p.available_at));oldTimes={observedLocal:$('observedAt').value,observed:p.observed_at,availableLocal:$('availableAt').value,available:p.available_at};set('sourceQuality',p.quality);set('context',p.context);set('comparisonContext',p.measurement_context_key);set('value',p.value);set('qualifier',p.qualifier||'exact');set('absentReason',p.absent_reason);set('encounter',p.encounter_id);set('summary',p.summary);set('relativeDegree',p.relative_degree||'first');set('professionalReference',p.professional_interpretation_reference);$('disclosureAuthorized').checked=!!p.disclosure_authorized;$('needsReview').checked=!!p.needs_review;$('identityVerified').checked=false;$('hasReference').checked=!!p.reference;if(p.assay)for(const [field,id] of Object.entries({name:'assayName',version:'assayVersion',laboratory:'laboratory',specimen:'specimen',method:'assayMethod',lower_quantitation_limit:'loqLow',upper_quantitation_limit:'loqHigh'}))set(id,p.assay[field]);if(p.reference)for(const [field,id] of Object.entries({kind:'referenceKind',lower:'referenceLow',upper:'referenceHigh',source:'referenceSource',population_context:'referencePopulation',applies_to_participant:'referenceApplies'}))set(id,p.reference[field]);if(p.instrument)for(const [field,id] of Object.entries({name:'instrumentName',version:'instrumentVersion',language:'instrumentLanguage',permission_basis:'permissionBasis',administered_by:'instrumentBy'}))set(id,p.instrument[field]);set('effectiveStart',p.effective_start?localTime(p.effective_start):'');set('effectiveEnd',p.effective_end?localTime(p.effective_end):'');formChanged();$('sourceKind').value=p.source.kind;for(const id of ['kind','entryMetric','sourceKind','organization','sourceReference','cohort','sourceSubject'])$(id).disabled=true;$('cancelEdit').hidden=false;$('saveRecord').textContent='Save amendment as revision '+(p.revision+1);$('saveStatus').textContent='Source identity remains immutable. Amendments append a new revision.';}
$('cancelEdit').onclick=()=>{editing=null;pendingId=null;oldTimes={};for(const id of ['kind','entryMetric','sourceKind','organization','sourceReference','cohort','sourceSubject'])$(id).disabled=false;$('cancelEdit').hidden=true;$('saveRecord').textContent='Save verified record';$('saveStatus').textContent='Amendment cancelled.';};
function download(text,type,name){const url=URL.createObjectURL(new Blob([text],{type})),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}function exportAllowed(){return current&&(!current.sensitive_included||confirm('This view includes explicitly disclosed professional genomic summaries. Authorize including them in this local export?'))}
$('export').onclick=()=>{if(exportAllowed())download(JSON.stringify(current,null,2),'application/json','bbc-be-'+(synthetic()?'synthetic-'+profile:mode)+'-evidence.json')};
const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));$('report').onclick=()=>{if(!exportAllowed())return;const d=current,lines=d.records.map(r=>'<tr>'+[r.label,resultText(r.payload),r.payload.source.organization,date(r.payload.observed_at),date(r.payload.available_at),date(r.known_at),r.interval_position||r.payload.quality].map(v=>'<td>'+escapeHTML(v)+'</td>').join('')+'</tr>').join('');const html='<!doctype html><meta charset="utf-8"><title>BBC-BE review report</title><style>body{font:14px/1.5 system-ui;max-width:1200px;margin:40px auto;color:#234}table{border-collapse:collapse;width:100%;font-size:11px}td,th{padding:9px;border:1px solid #ccd;text-align:left}p{max-width:1000px}</style><h1>Brain–Body Context · Review report</h1><p>'+escapeHTML(d.identity.display_name)+(synthetic()?' · SYNTHETIC SCENARIO':'')+'</p><h2>Cognitive session review</h2>'+$('sessionReview').innerHTML+'<h2>All visible health-context records</h2><p>Source-linked observations. No cause, neurological diagnosis, treatment or individual prevention benefit is established.</p><table><tr>'+['Observation','Result','Source','Observed','Available','Received','Context / quality'].map(s=>'<th>'+s+'</th>').join('')+'</tr>'+lines+'</table><h2>Evidence boundaries</h2><ul>'+d.boundaries.map(s=>'<li>'+escapeHTML(s)+'</li>').join('')+'</ul><p>Snapshot SHA-256: '+escapeHTML(d.revision)+'</p>';download(html,'text/html','bbc-be-review-report.html')};
async function refresh(force=false){if(needsParticipant)return;if(busy){pending=pending||force;return}if(document.hidden&&!force)return;busy=true;const token=epoch;try{if(!['active','demo'].includes(mode)||(!synthetic()&&!person))throw Error('Open BBC-BE from a selected BAINP participant, or use a synthetic demo workspace.');dictionary??=await api('dictionary');if(!$('entryMetric').children.length){options('entryMetric',Object.keys(dictionary.metrics),m=>dictionary.metrics[m].label);formChanged()}let path=synthetic()?'demo?'+new URLSearchParams({profile,include_sensitive:$('showSensitive').checked}):base()+'?'+new URLSearchParams({mode,include_sensitive:$('showSensitive').checked,...(asOf?{as_of:asOf}:{})});const d=await api(path);if(token!==epoch)return;if(d.revision!==lastRevision||force){render(d);lastRevision=d.revision}$('export').disabled=false;$('report').disabled=false;$('checked').textContent='Checked '+new Date().toLocaleTimeString();$('status').textContent=synthetic()?'Invented demonstration. No participant data are changed.':'Authorized stored sources refresh every 10 seconds. This does not acquire a wearable signal or lab test.'}catch(error){if(token===epoch){if([401,403,404].includes(error.status)){$('snapshotWorkspace').hidden=true;current=null;lastRevision=''}$('status').textContent=error.message;$('export').disabled=true;$('report').disabled=true;$('checked').textContent='Refresh failed · displayed evidence may be stale'}}finally{busy=false;if(pending||token!==epoch){pending=false;refresh(true)}}}
$('refresh').onclick=()=>refresh(true);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});refresh();setInterval(()=>refresh(),10000);

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
