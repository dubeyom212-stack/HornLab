"""HornLab: a local, multi-profile practice workspace."""

import csv
import io
import math
import os
import time
from datetime import date, timedelta
from uuid import UUID

import coach
from flask import Blueprint, Flask, Response, jsonify, render_template, request
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


class CoachBudget(db.Model):
    day = db.Column(db.String(10), primary_key=True)
    used = db.Column(db.Integer, nullable=False, default=0)
    last_request = db.Column(db.Float, nullable=False, default=0)


class SessionReceipt(db.Model):
    token = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)
    session_id = db.Column(
        db.Integer, db.ForeignKey("practice_session.id"), nullable=False
    )


class Passage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(
        db.Integer, db.ForeignKey("practice_item.id"), nullable=False, index=True
    )
    label = db.Column(db.String(200), nullable=False)
    start_tempo = db.Column(db.Integer, nullable=False, default=60)
    target_tempo = db.Column(db.Integer, nullable=False, default=100)
    target_reps = db.Column(db.Integer, nullable=False, default=3)
    tempo_unit = db.Column(db.String(20), nullable=False, default="quarter")
    active = db.Column(db.Boolean, nullable=False, default=True)
    item = db.relationship("PracticeItem")
    results = db.relationship("PassageResult", backref="passage", lazy=True)


class PassageResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    passage_id = db.Column(
        db.Integer, db.ForeignKey("passage.id"), nullable=False, index=True
    )
    session_id = db.Column(
        db.Integer, db.ForeignKey("practice_session.id"), nullable=False
    )
    tempo = db.Column(db.Integer, nullable=False)
    clean_reps = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(1000), nullable=False, default="")
    tempo_unit = db.Column(db.String(20), nullable=False)
    target_tempo = db.Column(db.Integer, nullable=False)
    target_reps = db.Column(db.Integer, nullable=False)
    session = db.relationship("PracticeSession")
    __table_args__ = (db.UniqueConstraint("passage_id", "session_id"),)


TEMPO_UNITS = {"quarter", "eighth", "dotted-quarter", "half"}


def passage_values(data):
    start = integer(data.get("start_tempo", 60), "Starting tempo", 30, 240)
    target = integer(data.get("target_tempo", 100), "Target tempo", 30, 240)
    if start > target:
        raise ValueError("Starting tempo cannot exceed the target tempo.")
    return dict(
        label=text_value(data.get("label"), "Passage name or measures", 200),
        start_tempo=start,
        target_tempo=target,
        target_reps=integer(data.get("target_reps", 3), "Clean repetition goal", 1, 20),
        tempo_unit=choice(data.get("tempo_unit", "quarter"), TEMPO_UNITS, "tempo unit"),
    )


def passage_summary(passage):
    rows = sorted(passage.results, key=lambda r: r.id, reverse=True)
    comparable = [r for r in rows if r.tempo_unit == passage.tempo_unit]
    last = comparable[0] if comparable else None
    reached = bool(
        last
        and last.tempo >= passage.target_tempo
        and last.clean_reps >= passage.target_reps
    )
    tempo = (
        passage.start_tempo
        if not last
        else min(
            passage.target_tempo,
            last.tempo + (4 if last.clean_reps >= passage.target_reps else 0),
        )
    )
    if reached:
        next_step = f"Review at {passage.target_tempo} BPM; aim for {passage.target_reps} clean repetitions again."
    elif not last:
        next_step = f"Establish a baseline at {tempo} BPM with {passage.target_reps} clean repetitions."
    elif last.clean_reps < passage.target_reps:
        next_step = f"Stay at {tempo} BPM. Aim for {passage.target_reps} clean repetitions before increasing."
    else:
        next_step = f"Try {tempo} BPM. Aim for {passage.target_reps} clean repetitions; slow down if consistency drops."
    return dict(
        id=passage.id,
        item_id=passage.item_id,
        item_title=passage.item.title,
        item_active=passage.item.active,
        label=passage.label,
        active=passage.active,
        start_tempo=passage.start_tempo,
        target_tempo=passage.target_tempo,
        target_reps=passage.target_reps,
        tempo_unit=passage.tempo_unit,
        suggested_tempo=tempo,
        goal_reached=reached,
        next_step=next_step,
        last_result=dict(
            tempo=last.tempo,
            clean_reps=last.clean_reps,
            notes=last.notes,
            date=last.session.date,
        )
        if last
        else None,
        best_clean_tempo=max(
            (r.tempo for r in comparable if r.clean_reps >= passage.target_reps),
            default=None,
        ),
        result_count=len(rows),
        history=[
            dict(
                tempo=r.tempo,
                clean_reps=r.clean_reps,
                notes=r.notes,
                tempo_unit=r.tempo_unit,
                date=r.session.date,
                target_tempo=r.target_tempo,
                target_reps=r.target_reps,
            )
            for r in rows[:20]
        ],
    )


