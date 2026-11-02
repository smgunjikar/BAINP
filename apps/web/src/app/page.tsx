'use client';
import { useEffect, useState, useRef } from 'react';
import { api, type DemoCase, type Timeline } from '@/lib/api';

type Tab='overview'|'assessment'|'research'|'care';
const STIMULI=['B','A','C','B','A','B','C','A'] as const;
type Trial={index:number;stimulus:'A'|'B'|'C';pressed:boolean;response_ms:number|null};
export default function Home(){
  const [tab,setTab]=useState<Tab>('overview');
  const [cases,setCases]=useState<DemoCase[]>([]);
  const [selected,setSelected]=useState('functional');
  const [timeline,setTimeline]=useState<Timeline>({participant_id:'demo-001',synthetic:true,sessions:[]});
  const [error,setError]=useState<string>('');
  const [message,setMessage]=useState<string>('');
  const [idx,setIdx]=useState(0);
  const [trials,setTrials]=useState<Trial[]>([]);
  const started=useRef<number>(0);
  const [activeTask,setActiveTask]=useState(false);
  async function refresh(){
    try {const [cs,tl]=await Promise.all([api<DemoCase[]>('/v1/demo/cases'),api<Timeline>('/v1/demo/timeline')]);setCases(cs);setTimeline(tl);setError('');}
    catch(e){setError(String(e));}
  }
  useEffect(()=>{void refresh();},[]);
  const current=cases.find(x=>x.id===selected);
  function begin(){setIdx(0);setTrials([]);setMessage('');setActiveTask(true);started.current=performance.now();}
  async function answer(pressed:boolean){
    if(!activeTask)return;
    const next:Trial={index:idx,stimulus:STIMULI[idx],pressed,response_ms:pressed?Math.round(performance.now()-started.current):null};
    const all=[...trials,next];setTrials(all);
    if(idx===STIMULI.length-1){
      setActiveTask(false);
      try{const result=await api<{correct:number;total:number;quality_status:string}>('/v1/demo/attention',{method:'POST',body:JSON.stringify({trials:all})});
        setMessage(`Saved: ${result.correct}/${result.total} correct · ${result.quality_status} · no clinical interpretation.`);
        await refresh();
      }catch(e){setError(String(e));}
    } else {setIdx(idx+1);started.current=performance.now();}
  }
  async function updateCare(status:string){
    if(!current)return;
    try{await api(`/v1/demo/cases/${current.id}/care`,{method:'PUT',body:JSON.stringify({status})});await refresh();setMessage('Synthetic care status updated.');}
    catch(e){setError(String(e));}
  }
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand-mark">◉</div><div className="brand">BAINP<br/><span>NEXUS / Research</span></div>
      <div className="menu-title">WORKSPACE</div>
      {(['overview','assessment','research','care'] as const).map(x=><button key={x} className={`nav ${tab===x?'selected':''}`} onClick={()=>setTab(x)}>{x==='overview'?'◫  Overview':x==='assessment'?'◎  Cognitive Lab':x==='research'?'⌁  Research Streams':'♡  CareLoop'}</button>)}
      <div className="sidebar-foot">VERSION 1.0 · SYNTHETIC DATA ONLY</div>
    </aside>
    <main className="main"><header><div><p className="eyebrow">BRAIN HEALTH INTELLIGENCE</p><h1>{tab==='overview'?'Research control center':tab==='assessment'?'Cognitive measurement lab':tab==='research'?'Independent research tracks':'CareLoop review workspace'}</h1><p className="subtitle">A transparent signal-to-care research platform. Not a diagnostic device.</p></div><div className="pill">● Demo environment</div></header>
      {error&&<div className="alert error"><b>API connection:</b> {error}. Start FastAPI at 127.0.0.1:8000.</div>}
      {message&&<div className="alert">{message}</div>}
      {tab==='overview'&&<><div className="stat-row"><div className="stat"><small>Simulated scenarios</small><strong>{cases.length}</strong><span>Evidence-aware test cases</span></div><div className="stat"><small>Saved cognitive sessions</small><strong>{timeline.sessions.length}</strong><span>SQLite demo records</span></div><div className="stat"><small>Research cohorts</small><strong>3</strong><span>Not joined across people</span></div></div>
      <section className="panel"><h2>From observed signals to appropriate action</h2><p>Our system separates quality assessment, longitudinal interpretation, prevention and human review. Each result has limitations.</p><div className="flow"><span>Acquire</span><b>→</b><span>Validate</span><b>→</b><span>Describe</span><b>→</b><span>Review</span><b>→</b><span>Follow up</span></div></section>
      <section className="panel"><h2>Research boundary</h2><p>OASIS structural MRI, PADS wrist movements and OpenNeuro EEG are separate cohorts. Their measurements must never be joined as a single real patient. Data-specific analyses are not deployed diagnostic functions.</p></section></>}
      {tab==='assessment'&&<><section className="panel"><h2>Experimental target-detection task</h2><p>Press <b>Target</b> whenever the displayed letter is <b>A</b>. Otherwise press <b>Skip</b>. Eight trials are recorded with browser response times. This is not a validated cognitive test.</p>
      {!activeTask?<button className="primary" onClick={begin}>Start eight-trial task</button>:<div className="test-box"><div className="eyebrow">TRIAL {idx+1} / 8</div><div className="stimulus">{STIMULI[idx]}</div><div className="buttons"><button className="primary" onClick={()=>void answer(true)}>Target (A)</button><button onClick={()=>void answer(false)}>Skip</button></div></div>}</section>
      <section className="panel"><h2>Stored sessions</h2>{timeline.sessions.length?timeline.sessions.map(s=><div className="session" key={s.id}><b>{s.correct}/{s.total} correct</b><span>{new Date(s.recorded_at).toLocaleString()}</span><small>{s.quality_status}</small></div>):<p>No recorded sessions yet. Complete the demonstration task.</p>}</section></>}
      {tab==='research'&&<div className="research-grid">{[
        ['OASIS-1 · MRI','Cross-sectional anatomical feature research','Accessible to project; analysis awaits local source files.'],
        ['OASIS-2 · MRI','Longitudinal anatomical and tabular change','Accessible to project; separate from OASIS-1.'],
        ['PADS · Movement','Participant-held-out wrist motion benchmarking','Public source; not yet downloaded or analyzed here.'],
        ['OpenNeuro ds004504 · EEG','Resting EEG features and artifact investigation','Cross-sectional, not presymptomatic screening.'],
        ['OASIS-3/4 and others','Additional clinical research and validation','Permission pending; no assumed access.'],
        ['NeuroPulse · Stream replay','Future real-time-compatible neural signal engine','Hardware and acquisition not yet integrated.']
      ].map(x=><section className="panel" key={x[0]}><h2>{x[0]}</h2><p>{x[1]}</p><div className="muted">{x[2]}</div></section>)}</div>}
      {tab==='care'&&<div className="care-grid"><section className="panel"><h2>Fictional scenarios</h2><div className="case-menu">{cases.map(c=><button className={selected===c.id?'active':''} key={c.id} onClick={()=>{setSelected(c.id);setMessage('');}}>{c.title}<span>›</span></button>)}</div></section><section className="panel"><h2>{current?.title||'Select a case'}</h2>{current&&<><p>{current.summary}</p><div className="case-result"><small>Evidence/status</small><h3>{current.interpretation.status.replaceAll('_',' ')}</h3><p>{current.interpretation.reason}</p></div><p className="muted">Fictional clinical workflow demonstration. No diagnosis.</p><label htmlFor="status">Care follow-up status</label><select id="status" value={current.care_status} onChange={e=>void updateCare(e.target.value)}><option value="not_started">Not started</option><option value="review_pending">Review pending</option><option value="reviewed">Reviewed</option><option value="follow_up_planned">Follow-up planned</option><option value="closed_demo">Closed (demo)</option></select></>}</section></div>}
      <footer>BAINP · Hackathon development build · All displayed participants and cases are fictional.</footer>
    </main>
  </div>;
}
