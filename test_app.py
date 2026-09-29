import os
import unittest
from datetime import date, timedelta
from uuid import uuid4

os.environ["HORNLAB_DATABASE_URI"] = "sqlite:///:memory:"
from app import (
    create_app,
    db,
    Profile,
    PracticeItem,
    PracticeSession,
    PracticeGoal,
    SessionReceipt,
    build_plan,
)


class HornLabTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
        )
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()
        self.profile = self.client.post(
            "/api/profiles", json={"name": "Musician"}
        ).json["profile"]["id"]

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def item(self, **values):
        result = self.client.post(
            "/api/items",
            json={"profile_id": self.profile, "title": "Mozart K.447", **values},
        )
        self.assertEqual(result.status_code, 201)
        return result.json["item"]["id"]

    def session(self, **values):
        return self.client.post(
            "/api/session",
            json={
                "profile_id": self.profile,
                "token": str(uuid4()),
                "duration": 30,
                "focus": "Repertoire",
                **values,
            },
        )

    def test_pages_and_assets(self):
        for path in [
            "/",
            "/setup",
            "/about",
            "/static/workspace.css",
            "/static/workspace.js",
        ]:
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200, path)
        self.assertIn(b"workspace.js", self.client.get("/").data)

    def test_plan_conserves_every_allowed_duration(self):
        for number in range(1, 6):
            self.item(title=f"Piece {number}")
            for minutes in range(5, 181):
                for mode in ["balanced", "deadline", "weakest"]:
                    plan = build_plan(
                        db.session.get(Profile, self.profile), minutes, mode
                    )
                    self.assertEqual(sum(step["duration"] for step in plan), minutes)
                    self.assertTrue(all(step["duration"] > 0 for step in plan))
                    self.assertEqual(plan[0]["type"], "warmup")

    def test_priority_and_archived_items(self):
        self.item(title="Comfortable", confidence="solid", priority="low")
        urgent = self.item(
            title="Audition",
            category="audition",
            confidence="needs-work",
            priority="high",
            deadline=date.today().isoformat(),
        )
        response = self.client.post(
            "/api/plan",
            json={"profile_id": self.profile, "minutes": 10, "mode": "deadline"},
        )
        self.assertEqual(response.json["plan"][1]["item_id"], urgent)
        self.client.patch(
            f"/api/items/{urgent}", json={"profile_id": self.profile, "active": False}
        )
        response = self.client.post(
            "/api/plan", json={"profile_id": self.profile, "minutes": 10}
        )
        self.assertNotEqual(response.json["plan"][1]["item_id"], urgent)

    def test_edit_archive_restore_and_profile_scope(self):
        item = self.item()
        other = self.client.post("/api/profiles", json={"name": "Other"}).json[
            "profile"
        ]["id"]
        self.assertEqual(
            self.client.patch(
                f"/api/items/{item}", json={"profile_id": other, "title": "Wrong"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/items/{item}", json={"profile_id": other}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(f"/api/items?profile={other}").json, [])
        edited = self.client.patch(
            f"/api/items/{item}",
            json={
                "profile_id": self.profile,
                "title": "New title",
                "confidence": "solid",
            },
        )
        self.assertEqual(edited.json["item"]["title"], "New title")
        self.client.delete(f"/api/items/{item}", json={"profile_id": self.profile})
        self.assertFalse(db.session.get(PracticeItem, item).active)
        self.client.patch(
            f"/api/items/{item}", json={"profile_id": self.profile, "active": True}
        )
        self.assertTrue(db.session.get(PracticeItem, item).active)

    def test_session_retry_is_idempotent(self):
        item = self.item()
        token = str(uuid4())
        first = self.session(token=token, completed_item_ids=[item, item])
        second = self.session(token=token, completed_item_ids=[item])
        self.assertEqual(first.status_code, 201)
        self.assertTrue(second.json["already_saved"])
        self.assertEqual(PracticeSession.query.count(), 1)
        self.assertEqual(SessionReceipt.query.count(), 1)
        self.assertEqual(
            db.session.get(PracticeItem, item).last_practiced, date.today().isoformat()
        )

    def test_session_rejects_other_profiles_items_atomically(self):
        item = self.item()
        other = self.client.post("/api/profiles", json={"name": "Other"}).json[
            "profile"
        ]["id"]
        self.assertEqual(
            self.session(profile_id=other, completed_item_ids=[item]).status_code, 400
        )
        self.assertEqual(PracticeSession.query.count(), 0)
        self.assertIsNone(db.session.get(PracticeItem, item).last_practiced)

    def test_validation_errors_do_not_write(self):
        for data in [
            [],
            None,
            {"name": None},
            {"name": 42},
            {"name": "x", "typical_time": True},
        ]:
            self.assertEqual(
                self.client.post("/api/profiles", json=data).status_code, 400
            )
        for values in [
            {"title": None},
            {"category": "bad"},
            {"priority": []},
            {"deadline": "2026-02-30"},
            {"confidence": "bad"},
        ]:
            self.assertEqual(
                self.client.post(
                    "/api/items",
                    json={"profile_id": self.profile, "title": "x", **values},
                ).status_code,
                400,
            )
        for duration in [0, -1, True, 2.5, 721]:
            self.assertEqual(self.session(duration=duration).status_code, 400)
        for minutes in [0, 181, 1.5, True]:
            self.assertEqual(
                self.client.post(
                    "/api/plan", json={"profile_id": self.profile, "minutes": minutes}
                ).status_code,
                400,
            )
        self.assertEqual(PracticeSession.query.count(), 0)
        self.assertEqual(PracticeItem.query.count(), 0)

    def test_calendar_totals_streak_and_goal(self):
        today = date.today()
        for days, minutes in [(0, 20), (0, 15), (1, 30), (2, 10), (8, 70)]:
            db.session.add(
                PracticeSession(
                    profile_id=self.profile,
                    date=(today - timedelta(days=days)).isoformat(),
                    duration=minutes,
                    focus="Practice",
                )
            )
        db.session.commit()
        result = self.client.get(f"/api/insights?profile={self.profile}").json
        self.assertEqual(result["total_minutes"], 145)
        self.assertEqual(result["recent_minutes"], 75)
        self.assertEqual(result["streak"], 3)
        self.assertEqual(result["series"][-1]["minutes"], 35)
        monday = today - timedelta(days=today.weekday())
        expected = sum(
            s.duration
            for s in PracticeSession.query.all()
            if monday.isoformat() <= s.date <= today.isoformat()
        )
        self.assertEqual(result["week_minutes"], expected)
        self.client.patch(
            "/api/goal", json={"profile_id": self.profile, "weekly_minutes": 210}
        )
        self.assertEqual(
            self.client.get(f"/api/insights?profile={self.profile}").json[
                "weekly_goal"
            ],
            210,
        )

    def test_csv_preserves_notes_and_neutralizes_formulas(self):
        self.session(focus="=1+1", notes="A phrase, then\na new line")
        result = self.client.get(f"/api/export?profile={self.profile}")
        self.assertIn("'=1+1", result.text)
        self.assertIn('"A phrase, then\na new line"', result.text)
        self.assertIn("attachment", result.headers["Content-Disposition"])

    def test_existing_schema_works_with_new_tables(self):
        # Simulate a database created by the old version, with no new tables.
        SessionReceipt.__table__.drop(db.engine)
        PracticeGoal.__table__.drop(db.engine)
        self.item()
        db.create_all()
        self.assertEqual(
            len(self.client.get(f"/api/items?profile={self.profile}").json), 1
        )
        self.assertEqual(self.session().status_code, 201)


if __name__ == "__main__":
    unittest.main()
