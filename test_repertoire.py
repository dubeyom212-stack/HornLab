"""Regression checks for the repertoire-entry feedback from the first five testers."""

import unittest

import test_app as baseline
from app import Passage, PracticeItem


class RepertoireTests(unittest.TestCase):
    setUp = baseline.HornLabTests.setUp
    tearDown = baseline.HornLabTests.tearDown
    item = baseline.HornLabTests.item

    def bulk(self, titles, **values):
        return self.client.post('/api/items/bulk', json={
            'profile_id': self.profile, 'titles': titles, **values})

    def practice(self, item, **values):
        return self.client.post(f'/api/items/{item}/practice', json={
            'profile_id': self.profile, **values})

    def test_title_alone_is_enough_and_details_can_be_added_later(self):
        item = self.item(title='Strauss No. 1')
        stored = self.client.get(f'/api/items?profile={self.profile}').json[0]
        self.assertEqual(stored['title'], 'Strauss No. 1')
        self.assertEqual(stored['priority'], 'medium')
        self.assertIsNone(stored['deadline'])
        self.assertEqual(self.client.patch(f'/api/items/{item}', json={
            'profile_id': self.profile, 'priority': 'high',
            'deadline': '2027-01-01'}).status_code, 200)

    def test_bulk_trims_and_skips_repeats_including_archived_items(self):
        old = self.item(title='Mozart K.447')
        self.client.delete(f'/api/items/{old}', json={'profile_id': self.profile})
        result = self.bulk([' mozart k.447 ', 'Kopprasch 1', 'KOPPRASCH 1', 'Strauss'])
        self.assertEqual(result.status_code, 201)
        self.assertEqual([item['title'] for item in result.json['items']], ['Kopprasch 1', 'Strauss'])
        self.assertEqual(len(result.json['skipped']), 2)
        retry = self.bulk(['Kopprasch 1', 'Strauss'])
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json['items'], [])
        self.assertEqual(PracticeItem.query.count(), 3)

    def test_bulk_invalid_input_saves_nothing(self):
        for titles in (None, 'Mozart', [], ['Mozart', ' '], ['Mozart', 42],
                       ['Mozart', 'x' * 201], ['Piece'] * 51):
            with self.subTest(titles=titles):
                result = self.bulk(titles)
                self.assertEqual(result.status_code, 400)
                self.assertEqual(PracticeItem.query.count(), 0)
        self.assertEqual(self.bulk([f'Piece {i}' for i in range(50)]).status_code, 201)
        self.assertEqual(PracticeItem.query.count(), 50)

    def test_bulk_does_not_skip_another_profiles_repertoire(self):
        self.item(title='Shared title')
        other = self.client.post('/api/profiles', json={'name': 'Other'}).json['profile']['id']
        result = self.bulk(['Shared title'], profile_id=other)
        self.assertEqual(len(result.json['items']), 1)
        self.assertEqual(PracticeItem.query.count(), 2)

    def test_practice_creates_one_whole_piece_goal_and_retry_reuses_it(self):
        item = self.item()
        first = self.practice(item)
        self.assertEqual(first.status_code, 200)
        passage = first.json['passage']
        self.assertEqual(passage['label'], 'Whole piece')
        self.assertEqual(passage['suggested_tempo'], 60)
        self.assertIsNone(passage['last_result'])
        self.assertEqual(self.practice(item).json['passage']['id'], passage['id'])
        self.assertEqual(Passage.query.count(), 1)

    def test_practice_uses_existing_passage_without_overwriting_its_settings(self):
        item = self.item()
        passage = self.client.post('/api/passages', json={
            'profile_id': self.profile, 'item_id': item, 'label': 'Measures 24-32',
            'start_tempo': 84, 'target_tempo': 120, 'tempo_unit': 'eighth',
            'target_reps': 4}).json['passage']
        result = self.practice(item).json['passage']
        self.assertEqual(result['id'], passage['id'])
        self.assertEqual(result['suggested_tempo'], 84)
        self.assertEqual(result['tempo_unit'], 'eighth')
        self.assertEqual(Passage.query.count(), 1)

    def test_new_endpoints_require_ownership_csrf_and_active_piece(self):
        item = self.item()
        other = baseline.registered_client(self.app, 'other-musician')
        profile = other.post('/api/profiles', json={'name': 'Other'}).json['profile']['id']
        for path, payload in (
            ('/api/items/bulk', {'profile_id': self.profile, 'titles': ['Foreign']}),
            (f'/api/items/{item}/practice', {'profile_id': self.profile}),
            (f'/api/items/{item}/practice', {'profile_id': profile}),
        ):
            self.assertEqual(other.post(path, json=payload).status_code, 404)
        for path in ('/api/items/bulk', f'/api/items/{item}/practice'):
            self.assertEqual(self.app.test_client().post(path, json={}).status_code, 401)
            self.assertEqual(self.client.post(path, json={'profile_id': self.profile},
                headers={'X-CSRF-Token': 'wrong'}).status_code, 403)
        self.client.delete(f'/api/items/{item}', json={'profile_id': self.profile})
        self.assertEqual(self.practice(item).status_code, 404)
        self.assertEqual(Passage.query.count(), 0)
        self.assertEqual(PracticeItem.query.count(), 1)


if __name__ == '__main__':
    unittest.main()
