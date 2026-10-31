"""Synthetic room/customer/actual-shift attribution boundary tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pipeline.attribute_comment_leads import attribute_document


def comment(record_id='c1', customer='customer-1', at=10, room='room-1', eligible=True):
    return dict(id=record_id, room_id=room, customer_id=customer, timestamp=at, eligible=eligible)


def lead(record_id='l1', customer='customer-1', at=20, room='room-1'):
    return dict(id=record_id, room_id=room, customer_id=customer, timestamp=at)


def shift(record_id='s1', host='host-a', start=0, end=100, room='room-1'):
    return dict(id=record_id, room_id=room, host_id=host, start=start, end=end, verified=True)


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.doc = {'comments': [comment()], 'leads': [lead()], 'shifts': [shift()],
                    'room_coverage': [{'room_id': 'room-1', 'comments_complete': True, 'leads_complete': True}]}

    def run_attribution(self):
        return attribute_document(self.doc)

    def test_closed_match_and_source_not_mutated(self):
        before = copy.deepcopy(self.doc)
        result = self.run_attribution()
        self.assertEqual(result['matches'][0]['host_id'], 'host-a')
        self.assertEqual(result['matches'][0]['last_comment_ids'], ['c1'])
        self.assertEqual(result['host_totals'][0]['post_comment_leads'], 1)
        self.assertEqual(self.doc, before)

    def test_handover_last_comment_selects_new_host(self):
        self.doc['shifts'] = [shift(end=50), shift('s2', 'host-b', 50, 100)]
        self.doc['comments'].append(comment('c2', at=60))
        self.doc['leads'][0]['timestamp'] = 70
        result = self.run_attribution()
        self.assertEqual(result['matches'][0]['host_id'], 'host-b')
        self.assertEqual({r['host_id']: r['converted'] for r in result['opportunities']},
                         {'host-a': False, 'host-b': True})

    def test_lead_during_next_host_without_new_comment_does_not_transfer(self):
        self.doc['shifts'] = [shift(end=50), shift('s2', 'host-b', 50, 100)]
        self.doc['leads'][0]['timestamp'] = 60
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertEqual(result['excluded'][0]['reason'], 'lead_at_or_after_comment_host_finished')

    def test_exact_handover_belongs_to_new_shift_but_submission_at_old_end_is_excluded(self):
        self.doc['shifts'] = [shift(end=50), shift('s2', 'host-b', 50, 100)]
        self.doc['leads'][0]['timestamp'] = 50
        self.assertFalse(self.run_attribution()['matches'])
        self.doc['comments'].append(comment('c2', at=50))
        self.doc['leads'][0]['timestamp'] = 51
        self.assertEqual(self.run_attribution()['matches'][0]['host_id'], 'host-b')

    def test_repeated_submission_counted_once_even_after_handover(self):
        self.doc['shifts'] = [shift(end=50), shift('s2', 'host-b', 50, 100)]
        self.doc['comments'].append(comment('c2', at=60))
        self.doc['leads'] += [lead('l2', at=30), lead('l3', at=70)]
        result = self.run_attribution()
        self.assertEqual(len(result['matches']), 1)
        self.assertEqual(len(result['duplicates']), 2)
        self.assertEqual(result['matches'][0]['host_id'], 'host-a')

    def test_same_nickname_different_ids_are_not_joined(self):
        self.doc['comments'][0]['nickname'] = 'same-display-name'
        self.doc['leads'][0].update(customer_id='other-id', nickname='same-display-name')
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertEqual(result['excluded'][0]['reason'], 'no_preceding_customer_comment')

    def test_same_customer_different_room_not_joined(self):
        self.doc['leads'][0]['room_id'] = 'room-2'
        self.doc['room_coverage'].append({'room_id': 'room-2', 'comments_complete': True, 'leads_complete': True})
        self.assertFalse(self.run_attribution()['matches'])

    def test_missing_id_is_pending_and_does_not_make_false_negative(self):
        self.doc['leads'][0].pop('customer_id')
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertEqual(result['pending'][0]['reason'], 'missing_room_or_customer_id')
        self.assertIsNone(result['opportunities'][0]['converted'])

    def test_open_shift_or_unverified_owner_is_pending(self):
        for field, value in (('end', None), ('start', None), ('verified', False), ('host_id', None)):
            with self.subTest(field=field):
                doc = copy.deepcopy(self.doc)
                doc['shifts'][0][field] = value
                result = attribute_document(doc)
                self.assertFalse(result['matches'])
                self.assertTrue(result['pending'])

    def test_overlapping_shifts_are_pending(self):
        self.doc['shifts'].append(shift('s2', 'host-b', 0, 100))
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertTrue(any(r['reason'] == 'overlapping_or_ambiguous_shifts' for r in result['pending']))

    def test_equal_second_never_establishes_order(self):
        self.doc['leads'][0]['timestamp'] = 10
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertEqual(result['pending'][0]['reason'], 'equal_timestamp_order_unresolved')
        self.assertIsNone(result['opportunities'][0]['converted'])

    def test_no_fixed_minutes_or_reply_completion_gate(self):
        self.doc['shifts'][0]['end'] = 7200
        self.doc['comments'][0].update(reply_confirmed=False, reply_end=7000)
        self.doc['leads'][0]['timestamp'] = 5000
        self.assertEqual(len(self.run_attribution()['matches']), 1)

    def test_last_ineligible_comment_still_selects_the_actual_host(self):
        self.doc['shifts'] = [shift(end=50), shift('s2', 'host-b', 50, 100)]
        self.doc['comments'].append(comment('c2', at=60, eligible=False))
        self.doc['leads'][0]['timestamp'] = 70
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertEqual(result['excluded'][0]['reason'], 'no_eligible_comment_in_actual_shift')

    def test_future_eligible_comment_cannot_qualify_earlier_submission(self):
        self.doc['comments'][0]['eligible'] = False
        self.doc['comments'].append(comment('c2', at=30))
        self.assertFalse(self.run_attribution()['matches'])

    def test_same_host_reentry_does_not_reuse_previous_shift_comment(self):
        self.doc['shifts'] = [shift(end=30), shift('s2', 'host-b', 30, 60), shift('s3', 'host-a', 60, 100)]
        self.doc['comments'].append(comment('c2', at=70, eligible=False))
        self.doc['leads'][0]['timestamp'] = 80
        self.assertFalse(self.run_attribution()['matches'])

    def test_missing_coverage_retains_pending_and_complete_no_submit_closes_false(self):
        self.doc['room_coverage'] = []
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertIsNone(result['opportunities'][0]['converted'])
        self.doc['room_coverage'] = [{'room_id': 'room-1', 'comments_complete': True, 'leads_complete': True}]
        self.doc['leads'] = []
        self.assertIs(self.run_attribution()['opportunities'][0]['converted'], False)

    def test_gap_between_comment_and_lead_is_pending(self):
        self.doc['shifts'][0]['unrecorded_gaps'] = [{'start': 14, 'end': 16}]
        result = self.run_attribution()
        self.assertFalse(result['matches'])
        self.assertEqual(result['pending'][0]['reason'], 'unrecorded_gap_between_comment_and_lead')
        self.assertIsNone(result['opportunities'][0]['converted'])

    def test_duplicate_input_record_and_conflicting_id(self):
        self.doc['leads'].append(copy.deepcopy(self.doc['leads'][0]))
        result = self.run_attribution()
        self.assertEqual(len(result['matches']), 1)
        self.assertEqual(result['duplicates'][0]['reason'], 'duplicate_input_record')
        self.doc['leads'][1]['timestamp'] = 21
        with self.assertRaises(ValueError):
            self.run_attribution()

    def test_cli_synthetic_fixture(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'result.json'
            result = subprocess.run([sys.executable, '-B', '-m', 'pipeline.attribute_comment_leads',
                '--input', str(root/'tests/fixtures/synthetic-attribution.json'), '--output', str(output)],
                cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = json.loads(output.read_text())
            self.assertEqual(doc['summary']['matched_room_customers'], 2)
            self.assertEqual(len(doc['duplicates']), 1)
            self.assertEqual(len(doc['opportunities']), 3)


if __name__ == '__main__':
    unittest.main()
