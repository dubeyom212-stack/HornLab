"""HornLab: a local, multi-profile practice workspace."""

import csv
import io
import math
import os
from datetime import date, timedelta
from uuid import UUID

from flask import Flask, Blueprint, Response, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException


db = SQLAlchemy()
bp = Blueprint("workspace", __name__)
CATEGORIES = {"repertoire", "technique", "audition", "performance", "assignment"}
PRIORITIES = {"low", "medium", "high"}
CONFIDENCES = {"needs-work", "developing", "solid"}
MODES = {"balanced", "deadline", "weakest"}


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instrument = db.Column(db.String(100), nullable=False, default="French horn")
    typical_time = db.Column(db.Integer, nullable=False, default=30)
    items = db.relationship(
        "PracticeItem", backref="profile", cascade="all, delete-orphan"
    )
    sessions = db.relationship(
        "PracticeSession", backref="profile", cascade="all, delete-orphan"
    )


class PracticeItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="repertoire")
    deadline = db.Column(db.String(20))
    priority = db.Column(db.String(20), nullable=False, default="medium")
    confidence = db.Column(db.String(20), nullable=False, default="developing")
    last_practiced = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)


class PracticeSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    focus = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text)


# New tables keep existing profile/item/session databases compatible.
class PracticeGoal(db.Model):
    profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), primary_key=True)
    weekly_minutes = db.Column(db.Integer, nullable=False, default=150)


class SessionReceipt(db.Model):
    token = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)
    session_id = db.Column(
        db.Integer, db.ForeignKey("practice_session.id"), nullable=False
    )


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object.")
    return data


def integer(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{label} must be a whole number.")
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a whole number.")
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}.")
    return value


def text_value(value, label, limit, required=True):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{label} is required.")
    if len(value) > limit:
        raise ValueError(f"{label} must be {limit} characters or fewer.")
    return value


def choice(value, allowed, label):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"Choose a valid {label}.")
    return value


def get_profile(value):
    profile_id = integer(value, "Profile", 1, 2147483647)
    return db.get_or_404(Profile, profile_id, description="Profile not found.")


def serialize_item(item):
    return {
        key: getattr(item, key)
        for key in (
            "id",
            "title",
            "category",
            "deadline",
            "priority",
            "confidence",
            "last_practiced",
            "active",
        )
    }


def serialize_session(session):
    return {
        key: getattr(session, key)
        for key in ("id", "date", "duration", "focus", "notes")
    }


def item_values(data):
    deadline = data.get("deadline") or None
    if deadline is not None:
        if not isinstance(deadline, str):
            raise ValueError("Deadline must be a date.")
        try:
            deadline = date.fromisoformat(deadline).isoformat()
        except ValueError:
            raise ValueError("Deadline must be a valid date.")
    return dict(
        title=text_value(data.get("title"), "Title", 200),
        category=choice(data.get("category", "repertoire"), CATEGORIES, "category"),
        priority=choice(data.get("priority", "medium"), PRIORITIES, "priority"),
        confidence=choice(
            data.get("confidence", "developing"), CONFIDENCES, "confidence"
        ),
        deadline=deadline,
    )


