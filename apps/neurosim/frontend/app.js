'use strict';

const $ = id => document.getElementById(id);
const query = new URLSearchParams(location.search);
const person = query.get('person');
const mode = query.get('mode') || (person ? 'active' : 'demo');
const fictional = mode === 'demo' && !person;
const care = location.pathname === '/careloop';
const scope = new URLSearchParams({mode, ...(person ? {person} : {})});
const labels = {
  request_review:'Record review request', plan_monitoring:'Plan monitoring',
  document_referral:'Document outside referral', plan_followup:'Plan or reschedule follow-up',
  confirm_followup:'Record outside follow-up completion', record_outcome:'Record outside outcome',
  close:'Close documented case', reopen:'Reopen for review', withdraw:'Withdraw consent'
};
const references = new Set(['document_referral','confirm_followup','record_outcome']);
const plans = new Set(['plan_monitoring','plan_followup']);
const inputs = {
  activity_minutes:['Weekly physical activity','min/week','activityValue'],
  sleep_hours:['Sleep duration','h','sleepValue'],
  systolic_mmhg:['Systolic BP','mmHg','bpValue']
};
let baseline = {activity_minutes:210,sleep_hours:7,systolic_mmhg:130};
let selected = null;
let caseEpoch = 0;
let pendingIntake;
let pendingEvent;

function element(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}
function option(value,text) {
  const item = element('option',text);
  item.value = value;
  return item;
}
function anchor(href,text) {
  const link = element('a',text);
  link.href = href;
  link.rel = 'noreferrer';
  return link;
}
const human = value => String(value || '').replaceAll('_',' ');
const stamp = value => new Date(value).toLocaleString();

async function api(path, body) {
  const response = await fetch('/api/prevention/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'Content-Type':'application/json','X-NeuroAccess-Request':'1'},
    ...(body === undefined ? {} : {body:JSON.stringify(body)}), cache:'no-store'
  });
  if (!response.ok) {
    const error = await response.json().catch(()=>({}));
    const detail = typeof error.detail === 'string' ? human(error.detail) : 'Check the entered fields.';
    if (response.status === 401) throw Error('Sign in through BAINP to use this workspace.');
    throw Error(detail + ' (' + response.status + ')');
  }
  return response.json();
}

function scoped(path) { return path + '?' + scope; }
function updateSliders() {
  for (const [key,[,unit,output]] of Object.entries(inputs)) $(output).textContent = $(key).value + ' ' + unit;
}
function resetScenario() {
  for (const [key,value] of Object.entries(baseline)) $(key).value = value;
  updateSliders();
  $('scenarioRows').replaceChildren();
  $('scenarioStatus').textContent = 'Example inputs loaded.';
}
async function education(event) {
  event?.preventDefault();
  $('educationStatus').textContent = 'Reading evidence…';
  $('topics').replaceChildren();
  $('practical').replaceChildren();
  try {
    const preferences = [...$('preferences').querySelectorAll('input:checked')].map(input=>input.value);
    const report = await api(scoped('education'),{preferences});
    $('educationStatus').textContent = report.topics.length
      ? 'Education for a discussion with a qualified professional.'
      : 'No eligible topics are available. Review BBC-BE consent, context and evidence eligibility.';
    for (const item of report.topics) {
      const article = element('article');
      article.append(element('h3',item.title),element('p',item.text),
        element('p','Context source · ' + item.origins.join(', ')),
        anchor(item.reference.url,item.reference.title),
        element('p',item.reference.population),
        element('p','Evidence type · ' + item.evidence_level + ' · Policy ' + item.policy_version));
      $('topics').append(article);
    }
    $('practical').replaceChildren(...report.preferences.map(text=>element('li',text)));
  } catch(error) { $('educationStatus').textContent = error.message; }
}

async function compareScenario(event) {
  event.preventDefault();
  const payload = Object.fromEntries(Object.keys(inputs).map(key=>[key,Number($(key).value)]));
  $('scenarioStatus').textContent = 'Comparing hypothetical inputs…';
  $('scenarioRows').replaceChildren();
  try {
    const result = await api('scenario',payload);
    for (const row of result.rows) {
      const line = element('tr');
      for (const text of [inputs[row.input][0],row.baseline + ' ' + row.unit,
        row.hypothetical + ' ' + row.unit,(row.difference > 0 ? '+' : '') + row.difference + ' ' + row.unit]) {
        line.append(element('td',text));
      }
      $('scenarioRows').append(line);
    }
    $('scenarioStatus').textContent = 'Input differences only. No model executed.';
  } catch(error) { $('scenarioStatus').textContent = error.message; }
}

