import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

os.environ["HORNLAB_DATABASE_URI"] = "sqlite:///:memory:"

from accounts import Account, AccountSession, AuthThrottle
from app import Profile, PracticeItem, PracticeSession, create_app, db
from test_app import registered_client


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SECRET_KEY": "test-only-session-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.context = self.app.app_context()
        self.context.push()
        self.client = registered_client(self.app)
        self.profile = self.client.post("/api/profiles", json={"name": "My horn"}).json["profile"]["id"]

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def form(self, client, path, **values):
        client.get(path)
        with client.session_transaction() as signed_session:
            csrf = signed_session["csrf"]
        return client.post(path, data={"csrf_token": csrf, **values})

    def test_anonymous_workspace_and_every_api_are_protected(self):
        guest = self.app.test_client()
        for path in ("/", "/setup"):
            self.assertEqual(guest.get(path).location, "/login")
        about = guest.get("/about")
        self.assertEqual(about.status_code, 200)
        self.assertIn("Om Dubey", about.text)
        self.assertNotIn('id="profileSelect"', about.text)
        self.assertNotIn("My horn", about.text)
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith("/api/"):
                continue
            path = rule.rule.replace("<int:profile_id>", "1").replace("<int:item_id>", "1").replace("<int:passage_id>", "1")
            for method in rule.methods - {"OPTIONS", "HEAD"}:
                response = guest.open(path, method=method, json={})
                self.assertEqual(response.status_code, 401, (method, path))
        self.assertEqual(guest.get("/login").status_code, 200)
        self.assertEqual(guest.get("/register").status_code, 200)

    def test_password_is_hashed_and_username_is_normalized(self):
        account = Account.query.one()
        self.assertNotEqual(account.password_hash, "test practice passphrase")
        self.assertTrue(account.password_hash.startswith("scrypt:"))
        guest = self.app.test_client()
        response = self.form(guest, "/login", username="MUSICIAN", password="test practice passphrase")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(guest.get("/api/account").json["username"], "musician")
        self.assertNotIn("password", guest.get("/api/account").text)
        duplicate = self.app.test_client()
        response = self.form(duplicate, "/register", username="MUSICIAN", password="another test passphrase", confirm_password="another test passphrase")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Account.query.count(), 1)

    def test_signup_validation_and_password_confirmation(self):
        for username, password, confirmation in (
            ("ab", "long test passphrase", "long test passphrase"),
            ("<script>", "long test passphrase", "long test passphrase"),
            ("tester", "short", "short"),
            ("tester", "long test passphrase", "something different"),
        ):
            guest = self.app.test_client()
            response = self.form(guest, "/register", username=username, password=password, confirm_password=confirmation)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Account.query.count(), 1)

    def test_csrf_blocks_form_and_api_writes_without_changing_data(self):
        guest = self.app.test_client()
        self.assertEqual(guest.post("/register", data={"username": "intruder"}).status_code, 403)
        for path, method, data in (
            ("/api/profiles", "POST", {"name": "Unwanted"}),
            (f"/api/profiles/{self.profile}/instrument", "PATCH", {"instrument": "Piano"}),
            ("/logout", "POST", {}),
        ):
            response = self.client.open(path, method=method, json=data, headers={"X-CSRF-Token": "wrong-token"})
            self.assertEqual(response.status_code, 403)
        self.assertEqual(Profile.query.count(), 1)
        self.assertEqual(db.session.get(Profile, self.profile).instrument, "French horn")
        self.assertEqual(self.client.get("/api/account").status_code, 200)

    def test_other_account_cannot_read_plan_export_or_modify_my_practice(self):
        item = self.client.post("/api/items", json={"profile_id": self.profile, "title": "Private piece"}).json["item"]["id"]
        passage = self.client.post("/api/passages", json={"profile_id": self.profile, "item_id": item, "label": "Private passage"}).json["passage"]["id"]
        saved = self.client.post("/api/session", json={"profile_id": self.profile, "token": str(uuid4()), "duration": 10, "notes": "Private journal"})
        self.assertEqual(saved.status_code, 201)
        other = registered_client(self.app, "other-musician")
        own = other.post("/api/profiles", json={"name": "Other profile"}).json["profile"]["id"]
        self.assertEqual([p["id"] for p in other.get("/api/profiles").json], [own])
        for name in ("items", "passages", "sessions", "insights", "export"):
            response = other.get(f"/api/{name}?profile={self.profile}")
            self.assertEqual(response.status_code, 404, name)
            self.assertNotIn("Private", response.text)
        for path, method, data in (
            ("/api/items", "POST", {"title": "Overwrite"}),
            ("/api/passages", "POST", {"item_id": item, "label": "Overwrite"}),
            ("/api/plan", "POST", {}),
            ("/api/coach", "POST", {}),
            ("/api/session", "POST", {"token": str(uuid4()), "duration": 1}),
            ("/api/goal", "PATCH", {"weekly_minutes": 999}),
            (f"/api/items/{item}", "PATCH", {"title": "Overwrite"}),
            (f"/api/items/{item}", "DELETE", {}),
            (f"/api/passages/{passage}", "PATCH", {"label": "Overwrite"}),
            (f"/api/profiles/{self.profile}/instrument", "PATCH", {"instrument": "Piano"}),
        ):
            response = other.open(path, method=method, json={"profile_id": self.profile, **data})
            self.assertEqual(response.status_code, 404, (method, path))
        # Supplying an owned profile cannot turn a foreign item into an owned one.
        self.assertEqual(other.patch(f"/api/items/{item}", json={"profile_id": own, "title": "Overwrite"}).status_code, 404)
        self.assertEqual(other.patch(f"/api/passages/{passage}", json={"profile_id": own, "label": "Overwrite"}).status_code, 404)
        self.assertEqual(other.post("/api/session", json={"profile_id": own, "duration": 1, "token": str(uuid4()), "completed_item_ids": [item]}).status_code, 400)
        self.assertEqual(PracticeItem.query.one().title, "Private piece")
        self.assertEqual(PracticeSession.query.count(), 1)

    def test_logout_revokes_a_copied_cookie_and_login_rotates_csrf(self):
        cookie = self.client.get_cookie("hornlab_session").value
        copied = self.app.test_client()
        copied.set_cookie("hornlab_session", cookie)
        self.assertEqual(copied.get("/api/profiles").status_code, 200)
        before = self.client.environ_base["HTTP_X_CSRF_TOKEN"]
        self.assertEqual(self.client.post("/logout").status_code, 302)
        self.assertEqual(copied.get("/api/profiles").status_code, 401)
        self.assertEqual(AccountSession.query.count(), 0)
        self.client.environ_base.pop("HTTP_X_CSRF_TOKEN")
        self.form(self.client, "/login", username="musician", password="test practice passphrase")
        with self.client.session_transaction() as signed_session:
            self.assertNotEqual(signed_session["csrf"], before)
        self.assertEqual(self.client.post("/api/profiles", json={"name": "Stale tab"}, headers={"X-CSRF-Token": before}).status_code, 403)

    def test_expired_sessions_and_owner_password_reset_revoke_access(self):
        record = AccountSession.query.one()
        record.expires = time.time() - 1
        db.session.commit()
        self.assertEqual(self.client.get("/api/profiles").status_code, 401)
        guest = self.app.test_client()
        self.form(guest, "/login", username="musician", password="test practice passphrase")
        result = self.app.test_cli_runner().invoke(args=["reset-account-password", "musician"], input="new practice passphrase\nnew practice passphrase\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(guest.get("/api/profiles").status_code, 401)
        newer = self.app.test_client()
        self.assertEqual(self.form(newer, "/login", username="musician", password="test practice passphrase").status_code, 401)
        self.assertEqual(self.form(newer, "/login", username="musician", password="new practice passphrase").status_code, 302)

    def test_failed_signin_limit_persists_across_clients(self):
        for attempt in range(21):
            guest = self.app.test_client()
            response = self.form(guest, "/login", username="unknown-user", password="wrong test passphrase")
            self.assertEqual(response.status_code, 401 if attempt < 20 else 429)
        self.assertLessEqual(AuthThrottle.query.count(), 2)

    def test_cookie_headers_and_private_pages_are_not_cached(self):
        guest = self.app.test_client()
        response = guest.get("/login", base_url="https://localhost")
        cookie = response.headers["Set-Cookie"]
        for flag in ("Secure", "HttpOnly", "SameSite=Lax"):
            self.assertIn(flag, cookie)
        for path in ("/", "/api/profiles", "/api/export?profile=" + str(self.profile)):
            response = self.client.get(path)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")


class LegacyMigrationTests(unittest.TestCase):
    def test_old_data_is_preserved_hidden_and_explicitly_assignable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            with sqlite3.connect(path) as connection:
                connection.executescript("""
                    CREATE TABLE profile (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL,
                        instrument VARCHAR(100) NOT NULL, typical_time INTEGER NOT NULL);
                    INSERT INTO profile VALUES (41, 'Existing player', 'French horn', 30);
                    CREATE TABLE practice_item (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL, category VARCHAR(50) NOT NULL,
                        deadline VARCHAR(20), priority VARCHAR(20) NOT NULL,
                        confidence VARCHAR(20) NOT NULL, last_practiced VARCHAR(20), active BOOLEAN);
                    INSERT INTO practice_item VALUES (61,41,'Existing piece','repertoire',NULL,'medium','developing',NULL,1);
                    CREATE TABLE practice_session (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL,
                        date VARCHAR(20) NOT NULL, duration INTEGER NOT NULL,
                        focus VARCHAR(200) NOT NULL, notes TEXT);
                    INSERT INTO practice_session VALUES (81,41,'2026-10-01',20,'Existing focus','Existing note');
                """)
            connection.close()
            config = {"TESTING": True, "SECRET_KEY": "legacy-test-key", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{path}"}
            app = create_app(config)
            with app.app_context():
                client = registered_client(app, "existing-player")
                self.assertEqual(client.get("/api/profiles").json, [])
                self.assertEqual(client.get("/api/items?profile=41").status_code, 404)
                self.assertEqual(db.session.get(PracticeItem, 61).title, "Existing piece")
                result = app.test_cli_runner().invoke(args=["claim-legacy-profile", "--username", "existing-player", "--profile-id", "41"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(client.get("/api/profiles").json[0]["id"], 41)
                self.assertEqual(client.get("/api/sessions?profile=41").json[0]["notes"], "Existing note")
                second = app.test_cli_runner().invoke(args=["claim-legacy-profile", "--username", "existing-player", "--profile-id", "41"])
                self.assertNotEqual(second.exit_code, 0)
                db.session.remove()
                db.engine.dispose()
            # A second startup must leave the schema, ownership and rows intact.
            restarted = create_app(config)
            with restarted.app_context():
                self.assertEqual(Profile.query.count(), 1)
                self.assertIsNotNone(db.session.get(Profile, 41).owner_id)
                self.assertEqual(PracticeSession.query.count(), 1)
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
