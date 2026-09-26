'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {normalize,eventAt,Engine} = require('./static/metronome.js');

test('3/4, 5/4, and 7/8 wrap at their own bar length', () => {
  for(const [numerator,denominator] of [[3,4],[5,4],[7,8]]) {
    const s=normalize({numerator,denominator});
    assert.equal(eventAt(numerator-1,s).beat,numerator-1);
    assert.equal(eventAt(numerator,s).beat,0);
    assert.equal(eventAt(numerator,s).accent,2);
  }
});
test('compound 6/8 counts two dotted quarters and six eighth clicks', () => {
  const s=normalize({numerator:6,denominator:8,compound:true,subdivision:3,bpm:60});
  assert.equal(s.beats,2); assert.equal(s.unit,'dotted-quarter');
  assert.deepEqual(Array.from({length:6},(_,i)=>eventAt(i,s).beat),[0,0,0,1,1,1]);
  assert.equal(eventAt(6,s).beat,0); assert.equal(eventAt(0,s).interval,1/3);
  const written=normalize({...s,compound:false,subdivision:1});
  assert.equal(written.beats,6); assert.equal(written.unit,'eighth');
  assert.equal(eventAt(0,written).interval,1);
});
test('accents, silent beats, and zero volume affect the entire pulse', () => {
  const s=normalize({numerator:3,subdivision:2,accents:[2,0,1]});
  assert.equal(eventAt(2,s).level,0); assert.equal(eventAt(3,s).level,0);
  assert.ok(eventAt(0,s).level>eventAt(4,s).level);
  assert.ok(eventAt(4,s).level>eventAt(5,s).level);
  assert.equal(eventAt(0,{...s,volume:0}).level,0);
});
test('invalid stored settings are normalized; compound unavailable for 7/8', () => {
  const s=normalize({numerator:99,denominator:3,bpm:0,subdivision:100,volume:-1});
  assert.equal(s.numerator,4); assert.equal(s.denominator,4); assert.equal(s.bpm,80);
  assert.equal(s.subdivision,1); assert.equal(s.volume,60);
  assert.equal(normalize({numerator:7,denominator:8,compound:true}).compound,false);
});
function harness() {
  let id=0; const pending=new Map(), starts=[], nodes=[];
  const timers={setTimeout(fn){pending.set(++id,fn);return id;},clearTimeout(i){pending.delete(i);},setInterval(fn){pending.set(++id,fn);return id;},clearInterval(i){pending.delete(i);}};
  const context={currentTime:0,destination:{},resume:async()=>{},createGain:()=>({gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}}),createOscillator(){const node={frequency:{},connect(){},disconnect(){},start(t){starts.push(t);},stop(t){if(t===undefined)this.cancelled=true;}};nodes.push(node);return node;}};
  return {context,timers,pending,starts,nodes};
}
test('audio timestamps keep spacing; stop cancels nodes and queued visuals', async () => {
  const h=harness(); const engine=new Engine({contextFactory:()=>h.context,timers:h.timers});
  await engine.start({bpm:120,subdivision:2});
  h.context.currentTime=.2; engine.schedule();
  h.context.currentTime=.45; engine.schedule();
  assert.equal(h.starts.length,3);
  assert.ok(Math.abs(h.starts[1]-h.starts[0]-.25)<1e-9);
  assert.ok(Math.abs(h.starts[2]-h.starts[1]-.25)<1e-9);
  engine.stop(); assert.equal(h.pending.size,0); assert.ok(h.nodes.every(n=>n.cancelled));
});
test('a suspended tab does not replay missed beats on returning',async()=>{
  const h=harness(); const engine=new Engine({contextFactory:()=>h.context,timers:h.timers});
  await engine.start({bpm:60}); const count=h.starts.length;
  h.context.currentTime=30; engine.schedule();
  assert.equal(h.starts.length,count+1); assert.ok(h.starts.at(-1)>=30); engine.stop();
});
test('stop while audio resume is pending cannot start a stray scheduler',async()=>{
  const h=harness(); let release; h.context.resume=()=>new Promise(resolve=>{release=resolve;});
  const engine=new Engine({contextFactory:()=>h.context,timers:h.timers});
  const starting=engine.start({}); engine.stop(); release(); await starting;
  assert.equal(engine.running,false); assert.equal(h.starts.length,0); assert.equal(h.pending.size,0);
});
