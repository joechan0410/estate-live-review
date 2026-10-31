"""Synthetic acoustic intervals exercise duration accounting without a model."""
import unittest

from pipeline.analyze_audio import speech_activity_metrics


class SpeechActivityTests(unittest.TestCase):
    def test_strict_threshold_counts_full_gap(self):
        result = speech_activity_metrics([
            {'start': 10, 'end': 20},
            {'start': 30.25, 'end': 40},
        ], 51)
        self.assertEqual(result['non_speech_windows_gt_10s'], [
            {'start': 20, 'end': 30.25, 'duration': 10.25},
            {'start': 40, 'end': 51, 'duration': 11},
        ])
        self.assertEqual(result['non_speech_seconds_above_threshold'], 21.25)

    def test_overlap_union_clips_recording_edges(self):
        result = speech_activity_metrics([
            {'start': 15, 'end': 30}, {'start': -5, 'end': 18},
            {'start': 50, 'end': 70},
        ], 60)
        self.assertEqual(result['speech_seconds'], 40)
        self.assertEqual(result['non_speech_windows_gt_10s'], [
            {'start': 30, 'end': 50, 'duration': 20},
        ])

    def test_no_speech_and_full_speech(self):
        self.assertEqual(speech_activity_metrics([], 10)['non_speech_windows_gt_10s'], [])
        self.assertEqual(speech_activity_metrics([], 10.001)['non_speech_seconds_above_threshold'], 10.001)
        self.assertEqual(speech_activity_metrics([{'start': 0, 'end': 25}], 25)['non_speech_windows_gt_10s'], [])

    def test_invalid_intervals_fail(self):
        for duration in (float('nan'), -1, True):
            with self.assertRaises(ValueError):
                speech_activity_metrics([], duration)
        with self.assertRaises(ValueError):
            speech_activity_metrics([{'start': 3, 'end': 2}], 10)


if __name__ == '__main__':
    unittest.main()
