'use strict';
(() => {
  const $ = id => document.getElementById(id);
  if (!$('phase2cSection')) return;
  let latest = null, serial = 0;
  const selected = () => $('scans')?.value;
  const active = () => $('mode')?.value === 'active';
  const message = txt => { $('p2cStatus').textContent = txt; };
  const add = (parent, text) => { const p=document.createElement('p');p.textContent=text;parent.append(p); };
  async function api(resource, options={}) {
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),20000);
    try {
      const res=await fetch('/api/neurovision/phase2c/'+resource+'?mode=active',{
        cache:'no-store', credentials:'same-origin', ...options, signal:controller.signal,
        headers:{'X-NeuroAccess-Request':'1',...(options.headers||{})}
      });
      const data=await res.json().catch(()=>({detail:'Non-JSON BAINP response'}));
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${typeof data.detail==='string'?data.detail:'Request failed'}`);
      return data;
    } finally {clearTimeout(timer);}
  }
  function render(d) {
    const target=$('p2cEvidence');target.replaceChildren();
    add(target,`Package integrity: ${d.package_integrity} · source recheck: ${d.retained_input.state}`);
    add(target,`Atlas label regions: ${d.atlas_measurements.region_count} · region-volume arithmetic: ${d.atlas_measurements.state}`);
    add(target,`Worker technical QC: ${d.technical_qc.state || 'NOT_RECORDED'} · Anatomical review: ${d.review.status}`);
    add(target,`Native grid: ${(d.geometry.native_shape||[]).join(' × ')} · labels present: ${d.labels_present?'yes':'no'}`);
    add(target,`QC flags: ${d.quality_flags.length?d.quality_flags.join(', '):'No automated flags recorded'}`);
    add(target, 'No clinical approval, pathology inference, or longitudinal eligibility is granted.');
    latest=d;
    $('p2cExport').disabled=false;
  }
  async function load() {
    const token=++serial;
    latest=null;$('p2cExport').disabled=true;$('p2cEvidence').replaceChildren();
    if(!active()|| !/^[a-f0-9]{24}$/.test(selected()||'')){
      message('Choose a real account-owned MRI in Authorized research scans. Demo is excluded.');return;
    }
    message('Verifying saved package and retained input provenance…');
    try {
      const evidence=await api('evidence/'+encodeURIComponent(selected()));
      if(token!==serial)return;
      render(evidence);message('Phase 2C evidence refreshed. Human anatomical QC remains required.');
    } catch(err){if(token===serial)message('Evidence unavailable: '+err.message);}
  }
  $('p2cLoad').addEventListener('click',load);
  document.addEventListener('bainp:neurovision:scan-loaded',()=>void load());
  $('mode').addEventListener('change',()=>void load());
  $('scans').addEventListener('change',()=>{serial++;latest=null;$('p2cExport').disabled=true;message('MRI selection changed. Reload evidence for that exact acquisition.');});
  $('p2cExport').addEventListener('click',()=>{
    if(!latest)return;
    const blob=new Blob([JSON.stringify(latest,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;
    anchor.download='BAINP_Phase2C_'+latest.scan_id+'.json';anchor.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $('p2cReview').addEventListener('submit',async evt=>{
    evt.preventDefault();
    if(!latest||selected()!==latest.scan_id){message('Reload evidence for the selected MRI before writing a finding.');return;}
    const planes=['axial','coronal','sagittal'].filter(p=>$('p2c_'+p).checked);
    if(!planes.length){message('Record which anatomical plane(s) you actually inspected.');return;}
    const note=$('p2cNote').value.trim();
    if(note.length<20){message('Describe findings or uncertainty in at least 20 characters.');return;}
    if(!$('p2cConfirm').checked){message('Confirm that this is research documentation, not medical approval.');return;}
    const payload={expected_package_sha256:latest.package_sha256,
      disposition:$('p2cDisposition').value, planes_inspected:planes,
      alignment:$('p2cAlignment').value,boundaries:$('p2cBoundaries').value,
      note,acknowledged_research_only:true};
    if(!confirm('Record this account-scoped QC finding? This cannot approve anatomy or trends.'))return;
    $('p2cSubmit').disabled=true;
    try {
      await api('reviews/'+encodeURIComponent(latest.scan_id),{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      message('Finding recorded in the existing imaging review audit. NeuroTwin linked views can display the review status.');
      await load();
    }catch(err){message('Finding not recorded: '+err.message);}
    finally{$('p2cSubmit').disabled=false;}
  });
})();
