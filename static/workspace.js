'use strict';
const $ = (id) => document.getElementById(id);
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
} [c]));
const label = (value) => String(value).replaceAll('-', ' ').replace(/^./, c => c.toUpperCase());
const state = {
    profiles: [],
    profile: null,
    items: [],
    insights: null,
    sessions: [],
    passages: [],
    practice: null,
    metro: null,
    audio: null,
    manualToken: null,
    savingPractice: false
};
const storage = {
    get(key) {
        try {
            return localStorage.getItem(key);
        } catch {
            return null;
        }
    },
    set(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch {
            notify('Browser storage is unavailable. Keep this tab open to retain the timer.', true);
        }
    },
    remove(key) {
        try {
            localStorage.removeItem(key);
        } catch {}
    }
};
let noticeTimeout;

function notify(message, error = false) {
    $('notice').textContent = message;
    $('notice').classList.toggle('error', error);
    $('notice').hidden = false;
    clearTimeout(noticeTimeout);
    noticeTimeout = setTimeout(() => {
        $('notice').hidden = true;
    }, 6000);
}
async function api(path, method = 'GET', data) {
    const response = await fetch(path, {
        method,
        headers: data ? {
            'Content-Type': 'application/json'
        } : {},
        body: data ? JSON.stringify(data) : undefined
    });
    let result;
    try {
        result = await response.json();
    } catch {
        throw new Error('The server did not return a valid response. Please retry.');
    }
    if (!response.ok) throw new Error(result.error || 'Something went wrong. Please retry.');
    return result;
}

function guard(fn) {
    return async function(...args) {
        try {
            await fn.apply(this, args);
        } catch (error) {
            notify(error.message, true);
        }
    };
}

function dayText(value, options = {
    month: 'short',
    day: 'numeric'
}) {
    return new Date(value + 'T12:00:00').toLocaleDateString(undefined, options);
}

function dueText(item) {
    if (!item.deadline) return 'No deadline';
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const days = Math.round((new Date(item.deadline + 'T00:00:00') - today) / 86400000);
    return days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? 'Due today' : `Due ${dayText(item.deadline)}`;
}

function activeItems() {
    return state.items.filter(i => i.active);
}

function empty(title, copy, button = '') {
    return `<div class="empty"><h3>${escapeHTML(title)}</h3><p>${escapeHTML(copy)}</p>${button}</div>`;
}

function openDialog(id) {
    const dialog = $(id);
    const error = dialog.querySelector('.form-error');
    if (error) error.textContent = '';
    dialog.showModal();
}