def item_score(item, mode="balanced"):
    today = date.today()

    confidence_score = {"needs-work": 1.00, "developing": 0.65, "solid": 0.25}.get(
        item.confidence, 0.50
    )

    priority_score = {"high": 1.00, "medium": 0.60, "low": 0.25}.get(
        item.priority, 0.50
    )

    urgency_score = 0.15

    if item.deadline:
        try:
            deadline = date.fromisoformat(item.deadline)
            days_left = (deadline - today).days

            if days_left <= 0:
                urgency_score = 1.25
            elif days_left <= 2:
                urgency_score = 1.00
            elif days_left <= 7:
                urgency_score = 0.85
            elif days_left <= 14:
                urgency_score = 0.65
            elif days_left <= 30:
                urgency_score = 0.40
            else:
                urgency_score = 0.20

        except ValueError:
            urgency_score = 0.15

    if item.last_practiced:
        try:
            last = date.fromisoformat(item.last_practiced)
            days_since = max(0, (today - last).days)

            if days_since == 0:
                recency_score = 0.10
            elif days_since == 1:
                recency_score = 0.25
            elif days_since <= 3:
                recency_score = 0.45
            elif days_since <= 7:
                recency_score = 0.70
            else:
                recency_score = 0.90

        except ValueError:
            recency_score = 0.50
    else:
        recency_score = 0.90

    if mode == "deadline":
        return (
            urgency_score * 0.55
            + confidence_score * 0.20
            + priority_score * 0.20
            + recency_score * 0.05
        )

    if mode == "weakest":
        return (
            confidence_score * 0.55
            + urgency_score * 0.20
            + priority_score * 0.15
            + recency_score * 0.10
        )

    return (
        urgency_score * 0.40
        + confidence_score * 0.30
        + priority_score * 0.20
        + recency_score * 0.10
    )


# ========================================
# PRACTICE DIRECTIONS
# ========================================


def action_for(item):
    category = item.category
    confidence = item.confidence

    if category in ["audition", "performance"]:
        if confidence == "needs-work":
            return {
                "focus": "Work the part that isn't there yet",
                "instruction": (
                    "Slow it down. Find the hardest spot and "
                    "get three clean reps before pushing the tempo."
                ),
                "success": "3 clean reps",
            }

        if confidence == "developing":
            return {
                "focus": "Clean up the rough spots",
                "instruction": (
                    "Pick the two spots you keep messing up. "
                    "Work them separately, then put them back together."
                ),
                "success": "2 clean spots",
            }

        return {
            "focus": "See what holds up",
            "instruction": (
                "Run the section without stopping. "
                "Afterward, go back to the one thing that stood out."
            ),
            "success": "1 solid run",
        }

    if category == "technique":
        return {
            "focus": "Clean up the basics",
            "instruction": (
                "Pick one thing to focus on. Start slow and "
                "only speed up when it stays clean."
            ),
            "success": "2 clean reps",
        }

    if category == "assignment":
        return {
            "focus": "Get the unfinished part done",
            "instruction": (
                "Start with the section you know you need to work on. "
                "Finish with one full attempt."
            ),
            "success": "One full attempt",
        }

    return {
        "focus": "Keep the fundamentals moving",
        "instruction": (
            "Play enough to get the sound and air feeling right. "
            "You don't need to turn this into a 20-minute warmup."
        ),
        "success": "Feels ready",
    }


def build_plan(profile, minutes, mode="balanced"):
    items = PracticeItem.query.filter_by(profile_id=profile.id, active=True).all()
    ranked = sorted(items, key=lambda item: (-item_score(item, mode), item.id))
    if not ranked:
        return []
    warmup = (
        2
        if minutes <= 10
        else 3
        if minutes <= 20
        else 4
        if minutes <= 30
        else 6
        if minutes <= 45
        else 8
    )
    count = 1 if minutes <= 10 else 2 if minutes <= 30 else 3 if minutes <= 45 else 4
    selected = ranked[:count]
    available = minutes - warmup
    weights = [1.5] + [1.0] * (len(selected) - 1)
    # Largest-remainder allocation conserves the requested number of minutes.
    shares = [available * weight / sum(weights) for weight in weights]
    durations = [math.floor(share) for share in shares]
    for i in sorted(range(len(shares)), key=lambda i: (-(shares[i] - durations[i]), i))[
        : available - sum(durations)
    ]:
        durations[i] += 1
    plan = [
        dict(
            title="Warm up",
            duration=warmup,
            focus="Find your sound",
            instruction="Easy long tones, relaxed breathing, then gentle lip slurs.",
            success="A comfortable, centered sound",
            type="warmup",
            priority=False,
        )
    ]
    for item, duration in zip(selected, durations):
        action = action_for(item)
        if item.category == "repertoire":
            action = dict(
                focus="Make one passage more reliable",
                instruction="Isolate a tricky phrase. Play slowly, then reconnect it to the surrounding music.",
                success="Three relaxed, consistent repetitions",
            )
        plan.append(
            dict(
                title=item.title,
                duration=duration,
                type=item.category,
                item_id=item.id,
                priority=item.priority == "high",
                **action,
            )
        )
    return plan


