from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///hornlab.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ========================================
# DATABASE
# ========================================

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instrument = db.Column(
        db.String(100),
        nullable=False,
        default="French horn"
    )
    typical_time = db.Column(
        db.Integer,
        nullable=False,
        default=30
    )

    items = db.relationship(
        "PracticeItem",
        backref="profile",
        lazy=True,
        cascade="all, delete-orphan"
    )

    sessions = db.relationship(
        "PracticeSession",
        backref="profile",
        lazy=True,
        cascade="all, delete-orphan"
    )


class PracticeItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    profile_id = db.Column(
        db.Integer,
        db.ForeignKey("profile.id"),
        nullable=False
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    category = db.Column(
        db.String(50),
        nullable=False,
        default="repertoire"
    )

    deadline = db.Column(
        db.String(20)
    )

    priority = db.Column(
        db.String(20),
        nullable=False,
        default="medium"
    )

    confidence = db.Column(
        db.String(20),
        nullable=False,
        default="developing"
    )

    last_practiced = db.Column(
        db.String(20)
    )

    active = db.Column(
        db.Boolean,
        default=True
    )


class PracticeSession(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    profile_id = db.Column(
        db.Integer,
        db.ForeignKey("profile.id"),
        nullable=False
    )

    date = db.Column(
        db.String(20),
        nullable=False
    )

    duration = db.Column(
        db.Integer,
        nullable=False
    )

    focus = db.Column(
        db.String(200),
        nullable=False
    )

    notes = db.Column(
        db.Text
    )


with app.app_context():
    db.create_all()


# ========================================
# HELPERS
# ========================================

def get_profile(profile_id):
    if not profile_id:
        return None

    try:
        return db.session.get(
            Profile,
            int(profile_id)
        )
    except (ValueError, TypeError):
        return None


def days_until(deadline):
    if not deadline:
        return None

    try:
        return (
            date.fromisoformat(deadline)
            - date.today()
        ).days
    except ValueError:
        return None


# ========================================
# PRIORITY
# ========================================

def item_score(item, mode="balanced"):
    today = date.today()

    confidence_score = {
        "needs-work": 1.00,
        "developing": 0.65,
        "solid": 0.25
    }.get(item.confidence, 0.50)

    priority_score = {
        "high": 1.00,
        "medium": 0.60,
        "low": 0.25
    }.get(item.priority, 0.50)

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
            days_since = max(
                0,
                (today - last).days
            )

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
                "success": "3 clean reps"
            }

        if confidence == "developing":
            return {
                "focus": "Clean up the rough spots",
                "instruction": (
                    "Pick the two spots you keep messing up. "
                    "Work them separately, then put them back together."
                ),
                "success": "2 clean spots"
            }

        return {
            "focus": "See what holds up",
            "instruction": (
                "Run the section without stopping. "
                "Afterward, go back to the one thing that stood out."
            ),
            "success": "1 solid run"
        }

    if category == "technique":
        return {
            "focus": "Clean up the basics",
            "instruction": (
                "Pick one thing to focus on. Start slow and "
                "only speed up when it stays clean."
            ),
            "success": "2 clean reps"
        }

    if category == "assignment":
        return {
            "focus": "Get the unfinished part done",
            "instruction": (
                "Start with the section you know you need to work on. "
                "Finish with one full attempt."
            ),
            "success": "One full attempt"
        }

    return {
        "focus": "Keep the fundamentals moving",
        "instruction": (
            "Play enough to get the sound and air feeling right. "
            "You don't need to turn this into a 20-minute warmup."
        ),
        "success": "Feels ready"
    }


# ========================================
# PLAN
# ========================================

def build_plan(profile, minutes, mode="balanced"):
    items = PracticeItem.query.filter_by(
        profile_id=profile.id,
        active=True
    ).all()

    if not items:
        return []

    ranked = sorted(
        items,
        key=lambda item: item_score(item, mode),
        reverse=True
    )

    if minutes <= 10:
        warmup = 2
        max_items = 1
    elif minutes <= 20:
        warmup = 3
        max_items = 2
    elif minutes <= 30:
        warmup = 4
        max_items = 2
    elif minutes <= 45:
        warmup = 6
        max_items = 3
    else:
        warmup = 8
        max_items = 4

    available = minutes - warmup

    plan = [
        {
            "title": "Warm up",
            "duration": warmup,
            "focus": "Get the horn going",
            "instruction": (
                "A few long tones and some flexibility. "
                "Get comfortable and move on."
            ),
            "success": "Feels ready",
            "type": "warmup",
            "priority": False
        }
    ]

    selected = ranked[:max_items]

    if not selected:
        return plan

    weights = []

    for index, item in enumerate(selected):
        weights.append(
            1.5 if index == 0 else 1.0
        )

    total_weight = sum(weights)

    durations = [
        max(
            3,
            round(
                available * weight / total_weight
            )
        )
        for weight in weights
    ]

    difference = available - sum(durations)

    if difference > 0:
        durations[0] += difference

    if len(durations) > 1 and durations[0] > 25:
        overflow = durations[0] - 25
        durations[0] = 25
        durations[-1] += overflow

    for item, duration in zip(
        selected,
        durations
    ):
        action = action_for(item)

        plan.append({
            "title": item.title,
            "duration": duration,
            "focus": action["focus"],
            "instruction": action["instruction"],
            "success": action["success"],
            "type": item.category,
            "priority": item.priority == "high",
            "item_id": item.id
        })

    return plan


# ========================================
# PAGES
# ========================================

@app.route("/")
def index():
    profiles = Profile.query.order_by(
        Profile.name
    ).all()

    profile_id = request.args.get(
        "profile"
    )

    profile = get_profile(
        profile_id
    )

    if not profile and profiles:
        profile = profiles[0]

    if not profile:
        return redirect(
            url_for("setup")
        )

    items = PracticeItem.query.filter_by(
        profile_id=profile.id,
        active=True
    ).all()

    item_data = []

    for item in items:
        item_data.append({
            "id": item.id,
            "title": item.title,
            "category": item.category,
            "deadline": item.deadline,
            "days_left": days_until(item.deadline),
            "priority": item.priority,
            "confidence": item.confidence,
            "last_practiced": item.last_practiced
        })

    today_display = date.today().strftime(
        "%A, %B %d"
    ).replace(
        " 0",
        " "
    )

    return render_template(
        "index.html",
        profile=profile,
        profiles=profiles,
        items=item_data,
        today=today_display
    )


@app.route("/setup")
def setup():
    return render_template(
        "setup.html"
    )


@app.route("/about")
def about():
    profiles = Profile.query.order_by(
        Profile.name
    ).all()

    return render_template(
        "about.html",
        profiles=profiles
    )


# ========================================
# CREATE PROFILE
# ========================================

@app.route(
    "/api/profiles",
    methods=["POST"]
)
def create_profile():
    data = request.get_json() or {}

    name = data.get(
        "name",
        ""
    ).strip()

    if not name:
        return jsonify({
            "error": "Name is required."
        }), 400

    instrument = data.get(
        "instrument",
        "French horn"
    ).strip()

    try:
        typical_time = int(
            data.get(
                "typical_time",
                30
            )
        )
    except (ValueError, TypeError):
        typical_time = 30

    profile = Profile(
        name=name,
        instrument=instrument or "French horn",
        typical_time=max(
            5,
            min(typical_time, 180)
        )
    )

    db.session.add(profile)
    db.session.commit()

    return jsonify({
        "success": True,
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "instrument": profile.instrument,
            "typical_time": profile.typical_time
        }
    })


