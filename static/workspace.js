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
    const view = ['today', 'repertoire', 'progress'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'today';
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
    stopMetronome();
    if (state.practice) pauseTimer();
    state.profile = state.profiles.find(p => p.id === Number(id)) || state.profiles[0] || null;
    $('welcome').hidden = !!state.profile;
    $('workspace').hidden = !state.profile;
    $('profileSelect').disabled = !state.profile;
    if (!state.profile) return;
    storage.set('hornlab:profile', String(state.profile.id));
    $('profileSelect').value = state.profile.id;
    $('minutes').value = state.profile.typical_time;
    setMinuteButtons();
    $('greeting').textContent = `${state.profile.name}, let's make space for a good ${state.profile.instrument.toLowerCase()} session.`;
    const url = new URL(location);
    url.searchParams.set('profile', state.profile.id);
    history.replaceState(null, '', url);
    loadPractice();
    await refresh();
}
async function refresh() {
    const id = state.profile.id;
    const [items, insights, sessions] = await Promise.all([api(`/api/items?profile=${id}`), api(`/api/insights?profile=${id}`), api(`/api/sessions?profile=${id}`)]);
    if (state.profile.id !== id) return;
    Object.assign(state, {
        items,
        insights,
        sessions
    });
    renderOverview();
    renderLibrary();
    renderProgress();
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
    $('goalMessage').textContent = data.week_minutes >= data.weekly_goal ? 'Your weekly goal is in the books. Take a moment to enjoy it.' : data.week_minutes ? `${data.weekly_goal-data.week_minutes} more minutes to your weekly goal. One focused session at a time.` : 'Your next session is the first step. Make a little room for it.';
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
    $('sessionHistory').innerHTML = state.sessions.map(s => `<article class="history-item"><time datetime="${escapeHTML(s.date)}">${escapeHTML(dayText(s.date,{month:'short',day:'numeric',year:'numeric'}))}</time><div><h3>${escapeHTML(s.focus)}</h3>${s.notes?`<p>${escapeHTML(s.notes)}</p>`:''}</div><strong>${s.duration} min</strong></article>`).join('') || empty('Every session has a story.', 'Finish a guided session or log practice to start your journal.');
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
    openDialog('saveDialog');
}

function stopMetronome() {
    if (state.metro) clearInterval(state.metro);
    state.metro = null;
    if (state.audio?.state === 'running') state.audio.suspend().catch(() => {});
    $('metronomeToggle').textContent = 'Play metronome';
    $('metronomeToggle').setAttribute('aria-pressed', 'false');
    $('beatLight').classList.remove('pulse');
}
async function startMetronome() {
    if (!state.audio) {
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!Audio) throw new Error('This browser does not support the metronome.');
        state.audio = new Audio();
    }
    await state.audio.resume();
    let beat = 0;
    const tick = () => {
        if (document.hidden) {
            stopMetronome();
            return;
        }
        const oscillator = state.audio.createOscillator(),
            gain = state.audio.createGain(),
            now = state.audio.currentTime;
        oscillator.frequency.value = beat++ % 4 === 0 ? 1100 : 800;
        gain.gain.setValueAtTime(.15, now);
        gain.gain.exponentialRampToValueAtTime(.001, now + .055);
        oscillator.connect(gain);
        gain.connect(state.audio.destination);
        oscillator.onended = () => {
            oscillator.disconnect();
            gain.disconnect();
        };
        oscillator.start(now);
        oscillator.stop(now + .06);
        $('beatLight').classList.add('pulse');
        setTimeout(() => $('beatLight').classList.remove('pulse'), 80);
    };
    tick();
    state.metro = setInterval(tick, 60000 / Number($('bpm').value));
    $('metronomeToggle').textContent = 'Stop metronome';
    $('metronomeToggle').setAttribute('aria-pressed', 'true');
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
handleForm('profileForm', async form => {
    const data = Object.fromEntries(new FormData(form));
    data.typical_time = Number(data.typical_time);
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

function renderProfiles() {
    $('profileSelect').innerHTML = state.profiles.map(p => `<option value="${p.id}">${escapeHTML(p.name)}</option>`).join('') || '<option>Create your first profile</option>';
}
document.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));
document.addEventListener('click', guard(async event => {
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
$('aboutButton').addEventListener('click', () => openDialog('aboutDialog'));
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
    if (state.metro) stopMetronome();
    else await startMetronome();
}));
$('bpm').addEventListener('input', guard(async () => {
    $('bpmLabel').textContent = `${$('bpm').value} BPM`;
    if (state.metro) {
        stopMetronome();
        await startMetronome();
    }
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
    if (location.pathname === '/about') openDialog('aboutDialog');
}
guard(init)();
