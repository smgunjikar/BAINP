/* Runs locally on the browser audio thread. Only aggregate signal levels leave it. */
class ResearchLevel extends AudioWorkletProcessor {
 constructor(){super();this.n=0;this.energy=0;this.clipped=0;}
 process(inputs){const channel=inputs[0]?.[0];if(channel){for(const v of channel){this.energy+=v*v;this.clipped+=Math.abs(v)>=.99?1:0;}this.n+=channel.length;if(this.n>=4096){this.port.postMessage({samples:this.n,energy:this.energy,clipped:this.clipped});this.n=0;this.energy=0;this.clipped=0;}}return true;}
}
registerProcessor('research-level',ResearchLevel);
