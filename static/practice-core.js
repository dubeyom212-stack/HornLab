(function(root) {
    'use strict';
    function attempt(run, clean) {
        if (run.reset) return run;
        const streak = clean ? run.streak + 1 : 0;
        return {...run, streak, attempts: [...run.attempts, {tempo: run.tempo, clean: !!clean, streak}], ready: streak >= run.passage.target_reps};
    }
    function changeTempo(run, delta) {
        if (run.reset) return run;
        return {...run, tempo: Math.max(30, Math.min(run.passage.target_tempo, run.tempo + delta)), streak: 0, ready: false};
    }
    const drills = {
        rhythm: {label: 'Uneven rhythm', task: 'Clap and count the smallest uneven group twice with the click. Then try just that group twice in the passage, keeping the spaces even.'},
        notes: {label: 'Missed notes', task: 'Choose the two notes where it breaks down. Play that pair slowly three times. Add one note before and after, then try the small group again.'},
        attacks: {label: 'Messy entrances', task: 'Isolate the beginning of the passage. Prepare before the beat, try three consistent starts, then add the next small group.'}
    };
    function drillFor(problem, guidance) {
        const drill = drills[problem];
        if (!drill) return null;
        if (problem === 'attacks' && guidance?.entrance) return {...drill, task: guidance.entrance};
        if (problem === 'notes' && guidance?.family === 'percussion') return {label: 'Missed strokes', task: 'Choose the two strokes where the pattern breaks down. Repeat them slowly three times with the intended sticking, then add one stroke on either side.'};
        if (problem === 'notes' && guidance?.family === 'voice') return {label: 'Pitch or syllable changes', task: 'Choose the two notes or syllables where the phrase breaks down. Sing that pair slowly in a comfortable range, then add the neighboring syllables.'};
        if (problem === 'notes' && (!guidance || guidance.family === 'other')) return {label: 'Unreliable changes', task: 'Choose the smallest change where the passage breaks down. Try it slowly three times, then add a little of the passage on either side.'};
        return drill;
    }
    function beginReset(run, problem) {
        if (run.reset || !drills[problem]) return run;
        const remaining = run.coach ? Math.max(0, Math.floor(run.coach.minutes * 60 - run.seconds)) : 90;
        if (remaining < 20) return run;
        const tempo = Math.max(30, Math.min(run.passage.target_tempo, Math.floor(run.tempo * 0.85)));
        return {...run, tempo, streak: 0, ready: false, paused: false,
            reset: {problem, ...drillFor(problem, run.guidance), start: run.seconds, duration: Math.min(90, remaining), stage: 'working'}};
    }
    function finishReset(run, helped) {
        if (!run.reset) return run;
        const entry = {problem: run.reset.problem, label: run.reset.label, tempo: run.tempo, helped: !!helped};
        return {...run, reset: null, streak: 0, ready: false, paused: true, attemptFloor: run.attempts.length,
            resets: [...(run.resets || []), entry].slice(-8)};
    }
    function resetSummary(run) {
        const last = run.resets?.at(-1);
        return last ? `Reset: ${last.label || drills[last.problem]?.label || 'Passage drill'} at ${last.tempo} BPM; ${last.helped ? 'felt better; retry full passage next' : 'still stuck; revisit this spot next time'}. ` : '';
    }
    function result(run) {
        if (!run.attempts.length) return null;
        // Save the last tempo actually attempted, never a newly unlocked tempo.
        const qualified = run.attempts.filter(a => a.streak >= run.passage.target_reps);
        const last = qualified.length ? qualified.reduce((a,b)=>a.tempo>b.tempo?a:b) : run.attempts.at(-1);
        const best = Math.max(...run.attempts.filter(a => a.tempo === last.tempo).map(a => a.streak));
        return {passage_id: run.passage.id, tempo: last.tempo, clean_reps: Math.min(100, best), tempo_unit: run.passage.tempo_unit,
            notes: `${resetSummary(run)}${run.goal}. ${run.attempts.length} attempts; ${run.attempts.filter(a => a.clean).length} marked clean. ${qualified.length?'Highest tempo meeting the repetition goal':'Last attempted tempo'}: ${last.tempo} BPM; best consecutive clean run there: ${best}.`};
    }
    const api = {attempt, changeTempo, result, drills, drillFor, beginReset, finishReset, resetSummary};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.HornPractice = api;
})(typeof window !== 'undefined' ? window : globalThis);