@bp.get("/")
@bp.get("/setup")
@bp.get("/about")
def index():
    return render_template("workspace.html")


@bp.get("/api/profiles")
def profiles():
    return jsonify(
        [
            dict(
                id=p.id,
                name=p.name,
                instrument=p.instrument,
                typical_time=p.typical_time,
            )
            for p in Profile.query.order_by(Profile.name).all()
        ]
    )


@bp.post("/api/profiles")
def create_profile():
    data = body()
    profile = Profile(
        name=text_value(data.get("name"), "Name", 100),
        instrument=text_value(data.get("instrument", "French horn"), "Instrument", 100),
        typical_time=integer(data.get("typical_time", 30), "Practice time", 5, 180),
    )
    db.session.add(profile)
    db.session.commit()
    return jsonify(
        success=True,
        profile=dict(
            id=profile.id,
            name=profile.name,
            instrument=profile.instrument,
            typical_time=profile.typical_time,
        ),
    ), 201


@bp.get("/api/items")
def list_items():
    profile = get_profile(request.args.get("profile"))
    return jsonify(
        [
            serialize_item(i)
            for i in PracticeItem.query.filter_by(profile_id=profile.id)
            .order_by(PracticeItem.id.desc())
            .all()
        ]
    )


@bp.post("/api/items")
def add_item():
    data = body()
    profile = get_profile(data.get("profile_id"))
    item = PracticeItem(profile_id=profile.id, **item_values(data))
    db.session.add(item)
    db.session.commit()
    return jsonify(success=True, item=serialize_item(item)), 201


@bp.route("/api/items/<int:item_id>", methods=["PATCH", "DELETE"])
def update_item(item_id):
    data = body()
    profile = get_profile(data.get("profile_id"))
    item = db.get_or_404(PracticeItem, item_id)
    if item.profile_id != profile.id:
        return jsonify(error="Item not found in this profile."), 404
    if request.method == "DELETE":
        item.active = False
    else:
        merged = {**serialize_item(item), **data}
        values = item_values(merged)
        active = merged.get("active", True)
        if not isinstance(active, bool):
            raise ValueError("Active must be true or false.")
        for key, value in values.items():
            setattr(item, key, value)
        item.active = active
    db.session.commit()
    return jsonify(success=True, item=serialize_item(item))


@bp.post("/api/plan")
def generate_plan():
    data = body()
    profile = get_profile(data.get("profile_id"))
    minutes = integer(
        data.get("minutes", profile.typical_time), "Practice time", 5, 180
    )
    mode = choice(data.get("mode", "balanced"), MODES, "approach")
    return jsonify(minutes=minutes, mode=mode, plan=build_plan(profile, minutes, mode))


