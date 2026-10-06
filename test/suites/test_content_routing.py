#!/usr/bin/env python3
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> int:
    errors = []
    orchestrator = read("skills/content-orchestrator/SKILL.md")
    project_rules = read("AGENTS.md")
    geo_manifest = read("capabilities/geo/manifest.json")

    expectations = [
        ("orchestrator supports the three target platforms", all(name in orchestrator for name in ["视频号", "抖音", "小红书"])),
        ("social content does not always load full GEO", "不得默认加载完整 GEO" in project_rules),
        ("GEO has a single source of truth", "GEO 能力唯一真源" in project_rules),
        ("GEO manifest declares the capability package", "geo" in geo_manifest.lower()),
        ("orchestrator must offer to scaffold a project root",
         "capabilities/project-scaffold/scripts/init_project.py" in orchestrator),
        ("orchestrator routes the marketplace channel",
         "capabilities/content-production/channels/xianyu.md" in orchestrator),
    ]
    for label, passed in expectations:
        if not passed:
            errors.append(label)

    writing_entries = [
        "skills/content-orchestrator/SKILL.md",
        "skills/geo-content-brief/SKILL.md",
        "skills/geo-website-renderer/SKILL.md",
        "skills/geo-prepublish-core/SKILL.md",
        "skills/geo-monitor/SKILL.md",
        "skills/article-pipeline/SKILL.md",
    ]
    for entry in writing_entries:
        if "capabilities/geo/methods/positioning-and-audience.md" not in read(entry):
            errors.append(f"writing entry detached from positioning method: {entry}")
    # 交付前必须跑严格定位门禁的两个入口，按名字取，不靠下标
    for entry in ["skills/content-orchestrator/SKILL.md", "skills/geo-prepublish-core/SKILL.md"]:
        if "--require-ready" not in read(entry):
            errors.append(f"delivery entry lacks strict positioning gate: {entry}")

    pipeline = read("skills/article-pipeline/SKILL.md")
    pipeline_expectations = [
        ("capabilities/content-production/strategies/creative-strategies.md",
         "文章流水线必须引用策略库真源"),
        ("capabilities/content-production/styles/README.md",
         "文章流水线必须引用风格约定"),
        ("capabilities/content-production/scripts/check_authorial.py",
         "文章流水线必须跑作者化检查"),
        ("tasks/", "文章流水线必须以任务单据为输入"),
    ]
    for needle, reason in pipeline_expectations:
        if needle not in pipeline:
            errors.append(reason)
    if "普通知识文章不强制品牌卡" not in orchestrator:
        errors.append("ordinary knowledge writing must not require brand positioning")

    retired = ["01-intent", "02-compete", "03-content", "04-monitor", "05-report",
               "06-source-pool", "07-prepublish", "lib"]
    for name in retired:
        if (ROOT / name).exists():
            errors.append(f"retired legacy module came back: {name}")

    for entry in writing_entries:
        body = read(entry)
        for name in retired:
            if re.search(rf"(?<![\w/-]){re.escape(name)}/", body):
                errors.append(f"{entry} still points at retired module: {name}/")

    # 路由表指向的每个系统层文件都得真的存在。写错一个路径，Agent 会照着跑然后失败，
    # 而失败现场在用户的对话里，不在这个仓库里——所以在这里拦住。
    system_path = re.compile(r"(?:capabilities|skills|test|00-meta)/[A-Za-z0-9_./-]+\.(?:py|json|jsonl|md|html)")
    for entry in writing_entries:
        for token in sorted(set(system_path.findall(read(entry)))):
            if not (ROOT / token).exists():
                errors.append(f"{entry} points at a path that does not exist: {token}")

    # 交易渠道契约：结构可以变，但「未知规则阻止发布」这条硬线不能在改稿时被顺手删掉——
    # 删掉它不会报错，只会让未核验类目和资质悄悄变成可发布。
    channel_contract = read("capabilities/content-production/channels/xianyu.md")
    if "未知项阻止" not in channel_contract:
        errors.append("交易渠道契约必须保留「未知项阻止发布」硬线")

    if errors:
        print("FAIL content routing contract")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS content routing contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
