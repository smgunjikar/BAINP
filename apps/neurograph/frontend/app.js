'use strict';

const $ = id => document.getElementById(id);
const query = new URLSearchParams(location.search);
const person = query.get('person');
const mode = query.get('mode') || (person ? 'active' : 'demo');
const params = new URLSearchParams({mode, ...(person ? {person} : {})});
const types = {
  direct_observation: 'Direct observation', clinical_context: 'Clinical context',
  research_association: 'Research association', clinical_guidance: 'Clinical guidance',
  hypothesis: 'Hypothesis', unknown: 'Unknown'
};
const claimTypes = {
  measurement: 'Recorded measurement', comparison: 'Descriptive comparison', context: 'Clinical context',
  association: 'Research association', guidance: 'Population guidance', hypothesis: 'Research question',
  uncertainty: 'Unknown mechanism', diagnosis: 'Diagnosis', causal_effect: 'Causal effect',
  treatment: 'Treatment instruction', clinical_prediction: 'Clinical prediction'
};
let report;
let evaluating = false;
let refreshRevision = 0;

function element(tag, text, cls) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (cls) item.className = cls;
  return item;
}

function option(value, label) {
  const item = element('option', label);
  item.value = value;
  return item;
}

function link(href, text) {
  const a = element('a', text);
  a.href = href;
  a.rel = 'noreferrer';
  return a;
}

function label(code) {
  return String(code || '').replaceAll('_', ' ').toLowerCase();
}

async function api(path, body) {
  const response = await fetch('/api/neuro-evidence/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'Content-Type': 'application/json', 'X-NeuroAccess-Request': '1'},
    ...(body === undefined ? {} : {body: JSON.stringify(body)}),
    cache: 'no-store'
  });
  if (!response.ok) {
    if (response.status === 401) throw Error('Sign in through BAINP to open the evidence workspace.');
    if (response.status === 409) throw Error('Evidence changed. Refresh the report before evaluating again.');
    throw Error('Evidence service request failed (' + response.status + '). Check the participant and mode.');
  }
  return response.json();
}

function showResult(target, result) {
  const status = element('p', result.state.toUpperCase() + ' · ' + label(result.reason), 'verdict ' + result.state);
  const items = [status, element('p', result.text)];
  if (result.evidence_ids.length) items.push(element('p', 'Source evidence: ' + result.evidence_ids.join(', '), 'small'));
  target.replaceChildren(...items);
}

function fillMeasurement() {
  const selected = report?.nodes.find(item => item.id === $('source').value);
  if (selected?.claim === 'measurement' && selected.eligible) {
    $('value').value = selected.value;
    $('unit').value = selected.unit;
  } else {
    $('value').value = '';
    $('unit').value = '';
  }
}

function configureClaim() {
  const numeric = $('claim').value === 'measurement';
  $('valueField').hidden = !numeric;
  $('unitField').hidden = !numeric;
}

function renderCards() {
  const list = $('evidenceList');
  list.replaceChildren();
  const filtered = report.nodes.filter(node => !$('filter').value || node.type === $('filter').value);
  const verdicts = new Map(report.claims.map(item => [item.id, item]));
  $('count').textContent = filtered.length + ' evidence entries';
  for (const node of filtered) {
    const result = verdicts.get('claim-' + node.id);
    const card = element('article');
    card.append(element('span', types[node.type], 'badge'), element('h3', node.title));
    const verdict = element('div');
    showResult(verdict, result);
    card.append(verdict, element('p', node.source, 'small'));
    if (node.observed_at) card.append(element('p', 'Observed ' + new Date(node.observed_at).toLocaleString(), 'small'));
    if (node.source_ids?.length) card.append(element('p', 'Source records: ' + node.source_ids.join(', '), 'small'));
    if (node.url) card.append(link(node.url, 'Open original source'));
    const use = element('button', 'Review this evidence');
    use.onclick = () => {
      $('source').value = node.id;
      $('claim').value = node.claim;
      fillMeasurement();
      configureClaim();
      $('guard').scrollIntoView?.();
      $('claim').focus();
    };
    card.append(use);
    list.append(card);
  }
  if (!filtered.length) list.append(element('p', 'No evidence in this category.'));
}

