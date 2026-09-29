'use strict';
(() => {
    let run = null, owner = null, lastTick = Date.now(), saving = false;
    let takes = [], urls = [], compare = {}, recordingAt = 0, busy = false, sequence = 0, recordRequest = 0;
    const recorder = new HornRecorder();
    const key = () => `hornlab:room:${owner}`;
    const time = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
    const message = text => { $('recordStatus').textContent = text; };
    function persistRun() {
        if (!owner) return;
        try {
            if (run) localStorage.setItem(key(), JSON.stringify(run));
            else localStorage.removeItem(key());
        } catch { notify('This browser could not save your practice draft. Finish this session before closing the tab.', true); }
    }
    function tick() {
        const now = Date.now();
        if (run && !run.paused && !document.hidden && location.hash === '#practice') {
            run.seconds += Math.min(2, (now - lastTick) / 1000);
            if (run.reset?.stage === 'working' && run.seconds >= run.reset.start + run.reset.duration) {
                run.reset.stage = 'review'; run.paused = true; stopMetronome(); recorder.stop(); draw();
            }
            if(run.coach && !run.coach.budgetReached && run.seconds >= run.coach.minutes*60) {
                run.paused=true;stopMetronome();recorder.stop();draw();
                notify('That task has reached its time budget. Save what you tried and move on, or resume if you choose.');
                run.coach.budgetReached=true;
            }
            persistRun();
        }
        lastTick = now;
        if (run) $('roomElapsed').textContent = `${time(run.seconds)} active`;
        if (run?.reset) $('roomResetClock').textContent = run.reset.stage === 'review' ? 'Time to check in.' : `${time(Math.max(0, run.reset.duration - (run.seconds - run.reset.start)))} left${run.paused ? ' · paused' : ''}`;
        $('recordClock').textContent = time(recordingAt ? (now - recordingAt) / 1000 : 0);
        $('roomClick').textContent = metroWanted ? 'Stop click' : 'Play click';
    }
    function draw() {
        $('roomSetup').hidden = !!run;
        $('roomActive').hidden = !run;
        if (!run) {
            $('roomResetSetup').hidden = true; $('roomStuck').setAttribute('aria-expanded', 'false');
            $('roomResetStatus').textContent = ''; return;
        }
        const resetting = !!run.reset;
        $('roomTitle').textContent = `${run.passage.item_title} · ${run.passage.label}`;
        $('roomProblem').options[1].textContent = HornPractice.drillFor('notes', run.guidance).label;
        $('roomTask').textContent = run.coach ? `${run.goal} Move on when: ${run.coach.stop_when} Time budget: ${run.coach.minutes} minutes.` : `Listen for: ${run.goal.toLowerCase()}. Play the passage once, then mark your attempt.`;
        $('roomTempo').textContent = run.tempo;
        $('roomUnit').textContent = `BPM · ${run.passage.tempo_unit} note`;
        $('roomCue').textContent = run.ready ? (run.tempo >= run.passage.target_tempo ? 'Target reached. Record a final take and compare it with your first.' : 'Clean run complete. Move up when you feel ready.') : `${run.streak} / ${run.passage.target_reps} consecutive clean attempts at this tempo.`;
        $('roomUp').disabled = resetting || !run.ready || run.tempo >= run.passage.target_tempo || saving;
        $('roomDown').disabled = resetting || run.tempo <= 30 || saving;
        $('roomUndo').disabled = resetting || run.attempts.length <= (run.attemptFloor || 0) || saving;
        $('roomClean').disabled = resetting || run.paused || saving;
        $('roomAgain').disabled = resetting || run.paused || saving;
        $('roomPause').textContent = run.paused ? 'Resume practice' : 'Pause practice';
        $('roomPause').disabled = saving || run.reset?.stage === 'review';
        $('roomFinish').disabled = resetting || saving || (!run.attempts.length && !run.resets?.length);
        $('roomFinish').textContent = saving ? 'Saving…' : 'Finish & save';
        $('roomStuck').hidden = resetting;
        $('roomStuck').disabled = saving;
        $('roomReset').hidden = !resetting;
        if (resetting) {
            $('roomResetSetup').hidden = true;
            $('roomStuck').setAttribute('aria-expanded', 'false');
            $('roomResetTitle').textContent = `${run.reset.label} · ${run.tempo} BPM`;
            $('roomResetTask').textContent = run.reset.task;
            $('roomResetDone').hidden = run.reset.stage === 'review';
            $('roomResetFeedback').hidden = run.reset.stage !== 'review';
            $('roomCue').textContent = 'Work on the small group below. Check in before trying the whole passage again.';
        }
        $('roomAttempts').innerHTML = run.attempts.slice(-8).reverse().map(a => `<li>${a.clean ? '✓ Clean' : '↻ Again'} <span>${a.tempo} BPM</span></li>`).join('');
    }
    async function setClick() {
        if (!run) return;
        const unit = run.passage.tempo_unit;
        const meter = unit === 'dotted-quarter' ? {numerator: 6, denominator: 8, compound: true, subdivision: 3} : {numerator: 4, denominator: {quarter:4,eighth:8,half:2}[unit], compound:false, subdivision:1};
        if (metroSettings.unit === unit) await configureMetronome({bpm:run.tempo});
        else await configureMetronome({...meter,bpm:run.tempo},true);
    }
    async function sync() {
        const id = state.profile?.id;
        if (!id) return;
        if (owner !== id) {
            owner = id; run = null; compare = {};
            $('roomResetStatus').textContent = ''; $('roomResetSetup').hidden = true;
            try {
                const saved = JSON.parse(localStorage.getItem(key()));
                if (saved?.version === 1 && saved.profile_id === id && Array.isArray(saved.attempts) && saved.passage && Number.isFinite(saved.seconds)) run = {...saved,paused:true};
            } catch {}
            $('roomNote').value = run?.note || '';
        }
        const selected = $('roomPassage').value;
        const passages = state.passages.filter(p=>p.active && p.item_active);
        $('roomPassage').innerHTML = passages.map(p=>`<option value="${p.id}">${escapeHTML(p.item_title)} · ${escapeHTML(p.label)}</option>`).join('');
        if (passages.some(p=>String(p.id)===selected)) $('roomPassage').value=selected;
        $('roomEmpty').hidden = !!passages.length;
        $('roomStart').disabled = !passages.length;
        draw(); await loadTakes();
    }
    $('roomProblem').onchange = () => { $('roomExercise').textContent = HornPractice.drillFor($('roomProblem').value, run?.guidance || state.profile?.guidance).task; };
    $('roomProblem').onchange();
    $('roomStuck').onclick = () => {
        if (!run || saving || run.reset) return;
        $('roomResetSetup').hidden = !$('roomResetSetup').hidden;
        $('roomStuck').setAttribute('aria-expanded', String(!$('roomResetSetup').hidden));
        $('roomProblem').onchange();
    };
    $('roomResetStart').onclick = guard(async () => {
        if (!run || saving || run.reset) return;
        if (busy) return message('Stop your take before starting a reset.');
        tick();
        const next = HornPractice.beginReset(run, $('roomProblem').value);
        if (next === run) { $('roomResetStatus').textContent = 'Less than 20 seconds left in this task. Save it and move on instead of squeezing in another exercise.'; return; }
        run = next; lastTick = Date.now(); $('roomResetStatus').textContent = '';
        persistRun(); draw(); tick(); await setClick();
    });
    $('roomResetDone').onclick = () => {
        if (!run?.reset || saving) return;
        tick(); run.reset.stage = 'review'; run.paused = true; stopMetronome(); recorder.stop(); persistRun(); draw(); tick();
    };
    for (const [id, helped] of [['roomResetBetter', true], ['roomResetLater', false]]) $(id).onclick = () => {
        if (!run?.reset || saving) return;
        if (busy) return message('Wait for the recording to finish before checking in.');
        run = HornPractice.finishReset(run, helped);
        const outOfTime = run.coach && run.seconds >= run.coach.minutes * 60;
        run.paused = !helped || !!outOfTime;
        lastTick = Date.now(); persistRun(); draw();
        $('roomResetStatus').textContent = helped && !outOfTime
            ? `Try the whole passage once at ${run.tempo} BPM. Mark that attempt below; the drill itself hasn't raised your score.`
            : 'Leave this spot here for today. Finish & save will keep the reset in your notes for next time.';
    };
    $('roomStart').onclick = guard(async () => {
        const passage = state.passages.find(p=>p.id===Number($('roomPassage').value));
        if (!passage || run || busy) return;
        if (state.practice?.started) pauseTimer();
        run = {version:1,guidance:state.profile.guidance,profile_id:owner,token:crypto.randomUUID(),passage:{...passage},goal:$('roomGoal').value,tempo:passage.suggested_tempo,streak:0,ready:false,attempts:[],seconds:0,paused:false,note:''};
        lastTick=Date.now(); persistRun(); await setClick(); draw(); await loadTakes();
    });
    window.addEventListener('hornlab-coach-start',guard(async event=>{
        if(run || busy) return notify('Finish or discard your current practice draft before starting this task.');
        const block=event.detail, passage=state.passages.find(p=>p.id===block.passage_id && p.active && p.item_active);
        if(!passage)return notify('This passage is no longer active. Make a new plan.');
        if(block.tempo_unit!==passage.tempo_unit)return notify('The passage tempo unit changed. Make a new plan before starting it.');
        if(state.practice?.started)pauseTimer();
        run={version:1,guidance:state.profile.guidance,profile_id:owner,token:crypto.randomUUID(),passage:{...passage},goal:block.task,tempo:Math.max(30,Math.min(passage.target_tempo,block.start_tempo)),streak:0,ready:false,attempts:[],seconds:0,paused:false,note:'',coach:{...block}};
        lastTick=Date.now();persistRun();await setClick();draw();await loadTakes();$('roomActive').scrollIntoView({behavior:'smooth',block:'start'});
    }));
    for (const [id, clean] of [['roomClean',true],['roomAgain',false]]) $(id).onclick = () => {
        if (!run || run.paused || saving) return;
        if (run.attempts.length >= 200) return notify('Finish and save this set before starting another.');
        run = HornPractice.attempt(run,clean); persistRun(); draw();
    };
    $('roomUndo').onclick = () => {
        if (!run?.attempts.length || run.reset || run.attempts.length <= (run.attemptFloor || 0) || saving) return;
        run.attempts.pop();
        const last = run.attempts.length > (run.attemptFloor || 0) ? run.attempts.at(-1) : null;
        run.streak = last?.tempo === run.tempo ? last.streak : 0;
        run.ready = run.streak >= run.passage.target_reps;
        persistRun(); draw();
    };
    for (const [id, delta] of [['roomUp',4],['roomDown',-4]]) $(id).onclick = guard(async () => {
        if (!run || saving || (delta>0 && !run.ready)) return;
        if (busy) return message('Stop this take before changing tempo.');
        run = HornPractice.changeTempo(run,delta); persistRun(); await setClick(); draw();
    });
    $('roomClick').onclick = guard(async () => { if (metroWanted) stopMetronome(); else {await setClick(); await startMetronome();} tick(); });
    $('roomPause').onclick = () => {
        if (!run || saving) return;
        tick(); run.paused=!run.paused; if(run.paused) {stopMetronome(); recorder.stop();} persistRun(); draw();
    };
    $('roomNote').oninput = () => {if(run) {run.note=$('roomNote').value;persistRun();}};
    $('roomDiscard').onclick = () => {
        if (saving || busy) return notify('Stop recording or wait for the save to finish first.');
        if ($('roomDiscard').textContent !== 'Confirm discard') { $('roomDiscard').textContent = 'Confirm discard'; return; }
        run=null;persistRun();stopMetronome();$('roomDiscard').textContent='Discard this practice draft';draw();
    };
    $('roomFinish').onclick = guard(async () => {
        if (!run || run.reset || (!run.attempts.length && !run.resets?.length) || saving) return;
        if (busy) { message('Stop your recording before finishing the session.'); return; }
        tick(); run.paused=true; persistRun(); stopMetronome(); saving=true; draw();
        const draft=run;
        try {
            const result=HornPractice.result(draft);
            await api('/api/session','POST',{profile_id:draft.profile_id,token:draft.token,duration:Math.max(1,Math.min(720,Math.round(draft.seconds/60))),focus:`${draft.passage.item_title} · ${draft.passage.label}`.slice(0,200),notes:`${HornPractice.resetSummary(draft)}Passage practice: ${draft.goal}. Active time ${time(draft.seconds)} (minutes rounded, minimum 1).\n${draft.attempts.map(a=>`${a.tempo}: ${a.clean?'clean':'again'}`).join('; ')}\n${draft.note}`,completed_item_ids:result?[draft.passage.item_id]:[],passage_results:result?[result]:[]});
            localStorage.removeItem(`hornlab:room:${draft.profile_id}`);
            if(run===draft) {run=null;$('roomNote').value='';}
            await refresh(); notify('Practice saved. Your takes are still here to listen to.');
        } finally { saving=false; draw(); }
    });
    function openDB() {
        return new Promise((resolve,reject)=>{
            const req=indexedDB.open('hornlab-audio',1);
            req.onupgradeneeded=()=>req.result.createObjectStore('takes',{keyPath:'id'});
            req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error);
        });
    }
    async function dbAction(mode, fn) {
        const db=await openDB();
        try {return await new Promise((resolve,reject)=>{
            const tx=db.transaction('takes',mode), req=fn(tx.objectStore('takes'));
            tx.oncomplete=()=>resolve(req.result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
        });} finally {db.close();}
    }
    async function loadTakes() {
        const id=owner, seq=++sequence;
        try {
            const rows=await dbAction('readonly',s=>s.getAll());
            if(id!==owner || seq!==sequence) return;
            takes=[...rows.filter(t=>t.profile===id),...takes.filter(t=>t.profile===id && t.temporary)].sort((a,b)=>b.date-a.date);
            renderTakes();
        } catch { message('Browser audio storage is unavailable. New takes will have a download link—save them before leaving.'); }
    }
    function renderTakes() {
        document.querySelectorAll('#practiceView audio').forEach(a=>a.pause());
        urls.forEach(u=>URL.revokeObjectURL(u));urls=[];
        const url = blob => {const u=URL.createObjectURL(blob);urls.push(u);return u;};
        const visible=takes.filter(t=>$('allTakes').checked || !run || t.passage===run.passage.id);
        $('takeList').innerHTML=visible.map(t=>`<article class="take-card"><strong>${escapeHTML(t.title)}</strong><small>${new Date(t.date).toLocaleString()}${t.tempo?` · ${t.tempo} BPM · ${escapeHTML(t.unit)} note`:''}${t.temporary?' · Not stored—download to keep':''}</small><audio controls preload="metadata" src="${url(t.blob)}" aria-label="Listen to ${escapeHTML(t.title)}"></audio><div class="button-row"><button class="secondary" data-compare="A" data-take="${t.id}">Use as A</button><button class="secondary" data-compare="B" data-take="${t.id}">Use as B</button><a class="text-link" href="${urls.at(-1)}" download="hornlab-${t.date}.${t.blob.type.includes('mp4')?'m4a':t.blob.type.includes('wav')?'wav':t.blob.type.includes('mpeg')?'mp3':t.blob.type.includes('ogg')?'ogg':'webm'}">Download</a><button class="text-button" data-delete-take="${t.id}">Delete</button></div></article>`).join('')||'<p class="quiet">No takes yet. Record a short passage, or import an audio file.</p>';
        $('comparePlayers').innerHTML=['A','B'].map(slot=>{
            const take=takes.find(t=>t.id===compare[slot]);
            return `<div><strong>Take ${slot}</strong>${take?`<p>${escapeHTML(take.title)}${take.tempo?` · ${take.tempo} BPM`:''}</p><audio controls preload="metadata" src="${url(take.blob)}" aria-label="Compare take ${slot}"></audio>`:'<p class="quiet">Choose a take below.</p>'}</div>`;
        }).join('');
        document.querySelectorAll('#practiceView audio').forEach(a=>a.addEventListener('play',()=>{
            stopMetronome(); document.querySelectorAll('#practiceView audio').forEach(other=>{if(other!==a)other.pause();});
        }));
    }
    function metadata() {
        return {id:crypto.randomUUID(),profile:owner,passage:run?.passage.id||null,title:run?`${run.passage.item_title} · ${run.passage.label}`:'Free practice',tempo:run?.tempo||null,unit:run?.passage.tempo_unit||null,date:Date.now()};
    }
    async function keepTake(blob,meta) {
        if(!blob.size) return message('No audio was captured. Check the microphone and try again.');
        const take={...meta,blob};
        try {
            const all=await dbAction('readonly',s=>s.getAll());
            if(all.reduce((n,t)=>n+t.blob.size,0)+blob.size>50*1024*1024) throw new Error('Audio storage limit reached');
            await dbAction('readwrite',s=>s.put(take));
            if(owner===meta.profile) {await loadTakes();message('Take saved on this device. Listen back, then mark your attempt.');}
        } catch {
            if(owner===meta.profile) {takes.unshift({...take,temporary:true});renderTakes();message('Could not store this take. Download it now to keep it.');}
        }
    }
    function recordingUI(active) {
        busy=active;$('recordTake').disabled=active;$('stopTake').disabled=!active;$('importTake').disabled=active;
        $('profileSelect').disabled=active;$('newProfile').disabled=active;
        $('editInstrument').disabled=active;
        $('recordTake').textContent=active?'● Recording…':'● Record a take';
    }
    $('recordTake').onclick=async()=>{
        if(busy || !owner)return;
        const request=++recordRequest;
        const meta=metadata();recordingUI(true);message('Waiting for microphone permission…');
        document.querySelectorAll('#practiceView audio').forEach(a=>a.pause());
        try {
            const started=await recorder.start((blob,warning)=>{
                recordingAt=0;recordingUI(false);
                keepTake(blob,meta).then(()=>{if(warning)message(warning);});
            });
            if(request!==recordRequest) return;
            if(started) {recordingAt=Date.now();message('Recording. Stop when you finish the passage.');}
            else {recordingUI(false);message('Recording cancelled.');}
        } catch(error) {if(request===recordRequest){recordingUI(false);message(error.message);}}
    };
    $('stopTake').onclick=()=>{recorder.stop();if(!recorder.recorder){++recordRequest;recordingUI(false);message('Recording cancelled.');}};
    $('importTake').onchange=guard(async e=>{
        const file=e.target.files[0];if(!file)return;
        e.target.value='';
        if(file.size>15*1024*1024) return message('Choose an audio file smaller than 15 MB.');
        if(!file.type.startsWith('audio/') && !/\.(wav|mp3|m4a|ogg|webm)$/i.test(file.name)) return message('Choose an audio recording.');
        const meta=metadata();meta.title=`${meta.title} · ${file.name}`;
        await keepTake(file,meta);
    });
    $('allTakes').onchange=renderTakes;
    $('takeList').onclick=guard(async e=>{
        const button=e.target.closest('[data-compare]');
        if(button){compare[button.dataset.compare]=button.dataset.take;renderTakes();return;}
        const del=e.target.closest('[data-delete-take]');
        if(del){
            const id=del.dataset.deleteTake;
            if(del.textContent!=='Confirm delete'){del.textContent='Confirm delete';return;}
            await dbAction('readwrite',s=>s.delete(id));takes=takes.filter(t=>t.id!==id);renderTakes();
        }
    });
    window.addEventListener('hornlab-refreshed',()=>guard(sync)());
    window.addEventListener('hornlab-profile-changing',()=>{
        recorder.stop();if(run){tick();run.paused=true;persistRun();} document.querySelectorAll('#practiceView audio').forEach(a=>a.pause());
    });
    function leave() {
        if(document.hidden || location.hash!=='#practice') {
            recorder.stop();
            if(busy && !recorder.recorder) {++recordRequest;recordingUI(false);message('Recording cancelled.');}
            if(run){tick();run.paused=true;persistRun();draw();}stopMetronome();
            document.querySelectorAll('#practiceView audio').forEach(a=>a.pause());
        }
    }
    document.addEventListener('visibilitychange',leave);window.addEventListener('hashchange',leave);
    window.addEventListener('pagehide',()=>{recorder.stop();persistRun();});
    window.addEventListener('beforeunload',e=>{if(busy){e.preventDefault();e.returnValue='';}});
    setInterval(tick,1000);
    if(state.profile)guard(sync)();
})();
