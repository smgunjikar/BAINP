<!-- BAINP_NS_REDESIGN_V1 -->
"use strict";
const $ = (id) => document.getElementById(id);
const query = new URLSearchParams(location.search);
const mode = query.get('mode') || 'active';
const person = query.get('person');
let paused = false;
let tick = 0;
let loading = false;
let currentSeries = 'steps';
let currentTab = 'live';

const metrics = [
  ['heart_rate', 'Resting heart rate', 'bpm', '❤'],
  ['sleep_duration', 'Sleep duration', 'h', '🛏'],
  ['steps', 'Daily activity', 'steps', '🚶'],
  ['movement_rms', 'Movement amplitude', 'g', '🧍'],
];

const participantLabel = person || 'No participant selected';
$('participantField').value = participantLabel;
$('connect').onclick = () => { $('options').hidden = !$('options').hidden; };
$('refreshNow').onclick = () => refresh(true);
$('pause').hidden = mode !== 'demo';
$('pause').onclick = () => {
  paused = !paused;
  $('pause').textContent = paused ? 'Resume demo stream' : 'Pause demo stream';
  refresh(true);
};
$('periodSelect').onchange = () => refresh(true);
document.querySelectorAll('.ns-tab').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.ns-tab').forEach((item) => item.classList.remove('is-active'));
    button.classList.add('is-active');
    currentTab = button.dataset.tab;
    applyTabState();
  });
});
document.querySelectorAll('.ns-segmented button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.ns-segmented button').forEach((item) => item.classList.remove('is-active'));
    button.classList.add('is-active');
    currentSeries = button.dataset.series;
    refresh(true);
  });
});

