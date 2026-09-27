# HornLab

![HornLab](static/hornlab-logo.svg)

I'm Om Dubey. I started HornLab because practice was one more thing to figure out between AP classes, music, and everything else. I wanted a clearer answer to “what should I work on today?”

I'm not in band anymore, but I still care about this problem. This is a student project, and it is still changing as I try it and get feedback.

## What changed after trying it

The first version leaned too much on a timer and a practice log. After using it and getting feedback, it was clear that logging minutes wasn't enough. The newer Practice screen focuses on working through a passage and listening back to actual takes.

## Try a practice session

1. In **Repertoire**, add a piece and a passage goal—something like measures 24–32, starting at 60 BPM, with a target of 80.
2. Open **Practice**, pick that passage, and choose what you're listening for.
3. Play it once. Tap **Clean** or **Again**. A clean streak unlocks a 4 BPM increase; you can also slow down.
4. Record a short take, listen back, and record another. Use **A** and **B** to compare them. You can import audio files too.
5. Hit **Finish & save**. The attempts become a session note automatically. Adding your own note is optional.

The app doesn't decide whether your playing is clean. You do. The tempo ladder is a simple rule, and the “I'm stuck” exercises are written suggestions—not an AI teacher.

## Other things in the app

- A metronome with different meters, subdivisions, accents, tap tempo, and volume.
- Pieces, passage goals, deadlines, and practice history.
- A timed routine if you prefer one, plus weekly totals and CSV export.
- An About page with the reason behind the project and a few photos.

## Run it

You need Python 3.10 or newer. Open a terminal in the folder containing `app.py` and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000. On macOS or Linux, use `.venv/bin/python` for the last two commands.

[RUN.md](RUN.md) has more detailed instructions and help with common setup errors. [WEB.md](WEB.md) covers PythonAnywhere's free hosting and updating an existing site.

## Where things are saved

Pieces and finished sessions are stored in SQLite, normally `instance/hornlab.db`. Back that file up before updating. Starting the app creates missing tables without replacing existing practice data.

Unfinished passage practice is saved in the browser. After a refresh it comes back paused. Use one tab per profile. Active time pauses when you leave Practice or hide the tab; saved minutes are rounded with a one-minute minimum.

Recordings stay in that browser's storage, grouped by profile. They are **not uploaded**, synced between devices, or included in the session CSV. Download takes you want to keep: clearing browser data can remove them. A public website and localhost have separate browser storage.

Recording needs a microphone, browser permission, and HTTPS (localhost works for development). Takes stop after three minutes or when the tab is hidden. Imported files can be up to 15 MB; the local audio collection is capped at 50 MB. If storing a take fails, the page offers a temporary download. Download it before closing the tab. Tempo labels record the practice setting, not a tempo detected from the audio.

## Current limits

Profiles are shared, **not private accounts**. Anyone using the same hosted app can view and change its saved practice data. Use demo data if you share it publicly. Private accounts are still needed before treating it as a personal service for multiple musicians.

The app doesn't listen for wrong notes, grade tone, or generate AI feedback. Microphone recording still needs hands-on testing across real phones and microphones; automated recorder tests use simulated devices. Imported audio and the practice flow have been checked in the browser.

## Development

The backend is Flask with Flask-SQLAlchemy. The interface uses plain JavaScript, HTML, and CSS. Browser recording uses MediaRecorder, and stored audio uses IndexedDB.

```sh
python -m unittest discover -v
node --test test_metronome.cjs test_practice.cjs
```

Python tests cover planning, saved data, and passage results. JavaScript tests cover metronome scheduling, tempo progression, and recording lifecycle behavior. Node is only needed for those tests, not for running the app.

The project has been developed with AI coding assistance. The practice problem and product direction come from my own experience and feedback; changes still need testing with actual players.
