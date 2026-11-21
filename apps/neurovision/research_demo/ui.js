'use strict';
const $ = id => document.getElementById(id);
const accessToken = new URLSearchParams(window.location.hash.slice(1)).get('token') || '';
if (accessToken) history.replaceState(null, '', window.location.pathname + window.location.search);
const authHeaders = { Authorization: 'Bearer ' + accessToken };
const sliceObjectUrls = new Map();
let sliceGeneration = 0;
const state = { cloud:[], yaw:0.6, pitch:0.22, visit:1, coords:[0,0,0], shape:[1,1,1], opacity:43, label:0, tick:0 };
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function updateSlices(){
  const params = new URLSearchParams({ visit:state.visit, x:state.coords[0], y:state.coords[1], z:state.coords[2], opacity:state.opacity/100, label:state.label });
  const generation = ++sliceGeneration;
  for (const plane of ['axial','coronal','sagittal']) {
    const url = '/api/slice?' + params.toString() + '&plane=' + plane;
    fetch(url, { headers:authHeaders, cache:'no-store' })
      .then(response => { if (!response.ok) throw new Error('MRI slice request failed: ' + response.status); return response.blob(); })
      .then(blob => {
        if (generation !== sliceGeneration) return;
        const objectUrl = URL.createObjectURL(blob);
        const previous = sliceObjectUrls.get(plane);
        const img = $(plane);
        img.onload = () => { if (previous) URL.revokeObjectURL(previous); };
        img.onerror = () => { if (previous) URL.revokeObjectURL(previous); };
        sliceObjectUrls.set(plane, objectUrl);
        img.src = objectUrl;
      })
      .catch(error => { if (generation === sliceGeneration) $('status').textContent = error.message; });
  }
  $('naxial').textContent='z='+state.coords[2]; $('ncoronal').textContent='y='+state.coords[1]; $('nsagittal').textContent='x='+state.coords[0];
  $('crosshair').textContent=state.coords.join(' / ');
}
function setMeta(data){
  const m=data.current; state.shape=m.shape; state.coords=[...m.center];
  $('visit').replaceChildren(...data.visits.map(v=>{const o=document.createElement('option');o.value=v.id;o.textContent=v.label;return o;}));$('visit').value=state.visit;
  $('status').textContent=m.mode==='SYNTHETIC'?'SYNTHETIC DEMO':'LOCAL SOURCE — UNREVIEWED';
  $('banner').textContent=m.mode==='SYNTHETIC'?'SYNTHETIC DEMONSTRATION · NOT AN OASIS-2 MRI · NOT A REAL PARTICIPANT SCAN · NO LESION DETECTION':'LOCAL MRI RESEARCH VIEW · NOT CLINICALLY REVIEWED · NO AUTOMATED ABNORMALITY DETECTION · NO PARTICIPANT RECORD WRITES';
  $('dataset').textContent=m.sample_id+' / '+m.visit;
  $('source').textContent=m.source;
  $('dims').textContent=m.shape.join(' × ');
  $('spacing').textContent=m.voxel_size_mm.map(x=>Number(x).toFixed(2)).join(' × ')+' mm';
  $('orientation').textContent=m.orientation;
  $('imgqc').textContent=m.qc;
  for(const [id,pos] of [['xslide',0],['yslide',1],['zslide',2]]){const slider=$(id);slider.max=m.shape[pos]-1;slider.value=state.coords[pos];}
  const options=[{id:0,name:'All overlays'}, ...m.labels.map(x=>({id:x.id,name:x.name}))];
  $('overlay').replaceChildren(...options.map(o=>{const el=document.createElement('option');el.value=o.id;el.textContent=o.name;return el;}));state.label=0;
  const colors=['#56dcb2','#559bff','#ffa754','#b888ed'];
  $('labeltable').innerHTML='<table><thead><tr><th>Region / label</th><th>Volume (mm³)</th><th>Eligibility</th></tr></thead><tbody>'+m.labels.map((r,i)=>'<tr><td><span class="swatch" style="background:'+colors[Math.min(i,3)]+'"></span>'+esc(r.name)+'</td><td>'+(r.volume_mm3===null?'Not verified':Number(r.volume_mm3).toLocaleString())+'</td><td>'+esc(r.status)+'</td></tr>').join('')+'</tbody></table>';
  if(!m.labels.length) $('labeltable').innerHTML='<p>No segmentation was supplied. Segmentation and lesion detection have not run.</p>';
  $('passport').innerHTML='<b>Source:</b> '+esc(m.source)+'<br><b>Software:</b> '+esc(m.software_version)+'<br><b>Model:</b> '+esc(m.model)+'<br><b>Source SHA-256:</b> '+esc(m.source_checksum || 'not applicable — synthetic')+'<br><b>Clinical use:</b> '+esc(m.clinical_use);
  state.cloud=m.preview_point_cloud||[];renderCloud();
  updateSlices();
}
async function load(){
  const response=await fetch('/api/meta?visit='+state.visit,{cache:'no-store',headers:authHeaders});
  if(!response.ok)throw new Error('Could not load MRI metadata');
  setMeta(await response.json());
}
$('visit').addEventListener('change',async e=>{state.visit=Number(e.target.value);try{await load()}catch(ex){$('status').textContent=ex.message;}});
$('overlay').addEventListener('change',e=>{state.label=Number(e.target.value);updateSlices();});
$('opacity').addEventListener('input',e=>{state.opacity=Number(e.target.value);$('opacityval').textContent=state.opacity+'%';updateSlices();});
for(const [id,pos] of [['xslide',0],['yslide',1],['zslide',2]])$(id).addEventListener('input',e=>{state.coords[pos]=Number(e.target.value);updateSlices();});
load().catch(e=>{$('status').textContent='Load failed: '+e.message;});

