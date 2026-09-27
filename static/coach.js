'use strict';
(() => {
    let plan = null, owner = null, requesting = false;
    const planKey = id => `hornlab:coach:${id}`;
    function renderPlan() {
        if (!plan) {$('coachPlan').innerHTML='';return;}
        $('coachPlan').innerHTML=`<div class="coach-reason"><span class="small-caps">AI SUGGESTION · ${plan.minutes} MINUTES TOTAL</span><h3>${escapeHTML(plan.summary)}</h3><p><strong>Leave for another day:</strong> ${escapeHTML(plan.skip_today)}</p><p><strong>First, ${plan.warmup_minutes} min:</strong> a comfortable warm-up. Then work through the tasks below.</p></div><div class="coach-blocks">${plan.blocks.map((b,i)=>`<article><span class="tag">${i+1} / ${b.minutes} min budget</span><h3>${escapeHTML(b.title)} · ${escapeHTML(b.passage)}</h3><p>${escapeHTML(b.task)}</p><p class="quiet"><strong>Why this:</strong> ${escapeHTML(b.why)}</p><p><strong>Move on when:</strong> ${escapeHTML(b.stop_when)} Or when the time budget runs out.</p><button class="primary" data-coach-start="${i}">Practice this · ${b.start_tempo} BPM</button></article>`).join('')}</div><p class="quiet">This is a suggestion based on your text feedback, not an assessment of your playing. Plans stay in this browser. Finish or discard an active passage before starting another task.</p>`;
    }
    async function sync() {
        const id=state.profile?.id;if(!id)return;
        if(owner!==id){owner=id;plan=null;try{const saved=JSON.parse(localStorage.getItem(planKey(id)));if(saved?.source==='ai'&&Array.isArray(saved.blocks))plan=saved;}catch{}renderPlan();}
        const selected=$('coachFocus').value;
        $('coachFocus').innerHTML='<option value="">Help me choose</option>'+state.items.filter(i=>i.active).map(i=>`<option value="${i.id}">${escapeHTML(i.title)}</option>`).join('');
        if(state.items.some(i=>String(i.id)===selected&&i.active))$('coachFocus').value=selected;
        try {
            const status=await api('/api/coach/status');
            $('coachConnection').textContent=status.configured?'AI connected':'AI not connected';
            if(!status.configured)$('coachStatus').textContent='The AI coach hasn’t been enabled on this site yet. You can still use the passage tools below.';
        } catch {$('coachConnection').textContent='Connection unavailable';}
    }
    $('coachForm').addEventListener('submit',async event=>{
        event.preventDefault();if(requesting||!owner)return;
        requesting=true;$('coachGenerate').disabled=true;$('coachStatus').textContent='Choosing a small set of useful tasks…';
        const id=owner;
        try {
            const result=await api('/api/coach','POST',{profile_id:id,minutes:Number($('coachMinutes').value),energy:$('coachEnergy').value,workload:$('coachWorkload').value,target_date:$('coachDate').value,focus_item_id:$('coachFocus').value?Number($('coachFocus').value):null,consent:$('coachConsent').checked});
            if(owner!==id)return;
            plan=result;storage.set(planKey(id),JSON.stringify(plan));renderPlan();$('coachStatus').textContent='Plan ready. Review it, then start the first task.';
        } catch(error) {if(owner===id)$('coachStatus').textContent=error.message;}
        finally {requesting=false;$('coachGenerate').disabled=false;}
    });
    $('coachPlan').addEventListener('click',event=>{
        const button=event.target.closest('[data-coach-start]');if(!button||!plan)return;
        window.dispatchEvent(new CustomEvent('hornlab-coach-start',{detail:plan.blocks[Number(button.dataset.coachStart)]}));
    });
    window.addEventListener('hornlab-refreshed',()=>sync());
    if(state.profile)sync();
})();
