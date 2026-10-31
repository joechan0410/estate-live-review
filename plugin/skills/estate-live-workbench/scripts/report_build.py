#!/usr/bin/env python3
"""Resolve current runtimes and plan/run an existing weekly report builder."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def executable(path):
    return path.is_file() and os.access(path, os.X_OK)


def version_key(path):
    for parent in path.parents:
        match = re.match(r"(\d+)\.(\d+)\.(\d+)(?:-|$)", parent.name)
        if match:
            return tuple(map(int, match.groups()))
    return (-1, -1, -1)


def resolve_runtime(week_root, node=None, data_app=None, python=None, home=None):
    home = home or Path.home()
    node_candidates = [Path(node).expanduser()] if node else []
    if not node:
        if shutil.which('node'):
            node_candidates.append(Path(shutil.which('node')))
        node_candidates.append(home / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
    node_path = next((p.resolve() for p in node_candidates if executable(p)), None)
    if node_path is None:
        raise ValueError('Node executable not found; provide --node from the current workspace runtime.')
    data_root = home / '.codex/plugins/cache/openai-curated-remote/data-analytics'
    data_candidates = [Path(data_app).expanduser()] if data_app else sorted(
        [*data_root.glob('*/scripts/data-app.mjs'), *data_root.glob('*/output_formats/html/scripts/data-app.mjs')],
        key=version_key, reverse=True)
    data_path = next((p.resolve() for p in data_candidates if p.is_file()), None)
    if data_path is None:
        raise ValueError('Data report builder not found; provide --data-app from the installed Data plugin.')
    python_candidates = [Path(python).expanduser()] if python else [
        week_root.parent.parent / '.venv/bin/python', Path(sys.executable)]
    python_path = next((p.absolute() for p in python_candidates if executable(p)), None)
    if python_path is None:
        raise ValueError('Python executable not found; provide --python.')
    return python_path, node_path, data_path


def build_plan(week_root, *, node=None, data_app=None, python=None,
               skip_snapshot=False, verify_http=False, preview_url=None, home=None):
    week_root = Path(week_root).expanduser().resolve()
    builder = week_root / 'scripts/rebuild_accepted_report.py'
    if not builder.is_file():
        raise ValueError('Selected week has no scripts/rebuild_accepted_report.py; adapt the accepted baseline first.')
    if not (week_root / '周报/src/data.json').is_file():
        raise ValueError('Selected week has no 周报/src/data.json. Prepare target-week evidence and report source first.')
    python_path, node_path, data_path = resolve_runtime(week_root, node, data_app, python, home)
    command = [str(python_path), str(builder), '--node', str(node_path), '--data-app', str(data_path)]
    if skip_snapshot:
        command.append('--skip-snapshot')
    if verify_http:
        if not preview_url:
            raise ValueError('--verify-http requires an explicitly verified --preview-url.')
        command.append('--verify-http')
    if preview_url:
        command += ['--preview-url', preview_url]
    return {'status': 'planned', 'week_root': str(week_root), 'command': command,
            'cwd': str(week_root), 'skip_snapshot': skip_snapshot,
            'note': 'This plan does not execute analysis or alter report files. --run starts the existing target-week builder.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', type=Path, help='Standalone web directory, containing package.json.')
    parser.add_argument('--week-root', type=Path, help='Optional existing weekly workspace builder.')
    parser.add_argument('--node', type=Path)
    parser.add_argument('--data-app', type=Path)
    parser.add_argument('--python', type=Path)
    parser.add_argument('--skip-snapshot', action='store_true')
    parser.add_argument('--verify-http', action='store_true')
    parser.add_argument('--preview-url')
    parser.add_argument('--run', action='store_true', help='Execute the existing builder; default only prints a plan.')
    args = parser.parse_args()
    if args.project_dir:
        project = args.project_dir.expanduser().resolve()
        if not (project / 'package.json').is_file():
            parser.error('--project-dir must contain package.json')
        npm = shutil.which('npm')
        if not npm:
            parser.error('npm is required for the standalone web build')
        plan = {'status': 'planned', 'command': [npm, 'run', 'build'], 'cwd': str(project), 'mode': 'standalone-web'}
        print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
        if not args.run:
            return 0
        return subprocess.run(plan['command'], cwd=project, check=False).returncode
    if not args.week_root:
        parser.error('provide --project-dir for the open-source web app or --week-root for an existing workspace')
    try:
        plan = build_plan(args.week_root, node=args.node, data_app=args.data_app,
                          python=args.python, skip_snapshot=args.skip_snapshot,
                          verify_http=args.verify_http, preview_url=args.preview_url)
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.run:
        return 0
    completed = subprocess.run(plan['command'], cwd=plan['cwd'], check=False)
    print(json.dumps({'status': 'builder_succeeded' if completed.returncode == 0 else 'builder_failed',
                      'returncode': completed.returncode,
                      'browser_verification': 'not_performed_by_this_wrapper'}, ensure_ascii=False))
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