function renderCloud(){
  const canvas=$('pointcloud'), ctx=canvas.getContext('2d'); if(!ctx)return;
  const w=canvas.width,h=canvas.height;ctx.fillStyle='#09151b';ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='#2b4c51';ctx.strokeRect(10,10,w-20,h-20);
  if(!state.cloud.length){ctx.fillStyle='#9cb0b8';ctx.font='17px Segoe UI';ctx.fillText('No supplied segmentation for 3D label preview',45,150);return;}
  const cy=Math.cos(state.yaw),sy=Math.sin(state.yaw),cp=Math.cos(state.pitch),sp=Math.sin(state.pitch);
  const data=state.cloud.map(p=>{let x=p[0]*cy+p[2]*sy,zz=-p[0]*sy+p[2]*cy;let y=p[1]*cp-zz*sp,z=p[1]*sp+zz*cp;return{x,y,z,label:p[3]};}).sort((a,b)=>a.z-b.z);
  const colors={1:'#43cba5',2:'#5e9bec',3:'#ffae64'};
  for(const p of data){const factor=1.75/(2.5-p.z);const px=w/2+p.x*205*factor,py=h/2-p.y*129*factor;ctx.fillStyle=colors[p.label]||'#ad8def';ctx.globalAlpha=.30+.55*(p.z+1)/2;ctx.beginPath();ctx.arc(px,py,Math.max(1.3,2.6*factor),0,2*Math.PI);ctx.fill();}
  ctx.globalAlpha=1;ctx.fillStyle='#a3bec5';ctx.font='12px Segoe UI';ctx.fillText('Research illustration · drag to rotate',18,h-19);
}
let dragging=false,lastX=0,lastY=0;
$('pointcloud').addEventListener('pointerdown',e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;$('pointcloud').setPointerCapture(e.pointerId);});
$('pointcloud').addEventListener('pointermove',e=>{if(!dragging)return;state.yaw+=(e.clientX-lastX)*.009;state.pitch=Math.max(-1.4,Math.min(1.4,state.pitch+(e.clientY-lastY)*.009));lastX=e.clientX;lastY=e.clientY;renderCloud();});
$('pointcloud').addEventListener('pointerup',()=>{dragging=false;});
$('pointcloud').addEventListener('pointercancel',()=>{dragging=false;});
