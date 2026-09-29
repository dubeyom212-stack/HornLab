const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('./static/practice-core.js');
const Recorder = require('./static/recorder.js');
const base = () => ({tempo:60,streak:0,attempts:[],goal:'Even rhythm',guidance:{family:'brass'},passage:{id:1,target_reps:3,target_tempo:66,tempo_unit:'quarter'}});
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

test('reset fits remaining budget, slows tempo, and never credits drill repetitions',()=>{
    const original={...base(),seconds:80,coach:{minutes:2}};
    let run=core.beginReset(original,'notes');
    assert.equal(run.reset.duration,40);assert.equal(run.tempo,51);
    assert.equal(core.attempt(run,true),run);assert.equal(core.changeTempo(run,4),run);
    assert.equal(core.result(run),null);
    run=core.finishReset(run,true);
    assert.equal(run.streak,0);assert.equal(run.ready,false);assert.equal(run.paused,true);
    assert.match(core.resetSummary(run),/felt better/);
    run=core.attempt(run,true);
    assert.equal(core.result(run).clean_reps,1);
    assert.match(core.result(run).notes,/Reset: Missed notes/);
    assert.equal(original.tempo,60);
});

test('reset does not extend an expired task, go below tempo floor, or erase earned progress',()=>{
    const expired={...base(),seconds:110,coach:{minutes:2}};
    assert.equal(core.beginReset(expired,'rhythm'),expired);
    let run={...base(),seconds:0};for(let i=0;i<3;i++)run=core.attempt(run,true);
    run=core.beginReset(run,'attacks');
    assert.equal(core.beginReset(run,'notes'),run);
    assert.equal(JSON.parse(JSON.stringify(run)).reset.stage,'working');
    run=core.finishReset(run,false);
    assert.equal(run.paused,true);assert.equal(run.attemptFloor,3);
    assert.equal(core.result(run).tempo,60);assert.equal(core.result(run).clean_reps,3);
    assert.match(core.result(run).notes,/still stuck/);
    assert.equal(core.beginReset({...base(),tempo:30,seconds:0},'rhythm').tempo,30);
});

test('reset exercises use instrument guidance with a neutral fallback',()=>{
    const sax={family:'woodwind',entrance:'Set the fingering and breathe with the pulse.'};
    assert.equal(core.drillFor('attacks',sax).task,sax.entrance);
    assert.doesNotMatch(core.drillFor('rhythm',sax).task,/horn|lip slur/i);
    assert.match(core.drillFor('notes',{family:'percussion'}).task,/strokes/);
    assert.match(core.drillFor('notes',{family:'voice'}).task,/Sing/);
    assert.doesNotMatch(core.drillFor('attacks').task,/breath|bow|valve/i);
    assert.match(core.drillFor('notes',{family:'other'}).task,/smallest change/);
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