function changeView() {
    const view = ['today', 'practice', 'repertoire', 'progress', 'about'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'today';
    $('welcome').hidden = !!state.profile || view === 'about';
    $('workspace').hidden = !state.profile || view === 'about';
    document.querySelectorAll('.view').forEach(el => {
        el.hidden = el.id !== view + 'View';
    });
    document.querySelectorAll('[data-view]').forEach(el => {
        el.classList.toggle('active', el.dataset.view === view);
        if (el.dataset.view === view) el.setAttribute('aria-current', 'page');
        else el.removeAttribute('aria-current');
    });
}

function profileKey() {
    return `hornlab:session:${state.profile.id}`;
}

function persist() {
    if (state.practice) storage.set(profileKey(), JSON.stringify(state.practice));
}

function loadPractice() {
    state.practice = null;
    try {
        const saved = JSON.parse(storage.get(profileKey()));
        if (saved && saved.version === 1 && Array.isArray(saved.plan) && saved.plan.length && Number.isInteger(saved.index) && saved.index >= 0 && saved.index < saved.plan.length && saved.plan.every(s => typeof s.title === 'string' && Number.isFinite(s.duration) && s.duration > 0) && Number.isFinite(saved.remaining) && Number.isFinite(saved.elapsed) && Array.isArray(saved.completed) && typeof saved.token === 'string' && (saved.started === null || Number.isFinite(saved.started))) state.practice = saved;
    } catch {}
    renderPractice();
}
async function selectProfile(id) {
    window.dispatchEvent(new Event('hornlab-profile-changing'));
    stopMetronome();
    if (state.practice) pauseTimer();
    state.profile = state.profiles.find(p => p.id === Number(id)) || state.profiles[0] || null;
    changeView();
    $('profileSelect').disabled = !state.profile;
    if (!state.profile) return;
    storage.set('hornlab:profile', String(state.profile.id));
    $('profileSelect').value = state.profile.id;
    $('minutes').value = state.profile.typical_time;
    setMinuteButtons();
    $('greeting').textContent = `Hi ${state.profile.name}. What needs work today?`;
    const url = new URL(location);
    url.searchParams.set('profile', state.profile.id);
    history.replaceState(null, '', url);
    loadMetronome();
    loadPractice();
    await refresh();
}
async function refresh() {
    const id = state.profile.id;
    const [items, insights, sessions, passages] = await Promise.all([api(`/api/items?profile=${id}`), api(`/api/insights?profile=${id}`), api(`/api/sessions?profile=${id}`), api(`/api/passages?profile=${id}`)]);
    if (state.profile.id !== id) return;
    Object.assign(state, {
        items,
        insights,
        sessions,
        passages
    });
    renderOverview();
    renderLibrary();
    renderProgress();
    renderPassages();
    window.dispatchEvent(new Event('hornlab-refreshed'));
}

function renderOverview() {
    const data = state.insights;
    const items = activeItems();
    $('itemCount').textContent = items.length;
    $('streakValue').textContent = data.streak;
    $('weekMinutes').textContent = data.week_minutes;
    $('goalCaption').textContent = `${data.week_minutes} of ${data.weekly_goal} min`;
    $('goalProgress').max = data.weekly_goal;
    $('goalProgress').value = data.week_minutes;
    $('goalMessage').textContent = data.week_minutes >= data.weekly_goal ? 'You reached your weekly goal. Nice work!' : data.week_minutes ? `${data.weekly_goal-data.week_minutes} more minutes to your weekly goal. Keep going when you have time.` : 'Save a session to start this week’s total.';
    const ranked = [...items].sort((a, b) => (a.deadline || '9999').localeCompare(b.deadline || '9999') || ({
        high: 0,
        medium: 1,
        low: 2
    } [a.priority] - {
        high: 0,
        medium: 1,
        low: 2
    } [b.priority]));
    $('focusCards').innerHTML = ranked.slice(0, 3).map(i => `<article class="focus-card"><div class="section-top"><span class="tag">${escapeHTML(i.category)}</span>${i.priority==='high'?'<span class="tag urgent">High priority</span>':''}</div><h3>${escapeHTML(i.title)}</h3><div class="card-bottom"><span>${escapeHTML(label(i.confidence))}</span><span>${escapeHTML(dueText(i))}</span></div></article>`).join('') || empty('A fresh music stand.', 'Add a piece, audition, or technique goal to build your first session.', '<button class="secondary" data-add>Add your first item +</button>');
}

function renderLibrary() {
    const query = $('search').value.trim().toLowerCase();
    const category = $('categoryFilter').value;
    const archived = $('statusFilter').value === 'archived';
    const items = state.items.filter(i => Boolean(i.active) !== archived && (category === 'all' || i.category === category) && i.title.toLowerCase().includes(query));
    $('libraryList').innerHTML = items.map(i => `<article class="library-item"><div><span class="tag">${escapeHTML(i.category)}</span><h3>${escapeHTML(i.title)}</h3><p>${i.last_practiced?'Last practiced '+escapeHTML(dayText(i.last_practiced)):'Not practiced yet'}</p></div><div class="meta"><strong>${escapeHTML(label(i.confidence))}</strong>${escapeHTML(dueText(i))}</div><div class="meta"><strong>PRIORITY</strong>${escapeHTML(label(i.priority))}</div><div class="actions"><button data-edit="${i.id}" aria-label="Edit ${escapeHTML(i.title)}">Edit</button><button data-archive="${i.id}">${i.active?'Archive':'Restore'}</button></div></article>`).join('') || empty(query || category !== 'all' ? 'No matching items.' : archived ? 'Nothing archived.' : 'Your music stand is empty.', query || category !== 'all' ? 'Try another search or category.' : archived ? 'Archived repertoire can be restored here.' : 'Add the music you want to move forward.', !archived && !query ? '<button class="secondary" data-add>+ Add repertoire</button>' : '');
}

function renderProgress() {
    const data = state.insights;
    $('totalMinutes').textContent = data.total_minutes;
    $('totalSessions').textContent = data.session_count;
    $('progressStreak').textContent = data.streak;
    $('weekComparison').textContent = `This week: ${data.week_minutes} min · Last full week: ${data.previous_week_minutes} min`;
    $('exportLink').href = `/api/export?profile=${state.profile.id}`;
    const max = Math.max(1, ...data.series.map(d => d.minutes));
    $('activityChart').innerHTML = data.series.map(d => `<div class="chart-column" title="${escapeHTML(dayText(d.date))}: ${d.minutes} minutes"><span>${d.minutes||''}</span><div class="bar" style="height:${Math.max(2,d.minutes/max*145)}px"></div><small>${new Date(d.date+'T12:00:00').getDate()}</small></div>`).join('');
    const chartText = data.series.map(d => `${dayText(d.date)}: ${d.minutes} minutes`).join('; ');
    $('activityChart').setAttribute('aria-label', chartText);
    $('chartAccessible').textContent = chartText;
    $('sessionHistory').innerHTML = state.sessions.map(s => `<article class="history-item"><time datetime="${escapeHTML(s.date)}">${escapeHTML(dayText(s.date,{month:'short',day:'numeric',year:'numeric'}))}</time><div><h3>${escapeHTML(s.focus)}</h3>${s.notes?`<p>${escapeHTML(s.notes)}</p>`:''}</div><strong>${s.duration} min</strong></article>`).join('') || empty('No sessions yet.', 'Finish a guided session or log practice to start your journal.');
}

function editItem(id) {
    const form = $('itemForm');
    form.reset();
    const item = state.items.find(i => i.id === Number(id));
    $('itemDialogTitle').textContent = item ? 'Keep your repertoire current' : 'Add to your music stand';
    for (const key of ['id', 'title', 'category', 'priority', 'confidence', 'deadline']) {
        if (item) form.elements[key].value = item[key] ?? '';
    }
    $('itemForm').elements.id.value = item?.id ?? '';
    openDialog('itemDialog');
}

function setMinuteButtons() {
    document.querySelectorAll('[data-minutes]').forEach(b => {
        const selected = Number(b.dataset.minutes) === Number($('minutes').value);
        b.classList.toggle('selected', selected);
        b.setAttribute('aria-pressed', String(selected));
    });
}

function currentRemaining() {
    const p = state.practice;
    return p ? Math.max(0, p.remaining - (p.started ? (Date.now() - p.started) / 1000 : 0)) : 0;
}

function pauseTimer() {
    const p = state.practice;
    if (!p?.started) return;
    const elapsed = Math.min(p.remaining, Math.max(0, (Date.now() - p.started) / 1000));
    p.elapsed += elapsed;
    p.remaining = Math.max(0, p.remaining - elapsed);
    p.started = null;
    persist();
    updateTimer();
}

function updateTimer() {
    const p = state.practice;
    if (!p) return;
    const seconds = Math.ceil(currentRemaining());
    $('timer').textContent = `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
    $('toggleTimer').textContent = p.started ? 'Pause timer' : seconds ? 'Start timer' : 'Time complete';
    $('toggleTimer').disabled = seconds === 0;
    $('sessionState').textContent = p.started ? 'IN SESSION' : seconds ? 'READY WHEN YOU ARE' : 'TIME COMPLETE';
    if (p.started && seconds === 0) {
        pauseTimer();
        stopMetronome();
        notify('Time is up. Complete this step when you are ready.');
    }
}

function renderPractice() {
    const p = state.practice;
    $('sessionPanel').hidden = !p;
    if (!p) return;
    const step = p.plan[p.index];
    $('stepTitle').textContent = step.title;
    $('stepInstruction').textContent = step.instruction;
    $('stepSuccess').textContent = `Aim for: ${step.success}`;
    $('nextStep').textContent = p.index === p.plan.length - 1 ? 'Complete & review ✓' : 'Complete step →';
    $('planSteps').innerHTML = p.plan.map((s, i) => `<li class="${i===p.index?'current':i<p.index?'done':''}"><div><strong>${escapeHTML(s.title)}</strong><small>${s.duration} min · ${escapeHTML(s.focus)}</small></div></li>`).join('');
    const passage = step.passage;
    $('passageCue').hidden = !passage;
    if (passage) $('passageCue').innerHTML = `<span class="small-caps">PASSAGE GOAL</span><h3>${escapeHTML(passage.label)}</h3><p>Target: ${passage.target_tempo} BPM · ${escapeHTML(passage.tempo_unit)} note · ${passage.target_reps} clean repetitions</p>${passage.last_result?.notes ? `<p>Last note: ${escapeHTML(passage.last_result.notes)}</p>` : ''}<button class="secondary" id="usePassageTempo">Use ${passage.suggested_tempo} BPM in metronome</button>`;
    updateTimer();
}
async function buildPlan() {
    if (!state.profile) return;
    if (state.practice && !confirm('Replace the current session? Its unsaved timer progress will be discarded.')) return;
    const minutes = Number($('minutes').value);
    if (!Number.isInteger(minutes) || minutes < 5 || minutes > 180) throw new Error('Choose between 5 and 180 whole minutes.');
    const button = $('buildPlan');
    button.disabled = true;
    try {
        const result = await api('/api/plan', 'POST', {
            profile_id: state.profile.id,
            minutes,
            mode: $('mode').value
        });
        if (!result.plan.length) {
            editItem();
            notify('Add an active repertoire item to build a session.');
            return;
        }
        stopMetronome();
        state.practice = {
            version: 1,
            token: crypto.randomUUID(),
            plan: result.plan,
            index: 0,
            remaining: result.plan[0].duration * 60,
            elapsed: 0,
            started: null,
            completed: []
        };
        persist();
        renderPractice();
        $('sessionPanel').scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    } finally {
        button.disabled = false;
    }
}

function openSave(manual = false) {
    stopMetronome();
    pauseTimer();
    state.savingPractice = !manual;
    if (manual) state.manualToken = crypto.randomUUID();
    const p = manual ? null : state.practice;
    const form = $('saveForm');
    form.reset();
    $('saveTitle').textContent = manual ? 'Make it part of your story.' : 'A session well spent.';
    form.elements.focus.value = p ? p.plan.filter(s => s.item_id && p.completed.includes(s.item_id)).map(s => s.title).join(', ').slice(0, 200) || 'Guided practice' : 'Practice';
    form.elements.duration.value = p ? Math.max(1, Math.round(p.elapsed / 60)) : state.profile.typical_time;
    const items = state.items.filter(i => i.active || p?.completed.includes(i.id));
    $('completedChoices').innerHTML = items.map(i => `<label><input type="checkbox" name="completed" value="${i.id}" ${p?.completed.includes(i.id)?'checked':''}>${escapeHTML(i.title)}</label>`).join('') || '<span class="quiet">No repertoire items yet.</span>';
    renderResultInputs(p);
    openDialog('saveDialog');
}

let metroSettings = HornMetronome.normalize();
let metroWanted = false;
let tapTimes = [];
const metroEngine = new HornMetronome.Engine({
    onTick(event) {
        document.querySelectorAll('[data-beat]').forEach(button => button.classList.toggle('playing', Number(button.dataset.beat) === event.beat));
        $('beatLight').textContent = `${event.beat + 1}${event.sub ? ' · ' + (event.sub + 1) : ''}`;
    }
});

function stopMetronome() {
    metroWanted = false;
    metroEngine.stop();
    $('metronomeToggle').textContent = 'Play metronome';
    $('metronomeToggle').setAttribute('aria-pressed', 'false');
    $('beatLight').textContent = '●';
    document.querySelectorAll('[data-beat]').forEach(b => b.classList.remove('playing'));
}
async function startMetronome() {
    metroWanted = true;
    $('metronomeToggle').textContent = 'Stop metronome';
    $('metronomeToggle').setAttribute('aria-pressed', 'true');
    try {
        await metroEngine.start(metroSettings);
    } catch (error) {
        stopMetronome();
        throw new Error('Audio could not start. Try the Play button again in a browser with Web Audio support.');
    }
}

function renderMetronome() {
    const s = metroSettings;
    $('bpm').value = s.bpm;
    $('bpmNumber').value = s.bpm;
    $('bpmLabel').textContent = `${s.bpm} BPM · ${s.unit} note`;
    $('meterNumerator').value = s.numerator;
    $('meterDenominator').value = s.denominator;
    const signature = `${s.numerator}/${s.denominator}`;
    $('meterPreset').value = ['2/4', '3/4', '4/4', '5/4', '6/8', '7/8', '9/8', '12/8'].includes(signature) ? signature : 'custom';
    $('meterCount').value = s.compound ? 'compound' : 'written';
    $('meterCount').querySelector('[value="compound"]').disabled = !(s.denominator === 8 && s.numerator >= 6 && s.numerator % 3 === 0);
    $('subdivision').value = s.subdivision;
    $('metroVolume').value = s.volume;
    $('beatButtons').innerHTML = s.accents.map((accent, i) => `<button type="button" data-beat="${i}" class="accent-${accent}" aria-label="Beat ${i+1}: ${['silent','normal','strong'][accent]}. Change accent.">${i+1}<small>${['silent','normal','strong'][accent]}</small></button>`).join('');
    $('meterDescription').textContent = `${signature}: ${s.beats} ${s.unit}-note beats per bar, ${s.subdivision} click${s.subdivision === 1 ? '' : 's'} per beat. BPM refers to the ${s.unit} note. Changes restart on beat 1.`;
}

function loadMetronome() {
    let saved;
    try {
        saved = JSON.parse(storage.get(`hornlab:metronome:${state.profile.id}`));
    } catch {}
    metroSettings = HornMetronome.normalize(saved || {});
    tapTimes = [];
    renderMetronome();
}
async function configureMetronome(changes, resetAccents = false) {
    const running = metroWanted;
    stopMetronome();
    metroSettings = HornMetronome.normalize({
        ...metroSettings,
        ...changes,
        ...(resetAccents ? {
            accents: []
        } : {})
    });
    storage.set(`hornlab:metronome:${state.profile.id}`, JSON.stringify(metroSettings));
    renderMetronome();
    if (running && !document.hidden) await startMetronome();
}

function renderPassages() {
    const showArchived = $('showArchivedPassages').checked;
    const passages = state.passages.filter(p => showArchived || (p.active && p.item_active));
    const card = p => `<article class="passage-card"><div class="section-top"><span class="tag">${escapeHTML(p.item_title)}</span><span class="tag ${p.goal_reached ? '' : 'urgent'}">${!p.active || !p.item_active ? 'Archived' : p.goal_reached ? 'Goal met · review' : 'Building consistency'}</span></div><h3>${escapeHTML(p.label)}</h3><p>Goal: ${p.target_reps} clean repetitions at ${p.target_tempo} BPM · ${escapeHTML(p.tempo_unit)} note</p><div class="passage-metrics"><span>Last result<strong>${p.last_result ? `${p.last_result.tempo} BPM · ${p.last_result.clean_reps} clean reps` : 'No result yet'}</strong></span><span>Best clean tempo<strong>${p.best_clean_tempo ? p.best_clean_tempo + ' BPM' : 'Not reached yet'}</strong></span></div><p class="next-practice">Next: ${escapeHTML(p.next_step)}</p>${p.last_result?.notes ? `<p class="passage-note">${escapeHTML(p.last_result.notes)}</p>` : ''}<div class="button-row"><button class="secondary" data-passage-history="${p.id}">History (${p.result_count})</button><button class="text-button" data-passage-edit="${p.id}">Edit goal</button><button class="text-button" data-passage-archive="${p.id}">${p.active ? 'Archive passage' : 'Restore passage'}</button></div></article>`;
    $('passageList').innerHTML = passages.map(card).join('') || empty('Got a tricky passage?', 'Add a measure range, starting tempo, and repetition goal.');
    $('passageProgress').innerHTML = state.passages.filter(p => p.active && p.item_active).map(card).join('') || empty('Progress beyond the clock.', 'Add a passage goal in Repertoire, then record your results after practice.');
}

function editPassage(id) {
    const passage = state.passages.find(p => p.id === Number(id));
    const items = state.items.filter(i => i.active || i.id === passage?.item_id);
    if (!items.length) {
        notify('Add a repertoire item before creating a passage goal.');
        editItem();
        return;
    }
    const form = $('passageForm');
    form.reset();
    $('passageItem').innerHTML = items.map(i => `<option value="${i.id}">${escapeHTML(i.title)}</option>`).join('');
    $('passageItem').disabled = !!passage;
    form.elements.id.value = passage?.id || '';
    if (passage)
        for (const key of ['item_id', 'label', 'start_tempo', 'target_tempo', 'target_reps', 'tempo_unit']) form.elements[key].value = passage[key];
    $('passageDialogTitle').textContent = passage ? 'Refine your passage goal' : 'Add a passage goal';
    openDialog('passageDialog');
}

function showPassageHistory(id) {
    const p = state.passages.find(p => p.id === Number(id));
    $('passageHistoryTitle').textContent = p.label;
    $('passageHistorySummary').textContent = `${p.item_title} · Latest 20 of ${p.result_count} self-reported results. Historical goals are kept with each result.`;
    $('passageHistoryRows').innerHTML = p.history.map(r => `<article class="passage-history-row"><strong>${r.tempo} BPM · ${r.clean_reps} clean reps</strong><small>${escapeHTML(dayText(r.date))} · ${escapeHTML(r.tempo_unit)} note</small><p>Goal then: ${r.target_reps} clean reps at ${r.target_tempo} BPM</p>${r.notes ? `<p>${escapeHTML(r.notes)}</p>` : ''}</article>`).join('') || empty('Start with an honest baseline.', 'Record your first result after a session.');
    openDialog('passageHistoryDialog');
}

function renderResultInputs(practice) {
    const ids = practice ? new Set(practice.plan.slice(0, practice.index + 1).filter(s => s.passage).map(s => s.passage.id)) : null;
    const passages = state.passages.filter(p => ids ? ids.has(p.id) : p.active && p.item_active);
    $('passageResults').innerHTML = passages.map(p => `<div class="passage-result" data-result="${p.id}" data-unit="${p.tempo_unit}"><label class="inline-check"><input type="checkbox" data-record>Record ${escapeHTML(p.item_title)} · ${escapeHTML(p.label)}</label><div class="result-fields" hidden><p class="quiet">Goal: ${p.target_reps} clean repetitions at ${p.target_tempo} BPM · ${escapeHTML(p.tempo_unit)} note</p><div class="form-grid"><label>Achieved tempo (BPM)<input data-tempo type="number" min="30" max="240" required disabled></label><label>Clean repetitions<input data-reps type="number" min="0" max="100" required disabled></label></div><label>What needs attention next?<textarea data-result-note maxlength="1000" rows="2" disabled></textarea></label></div></div>`).join('') || '<p class="quiet">No passage goals in this session yet. Add them in Repertoire for specific feedback next time.</p>';
}

function collectResults() {
    return [...document.querySelectorAll('[data-result]')].filter(row => row.querySelector('[data-record]').checked).map(row => ({
        passage_id: Number(row.dataset.result),
        tempo_unit: row.dataset.unit,
        tempo: Number(row.querySelector('[data-tempo]').value),
        clean_reps: Number(row.querySelector('[data-reps]').value),
        notes: row.querySelector('[data-result-note]').value
    }));
}

function handleForm(id, submit) {
    $(id).addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const button = form.querySelector('button.primary');
        button.disabled = true;
        form.querySelector('.form-error').textContent = '';
        try {
            await submit(form);
        } catch (error) {
            form.querySelector('.form-error').textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });
}
function instrumentValue(form) {
    return form.elements.instrument.value === 'other' ? form.elements.custom_instrument.value.trim() : form.elements.instrument.value;
}
document.querySelectorAll('[data-instrument-picker]').forEach(select => {
    select.onchange = () => {
        const custom = select.form.querySelector('[data-custom-instrument]');
        const other = select.value === 'other';
        custom.hidden = !other; custom.querySelector('input').disabled = !other; custom.querySelector('input').required = other;
    };
    select.form.addEventListener('reset', () => {select.form.querySelector('[data-custom-instrument]').hidden = true; select.form.elements.custom_instrument.disabled = true; select.form.elements.custom_instrument.required = false;});
});
$('editInstrument').onclick = () => {
    if (!state.profile) return notify('Create a profile first.');
    if (storage.get(`hornlab:room:${state.profile.id}`) || state.practice) return notify('Finish or discard your current practice draft before changing instruments.');
    const form = $('instrumentForm'), select = form.elements.instrument;
    const name = state.profile.guidance?.name || state.profile.instrument;
    select.value = [...select.options].some(o => o.value === name) ? name : 'other';
    form.elements.custom_instrument.value = state.profile.instrument;
    select.onchange(); openDialog('instrumentDialog');
};
handleForm('instrumentForm', async form => {
    await api(`/api/profiles/${state.profile.id}/instrument`, 'PATCH', {instrument:instrumentValue(form)});
    localStorage.removeItem(`hornlab:coach:${state.profile.id}`);
    location.reload();
});
handleForm('profileForm', async form => {
    const data = Object.fromEntries(new FormData(form));
    data.typical_time = Number(data.typical_time);
    data.instrument = instrumentValue(form); delete data.custom_instrument;
    const result = await api('/api/profiles', 'POST', data);
    state.profiles.push(result.profile);
    renderProfiles();
    $('profileDialog').close();
    form.reset();
    await selectProfile(result.profile.id);
    notify('Your practice space is ready. Add your first repertoire item.');
});
handleForm('itemForm', async form => {
    const data = Object.fromEntries(new FormData(form));
    const id = data.id;
    delete data.id;
    data.profile_id = state.profile.id;
    await api(id ? `/api/items/${id}` : '/api/items', id ? 'PATCH' : 'POST', data);
    $('itemDialog').close();
    await refresh();
    notify(id ? 'Repertoire updated.' : 'Added to your music stand.');
});
handleForm('goalForm', async form => {
    await api('/api/goal', 'PATCH', {
        profile_id: state.profile.id,
        weekly_minutes: Number(form.elements.weekly_minutes.value)
    });
    $('goalDialog').close();
    await refresh();
    notify('Weekly goal updated.');
});
handleForm('saveForm', async form => {
    const p = state.savingPractice ? state.practice : null;
    await api('/api/session', 'POST', {
        profile_id: state.profile.id,
        token: p ? p.token : state.manualToken,
        focus: form.elements.focus.value,
        duration: Number(form.elements.duration.value),
        notes: form.elements.notes.value,
        passage_results: collectResults(),
        completed_item_ids: [...form.querySelectorAll('input[name="completed"]:checked')].map(el => Number(el.value))
    });
    if (p) {
        storage.remove(profileKey());
        state.practice = null;
        renderPractice();
    }
    $('saveDialog').close();
    await refresh();
    notify('Session saved. A little more progress, in the books.');
});

handleForm('passageForm', async form => {
    const data = Object.fromEntries(new FormData(form));
    const id = data.id;
    delete data.id;
    data.profile_id = state.profile.id;
    for (const key of ['start_tempo', 'target_tempo', 'target_reps']) data[key] = Number(data[key]);
    if (!id) data.item_id = Number(data.item_id);
    await api(id ? `/api/passages/${id}` : '/api/passages', id ? 'PATCH' : 'POST', data);
    $('passageDialog').close();
    await refresh();
    notify('Passage goal saved. New plans will use it.');
});
$('addPassage').addEventListener('click', () => editPassage());
$('showArchivedPassages').addEventListener('change', renderPassages);
$('passageResults').addEventListener('change', event => {
    if (!event.target.matches('[data-record]')) return;
    const row = event.target.closest('[data-result]');
    row.querySelector('.result-fields').hidden = !event.target.checked;
    row.querySelectorAll('.result-fields input, .result-fields textarea').forEach(el => el.disabled = !event.target.checked);
});

function renderProfiles() {
    $('profileSelect').innerHTML = state.profiles.map(p => `<option value="${p.id}">${escapeHTML(p.name)}</option>`).join('') || '<option>Create your first profile</option>';
}
document.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));
document.addEventListener('click', guard(async event => {
    const passageEdit = event.target.closest('[data-passage-edit]');
    if (passageEdit) editPassage(passageEdit.dataset.passageEdit);
    const passageHistory = event.target.closest('[data-passage-history]');
    if (passageHistory) showPassageHistory(passageHistory.dataset.passageHistory);
    const passageArchive = event.target.closest('[data-passage-archive]');
    if (passageArchive) {
        const passage = state.passages.find(p => p.id === Number(passageArchive.dataset.passageArchive));
        await api(`/api/passages/${passage.id}`, 'PATCH', {
            profile_id: state.profile.id,
            active: !passage.active
        });
        await refresh();
    }
    const beat = event.target.closest('[data-beat]');
    if (beat) {
        const accents = [...metroSettings.accents];
        const i = Number(beat.dataset.beat);
        accents[i] = (accents[i] + 2) % 3;
        await configureMetronome({
            accents
        });
    }
    if (event.target.closest('#usePassageTempo')) {
        const passage = state.practice.plan[state.practice.index].passage;
        const meter = passage.tempo_unit === 'dotted-quarter' ? {
            numerator: 6,
            denominator: 8,
            compound: true,
            subdivision: 3
        } : {
            numerator: 4,
            denominator: ({
                half: 2,
                quarter: 4,
                eighth: 8
            })[passage.tempo_unit],
            compound: false,
            subdivision: 1
        };
        if (metroSettings.unit === passage.tempo_unit) await configureMetronome({
            bpm: passage.suggested_tempo
        });
        else await configureMetronome({
            ...meter,
            bpm: passage.suggested_tempo
        }, true);
        $('metroPanel').open = true;
        $('metroPanel').scrollIntoView({
            behavior: 'smooth'
        });
        notify(`Metronome set to ${passage.suggested_tempo} BPM per ${passage.tempo_unit} note.`);
    }
    const add = event.target.closest('[data-add]');
    if (add) editItem();
    const edit = event.target.closest('[data-edit]');
    if (edit) editItem(edit.dataset.edit);
    const archive = event.target.closest('[data-archive]');
    if (archive) {
        const item = state.items.find(i => i.id === Number(archive.dataset.archive));
        archive.disabled = true;
        try {
            await api(`/api/items/${item.id}`, 'PATCH', {
                profile_id: state.profile.id,
                active: !item.active
            });
            await refresh();
            notify(item.active ? 'Item archived. Restore it from the Archived filter.' : 'Item restored.');
        } finally {
            archive.disabled = false;
        }
    }
}));
$('profileSelect').addEventListener('change', guard(event => selectProfile(event.target.value)));
$('newProfile').addEventListener('click', () => openDialog('profileDialog'));
$('welcomeCreate').addEventListener('click', () => openDialog('profileDialog'));

$('addItem').addEventListener('click', () => editItem());
$('editGoal').addEventListener('click', () => {
    $('goalForm').elements.weekly_minutes.value = state.insights.weekly_goal;
    openDialog('goalDialog');
});
['search', 'categoryFilter', 'statusFilter'].forEach(id => $(id).addEventListener('input', renderLibrary));
document.querySelectorAll('[data-minutes]').forEach(b => b.addEventListener('click', () => {
    $('minutes').value = b.dataset.minutes;
    setMinuteButtons();
}));
$('minutes').addEventListener('input', setMinuteButtons);
$('buildPlan').addEventListener('click', guard(buildPlan));
$('toggleTimer').addEventListener('click', () => {
    const p = state.practice;
    if (!p) return;
    if (p.started) pauseTimer();
    else {
        p.started = Date.now();
        persist();
    }
    updateTimer();
});
$('nextStep').addEventListener('click', () => {
    const p = state.practice;
    if (!p) return;
    pauseTimer();
    stopMetronome();
    const item = p.plan[p.index];
    if (item.item_id && !p.completed.includes(item.item_id)) p.completed.push(item.item_id);
    if (p.index === p.plan.length - 1) {
        persist();
        openSave();
        return;
    }
    p.index++;
    p.remaining = p.plan[p.index].duration * 60;
    persist();
    renderPractice();
});
$('finishSession').addEventListener('click', () => openSave());
$('manualSession').addEventListener('click', () => openSave(true));
$('metronomeToggle').addEventListener('click', guard(async () => {
    if (metroWanted) stopMetronome();
    else await startMetronome();
}));
for (const id of ['bpm', 'bpmNumber']) $(id).addEventListener(id === 'bpm' ? 'input' : 'change', guard(async () => {
    const bpm = Number($(id).value);
    if (!Number.isInteger(bpm) || bpm < 30 || bpm > 240) {
        renderMetronome();
        throw new Error('Choose a tempo from 30 to 240 BPM.');
    }
    await configureMetronome({
        bpm
    });
}));
$('meterPreset').addEventListener('change', guard(async () => {
    if ($('meterPreset').value === 'custom') {
        $('meterNumerator').focus();
        return;
    }
    const [numerator, denominator] = $('meterPreset').value.split('/').map(Number);
    const compound = denominator === 8 && numerator % 3 === 0;
    await configureMetronome({
        numerator,
        denominator,
        compound,
        subdivision: compound ? 3 : 1
    }, true);
}));
$('meterNumerator').addEventListener('change', guard(async () => {
    const numerator = Number($('meterNumerator').value);
    if (!Number.isInteger(numerator) || numerator < 1 || numerator > 12) {
        renderMetronome();
        throw new Error('Choose 1 to 12 beats per bar.');
    }
    await configureMetronome({
        numerator
    }, true);
}));
$('meterDenominator').addEventListener('change', guard(() => configureMetronome({
    denominator: Number($('meterDenominator').value)
}, true)));
$('meterCount').addEventListener('change', guard(() => configureMetronome({
    compound: $('meterCount').value === 'compound'
}, true)));
$('subdivision').addEventListener('change', guard(() => configureMetronome({
    subdivision: Number($('subdivision').value)
})));
$('metroVolume').addEventListener('change', guard(() => configureMetronome({
    volume: Number($('metroVolume').value)
})));
$('tapTempo').addEventListener('click', guard(async () => {
    const now = performance.now();
    if (tapTimes.length && now - tapTimes.at(-1) > 2200) tapTimes = [];
    tapTimes.push(now);
    tapTimes = tapTimes.slice(-6);
    if (tapTimes.length > 1) {
        const bpm = Math.round(60000 * (tapTimes.length - 1) / (tapTimes.at(-1) - tapTimes[0]));
        if (bpm >= 30 && bpm <= 240) await configureMetronome({
            bpm
        });
        else notify('Tap between 30 and 240 beats per minute.');
    } else notify('Keep tapping at your desired tempo.');
}));
document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopMetronome();
    else updateTimer();
});
window.addEventListener('hashchange', changeView);
window.addEventListener('pagehide', () => {
    persist();
    stopMetronome();
});
setInterval(updateTimer, 250);
async function init() {
    if (!location.hash) location.hash = location.pathname === '/about' ? 'about' : 'practice';
    $('dateLabel').textContent = new Date().toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric'
    });
    changeView();
    state.profiles = await api('/api/profiles');
    renderProfiles();
    const selected = new URLSearchParams(location.search).get('profile') || storage.get('hornlab:profile');
    await selectProfile(selected);
    if (location.pathname === '/setup' && state.profile) openDialog('profileDialog');
    if (location.pathname === '/about' && !location.hash) location.hash = 'about';
}
guard(init)();
