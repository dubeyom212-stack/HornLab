# Private accounts

Open HornLab and choose **Create an account**. Pick a username and a password of at least 12 characters. No email is collected. After signing in, create your practice profile and add your instrument and pieces.

Accounts can have several practice profiles. The profile picker only shows the signed-in account's profiles. Profile ownership is checked on the server for pieces, passages, plans, saved sessions, goals, and CSV exports. The public `/about` page explains the project without requiring a sign-in.

Passwords use Werkzeug's scrypt hashing. Sign-ins expire after eight hours. Signing out revokes that sign-in on the server, and forms and API changes require a CSRF token. Sign-in and signup requests have database-backed limits shared by the hosting workers. These controls do not replace HTTPS or host-level protection against heavy traffic.

## Upgrade an existing site

1. Finish or save any open practice sessions. Download recordings you want to keep before upgrading.
2. Back up `instance/hornlab.db`. Keep that database on the host; source downloads should not contain it.
3. Install the complete source from the branch or release being tested, including `accounts.py`, `database.py`, both account templates, the shared About partial, and the changed scripts. A partial practice-only update is insufficient.
4. Reload the host. Startup adds account tables and the profile ownership column while keeping existing pieces, passage results, goals, and sessions.
5. Create your account. Old shared profiles will be hidden until the server owner assigns them. Creating the first account does not claim existing data.

From the host's Bash console, activate the virtual environment, open the folder containing `app.py`, and assign each old profile you own:

```sh
python -m flask --app app claim-legacy-profile --username YOUR_USERNAME --profile-id PROFILE_ID
```

Replace `PROFILE_ID` with the old numeric profile ID, visible in the previous site's `?profile=...` URL. The command only assigns an unowned profile; it cannot transfer someone else's account data. Other musicians cannot run it through the website. For unowned demo profiles, leave them unassigned.

Browser storage is now separated by a random, persistent account identifier. Old browser recordings are not automatically assigned to the first account. Import downloaded audio into the matching account when needed. Recordings and drafts remain on that browser; this update does not add recording sync or device encryption.

## Session key and hosting

The app creates a private `instance/session.key` file on first startup. Keep it across reloads, outside the public static directory. Alternatively, set a strong random `HORNLAB_SECRET_KEY` in the host environment. Never commit either secret or a database. Source archives of this version exclude both old shared databases.

The host must serve the public site over HTTPS. Secure cookies are enabled automatically for requests the app sees as HTTPS. If a hosting proxy terminates HTTPS, configure the host correctly rather than trusting arbitrary client headers. Verify `Secure`, `HttpOnly`, and `SameSite=Lax` on the `hornlab_session` cookie before sharing a public pilot. HTTP localhost remains supported for development.

## Help a tester recover an account

There is no automated email recovery. After verifying the tester's identity yourself, use the host console:

```sh
python -m flask --app app reset-account-password THEIR_USERNAME
```

The command prompts for a new password twice and revokes existing sign-ins. It does not print the password. Share the replacement privately, outside this repository. Do not put passwords in shell command arguments.

The person running the site can access its database and backups. Keep pilot data limited to what musicians need for practice. Browser recordings and drafts remain available to someone with access to that browser profile, even after sign-out.
