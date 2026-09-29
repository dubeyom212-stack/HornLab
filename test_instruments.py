import unittest

from instruments import INSTRUMENTS, instrument_guidance
from app import Profile, build_plan, db
import test_app


class InstrumentTests(unittest.TestCase):
    setUp = test_app.HornLabTests.setUp
    tearDown = test_app.HornLabTests.tearDown
    item = test_app.HornLabTests.item

    def test_aliases_and_unknown_names(self):
        self.assertEqual(instrument_guidance("  TENOR   SAX ")["name"], "Tenor saxophone")
        self.assertEqual(instrument_guidance("bass")["family"], "other")
        self.assertEqual(instrument_guidance("Custom instrument")["family"], "other")
        for name, family, _, _ in INSTRUMENTS:
            self.assertEqual(instrument_guidance(name)["family"], family)

    def test_existing_profile_can_change_instrument_and_routine(self):
        self.item()
        response = self.client.patch(f"/api/profiles/{self.profile}/instrument", json={"instrument": "tenor sax"})
        self.assertEqual(response.status_code, 200)
        profile = db.session.get(Profile, self.profile)
        warmup = build_plan(profile, 15)[0]["instruction"]
        self.assertIn("fingering", warmup)
        self.assertNotIn("lip slurs", warmup)
        row = next(p for p in self.client.get('/api/profiles').json if p['id'] == self.profile)
        self.assertEqual(row['guidance']['family'], 'woodwind')
        self.assertEqual(self.client.patch(f"/api/profiles/{self.profile}/instrument", json={"instrument":""}).status_code, 400)

    def test_non_wind_guidance_has_no_wind_warmup(self):
        for name in ("Piano", "Violin", "Percussion", "Guitar", "Unknown"):
            advice = instrument_guidance(name)
            self.assertNotIn("lip slur", advice['warmup'])
            self.assertNotIn("breathe", advice['entrance'])
        markup = self.client.get('/').text
        self.assertIn('Tenor saxophone', markup)
        self.assertIn('Other instrument', markup)

    def test_new_profile_returns_guidance(self):
        response = self.client.post('/api/profiles', json={'name':'Sax player','instrument':'Tenor saxophone'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['profile']['guidance']['family'], 'woodwind')