function render() {
  $('mode').textContent = report.synthetic ? 'Fictional demonstration' : mode === 'demo' ? 'Demo participant workspace' : 'Authorized participant workspace';
  $('source').replaceChildren(option('', 'Choose evidence'), ...report.nodes.map(node => option(node.id, node.title + ' · ' + node.id)));
  $('claim').value = 'measurement';
  fillMeasurement();
  configureClaim();
  renderCards();
  $('coverageState').textContent = report.synthetic ? 'This is a fictional case.' : report.coverage.length
    ? 'These statuses describe the available participant sources and their authorization.'
    : 'Source inventory unavailable. Open the participant BBC-BE workspace to review consent and connections.';
  $('coverage').replaceChildren(...report.coverage.map(item => {
    const line = element('li', item.name + ' · ' + label(item.state) + (item.count == null ? '' : ' · ' + item.count));
    if (item.href) line.append(' ', link(item.href, 'Open workspace'));
    return line;
  }));
  $('limits').replaceChildren(...report.limits.map(item => element('li', item)));
  $('policy').textContent = report.policy_version + ' · snapshot ' + report.revision.slice(0, 12);
  $('model').hidden = !report.synthetic;
  $('modelButton').disabled = !report.demo_model_configured;
  $('modelResult').textContent = report.demo_model_configured ? '' : 'Local model is disabled. The deterministic report is available above.';
  $('falseValue').hidden = !report.synthetic;
  $('diagnosis').hidden = !report.synthetic;
  $('export').disabled = false;
  $('report').hidden = false;
}

async function refresh() {
  const token = ++refreshRevision;
  report = null;
  $('report').hidden = true;
  $('export').disabled = true;
  $('decision').replaceChildren();
  $('status').textContent = 'Reading evidence…';
  try {
    const fresh = await api('report?' + params);
    if (token !== refreshRevision) return;
    report = fresh;
    render();
    $('status').textContent = 'Evidence snapshot loaded.';
  } catch (error) {
    if (token === refreshRevision) $('status').textContent = error.message;
  }
}

async function evaluate(event) {
  event?.preventDefault();
  if (!report || evaluating) return;
  evaluating = true;
  const token = refreshRevision;
  $('evaluate').disabled = true;
  const body = {revision: report.revision, claim: $('claim').value, evidence_id: $('source').value || null};
  if (body.claim === 'measurement') {
    body.value = $('value').value === '' ? null : Number($('value').value);
    body.unit = $('unit').value || null;
  }
  try {
    const result = await api('evaluate?' + params, body);
    if (token === refreshRevision) showResult($('decision'), result);
  } catch (error) {
    if (token === refreshRevision) $('decision').textContent = error.message;
  } finally {
    evaluating = false;
    $('evaluate').disabled = false;
  }
}

$('back').href = '/?' + params;
for (const [value, text] of Object.entries(types)) $('filter').append(option(value, text));
for (const [value, text] of Object.entries(claimTypes)) $('claim').append(option(value, text));
$('filter').onchange = renderCards;
$('claim').onchange = configureClaim;
$('source').onchange = fillMeasurement;
$('refresh').onclick = refresh;
$('proposal').onsubmit = evaluate;
$('falseValue').onclick = () => {
  const node = report?.nodes.find(item => item.claim === 'measurement' && item.eligible);
  if (!node) return;
  $('claim').value = 'measurement';
  $('source').value = node.id;
  fillMeasurement();
  configureClaim();
  $('value').value = node.value + 10;
  evaluate();
};
$('diagnosis').onclick = () => {
  $('claim').value = 'diagnosis';
  configureClaim();
  evaluate();
};
$('modelButton').onclick = async () => {
  const token = refreshRevision;
  $('modelButton').disabled = true;
  try {
    const result = await api('demo/model-plan', {});
    if (token !== refreshRevision) return;
    $('modelResult').replaceChildren(element('p', result.state.toUpperCase() + ' · ' + label(result.reason)),
      ...result.claims.map(item => element('p', item.text)));
  } catch (error) {
    if (token === refreshRevision) $('modelResult').textContent = error.message;
  } finally {
    if (token === refreshRevision) $('modelButton').disabled = !report?.demo_model_configured;
  }
};
$('export').onclick = async () => {
  if (!report) return;
  const token = refreshRevision;
  $('export').disabled = true;
  try {
    const data = await api('export?' + params, {revision: report.revision});
    if (token !== refreshRevision) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
    const a = link(url, 'Download');
    a.download = 'bainp-reviewed-evidence.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    if (token === refreshRevision) $('status').textContent = error.message;
  } finally {
    if (token === refreshRevision) $('export').disabled = false;
  }
};
$('urgent').addEventListener('change', () => {
  const selected = $('urgent').querySelector('input:checked');
  $('safetyStatus').textContent = selected
    ? 'Call your local emergency number now. In India, call 112.'
    : 'No warning sign selected. This checklist cannot rule out an emergency.';
});
refresh();

$('careloopLink').href = '/careloop?' + params;