function updateAction() {
  const action = $('action').value;
  const needsRef = references.has(action), needsDate = plans.has(action);
  $('referenceLabel').hidden = !needsRef;
  $('dueLabel').hidden = !needsDate;
  $('noteLabel').hidden = action === 'withdraw';
  $('reference').required = needsRef;
  $('due').required = needsDate;
  $('note').required = action !== 'withdraw';
  $('actionHint').textContent = action === 'withdraw'
    ? 'Withdrawal hides case details and stops sharing markers with NeuroTwin.'
    : needsRef ? 'Use the reference of an outside document or confirmation you can inspect. The app records your entry locally.'
    : action === 'close' ? 'Close only after documenting the outcome and next steps.' : 'Record the step agreed or requested.';
}

function renderCase(data) {
  selected = data;
  $('caseDetail').replaceChildren();
  $('history').replaceChildren();
  $('event').hidden = !data?.actions.length;
  if (!data) return;
  $('caseDetail').append(element('h3',human(data.state)));
  if (data.state === 'withdrawn') {
    $('caseDetail').append(element('p','Consent withdrawn. Case details are hidden.'));
    return;
  }
  $('caseDetail').append(element('p',data.concern),element('p',human(data.priority)));
  if (data.due_on) $('caseDetail').append(element('p','Planned date · ' + data.due_on));
  $('action').replaceChildren(...data.actions.map(action=>option(action,labels[action])));
  $('note').value = '';
  $('reference').value = '';
  $('due').value = '';
  updateAction();
  $('history').replaceChildren(...data.history.map(event=>{
    const entry = element('li');
    entry.append(element('strong',human(event.state)),element('p',stamp(event.at)));
    if (event.note) entry.append(element('p',event.note));
    if (event.reference) entry.append(element('p','Operator-recorded reference · ' + event.reference));
    if (event.due_on) entry.append(element('p','Planned date · ' + event.due_on));
    return entry;
  }));
}

async function openCase() {
  const token = ++caseEpoch, id = $('caseSelect').value;
  renderCase(null);
  $('eventStatus').textContent = '';
  if (!id) return;
  try {
    const data = await api(scoped('cases/' + id));
    if (token === caseEpoch) renderCase(data);
  } catch(error) { if (token === caseEpoch) $('eventStatus').textContent = error.message; }
}

async function listCases(id = $('caseSelect').value) {
  try {
    const data = await api(scoped('cases'));
    $('caseSelect').replaceChildren(option('','Choose a case'), ...data.cases.map(item =>
      option(item.id,human(item.state) + ' · ' + stamp(item.updated_at) + ' · ' + item.id.slice(0,8))));
    if (data.cases.some(item=>item.id === id)) $('caseSelect').value = id;
    await openCase();
    $('status').textContent = data.cases.length + ' local cases';
  } catch(error) {
    $('caseSelect').replaceChildren(option('','Choose a case'));
    renderCase(null);
    $('status').textContent = error.message;
  }
}

