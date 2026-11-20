'use strict';
// Independent account-owned RESEARCH workspace. Never writes or links participant identities.
(() => {
  function mountResearchPreview() {
  const host = document.getElementById('anatomical');
  if (!host || document.getElementById('researchPreview2D')) return;
  const panel = document.createElement('section'); panel.id='researchPreview2D';
  panel.style.cssText='margin:16px 0;border:1px solid #80a5ae;border-radius:12px;padding:16px';
  const heading=document.createElement('h3');heading.textContent='Independent research MRI preview · Phase 2D';
  const note=document.createElement('p');note.textContent='Separate account-owned research acquisitions. Viewing a research scan does NOT link it to this participant or add a verified MRI visit. No clinical interpretation or longitudinal inference.';
  const controls=document.createElement('div');controls.style.cssText='display:flex;flex-wrap:wrap;gap:10px;align-items:center';
  const load=document.createElement('button');load.type='button';load.textContent='Load my research MRI catalog';
  const selector=document.createElement('select');selector.setAttribute('aria-label','Independent research acquisition');selector.disabled=true;
  const inspect=document.createElement('button');inspect.type='button';inspect.textContent='Inspect research QC';inspect.disabled=true;
  const open=document.createElement('a');open.textContent='Open MRI in NeuroVision';open.style.cssText='display:none;text-decoration:underline';
  const status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const details=document.createElement('div');
  const caution=document.createElement('p');caution.textContent='The personal NeuroTwin remains unchanged. Independent anatomical review is still required.';
  controls.append(load,selector,inspect,open);panel.append(heading,note,controls,status,details,caution);host.append(panel);
  const params=new URLSearchParams(location.search);
  const active=params.get('mode')==='active';
  const validID=id=>typeof id==='string'&&/^[a-f0-9]{24}$/.test(id);
  function message(text){status.textContent=text;}
  function item(label,value){const p=document.createElement('p');const strong=document.createElement('strong');strong.textContent=label+': ';p.append(strong,document.createTextNode(String(value)));details.append(p);}
  async function request(url){const c=new AbortController();const timer=setTimeout(()=>c.abort(),20000);try{const r=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{'X-NeuroAccess-Request':'1'},signal:c.signal});const data=await r.json().catch(()=>({detail:'Invalid JSON'}));if(!r.ok)throw Error('HTTP '+r.status+': '+(typeof data.detail==='string'?data.detail:'Request rejected'));return data;}finally{clearTimeout(timer);}}
  function choice(){const id=selector.value;const ok=validID(id);inspect.disabled=!ok;open.style.display=ok?'inline':'none';if(ok){const u=new URL('/neurovision',location.origin);u.searchParams.set('mode','active');u.searchParams.set('scan',id);open.href=u.pathname+u.search;}else open.removeAttribute('href');details.replaceChildren();}
  selector.addEventListener('change',choice);
  load.addEventListener('click',async()=>{
    if(!active){message('Active research workspace required; this panel never queries or displays synthetic data.');return;}
    load.disabled=true;inspect.disabled=true;selector.disabled=true;selector.replaceChildren();details.replaceChildren();open.style.display='none';message('Loading account-owned research scans…');
    try{const data=await request('/api/neurovision/scans?mode=active');const scans=Array.isArray(data.items)?data.items:[];for(const s of scans){if(!validID(s.id))continue;const option=document.createElement('option');option.value=s.id;option.textContent=[s.cohort,s.subject,s.visit,s.id.slice(0,8)].filter(Boolean).join(' / ');selector.append(option);}selector.disabled=!selector.options.length;choice();message(selector.options.length?selector.options.length+' account-owned research scan(s) available. This is NOT a participant identity match.':'No account-owned prepared scans available.');}
    catch(e){message('Research catalog unavailable: '+e.message);}
    finally{load.disabled=false;}
  });
  inspect.addEventListener('click',async()=>{
    const id=selector.value;if(!validID(id))return;inspect.disabled=true;details.replaceChildren();message('Checking research evidence…');
    try{const d=await request('/api/neurovision/phase2c/evidence/'+encodeURIComponent(id)+'?mode=active');if(selector.value!==id)return;
      item('Research identity',[d.research_cohort,d.research_subject,d.research_visit].join(' / '));
      item('Saved package',d.package_integrity||'UNKNOWN');
      item('Retained MRI source',d.retained_input?.state||'UNKNOWN');
      item('Atlas regions',d.atlas_measurements?.region_count??'UNKNOWN');
      item('Measurement arithmetic',d.atlas_measurements?.state||'UNKNOWN');
      item('Technical QC',d.technical_qc?.state||'UNKNOWN');
      item('Anatomical review',d.review?.status||'UNKNOWN');
      item('Longitudinal eligible','NO — independent sample preview only');
      message('Research evidence loaded. Open NeuroVision for actual overlays and 3D surfaces; evidence is not anatomical approval.');
    }catch(e){message('Research evidence unavailable: '+e.message);}
    finally{inspect.disabled=false;}
  });
  }
  // NeuroTwin may construct or replace its anatomical tab after deferred scripts run.
  // Observe DOM changes, but never create duplicate preview panels.
  const observer = new MutationObserver(() => {
    if (document.getElementById('anatomical') &&
        !document.getElementById('researchPreview2D')) {
      mountResearchPreview();
    }
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});
  mountResearchPreview();
})();
