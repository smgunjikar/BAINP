'use strict';
const q = new URLSearchParams(location.search);
const mode = q.get('mode') === 'demo' ? 'demo' : 'active';
const pid = q.get('person') || '';
let workspace = null, busy = false, expiryTimer = null;
const $ = id => document.getElementById(id);
const node = (tag, value, className) => {
  const e = document.createElement(tag);
  if (value !== undefined) e.textContent = value;
  if (className) e.className = className;
  return e;
};
const titles = {baseline:'Baseline assessment',reassessment:'Assessment offer',repeat:'Quality correction before repeat',targeted:'Domain clarification',monitor:'Continue monitoring',professional_review:'Request professional review',urgent_guidance:'Urgent safety guidance',abstain:'Assessment on hold'};
const scoped = path => path + '?' + new URLSearchParams({mode,...(pid ? {person:pid} : {})});
function link(label,path){const a=node('a',label);a.href=scoped(path);return a;}
function message(value,error=false){$('message').textContent=value;$('message').classList.toggle('error',error);}
async function api(path,body){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try {
    const r=await fetch(path,{signal:controller.signal,method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-NeuroAccess-Request':'1'},...(body?{body:JSON.stringify(body)}:{})});
    const data=await r.json();
    if(!r.ok){const error=Error(typeof data.detail==='string'?data.detail:'Request could not be completed');error.status=r.status;throw error;}
    return data;
  } finally {clearTimeout(timer);}
}
function exportDecision(d){
  const url=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json'}));
  const a=node('a');a.href=url;a.download='NeuroQuest-decision.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function facts(entries){const dl=node('dl',undefined,'facts');for(const [label,value] of entries){dl.append(node('dt',label),node('dd',String(value ?? 'Not available')));}return dl;}
function evidence(d,record){
  const details=node('details',undefined,'evidence');details.append(node('summary','Decision evidence'));
  details.append(facts([['Expires',d.expires_at ? new Date(d.expires_at).toLocaleString() : 'Legacy decision'],['Policy',d.policy],['Recorded',new Date(d.selected_at).toLocaleString()],['Task selection',d.task_ids?.join(', ')||'No executable task selected'],['Source references',d.evidence?.length||0],['Integrity',record ? (record.integrity_ok?'Stored hash matches':'Integrity could not be verified') : 'Decision saved; hash available in export']]));
  details.append(node('p',d.comparison||'Source comparison is not established.','muted'));
  if(d.uncertainty?.length)details.append(node('p',d.uncertainty.join(' '),'muted'));
  const button=node('button','Download full evidence JSON','secondary');button.type='button';button.addEventListener('click',()=>exportDecision(d));details.append(button);
  return details;
}
function showDecision(d,record){
  clearTimeout(expiryTimer);
  const current=record?.lifecycle==='current' && record.integrity_ok && Date.parse(d.expires_at)>Date.now();
  const root=$('result'),urgent=d.action==='urgent_guidance';
  root.replaceChildren(node('span',urgent?'SAFETY GUIDANCE':!current?'HISTORICAL · RE-EVALUATE':d.executable?'ASSESSMENT OFFER':'NEXT ACTION','badge'),node('h2',titles[d.action]||'Review next action'),node('p',d.reason));
  root.closest('section').classList.toggle('urgent',urgent);
  root.append(node('p',urgent?'Routine assessment is not offered on this pathway.':d.executable?'Native device checks, preparation and scoring remain required.':'No cognitive assessment is launched by this recommendation.','outcome'));
  if(urgent){
    const guidance=node('div',undefined,'guidance');guidance.setAttribute('role','alert');guidance.append(node('h3','NeuroGuard guidance'),node('p',d.guidance?.text||'Open existing NeuroGuard safety guidance.'));root.append(guidance);
    const sources=d.guidance?.sources||[];
    for(const source of sources){try{const u=new URL(source.url);if(u.protocol!=='https:')continue;const a=node('a',source.label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.className='source-link';root.append(a);}catch{}}
    root.append(link('Open NeuroGuard','/neuroguard'));
  }else if(d.executable && current){root.append(link('Continue in NeuroContinuum →','/neurocontinuum'));}
  else if(d.action==='monitor'){root.append(link('Open monitoring history','/neurotwin'));}
  else if(d.action==='abstain'){root.append(link('Review consent and access','/neurocontinuum'));}
  if(!urgent)root.append(link('Open CareLoop review','/careloop'));
  if(!current)root.append(node('p','This saved decision cannot be used to continue. Evaluate the current context first.','outcome'));
  if(d.quality_issues?.length){const list=node('ul');for(const issue of d.quality_issues)list.append(node('li',issue.task+': '+(issue.flags?.join(', ')||'No detailed quality flag supplied by the source')+' · source '+(issue.source_id||'unavailable')));root.append(list);}
  if(current)expiryTimer=setTimeout(invalidateResult,Math.max(0,Date.parse(d.expires_at)-Date.now()));
  if(d.next_eligible_at)root.append(node('p','Engineering cooldown ends '+new Date(d.next_eligible_at).toLocaleString()+'. Keep any existing clinical follow-up plan.','muted'));
  root.append(evidence(d,record));
}
function renderHistory(records){
  $('history').replaceChildren();
  if(!records.length){$('history').append(node('p','No decision history is available under the current permissions.','muted'));return;}
  for(const record of records){const d=record.decision,item=node('details',undefined,'history-item');item.append(node('summary',(record.lifecycle==='current'?'Current · ':'Historical · ')+(titles[d.action]||d.action)+' · '+new Date(record.created_at).toLocaleString()));item.append(node('p',d.reason),node('p',record.integrity_ok?'Stored evidence hash matches.':'Evidence integrity check failed.','muted'),evidence(d,record));$('history').append(item);}
}
function updateIntent(){
  const urgent=Boolean($('sign').value),review=$('functional').checked;
  for(const input of $('decision-form').querySelectorAll('input,select'))input.disabled=busy;
  $('refresh').disabled=busy;
  $('checkin').required=!urgent&&!review;
  $('checkin').disabled=busy||urgent||review;
  $('domain').disabled=busy||urgent||review;
  $('corrected').disabled=busy||urgent||review;
  $('run').textContent=urgent?'Get safety guidance →':review?'Record review recommendation →':'Evaluate next action →';
  $('run').disabled=busy||!pid||!workspace?.consent.enabled;
  $('safety-notice').hidden=!urgent;
}
async function load(){
  const selected=$('checkin').value;
  const people=await api('/api/participants?mode='+mode);
  $('participant').replaceChildren(new Option('Select participant',''));
  for(const p of people.items||[])$('participant').add(new Option(p.profile.display_name,p.id));
  if(!pid){message('Select an existing participant. '+mode.toUpperCase()+' records stay separate.');updateIntent();return;}
  workspace=await api('/api/neuroquest/v1/participants/'+pid+'?mode='+mode);
  if(![...$('participant').options].some(o=>o.value===pid))$('participant').add(new Option(workspace.name,pid));
  $('participant').value=pid;
  $('identity').textContent=workspace.name+' · '+mode.toUpperCase();
  $('checkin').replaceChildren(new Option('Select completed check-in',''));
  for(const c of workspace.checkins.filter(c=>c.status==='completed'))$('checkin').add(new Option(new Date(c.created_at).toLocaleString(),c.id));
  if([...$('checkin').options].some(o=>o.value===selected))$('checkin').value=selected;
  else if(workspace.checkins.filter(c=>c.status==='completed').length===1)$('checkin').selectedIndex=1;
  message(workspace.consent.enabled?'Review current concerns, then evaluate. Saved decisions remain available below.':'Enable applicable permissions in NeuroContinuum → Consent & access. NeuroGuard guidance is always accessible from navigation.');
  renderHistory(workspace.decisions);
  if(workspace.decisions.length){const r=workspace.decisions[0];showDecision(r.decision,r);}
  else $('result').replaceChildren(node('h2','Evidence before action.'),node('p','Evaluate current context to record an explained recommendation.'));
  $('catalogue').replaceChildren(node('p','Existing core research battery · '+workspace.registry.core.length+' tasks. Native task ordering and preparation remain authoritative.'),facts([['Protocol',workspace.registry.protocol],['Isolated task execution',workspace.registry.single_task_execution?'Available':'Unavailable in current native contract']]));
  updateIntent();
}
function fail(error){invalidateResult();message(error.name==='AbortError'?'The request timed out. Its save status is uncertain. Retry the same inputs to recover the original operation.':error.status===401?'Sign in through the BAINP main page, then return.':'Unable to complete: '+error.message+'. No success is inferred.',true);}
$('nav').append(link('BAINP main page','/'),link('NeuroContinuum','/neurocontinuum'),link('NeuroCognition X','/cognition-dashboard'),link('NeuroTwin X','/neurotwin'),link('NeuroGuard','/neuroguard'),link('CareLoop','/careloop'));
$('home').href=scoped('/');$('links').append(link('NeuroGuard ↗','/neuroguard'),link('CareLoop ↗','/careloop'));
$('participant').addEventListener('change',()=>{location.href='/neuroquest?'+new URLSearchParams({mode,person:$('participant').value});});
$('refresh').addEventListener('click',()=>load().catch(fail));
$('decision-form').addEventListener('change',()=>{invalidateResult();updateIntent();});
$('decision-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!pid||busy)return;
  const urgent=Boolean($('sign').value),review=$('functional').checked;
  const body={checkin_id:urgent||review?null:$('checkin').value,concerns_checked:$('checked').checked,functional_concern:review,pause_requested:$('pause').checked,quality_problem_addressed:!urgent&&!review&&$('corrected').checked,target_domain:urgent||review?'none':$('domain').value,signs:urgent?[$('sign').value]:[]};
  const key='nq-pending-'+mode+'-'+pid;
  let saved;try{saved=JSON.parse(sessionStorage.getItem(key)||'null');}catch{saved=null;}
  const pending=saved&&JSON.stringify(saved.body)===JSON.stringify(body)?saved:{body,operation_id:crypto.randomUUID()};
  sessionStorage.setItem(key,JSON.stringify(pending));busy=true;updateIntent();
  try{const result=await api('/api/neuroquest/v1/participants/'+pid+'/recommendations?mode='+mode,{...body,operation_id:pending.operation_id});sessionStorage.removeItem(key);await load();message(urgent?'Safety override recorded. Existing open monitoring workflows are blocked for safety review.':'Decision recorded. NeuroContinuum rechecks permissions and source data before acting.');}
  catch(error){if(error.status&&error.status<500)sessionStorage.removeItem(key);fail(error);}
  finally{busy=false;updateIntent();}
});
load().catch(fail);

function invalidateResult(){
  clearTimeout(expiryTimer);
  const root=$('result');
  root.replaceChildren(node('span','RE-EVALUATION REQUIRED','badge'),node('h2','Check your current next step'),node('p','Inputs changed or this permission expired. Evaluate again before continuing.'));
  root.closest('section').classList.remove('urgent');
  if($('sign').value){const guidance=node('p','Stop routine testing and seek emergency help using your local emergency number. This application has not contacted emergency services.','guidance');guidance.setAttribute('role','alert');root.append(guidance);}
}
