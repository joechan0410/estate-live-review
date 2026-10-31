"""Temporary-workspace tests for the read-only discovery command."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("workspace.py")


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "工作区"
        self.project = self.root / "outputs/live-review/demo-project"
        self.project.mkdir(parents=True)
        (self.root / "knowledge").mkdir()
        self.old = self.project / "2026-09-19"
        self.latest = self.project / "2026-09-26"
        for path in (self.old, self.latest):
            (path / "scripts").mkdir(parents=True)
        self.env = {key: value for key, value in os.environ.items() if key != "ESTATE_WORKBENCH_ROOT"}
        self.env["HOME"] = str(self.base / "empty-home")

    def run_cli(self, *args, cwd=None, env=None):
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args],
            cwd=str(cwd or self.base), env=env or self.env,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.stderr, "")
        return completed.returncode, json.loads(completed.stdout)

    def snapshot(self):
        return {
            str(p.relative_to(self.root)): (p.is_dir(), p.read_bytes() if p.is_file() else None)
            for p in self.root.rglob("*")
        }

    def test_explicit_latest_and_specified_week(self):
        (self.project / "2026-99-99").mkdir()
        (self.project / "2026-9-30").mkdir()
        code, result = self.run_cli("--workspace", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(result["workspace"]["selected_by"], "argument")
        self.assertEqual([p["week"] for p in result["weeks"]], ["2026-09-19", "2026-09-26"])
        self.assertEqual(result["selected_week"]["week"], "2026-09-26")
        self.assertEqual(result["selected_week"]["selected_by"], "latest_existing_directory")
        self.assertFalse(result["selected_week"]["is_user_specified"])
        code, result = self.run_cli("--workspace", str(self.root), "--week", "2026-09-19")
        self.assertEqual(code, 0)
        self.assertEqual(result["selected_week"]["selected_by"], "argument")

    def test_ancestor_discovery_and_environment_precedence(self):
        code, result = self.run_cli(cwd=self.latest / "scripts")
        self.assertEqual(code, 0)
        self.assertEqual(result["workspace"]["path"], str(self.root.resolve()))
        self.assertEqual(result["workspace"]["selected_by"], "cwd_ancestor")
        env = dict(self.env, ESTATE_WORKBENCH_ROOT=str(self.root))
        code, result = self.run_cli(env=env)
        self.assertEqual(code, 0)
        self.assertEqual(result["workspace"]["selected_by"], "environment")
        env["ESTATE_WORKBENCH_ROOT"] = str(self.base / "missing")
        code, result = self.run_cli("--workspace", str(self.root), env=env)
        self.assertEqual(code, 0)
        self.assertEqual(result["workspace"]["selected_by"], "argument")
        code, result = self.run_cli(cwd=self.latest, env=env)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["code"], "workspace_not_found")

    def test_invalid_week_traversal_and_missing_week_do_not_write(self):
        before = self.snapshot()
        for value in ("2026-02-30", "2026-9-19", "../2026-09-19", "/tmp", "2026-09-19/../2026-09-26"):
            with self.subTest(week=value):
                code, result = self.run_cli("--workspace", str(self.root), "--week", value)
                self.assertNotEqual(code, 0)
                self.assertEqual(result["error"]["code"], "invalid_week")
        code, result = self.run_cli("--workspace", str(self.root), "--project", "../elsewhere")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["code"], "invalid_project")
        code, result = self.run_cli("--workspace", str(self.root), "--week", "2026-10-03")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["code"], "week_not_found")
        self.assertEqual(before, self.snapshot())

    def test_only_existing_stage_paths_and_baseline_references(self):
        (self.old / "scripts/queue_media.py").write_text("raise RuntimeError('must never execute')")
        (self.old / "scripts/queue_weekly.py").write_text("raise RuntimeError('must never execute')")
        (self.latest / "scripts/queue_media.py").write_text("raise RuntimeError('must never execute')")
        secret = self.root / "knowledge/demo-project/automation/state.json"
        secret.parent.mkdir(parents=True)
        secret.write_text('{"private_id":"DO_NOT_OUTPUT", "credential":"SECRET_VALUE"}')
        before = self.snapshot()
        code, result = self.run_cli("--workspace", str(self.root))
        self.assertEqual(code, 0)
        collection = result["stages"]["collection"]
        self.assertEqual([p["name"] for p in collection["paths"]], ["queue_media"])
        self.assertEqual([p["name"] for p in collection["baseline_paths"]], ["queue_weekly"])
        self.assertIn("仅参考", collection["baseline_use"])
        self.assertEqual(result["stages"]["publication"]["paths"], [])
        self.assertFalse(result["artifacts"]["state"]["contents_read"])
        self.assertNotIn("DO_NOT_OUTPUT", json.dumps(result))
        self.assertNotIn("SECRET_VALUE", json.dumps(result))
        self.assertEqual(before, self.snapshot())

    def test_missing_workspace_project_and_weeks(self):
        before = self.snapshot()
        missing = self.base / "missing"
        code, result = self.run_cli("--workspace", str(missing))
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["code"], "workspace_not_found")
        self.assertFalse(missing.exists())
        code, result = self.run_cli("--workspace", str(self.root), "--project", "unknown")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["code"], "project_not_found")
        self.assertEqual(before, self.snapshot())
        empty = self.root / "outputs/live-review/empty"
        empty.mkdir()
        code, result = self.run_cli("--workspace", str(self.root), "--project", "empty")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["code"], "week_not_found")
        self.assertEqual(list(empty.iterdir()), [])

    def test_external_week_symlink_is_not_selected(self):
        external = self.base / "external"
        external.mkdir()
        (self.project / "2026-10-03").symlink_to(external, target_is_directory=True)
        code, result = self.run_cli("--workspace", str(self.root), "--week", "2026-10-03")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"]["code"], "week_not_found")

    def test_dependency_probe_reads_metadata_without_site_or_business_imports(self):
        venv = self.root / "outputs/live-review/.venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin/python").symlink_to(sys.executable)
        (venv / "pyvenv.cfg").write_text("home = " + str(Path(sys.executable).parent) + "\n")
        site = venv / "lib" / ("python%d.%d" % sys.version_info[:2]) / "site-packages"
        site.mkdir(parents=True)
        marker = self.base / "import-side-effect"
        bad_import = "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('unsafe')\n"
        (site / "sitecustomize.py").write_text(bad_import)
        (site / "torch.py").write_text(bad_import)
        (site / "side_effect.pth").write_text("import sitecustomize\n")
        distribution = site / "torch-9.8.7.dist-info"
        distribution.mkdir()
        (distribution / "METADATA").write_text("Metadata-Version: 2.1\nName: torch\nVersion: 9.8.7\n")
        before = self.snapshot()
        code, result = self.run_cli("--workspace", str(self.root), "--check-dependencies")
        self.assertEqual(code, 0)
        probe = result["dependencies"]["python"]
        self.assertTrue(probe["probe_ok"], probe)
        self.assertEqual(probe["selected_by"], "workspace_venv")
        self.assertEqual(probe["packages"]["torch"]["version"], "9.8.7")
        self.assertFalse(marker.exists())
        self.assertEqual(before, self.snapshot())
        self.assertEqual(set(result["dependencies"]["binaries_on_path"]), {"node", "ffmpeg", "ffprobe"})


if __name__ == "__main__":
    unittest.main()
