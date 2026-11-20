'use strict';
// Only a marked, non-text activity surface. No keyboard/input/clipboard/document pointer listeners.
window.NeuroShadowCollector=class {
  constructor(surface,pointer,onStop){this.surface=surface;this.pointer=pointer;this.onStop=onStop;this.events=[];this.frames=0;this.slow=0;this.hidden=0;this.resized=0;this.active=false;}
  start(){
    if(this.surface.dataset.neuroshadowActivity!=='shadow-explore-v1')throw Error('Unregistered activity');
    this.active=true;this.started=performance.now();this.lastMove=-100;this.previousFrame=null;
    this.listen=e=>{
      if(!this.active||!e.isTrusted||e.pointerType!==this.pointer||!e.isPrimary||e.target.closest('input,textarea,select,[contenteditable]'))return;
      const elapsed=performance.now()-this.started;
      if(elapsed>120000||this.events.length>=2400){this.stop();this.onStop('Sample limit reached. Save or discard this buffer.');return;}
      const kind=e.type==='pointermove'?'move':e.type==='pointerdown'?'down':'up';
      if(kind==='move'&&elapsed-this.lastMove<50)return;
      if(kind==='move')this.lastMove=elapsed;
      const rect=this.surface.getBoundingClientRect();
      if(!rect.width||!rect.height)return;
      this.events.push({t_ms:Math.floor(elapsed/50)*50,kind,pointer:e.pointerType,x_bin:Math.max(0,Math.min(20,Math.round((e.clientX-rect.left)/rect.width*20))),y_bin:Math.max(0,Math.min(20,Math.round((e.clientY-rect.top)/rect.height*20)))});
    };
    for(const kind of ['pointermove','pointerdown','pointerup'])this.surface.addEventListener(kind,this.listen,{passive:true});
    this.visibility=()=>{if(document.hidden){this.hidden++;this.stop();this.onStop('Activity hidden. Capture stopped; discard or save for quality review.');}};
    this.resize=()=>{this.resized++;this.stop();this.onStop('Viewport changed. Capture stopped; discard or save for quality review.');};
    document.addEventListener('visibilitychange',this.visibility);window.addEventListener('resize',this.resize);
    const frame=t=>{if(!this.active)return;if(this.previousFrame!==null){this.frames++;if(t-this.previousFrame>100)this.slow++;}this.previousFrame=t;this.raf=requestAnimationFrame(frame);};this.raf=requestAnimationFrame(frame);
    this.timer=setTimeout(()=>{this.stop();this.onStop('Two-minute limit reached. Save or discard this buffer.');},120000);
  }
  stop(){if(!this.active)return;this.duration=Math.min(120000,Math.floor((performance.now()-this.started)/50)*50);this.active=false;clearTimeout(this.timer);cancelAnimationFrame(this.raf);for(const kind of ['pointermove','pointerdown','pointerup'])this.surface.removeEventListener(kind,this.listen);document.removeEventListener('visibilitychange',this.visibility);window.removeEventListener('resize',this.resize);}
  payload(){this.stop();return {duration_ms:this.duration||0,events:this.events,frame_count:Math.min(30000,this.frames),slow_frames:Math.min(30000,this.slow),hidden_count:this.hidden,resize_count:this.resized};}
  clear(){this.stop();this.events.length=0;this.events=[];}
};
