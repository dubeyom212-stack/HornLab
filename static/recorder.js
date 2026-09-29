(function(root) {
    'use strict';
    class Recorder {
        constructor(env = globalThis) { this.env = env; this.generation = 0; this.active = false; }
        async start(onStop) {
            if (this.active) throw new Error('A recording is already running.');
            if (!this.env.navigator?.mediaDevices?.getUserMedia || !this.env.MediaRecorder) throw new Error('Recording needs HTTPS and a browser with microphone support. You can import an audio file instead.');
            const generation = ++this.generation;
            this.active = true;
            let stream;
            try {
                stream = await this.env.navigator.mediaDevices.getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
                if (generation !== this.generation) { stream.getTracks().forEach(t => t.stop()); return false; }
                this.stream = stream;
                const mime = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find(t => this.env.MediaRecorder.isTypeSupported(t));
                const recorder = new this.env.MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
                this.recorder = recorder;
                let chunks = [], size = 0;
                this.done = new Promise(resolve => {
                    recorder.ondataavailable = e => {
                        if (e.data.size) { chunks.push(e.data); size += e.data.size; }
                        if (size > 15 * 1024 * 1024 && recorder.state === 'recording') this.stop();
                    };
                    recorder.onerror = () => { this.failed = true; this.stop(); };
                    recorder.onstop = () => {
                        clearTimeout(this.limit);
                        stream.getTracks().forEach(t => t.stop());
                        this.stream = null; this.active = false; this.recorder = null;
                        const blob = new Blob(chunks, {type: recorder.mimeType || chunks[0]?.type || 'audio/webm'});
                        chunks = [];
                        onStop(blob, this.failed ? 'Recording was interrupted; this take may be incomplete.' : '');
                        resolve();
                    };
                });
                this.failed = false;
                recorder.start(1000);
                this.limit = setTimeout(() => this.stop(), 180000);
                return true;
            } catch (error) {
                stream?.getTracks().forEach(t => t.stop());
                if (generation !== this.generation) return false;
                this.active = false;
                const messages = {NotAllowedError: 'Microphone access was denied. Allow it in your browser settings, or import a recording.', NotFoundError: 'No microphone was found. Connect one or import an audio file.', NotReadableError: 'The microphone is busy. Close other recording apps and try again.'};
                throw new Error(messages[error.name] || error.message);
            }
        }
        stop() {
            ++this.generation;
            clearTimeout(this.limit);
            if (this.recorder?.state === 'recording') { this.recorder.stop(); return this.done; }
            if (!this.recorder) { this.active = false; this.stream?.getTracks().forEach(t => t.stop()); }
            return this.done || Promise.resolve();
        }
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = Recorder;
    else root.HornRecorder = Recorder;
})(typeof window !== 'undefined' ? window : globalThis);
