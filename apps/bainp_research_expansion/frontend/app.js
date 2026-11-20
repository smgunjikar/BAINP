'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const set = (id, value) => { $(id).textContent = value; };
  async function get(path) {
    const c=new AbortController(); const timer=setTimeout(()=>c.abort(),18000);
    try {
      const r=await fetch(path,{credentials:'same-origin',headers:{'X-NeuroAccess-Request':'1'},cache:'no-store',signal:c.signal});
      const d=await r.json().catch(()=>({detail:'Invalid JSON response'}));
      if(!r.ok)throw new Error('HTTP '+r.status+' · '+String(d.detail||'Request rejected'));
      return d;
    } finally {clearTimeout(timer);}
  }
  const show=(id, value)=>set(id,JSON.stringify(value,null,2));
  async function init() {
    try {
      const data=await get('/api/bainp-research/capabilities?mode=active');
      set('systemStatus','Authenticated research extension responding · code modules present, no dataset validation assumed');
      const g=$('phaseGrid');g.replaceChildren();
      for(const [name,rec] of Object.entries(data.phases||{})) {
        const e=document.createElement('article');const title=document.createElement('h3');title.textContent='Phase '+name;
        const p=document.createElement('p');p.textContent=rec.description;
        const status=document.createElement('small');status.textContent='Source: available · Dataset validation: not established';
        e.append(title,p,status);g.append(e);
      }
      const dep=Object.entries(data.dependencies||{}).map(([k,v])=>k+': '+(v?'installed':'not in this Python runtime')).join(' | ');
      set('dependencyGrid',dep);
    } catch(error) {set('systemStatus','Research status unavailable: '+error.message);}
  }
  $('catalog').addEventListener('click',async()=>{
    try {
      set('qc','Loading account-owned research catalog…');
      const data=await get('/api/neurovision/scans?mode=active');
      const rows=Array.isArray(data)?data:Array.isArray(data.scans)?data.scans:Array.isArray(data.items)?data.items:[];
      const sel=$('scan');sel.replaceChildren();
      const empty=new Option('Choose a prepared MRI','');sel.append(empty);
      for(const row of rows){
        if(!/^[a-f0-9]{24}$/.test(row.id||''))continue;
        const label=[row.cohort,row.subject,row.visit].filter(Boolean).join(' / ')||row.id;
        sel.append(new Option(label,row.id));
      }
      set('qc',sel.options.length>1?'Select a scan, then Inspect QC.':'No account-owned prepared scans returned.');
    }catch(e){set('qc','Research catalog unavailable: '+e.message);}
  });
  $('scan').addEventListener('change',()=>{
    const id=$('scan').value;const ok=/^[a-f0-9]{24}$/.test(id);
    $('inspect').disabled=!ok;
    $('openScan').href=ok?'/neurovision?mode=active&scan='+encodeURIComponent(id):'/neurovision?mode=active';
  });
  $('inspect').addEventListener('click',async()=>{
    try {
      const id=$('scan').value;if(!/^[a-f0-9]{24}$/.test(id))throw new Error('Select a prepared MRI first');
      const d=await get('/api/neurovision/phase2c/evidence/'+encodeURIComponent(id)+'?mode=active');
      show('qc',{research_cohort:d.research_cohort,research_subject:d.research_subject,
        scan_id:d.scan_id,package_integrity:d.package_integrity,source:d.retained_input?.state,
        region_count:d.atlas_measurements?.region_count,measurement_state:d.atlas_measurements?.state,
        review:d.review?.status,quality_flags:d.quality_flags,
        clinical_approval:false,auto_identity_link:false});
    }catch(e){set('qc','Research QC unavailable: '+e.message);}
  });
  $('personal').addEventListener('click',async()=>{
    const id=$('person').value.trim();
    if(!/^[0-9a-fA-F-]{36}$/.test(id)){set('personalResult','Enter a valid authorized participant UUID');return;}
    try {show('personalResult',await get('/api/bainp-research/participant/'+encodeURIComponent(id)+'/status?mode=active'));}
    catch(e){set('personalResult','Participant lookup unavailable: '+e.message);}
  });
  init();
})();
