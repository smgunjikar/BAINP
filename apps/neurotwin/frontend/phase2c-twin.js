'use strict';
(() => {
  const params = new URLSearchParams(location.search);
  const pid = params.get('person') || '';
  const real = params.get('mode')==='active' && /^[0-9a-f-]{36}$/i.test(pid);
  const panel = document.getElementById('anatomical');
  if (!panel) return;
  const box=document.createElement('section');box.id='p2cTwinEvidence';
  box.style.cssText='border:1px solid #7b9aaa;border-radius:10px;padding:14px;margin:18px 0;max-width:100%';
  const title=document.createElement('h3');title.textContent='Phase 2C · Source-linked imaging QC';
  const note=document.createElement('p');note.textContent='Only scans already linked to this participant through the verified identity workflow can appear here. Review is not clinical acceptance.';
  const button=document.createElement('button');button.type='button';button.textContent='Refresh linked imaging evidence';
  const listing=document.createElement('div');listing.setAttribute('role','status');listing.setAttribute('aria-live','polite');
  box.append(title,note,button,listing);panel.append(box);
  function line(text) {const p=document.createElement('p');p.textContent=text;listing.append(p);}
  async function request(path) {
    const response=await fetch(path,{cache:'no-store',credentials:'same-origin',headers:{'X-NeuroAccess-Request':'1'}});
    const body=await response.json().catch(()=>({detail:'Invalid JSON'}));
    if(!response.ok)throw Error('HTTP '+response.status+' · '+String(body.detail||'Request failed'));
    return body;
  }
  async function refresh() {
    listing.replaceChildren();
    if(!real){line('Active participant context required. Demo and unrelated scans are excluded.');return;}
    button.disabled=true;line('Checking linked imaging evidence…');
    try {
      const twin=await request('/api/neurotwin/participants/'+encodeURIComponent(pid)+'?mode=active');
      const images=Array.isArray(twin.imaging)?twin.imaging:[];
      listing.replaceChildren();
      if(!images.length){line('No verified MRI identity link yet. Use Evidence & NeuroCore → Verify a research imaging identity.');return;}
      for(const image of images.slice(0,20)){
        if(!/^[a-f0-9]{24}$/.test(image.id||''))continue;
        try {
          const qc=await request('/api/neurovision/phase2c/evidence/'+image.id+'?mode=active');
          line((image.metadata?.visit||'Unrecorded visit')+' · '+image.id.slice(0,8)+
            ' · package '+qc.package_integrity+
            ' · source '+qc.retained_input.state+
            ' · atlas regions '+qc.atlas_measurements.region_count+
            ' · review '+qc.review.status+
            ' · longitudinal eligible: NO');
        }catch(e){line('Linked scan '+image.id.slice(0,8)+' · Phase 2C evidence unavailable: '+e.message);}
      }
      if(images.length>20)line('Displaying the first 20 linked scans; open NeuroVision for additional evidence.');
    }catch(e){listing.replaceChildren();line('Linked evidence unavailable: '+e.message);}
    finally{button.disabled=false;}
  }
  button.addEventListener('click',()=>void refresh());
  void refresh();
})();
