/* NeuroVision V4: standalone enhancement, no read/write to unrelated participants. */
'use strict';
(() => {
  const el = (id) => document.getElementById(id);
  if (!el('analysisStudio')) return;
  const write = (message) => { el('analysisProgress').textContent = String(message); };
  const request = async (url, method = 'GET') => {
    const response = await fetch(url, {
      method, cache:'no-store',
      headers: {'X-NeuroAccess-Request':'1'}, credentials:'same-origin'
    });
    let result;
    try { result = await response.json(); }
    catch { throw Error('The BAINP API returned a non-JSON response (HTTP '+response.status+').'); }
    if (!response.ok) throw Error('HTTP '+response.status+': '+String(result.detail || 'request failed'));
    return result;
  };
  const api = (p) => '/api/neurovision/' + p + (p.includes('?') ? '&' : '?') + 'mode=active';
  let caps = null, busy = false;
  async function readiness() {
    if (el('mode').value !== 'active') {
      el('synthsegState').textContent = 'Synthetic demo is read-only.';
      el('runSynthseg').disabled = true;
      el('runWmh').disabled = true;
      el('wmhState').textContent='Synthetic demo is read-only.';
      return;
    }
    try {
      caps = await request(api('analysis-capabilities'));
      const ready = caps.worker_online && caps.synthseg_installed;
      el('synthsegState').textContent = !caps.worker_online ? 'Imaging worker offline' :
        !caps.worker_compatible ? 'Restart worker with installed V4 code' :
        ready ? 'SynthSeg installed · review required' : 'SynthSeg not installed in worker environment';
      el('runSynthseg').disabled = !ready || busy;
      el('runWmh').disabled = !caps.worker_compatible || !caps.wmh_synthseg_installed || busy;
      el('wmhState').textContent = !caps.worker_compatible ? 'V5 worker required' : caps.wmh_synthseg_installed ? 'External WMH-SynthSeg found · results unreviewed' : 'External WMH-SynthSeg unavailable';
      el('atlasState').textContent = 'A real labelmap is required. MRI intensity is not a labelmap.';
      if (!ready) write('Install an appropriate FreeSurfer/SynthSeg environment first. No model is bundled or downloaded automatically.');
    } catch (err) { el('runSynthseg').disabled=true;el('runWmh').disabled=true;write(err.message); }
  }
  async function monitor(id) {
    for (let n=0; n<360; n++) {
      const d=await request(api('import-jobs/'+encodeURIComponent(id)));
      write('Segmentation job '+id.slice(0,8)+' · '+d.state+' · original scan remains unchanged');
      if (d.state==='complete') {
        if(!/^[a-f0-9]{24}$/.test(d.package_id||'')) throw Error('Worker completed without a valid package ID');
        write('External model output prepared. Anatomical QC is still required. Loading derived overlays…');
        const u=new URL(location.href);u.searchParams.set('scan',d.package_id);location.assign(u.href);return;
      }
      if (d.state==='failed'||d.state==='cancelled') throw Error('Job '+d.state+': '+String(d.error||'inspect worker log'));
      await new Promise(resolve=>setTimeout(resolve,2000));
    }
    throw Error('No completion within the monitoring window. The job remains queued; check its status without resubmitting.');
  }
  el('runSynthseg').addEventListener('click', async () => {
    if (busy || el('mode').value!=='active') return;
    const scan=el('scans')?.value;
    if (!/^[a-f0-9]{24}$/.test(scan||'')) { write('Select a prepared active MRI first.'); return; }
    if (!confirm('Run installed SynthSeg on the selected retained MRI? This is research-only; no diagnosis or automatic identity linkage.')) return;
    busy=true;el('runSynthseg').disabled=true;
    try {
      write('Requesting model preparation from authorized source…');
      const job=await request(api('analysis-jobs/from-scan/'+scan),'POST');
      if(!/^[a-f0-9]{32}$/.test(job.id)) throw Error('Invalid job identifier from backend');
      await monitor(job.id);
    } catch(err) { write(err.message); }
    finally { busy=false;await readiness(); }
  });
  function displayScan({metadata:m,surfaceCount}) {
    const real = m.synthetic === false;
    const labels = (m.measurements || []).filter(x=>/^\d+$/.test(String(x.id)));
    const hasLabels = labels.length > 0;
    const qc = m.v5_technical_qc || null;
    el('v5ScanStatus').textContent = (real ? 'Real authorized research acquisition' : 'Synthetic demo only') + ' · ' + (m.modality || 'unknown');
    el('v5LabelStatus').textContent = hasLabels ? labels.length + ' label ID(s) measured' : 'Unavailable: run segmentation first';
    el('v5QcStatus').textContent = qc ? 'Technical QC performed · anatomical review pending' : 'No V5 technical QC on this package';
    el('v5TwinStatus').textContent = real ? 'Explicit identity verification required in NeuroTwin' : 'Demo never linked to a person';
    el('v5AtlasSummary').textContent = hasLabels ?
      'Measured volumes in native MRI grid; display is not diagnostic and label identities require QC.' :
      'This acquisition is an MRI intensity volume. No atlas or brain extraction labelmap has been accepted.';
    const root = el('v5RegionList');root.replaceChildren();
    if(hasLabels){
      for(const x of labels.slice(0,20)){
        const line=document.createElement('div');line.className='v5RegionRow';
        const name=document.createElement('span');name.textContent=x.name;
        const volume=document.createElement('strong');volume.textContent=Number(x.volume_ml).toFixed(2)+' mL';
        line.append(name,volume);root.append(line);
      }
      if(labels.length>20){const more=document.createElement('p');more.textContent='Showing 20 of '+labels.length+' regions; full values appear in the native-grid measurement table.';root.append(more);}
    } else {const missing=document.createElement('p');missing.textContent='No computed anatomical volumes. The raw 3D intensity preview is not a brain segmentation.';root.append(missing);}
    if(qc?.warnings?.length)el('v5QcStatus').textContent += ' · '+qc.warnings.join(', ');
    if(!real)el('runSynthseg').disabled=true;
  }
  document.addEventListener('bainp:neurovision:scan-loaded',event=>displayScan(event.detail));
  async function updateModuleReadiness(){
    if(el('mode').value==='demo'){
      el('v5ModuleStatus').textContent='DEMO: mathematical phantom; do not infer clinical anatomy.';return;
    }
    try {
      const d=await request(api('analysis-capabilities'));
      const modules=[
        ['Anatomical segmentation',d.synthseg_installed&&d.worker_compatible?'MODEL AVAILABLE':'MODEL / WORKER REQUIRED'],
        ['WMH-SynthSeg',d.wmh_synthseg_installed?'EXTERNAL MODEL READY · QC REQUIRED':'MODEL NOT INSTALLED'],
        ['Longitudinal registration','SECOND VERIFIED VISIT + LOCAL SCIENTIFIC TOOL REQUIRED'],
        ['PET quantification','PET AND COREGISTERED ROIS REQUIRED'],
        ['Normative references','DOCUMENTED REFERENCE DATA REQUIRED'],
        ['Electrical-field simulation','SIMNIBS MODEL AND SPECIALIST PROTOCOL REQUIRED']
      ];
      const box=el('v5ModuleStatus');box.replaceChildren();
      for(const [name,state] of modules){const row=document.createElement('div');row.className='v5ModuleRow';const a=document.createElement('span');a.textContent=name;const b=document.createElement('strong');b.textContent=state;row.append(a,b);box.append(row);}
    }catch(err){el('v5ModuleStatus').textContent='Research engine status unavailable: '+err.message;}
  }
  document.addEventListener('bainp:neurovision:scan-loaded',()=>void updateModuleReadiness());
  el('mode').addEventListener('change',()=>void updateModuleReadiness());
  void updateModuleReadiness();
  el('runWmh').addEventListener('click', async () => {
    if (busy || el('mode').value !== 'active') return;
    const scan=el('scans')?.value;
    if (!/^[a-f0-9]{24}$/.test(scan||'')) {write('Select a retained authorized MRI first.');return;}
    if (!confirm('Run the installed WMH-SynthSeg research model? Its outputs are unreviewed segmentation labels, NOT a diagnosis or pathology confirmation.')) return;
    busy=true;el('runWmh').disabled=true;el('runSynthseg').disabled=true;
    try{
      write('Requesting WMH-SynthSeg on retained MRI…');
      const job=await request(api('analysis-jobs/from-scan/'+scan+'?model=wmh-synthseg'),'POST');
      if(!/^[a-f0-9]{32}$/.test(job.id))throw Error('Invalid job identifier.');
      await monitor(job.id);
    }catch(err){write(err.message);}
    finally{busy=false;await readiness();}
  });
  el('mode').addEventListener('change',readiness);
  void readiness();
})();
