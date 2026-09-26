# HornLab

A focused local practice workspace for musicians, built with Flask and SQLite.

## Run

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

On macOS or Linux, use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.
Open http://127.0.0.1:5000. Create a profile, add repertoire, and build a session.

## Workspace

- **Today:** choose 5–180 minutes and a balanced, deadline-first, or weakest-area approach. Plans include a warm-up and conserve the exact requested time.
- **Guided sessions:** pause/resume each step, mark it complete, or finish early. Timer state survives refresh in this browser, separately for each profile. Review actual minutes and practiced items before saving; unfinished steps are not automatically marked practiced.
- **Metronome:** 30–240 BPM with a four-beat accent. Runs while the tab is active and stops on backgrounding. Browser scheduling is not a substitute for precision audio hardware.
- **Repertoire:** create, search, filter, edit, archive, and restore pieces and technical goals. Set confidence, priority, and deadlines.
- **Progress:** Monday-based weekly goals, a 14-day chart, total practice, current streak, and the latest 100 journal entries. A streak includes yesterday when today has not yet been practiced. All dates follow the server computer.
- **Journal:** log guided or manual sessions, track completed repertoire, and export the full history as CSV. Duplicate retries of the same guided save are deduplicated with a session token.

## Existing data

The original `Profile`, `PracticeItem`, and `PracticeSession` table layouts are unchanged. On startup HornLab adds the `practice_goal` and `session_receipt` tables if absent. Back up `instance/hornlab.db` while the app is stopped before upgrading. The old `hornlab_old.db` is not used or modified.

By default the database remains `instance/hornlab.db`. Set `HORNLAB_DATABASE_URI` to use a different database, for example `sqlite:///demo.db` for a separate demo. `PORT` overrides port 5000. Do not commit personal database files.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

The tests use isolated, in-memory databases. They cover all supported plan lengths with 1–5 repertoire items in each mode, ranking, profile-scoped edits, archive/restore, validation, duplicate session retries, CSV output, calendar totals, and old schema compatibility.

Browser verification covers profile creation, repertoire editing, archive/restore, search, generating a session, timer recovery after reload, metronome controls, saving a journal entry, weekly goals, and desktop/mobile layouts.

## Operating scope

This is a personal/local app, bound to `127.0.0.1` by default with debug mode disabled. Profiles are organizational conveniences, not authenticated accounts; anyone with access to this app can select another profile. Do not expose it publicly without adding authentication, authorization, CSRF protection, a production server, and a deployment-specific review.

Session timer state is stored in browser local storage, so private browsing or clearing storage removes that unsaved state. Recorded sessions and repertoire remain in SQLite. Use one active tab per profile for a guided session. The UI uses optional Google Fonts with system fallbacks and has no JavaScript CDN dependencies.