def chosen_passage(item):
    passages = [
        passage_summary(p)
        for p in Passage.query.filter_by(item_id=item.id, active=True).all()
    ]
    # Unfinished goals come first; rotate by the oldest recorded practice date.
    return (
        min(
            passages,
            key=lambda p: (
                p["goal_reached"],
                (p["last_result"] or {}).get("date", ""),
                p["id"],
            ),
        )
        if passages
        else None
    )


@bp.get("/api/passages")
def list_passages():
    profile = get_profile(request.args.get("profile"))
    passages = (
        Passage.query.join(PracticeItem)
        .filter(PracticeItem.profile_id == profile.id)
        .order_by(Passage.id)
        .all()
    )
    return jsonify([passage_summary(p) for p in passages])


@bp.post("/api/passages")
def add_passage():
    data = body()
    profile = get_profile(data.get("profile_id"))
    item = db.get_or_404(
        PracticeItem, integer(data.get("item_id"), "Item", 1, 2147483647)
    )
    if item.profile_id != profile.id or not item.active:
        raise ValueError("Choose an active item in this profile.")
    passage = Passage(item_id=item.id, **passage_values(data))
    db.session.add(passage)
    db.session.commit()
    return jsonify(success=True, passage=passage_summary(passage)), 201


@bp.patch("/api/passages/<int:passage_id>")
def edit_passage(passage_id):
    data = body()
    profile = get_profile(data.get("profile_id"))
    passage = db.get_or_404(Passage, passage_id)
    if passage.item.profile_id != profile.id:
        return jsonify(error="Passage not found in this profile."), 404
    values = passage_values({**passage_summary(passage), **data})
    active = data.get("active", passage.active)
    if not isinstance(active, bool):
        raise ValueError("Active must be true or false.")
    for key, value in values.items():
        setattr(passage, key, value)
    passage.active = active
    db.session.commit()
    return jsonify(success=True, passage=passage_summary(passage))