# ========================================
# PLAN API
# ========================================

@app.route(
    "/api/plan",
    methods=["POST"]
)
def generate_plan():
    data = request.get_json() or {}

    profile = get_profile(
        data.get("profile_id")
    )

    if not profile:
        return jsonify({
            "error": "Profile not found."
        }), 404

    try:
        minutes = int(
            data.get(
                "minutes",
                profile.typical_time
            )
        )
    except (ValueError, TypeError):
        minutes = profile.typical_time

    mode = data.get(
        "mode",
        "balanced"
    )

    minutes = max(
        5,
        min(minutes, 180)
    )

    plan = build_plan(
        profile,
        minutes,
        mode
    )

    return jsonify({
        "minutes": minutes,
        "mode": mode,
        "plan": plan
    })


# ========================================
# ADD ITEM
# ========================================

@app.route(
    "/api/items",
    methods=["POST"]
)
def add_item():
    data = request.get_json() or {}

    profile = get_profile(
        data.get("profile_id")
    )

    if not profile:
        return jsonify({
            "error": "Profile not found."
        }), 404

    title = data.get(
        "title",
        ""
    ).strip()

    if not title:
        return jsonify({
            "error": "Give it a name first."
        }), 400

    item = PracticeItem(
        profile_id=profile.id,
        title=title,
        category=data.get(
            "category",
            "repertoire"
        ),
        deadline=data.get(
            "deadline"
        ) or None,
        priority=data.get(
            "priority",
            "medium"
        ),
        confidence=data.get(
            "confidence",
            "developing"
        )
    )

    db.session.add(item)
    db.session.commit()

    return jsonify({
        "success": True,
        "item": {
            "id": item.id,
            "title": item.title,
            "category": item.category,
            "deadline": item.deadline,
            "priority": item.priority,
            "confidence": item.confidence
        }
    })


