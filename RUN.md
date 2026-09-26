# Running HornLab

This guide runs HornLab on your own computer. You do not need to merge the GitHub pull request to try the upgraded version.

## 1. Get the upgraded code

1. Open the [HornLab upgrade branch](https://github.com/dubeyom212-stack/HornLab/tree/codex/advanced-practice-workspace).
2. Click **Code**, then **Download ZIP**.
3. Extract the ZIP into a folder you can find again.
4. Open the extracted folder containing `app.py`, `requirements.txt`, and this guide.

If the upgrade has already been merged into `main`, you can download `main` instead. If you already have the extracted `HornLab-advanced.zip` from this chat, use that folder.

## 2. First-time setup on Windows

You need Python 3.10 or newer and an internet connection for the first installation.

In the HornLab folder, right-click an empty space and choose **Open in Terminal**. Use a PowerShell tab. You can also open PowerShell, type `cd `, drag the HornLab folder into the window, and press Enter.

Check Python:

```powershell
python --version
```

If Python is not available, install Python 3.10 or newer, reopen the terminal, and try again. If `py --version` works instead, use `py` for the first command below.

Run these commands one at a time:

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe app.py
```

When the terminal shows `Running on http://127.0.0.1:5000`, open [HornLab in your browser](http://127.0.0.1:5000).

Keep the terminal open while using HornLab. These commands use the environment's Python directly; you do not need to activate it or change PowerShell's execution policy.

## 3. Start HornLab next time

Open a terminal in the **same HornLab folder**, then run only:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

To stop HornLab, return to the terminal and press **Ctrl+C**. Closing the browser alone does not stop the app.

## 4. Your first practice session

1. Create a practice profile, or select an existing one.
2. Open **Repertoire** and add a piece or practice goal.
3. Set its confidence, priority, and optional deadline.
4. Open **Today**, choose your available time, and click **Build my session**.
5. Use the timer and complete each step when ready.
6. Review the actual minutes and practiced items, add notes, and save the session.
7. Open **Progress** to see your history and export it.

## Make your practice specific

1. Open **Repertoire**, then **Add passage** under Passage goals.
2. Choose a piece and enter a measure range or goal, such as “Measures 24–32 · clean attacks.”
3. Set your starting tempo, target tempo, clean repetition goal, and tempo unit.
4. Build a new session. The passage step shows a specific goal and, after your first result, where you left off.
5. When saving the session, select **Record** beside a passage and enter the tempo and clean repetitions you actually achieved. You can enter zero clean repetitions.
6. Open **Progress → Passage progress → History** to compare results. Your next plan uses the new result automatically.

The suggested tempo stays the same until you meet the repetition goal, then increases by 4 BPM, capped at your target. These are suggestions based on your entries; HornLab does not listen to or grade your playing.

## Customize the metronome

The **Custom metronome** panel on **Today** works even before you build a session.

- Choose a meter preset, or set the number of beats and written beat value yourself.
- In 6/8, 9/8, or 12/8, choose individual written beats or groups of three. For example, 6/8 can be six eighth-note beats or two dotted-quarter beats.
- The tempo label tells you which note value the BPM measures. Changing the counting mode keeps the displayed BPM, so it changes the bar duration; adjust BPM if you want the same musical pace.
- Choose 1–4 equally spaced clicks per counted beat.
- Click each beat button to cycle **strong → normal → silent**. A silent beat also silences its subdivisions.
- Adjust volume or tap **Tap tempo** repeatedly to set the pace.
- Changes restart the pattern on beat 1. Settings are saved for the selected profile in this browser. Sound stops when the tab is hidden.

**Use tempo in metronome** on a passage applies its suggested tempo. If the current tempo unit matches, your meter and accents are preserved. If it differs, HornLab chooses a matching meter and displays the new note value.

## Updating an older copy

Stop HornLab with **Ctrl+C**, back up `instance/hornlab.db`, and download the latest upgrade branch. Use the data section below to carry your database into the new folder. Run the installation command and start the app from that updated folder, then refresh the browser. Downloading new files does not update an already-running server.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| `python` is not recognized, or opens the Microsoft Store | Try `py --version`. If it works, use `py -m venv .venv`. Otherwise install Python and reopen the terminal. |
| `requirements.txt` or `app.py` cannot be found | Open the extracted folder containing both files. Run `Get-ChildItem` to check the current folder. Do not run the app inside the ZIP. |
| `.venv\Scripts\python.exe` cannot be found | Run `python -m venv .venv` from the HornLab folder first. |
| `No module named flask` or `flask_sqlalchemy` | Run the dependency installation command in step 2, then launch with `.\.venv\Scripts\python.exe app.py`. |
| The browser says it cannot connect | Check that the terminal is still running the app and use the exact address printed there. |
| Port 5000 is already in use | An earlier HornLab session may still be running. Use it, stop it with Ctrl+C, or choose another port as shown below. |
| You see an older version | Stop the old app before starting the upgraded folder. Confirm you downloaded the upgrade branch, then refresh the browser. |
| Your previous profile is missing | Different extracted folders have separate databases. See the data section below before moving files. |

To use port 5001 instead:

```powershell
$env:PORT = "5001"
.\.venv\Scripts\python.exe app.py
```

Then open [http://127.0.0.1:5001](http://127.0.0.1:5001). This setting lasts for that terminal session. To return to the default, stop the app, open a new terminal, and use the usual start command.

## Where your data lives

Profiles, repertoire, and saved sessions are stored in `instance/hornlab.db` inside your HornLab folder. Restarting the app from that folder keeps them.

Before upgrading or moving to a new folder, stop the app and make a backup copy of that database. To carry your data into a new copy of HornLab, copy the backed-up database into the new folder's `instance` directory before starting it. If the destination already has a database, back it up too before replacing it. The upgrade adds its new tables automatically.

The guided timer's unsaved state belongs to the browser and profile. Clearing browser storage removes that timer state, but does not remove sessions already saved in the database. Changing ports uses a different browser storage location.

## macOS or Linux

Open a terminal in the extracted HornLab folder, then run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

For later starts, only run `.venv/bin/python app.py`. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and keep the terminal open.

## Optional: run the automated checks

On Windows, from the HornLab folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

On macOS or Linux, use `.venv/bin/python -m unittest discover -v`.

## Local use

The `127.0.0.1` address works on the computer running HornLab. It is not a public website address or a link you can share with someone on another device. Profiles are not password-protected accounts. Public hosting requires a separate deployment setup.
