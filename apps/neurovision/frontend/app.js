'use strict';const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);let comparisonPack=null,scan=null,vol=null,overlay=null,catalog=[],serial=0,angleX=.3,angleY=.5,zoom=1,drag=null;
const renderer=new window.MRITextureVolume($('volume3d'),message=>$('volumeStatus').textContent=message);
$('mode').value=params.get('mode')==='demo'?'demo':'active';const palette=Array.from({length:256},(_,i)=>{if(i===0)return [0,0,0];const h=((i*137.508)%360)/60,c=.74,x=c*(1-Math.abs(h%2-1)),t=h<1?[c,x,0]:h<2?[x,c,0]:h<3?[0,c,x]:h<4?[0,x,c]:h<5?[x,0,c]:[c,0,x];return t.map(v=>Math.round((v+.15)*235))});
function text(tag,s){const e=document.createElement(tag);e.textContent=s;return e}
function table(id,headers,rows){const root=$(id);root.replaceChildren();const t=document.createElement('table');[headers,...rows].forEach((row,i)=>{const tr=document.createElement('tr');row.forEach(v=>tr.append(text(i?'td':'th',v)));t.append(tr)});root.append(t)}
async function api(path){const r=await fetch('/api/neurovision/'+path+(path.includes('?')?'&':'?')+'mode='+$('mode').value,{cache:'no-store'});if(!r.ok)throw Error(r.status===401?'Sign in on the BAINP home page first.':'Imaging API returned '+r.status+': '+await r.text());return r.json()}
async function action(fn){try{await fn()}catch(e){$('status').textContent=e.message}}
function clear(){renderer.clear();comparisonPack=null;scan=null;vol=null;overlay=null;for(const id of ['axial','coronal','sagittal','mesh','baselineView','followView']){const c=$(id);c.getContext('2d').clearRect(0,0,c.width,c.height)}for(const id of ['measurements','quality','limits','provenance','comparison','scanInfo','evidenceSummary'])$(id).replaceChildren();$('scanTitle').textContent='Select a prepared scan'}
async function directory(){serial++;clear();$('status').textContent='Loading prepared imaging catalog…';const d=await api('scans');catalog=d.items;$('scans').replaceChildren();for(const item of catalog){const o=document.createElement('option');o.value=item.id;o.textContent=item.cohort+' / '+item.subject+' / '+item.visit+' / '+(item.acquisition||item.id.slice(0,8));$('scans').append(o)}if(!catalog.length){$('status').textContent='No prepared research scans in this mode. Run the NeuroVision preparation command, or select Synthetic demonstration.';return}if(params.get('scan')&&catalog.some(x=>x.id===params.get('scan')))$('scans').value=params.get('scan');await choose()}
async function choose(){const token=++serial;clear();$('status').textContent='Loading imaging package…';const pack=await api('scans/'+encodeURIComponent($('scans').value));if(token!==serial)return;scan=pack;const m=scan.metadata;vol=Uint8Array.from(atob(scan.volume),c=>c.charCodeAt(0));overlay=Uint8Array.from(atob(scan.overlay),c=>c.charCodeAt(0));const expected=m.display_shape.reduce((a,b)=>a*b,1);if(vol.length!==expected||overlay.length!==expected)throw Error('Display package dimensions do not match');['x','y','z'].forEach((id,i)=>{$(id).max=m.display_shape[i]-1;$(id).value=Math.floor(m.display_shape[i]/2)});$('scanTitle').textContent=m.cohort+' / '+m.subject+' / '+m.visit;$('scanInfo').textContent=(m.synthetic?'SYNTHETIC PHANTOM · ':'RESEARCH ACQUISITION · ')+m.native_shape.join(' × ')+' voxels · native axes '+m.native_axes.join('')+' · display spacing '+m.display_spacing_mm.toFixed(2)+' mm';
table('measurements',['Measurement','Voxels','Volume (mL)','Mask fraction','Meaning'],m.measurements.map(x=>[x.name,x.voxel_count??'Not recorded',x.volume_ml.toFixed(3),x.fraction_of_mask_percent==null?'—':x.fraction_of_mask_percent.toFixed(2)+'%',x.status]));$('quality').append(text('p','Review: '+m.review),text('p','Flags: '+[...(m.quality_flags||[]),...(m.upstream_flags||[])].join(', ')||'No automated flags'));for(const s of m.limitations)$('limits').append(text('li',s));$('provenance').textContent=JSON.stringify(m,null,2);renderEvidence(m);$('surface').replaceChildren();scan.surfaces.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=s.name;$('surface').append(o)});const firstAtlasSurface=scan.surfaces.findIndex(s=>Number(s.id)>0);if(firstAtlasSurface>=0)$('surface').value=String(firstAtlasSurface);$('followup').replaceChildren();const same=catalog.filter(x=>x.subject===m.subject&&x.cohort===m.cohort&&x.id!==$('scans').value),visits=same.filter(x=>x.visit!==m.visit);
for(const item of visits){const o=document.createElement('option');o.value=item.id;o.textContent=item.visit+' · '+(item.date||'date unavailable');$('followup').append(o)}
$('compare').disabled=!visits.length;
if(!visits.length){const o=document.createElement('option');o.value='';o.textContent='No distinct follow-up visit prepared';$('followup').append(o);$('comparisonHelp').textContent='No second visit is available for this research subject. '+(same.length?'Other acquisitions belong to the same visit. ':'')+'The baseline image is shown below. Prepare an actual later visit to compare; adding other people does not create longitudinal follow-up.'}else{$('comparisonHelp').textContent='A distinct visit is available. Images can be inspected side by side; quantitative differences require documented dates, matching methods and approved comparability.'}
$('surfaceHelp').textContent=scan.surfaces.length
  ?(m.quality_flags?.includes('IMAGE_FOREGROUND_PREVIEW_NOT_ANATOMICAL')
    ?'3D foreground preview available: this is an intensity-based outline, not brain extraction, segmentation, or lesion detection.'
    :'Aligned mask/label surfaces are available for anatomical QC; unreviewed labels do not establish anatomical validity.')
  :'No surface in this saved package. Use Build / update 3D preview from saved scan or supply a separately generated aligned mask/atlas. The existing source has not been altered.';