# ========================================
# DELETE ITEM
# ========================================

@app.route(
    "/api/items/<int:item_id>",
    methods=["DELETE"]
)
def delete_item(item_id):
    item = db.session.get(
        PracticeItem,
        item_id
    )

    if not item:
        return jsonify({
            "error": "Couldn't find that."
        }), 404

    item.active = False
    db.session.commit()

    return jsonify({
        "success": True
    })


# ========================================
# SAVE SESSION
# ========================================

@app.route(
    "/api/session",
    methods=["POST"]
)
def save_session():
    data = request.get_json() or {}

    profile = get_profile(
        data.get("profile_id")
    )

    if not profile:
        return jsonify({
            "error": "Profile not found."
        }), 404

    try:
        duration = int(
            data.get(
                "duration",
                0
            )
        )
    except (ValueError, TypeError):
        duration = 0

    session = PracticeSession(
        profile_id=profile.id,
        date=date.today().isoformat(),
        duration=max(0, duration),
        focus=data.get(
            "focus",
            "Practice"
        ),
        notes=data.get(
            "notes",
            ""
        )
    )

    db.session.add(session)

    completed_ids = data.get(
        "completed_item_ids",
        []
    )

    for item_id in completed_ids:
        try:
            item = db.session.get(
                PracticeItem,
                int(item_id)
            )
        except (ValueError, TypeError):
            item = None

        if item and item.profile_id == profile.id:
            item.last_practiced = (
                date.today().isoformat()
            )

    db.session.commit()

    return jsonify({
        "success": True
    })


# ========================================
# INSIGHTS
# ========================================

@app.route(
    "/api/insights"
)
def insights():
    profile = get_profile(
        request.args.get("profile")
    )

    if not profile:
        return jsonify({
            "total_minutes": 0,
            "session_count": 0,
            "recent_minutes": 0
        })

    sessions = PracticeSession.query.filter_by(
        profile_id=profile.id
    ).order_by(
        PracticeSession.id.desc()
    ).all()

    total_minutes = sum(
        session.duration
        for session in sessions
    )

    recent = sessions[:7]

    recent_minutes = sum(
        session.duration
        for session in recent
    )

    return jsonify({
        "total_minutes": total_minutes,
        "session_count": len(sessions),
        "recent_minutes": recent_minutes
    })


# ========================================
# RUN
# ========================================

if __name__ == "__main__":
    app.run(debug=True)