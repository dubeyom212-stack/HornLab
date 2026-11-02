"""Private accounts, revocable sessions, and form/API request protection."""

import hashlib
import hmac
import os
import re
import secrets
import tempfile
import time
from datetime import timedelta
from pathlib import Path

import click
from flask import (
    Blueprint, current_app, g, jsonify, redirect, render_template,
    request, session, url_for,
)
from flask.sessions import SecureCookieSessionInterface
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from database import db

accounts = Blueprint("accounts", __name__)
SESSION_SECONDS = 8 * 60 * 60


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    storage_id = db.Column(db.String(32), nullable=False, unique=True, default=lambda: secrets.token_hex(16))


class AccountSession(db.Model):
    token_hash = db.Column(db.String(64), primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False)
    expires = db.Column(db.Float, nullable=False, index=True)


class AuthThrottle(db.Model):
    bucket = db.Column(db.String(64), primary_key=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    expires = db.Column(db.Float, nullable=False, index=True)


class SiteCookieSessionInterface(SecureCookieSessionInterface):
    def get_cookie_secure(self, app):
        # HTTPS hosts get Secure cookies; localhost still works over HTTP.
        return app.config["SESSION_COOKIE_SECURE"] or request.is_secure


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def username_value(value):
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{3,30}", value):
        raise ValueError("Use 3 to 30 letters, numbers, periods, hyphens, or underscores.")
    return value


def password_value(value):
    if not 12 <= len(value) <= 128:
        raise ValueError("Use a password with 12 to 128 characters.")
    return value


def throttle(action, limit, seconds):
    """An atomic, database-backed limit shared by the hosting workers."""
    now = time.time()
    window = int(now // seconds)
    identity = f"{action}:{request.remote_addr}:{window}".encode()
    bucket = hmac.new(current_app.secret_key.encode(), identity, hashlib.sha256).hexdigest()
    AuthThrottle.query.filter(AuthThrottle.expires <= now).delete()
    AccountSession.query.filter(AccountSession.expires <= now).delete()
    db.session.commit()
    if not db.session.get(AuthThrottle, bucket):
        db.session.add(AuthThrottle(bucket=bucket, attempts=0, expires=(window + 1) * seconds))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()  # Another worker created this bucket first.
    result = db.session.execute(
        update(AuthThrottle)
        .where(AuthThrottle.bucket == bucket, AuthThrottle.attempts < limit)
        .values(attempts=AuthThrottle.attempts + 1)
    )
    db.session.commit()
    if not result.rowcount:
        return False
    return True


def sign_in(account):
    if g.auth_session:
        db.session.delete(g.auth_session)
    session.clear()
    token = secrets.token_urlsafe(32)
    db.session.add(AccountSession(
        token_hash=token_hash(token), account_id=account.id,
        expires=time.time() + SESSION_SECONDS,
    ))
    db.session.commit()
    session["auth"] = token
    session.permanent = True
    csrf_token()


def auth_page(register=False, error=None, status=200):
    return render_template(
        "account.html", register=register, error=error,
        username=request.form.get("username", "")[:30],
    ), status


@accounts.route("/register", methods=["GET", "POST"])
def register():
    if g.account:
        return redirect(url_for("workspace.index"))
    if request.method == "GET":
        return auth_page(register=True)
    if not throttle("register", 5, 3600):
        return auth_page(True, "Too many signup attempts. Try again in an hour.", 429)
    try:
        username = username_value(request.form.get("username", ""))
        password = password_value(request.form.get("password", ""))
        if password != request.form.get("confirm_password"):
            raise ValueError("The passwords do not match.")
    except ValueError as error:
        return auth_page(True, str(error), 400)
    account = Account(username=username, password_hash=generate_password_hash(password))
    db.session.add(account)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return auth_page(True, "That username is already taken. Choose another.", 409)
    sign_in(account)
    return redirect(url_for("workspace.index"))


@accounts.route("/login", methods=["GET", "POST"])
def login():
    if g.account:
        return redirect(url_for("workspace.index"))
    if request.method == "GET":
        return auth_page()
    if not throttle("login", 20, 900):
        return auth_page(False, "Too many sign-in attempts. Try again in 15 minutes.", 429)
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    account = Account.query.filter_by(username=username).first()
    # Unknown usernames still run the same password hash check.
    stored = account.password_hash if account else current_app.config["DUMMY_PASSWORD_HASH"]
    valid = check_password_hash(stored, password) if len(password) <= 128 else False
    if not account or not valid:
        return auth_page(False, "The username or password is incorrect.", 401)
    sign_in(account)
    return redirect(url_for("workspace.index"))


@accounts.post("/logout")
def logout():
    if g.auth_session:
        db.session.delete(g.auth_session)
        db.session.commit()
    session.clear()
    return redirect(url_for("accounts.login"))


@accounts.get("/api/account")
def account_status():
    return jsonify(id=g.account.id, username=g.account.username, storage_id=g.account.storage_id)


def install_accounts(app):
    if not app.secret_key:
        if app.testing:
            app.secret_key = secrets.token_hex(32)
        else:
            # Persistent across reloads and workers; never checked into source.
            path = Path(app.instance_path) / "session.key"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                # Publish a complete file atomically when workers start together.
                with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
                    candidate = Path(output.name)
                    output.write(secrets.token_hex(32))
                try:
                    os.link(candidate, path)
                except FileExistsError:
                    pass
                finally:
                    candidate.unlink()
            app.secret_key = path.read_text().strip()
            if len(app.secret_key) < 32:
                raise RuntimeError("HornLab's session key is missing or incomplete.")
    if not app.testing and (not isinstance(app.secret_key, str) or len(app.secret_key) < 32):
        raise RuntimeError("Set HORNLAB_SECRET_KEY to a random value of at least 32 characters.")
    app.config.update(
        SESSION_COOKIE_NAME="hornlab_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=SESSION_SECONDS),
        SESSION_REFRESH_EACH_REQUEST=False,
        DUMMY_PASSWORD_HASH=generate_password_hash(secrets.token_urlsafe(32)),
    )
    app.session_interface = SiteCookieSessionInterface()
    app.register_blueprint(accounts)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def protect_workspace():
        if request.endpoint == "static":
            return
        g.account = None
        g.auth_session = None
        raw = session.get("auth")
        if isinstance(raw, str):
            record = db.session.get(AccountSession, token_hash(raw))
            if record and record.expires > time.time():
                g.account = db.session.get(Account, record.account_id)
                if g.account:
                    g.auth_session = record
        public = request.endpoint in {"accounts.login", "accounts.register"} or (
            request.endpoint == "workspace.about"
        )
        if not public and not g.account:
            if request.path.startswith("/api/"):
                return jsonify(error="Sign in to open your practice workspace."), 401
            return redirect(url_for("accounts.login"))
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
            expected = session.get("csrf", "")
            if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
                if request.path.startswith("/api/"):
                    return jsonify(error="Your sign-in changed. Reload the page and try again."), 403
                return auth_page(request.endpoint == "accounts.register", "Reload the page and try again.", 403)

    @app.after_request
    def private_response(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.cli.command("claim-legacy-profile")
    @click.option("--username", required=True)
    @click.option("--profile-id", required=True, type=int)
    def claim_legacy(username, profile_id):
        """Assign one old shared profile, using the server owner's console only."""
        from app import Profile
        account = Account.query.filter_by(username=username.lower()).first()
        profile = db.session.get(Profile, profile_id)
        if not account or not profile:
            raise click.ClickException("Account or profile not found.")
        if profile.owner_id is not None:
            raise click.ClickException("This profile already belongs to an account.")
        profile.owner_id = account.id
        db.session.commit()
        click.echo(f"Assigned profile {profile.id} to {account.username}.")

    @app.cli.command("reset-account-password")
    @click.argument("username")
    @click.password_option(confirmation_prompt=True)
    def reset_password(username, password):
        """Help a pilot tester recover their account from the server console."""
        account = Account.query.filter_by(username=username.lower()).first()
        if not account:
            raise click.ClickException("Account not found.")
        try:
            password = password_value(password)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        account.password_hash = generate_password_hash(password)
        AccountSession.query.filter_by(account_id=account.id).delete()
        db.session.commit()
        click.echo("Password reset. Previous sign-ins have been revoked.")