document.dispatchEvent(new CustomEvent('bainp:neurovision:scan-loaded',{detail:{metadata:m, surfaceCount:scan.surfaces.length}}));renderer.setPackage(scan);$('threshold').value=.14;$('clip').value=1;$('brainOnly').checked=renderer.hasMask===true;$('brainOnly').disabled=!renderer.hasMask;drawPlanes();drawMesh();drawPair();$('status').textContent=m.synthetic?'Synthetic demonstration loaded. No human MRI or biological change is represented.':'Prepared research scan loaded. '+(m.quality_flags.includes('IMAGE_FOREGROUND_PREVIEW_NOT_ANATOMICAL')?'3D signal foreground is NOT a brain mask or disease finding. ':'')+'Review source provenance and segmentation quality.'}
function drawPlanes(){if(!scan)return;const shape=scan.metadata.display_shape,[nx,ny,nz]=shape,alpha=Number($('opacity').value),contrast=Number($('window').value),spacing=scan.metadata.display_spacing_mm;const get=(x,y,z)=>x*ny*nz+y*nz+z;
for(const [canvasId,axis] of [['axial',2],['coronal',1],['sagittal',0]]){const fixed=Number($(['x','y','z'][axis]).value);const w=axis===0?ny:nx,h=axis===2?ny:nz;const off=document.createElement('canvas');off.width=w;off.height=h;const ctx=off.getContext('2d'),im=ctx.createImageData(w,h);for(let j=0;j<h;j++)for(let i=0;i<w;i++){let xyz=axis===2?[i,j,fixed]:axis===1?[i,fixed,j]:[fixed,i,j];const idx=get(...xyz),target=((h-1-j)*w+i)*4;let g=Math.max(0,Math.min(255,(vol[idx]-128)/contrast+128));const label=overlay[idx],rgb=palette[label]||palette[1];for(let k=0;k<3;k++)im.data[target+k]=label?g*(1-alpha)+rgb[k]*alpha:g;im.data[target+3]=255}ctx.putImageData(im,0,0);const c=$(canvasId),g=c.getContext('2d');g.fillStyle='#08121c';g.fillRect(0,0,c.width,c.height);const scale=Math.min(c.width/w,c.height/h),dw=w*scale,dh=h*scale;g.drawImage(off,(c.width-dw)/2,(c.height-dh)/2,dw,dh);g.fillStyle='white';g.font='14px system-ui';g.fillText(axis===0?'P':'L',8,195);g.fillText(axis===0?'A':'R',360,195);g.fillText(axis===2?'A':'S',188,18);g.fillText(axis===2?'P':'I',188,374);const row=scan.metadata.display_affine[axis];$(['xpos','ypos','zpos'][axis]).textContent='Slice '+fixed+' · '+(row[axis]*fixed+row[3]).toFixed(1)+' mm (RAS '+['X','Y','Z'][axis]+')'} }
function drawMesh(){const c=$('mesh'),g=c.getContext('2d');g.fillStyle='#0b1722';g.fillRect(0,0,c.width,c.height);if(!scan)return;const s=scan.surfaces[Number($('surface').value)];if(!s){g.fillStyle='white';g.fillText('No mask/label surface available',20,30);return}const co=Math.cos(angleY),si=Math.sin(angleY),cx=Math.cos(angleX),sx=Math.sin(angleX),vertices=s.vertices_mm.map(([x,y,z])=>{const a=x*co+z*si,b=-x*si+z*co;return[a,y*cx-b*sx,y*sx+b*cx]});let extent=1;for(const v of vertices)extent=Math.max(extent,Math.hypot(...v));const scale=180/extent*zoom;const faces=s.faces.map(f=>({f,depth:f.reduce((t,i)=>t+vertices[i][2],0)/3})).sort((a,b)=>a.depth-b.depth);for(const obj of faces){const f=obj.f,a=vertices[f[0]],b=vertices[f[1]],d=vertices[f[2]],u=b.map((v,i)=>v-a[i]),v=d.map((x,i)=>x-a[i]),normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],light=.35+.65*Math.abs(normal[2])/(Math.hypot(...normal)||1);const intensity=s.intensity?f.reduce((t,i)=>t+s.intensity[i],0)/3:.65;const gray=Math.round((.25+.75*intensity)*light*255);const anatomical=Number(s.id)>0&&!scan.metadata.quality_flags?.includes('IMAGE_FOREGROUND_PREVIEW_NOT_ANATOMICAL');const rgb=palette[1+(Math.abs(Number(s.id))%254)]||[120,220,205];g.fillStyle=anatomical?`rgb(${rgb.map(x=>Math.round(x*(.28+.72*light))).join(',')})`:`rgb(${gray},${gray},${gray})`;g.beginPath();f.forEach((idx,j)=>{const p=vertices[idx],x=300+p[0]*scale,y=210-p[1]*scale;j?g.lineTo(x,y):g.moveTo(x,y)});g.closePath();g.fill()}g.fillStyle='white';g.fillText(s.name,15,25)}
$('mesh').onpointerdown=e=>{drag=[e.clientX,e.clientY];$('mesh').setPointerCapture(e.pointerId)};$('mesh').onpointermove=e=>{if(!drag)return;angleY+=(e.clientX-drag[0])*.01;angleX+=(e.clientY-drag[1])*.01;drag=[e.clientX,e.clientY];drawMesh()};$('mesh').onpointerup=()=>drag=null;$('mesh').onpointercancel=()=>drag=null;$('mesh').addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.4,Math.min(3,zoom*Math.exp(-e.deltaY*.001)));drawMesh()},{passive:false});
for(const id of ['x','y','z','opacity','window'])$(id).oninput=()=>{drawPlanes();drawPair()};$('surface').onchange=drawMesh;$('reload').onclick=()=>action(directory);$('mode').onchange=()=>{configureImportMode();void action(directory)};$('scans').onchange=()=>action(choose);$('compare').onclick=()=>action(async()=>{if(!$('followup').value)throw Error('No other prepared acquisition for this subject.');comparisonPack=await api('scans/'+encodeURIComponent($('followup').value));drawPair();const c=await api('compare?baseline='+encodeURIComponent($('scans').value)+'&followup='+encodeURIComponent($('followup').value));$('comparison').replaceChildren(text('p',c.state+(c.reasons.length?' · '+c.reasons.join(', '):'')),text('p',c.interpretation));if(c.changes.length){const div=document.createElement('div');div.id='changeTable';$('comparison').append(div);table('changeTable',['Measurement','Baseline mL','Follow-up mL','Difference mL','Difference %'],c.changes.map(x=>[x.name,x.baseline_ml.toFixed(3),x.followup_ml.toFixed(3),x.difference_ml.toFixed(3),x.percent_difference.toFixed(2)]))}});action(directory);

