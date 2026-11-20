const {JSDOM}=require('jsdom'),fs=require('fs'),assert=require('assert');
const path=__dirname+'/payload/apps/';
const dom=new JSDOM('<div id="app"></div><div id="toast"></div><dialog id="detail"><div id="dialog-content"></div><button id="close-dialog">Close</button></dialog><button data-action="start">Start</button>',{url:'http://127.0.0.1:3000/neurocontinuum?mode=active&person=alice',runScripts:'outside-only'});
const win=dom.window;win.HTMLDialogElement.prototype.showModal=function(){this.open=true};
let script=fs.readFileSync(path+'neurocontinuum/frontend/app.js','utf8').replace(/load\(\)\.catch\(showError\);\s*$/,'');
win.eval(script+`;render=()=>{};w={consent:{enabled:true},sessions:[],checkins:[]};window.denyConsent=()=>{w.consent.enabled=false;};`);
win.document.querySelector('[data-action=start]').click();
assert(win.document.querySelector('dialog').open);assert(!win.document.querySelector('select'));
const a=win.document.querySelector('#dialog-content a'),u=new URL(a.href);assert.equal(u.hash,'#/journey');assert.equal(u.searchParams.get('person'),'alice');assert.equal(u.searchParams.get('journey_step'),'accessibility');
// Shared navigation must not rewrite the explicit preparation link.
win.eval(fs.readFileSync(path+'neuroaccess/web/shared-navigation.js','utf8'));assert.equal(new URL(a.href).hash,'#/journey');
win.denyConsent();win.document.querySelector('dialog').open=false;win.document.querySelector('[data-action=start]').click();assert(!win.document.querySelector('dialog').open);
const main=fs.readFileSync(path+'neuroaccess/web/app.js','utf8');assert(main.includes("href:route('/')+'#/journey'},text('Open monitoring session'"));assert(main.includes("if(params.get('person'))await loadPerson(params.get('person'))"));
console.log('PASS empty-checkin recovery, participant-preserving deep link, shared-navigation compatibility, consent prerequisite and overview routing');win.close();
