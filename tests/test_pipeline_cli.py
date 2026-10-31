"""Exercise public CLI entry points and the runnable synthetic scoring example."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PipelineCLITests(unittest.TestCase):
    def test_all_help_commands_work_without_model_imports(self):
        for name in ('collect_media', 'process_transcripts', 'analyze_audio',
                     'transcribe_missing', 'archive_audio', 'score_hosts', 'attribute_comment_leads'):
            with self.subTest(module=name):
                result = subprocess.run([sys.executable, '-B', '-m', f'pipeline.{name}', '--help'],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_synthetic_scoring_example(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ratings.json'
            result = subprocess.run([sys.executable, '-B', '-m', 'pipeline.score_hosts',
                '--input', str(ROOT/'tests/fixtures/synthetic-hosts.json'), '--output', str(target)],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = json.loads(target.read_text())
            self.assertEqual([host['rank'] for host in doc['hosts']], [1, 2])
            self.assertTrue(all(len(host['dimensions']) == 7 for host in doc['hosts']))
            self.assertTrue(all(host['status'] == 'provisional' for host in doc['hosts']))


if __name__ == '__main__':
    unittest.main()
