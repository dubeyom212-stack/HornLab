(function(root) {
    'use strict';
    function attempt(run, clean) {
        const streak = clean ? run.streak + 1 : 0;
        return {...run, streak, attempts: [...run.attempts, {tempo: run.tempo, clean: !!clean, streak}], ready: streak >= run.passage.target_reps};
    }
    function changeTempo(run, delta) {
        return {...run, tempo: Math.max(30, Math.min(run.passage.target_tempo, run.tempo + delta)), streak: 0, ready: false};
    }
    function result(run) {
        if (!run.attempts.length) return null;
        // Save the last tempo actually attempted, never a newly unlocked tempo.
        const qualified = run.attempts.filter(a => a.streak >= run.passage.target_reps);
        const last = qualified.length ? qualified.reduce((a,b)=>a.tempo>b.tempo?a:b) : run.attempts.at(-1);
        const best = Math.max(...run.attempts.filter(a => a.tempo === last.tempo).map(a => a.streak));
        return {passage_id: run.passage.id, tempo: last.tempo, clean_reps: Math.min(100, best), tempo_unit: run.passage.tempo_unit,
            notes: `${run.goal}. ${run.attempts.length} attempts; ${run.attempts.filter(a => a.clean).length} marked clean. ${qualified.length?'Highest tempo meeting the repetition goal':'Last attempted tempo'}: ${last.tempo} BPM; best consecutive clean run there: ${best}.`};
    }
    const api = {attempt, changeTempo, result};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.HornPractice = api;
})(typeof window !== 'undefined' ? window : globalThis);
