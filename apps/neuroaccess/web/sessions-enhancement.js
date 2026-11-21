/* Sessions-only progressive enhancement; original BAINP JS remains authoritative. */
(()=>{
  'use strict';
  const routeIsSessions=()=>/^#\/workspace\/sessions(?:[/?]|$)/.test(location.hash);
  let busy=false;
  function enhance(){
    if(busy)return;
    busy=true;
    try{
      const active=routeIsSessions();
      document.body.classList.toggle('bainp-sessions-upgraded',active);
      if(!active)return;
      const app=document.querySelector('#app');
      if(!app)return;
      const grid=app.querySelector('.module-grid');
      const input=app.querySelector('input[type="search"][placeholder]');
      const main=grid?.closest('main')||grid?.parentElement;
      if(!grid||!input||!main)return;
      grid.classList.add('sessions-grid-enhanced');
      if(!main.querySelector('.sessions-intro')){
        const hero=document.createElement('section');
        hero.className='sessions-intro';
        hero.setAttribute('aria-label','Sessions introduction');
        const copy=document.createElement('div');
        const kicker=document.createElement('p');kicker.className='sessions-kicker';kicker.textContent='BAINP · YOUR WORKSPACES';
        const heading=document.createElement('h2');heading.textContent='Continue your brain-health journey';
        const description=document.createElement('p');description.textContent='Open your connected workflow, review your next assessment, or continue an available cognitive session.';
        copy.append(kicker,heading,description);
        const number=document.createElement('div');number.className='sessions-count';
        const value=document.createElement('strong');value.textContent=String(grid.querySelectorAll('.module-tile').length);
        const legend=document.createElement('span');legend.textContent='available workspaces';
        number.append(value,legend);hero.append(copy,number);
        main.insertBefore(hero,input);
      }
      if(!input.closest('.sessions-search-bar')){
        const wrap=document.createElement('div');wrap.className='sessions-search-bar';
        const label=document.createElement('label');label.textContent='FIND A WORKSPACE';
        if(!input.id)input.id='bainp-sessions-search';label.htmlFor=input.id;
        input.parentNode.insertBefore(wrap,input);wrap.append(label,input);
        const note=document.createElement('p');note.className='sessions-search-note';note.textContent='Search the workspaces available to your account. Access and results remain controlled by BAINP.';
        wrap.append(note);
      }
      // All links, search handlers, permissions, and statuses are supplied by original app.js.
    } finally {busy=false;}
  }
  let scheduled=false;
  function requestEnhance(){if(scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;enhance();});}
  const observer=new MutationObserver((mutations)=>{
    if(mutations.some(m=>m.target.closest?.('.sessions-intro,.sessions-search-bar')||false))return;
    requestEnhance();
  });
  function start(){observer.observe(document.querySelector('#app')||document.body,{childList:true,subtree:true});requestEnhance();}
  window.addEventListener('hashchange',requestEnhance);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
