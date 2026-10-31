"""Synthetic runtime/dispatch checks; never rebuild a real report."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from report_build import build_plan


class ReportBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.week = self.root / 'live-review/test-project/2026-09-19'
        (self.week / 'scripts').mkdir(parents=True)
        (self.week / '周报/src').mkdir(parents=True)
        (self.week / '周报/src/data.json').write_text('{}')
        (self.week / 'scripts/rebuild_accepted_report.py').write_text(
            'from pathlib import Path\nimport json, sys\n'
            'Path("called.json").write_text(json.dumps(sys.argv[1:]))\n')
        self.home = self.root / 'home'
        for version in ['1.0.9', '1.0.11']:
            f = self.home / '.codex/plugins/cache/openai-curated-remote/data-analytics' / version / 'scripts/data-app.mjs'
            f.parent.mkdir(parents=True)
            f.write_text('// synthetic')
        self.runtime = {'node': Path(sys.executable), 'python': Path(sys.executable), 'home': self.home}

    def test_current_runtime_and_read_only_default(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        plan = build_plan(self.week, **self.runtime)
        self.assertIn('/1.0.11/', plan['command'][5])
        self.assertEqual(plan['cwd'], str(self.week.resolve()))
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))
        self.assertFalse((self.week / 'called.json').exists())

    def test_explicit_bad_runtime_does_not_silently_fallback(self):
        with self.assertRaises(ValueError):
            build_plan(self.week, **dict(self.runtime, node=self.root / 'missing'))
        with self.assertRaises(ValueError):
            build_plan(self.week, **self.runtime, data_app=self.root / 'missing')

    def test_no_baseline_substitution(self):
        with self.assertRaises(ValueError):
            build_plan(self.week.parent / '2026-09-26', **self.runtime)

    def test_verify_requires_preview(self):
        with self.assertRaises(ValueError):
            build_plan(self.week, **self.runtime, verify_http=True)
        plan = build_plan(self.week, **self.runtime, verify_http=True,
                          preview_url='http://127.0.0.1:9999/', skip_snapshot=True)
        self.assertIn('--skip-snapshot', plan['command'])
        self.assertIn('--verify-http', plan['command'])

    def test_explicit_run_forwards_to_synthetic_builder(self):
        data = self.home / '.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11/scripts/data-app.mjs'
        cmd = [sys.executable, str(Path(__file__).with_name('report_build.py')),
               '--week-root', str(self.week), '--python', sys.executable,
               '--node', sys.executable, '--data-app', str(data), '--skip-snapshot']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.week / 'called.json').exists())
        result = subprocess.run(cmd + ['--run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        forwarded = json.loads((self.week / 'called.json').read_text())
        self.assertIn('--skip-snapshot', forwarded)
        self.assertEqual(forwarded[forwarded.index('--data-app') + 1], str(data.resolve()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
