(()=>{
'use strict';
const key='bainp.workspace.return.v1',root=location.pathname==='/',local=u=>u.origin===location.origin;
function valid(value){try{const u=new URL(value,location.origin);return local(u)&&u.pathname==='/'&&u.hash.startsWith('#/workspace')?u:null;}catch{return null;}}
function remember(){if(!root||!location.hash.startsWith('#/workspace'))return;try{sessionStorage.setItem(key,location.pathname+location.search+location.hash);}catch{}}
function fallback(){const q=new URLSearchParams(location.search),p=new URLSearchParams();for(const k of ['mode','person','checkin'])if(q.has(k))p.set(k,q.get(k));return '/?'+p+'#/workspace';}
function returnPath(){try{const u=valid(sessionStorage.getItem(key));if(u){const current=new URLSearchParams(location.search);for(const k of ['mode','person'])if(current.has(k)&&u.searchParams.get(k)!==current.get(k))return fallback();return u.pathname+u.search+u.hash;}}catch{}return fallback();}
function patch(){if(root){remember();return;}for(const a of document.querySelectorAll('a[href]')){let u;try{u=new URL(a.getAttribute('href'),location.href);}catch{continue;}if(local(u)&&u.pathname==='/'&&(!u.hash||u.hash.startsWith('#/workspace'))){a.href=returnPath();a.title='Return to your workspace with context';}}}
document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a||e.defaultPrevented)return;if(root)remember();else patch();},true);
window.addEventListener('hashchange',remember);window.addEventListener('pagehide',remember);window.addEventListener('pageshow',patch);
if(!root){const cognitive=/^\/cognition(?:$|-)/.test(location.pathname)||location.pathname==='/neurosense';if(!cognitive)document.documentElement.classList.add('bainp-unified');const bar=document.createElement('div');bar.className='bainp-return-bar';const link=document.createElement('a');link.textContent='Return to workspace';link.href=returnPath();bar.append(link);document.body.prepend(bar);}
new MutationObserver(patch).observe(document.body,{childList:true,subtree:true});patch();
})();

// Common cross-module shell. Stores navigation URLs, never observations or responses.
(()=>{
 const allowed=new Set(['/','/neurocontinuum','/neuroquest','/cognition','/cognition-dashboard','/cognition-results','/sense-monitor','/neurosense','/neurotwin','/neuroshadow','/neuromimic','/careloop','/neuroproof','/neurograph','/neuroguard','/neurovision','/neuropulse','/brain-body','/neurosim','/arena','/platform-core']);
 const key='bainp.previous.route.v2',here=()=>location.pathname+location.search+location.hash;
 const safe=value=>{try{const u=new URL(value,location.origin);return u.origin===location.origin&&allowed.has(u.pathname)?u:null;}catch{return null;}};
 function contextMatches(u){const q=new URLSearchParams(location.search);for(const k of ['mode','person'])if(q.has(k)&&u.searchParams.has(k)&&q.get(k)!==u.searchParams.get(k))return false;return true;}
 function prior(){try{const u=safe(sessionStorage.getItem(key));return u&&contextMatches(u)&&u.pathname+u.search+u.hash!==here()?u:null;}catch{return null;}}
 function destination(path){const p=new URLSearchParams(location.search),q=new URLSearchParams();for(const k of ['mode','person','checkin'])if(p.has(k))q.set(k,p.get(k));return path+'?'+q;}
 document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a||e.defaultPrevented||a.dataset.flowBack)return;const u=safe(a.href);if(!u||u.pathname+u.search+u.hash===here())return;try{sessionStorage.setItem(key,here());}catch{}},true);
 function mount(){const root=location.pathname==='/';if(root){document.getElementById('bainp-flow-shell')?.remove();return;}if(document.getElementById('bainp-flow-shell'))return;
 const bar=document.createElement('nav');bar.id='bainp-flow-shell';bar.setAttribute('aria-label','Connected BAINP workflow');
 const brand=document.createElement('strong');brand.textContent='bainp';bar.append(brand);
 const back=document.createElement('a');back.dataset.flowBack='1';back.textContent='Back';const previous=prior();back.href=previous?previous.pathname+previous.search+previous.hash:destination('/')+'#/workspace';back.addEventListener('click',()=>{try{sessionStorage.removeItem(key);}catch{}});bar.append(back);
 for(const [name,path]of [['Workspace','/'],['My Brain Health','/'],['Assessment selection','/neuroquest'],['Monitoring','/sense-monitor'],['Review','/careloop'],['Evidence','/neuroproof']]){const a=document.createElement('a');a.textContent=name;a.href=destination(path)+(path==='/'?(name==='My Brain Health'?'#/journey':'#/workspace/home'):'');if(location.pathname===path)a.setAttribute('aria-current','page');bar.append(a);}
 const q=new URLSearchParams(location.search),badge=document.createElement('span');badge.className='flow-context';badge.textContent=(q.get('mode')==='demo'?'Demo':'Active')+(q.get('person')?' · Participant '+q.get('person').slice(0,8):' · Participant context in module');bar.append(badge);
 document.querySelector('.bainp-return-bar')?.remove();document.body.prepend(bar);
 }
 window.addEventListener('hashchange',()=>{document.getElementById('bainp-flow-shell')?.remove();mount();});mount();
})();
