import io
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

import coach
import test_tracking


class CoachTransportTests(unittest.TestCase):
    def test_request_identifies_app_and_reads_plan(self):
        answer = {"summary": "Focus on the entrance."}
        response = io.BytesIO(json.dumps({"choices": [{"message": {
            "content": json.dumps(answer)
        }}]}).encode())
        with patch("coach.urlopen", return_value=response) as send:
            self.assertEqual(coach.ask({"minutes": 15}, "test-key"), answer)
        request = send.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "HornLab/1.0")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data)["response_format"], {"type": "json_object"})
        self.assertIn("Never assume the player plays horn", json.loads(request.data)["messages"][0]["content"])

    def test_provider_errors_show_status_without_private_response(self):
        for status in (400, 401, 403, 404, 413, 422, 429, 500, 503):
            with self.subTest(status=status):
                error = HTTPError("https://api.groq.com", status, "secret-key", {},
                                  io.BytesIO(b"private practice notes and secret-key"))
                with patch("coach.urlopen", side_effect=error):
                    with self.assertRaises(coach.CoachUnavailable) as raised:
                        coach.ask({}, "secret-key")
                message = str(raised.exception)
                self.assertIn(f"HTTP {status}", message)
                self.assertNotIn("secret-key", message)
                self.assertNotIn("private practice", message)


class CoachTests(unittest.TestCase):
    setUp = test_tracking.TrackingTests.setUp
    tearDown = test_tracking.TrackingTests.tearDown
    item = test_tracking.TrackingTests.item
    passage = test_tracking.TrackingTests.passage

    def brief(self, **values):
        return dict(
            profile_id=self.profile,
            minutes=15,
            energy="low",
            workload="AP Calc in 2 days",
            consent=True,
            **values,
        )

    def answer(self, passage_id):
        return dict(
            summary="Keep this short before studying.",
            skip_today="Full run-throughs can wait.",
            warmup_minutes=2,
            blocks=[
                dict(
                    passage_id=passage_id,
                    weight=3,
                    task="Isolate the entrance, then connect it to the next phrase.",
                    why="This is the closest deadline.",
                    stop_when="Three clean attempts.",
                    start_tempo=60,
                )
            ],
        )

    def test_disconnected_does_not_call_provider(self):
        with patch("coach.api_key", return_value=""), patch("coach.ask") as ask:
            response = self.client.post("/api/coach", json=self.brief())
            self.assertEqual(response.status_code, 503)
            ask.assert_not_called()

    def test_plan_scope_budget_and_data_minimization(self):
        p = self.passage()
        other = self.client.post("/api/profiles", json={"name": "Other player"}).json[
            "profile"
        ]["id"]
        with (
            patch("coach.api_key", return_value="secret"),
            patch("coach.ask", return_value=self.answer(p["id"])) as ask,
        ):
            result = self.client.post("/api/coach", json=self.brief())
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(
            result.json["warmup_minutes"]
            + sum(b["minutes"] for b in result.json["blocks"]),
            15,
        )
        context = ask.call_args.args[0]
        self.assertNotIn("name", context)
        self.assertNotIn("secret", str(result.json))
        self.assertEqual([x["id"] for x in context["passages"]], [p["id"]])
        self.assertEqual(context["other_commitments"], "AP Calc in 2 days")
        self.assertEqual(context["instrument_guidance"]["family"], "brass")
        with patch("coach.api_key", return_value="secret"), patch("coach.ask") as ask:
            retry = self.client.post("/api/coach", json=self.brief())
            self.assertEqual(retry.status_code, 429)
            ask.assert_not_called()

    def test_rejects_unscoped_passage_and_unearned_tempo(self):
        p = self.passage()
        for change in [{"passage_id": 9999}, {"start_tempo": 200}, {"weight": 0}]:
            answer = self.answer(p["id"])
            answer["blocks"][0].update(change)
            with self.assertRaises(coach.CoachUnavailable):
                coach.validate_plan(answer, [p], 15)

    def test_no_consent_and_provider_failure(self):
        self.passage()
        brief = self.brief()
        brief["consent"] = False
        with patch("coach.ask") as ask:
            self.assertEqual(
                self.client.post("/api/coach", json=brief).status_code, 400
            )
            ask.assert_not_called()
        with (
            patch("coach.api_key", return_value="secret"),
            patch("coach.ask", side_effect=coach.CoachUnavailable("Unavailable")),
        ):
            self.assertEqual(
                self.client.post("/api/coach", json=self.brief()).status_code, 503
            )

    def test_time_allocation_for_multiple_blocks(self):
        passages = [self.passage(label=f"Passage {i}") for i in range(3)]
        for minutes in range(5, 91):
            answer = self.answer(passages[0]["id"])
            answer["blocks"] = [
                {**answer["blocks"][0], "passage_id": p["id"], "weight": i + 1}
                for i, p in enumerate(passages)
            ]
            result = coach.validate_plan(answer, passages, minutes)
            self.assertEqual(
                sum(b["minutes"] for b in result["blocks"]) + result["warmup_minutes"],
                minutes,
            )
            self.assertTrue(all(b["minutes"] >= 1 for b in result["blocks"]))
