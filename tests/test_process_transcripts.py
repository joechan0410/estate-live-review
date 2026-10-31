"""Portable lexicon regression checks using synthetic, temporary input only."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pipeline.process_transcripts import load_lexicons, normalize_local_segments


class TranscriptLexiconTests(unittest.TestCase):
    def test_local_asr_clips_ranges_and_keeps_original_text(self):
        chunk = {'start': 100.5, 'end': 110.5, 'segments': [
            {'start': -2, 'end': 2, 'text': '合成开头。'},
            {'start': 2, 'end': 25, 'text': '合成结尾。'},
            {'start': 20, 'end': 21, 'text': '范围外。'},
            {'start': 3, 'end': 3, 'text': '零时长。'},
        ]}
        self.assertEqual(normalize_local_segments(chunk), [
            {'start': 100.5, 'end': 110.5, 'raw': '合成开头。合成结尾。'},
        ])

    def test_local_asr_invalid_chunk_fails(self):
        for start, end in ((5, 4), (-1, 10), (0, float('inf'))):
            with self.assertRaises(ValueError):
                normalize_local_segments({'start': start, 'end': end, 'segments': []})

    def test_cli_without_project_lexicon_uses_bundled_candidates(self):
        with tempfile.TemporaryDirectory(prefix='live-lexicon-test-') as directory:
            root = Path(directory)
            session = root / 'data' / 'synthetic-session'
            session.mkdir(parents=True)
            (session / 'complete.json').write_text('{}', encoding='utf-8')
            snapshots = [
                {'offset': 0, 'text': '请点击小峰车预约', 'program_time': None},
                {'offset': 2, 'text': '欢迎大家', 'program_time': None},
            ]
            (session / 'subtitle_snapshots.jsonl').write_text(
                ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in snapshots),
                encoding='utf-8',
            )
            result = subprocess.run(
                [sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'pipeline/process_transcripts.py'),
                 '--root', str(root)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            transcript = json.loads((session / 'transcript.json').read_text(encoding='utf-8'))
            self.assertEqual(transcript[0]['raw'], '请点击小峰车预约')
            self.assertEqual(transcript[0]['text'], transcript[0]['raw'])
            with (session / 'term_review_candidates.csv').open(encoding='utf-8-sig') as source:
                candidates = list(csv.DictReader(source))
            self.assertTrue(any(row['observed'] == '小峰车' and row['candidate'] == '小风车'
                                for row in candidates))
            self.assertFalse((root / 'knowledge').exists())

    def test_project_extension_keeps_bundled_terms_and_explicit_corrections(self):
        with tempfile.TemporaryDirectory(prefix='live-lexicon-test-') as directory:
            root = Path(directory)
            knowledge = root / 'knowledge'
            knowledge.mkdir()
            (knowledge / 'general-lexicon.csv').write_text(
                '标准词,候选误识别,类别,纠错规则\n测试花园,测试花元,项目,核实后使用\n',
                encoding='utf-8',
            )
            (knowledge / 'project-lexicon.csv').write_text(
                'standard,variants,auto_correct\n合成项目,合成项木,true\n候选学校,候选学小,false\n',
                encoding='utf-8',
            )
            aliases, terms = load_lexicons(root)
            self.assertEqual(aliases, {'合成项木': '合成项目'})
            self.assertIn('小风车', {row['标准词'] for row in terms})
            self.assertIn('测试花园', {row['标准词'] for row in terms})

    def test_empty_optional_lexicon_keeps_bundled_terms(self):
        with tempfile.TemporaryDirectory(prefix='live-lexicon-test-') as directory:
            root = Path(directory)
            (root / 'knowledge').mkdir()
            (root / 'knowledge' / 'general-lexicon.csv').write_text(
                '标准词,候选误识别,类别,纠错规则\n', encoding='utf-8',
            )
            aliases, terms = load_lexicons(root)
            self.assertEqual(aliases, {})
            self.assertGreater(len(terms), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
