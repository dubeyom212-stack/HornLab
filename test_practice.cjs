const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('./static/practice-core.js');
const Recorder = require('./static/recorder.js');
const base = () => ({tempo:60,streak:0,attempts:[],goal:'Even rhythm',passage:{id:1,target_reps:3,target_tempo:66,tempo_unit:'quarter'}});
test('clean streak unlocks a step; a miss resets the streak',()=>{
    let run=base();run=core.attempt(core.attempt(run,true),true);
    run=core.attempt(run,false);assert.equal(run.streak,0);assert.equal(run.ready,false);
    for(let i=0;i<3;i++)run=core.attempt(run,true);
    assert.equal(run.ready,true);run=core.changeTempo(run,4);
    assert.equal(run.tempo,64);assert.equal(run.streak,0);
});
test('save uses achieved tempo, not unlocked tempo; retains successful lower tempo after a miss',()=>{
    let run=base();for(let i=0;i<3;i++)run=core.attempt(run,true);
    run=core.changeTempo(run,4);assert.equal(core.result(run).tempo,60);
    run=core.attempt(run,false);assert.equal(core.result(run).clean_reps,3);
    assert.equal(core.result(run).tempo,60);
    assert.equal(core.result(core.attempt(base(),false)).clean_reps,0);
    assert.equal(core.changeTempo(run,4).tempo,66);
    assert.equal(core.changeTempo(run,-100).tempo,30);
    assert.equal(core.result(base()),null);
});
test('cancelling pending microphone permission stops late stream',async()=>{
    let accept,stopped=0;
    const recorder=new Recorder({navigator:{mediaDevices:{getUserMedia:()=>new Promise(r=>accept=r)}},MediaRecorder:class{}});
    const start=recorder.start(()=>assert.fail('must not record'));
    await recorder.stop();accept({getTracks:()=>[{stop:()=>stopped++}]});
    assert.equal(await start,false);assert.equal(stopped,1);assert.equal(recorder.active,false);
});
test('microphone denial provides recovery and releases active state',async()=>{
    const recorder=new Recorder({navigator:{mediaDevices:{getUserMedia:async()=>{throw {name:'NotAllowedError'};}}},MediaRecorder:class{}});
    await assert.rejects(()=>recorder.start(()=>{}),/denied/);assert.equal(recorder.active,false);
});
test('recorder selects supported format, collects final audio, and releases microphone',async()=>{
    let stopped=0,recorded;
    class Fake {
        static isTypeSupported(m){return m==='audio/mp4';}
        constructor(stream,options){this.mimeType=options.mimeType;this.state='inactive';}
        start(){this.state='recording';}
        stop(){this.state='inactive';this.ondataavailable({data:new Blob(['audio'])});this.onstop();}
    }
    const recorder=new Recorder({navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop:()=>stopped++}]})}},MediaRecorder:Fake});
    await recorder.start(b=>recorded=b);await recorder.stop();
    assert.equal(recorded.type,'audio/mp4');assert.equal(recorded.size,5);assert.equal(stopped,1);assert.equal(recorder.active,false);
});