function drawPair(){if(!scan)return;const z=Number($('z').value),aff=scan.metadata.display_affine,worldZ=z*aff[2][2]+aff[2][3];for(const [id,pack] of [['baselineView',scan],...(comparisonPack?[['followView',comparisonPack]]:[])]){const [nx,ny,nz]=pack.metadata.display_shape,a=pack.metadata.display_affine,k=Math.round((worldZ-a[2][3])/a[2][2]),c=$(id),g=c.getContext('2d');g.fillStyle='#08121c';g.fillRect(0,0,384,384);if(k<0||k>=nz){g.fillStyle='white';g.fillText('Coordinate outside field of view',15,25);continue}const data=Uint8Array.from(atob(pack.volume),v=>v.charCodeAt(0)),off=document.createElement('canvas');off.width=nx;off.height=ny;const ctx=off.getContext('2d'),im=ctx.createImageData(nx,ny);for(let y=0;y<ny;y++)for(let x=0;x<nx;x++){const v=data[x*ny*nz+y*nz+k],i=((ny-y-1)*nx+x)*4;im.data[i]=im.data[i+1]=im.data[i+2]=v;im.data[i+3]=255}ctx.putImageData(im,0,0);const scale=Math.min(384/nx,384/ny);g.drawImage(off,(384-nx*scale)/2,(384-ny*scale)/2,nx*scale,ny*scale);g.fillStyle='white';g.fillText('L',8,190);g.fillText('R',365,190)}}