function safetySelection() {
  const signs = [...$('signs').querySelectorAll('input:checked')].map(input=>input.value);
  $('safety').textContent = signs.length ? 'Call your local emergency number now. In India, call 112. Seek help even if symptoms have resolved.' : '';
  return signs;
}
function requestKey(pending, payload) {
  const fingerprint = JSON.stringify(payload);
  return pending?.fingerprint === fingerprint ? pending : {fingerprint,id:crypto.randomUUID()};
}
async function create(event) {
  event.preventDefault();
  const signs = safetySelection();
  if (signs.length) {
    $('intakeStatus').textContent = 'Follow the urgent guidance above. This concern has not been added to the queue.';
    return;
  }
  const values = {category:$('category').value, concern:$('concern').value.trim(), screening:$('screening').value,
    signs, consent:$('consent').checked, share_with_twin:!fictional && $('share').checked};
  pendingIntake = requestKey(pendingIntake,values);
  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    const result = await api(scoped('cases'),{...values,case_id:pendingIntake.id});
    if (!result.case) { $('intakeStatus').textContent = result.safety.text; return; }
    pendingIntake = null;
    $('intake').reset();
    $('intakeStatus').textContent = 'Concern saved locally. Select the saved case to record follow-up. This does not contact a provider or clear an assessment restriction.';
    await listCases(result.case.id);
  } catch(error) { $('intakeStatus').textContent = error.message; }
  finally { if (button) button.disabled = false; }
}
async function addEvent(event) {
  event.preventDefault();
  if (!selected) return;
  const token = caseEpoch, id = selected.id, action = $('action').value;
  if (action === 'withdraw' && !window.confirm('Withdraw this case’s consent and hide its details?')) return;
  const values = {expected_version:selected.version, action,
    note:action === 'withdraw' ? null : $('note').value.trim(),
    reference:references.has(action) ? $('reference').value.trim() : null,
    due_on:plans.has(action) ? $('due').value : null};
  pendingEvent = requestKey(pendingEvent,{id,...values});
  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    await api(scoped('cases/' + id + '/events'),{...values,operation_id:pendingEvent.id});
    pendingEvent = null;
    if (token === caseEpoch) {
      await listCases(id);
      $('eventStatus').textContent = 'Action recorded locally.';
    }
  } catch(error) { if (token === caseEpoch) $('eventStatus').textContent = error.message; }
  finally { if (button) button.disabled = false; }
}

$('title').textContent = care ? 'CareLoop' : 'NeuroSim';
$('modeBadge').textContent = fictional ? 'Fictional workspace' : mode === 'demo' ? 'Demo participant' : 'Active participant · local operator';
$('home').href = '/?' + scope;
$('simLink').href = '/neurosim?' + scope;
$('careLink').href = '/careloop?' + scope;
$('demoLink').href = location.pathname + '?mode=demo';
$('bodyLink').href = '/brain-body?' + scope;
$('graphLink').href = '/neurograph?' + scope;
$('twinLink').hidden = !person;
$('twinLink').href = '/neurotwin?' + new URLSearchParams({...Object.fromEntries(scope), ...(mode === 'demo' ? {profile:'selected'} : {})});
$('sim').hidden = care;
$('scenario').hidden = care;
$('care').hidden = !care;
$('seedDemo').hidden = !fictional;
$('shareLabel').hidden = !person;
$('refresh').onclick = () => care ? listCases() : education();
$('preferences').onsubmit = education;
$('scenarioForm').onsubmit = compareScenario;
$('resetScenario').onclick = resetScenario;
for (const key of Object.keys(inputs)) $(key).oninput = updateSliders;
$('seedDemo').onclick = () => {
  $('category').value = 'daily_function';
  $('concern').value = 'Fictional concern: increasing difficulty organizing everyday activities.';
  $('screening').value = 'none_selected';
};
$('signs').onchange = safetySelection;
$('intake').onsubmit = create;
$('intake').addEventListener('invalid',event=>{
 const names={concern:'Enter a concern of at least five characters.',screening:'Choose an answer under “If you selected no warning signs”.',consent:'Storage consent is required to save this concern.'};
 $('intakeStatus').textContent=names[event.target.id]||'Complete the highlighted required field.';
},true);
$('intakeStatus').setAttribute('tabindex','-1');
new MutationObserver(()=>{if($('intakeStatus').textContent){$('intakeStatus').scrollIntoView({block:'nearest'});}}).observe($('intakeStatus'),{childList:true,subtree:true,characterData:true});
$('caseSelect').onchange = openCase;
$('event').onsubmit = addEvent;
$('action').onchange = updateAction;
$('runModel').onclick = async () => {
  $('runModel').disabled = true;
  $('modelStatus').textContent = 'Selecting fictional topics…';
  $('modelTopics').replaceChildren();
  try {
    const result = await api('demo/model-plan',{});
    $('modelStatus').textContent = human(result.reason);
    $('modelTopics').replaceChildren(...result.claims.map(claim => element('li',claim.title)));
  } catch(error) { $('modelStatus').textContent = error.message; }
  finally { $('runModel').disabled = false; }
};
if (care) listCases();
else {
  resetScenario();
  education();
  api('settings').then(settings=>{
    baseline = settings.scenario_baseline;
    $('planner').hidden = !(fictional && settings.model_demo_configured);
  }).catch(()=>{});
}
