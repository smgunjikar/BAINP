const fs=require('fs'),assert=require('assert'),{JSDOM}=require('jsdom');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function until(fn){for(let i=0;i<1000;i++){if(fn())return;await delay(5);}throw Error('UI timeout');}
async function setup(role='admin'){
 const dom=new JSDOM('<div id="app"></div>',{url:'http://127.0.0.1:3000/#/research-lab',runScripts:'outside-only'}),w=dom.window,calls=[];
 const source=fs.readFileSync(__dirname+'/../payload/apps/neuroaccess/web/research-ui.js','utf8');w.eval(source.replace('export function researchScreen','window.researchScreen=function'));const native=w.setTimeout.bind(w);w.setTimeout=(fn,ms,...args)=>native(fn,Math.min(ms,10),...args);
 function h(tag,attrs={},...children){const el=w.document.createElement(tag);for(const[k,v]of Object.entries(attrs)){if(k.startsWith('on'))el.addEventListener(k.slice(2).toLowerCase(),v);else if(['disabled','checked','required'].includes(k))el[k]=!!v;else el.setAttribute(k,v);}for(const child of children.flat(Infinity)){if(child==null||child===false)continue;el.append(child instanceof w.Node?child:w.document.createTextNode(String(child)));}return el;}
 const tasks={'spatial-sequence':{title:'Spatial sequence',domain:'Recall',instructions:'Recall',duration:'2 minutes'},'response-control':{title:'Respond or wait',domain:'Control',instructions:'Respond to GO',duration:'1 minute'},'paired-association':{title:'Symbol–location learning',domain:'Learning',instructions:'Remember locations',duration:'2 minutes'}};
 const plans={'spatial-sequence':{sequences:[[0,1],[1,2],[2,3,4],[3,4,5],[1,2,3,4],[2,3,4,5]]},'response-control':{go:[true,false,true,false],window_ms:1500,gap_ms:500},'paired-association':{pairs:[3,2,1,0],symbols:['★','◆','●','▲'],queries:[[0,1,2,3],[3,2,1,0]]}};
 const api=async(path,method='GET',body)=>{calls.push({path,method,body});if(path==='/session')return{role,workspace:'test'};if(path.includes('/catalogue'))return{tasks};if(path.includes('/start'))return{id:'run',task:body.task,plan:plans[body.task]};if(path.includes('/complete'))return{state:body.state,answers:body.answers};if(path.includes('/records'))return{items:[],has_more:false};throw Error('Unexpected '+path);};
 w.researchScreen({api,h});await delay(20);return{w,calls,plans,dom};
}
function click(w,text,n=0){const matches=[...w.document.querySelectorAll('button')].filter(x=>x.textContent===text);assert(matches[n],text);matches[n].click();}
(async()=>{
 let s=await setup('user');assert(s.w.document.body.textContent.includes('administrator-only'));assert(!s.calls.some(x=>x.path.includes('catalogue')));s.dom.window.close();
 for(let task=0;task<3;task++){
  s=await setup();const {w,calls,plans}=s;assert.equal([...w.document.querySelectorAll('button')].filter(x=>x.textContent==='Prepare task').length,3);click(w,'Prepare task',task);await delay(10);for(const input of w.document.querySelectorAll('input[type=checkbox]'))input.checked=true;click(w,'Start experimental task');
  if(task===0){for(let i=0;i<6;i++){await until(()=>w.document.body.textContent.includes('Repeat the sequence'));for(const cell of plans['spatial-sequence'].sequences[i])w.document.querySelector('[aria-label="Cell '+(cell+1)+'"]').click();await delay(15);}}
  if(task===2){for(const query of plans['paired-association'].queries){for(const symbol of query){await until(()=>w.document.querySelector('.stimulus')?.textContent===plans['paired-association'].symbols[symbol]);const buttons=w.document.querySelectorAll('.task-stage button');buttons[plans['paired-association'].pairs[symbol]].click();await delay(5);}}}
  await until(()=>w.document.body.textContent.includes('Measurement saved'));const completion=calls.filter(x=>x.path.includes('/complete'));assert.equal(completion.length,1);assert.equal(completion[0].body.state,'completed');assert.equal(completion[0].body.answers.length,[6,4,8][task]);
  click(w,'Voice');await delay(10);assert(w.document.body.textContent.includes('Audio is not uploaded'));assert(!calls.some(x=>x.path.includes('import/voice')));s.dom.window.close();
 }
 s=await setup();click(s.w,'Prepare task');await delay(10);for(const i of s.w.document.querySelectorAll('input[type=checkbox]'))i.checked=true;click(s.w,'Start experimental task');await until(()=>s.w.document.body.textContent.includes('Stop this run'));click(s.w,'Movement');await delay(30);assert(s.calls.some(x=>x.body?.state==='aborted'));assert(s.w.document.body.textContent.includes('Movement signal review'));s.dom.window.close();
 console.log('PASS DOM: admin gate, 3 task runners, response payloads, voice consent display, module navigation and aborted-run storage. Timers accelerated; no visual/hardware validation.');
})().catch(e=>{console.error(e);process.exit(1)});
