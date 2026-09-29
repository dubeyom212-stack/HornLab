# Connect the practice coach

The coach uses Groq to turn a time budget, workload, deadlines, and recent passage results into a short practice plan. It is optional. It does not hear recordings or read sheet music.

## 1. Get a Groq API key

Open [Groq Console](https://console.groq.com/keys), create an eligible account, and create an API key. Keep it private: do not paste it into GitHub, the app's practice notes, or this chat.

Groq offers model-dependent [free request limits](https://console.groq.com/docs/rate-limits). Check your account's available models and limits. This integration defaults to `openai/gpt-oss-20b`, listed on [Groq's models page](https://console.groq.com/docs/models). Free access and model availability can change. Enabling paid billing may create charges; it is not required by HornLab.

## 2. Update PythonAnywhere

Back up `HornLab/instance/hornlab.db`, upload the latest source ZIP, and extract it over the existing folder. Follow the update section in [WEB.md](WEB.md). This update adds one small usage-counter table on startup and does not replace existing data. It needs no new Python packages.

## 3. Store the key privately

In a PythonAnywhere **Bash** console, paste this as one line:

```bash
python -c "from pathlib import Path; from getpass import getpass; p=Path.home()/'.config/hornlab/groq.key'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(getpass('Groq API key (hidden): ').strip()); p.chmod(0o600)"
```

When it asks for the key, paste your key and press Enter. The input is hidden. The key is saved outside the project and outside the public static folder. Do not add that file to a ZIP or repository.

An alternative is the `GROQ_API_KEY` server environment variable. Environment values must be available to the WSGI process, not only a Bash session. The private file method above avoids that confusion. `GROQ_MODEL` optionally changes the model if the default is unavailable to your account.

## 4. Reload and test

Click **Web → Reload** on PythonAnywhere. Open your website using HTTPS, then **Practice**. It should show **AI connected**; this means a key was found, not that the provider has validated it yet.

Add at least one real passage goal in Repertoire. Enter your available time, energy, priority piece, and other commitments. Read the data-sharing checkbox, select it if you agree, then click **Make my practice plan**.

The request sends the brief, instrument, up to 12 active passage goals, associated deadlines/confidence, and recent passage results/notes (notes shortened to 160 characters) to Groq. Your profile name and audio files are not sent. Avoid putting personal details in the brief or notes you choose to share.

The resulting plan explains the priorities, what to skip, a short warmup, and one to three practice tasks. **Practice this** loads the passage and starting tempo into the practice room. Its time budget pauses the task when reached; you can save or deliberately resume. Finish/discard the current passage before starting another task.

## Limits and troubleshooting

- HornLab allows 30 coach requests per server day across the entire app, with a 10-second cooldown. Failed provider calls count too. This protects the key on a site that currently has shared profiles. Groq's own limits may be lower.
- **AI not connected:** check the key file exists under the PythonAnywhere account running the site, then Reload.
- **Connection needs attention:** check the key and model in Groq Console. No secret provider error text is shown in the app.
- **AI service couldn't be reached:** the free PythonAnywhere account requires allowed destinations and the HTTPS proxy. `api.groq.com` is on its [allowlist](https://www.pythonanywhere.com/whitelist/); the standard Python request uses the host's proxy environment.
- **Plan didn't fit:** the app rejected an unknown passage, invalid tempo, or malformed answer. Try again after the cooldown. It never silently substitutes a template and labels it AI.

This is a suggested allocation of practice time, not a guarantee of readiness. You still judge the attempts and decide whether an exercise helps. Real provider response quality needs evaluation with actual practice briefs once your key is connected. No live AI call was made during the credential-free build; tests use fixed provider responses.
