/* Web Audio clock scheduling; UI timers never determine click onset times. */
(function(root) {
    'use strict';
    const integer = (v, fallback, low, high) => Number.isInteger(Number(v)) && Number(v) >= low && Number(v) <= high ? Number(v) : fallback;

    function normalize(input = {}) {
        const numerator = integer(input.numerator, 4, 1, 12);
        const denominator = [2, 4, 8, 16].includes(Number(input.denominator)) ? Number(input.denominator) : 4;
        const compound = Boolean(input.compound) && denominator === 8 && numerator >= 6 && numerator % 3 === 0;
        const beats = compound ? numerator / 3 : numerator;
        const accents = Array.from({
            length: beats
        }, (_, i) => [0, 1, 2].includes(input.accents?.[i]) ? input.accents[i] : i === 0 ? 2 : 1);
        return {
            numerator,
            denominator,
            compound,
            beats,
            accents,
            bpm: integer(input.bpm, 80, 30, 240),
            subdivision: integer(input.subdivision, 1, 1, 4),
            volume: integer(input.volume, 60, 0, 100),
            unit: compound ? 'dotted-quarter' : ({
                2: 'half',
                4: 'quarter',
                8: 'eighth',
                16: 'sixteenth'
            })[denominator]
        };
    }

    function eventAt(step, settings) {
        const s = normalize(settings);
        const beat = Math.floor(step / s.subdivision) % s.beats;
        const sub = step % s.subdivision;
        const accent = s.accents[beat];
        return {
            beat,
            sub,
            accent,
            frequency: sub ? 650 : accent === 2 ? 1250 : 880,
            level: accent === 0 ? 0 : (sub ? .045 : accent === 2 ? .18 : .11) * s.volume / 100,
            interval: 60 / s.bpm / s.subdivision
        };
    }
    class Engine {
        constructor({
            contextFactory,
            onTick = () => {},
            timers = globalThis
        } = {}) {
            this.contextFactory = contextFactory || (() => new(globalThis.AudioContext || globalThis.webkitAudioContext)());
            this.onTick = onTick;
            this.timers = timers;
            this.nodes = new Set();
            this.visuals = new Set();
            this.generation = 0;
            this.running = false;
            this.interval = null;
        }
        stop() {
            this.generation++;
            this.running = false;
            if (this.interval !== null) this.timers.clearInterval(this.interval);
            this.interval = null;
            for (const timer of this.visuals) this.timers.clearTimeout(timer);
            this.visuals.clear();
            for (const node of this.nodes) {
                try {
                    node.stop();
                } catch {}
            }
            this.nodes.clear();
        }
        async start(settings) {
            this.stop();
            const generation = this.generation;
            this.context ||= this.contextFactory();
            await this.context.resume();
            if (generation !== this.generation) return;
            this.settings = normalize(settings);
            this.running = true;
            this.next = this.context.currentTime + .04;
            this.step = 0;
            this.schedule();
            this.interval = this.timers.setInterval(() => this.schedule(), 25);
        }
        schedule() {
            if (!this.running) return;
            const now = this.context.currentTime;
            // A stalled tab must never replay a backlog of clicks.
            if (this.next < now) {
                this.next = now + .04;
                this.step = 0;
            }
            while (this.next < now + .12) {
                const event = eventAt(this.step, this.settings);
                if (event.level > 0) {
                    const oscillator = this.context.createOscillator(),
                        gain = this.context.createGain();
                    oscillator.frequency.value = event.frequency;
                    gain.gain.setValueAtTime(event.level, this.next);
                    gain.gain.exponentialRampToValueAtTime(.0001, this.next + .045);
                    oscillator.connect(gain);
                    gain.connect(this.context.destination);
                    oscillator.onended = () => {
                        oscillator.disconnect();
                        gain.disconnect();
                        this.nodes.delete(oscillator);
                    };
                    this.nodes.add(oscillator);
                    oscillator.start(this.next);
                    oscillator.stop(this.next + .05);
                }
                const generation = this.generation;
                const timer = this.timers.setTimeout(() => {
                    this.visuals.delete(timer);
                    if (this.running && this.generation === generation) this.onTick(event);
                }, Math.max(0, (this.next - now) * 1000));
                this.visuals.add(timer);
                this.next += event.interval;
                this.step++;
            }
        }
    }
    const api = {
        normalize,
        eventAt,
        Engine
    };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.HornMetronome = api;
})(globalThis);
