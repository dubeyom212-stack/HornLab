# HornLab

**Spend less time deciding what to practice and more time playing.**

HornLab is a music practice planner created by French horn player and student
Om Dubey. Add the pieces, auditions, assignments, and technique work on your list,
choose how much time you have, and build a session around what needs attention.

## Features

- **Practice profiles:** store a name, instrument, and usual session length.
- **Practice list:** add items with a category, deadline, priority, and confidence level.
- **Session planning:** choose balanced, deadline-focused, or weakest-first planning.
- **Guided practice:** work through a warmup and selected items with suggested time
  allocations, directions, and a success target.
- **Session timer:** move between practice blocks and pause or resume the timer.
- **Practice totals:** see saved session counts, total minutes, and minutes across
  the last seven sessions.

The current planner uses rules based on deadlines, confidence, priority, and
when an item was last practiced. It does not require an AI service or API key.
Instrument names are customizable; the built-in warmup directions are horn-focused.

## Run locally

You need Python and Git. Python 3.11 or newer is a suggested starting point.

```sh
git clone https://github.com/dubeyom212-stack/HornLab.git
cd HornLab
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install Flask Flask-SQLAlchemy
.\.venv\Scripts\python.exe -m flask --app app run --port 5000
```

### macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install Flask Flask-SQLAlchemy
.venv/bin/python -m flask --app app run --port 5000
```

Open [localhost:5000](http://127.0.0.1:5000). If there are no profiles, HornLab opens
the setup page. Otherwise, it opens an existing profile. You can visit
[/setup](http://127.0.0.1:5000/setup) to create another one.

Dependencies are installed directly here because the current repository does not
include a requirements file. There is no frontend build step.

## Your first session

1. Create a profile with your instrument and usual practice time.
2. Add a practice item, such as an audition excerpt or a technique exercise.
3. Set its deadline, priority, and how confident you feel about it.
4. Choose your available minutes and planning mode, then select **Build my session**.
5. Work through the session and finish it to save your practice record.

Completed items get a last-practiced date that affects future planning. Leaving
an unfinished session does not save its progress.

## How planning works

The planner ranks active items using four signals:

| Signal | What it represents |
| --- | --- |
| Deadline | How soon the item is due, including overdue work. |
| Confidence | Whether the item needs work, is developing, or feels solid. |
| Priority | The importance you assigned to the item. |
| Recency | How long it has been since you last practiced it. |

Balanced mode gives the most weight to deadlines and confidence. Deadline mode
emphasizes urgency; weakest-first mode emphasizes lower confidence. The planner
reserves time for a warmup, then selects up to four items depending on session
length. These are suggested allocations, not an assessment of playing ability.

## Data and local use

HornLab uses Flask, Flask-SQLAlchemy, SQLite, Jinja templates, and browser JavaScript.
Profiles, practice items, and sessions are stored in `instance/hornlab.db`.
Tables are created automatically when the application starts.

The current repository includes `hornlab.db` and `hornlab_old.db`, so a clone may
already contain saved records. The app uses `hornlab.db`; the old file is not
selected by the application. Back up your database before replacing a checkout or
changing stored data, and do not commit personal practice records.

Profiles are not password-protected accounts. The current app has no sign-in or
access controls and is intended for trusted local use. Keep it on localhost;
public hosting would require authentication and additional security work.
The commands above start Flask's development server.

## Project layout

```text
app.py              Routes, database models, ranking, and session planning
templates/          Jinja pages and browser-side session behavior
static/style.css    Application styles
instance/           SQLite database files
```

## Troubleshooting

- **Missing Flask module:** install the dependencies using the same virtual
  environment Python that you use to start the app.
- **Port 5000 is occupied:** use `--port 5001` and open `http://127.0.0.1:5001`.
- **Empty plan:** add at least one active practice item to the selected profile.
- **Unexpected existing profile:** the repository includes a database; create a
  new profile through `/setup` if needed.
- **Practice totals did not change:** finish the session so it is saved. The
  recent-minutes total refers to the last seven sessions, not seven calendar days.

## Contributing

Create a branch for a focused change and open a pull request describing the
behavior and how you checked it. For planner changes, check different session
lengths, deadlines, confidence levels, and empty practice lists. For UI changes,
check both desktop and narrow screens.

The current published version does not include an automated test suite. At a
minimum, verify profile creation, adding an item, building a plan, finishing a
session, and the updated practice totals before proposing behavior changes.
