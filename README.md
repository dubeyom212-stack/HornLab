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
- **Metronome:** 30–240 BPM with tap tempo, custom 1–12-beat bars, half/quarter/eighth/sixteenth note values, 1–4 clicks per counted beat, per-beat strong/normal/silent accents, and volume. Compound 6/8, 9/8, and 12/8 can count dotted-quarter groups or individual eighth notes. BPM always names the counted note value. Settings persist per profile in this browser. Clicks are scheduled against the Web Audio clock and stop when the tab is hidden. Changing settings restarts at beat 1.
- **Repertoire:** create, search, filter, edit, archive, and restore pieces and technical goals. Set confidence, priority, and deadlines.
- **Progress:** Monday-based weekly goals, a 14-day chart, total practice, current streak, and the latest 100 journal entries. A streak includes yesterday when today has not yet been practiced. All dates follow the server computer.
- **Journal:** log guided or manual sessions, track completed repertoire, and export the full history as CSV. Duplicate retries of the same guided save are deduplicated with a session token.

## Passage goals and feedback

In **Repertoire → Passage goals**, attach a measure range or specific goal to a piece. Set a starting tempo, target tempo, clean-repetition goal, and tempo unit. At the end of a guided session (or in a manual log), optionally record the actual tempo, clean repetitions, and a short passage note.

New plans give unfinished passage goals an additional ranking weight and select one passage per chosen repertoire item. Within a piece, unfinished goals come first, then the oldest practice date. No result starts at the baseline; fewer than the target clean repetitions suggests staying at the last tempo; meeting the repetition goal suggests +4 BPM up to the target. A goal met at target tempo becomes a review suggestion. These are transparent practice heuristics, not automatic audio assessment; results are self-reported.

**Progress → Passage progress** shows the last result, best tempo meeting the current repetition goal, and the next suggested step. History preserves the latest 20 results with the tempo unit and goals recorded at that time. All results remain in the database. Changing the tempo unit separates comparisons; it does not relabel older results. Session CSV export remains a summary of dates, minutes, focus, and session notes; passage-level results are viewed in passage history.

Passage archive/restore preserves history. Archiving a repertoire item excludes its passages from new plans. Existing in-progress plans keep their original goals; generate a new plan after editing a goal.

## Existing data

The original `Profile`, `PracticeItem`, and `PracticeSession` table layouts are unchanged. On startup HornLab adds the `practice_goal`, `session_receipt`, `passage`, and `passage_result` tables if absent. Back up `instance/hornlab.db` while the app is stopped before upgrading. The old `hornlab_old.db` is not used or modified.

By default the database remains `instance/hornlab.db`. Set `HORNLAB_DATABASE_URI` to use a different database, for example `sqlite:///demo.db` for a separate demo. `PORT` overrides port 5000. Do not commit personal database files.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

The tests use isolated, in-memory databases. They cover all supported plan lengths with 1–5 repertoire items in each mode, ranking, profile-scoped edits, archive/restore, validation, duplicate session retries, CSV output, calendar totals, and old schema compatibility.

Browser verification covers profile creation, repertoire editing, archive/restore, search, generating a session, timer recovery after reload, metronome controls, saving a journal entry, weekly goals, and desktop/mobile layouts.

The seven metronome scheduling tests need Node.js 18 or newer (Node is not needed to run HornLab):

```sh
node --test test_metronome.cjs
```

The tracking tests cover repeat/advance/review suggestions, history snapshots, tempo-unit changes, validation, profile separation, archived passages, additive database tables, and retry deduplication. Audio tests cover meter lengths, compound subdivision timing, muted beats, cancellation, and stalled-tab recovery.

## Operating scope

This is a personal/local app, bound to `127.0.0.1` by default with debug mode disabled. Profiles are organizational conveniences, not authenticated accounts; anyone with access to this app can select another profile. Do not expose it publicly without adding authentication, authorization, CSRF protection, a production server, and a deployment-specific review.

Session timer state is stored in browser local storage, so private browsing or clearing storage removes that unsaved state. Recorded sessions and repertoire remain in SQLite. Use one active tab per profile for a guided session. The UI uses optional Google Fonts with system fallbacks and has no JavaScript CDN dependencies.
