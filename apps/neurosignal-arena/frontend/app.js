'use strict';

const $ = id=>document.getElementById(id);
const platform = location.pathname === '/platform-core';
let report;
let selected;
let epoch = 0;
let busy = false;
let pendingId;

function el(tag,text,cls) {
  const item=document.createElement(tag);
  if(text!==undefined)item.textContent=text;
  if(cls)item.className=cls;
  return item;
}
function option(value,text) {
  const item=el('option',text);
  item.value=value;
  return item;
}
function row(values) {
  const tr=el('tr');
  for(const value of values)tr.append(el('td',value));
  return tr;
}
function human(value) { return String(value).replaceAll('_',' '); }
function format(value) { return Number(value).toFixed(3); }

async function api(path,body) {
  const response=await fetch('/api/platform/v1/'+path,{
    method:body===undefined?'GET':'POST',
    headers:{'Content-Type':'application/json','X-NeuroAccess-Request':'1'},
    ...(body===undefined?{}:{body:JSON.stringify(body)}),cache:'no-store'
  });
  if(!response.ok) {
    const detail=await response.json().catch(()=>({}));
    if(response.status===401)throw Error('Sign in through BAINP to open this workspace.');
    throw Error(typeof detail.detail==='string'?human(detail.detail):'Platform request failed ('+response.status+').');
  }
  return response.json();
}

function download(data,filename) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const link=el('a');
  link.href=url;
  link.download=filename;
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function arena(data) {
  report=data.oasis2;
  $('protocol').textContent=data.protocol+' · '+data.protocol_sha256;
  $('oasisDetails').textContent=report.participants+' participants · '+report.outcome;
  $('oasisRows').replaceChildren(
    row(['Persistence',format(report.persistence.MAE),format(report.persistence.RMSE)]),
    row(['Ridge regression',format(report.ridge.MAE),format(report.ridge.RMSE)]));
  const interval=report.bootstrap_95_percentile_intervals.ridge_minus_persistence_MAE;
  $('oasisInterval').textContent='Ridge minus persistence MAE · 95% paired interval '+interval.map(format).join(' to ')+' MMSE points.';
  $('oasisProvenance').replaceChildren(...[report.evaluation,report.uncertainty_note,...report.limitations,
    'Analysis plan SHA-256 · '+report.analysis_plan_sha256,'Script SHA-256 · '+report.script_sha256,
    'Runtime · '+Object.entries(report.versions).map(([key,value])=>key+' '+value).join(', ')].map(text=>el('li',text)));
  $('datasets').replaceChildren(...data.datasets.map(item=>el('li',item.id+' · '+item.scope+' · '+item.permission)));
  $('exportOasis').disabled=false;
  $('arena').hidden=false;
}

function operations(data) {
  const cards=[
    ['Storage',data.storage],['Identity',data.identity],['API uptime',Math.round(data.uptime_seconds)+' s'],
    ['Requests observed',Object.values(data.requests).reduce((a,b)=>a+b,0)],
    ['Last API request',data.last_request_ms==null?'—':data.last_request_ms+' ms'],
    ['Pending jobs',(data.jobs.queued||0)+(data.jobs.running||0)],
    ['API responses',Object.entries(data.requests).map(([key,count])=>key+' '+count).join(' · ')||'—']
  ];
  $('health').replaceChildren(...cards.map(([name,value])=>{
    const card=el('article');
    card.append(el('p',name),el('strong',value));
    return card;
  }));
  const model=data.model_registry;
  $('model').textContent=model.module+' · '+human(model.state)
    +(model.version?' · '+model.version:'')+(model.reasons.length?' · '+model.reasons.map(human).join(', '):'');
  $('modules').replaceChildren(...data.modules.map(item=>{
    const line=el('li',item.name+' · '+(item.source_present?'Source found':'Source check unavailable'));
    if(item.local_route) {
      const link=el('a','Open demo workspace');
      link.href=item.local_route+(item.local_route==='/'?'':'?mode=demo');
      line.append(' ',link);
    }
    return line;
  }));
  $('platform').hidden=false;
}

