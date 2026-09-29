import unittest
from uuid import uuid4
import test_app as baseline
from app import (
    db,
    Passage,
    PassageResult,
    PracticeSession,
    PracticeItem,
)


class TrackingTests(unittest.TestCase):
    setUp = baseline.HornLabTests.setUp
    tearDown = baseline.HornLabTests.tearDown
    item = baseline.HornLabTests.item
    session = baseline.HornLabTests.session

    def passage(self, **values):
        item_id = values.pop("item_id", None) or self.item()
        response = self.client.post(
            "/api/passages",
            json={
                "profile_id": self.profile,
                "item_id": item_id,
                "label": "Measures 24–32",
                "start_tempo": 60,
                "target_tempo": 80,
                "target_reps": 3,
                **values,
            },
        )
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["passage"]

    def result(self, passage, **values):
        return self.session(
            passage_results=[
                {"passage_id": passage["id"], "tempo": 72, "clean_reps": 2, **values}
            ]
        )

    def summary(self, passage):
        return next(
            p
            for p in self.client.get(f"/api/passages?profile={self.profile}").json
            if p["id"] == passage["id"]
        )

    def test_feedback_loop_repeat_advance_and_review(self):
        passage = self.passage()
        self.assertEqual(passage["suggested_tempo"], 60)
        self.assertIsNone(passage["last_result"])
        self.assertEqual(
            self.result(passage, notes="Keep the attacks relaxed").status_code, 201
        )
        summary = self.summary(passage)
        self.assertEqual(summary["suggested_tempo"], 72)
        self.assertIn("Stay at", summary["next_step"])
        self.assertEqual(summary["last_result"]["notes"], "Keep the attacks relaxed")
        self.assertIsNone(summary["best_clean_tempo"])
        self.result(passage, clean_reps=3)
        self.assertEqual(self.summary(passage)["suggested_tempo"], 76)
        self.result(passage, tempo=78, clean_reps=3)
        self.assertEqual(self.summary(passage)["suggested_tempo"], 80)
        self.result(passage, tempo=80, clean_reps=3)
        summary = self.summary(passage)
        self.assertTrue(summary["goal_reached"])
        self.assertEqual(summary["best_clean_tempo"], 80)
        self.assertIn("Review", summary["next_step"])
        self.assertEqual(len(summary["history"]), 4)
        self.result(passage, tempo=70, clean_reps=0)
        self.assertFalse(self.summary(passage)["goal_reached"])

    def test_plan_uses_passage_and_preserves_total(self):
        passage = self.passage()
        self.result(passage, notes="Air through the phrase")
        plan = self.client.post(
            "/api/plan", json={"profile_id": self.profile, "minutes": 30}
        ).json["plan"]
        self.assertEqual(sum(p["duration"] for p in plan), 30)
        self.assertEqual(plan[1]["passage"]["id"], passage["id"])
        self.assertIn("72 BPM", plan[1]["instruction"])
        self.assertEqual(
            plan[1]["passage"]["last_result"]["notes"], "Air through the phrase"
        )

    def test_unfinished_passage_is_chosen_before_completed_goal(self):
        first = self.passage()
        self.result(first, tempo=80, clean_reps=3)
        second = self.passage(item_id=first["item_id"], label="Measures 40–48")
        plan = self.client.post(
            "/api/plan", json={"profile_id": self.profile, "minutes": 10}
        ).json["plan"]
        self.assertEqual(plan[1]["passage"]["id"], second["id"])

    def test_edit_unit_keeps_history_but_resets_comparison(self):
        passage = self.passage()
        self.result(passage, tempo=80, clean_reps=3)
        self.client.patch(
            f"/api/passages/{passage['id']}",
            json={
                "profile_id": self.profile,
                "tempo_unit": "dotted-quarter",
                "target_tempo": 100,
            },
        )
        summary = self.summary(passage)
        self.assertIsNone(summary["last_result"])
        self.assertFalse(summary["goal_reached"])
        self.assertEqual(summary["suggested_tempo"], 60)
        self.assertEqual(summary["history"][0]["tempo_unit"], "quarter")
        self.assertEqual(summary["history"][0]["target_tempo"], 80)
        self.assertEqual(self.result(passage, tempo_unit="quarter").status_code, 400)

    def test_archive_restore_and_item_archiving(self):
        passage = self.passage()
        self.result(passage)
        self.client.patch(
            f"/api/passages/{passage['id']}",
            json={"profile_id": self.profile, "active": False},
        )
        plan = self.client.post(
            "/api/plan", json={"profile_id": self.profile, "minutes": 10}
        ).json["plan"]
        self.assertIsNone(plan[1]["passage"])
        self.client.patch(
            f"/api/passages/{passage['id']}",
            json={"profile_id": self.profile, "active": True},
        )
        self.assertEqual(self.summary(passage)["result_count"], 1)
        self.client.patch(
            f"/api/items/{passage['item_id']}",
            json={"profile_id": self.profile, "active": False},
        )
        self.assertEqual(
            self.client.post(
                "/api/plan", json={"profile_id": self.profile, "minutes": 10}
            ).json["plan"],
            [],
        )

    def test_retries_do_not_duplicate_passage_results(self):
        passage = self.passage()
        token = str(uuid4())
        data = {
            "token": token,
            "passage_results": [
                {"passage_id": passage["id"], "tempo": 72, "clean_reps": 3}
            ],
        }
        self.assertEqual(self.session(**data).status_code, 201)
        self.assertTrue(self.session(**data).json["already_saved"])
        self.assertEqual(PassageResult.query.count(), 1)
        self.assertEqual(PracticeSession.query.count(), 1)
        self.assertIsNotNone(
            db.session.get(PracticeItem, passage["item_id"]).last_practiced
        )

    def test_foreign_profile_and_invalid_results_are_atomic(self):
        passage = self.passage()
        other = self.client.post("/api/profiles", json={"name": "Other"}).json[
            "profile"
        ]["id"]
        self.assertEqual(self.client.get(f"/api/passages?profile={other}").json, [])
        self.assertEqual(
            self.client.patch(
                f"/api/passages/{passage['id']}",
                json={"profile_id": other, "label": "Wrong"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.session(
                profile_id=other,
                passage_results=[
                    {"passage_id": passage["id"], "tempo": 72, "clean_reps": 3}
                ],
            ).status_code,
            400,
        )
        for changes in [
            {"tempo": False},
            {"tempo": 241},
            {"clean_reps": -1},
            {"clean_reps": 2.5},
            {"notes": None},
        ]:
            self.assertEqual(self.result(passage, **changes).status_code, 400)
        entry = {"passage_id": passage["id"], "tempo": 72, "clean_reps": 3}
        self.assertEqual(self.session(passage_results=[entry, entry]).status_code, 400)
        self.assertEqual(PracticeSession.query.count(), 0)
        self.assertEqual(PassageResult.query.count(), 0)

    def test_new_tables_are_additive(self):
        PassageResult.__table__.drop(db.engine)
        Passage.__table__.drop(db.engine)
        original = self.item()
        self.session()
        db.create_all()
        passage = self.passage(item_id=original)
        self.assertEqual(self.result(passage).status_code, 201)
        self.assertEqual(PracticeSession.query.count(), 2)

    def test_goal_validation_and_snapshot_history(self):
        item = self.item()
        for values in [
            {"start_tempo": 100, "target_tempo": 60},
            {"target_reps": 0},
            {"tempo_unit": "wrong"},
            {"label": None},
        ]:
            response = self.client.post(
                "/api/passages",
                json={
                    "profile_id": self.profile,
                    "item_id": item,
                    "label": "Measures 1–8",
                    **values,
                },
            )
            self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(Passage.query.count(), 0)
        passage = self.passage(item_id=item)
        self.result(passage, tempo=80, clean_reps=3)
        self.client.patch(
            f"/api/passages/{passage['id']}",
            json={"profile_id": self.profile, "target_reps": 5},
        )
        summary = self.summary(passage)
        self.assertFalse(summary["goal_reached"])
        self.assertEqual(summary["history"][0]["target_reps"], 3)


if __name__ == "__main__":
    unittest.main()
