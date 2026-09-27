# Put HornLab online for free

Use PythonAnywhere's free account for this Flask app. Your address will be `https://YOURUSERNAME.pythonanywhere.com`. You do not need a domain, a credit card for a paid plan, or your laptop running once the website is set up.

The free plan currently includes one small web app, 512 MiB storage, and a one-month web-app expiry. Check the Web tab's expiry date regularly and use its renewal control before that date. This is a small demo host, not unlimited hosting. See [current free-account limits](https://help.pythonanywhere.com/pages/FreeAccountsFeatures).

## Before sharing

This version has shared profiles, not private accounts: visitors can view and change the same practice data. Start with a fresh demo database and sample notes. Do not upload your local database. Private use by multiple musicians needs login and access controls first. The About photos and name will be visible to anyone with the public URL.

## 1. Create your hosting account

Open [PythonAnywhere](https://www.pythonanywhere.com/pricing/) and choose the limited free account. Pick your username carefully: it becomes the first part of your website address. Complete signup yourself.

## 2. Upload the latest ZIP

Use **HornLab-advanced.zip from this chat**, which includes the About page, photos, and logo. On PythonAnywhere open **Files**, stay in `/home/YOURUSERNAME`, and upload the ZIP. Do not upload a Windows virtual environment or your `instance` folder.

Open **Consoles → Bash**. The following commands go in that PythonAnywhere Bash console, not in Windows PowerShell or a Python prompt. Run each separately:

```bash
cd ~
```

```bash
unzip HornLab-advanced.zip -d HornLab
```

```bash
cd ~/HornLab
```

```bash
ls
```

You should see `app.py`, `requirements.txt`, `static`, and `templates`. If you do not, stop and locate the folder containing `app.py` before continuing.

## 3. Install the dependencies

Use Python 3.13 if offered by your account. If it offers a different version, use that same version in both this command and the Web tab (Python 3.10 or newer).

```bash
mkvirtualenv --python=/usr/bin/python3.13 hornlab-env
```

```bash
pip install -r requirements.txt
```

## 4. Create the website

Open **Web → Add a new web app**. Keep the free PythonAnywhere address. Choose **Manual configuration**, then the same Python version you used above. Do not choose the starter Flask template: you already have an app.

In the Web tab, set:

| Setting | Value (replace YOURUSERNAME) |
| --- | --- |
| Source code | `/home/YOURUSERNAME/HornLab` |
| Working directory | `/home/YOURUSERNAME/HornLab` |
| Virtualenv | `/home/YOURUSERNAME/.virtualenvs/hornlab-env` |

Open the **WSGI configuration file** linked in that tab. Replace its example content with the following. Replace YOURUSERNAME with your actual username, preserving capitalization:

```python
import sys

project = '/home/YOURUSERNAME/HornLab'
if project not in sys.path:
    sys.path.insert(0, project)

from app import app as application
```

Save. HornLab creates its empty database automatically when imported. Do not run `python app.py` to publish; the Web tab runs the website for you. See [PythonAnywhere's Flask setup](https://help.pythonanywhere.com/pages/Flask).

## 5. Connect the photos and styling

Under **Static files**, add:

- URL: `/static/`
- Directory: `/home/YOURUSERNAME/HornLab/static`

Map only that static folder, not the entire project or database folder. [Static-file setup reference](https://help.pythonanywhere.com/pages/StaticFiles/).

## 6. Reload and try it

Click the green **Reload** button on the Web tab, then open `https://YOURUSERNAME.pythonanywhere.com`.

Create a demo profile and add a sample piece. Check About, all three photos, the metronome, and saving a session. Refresh to check the result is still there. Open the same URL on your phone. Once these work, that is the link you can share; `127.0.0.1` is not a public link.

This publishes a mobile-friendly website. It does not yet add full PWA installation/offline support or submit anything to an app store.

## If something goes wrong

- **Cannot find requirements.txt:** Run `pwd` and `ls`. Navigate to the folder with `app.py` and `requirements.txt` before installing.
- **No module named flask:** In Bash run `workon hornlab-env`, then install the requirements. Check the Web tab uses that same virtualenv and Python version.
- **Something went wrong / server error:** Open the Web tab's error log. The last few lines usually identify the missing module or incorrect path.
- **Photos or styling missing:** Check the static mapping and click Reload. On a computer, refresh with Ctrl+F5.
- **Site stopped later:** Check the free web app's expiry date in the Web tab.

## Updating later

Back up `HornLab/instance/hornlab.db` first using the Files tab. Upload a new source ZIP, replace the source files, and click Reload. Preserve the existing `instance` folder and database. This chat's source ZIP excludes databases so uploading it does not replace saved practice by itself.

Hosting instructions checked September 26, 2026. Host menus and free-plan limits may change.


## Update an existing PythonAnywhere site with the Practice room

Download the latest `HornLab-advanced.zip` from the chat. First download a backup of `HornLab/instance/hornlab.db` from PythonAnywhere's Files tab. Upload the new ZIP into your home folder, replacing the older ZIP if asked. In a PythonAnywhere Bash console run:

```bash
cd ~
unzip -o HornLab-advanced.zip -d HornLab
```

This ZIP contains source files, not a database. The command replaces matching source files and keeps your `instance` database. In the Web tab click **Reload**, then refresh the website. You should see **Practice** in the navigation. There are no new Python dependencies for this update.

Use your **https://** website address for microphone access. Click **Record a take**, allow the microphone, play a short passage, and click **Stop**. Try playback before relying on the recording. Audio stays in that browser; recordings made on localhost do not transfer to the public site. Download them from the original browser if you want to import them on the public site.