function renderJob(job) {
  selected=job;
  $('jobDetail').hidden=!job;
  if(!job)return;
  $('jobState').textContent=human(job.state)+' · '+job.attempts+' attempt(s)'
    +(job.error_code?' · '+human(job.error_code):'')
    +(job.result?' · '+job.result.passed+'/'+job.result.total+' cases passed':'');
  $('runSelected').disabled=busy||!['queued','running'].includes(job.state);
  $('cancel').disabled=busy||job.state!=='queued';
  $('exportJob').disabled=!job.result;
  $('jobEvents').replaceChildren(...job.events.map(event=>el('li',human(event.action)+' · '+new Date(event.at).toLocaleString())));
  $('caseTable').hidden=!job.result;
  $('caseRows').replaceChildren(...(job.result?.cases||[]).map(item=>{
    const tr=row([human(item.id.replaceAll('-','_')),item.expected,item.actual,item.passed?'Pass':'Fail']);
    tr.lastChild.className=item.passed?'pass':'fail';
    return tr;
  }));
}

async function detail() {
  const token=++epoch,id=$('jobSelect').value;
  renderJob(null);
  if(!id)return;
  try {
    const job=await api('jobs/'+id);
    if(token===epoch)renderJob(job);
  } catch(error) {
    if(token===epoch)$('jobStatus').textContent=error.message;
  }
}

async function jobs(id=$('jobSelect').value) {
  const data=await api('jobs');
  $('jobSelect').replaceChildren(option('','Choose a job'),...data.jobs.map(job=>
    option(job.id,job.id.slice(0,8)+' · '+human(job.state)+' · '+new Date(job.updated_at).toLocaleString())));
  if(data.jobs.some(job=>job.id===id))$('jobSelect').value=id;
  await detail();
  $('jobs').hidden=false;
}

async function refresh() {
  $('status').textContent='Reading workspace…';
  try {
    if(platform) {
      const [data,catalog]=await Promise.all([api('status'),api('arena')]);
      operations(data);
      $('protocol').textContent=catalog.protocol+' · '+catalog.protocol_sha256;
    } else arena(await api('arena'));
    await jobs();
    $('status').textContent='Workspace ready.';
  } catch(error) {
    $('arena').hidden=true;
    $('platform').hidden=true;
    $('jobs').hidden=true;
    $('status').textContent=error.message;
  }
}

async function action(operation) {
  if(busy)return;
  busy=true;
  for(const id of ['run','queue','next','runSelected','cancel'])$(id).disabled=true;
  $('jobStatus').textContent='Working…';
  try {
    const id=await operation();
    await jobs(id||$('jobSelect').value);
    $('jobStatus').textContent=id?'Job state updated.':'No queued job to process.';
  } catch(error) { $('jobStatus').textContent=error.message; }
  finally {
    busy=false;
    for(const id of ['run','queue','next'])$(id).disabled=false;
    if(selected)renderJob(selected);
  }
}
async function create(run) {
  pendingId ||= crypto.randomUUID();
  const job=await api('jobs',{job_id:pendingId,kind:'engineering_v1'});
  if(run)await api('jobs/'+job.id+'/run',{});
  pendingId=null;
  return job.id;
}
$('title').textContent=platform?'Platform Core':'NeuroSignal ARENA';
$('description').textContent=platform?'Inspect the local service, model review status, and benchmark job history.':'Run a fixed safety suite and review a measured OASIS-2 baseline comparison.';
$('refresh').onclick=refresh;
$('jobSelect').onchange=detail;
$('run').onclick=()=>action(()=>create(true));
$('queue').onclick=()=>action(()=>create(false));
$('next').onclick=()=>action(async()=> (await api('worker/run-next',{})).job?.id);
$('runSelected').onclick=()=>action(async()=> (await api('jobs/'+selected.id+'/run',{})).id);
$('cancel').onclick=()=>action(async()=> (await api('jobs/'+selected.id+'/cancel',{})).id);
$('exportJob').onclick=()=>{if(selected?.result)download(selected.result,'arena-engineering-report.json');};
$('exportOasis').onclick=()=>{if(report)download(report,'arena-oasis2-aggregate.json');};
refresh();