$('brainOnly').onchange=()=>{renderer.masked=$('brainOnly').checked;renderer.draw()};$('threshold').oninput=()=>{renderer.threshold=Number($('threshold').value);renderer.draw()};$('clip').oninput=()=>{renderer.clipping=Number($('clip').value);renderer.draw()};$('resetVolume').onclick=()=>{renderer.rx=.2;renderer.ry=.3;renderer.zoom=1;renderer.clipping=1;$('clip').value=1;renderer.draw()};$('fullVolume').onclick=()=>action(async()=>{if(document.fullscreenElement)await document.exitFullscreen();else await $('volume3d').requestFullscreen()});
$('followup').onchange=()=>{comparisonPack=null;$('followView').getContext('2d').clearRect(0,0,384,384);$('comparison').replaceChildren();drawPair()};

function renderEvidence(m){const rows=[['Source',m.synthetic?'Synthetic phantom, not a human MRI':(m.source_kind||'Research MRI')],['Research identity',m.cohort+' / '+m.subject+' / '+m.visit],['Modality',m.modality||'Not recorded'],['Review status',m.review||'Not recorded'],['Native geometry',m.native_shape.join(' × ')+' voxels; '+m.native_axes.join('')+' axes'],['Display grid','RAS+ resampling, '+m.display_spacing_mm.toFixed(2)+' mm'],['Measurements',m.measurements.length?'Native-grid voxel counts; interpret each measurement status carefully':'No supplied brain mask or anatomical labels; regional volumes not computed'],['Segmentation meaning',m.measurements.some(v=>v.status.includes('intensity class'))?'Experimental intensity classes; anatomical identity is not established':'See each measurement’s upstream segmentation status'],['Longitudinal comparison',m.longitudinal_comparable===true?'Explicit comparability recorded; further gate checks apply':'Comparability not established'],['Processing version',m.version],['Source integrity',Object.keys(m.source_sha256||{}).length+' source hashes recorded; prepared package hash checked by API']];table('evidenceSummary',['Evidence item','Recorded information'],rows)}
$('refreshPreview').onclick=()=>action(async()=>{
 if($('mode').value!=='active'||!scan)throw Error('Select an existing active research MRI first.');
 if(!confirm('Reprocess the selected saved scan with the current imaging engine? The original MRI and old package will be preserved. This will NOT run anatomical segmentation.'))return;
 const worker=await workerStatus();if(!worker?.online)throw Error('Imaging worker offline; start it and retry.');
 const r=await boundedRequest('/api/neurovision/import-jobs/refresh-package/'+encodeURIComponent($('scans').value)+'?mode=active', {method:'POST',headers:{'X-NeuroAccess-Request':'1'}},20000);
 const job=await r.json();if(!/^[0-9a-f]{32}$/.test(job.id))throw Error('Invalid refresh job');
 currentJob=job.id;sessionStorage.setItem('nv_import_job',currentJob);
 importMessage('Repreparing saved source image; original source is unchanged.');
 await pollJob();
});
$('downloadEvidence').onclick=()=>action(async()=>{if(!scan)throw Error('Select a scan first.');const report={title:'NeuroVision research evidence',generated_at:new Date().toISOString(),metadata:scan.metadata,interpretation:'Research observations; no disease diagnosis or clinical prediction.'};const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='neurovision-evidence-'+$('scans').value+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
$('copyImport').onclick=()=>action(async()=>{const command=$('importCommand').textContent;try{await navigator.clipboard.writeText(command);$('importStatus').textContent='Local import command copied.'}catch(e){$('importStatus').textContent='Select and copy the command shown below.'}});
// MRI import is a separate, asynchronous worker workflow. Never hide errors in
// the page-level status while the upload panel still says 'Creating local import'.
let currentJob=null,jobTimer=null,workerCheckPromise=null,submittingImport=false,lastWorkerError=null;
function importMessage(message,kind='info'){
  const el=$('importStatus');el.textContent=message;el.dataset.state=kind;
  if(kind==='error')$('status').textContent='MRI import needs attention. Details appear below the upload form.';
}
function apiErrorMessage(status,data){
  let detail='';
  if(data&&typeof data==='object'){
    const d=data.detail;
    detail=typeof d==='string'?d:(Array.isArray(d)?d.map(x=>x.msg||JSON.stringify(x)).join('; '):JSON.stringify(d||data));
  }else detail=String(data||'');
  if(status===401||status===403)return 'MRI access is denied for this signed-in account. Sign in again or check the account status. '+detail;
  if(status===404)return 'MRI import API was not found. Restart the existing BAINP API, and check that the NeuroVision import bridge is mounted. '+detail;
  if(status===413)return 'MRI upload exceeds the server limit. Use the local NIfTI import command. '+detail;
  if(status===409)return 'Import conflict or the queue is full. Check existing import jobs; do not delete raw MRI files. '+detail;
  if(status===422)return 'MRI metadata or upload was rejected. Check format, protocol, IDs and image dimensions. '+detail;
  if(status===503)return 'BAINP API or imaging storage unavailable. Restart or inspect local services. '+detail;
  return 'MRI API error HTTP '+status+(detail?': '+detail:'');
}
function requestStage(path){
  if(/\/aux\/(mask|labels)/.test(path))return 'aligned mask/label upload';
  if(/\/image(?:\?|$)/.test(path))return 'primary MRI upload';
  if(/\/finalize(?:\?|$)/.test(path))return 'import finalization';
  if(/\/import-jobs(?:\?|$)/.test(path))return 'job creation';
  if(/\/import-worker/.test(path))return 'worker readiness';
  return 'MRI API request';
}
async function boundedRequest(path,options={},timeoutMs=18000){
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const response=await fetch(path,{...options,signal:controller.signal,cache:'no-store'});
    if(!response.ok){let details;try{details=await response.json()}catch(_){details=await response.text().catch(()=>"")};throw Error(apiErrorMessage(response.status,details))}
    return response;
  }catch(e){
    if(e.name==='AbortError')throw Error('Request timed out ('+Math.ceil(timeoutMs/1000)+' s) at '+requestStage(path)+'. The upload may still exist; check job status before retrying.');
    if(e instanceof TypeError)throw Error('Network connection lost at '+requestStage(path)+'. This is a browser-to-BAINP server/proxy failure, not a result from the MRI model. Check the API and proxy terminals; inspect the existing job before retrying.');
    throw e;
  }
  finally{clearTimeout(timeout)}
}
async function workerStatus(){
  if($('mode').value==='demo')return null;
  if(workerCheckPromise)return workerCheckPromise;
  workerCheckPromise=(async()=>{try{
    const response=await boundedRequest('/api/neurovision/import-worker?mode=active',{},12000);
    const worker=await response.json();lastWorkerError=null;
    $('workerStatus').textContent=worker.online
      ?'Imaging worker online · queued '+(worker.queue?.queued??0)+' · processing '+(worker.queue?.processing??0)+'.'
      :'Imaging worker OFFLINE. Open a second PowerShell terminal, run: conda activate bainp-brain, then & "'+(worker.worker_script||'apps\\neurovision\\Start-NeuroVision-Worker.ps1')+'". Keep that terminal available to inspect logs.';
    $('workerStatus').dataset.state=worker.online?'ok':'error';
    return worker;
  }catch(e){lastWorkerError=e.message;$('workerStatus').textContent='MRI import preflight failed: '+e.message;$('workerStatus').dataset.state='error';return null}
  finally{workerCheckPromise=null}})();
  return workerCheckPromise;
}
async function pollJob(){
  if(!currentJob)return;
  const jobId=currentJob;
  try{
    const r=await boundedRequest('/api/neurovision/import-jobs/'+encodeURIComponent(jobId)+'?mode=active',{},15000);
    const job=await r.json();
    const state=job.state||'unknown';
    $('discardImport').hidden=true;
    if(state==='complete'){
      importMessage('MRI preparation completed. Loading the scan in all viewers…','ok');
      currentJob=null;sessionStorage.removeItem('nv_import_job');$('importSubmit').disabled=false;
      await directory();
      if(job.package_id){$('scans').value=job.package_id;await choose()}
      importMessage('MRI loaded. Signal foreground previews are not anatomical segmentations; true regional volumes require aligned and quality-reviewed labels.','ok');
      return;
    }
    if(state==='failed'){
      currentJob=null;sessionStorage.removeItem('nv_import_job');$('importSubmit').disabled=false;
      importMessage('MRI preparation FAILED: '+(job.error||'No detail returned')+'. See worker logs; original source is preserved.','error');return;
    }
    if(state==='awaiting_overlays'||state==='awaiting_upload'){
      importMessage('Import '+jobId.slice(0,8)+' is '+state.replaceAll('_',' ')+'. If the upload was interrupted, discard this incomplete job then submit corrected files. No MRI results were accepted.','error');
      $('discardImport').hidden=false;$('importSubmit').disabled=false;return;
    }
    if(state==='cancelled'){
      currentJob=null;sessionStorage.removeItem('nv_import_job');$('discardImport').hidden=true;
      $('importSubmit').disabled=false;importMessage('Incomplete import discarded. Select valid files for a new import.','info');return;
    }
    const age=job.updated_at?Math.floor((Date.now()/1000-job.updated_at)):-1;
    const ageInfo=age>=0?' · last stage change '+age+'s ago':'';
    importMessage('MRI '+state.replaceAll('_',' ')+' · job '+jobId.slice(0,8)+ageInfo+'. The viewers will remain empty until preparation completes.','info');
    if(state==='queued'&&job.worker_online===false)await workerStatus();
    jobTimer=setTimeout(pollJob,2500);
  }catch(e){
    importMessage('Unable to check import job '+jobId.slice(0,8)+': '+e.message+'. Use Check import status to retry.','error');
    $('importSubmit').disabled=false;
  }
}
$('discardImport').onclick=()=>action(async()=>{
  if(!currentJob)throw Error('No incomplete import job selected.');
  if(!confirm('Discard the incomplete upload job? Original completed MRI packages and raw scans are preserved.'))return;
  const r=await boundedRequest('/api/neurovision/import-jobs/'+currentJob+'/cancel?mode=active',
    {method:'POST',headers:{'X-NeuroAccess-Request':'1'}},18000);
  const result=await r.json();
  if(result.state!=='cancelled')throw Error('Upload cancellation was not confirmed.');
  currentJob=null;sessionStorage.removeItem('nv_import_job');$('discardImport').hidden=true;
  importMessage('Incomplete upload cancelled. You can now select a valid MRI and submit again.','info');
});
$('importRetry').onclick=()=>{
  if(jobTimer)clearTimeout(jobTimer);
  void (async()=>{await workerStatus();if(currentJob)await pollJob();else importMessage('No active import job in this tab. Check the scan catalog or start a new authorized import.')})();
};
$('importForm').onsubmit=async event=>{
  event.preventDefault();if(submittingImport)return;
  submittingImport=true;$('importSubmit').disabled=true;
  try{
    if($('mode').value!=='active')throw Error('Select Authorized research scans to import a real scan.');
    if(currentJob)throw Error('An earlier upload is still tracked. Check its status or discard the incomplete upload before creating another.');
    const f=$('importFile').files[0];
    if(!f||!/\.nii(\.gz)?$/i.test(f.name))throw Error('Select a NIfTI .nii or .nii.gz scan. Analyze .hdr/.img requires the local companion.');
    if(f.size>64*1024*1024)throw Error('File exceeds 64 MiB; use the local import script.');
    if(f.size<32)throw Error('File is empty or unusually small. Select a valid 3D MRI.');
    if(!$('importConsent').checked)throw Error('Confirm you are authorized to process this research scan.');
    const worker=await workerStatus();
    if(!worker)throw Error(lastWorkerError||'The local NeuroVision API is unreachable; cannot start an import.');
    if(!worker.online)throw Error('The MRI worker is OFFLINE. Open a second VS Code terminal and run: conda activate bainp-brain; then & "'+(worker.worker_script||'apps\\neurovision\\Start-NeuroVision-Worker.ps1')+'". Return here and click Check import status.');
    importMessage('Step 1/3: Creating local import job…');
    const mask=$('importMask').files[0],labels=$('importLabels').files[0];
    for(const extra of [mask,labels])if(extra&&(!/\.nii(\.gz)?$/i.test(extra.name)||extra.size>64*1024*1024||extra.size<32))throw Error('Aligned mask/labels must be valid NIfTI files up to 64 MiB.');
    // The same T1 MRI cannot be a brain extraction mask or atlas labelmap.
    const matchesFile=(a,b)=>Boolean(a&&b&&a.name===b.name&&a.size===b.size&&a.lastModified===b.lastModified);
    if(matchesFile(f,mask)||matchesFile(f,labels)||matchesFile(mask,labels))
      throw Error('The same file was selected for MRI, mask or labels. Upload only the MRI unless you have separately generated, correctly aligned binary mask/atlas files.');

    const data={mask_filename:mask?.name||'',labels_filename:labels?.name||'',filename:f.name,cohort:$('importCohort').value,subject:$('importSubject').value,visit:$('importVisit').value,modality:$('importModality').value,protocol:$('importProtocol').value,visit_date:$('importDate').value,authorized:true};
    let r=await boundedRequest('/api/neurovision/import-jobs?mode=active',{method:'POST',headers:{'Content-Type':'application/json','X-NeuroAccess-Request':'1'},body:JSON.stringify(data)},20000);
    const j=await r.json();if(!/^[0-9a-f]{32}$/.test(j.id))throw Error('API returned an invalid import job identifier.');
    currentJob=j.id;sessionStorage.setItem('nv_import_job',currentJob);
    importMessage('Step 2/3: Uploading '+f.name+' ('+(f.size/1048576).toFixed(1)+' MiB) to local BAINP storage…');
    r=await boundedRequest('/api/neurovision/import-jobs/'+currentJob+'/image?mode=active',{method:'PUT',headers:{'Content-Type':'application/octet-stream','X-NeuroAccess-Request':'1'},body:f},180000);
    const upload=await r.json();if(upload.state!=='queued'&&upload.state!=='awaiting_overlays')throw Error('Server did not accept the uploaded MRI.');
    if(upload.state==='awaiting_overlays'){
      for(const [kind,file] of [['mask',mask],['labels',labels]]){
        if(!file)continue;
        importMessage('Uploading '+kind+' ('+(file.size/1048576).toFixed(1)+' MiB); geometry will be validated by the imaging worker…');
        await boundedRequest('/api/neurovision/import-jobs/'+currentJob+'/aux/'+kind+'?mode=active',{method:'PUT',headers:{'Content-Type':'application/octet-stream','X-NeuroAccess-Request':'1'},body:file},180000);
      }
      const done=await boundedRequest('/api/neurovision/import-jobs/'+currentJob+'/finalize?mode=active',{method:'POST',headers:{'X-NeuroAccess-Request':'1'}},18000);
      if((await done.json()).state!=='queued')throw Error('The server could not finalize mask/labels upload.');
    }
    sessionStorage.setItem('nv_import_job',currentJob);
    importMessage('Step 3/3: Image uploaded. Waiting for MRI preparation worker…');
    await pollJob();
  }catch(e){
    importMessage(e.message+(currentJob?' Existing import job: '+currentJob.slice(0,8)+'. Click Check import status; do not blindly create more jobs.':''),'error');
    $('importSubmit').disabled=false;
  }finally{submittingImport=false;if(!currentJob)$('importSubmit').disabled=false}
};
function configureImportMode(){
 const demo=$('mode').value==='demo';
 $('importForm').hidden=demo;
 $('refreshPreview').hidden=demo;
 $('importRetry').hidden=demo;
 $('workerStatus').textContent=demo
   ?'Synthetic demo: read-only mathematical phantom. No real MRI upload or clinical result.'
   :'Checking signed-in account imaging worker and available import jobs…';
}
configureImportMode();
const remembered=sessionStorage.getItem('nv_import_job');
if($('mode').value==='active'&&remembered&&/^[0-9a-f]{32}$/.test(remembered)){currentJob=remembered;importMessage('Resuming status check for the previous MRI import…');void pollJob()}
if($('mode').value==='active')workerStatus();setInterval(()=>{if(!document.hidden&&$('mode').value==='active')workerStatus()},15000);