def validate_passage_results(data, profile):
    rows = data.get("passage_results", [])
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Passage results must be a list of up to 100 entries.")
    results, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each passage result must be an object.")
        passage_id = integer(row.get("passage_id"), "Passage ID", 1, 2147483647)
        if passage_id in seen:
            raise ValueError("Record each passage once per session.")
        seen.add(passage_id)
        passage = db.session.get(Passage, passage_id)
        if not passage or passage.item.profile_id != profile.id:
            raise ValueError("A passage does not belong to this profile.")
        unit = choice(
            row.get("tempo_unit", passage.tempo_unit), TEMPO_UNITS, "tempo unit"
        )
        if unit != passage.tempo_unit:
            raise ValueError(
                "This passage's tempo unit changed. Refresh the page before saving a result."
            )
        results.append(
            (
                passage,
                dict(
                    tempo=integer(row.get("tempo"), "Achieved tempo", 30, 240),
                    clean_reps=integer(
                        row.get("clean_reps"), "Clean repetitions", 0, 100
                    ),
                    notes=text_value(
                        row.get("notes", ""), "Passage note", 1000, required=False
                    ),
                    tempo_unit=unit,
                    target_tempo=passage.target_tempo,
                    target_reps=passage.target_reps,
                ),
            )
        )
    return results


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
    passages = {item.id: chosen_passage(item) for item in items}
    ranked = sorted(
        items,
        key=lambda item: (
            -(
                item_score(item, mode)
                + (
                    0.3
                    if passages[item.id] and not passages[item.id]["goal_reached"]
                    else 0
                )
            ),
            item.id,
        ),
    )
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
        passage = passages[item.id]
        if passage:
            last = passage["last_result"]
            previous = (
                f"Last: {last['tempo']} BPM, {last['clean_reps']} clean repetitions. "
                if last
                else ""
            )
            action = dict(
                focus=passage["label"],
                instruction=previous + passage["next_step"],
                success=f"{passage['target_reps']} clean repetitions at {passage['suggested_tempo']} BPM ({passage['tempo_unit']} note)",
            )
        plan.append(
            dict(
                title=item.title,
                duration=duration,
                type=item.category,
                item_id=item.id,
                passage=passage,
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


@bp.get("/api/coach/status")
def coach_status():
    return jsonify(configured=bool(coach.api_key()))


@bp.post("/api/coach")
def coach_plan():
    data = body()
    profile = get_profile(data.get("profile_id"))
    minutes = integer(data.get("minutes"), "Available time", 5, 90)
    energy = choice(data.get("energy"), {"low", "normal", "fresh"}, "energy level")
    workload = text_value(
        data.get("workload", ""), "Other commitments", 500, required=False
    )
    target_date = data.get("target_date") or None
    if target_date:
        if not isinstance(target_date, str):
            raise ValueError("Choose a valid audition date.")
        try:
            target_date = date.fromisoformat(target_date).isoformat()
        except ValueError:
            raise ValueError("Choose a valid audition date.")
    if data.get("consent") is not True:
        raise ValueError("Agree to send the practice context to the AI service first.")
    key = coach.api_key()
    if not key:
        return jsonify(
            error="AI isn't connected yet. The site owner needs to enable it. No AI request was sent."
        ), 503
    items = PracticeItem.query.filter_by(profile_id=profile.id, active=True).all()
    selected = data.get("focus_item_id")
    if selected is not None:
        selected = integer(selected, "Priority piece", 1, 2147483647)
        if selected not in {i.id for i in items}:
            raise ValueError("Choose an active piece from this profile.")
    rows = (
        Passage.query.join(PracticeItem)
        .filter(
            PracticeItem.profile_id == profile.id,
            PracticeItem.active.is_(True),
            Passage.active.is_(True),
        )
        .all()
    )
    rows.sort(
        key=lambda p: (
            p.item_id != selected if selected else False,
            p.item.deadline or "9999",
            p.id,
        )
    )
    passages = []
    for p in rows[:12]:
        s = passage_summary(p)
        passages.append(
            {
                k: s[k]
                for k in (
                    "id",
                    "item_id",
                    "item_title",
                    "label",
                    "target_tempo",
                    "target_reps",
                    "tempo_unit",
                    "suggested_tempo",
                    "best_clean_tempo",
                    "last_result",
                )
            }
        )
        if passages[-1]["last_result"]:
            passages[-1]["last_result"] = {
                **passages[-1]["last_result"],
                "notes": passages[-1]["last_result"].get("notes", "")[:160],
            }
        passages[-1].update(
            deadline=p.item.deadline,
            confidence=p.item.confidence,
            priority=p.item.priority,
        )
    if not passages:
        raise ValueError(
            "Add a piece and at least one passage goal in Repertoire first."
        )
    today = date.today().isoformat()
    if not db.session.get(CoachBudget, today):
        db.session.add(CoachBudget(day=today))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    now = time.time()
    reserved = CoachBudget.query.filter(
        CoachBudget.day == today,
        CoachBudget.used < 30,
        CoachBudget.last_request <= now - 10,
    ).update(
        {CoachBudget.used: CoachBudget.used + 1, CoachBudget.last_request: now},
        synchronize_session=False,
    )
    db.session.commit()
    if not reserved:
        return jsonify(
            error="The coach has a 10-second cooldown and a shared limit of 30 requests per day. Try later; the practice room still works."
        ), 429
    context = dict(
        today=today,
        instrument=profile.instrument,
        minutes=minutes,
        energy=energy,
        other_commitments=workload,
        audition_date=target_date,
        priority_item_id=selected,
        passages=passages,
    )
    try:
        plan = coach.validate_plan(coach.ask(context, key), passages, minutes)
    except coach.CoachUnavailable as error:
        return jsonify(error=str(error)), 503
    return jsonify(plan)


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
    passage_results = validate_passage_results(data, profile)
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
    for passage, values in passage_results:
        db.session.add(
            PassageResult(passage_id=passage.id, session_id=practice.id, **values)
        )
        passage.item.last_practiced = session_date
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
