"use strict";
(() => {
  const $=id=>document.getElementById(id);
  if (!$('p2bAttach')) return;
  let busy=false;
  const mode=()=>$('mode').value;
  const selected=()=>$('scans').value;
  const status=(s)=>{$('p2bStatus').textContent=s;};
  async function call(path,options={},timeoutMs=30000){
    const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),timeoutMs);
    try{
      const r=await fetch('/api/neurovision/'+path+(path.includes('?')?'&':'?')+'mode=active',{
        cache:'no-store',credentials:'same-origin',...options,signal:controller.signal,
        headers:{'X-NeuroAccess-Request':'1',...(options.headers||{})}});
      let obj; try{obj=await r.json()}catch{obj={detail:'Expected JSON from BAINP API'};}
      if(!r.ok)throw Error('HTTP '+r.status+': '+String(obj.detail||'Request failed'));
      return obj;
    }catch(err){if(err.name==='AbortError')throw Error('Request timed out. Existing job may still be queued: check its ID before resubmitting.');throw err;}
    finally{clearTimeout(timer);}
  }
  async function selectedMetadata(){
    if(mode()!=='active'|| !/^[a-f0-9]{24}$/.test(selected()||''))throw Error('Select a real active MRI first. Demo scans cannot be used.');
    const d=await call('scans/'+encodeURIComponent(selected()));
    if(d.metadata.synthetic!==false)throw Error('Synthetic/demo MRI is not eligible.');
    if(!/^[a-f0-9]{64}$/.test(d.metadata.source_sha256?.image||''))throw Error('Stored scan is missing a valid original SHA-256.');
    return d.metadata;
  }
  async function sha(file){
    if(!globalThis.crypto?.subtle)throw Error('Secure browser SHA-256 is unavailable. Use local localhost browser.');
    const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
    return [...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
  }
  const controls=['p2bAttach','p2bCheck','p2bReviewRequest','p2bReject'];
  function setBusy(v){busy=v;for(const id of controls)$(id).disabled=v;}
  async function monitor(id){
    for(let n=0;n<360;n++){
      const d=await call('import-jobs/'+id,{},16000);
      status('Job '+id.slice(0,8)+' · '+d.state+(d.error?' · '+d.error:''));
      if(d.state==='complete'){
        if(!/^[a-f0-9]{24}$/.test(d.package_id||''))throw Error('Completed without valid package ID');
        status('Source-linked segmentation prepared. Anatomical QC pending. Opening new reviewed-package view…');
        const u=new URL(location.href);u.searchParams.set('scan',d.package_id);location.assign(u.href);return;
      }
      if(d.state==='failed'||d.state==='cancelled')throw Error('Derived job '+d.state+': '+(d.error||'see imaging-worker log'));
      await new Promise(ok=>setTimeout(ok,2000));
    }
    throw Error('Job still processing after monitoring window. Use the job ID in the status; do not upload again.');
  }
  $('p2bAttach').onclick=async()=>{
    if(busy)return;
    setBusy(true);
    try{
      const m=await selectedMetadata();
      const original=$('p2bOriginal').files[0],labels=$('p2bLabels').files[0];
      if(!original||!labels)throw Error('Select both the original MRI and the separate SynthSeg segmentation file.');
      if(original.size>64*1048576||labels.size>64*1048576)throw Error('Maximum file size is 64 MiB each.');
      if(original.name===labels.name && original.size===labels.size)throw Error('The original MRI cannot be submitted as a segmentation.');
      if(!$('p2bAttest').checked)throw Error('Confirm source correspondence and authorization.');
      status('Hash-verifying source MRI locally; no source bytes are uploaded…');
      const h=await sha(original);
      if(h!==m.source_sha256.image)throw Error('Source MRI hash mismatch. Select the exact original MRI from the same BAINP acquisition. Nothing uploaded.');
      const labelHash=await sha(labels);
      if(h===labelHash)throw Error('Segmentation is byte-identical to MRI; select actual SynthSeg labelmap.');
      const id=selected();status('Creating a derived analysis job from retained MRI…');
      const job=await call('import-jobs/from-scan/'+id+'/labels',{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_source_sha256:h,attested_same_research_acquisition:true})});
      if(!/^[a-f0-9]{32}$/.test(job.id))throw Error('Invalid job ID');
      sessionStorage.setItem('nv_import_job',job.id);
      status('Uploading labelmap to job '+job.id.slice(0,8)+'; physical-space alignment happens in the worker…');
      await call('import-jobs/'+job.id+'/aux/labels',{method:'PUT',headers:{'Content-Type':'application/octet-stream'},body:labels},180000);
      await call('import-jobs/'+job.id+'/finalize',{method:'POST'},20000);
      status('Segmentation queued; source retained · job '+job.id);
      await monitor(job.id);
    }catch(e){status('Action failed: '+e.message);}
    finally{setBusy(false);}
  };
  async function review(){
    const m=await selectedMetadata();const d=await call('import-jobs/reviews/'+selected());
    $('p2bReview').textContent='Review: '+d.review+' · Anatomical atlas labels: '+(d.has_real_atlas_labels?'present':'missing')+
      ' · Technical QC: '+(d.technical_qc?.state||'not performed')+
      ' · Longitudinal trend eligible: NO. '+d.note;
  }
  $('p2bCheck').onclick=async()=>{try{await review()}catch(e){status(e.message);}};
  async function record(disposition){
    if(busy)return;
    setBusy(true);
    try{
      await selectedMetadata();const note=$('p2bReviewNote').value.trim();
      if(note.length<15)throw Error('Describe your QC finding in at least 15 characters.');
      if(!confirm('Record '+disposition+' as an auditable research review event?'))return;
      await call('import-jobs/reviews/'+selected(),{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({disposition,note})});
      status('QC event recorded; this is not clinical approval.');await review();
    }catch(e){status(e.message);}
    finally{setBusy(false);}
  }
  $('p2bReviewRequest').onclick=()=>record('NEEDS_REVIEW');
  $('p2bReject').onclick=()=>record('REJECTED');
  $('mode').addEventListener('change',()=>{if(mode()==='demo')status('Demo scans are read-only and cannot receive human MRI labels.');});
  $('scans').addEventListener('change',()=>{ $('p2bReview').textContent='';status('Selected a different scan; confirm the original MRI and labelmap.'); });
  if(mode()==='demo')status('Demo is read-only. Switch to Authorized research scans.');
})();