@bp.post("/api/session")
def save_session():
    data = body()
    profile = get_profile(data.get("profile_id"))
    token = text_value(data.get("token"), "Session token", 36)
    try:
        token = str(UUID(token))
    except ValueError:
        raise ValueError("Session token must be a UUID.")
    receipt = db.session.get(SessionReceipt, token)
    if receipt:
        if receipt.profile_id != profile.id:
            raise ValueError("Session token belongs to a different profile.")
        return jsonify(success=True, session_id=receipt.session_id, already_saved=True)
    duration = integer(data.get("duration"), "Duration", 1, 720)
    focus = text_value(data.get("focus", "Practice"), "Focus", 200)
    notes = text_value(data.get("notes", ""), "Notes", 5000, required=False)
    ids = data.get("completed_item_ids", [])
    if not isinstance(ids, list) or len(ids) > 100:
        raise ValueError("Completed items must be a list of up to 100 IDs.")
    completed = []
    for item_id in set(integer(v, "Item ID", 1, 2147483647) for v in ids):
        item = db.session.get(PracticeItem, item_id)
        if not item or item.profile_id != profile.id:
            raise ValueError("A completed item does not belong to this profile.")
        completed.append(item)
    session_date = date.today().isoformat()
    practice = PracticeSession(
        profile_id=profile.id,
        date=session_date,
        duration=duration,
        focus=focus,
        notes=notes,
    )
    db.session.add(practice)
    db.session.flush()
    db.session.add(
        SessionReceipt(token=token, profile_id=profile.id, session_id=practice.id)
    )
    for item in completed:
        item.last_practiced = session_date
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        receipt = db.session.get(SessionReceipt, token)
        if receipt and receipt.profile_id == profile.id:
            return jsonify(
                success=True, session_id=receipt.session_id, already_saved=True
            )
        raise
    return jsonify(success=True, session_id=practice.id), 201


@bp.get("/api/sessions")
def sessions():
    profile = get_profile(request.args.get("profile"))
    return jsonify(
        [
            serialize_session(s)
            for s in PracticeSession.query.filter_by(profile_id=profile.id)
            .order_by(PracticeSession.date.desc(), PracticeSession.id.desc())
            .limit(100)
            .all()
        ]
    )


@bp.patch("/api/goal")
def set_goal():
    data = body()
    profile = get_profile(data.get("profile_id"))
    minutes = integer(data.get("weekly_minutes"), "Weekly goal", 15, 3000)
    goal = db.session.get(PracticeGoal, profile.id)
    if not goal:
        goal = PracticeGoal(profile_id=profile.id)
        db.session.add(goal)
    goal.weekly_minutes = minutes
    db.session.commit()
    return jsonify(success=True, weekly_minutes=minutes)


@bp.get("/api/insights")
def insights():
    profile = get_profile(request.args.get("profile"))
    rows = PracticeSession.query.filter_by(profile_id=profile.id).all()
    totals = {}
    for row in rows:
        totals[row.date] = totals.get(row.date, 0) + row.duration
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    last_week = monday - timedelta(days=7)
    week_minutes = sum(
        v for d, v in totals.items() if monday.isoformat() <= d <= today.isoformat()
    )
    previous = sum(
        v for d, v in totals.items() if last_week.isoformat() <= d < monday.isoformat()
    )
    cursor = (
        today if totals.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    )
    streak = 0
    while totals.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    goal = db.session.get(PracticeGoal, profile.id)
    series = [
        dict(
            date=(today - timedelta(days=i)).isoformat(),
            minutes=totals.get((today - timedelta(days=i)).isoformat(), 0),
        )
        for i in range(13, -1, -1)
    ]
    return jsonify(
        total_minutes=sum(totals.values()),
        session_count=len(rows),
        recent_minutes=sum(
            totals.get((today - timedelta(days=i)).isoformat(), 0) for i in range(7)
        ),
        week_minutes=week_minutes,
        previous_week_minutes=previous,
        streak=streak,
        weekly_goal=goal.weekly_minutes if goal else 150,
        series=series,
    )


@bp.get("/api/export")
def export():
    profile = get_profile(request.args.get("profile"))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Minutes", "Focus", "Notes"])

    def safe(value):
        value = str(value or "")
        return (
            "'" + value
            if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
            else value
        )

    for session in (
        PracticeSession.query.filter_by(profile_id=profile.id)
        .order_by(PracticeSession.date, PracticeSession.id)
        .all()
    ):
        writer.writerow(
            [session.date, session.duration, safe(session.focus), safe(session.notes)]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=hornlab-practice-{profile.id}.csv"
        },
    )


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "HORNLAB_DATABASE_URI", "sqlite:///hornlab.db"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=65536,
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    app.register_blueprint(bp)

    @app.errorhandler(ValueError)
    def invalid(error):
        db.session.rollback()
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    with app.app_context():
        db.create_all()
    return app


app = create_app()
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