function formatNumber(value, digits = 0) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}
function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
function average(values) { return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null; }
function latestUsable(items, metric) {
  return items.filter((x) => x.metric === metric && x.quality === 'usable').at(-1) || null;
}
function usableSeries(items, metric) {
  const days = Number($('periodSelect').value || '30');
  const cutoff = Date.now() - days * 86400000;
  return items.filter((x) => x.metric === metric && x.quality === 'usable' && Date.parse(x.timestamp) >= cutoff);
}
function groupDaily(items) {
  const map = new Map();
  items.forEach((item) => {
    const key = new Date(item.timestamp).toISOString().slice(0, 10);
    const bucket = map.get(key) || [];
    bucket.push(item.value);
    map.set(key, bucket);
  });
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([date, values]) => ({
    date,
    value: average(values),
  }));
}
function demo() {
  const now = Date.now();
  const items = [];
  for (let d = 35; d >= 0; d--) {
    const wave = Math.sin((d + tick / 2) * 0.55);
    const wave2 = Math.cos((d + tick / 3) * 0.4);
    items.push({ metric: 'heart_rate', unit: 'bpm', value: 63 + wave * 4 + (d === 0 ? tick % 3 : 0), timestamp: new Date(now - d * 86400000).toISOString(), quality: 'usable', device: 'Simulated research wearable', method: 'simulation', protocol: 'demo-dashboard-v3' });
    items.push({ metric: 'sleep_duration', unit: 'h', value: 7.2 + wave2 * 0.45, timestamp: new Date(now - d * 86400000).toISOString(), quality: 'usable', device: 'Simulated research wearable', method: 'simulation', protocol: 'demo-dashboard-v3' });
    items.push({ metric: 'steps', unit: 'steps', value: 7200 + Math.round(wave * 1600 + wave2 * 700), timestamp: new Date(now - d * 86400000).toISOString(), quality: 'usable', device: 'Simulated research wearable', method: 'simulation', protocol: 'demo-dashboard-v3' });
    items.push({ metric: 'movement_rms', unit: 'g', value: 0.042 + wave2 * 0.006, timestamp: new Date(now - d * 86400000).toISOString(), quality: 'usable', device: 'Simulated research wearable', method: 'simulation', protocol: 'demo-dashboard-v3' });
  }
  return { items, analysis: { streams: [
    { metric: 'activity', state: 'stable_with_expected_variation', baseline_days: 21, device: 'Simulated research wearable' },
    { metric: 'sleep', state: 'adequate_duration_pattern', baseline_days: 21, device: 'Simulated research wearable' },
  ] } };
}
function setConnectionState(items) {
  const recent = items.at(-1);
  const hasItems = items.length > 0;
  if (mode === 'demo') {
    $('device').textContent = 'Simulated research wearable';
    $('transport').textContent = paused ? 'Simulation paused' : 'Demo stream · updates every 5 seconds';
    $('connectionBadge').textContent = paused ? 'Demo paused' : 'Demo active';
  } else if (hasItems) {
    $('device').textContent = recent.device || 'Stored source available';
    $('transport').textContent = recent.method ? `Source method: ${recent.method}` : 'Stored observations available';
    $('connectionBadge').textContent = 'Stored data available';
  } else {
    $('device').textContent = 'No device connected';
    $('transport').textContent = 'Awaiting a supported adapter';
    $('connectionBadge').textContent = 'Awaiting data';
  }
}
function renderMetricCards(items) {
  const host = $('metricCards');
  host.replaceChildren();
  metrics.forEach(([metric, label, unit, icon]) => {
    const series = usableSeries(items, metric);
    const latest = series.at(-1) || null;
    const previous = series.length > 1 ? series.at(-2).value : null;
    let deltaText = 'Awaiting more observations';
    if (latest && previous != null) {
      const delta = latest.value - previous;
      const sign = delta > 0 ? '+' : '';
      deltaText = `${sign}${metric === 'movement_rms' ? delta.toFixed(3) : metric === 'sleep_duration' ? delta.toFixed(2) : Math.round(delta)} vs previous sample`;
    }
    const card = document.createElement('article');
    card.className = 'ns-toolbar-card ns-metric-card';
    const value = latest ? (metric === 'steps' ? formatNumber(Math.round(latest.value)) : metric === 'movement_rms' ? latest.value.toFixed(3) : latest.value.toFixed(metric === 'sleep_duration' ? 2 : 1)) : '—';
    card.innerHTML = `
      <div class="ns-metric-icon">${icon}</div>
      <div>
        <div class="ns-metric-label">${label}</div>
        <div class="ns-metric-value">${value}${latest ? `<span class="ns-unit"> ${unit}</span>` : ''}</div>
        <div class="ns-metric-sub">${deltaText}</div>
      </div>
      <canvas class="ns-spark" width="92" height="40" aria-hidden="true"></canvas>`;
    host.append(card);
    drawSparkline(card.querySelector('canvas'), series.map((x) => x.value), metric === 'steps' ? '#39c874' : metric === 'heart_rate' ? '#88bf91' : metric === 'sleep_duration' ? '#a881ff' : '#54c887');
  });
}
function drawSparkline(canvas, values, stroke) {
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (values.length < 2) return;
  const lo = Math.min(...values), hi = Math.max(...values), range = hi - lo || 1;
  ctx.lineWidth = 2.2;
  ctx.strokeStyle = stroke;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = 6 + index * ((canvas.width - 12) / (values.length - 1));
    const y = canvas.height - 6 - ((value - lo) / range) * (canvas.height - 12);
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}
function drawBarLineChart(canvas, daily, color, label) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (!daily.length) {
    ctx.fillStyle = '#5f6f69';
    ctx.font = '14px sans-serif';
    ctx.fillText('No observations in the selected period.', 18, 28);
    return;
  }
  const chart = { left: 58, top: 18, width: w - 76, height: h - 52 };
  const vals = daily.map((d) => d.value);
  const max = Math.max(...vals) * 1.12;
  ctx.strokeStyle = '#d8e6de';
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) {
    const y = chart.top + i * (chart.height / 4);
    ctx.beginPath(); ctx.moveTo(chart.left, y); ctx.lineTo(chart.left + chart.width, y); ctx.stroke();
  }
  ctx.fillStyle = '#6a7b74'; ctx.font = '12px sans-serif';
  const step = daily.length > 10 ? Math.ceil(daily.length / 7) : 1;
  daily.forEach((point, idx) => {
    if (idx % step === 0 || idx === daily.length - 1) {
      const x = chart.left + idx * (chart.width / Math.max(1, daily.length - 1));
      ctx.fillText(point.date.slice(5), x - 14, chart.top + chart.height + 18);
    }
  });
  if (currentSeries === 'steps') {
    const barWidth = Math.max(10, chart.width / daily.length - 10);
    daily.forEach((point, idx) => {
      const x = chart.left + idx * (chart.width / daily.length) + 6;
      const barH = (point.value / max) * (chart.height - 8);
      const y = chart.top + chart.height - barH;
      const gradient = ctx.createLinearGradient(0, y, 0, chart.top + chart.height);
      gradient.addColorStop(0, 'rgba(48, 199, 115, .95)');
      gradient.addColorStop(1, 'rgba(48, 199, 115, .18)');
      ctx.fillStyle = gradient;
      roundRect(ctx, x, y, barWidth, barH, 10, true, false);
    });
  } else {
    ctx.lineWidth = 3; ctx.strokeStyle = color; ctx.beginPath();
    daily.forEach((point, idx) => {
      const x = chart.left + idx * (chart.width / Math.max(1, daily.length - 1));
      const y = chart.top + chart.height - (point.value / max) * (chart.height - 10);
      idx ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
    daily.forEach((point, idx) => {
      const x = chart.left + idx * (chart.width / Math.max(1, daily.length - 1));
      const y = chart.top + chart.height - (point.value / max) * (chart.height - 10);
      ctx.fillStyle = '#fff'; ctx.strokeStyle = color; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    });
  }
  const legend = $('activityLegend');
  legend.innerHTML = '';
  const latest = daily.at(-1);
  const avg = average(daily.map((x) => x.value));
  [{k: 'Latest', v: latest ? latest.value : null}, {k: 'Average', v: avg}, {k: 'Samples', v: daily.length}].forEach((item) => {
    const div = document.createElement('div'); div.className = 'mini';
    div.innerHTML = `<span>${item.k}</span><b>${item.v == null ? '—' : (item.k === 'Samples' ? item.v : currentSeries === 'steps' ? formatNumber(Math.round(item.v)) : currentSeries === 'movement_rms' ? item.v.toFixed(3) : item.v.toFixed(1))}${item.k === 'Samples' ? '' : currentSeries === 'steps' ? ' steps' : currentSeries === 'movement_rms' ? ' g' : ''}</b>`;
    legend.append(div);
  });
}
function drawRing(canvas, valueHours) {
  const ctx = canvas.getContext('2d');
  const cx = canvas.width / 2, cy = canvas.height / 2, r = 66;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.lineWidth = 16;
  ctx.strokeStyle = '#e6f1eb';
  ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, Math.PI * 1.5); ctx.stroke();
  const ratio = clamp((valueHours || 0) / 8, 0, 1);
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, '#56d082'); gradient.addColorStop(1, '#0b8a5e');
  ctx.strokeStyle = gradient;
  ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + ratio * Math.PI * 2); ctx.stroke();
  ctx.fillStyle = '#13201b'; ctx.textAlign = 'center'; ctx.font = '800 28px sans-serif';
  ctx.fillText(valueHours ? `${valueHours.toFixed(2)} h` : '—', cx, cy + 8);
  ctx.font = '13px sans-serif'; ctx.fillStyle = '#5f6f69';
  ctx.fillText('Sleep duration', cx, cy + 30);
}
function drawMultiLine(canvas, heartSeries, moveSeries) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const merged = [...heartSeries.map((x) => ({...x, stream: 'heart'})), ...moveSeries.map((x) => ({...x, stream: 'move'}))].sort((a,b)=> Date.parse(a.timestamp)-Date.parse(b.timestamp));
  if (!merged.length) {
    ctx.fillStyle = '#5f6f69'; ctx.font = '14px sans-serif'; ctx.fillText('No physiological observations available for the selected period.', 18, 28); return;
  }
  const chart = { left: 52, top: 16, width: w - 72, height: h - 40 };
  ctx.strokeStyle = '#d8e6de'; ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) { const y = chart.top + i * (chart.height / 4); ctx.beginPath(); ctx.moveTo(chart.left, y); ctx.lineTo(chart.left + chart.width, y); ctx.stroke(); }
  function drawSeries(series, color) {
    if (series.length < 2) return;
    const vals = series.map((x) => x.value);
    const lo = Math.min(...vals), hi = Math.max(...vals), range = hi - lo || 1;
    ctx.strokeStyle = color; ctx.lineWidth = 2.4; ctx.beginPath();
    series.forEach((point, idx) => {
      const x = chart.left + idx * (chart.width / Math.max(1, series.length - 1));
      const y = chart.top + chart.height - ((point.value - lo) / range) * (chart.height - 10) - 5;
      idx ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
  }
  drawSeries(heartSeries, '#34bd71');
  drawSeries(moveSeries, '#8c63ff');
  ctx.fillStyle = '#34bd71'; ctx.fillRect(18, h - 16, 12, 4); ctx.fillStyle = '#5f6f69'; ctx.fillText('Heart rate (bpm)', 36, h - 10);
  ctx.fillStyle = '#8c63ff'; ctx.fillRect(154, h - 16, 12, 4); ctx.fillStyle = '#5f6f69'; ctx.fillText('Movement amplitude (g)', 172, h - 10);
}
function roundRect(ctx, x, y, w, h, r, fill, stroke) {
  if (w < 2 * r) r = w / 2; if (h < 2 * r) r = h / 2;
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
  if (fill) ctx.fill(); if (stroke) ctx.stroke();
}
function renderSleep(items) {
  const series = usableSeries(items, 'sleep_duration');
  const latest = series.at(-1) || null;
  drawRing($('sleepRing'), latest ? latest.value : null);
  $('sleepValue').textContent = latest ? `${latest.value.toFixed(2)} h` : '—';
  $('sleepBadge').textContent = latest ? (latest.value >= 7 ? 'Within target range' : 'Below 7-hour target') : 'Awaiting observations';
  const list = $('sleepStats');
  list.innerHTML = '';
  const avg = average(series.map((x) => x.value));
  const min = series.length ? Math.min(...series.map((x) => x.value)) : null;
  const max = series.length ? Math.max(...series.map((x) => x.value)) : null;
  [
    ['Average duration', avg == null ? '—' : `${avg.toFixed(2)} h`],
    ['Shortest night', min == null ? '—' : `${min.toFixed(2)} h`],
    ['Longest night', max == null ? '—' : `${max.toFixed(2)} h`],
    ['Available samples', `${series.length}`],
  ].forEach(([label, value]) => {
    const row = document.createElement('div'); row.className = 'ns-stat'; row.innerHTML = `<span>${label}</span><span>${value}</span>`; list.append(row);
  });
}
function renderInsights(items) {
  const heart = usableSeries(items, 'heart_rate');
  const sleep = usableSeries(items, 'sleep_duration');
  const steps = usableSeries(items, 'steps');
  const move = usableSeries(items, 'movement_rms');
  const summary = [];
  if (steps.length) summary.push('Activity observations available');
  if (sleep.length) summary.push('sleep-duration tracking available');
  if (heart.length) summary.push('heart-rate series available');
  if (move.length) summary.push('movement-amplitude series available');
  $('insightSummary').textContent = summary.length ? `Overall: ${summary.join(', ')}.` : 'Overall: No participant-level observations available yet.';
  const list = $('insightList'); list.innerHTML = '';
  const bullets = [];
  const stepAvg = average(steps.map((x) => x.value));
  if (stepAvg != null) bullets.push(`Average daily steps across the selected period: ${formatNumber(Math.round(stepAvg))}.`);
  const sleepAvg = average(sleep.map((x) => x.value));
  if (sleepAvg != null) bullets.push(`Average recorded sleep duration: ${sleepAvg.toFixed(2)} hours.`);
  const heartAvg = average(heart.map((x) => x.value));
  if (heartAvg != null) bullets.push(`Average recorded heart rate: ${heartAvg.toFixed(1)} bpm.`);
  if (move.length) bullets.push('Movement amplitude is shown as a research signal and is not a clinical motor score.');
  if (!bullets.length) bullets.push('Load demo mode or select a participant with stored observations to view summaries.');
  bullets.forEach((text) => { const li = document.createElement('li'); li.textContent = text; list.append(li); });
}
function renderResearchMetrics(items) {
  const host = $('researchMetrics'); host.innerHTML = '';
  const steps = usableSeries(items, 'steps');
  const move = usableSeries(items, 'movement_rms');
  const heart = usableSeries(items, 'heart_rate');
  const sleep = usableSeries(items, 'sleep_duration');
  const metricsToRender = [
    ['Activity mean', steps.length ? `${formatNumber(Math.round(average(steps.map((x) => x.value))))}` : '—', 'steps/day'],
    ['Movement mean', move.length ? `${average(move.map((x) => x.value)).toFixed(3)}` : '—', 'g'],
    ['Heart-rate mean', heart.length ? `${average(heart.map((x) => x.value)).toFixed(1)}` : '—', 'bpm'],
    ['Sleep mean', sleep.length ? `${average(sleep.map((x) => x.value)).toFixed(2)}` : '—', 'h'],
  ];
  metricsToRender.forEach(([label, value, unit]) => {
    const card = document.createElement('div'); card.className = 'ns-key-metric';
    card.innerHTML = `<div><strong>${label}</strong><b>${value}</b></div><div class="${value === '—' ? 'ns-trend-flat' : 'ns-trend-up'}">${unit}</div>`;
    host.append(card);
  });
}
function renderEventsAndCapabilities(data, items) {
  const events = $('events'); events.innerHTML = '';
  const streams = data.analysis?.streams || [];
  if (streams.length) {
    streams.forEach((stream) => {
      const p = document.createElement('div'); p.className = 'ns-event';
      p.textContent = `${stream.metric}: ${String(stream.state || 'observed').replaceAll('_', ' ')} · ${stream.baseline_days || 0} baseline days · ${stream.device || 'source not stated'}`;
      events.append(p);
    });
  } else {
    const p = document.createElement('div'); p.className = 'ns-event';
    p.textContent = mode === 'demo' ? 'Simulated trends shown. No clinical event or physiological anomaly has been inferred.' : 'No evaluated events. Personal baselines require sufficient comparable observations.';
    events.append(p);
  }
  const available = new Set(items.map((x) => x.metric));
  const capabilities = $('capabilities'); capabilities.innerHTML = '';
  [
    ['Heart rate', 'heart_rate'],
    ['Sleep duration', 'sleep_duration'],
    ['Activity', 'steps'],
    ['Movement amplitude', 'movement_rms'],
    ['ECG waveform', 'ecg'],
    ['PPG waveform', 'ppg'],
    ['Tremor / gait', 'gait'],
  ].forEach(([label, key]) => {
    const row = document.createElement('div'); row.className = 'ns-capability';
    row.innerHTML = `<div><strong>${label}</strong><span>${available.has(key) ? (mode === 'demo' ? 'Simulated availability' : 'Stored observations available') : 'Not available in this build'}</span></div><div class="ns-chip">${available.has(key) ? 'Available' : 'Unavailable'}</div>`;
    capabilities.append(row);
  });
}
function applyTabState() {
  const map = {
    live: ['activity', 'sleep', 'insights', 'physiology', 'metrics', 'biomarkers'],
    activity: ['activity', 'metrics'],
    sleep: ['sleep', 'insights'],
    physiology: ['physiology', 'metrics'],
    trends: ['activity', 'physiology', 'events'],
    reports: ['insights', 'biomarkers'],
  };
  const visible = new Set(map[currentTab] || map.live);
  document.querySelectorAll('[data-panel]').forEach((node) => {
    node.hidden = !visible.has(node.dataset.panel);
  });
}
function render(data) {
  const items = data.items.slice().sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  setConnectionState(items);
  renderMetricCards(items);
  const activitySeries = groupDaily(usableSeries(items, currentSeries));
  drawBarLineChart($('activityChart'), activitySeries, '#34bd71', currentSeries);
  renderSleep(items);
  renderInsights(items);
  drawMultiLine($('physioChart'), usableSeries(items, 'heart_rate'), usableSeries(items, 'movement_rms'));
  renderResearchMetrics(items);
  renderEventsAndCapabilities(data, items);
  const latest = items.at(-1);
  if (mode === 'demo') {
    $('status').textContent = 'Demonstration only. Simulated values are not saved as participant measurements.';
  } else {
    $('status').textContent = latest ? `Loaded stored observations through ${new Date(latest.timestamp).toLocaleString()}. This page summarizes available participant-level data only.` : 'No stored participant-level observations were returned.';
  }
  applyTabState();
}
async function refresh(force = false) {
  if ((loading && !force) || document.hidden) return;
  loading = true;
  try {
    if (!person && mode !== 'demo') throw new Error('Open this page from a selected participant.');
    let payload;
    if (mode === 'demo') {
      if (!paused) tick++;
      payload = demo();
    } else {
      const response = await fetch(`/api/neurosense/${encodeURIComponent(person)}/observations?mode=active`, { cache: 'no-store' });
      if (!response.ok) throw new Error(response.status === 401 ? 'Sign in to NeuroAccess first.' : `Monitoring API unavailable (${response.status}).`);
      payload = await response.json();
    }
    render(payload);
  } catch (error) {
    $('status').textContent = error.message;
  } finally {
    loading = false;
  }
}

refresh();
setInterval(() => refresh(), 5000);
