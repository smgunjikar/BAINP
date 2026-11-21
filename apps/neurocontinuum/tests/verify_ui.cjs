/* Run with JSDOM_PATH=/absolute/path/to/jsdom node .../tests/verify_ui.cjs.
   DOM behavior tests, not a browser layout or clinical validation. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require(process.env.JSDOM_PATH||'jsdom');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'frontend/app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'frontend/index.html'),'utf8').replace(/<script[^>]*><\/script>/g,'').replace(/<link[^>]*>/g,'');
const pid='11111111-1111-4111-8111-111111111111';
const wait=()=>new Promise(r=>setTimeout(r,25));
function start({checks=[],experience=false,auth=true,action={kind:'checkin',title:'Complete preparation',reason:'No eligible preparation.'}}={}){
 const errors=[],calls=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
 const dom=new JSDOM(html,{url:'http://127.0.0.1:3000/neurocontinuum?person='+pid+(experience?'&experience=participant':''),runScripts:'outside-only',virtualConsole:vc});
 const win=dom.window;win.HTMLDialogElement.prototype.showModal=function(){this.open=true};win.HTMLDialogElement.prototype.close=function(){this.open=false};
 const state={action};const workspace={participant_id:pid,display_name:'Test person',profile_revision:2,preferences:{language:'en'},sessions:[],checkins:checks,cases:[],observation_references:[],modules:[],consent:{revision:1,enabled:true,assessment_allowed:true,case_tracking:false}};
 win.fetch=async(url,opt={})=>{calls.push({url,opt});let data={};let code=200;
  if(url==='/api/session'&&!auth){code=401;data={detail:'Sign in'};}
  else if(url.endsWith('/status'))data={version:'test',modules:[],guard_connected:true,careloop_connected:true};
  else if(url.startsWith('/api/participants?'))data={items:[{id:pid,profile:{display_name:'Test person'}}]};
  else if(url.includes('/workspace?'))data=workspace;
  else if(url.includes('/next-action?'))data={next_action:state.action};
  else if(url.includes('/participant-home/participants/'))data={participant:{id:pid,revision:2,profile:{display_name:'Test person'}},onboarding:{version:0,answers:{}},next_action:{kind:'onboarding',step:'welcome'},workspace,shadow:{available:false}};
  return {ok:code===200,status:code,json:async()=>data};};
 const css=win.document.createElement('style');css.textContent=fs.readFileSync(path.join(root,'frontend/style.css'),'utf8');win.document.head.append(css);
 win.eval(source);return {dom,win,state,errors,calls};
}
(async()=>{
 let t=start();await wait();assert.match(t.win.document.body.textContent,/My Brain Health/);t.win.document.querySelector('[data-action=start]').click();await wait();assert.match(t.win.document.querySelector('#dialog-content').textContent,/No completed check-in/);assert.match(t.win.document.querySelector('#dialog-content a').href,/experience=participant#checkin/);assert.equal(t.errors.length,0);t.dom.window.close();
 t=start({checks:[{id:'old',status:'completed',participant_revision:1},{id:'unfinished',status:'pending',participant_revision:2},{id:'ready',status:'completed',participant_revision:2}]});await wait();t.win.document.querySelector('[data-action=start]').click();await wait();assert.deepEqual([...t.win.document.querySelectorAll('#checkin-choice option')].map(o=>o.value),['ready']);t.dom.window.close();
 t=start({action:{kind:'assessment',title:'Open assessment',reason:'Saved suggestion',url:'/cognition?checkin=old'}});await wait();t.state.action={kind:'consent',title:'Review consent',reason:'Withdrawn'};t.win.document.querySelector('[data-action=next-action]').click();await wait();assert.match(t.win.document.querySelector('main').textContent,/Consent, before coordination/);assert.equal(t.calls.filter(c=>c.opt.method==='POST').length,0);assert.equal(t.errors.length,0);t.dom.window.close();
 t=start({experience:true,auth:false});await wait();assert.match(t.win.document.body.textContent,/Go to secure sign in/);assert.equal(t.win.document.querySelector('input[type=password]'),null);assert.equal(t.errors.length,0);t.dom.window.close();
 t=start({experience:true});await wait();assert.match(t.win.document.body.textContent,/Welcome, Test person/);assert.equal(t.win.document.body.classList.contains('participant-experience'),true);assert.equal(t.errors.length,0);t.dom.window.close();
 console.log('PASS 5 DOM scenarios: empty preparation, current completed selection, fresh consent decision, host sign-in, participant home; CSS parsed without errors.');
})().catch(e=>{console.error(e);process.exitCode=1});
