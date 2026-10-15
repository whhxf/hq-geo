#!/usr/bin/env python3
"""Render a local parameterized clip with the integrated huashu engine."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ENGINE = Path(__file__).resolve().parents[1] / 'engines/huashu/scripts/engine/render.py'


def command(spec, out, python=sys.executable):
    data = json.loads(Path(spec).read_text())
    if data.get('grammar') != 'y2_vox':
        raise ValueError('尚未验证的 huashu 语法，不得静默替换')
    if not 0 < float(data.get('duration', 0)) <= 8:
        raise ValueError('每镜时长必须在 0 到 8 秒之间')
    return [python, str(ENGINE), '--spec', str(Path(spec).resolve()), '--out', str(Path(out).resolve())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        cmd = command(args.spec, args.out, args.python)
        if args.dry_run:
            print(json.dumps({'command': cmd, 'engine': 'huashu', 'status': 'planned'}, ensure_ascii=False))
            return 0
        if not shutil.which('ffmpeg'):
            raise ValueError('环境不可用：缺少 ffmpeg')
        probe = subprocess.run([args.python, '-c', 'import playwright.sync_api'], capture_output=True)
        if probe.returncode:
            raise ValueError('环境不可用：所选 Python 缺少 Playwright；指定 --python，不降级为字卡')
        return subprocess.run(cmd, check=False).returncode
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
