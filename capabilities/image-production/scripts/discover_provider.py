#!/usr/bin/env python3
"""Resolve an observed image tool; never invoke or invent host capabilities."""
import argparse
import json
from pathlib import Path


def discover(tools, local_skills=()):
    for tool in tools:
        if tool.get('available') is True and 'generate' in tool.get('operations', []):
            return {'status': 'host_action_required', 'provider': tool['id'],
                    'kind': 'host', 'evidence': tool.get('evidence', 'observed session tool schema')}
    for skill in local_skills:
        path = Path(skill.get('path', ''))
        if path.is_file() and skill.get('executable_verified') is True:
            return {'status': 'skill_action_required', 'provider': skill['id'],
                    'kind': 'local_skill', 'path': str(path),
                    'evidence': skill.get('evidence', 'verified local entry and dependencies')}
    return {'status': 'needs_user_input', 'question': '当前没有已验证的生图能力。请提供图片、指定可用 Skill，或配置生图服务。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text())
    print(json.dumps(discover(data.get('tools', []), data.get('local_skills', [])), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
