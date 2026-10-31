#!/usr/bin/env python3
"""Read-only workspace discovery. Never load or execute business scripts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


BASELINE_WEEK = "2026-09-19"
STAGES = {
    "collection": ("queue_media", "queue_weekly"),
    "evidence": ("prepare_whole_week_evidence", "prepare_full_comment_review"),
    "comments": (
        "audit_all_comments", "audit_all_comment_leads",
        "adjudicate_host_session_conversion", "build_comment_acquisition_insights",
    ),
    "metrics": ("build_current_host_metrics", "apply_content_scoring_v2"),
    "report": ("rebuild_accepted_report", "build_period_views"),
    "verify": ("verify_two_week_delivery", "verify_whole_week_review"),
    "publication": ("prepare_protected_release", "verify_published_release_http"),
}
PACKAGES = (
    "httpx", "m3u8", "silero-vad", "scikit-learn",
    "numpy", "pandas", "requests", "soundfile", "torch", "torchaudio",
    "pyannote.audio", "funasr", "faster-whisper", "openai-whisper",
    "mlx-whisper", "librosa", "scipy", "transformers",
)


class DiagnosticError(Exception):
    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.payload = {"ok": False, "error": {"code": code, "message": message, **details}}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise DiagnosticError("invalid_arguments", message)


def valid_week(value: str) -> bool:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def workspace_exists(root: Path) -> bool:
    return ((root / "outputs/live-review").is_dir() and (root / "knowledge").is_dir()) or ((root / "web/package.json").is_file() and (root / "pipeline").is_dir())


def discover_workspace(explicit: str | None) -> tuple[Path, str]:
    configured = explicit if explicit is not None else os.environ.get("ESTATE_WORKBENCH_ROOT")
    if configured is not None:
        root = Path(configured).expanduser().resolve()
        source = "argument" if explicit is not None else "environment"
        if not workspace_exists(root):
            raise DiagnosticError(
                "workspace_not_found", "工作区须包含 outputs/live-review 与 knowledge 目录。",
                path=str(root), selected_by=source,
            )
        return root, source
    cwd = Path.cwd().resolve()
    for root in (cwd, *cwd.parents):
        if workspace_exists(root):
            return root, "cwd_ancestor"
    fallback = Path.home() / "Documents/地产工作台"
    if workspace_exists(fallback):
        return fallback.resolve(), "home_default"
    raise DiagnosticError("workspace_not_found", "未找到工作区；请设置 --workspace。")


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def file_status(path: Path) -> dict:
    return {"path": str(path), "exists": path.is_file(), "contents_read": False}


def stage_paths(week: Path, names: tuple[str, ...]) -> list[dict]:
    return [
        {"name": name, "path": str(week / "scripts" / (name + ".py"))}
        for name in names
        if (week / "scripts" / (name + ".py")).is_file()
        and inside(week / "scripts" / (name + ".py"), week)
    ]


def check_dependencies(root: Path) -> dict:
    candidate = root / "outputs/live-review/.venv/bin/python"
    use_venv = candidate.is_file() and os.access(candidate, os.X_OK)
    interpreter = str(candidate if use_venv else Path(sys.executable).absolute())
    # -I removes cwd/PYTHONPATH/user-site; -S also prevents sitecustomize and .pth
    # execution. Add package directories directly for metadata reads only.
    probe = r'''
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import sysconfig
executable = Path(sys.argv[1])
venv_root = executable.parent.parent
if (venv_root / "pyvenv.cfg").is_file():
    paths = [venv_root / "lib" / ("python%d.%d" % sys.version_info[:2]) / "site-packages",
             venv_root / "Lib/site-packages"]
else:
    paths = [Path(sysconfig.get_path(key)) for key in ("purelib", "platlib")]
for path in paths:
    if path.is_dir() and str(path) not in sys.path:
        sys.path.append(str(path))
versions = {}
for name in json.loads(sys.argv[2]):
    try:
        versions[name] = {"installed": True, "version": metadata.version(name)}
    except metadata.PackageNotFoundError:
        versions[name] = {"installed": False, "version": None}
print(json.dumps({"python_version": sys.version.split()[0], "packages": versions}))
'''
    python_result = {
        "path": interpreter,
        "selected_by": "workspace_venv" if use_venv else "current_interpreter",
        "metadata_only": True,
        "site_initialization": False,
    }
    try:
        completed = subprocess.run(
            [interpreter, "-I", "-S", "-B", "-c", probe, interpreter, json.dumps(PACKAGES)],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if completed.returncode == 0:
            python_result.update(json.loads(completed.stdout))
            python_result["probe_ok"] = True
        else:
            python_result.update(probe_ok=False, error="metadata_probe_failed", exit_code=completed.returncode)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        python_result.update(probe_ok=False, error="metadata_probe_unavailable")
    binaries = {}
    for name in ("ffmpeg", "ffprobe", "node"):
        found = shutil.which(name)
        binaries[name] = {"available": found is not None, "path": str(Path(found).absolute()) if found else None}
    legacy_node = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    return {
        "python": python_result,
        "binaries_on_path": binaries,
        "node_legacy_default": {
            "path": str(legacy_node),
            "exists": legacy_node.is_file(),
            "executable": legacy_node.is_file() and os.access(legacy_node, os.X_OK),
            "available_path": binaries["node"]["path"],
            "note": "历史报告入口使用固定 Node 路径；执行前核对该路径，可用 PATH 路径仅供配置参考。",
        },
    }


def inspect_workspace(args) -> dict:
    if not re.fullmatch(r"[\w-]+", args.project):
        raise DiagnosticError("invalid_project", "project 须为单个目录名称。")
    if args.week is not None and not valid_week(args.week):
        raise DiagnosticError("invalid_week", "week 须为真实日期，格式 YYYY-MM-DD。")
    root, source = discover_workspace(args.workspace)
    if (root / "web/package.json").is_file() and (root / "pipeline").is_dir():
        result = {
            "ok": True, "read_only": True, "mode": "standalone-source",
            "workspace": {"path": str(root), "selected_by": source},
            "web": {"path": str(root / "web"), "build_command": ["npm", "run", "build"]},
            "pipeline": {"path": str(root / "pipeline"), "scripts": sorted(p.name for p in (root / "pipeline").glob("*.py") if p.name != "__init__.py")},
            "requested_week": args.week,
        }
        if args.check_dependencies:
            result["dependencies"] = {"python": sys.version.split()[0], **{name: shutil.which(name) for name in ("node", "npm", "ffmpeg", "ffprobe")}}
        return result
    project = root / "outputs/live-review" / args.project
    if not project.is_dir() or not inside(project, root):
        raise DiagnosticError("project_not_found", "项目目录不存在或位于工作区之外。", path=str(project))
    weeks = sorted(
        p.name for p in project.iterdir()
        if p.is_dir() and valid_week(p.name) and inside(p, project)
    )
    if args.week is not None:
        selected = args.week
        if selected not in weeks:
            raise DiagnosticError("week_not_found", "指定周目录不存在。", path=str(project / selected))
        selected_by = "argument"
    elif weeks:
        selected, selected_by = weeks[-1], "latest_existing_directory"
    else:
        raise DiagnosticError("week_not_found", "项目中未发现有效的现有周目录。", path=str(project))
    week = project / selected
    knowledge = root / "knowledge" / args.project
    automation = knowledge / "automation"
    workflow_candidates = (
        root / "workflows/weekly-workflow.md",
        automation / "weekly-workflow.md",
    )
    artifacts = {
        "weekly_workflow": [file_status(p) for p in workflow_candidates],
        "weekly_acceptance": file_status(automation / "weekly-acceptance.md"),
        "rule_updates": file_status(automation / "rule-updates.json"),
        "state": file_status(automation / "state.json"),
        "continuation": file_status(week / "CONTINUATION.json"),
        "processing_states": [file_status(week / name) for name in (
            "processing-state.json", "media-processing-state.json",
            "alignment-processing-state.json", "compression-processing-state.json",
        )],
        "runtime_locks": [file_status(week / name) for name in (
            "data-processing.lock", "media-processing.lock",
            "alignment-processing.lock", "compression-processing.lock",
            "processing.lock", "data/review/rebuild-accepted-report.lock",
        )],
        "roster": [file_status(knowledge / "roster" / name) for name in (
            "hosts.json", "people.json", "confirmed-aliases.json",
            "operator-accounts.json", "project-accounts.json",
        )],
    }
    baseline = project / BASELINE_WEEK
    stages = {}
    for stage, names in STAGES.items():
        current_paths = stage_paths(week, names)
        current_names = {entry["name"] for entry in current_paths}
        missing = tuple(name for name in names if name not in current_names)
        references = stage_paths(baseline, missing) if baseline != week and inside(baseline, project) else []
        stages[stage] = {
            "paths": current_paths,
            "missing_entrypoints": list(missing),
            "baseline_paths": references,
            "baseline_use": "仅参考；不可直接对目标周执行，须先检查并适配周目录及输入。" if references else None,
        }
    result = {
        "ok": True,
        "read_only": True,
        "workspace": {"path": str(root), "selected_by": source},
        "project": {"name": args.project, "path": str(project)},
        "weeks": [{"week": name, "path": str(project / name)} for name in weeks],
        "selected_week": {
            "week": selected, "path": str(week), "selected_by": selected_by,
            "is_user_specified": args.week is not None,
            "note": "最新现有周仅用于目录诊断；用户的分析目标周仍需按请求确定。" if args.week is None else "用户显式指定的现有周目录。",
        },
        "artifacts": artifacts,
        "stages": stages,
    }
    if args.check_dependencies:
        result["dependencies"] = check_dependencies(root)
    return result


def main(argv=None) -> int:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="工作区根目录；其次使用 ESTATE_WORKBENCH_ROOT。")
    parser.add_argument("--project", default="demo-project")
    parser.add_argument("--week", help="已有周目录，严格 YYYY-MM-DD。")
    parser.add_argument("--check-dependencies", action="store_true")
    try:
        result = inspect_workspace(parser.parse_args(argv))
    except DiagnosticError as error:
        print(json.dumps(error.payload, ensure_ascii=False, indent=2))
        return 2
    except OSError:
        print(json.dumps({"ok": False, "error": {"code": "filesystem_unavailable", "message": "无法读取工作区路径。"}}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
