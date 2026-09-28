#!/usr/bin/env python3
"""HQ Content Engine 统一质量门禁。仅使用 Python 标准库。

只有一条命令：`python3 test/run_quality_gate.py`。全部测试都很快，
分 quick/full/release 三档只会让人挑便宜的那档跑，然后误以为通过了门禁。
需要更短的反馈时用 `--changed`，但它不能替代最终门禁。
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "test/reports"
BASELINE = ROOT / "test/baseline.json"
SCHEMA_VERSION = 2

# 系统根和项目根是两个目录。ROOT 永远是系统根（门禁、基准住这里），
# 项目根由 --project 决定，并通过环境变量传给每个测试子进程。
sys.path.insert(0, str(ROOT))
from project import MARKER, find_project  # noqa: E402

# 无论改动落在哪里都必须跑的测试：它们守的是门禁和分层本身，
# 一旦被跳过，其余测试是否真的跑了就无从判断。
ALWAYS_RUN = {"feature-registry-contract"}
RULE_DOCS = {"AGENTS.md", "TEST_PLAN.md", "README.md"}


def load_json(path: Path):
    """读 JSON，坏掉时报人能看懂的话。

    这里不吞异常。项目标记坏了就必须停机：降级成「没有基准」会让门禁把产出基准
    按当前状态重建一次，而当前状态可能正是被删空的那个——那等于用一次静默重建
    盖掉「稿子没了」这个信号，而这条信号正是产出基准存在的理由。
    """
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise SystemExit(f"读不到 {path}：{exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{path} 不是合法 JSON（第 {exc.lineno} 行）：{exc.msg}\n"
            f"这个文件是项目标记，坏了就认不出项目、也读不到产出基准。\n"
            f"修好它，或从备份取回；确认要重建就先删掉它，再跑\n"
            f"  python3 {ROOT}/capabilities/project-scaffold/scripts/init_project.py {path.parent}"
        )


def changed_paths() -> list[str]:
    commands = [
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    paths = set()
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            paths.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(paths)


def base_ids(tests: list[dict]) -> set[str]:
    return set(ALWAYS_RUN) | {item["id"] for item in tests if item["tier"] == "static"}


def select_by_changes(tests: list[dict], registry: dict, paths: list[str]) -> tuple[list[dict], list[str]]:
    selected_ids = base_ids(tests)
    impacted = []
    for feature in registry["features"]:
        if any(path == owner or path.startswith(owner.rstrip("/") + "/") for owner in feature["owner_paths"] for path in paths):
            impacted.append(feature["id"])
            selected_ids.update(feature["test_ids"])
    # 规则文档和门禁自身变动时无法局部判断影响面，全量跑。
    if any(path in RULE_DOCS or path.startswith("test/") for path in paths):
        selected_ids.update(item["id"] for item in tests)
    return [item for item in tests if item["id"] in selected_ids], impacted


def run_test(item: dict) -> dict:
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(item["command"], cwd=ROOT, env=env, capture_output=True, text=True,
                                timeout=item.get("timeout_seconds", 120), check=False)
        status = "pass" if result.returncode == 0 else "fail"
        output = (result.stdout + result.stderr).strip()
        return_code = result.returncode
    except subprocess.TimeoutExpired as exc:
        status, return_code = "fail", 124
        output = f"Timeout after {item.get('timeout_seconds', 120)}s\n{exc.stdout or ''}\n{exc.stderr or ''}".strip()
    return {"id": item["id"], "name": item["name"], "tier": item["tier"], "status": status,
            "return_code": return_code, "duration_seconds": round(time.monotonic() - started, 3), "output": output}


def output_metrics(project: Path) -> dict:
    """产出指标。数的是**项目根**里的产物。

    宪法第 1 条：价值等于署名产物。所以基准要数产物，不能只数代码和测试。
    这些数字是判断「系统有没有在产出」的唯一客观依据。
    """
    tasks_dir = project / "tasks"
    task_files = [path for path in tasks_dir.glob("*.md")
                  if path.name not in {"README.md", "_template.md"}] if tasks_dir.is_dir() else []
    delivered = 0
    for path in task_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^stage:\s*(delivered|distributed)\s*$", text, re.MULTILINE):
            delivered += 1
    packages = project / "content/packages"
    # 渠道包是**目录**，不是某个文件名。一个 `<channel>/<idea>/<topic>/` 目录就是一个渠道包，
    # 主稿 `article.md` 和派生的 `copy.md` 都算数。
    #
    # 这里曾经只数 `copy.md`——那个口径建立在「主稿固定住 blog/」的旧假设上，
    # 数的是「派生了几个其他渠道版本」。2026-09-28 站 5 把主稿路径改成按渠道参数化，
    # 主稿住进目标渠道目录后，这个口径就数不到它了：项目里明明有一个 toutiao 渠道包，
    # 门禁报 `渠道包: 1 → 0`。**产出统计口径必须跟着路径约定走**，否则产物丢了它也不会红。
    package_dirs = [
        path for path in packages.glob("*/*/*")
        if path.is_dir() and any((path / name).is_file() for name in ("article.md", "copy.md"))
    ]
    return {
        "tasks": len(task_files),
        "tasks_delivered": delivered,
        "articles": len(list(packages.glob("*/*/*/article.md"))),
        "channel_packages": len(package_dirs),
        "production_briefs": len(list((project / "content/briefs").glob("*/*/production-brief.json"))),
        "fact_packs": len(list((project / "facts").glob("*/*/manifest.json"))),
    }


LABELS = {"tasks": "任务", "tasks_delivered": "已交付任务", "articles": "文章成稿",
          "channel_packages": "渠道包", "production_briefs": "制作简报", "fact_packs": "事实包"}


def compare_baseline(metrics: dict, report: dict, project: Path) -> tuple:
    """和基准比，返回（说明行，是否有产出倒退）。

    基准分两处：**健康基准在系统**（测试数、覆盖率），**产出基准在项目**。
    分开的理由——系统健康是全局的，产物是每个项目自己的。
    两个项目共用一个产出基准，只会互相干扰。

    **产出变少直接判 FAIL。** 这条信号不能只报告不拦截：产物消失往往没有报错，
    页面就是空的，如果门禁还是绿的，就没人会发现。变多不算问题。
    确实要减少（清理旧稿、拆项目），就改 `.hq-geo.json` 的 `output_baseline`
    并在 note 里写清原因——让减少变成一个有人做过的决定，而不是一次静默丢失。
    """
    lines = []
    if not BASELINE.is_file():
        lines.append("系统基准未定义：test/baseline.json 不存在，无法判断这次改动是进步还是退步")
    else:
        health = load_json(BASELINE).get("health", {})
        if health:
            lines.append(f"测试 {report['passed']}/{report['total']}"
                         f"（基准 {health.get('tests_passing', '?')}/{health.get('tests_total', '?')}）")
            lines.append(f"覆盖率 {report['coverage']['coverage_percent']}%"
                         f"（基准 {health.get('feature_coverage_percent', '?')}%）")

    descriptor = load_json(project / MARKER)
    old_output = descriptor.get("output_baseline")
    if not old_output:
        # 只建立，不自动更新——更新基准需要理由，见 test/baseline.json 的 how_to_read。
        descriptor["output_baseline"] = metrics
        (project / MARKER).write_text(
            json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines.append(f"产出基准已建立（{len(metrics)} 项），下次运行开始比对")
        return lines, False

    regressed = []
    output_lines = []
    for key, value in metrics.items():
        old = old_output.get(key)
        if old is None:
            output_lines.append(f"{LABELS.get(key, key)}: {value}（基准未记录）")
        elif value < old:
            output_lines.append(f"{LABELS.get(key, key)}: {old} → {value} ({value - old:+d}) ← 变少")
            regressed.append(key)
        elif value > old:
            output_lines.append(f"{LABELS.get(key, key)}: {old} → {value} ({value - old:+d})")
    # 没有差异也要说一句。静默会被读成「没检查」。
    lines.extend(output_lines or [f"产出 {len(metrics)} 项与基准一致"])
    if regressed:
        lines.append(f"产出倒退 {len(regressed)} 项。确认是有意清理后，"
                     f"改 {project / MARKER} 的 output_baseline 并在 note 里写明原因。")
    return lines, bool(regressed)


def report_dir(project: Path) -> Path:
    """报告按项目分目录。

    报告是「系统在某个项目上跑出来的结果」。混在一个目录里，
    两个项目的趋势线会互相污染，也就没法比较系统在哪个项目上更有效。

    用 `.hq-geo.json` 的 slug 而不是文件夹名：项目文件夹可以搬、可以改名，
    报告历史不该跟着丢。slug 读不到才退回文件夹名，至少还能跑。
    """
    try:
        slug = json.loads((project / MARKER).read_text(encoding="utf-8")).get("slug")
    except (OSError, ValueError):
        slug = None
    return REPORT_ROOT / (slug or project.name)


def append_history(report: dict, project: Path) -> None:
    """每次结果追加一行。没有历史就没有趋势，没有趋势就谈不上改进。"""
    history = report_dir(project) / "history.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "generated_at": report["generated_at"],
        "mode": report["mode"],
        "project_root": report.get("project_root"),
        "verdict": report["verdict"],
        "passed": report["passed"],
        "total": report["total"],
        "failed": report["failed"],
        "coverage_percent": report["coverage"]["coverage_percent"],
        "duration_seconds": round(sum(item["duration_seconds"] for item in report["results"]), 3),
        "output": report["output"],
    }
    with history.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def coverage_summary(registry: dict) -> dict:
    active = [item for item in registry["features"] if item["status"] in {"implemented", "partial"}]
    covered = [item for item in active if item["test_ids"]]
    return {"implemented_or_partial": len(active), "covered": len(covered),
            "coverage_percent": round(100 * len(covered) / len(active), 1) if active else 100.0,
            "planned": sum(1 for item in registry["features"] if item["status"] == "planned"),
            "frozen": len(registry.get("frozen", []))}


def write_reports(report: dict, project: Path) -> None:
    directory = report_dir(project)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mark = {"pass": "PASS", "fail": "FAIL"}
    lines = ["# 质量门禁报告", "", f"- 结论：**{report['verdict'].upper()}**",
             f"- 模式：`{report['mode']}`", f"- 时间：{report['generated_at']}",
             f"- 系统根：`{report.get('system_root', '?')}`",
             f"- 项目根：`{report.get('project_root', '?')}`",
             f"- 测试：{report['passed']}/{report['total']} 通过",
             f"- 现有能力覆盖：{report['coverage']['covered']}/{report['coverage']['implemented_or_partial']}（{report['coverage']['coverage_percent']}%）",
             f"- 仍在规划、不可对外承诺：{report['coverage']['planned']} 项",
             f"- 已冻结、不接入门禁：{report['coverage']['frozen']} 项", "", "## 测试结果", "",
             "| 测试 | 层级 | 结果 | 耗时 |", "|---|---|---:|---:|"]
    for item in report["results"]:
        lines.append(f"| {item['name']} (`{item['id']}`) | {item['tier']} | {mark[item['status']]} | {item['duration_seconds']}s |")
    output = report.get("output")
    if output:
        lines.extend(["", "## 产出", "", "| 指标 | 数量 |", "|---|---:|"])
        for key, value in output.items():
            lines.append(f"| {LABELS.get(key, key)} | {value} |")
    diff = report.get("baseline_diff") or []
    if diff:
        title = "## 相对基准（产出倒退，判 FAIL）" if report.get("output_regressed") else "## 相对基准"
        lines.extend(["", title, ""])
        lines.extend(f"- {line}" for line in diff)
    if report.get("changed_paths") is not None:
        lines.extend(["", "## 变更影响", "", f"检测到 {len(report['changed_paths'])} 个变更路径；命中功能：{', '.join(report['impacted_features']) or '无明确映射，仅运行基础门禁'}。"])
    failures = [item for item in report["results"] if item["status"] == "fail"]
    if failures:
        lines.extend(["", "## 失败详情", ""])
        for item in failures:
            lines.extend([f"### {item['name']}", "", "```text", item["output"][-4000:] or "无输出", "```", ""])
    (directory / "latest.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 HQ Content Engine 质量门禁")
    parser.add_argument("--project", help="项目根目录。不传则从当前目录向上找 .hq-geo.json")
    parser.add_argument("--changed", action="store_true", help="只运行本地变更影响到的测试（不能替代最终门禁）")
    parser.add_argument("--list", action="store_true", help="列出测试但不执行")
    args = parser.parse_args()
    manifest = load_json(ROOT / "test/test_manifest.json")
    registry = load_json(ROOT / "test/feature_registry.json")
    tests = list(manifest["tests"])
    mode = "full"
    paths, impacted = None, []
    if args.changed:
        mode = "changed"
        paths = changed_paths()
        tests, impacted = select_by_changes(tests, registry, paths)
    if args.list:
        for item in tests:
            print(f"{item['id']:<30} {item['tier']:<12} {item['name']}")
        return 0

    project = find_project(args.project)
    # 每个测试子进程都从环境变量拿项目根，不用各自去猜。
    os.environ["HQ_GEO_PROJECT"] = str(project)

    results = []
    print(f"HQ quality gate ({mode}, {len(tests)} tests)")
    print(f"system  {ROOT}")
    print(f"project {project}")
    for item in tests:
        print(f"RUN  {item['id']} ...", flush=True)
        result = run_test(item)
        results.append(result)
        print(f"{result['status'].upper():4} {item['id']} ({result['duration_seconds']}s)")
    coverage = coverage_summary(registry)
    failed = [item for item in results if item["status"] == "fail"]
    metrics = output_metrics(project)
    report = {"schema_version": SCHEMA_VERSION,
              "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
              "mode": mode, "total": len(results),
              "system_root": str(ROOT), "project_root": str(project),
              "passed": sum(1 for item in results if item["status"] == "pass"), "failed": len(failed),
              "coverage": coverage, "output": metrics, "changed_paths": paths,
              "impacted_features": impacted, "results": results}
    report["baseline_diff"], regressed = compare_baseline(metrics, report, project)
    report["output_regressed"] = regressed
    verdict = "pass" if not failed and not regressed and coverage["coverage_percent"] == 100.0 else "fail"
    report["verdict"] = verdict
    write_reports(report, project)
    append_history(report, project)
    print("\n相对基准：")
    for line in report["baseline_diff"]:
        print(f"  {line}")
    print(f"\nVERDICT: {verdict.upper()}")
    print(f"Report: {report_dir(project) / 'latest.md'}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
