#!/usr/bin/env python3
"""视频线的契约检查。

视频线最容易出的事不是崩，是**悄悄退化**：

- 合身检查被摘掉，标题折成孤字，而没人报错；
- 时长回到「我觉得 5 秒好看」，语速一变音画就错位；
- 旁白被省掉，视频变成无声幻灯片；
- 「还没做」那几条被当成「已经做了」，于是对外宣称已适配平台安全区。

所以这个检查盯的是**判据在不在、顺序有没有被写死、缺口有没有留痕**。
"""

import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]
CAP = "capabilities/video-production"
TYPO = "capabilities/typography"

SKILL = "skills/video-pipeline/SKILL.md"
README = f"{CAP}/README.md"
TEMPLATE = f"{CAP}/templates/video-scene-type-spec.json"
BUILD = f"{CAP}/scripts/build_frames.py"
COMPOSE = f"{CAP}/scripts/compose.py"
FIT = f"{TYPO}/scripts/check_fit.py"
STYLES = f"{CAP}/styles/video-styles.json"
STYLE_MAP = f"{CAP}/styles/style-map.json"
GALLERY = f"{CAP}/styles/gallery.html"


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def load(relative: str) -> dict:
    return json.loads(read(relative))


def check_skill(errors: list) -> None:
    """六站的判据在不在。删掉一条，Agent 就会自己编一套做法。"""
    if not (SYSTEM / SKILL).is_file():
        errors.append(f"视频流水线 skill 不见了：{SKILL}")
        return
    skill = read(SKILL)
    for needle, reason in [
        ("**先写旁白，再写画面。**", "顺序反了就会做出「画面漂亮但没话说」的视频"),
        ("**缺料停机**", "没有这条，会拿编出来的事实做视频"),
        ("**每一幕的时长由旁白决定**", "时长没有依据，音画必然错位"),
        ("**检查器只负责说出来。**", "不写这条，合身检查会被当成自动改写"),
        ("**判的人不能是写脚本的人。**", "验收必须职责分离；不写这条，验收会退化成自评"),
        ("**环境音垫是垫底，不是音乐。**", "不写这条，会拿音垫当配乐，或者去找有授权的曲子"),
        ("**平台安全区未核验。**", "不写这条，「已适配平台安全区」会被当成可写的话"),
        ("**不自动发布。**", "不写这条，视频会绕过发布授权直接发出去"),
        ("check_fit.py", "合身检查的入口不在 skill 里，判据就没有执行者"),
        ("build_frames.py", "出帧入口不在 skill 里，站 3 会现场编一套渲染做法"),
        ("compose.py", "成片入口不在 skill 里，站 4 会现场编一套合成做法"),
        ("video-scene-type-spec.json", "金样本入口不在 skill 里，每次都要现场编一套参数"),
        ("style-map.json", "选题到风格的映射表不在 skill 里，站 2 会现场编一套风格"),
        ("gallery.html", "风格选择页不在 skill 里，人没法并排看风格"),
    ]:
        if needle not in skill:
            errors.append(f"视频线判据缺失（{reason}）: {needle}")


def check_golden_spec(errors: list) -> None:
    """金样本必须是竖屏 9:16，而且过得了排版校验器。"""
    if not (SYSTEM / TEMPLATE).is_file():
        errors.append(f"视频金样本不见了：{TEMPLATE}")
        return
    spec = load(TEMPLATE)
    canvas = spec.get("canvas", {})
    width, height = canvas.get("width"), canvas.get("height")
    if (width, height) != (1080, 1920):
        errors.append(f"金样本画布变了：{width}×{height}——视频线是竖屏 1080×1920")

    sys.path.insert(0, str(SYSTEM / TYPO / "scripts"))
    import validate_type_spec

    problems = validate_type_spec.validate(spec)
    for problem in problems:
        errors.append(f"视频金样本没过排版判据：{problem}")


def check_fit_is_wired(errors: list) -> None:
    """合身检查必须挂在出帧之前。

    2026-10-10 实测：9 个字的标题在 108px 下要 1030px，只有 864px 可用，
    折成「或者遇到敏感问」+「题，」。**机器一条都不报。**
    这个检查盯的就是「那条拦不住的路，现在有没有人拦」。
    """
    if not (SYSTEM / FIT).is_file():
        errors.append(f"合身检查脚本不见了：{FIT}")
        return
    for anchor in ("def char_width(", "def line_em(", "def check_content("):
        if anchor not in read(FIT):
            errors.append(f"check_fit.py 少了 {anchor}——判据没有执行者")

    build = read(BUILD)
    if "check_fit" not in build:
        errors.append("build_frames.py 没接合身检查——放不下的文案会照常出帧")
    if "check_content" not in build:
        errors.append("build_frames.py 引了 check_fit 但没调用 check_content")
    if build.index("check_content") > build.index("render_cover"):
        errors.append("build_frames.py 里渲染排在合身检查之前——顺序反了，等于没检查")


def check_audio_first(errors: list) -> None:
    """时长必须由旁白算出来，不能是写死的常量。"""
    compose = read(COMPOSE)
    for anchor, reason in [
        ("def synthesize(", "没有旁白合成，视频就是无声幻灯片"),
        ("def probe_duration(", "不量旁白时长，时长就没有依据"),
        ("def generate_bed(", "没有音垫生成，静音处会空"),
        ("def build_scene_plan(", "没有分镜计划，时长和帧数算不出来"),
    ]:
        if anchor not in compose:
            errors.append(f"compose.py 少了 {anchor}——{reason}")

    if "max(min_seconds, spoken + tail)" not in compose:
        errors.append("compose.py 里时长不再由旁白决定——语速一变音画就错位")
    if "apad=whole_dur" not in compose:
        errors.append("compose.py 不再把旁白补齐到整幕长度——音画会对不齐")


def check_gaps_are_recorded(errors: list) -> None:
    """还没做的必须留在纸上。删掉缺口段落，就等于宣称已经做完了。"""
    readme = read(README)
    for needle, reason in [
        ("背景音乐", "背景音乐没接这件事必须留痕，否则会被当成已经有了"),
        ("平台安全区", "平台遮挡范围没核验过，必须留痕"),
        ("没有核验过", "安全区那一条要写明「没核验」，不能只写「已留白」"),
    ]:
        if needle not in readme:
            errors.append(f"视频能力 README 缺「还没做」的记录（{reason}）: {needle}")


def check_style_registry(errors: list) -> None:
    """风格库的引用必须闭合，首选必须跑得动，屏蔽必须生效。

    2026-10-10 建。最容易出的两件事：映射表引一个不存在的风格 id；
    首选指向 prompt-only——那样「选题定了自动走到生成」会在第一步就断。

    2026-10-11 加屏蔽。Conan 判 32 条不需要，清单在 video-styles.json 的
    `blocked.ids`。屏蔽最容易出的两件事：清单写错 id（写错了不报错，
    那条风格照常出现在页面上）；屏蔽只改了数据、没重新生成 gallery
    （页面上那 32 张卡片还在）。两条都盯。
    """
    for path in (STYLES, STYLE_MAP, GALLERY):
        if not (SYSTEM / path).is_file():
            errors.append(f"视频风格库文件不见了：{path}")
    if not (SYSTEM / STYLES).is_file() or not (SYSTEM / STYLE_MAP).is_file():
        return

    registry = load(STYLES)
    mapping = load(STYLE_MAP)

    blocked = set(registry.get("blocked", {}).get("ids", []))
    items = registry.get("styles", []) + registry.get("grammars", [])
    all_ids = {item["id"] for item in items if item.get("id")}
    known = all_ids - blocked
    exec_of = {item["id"]: item.get("execution") for item in items if item.get("id")}

    for item in items:
        for field in ("id", "name", "source", "execution", "status"):
            if not item.get(field):
                errors.append(f"风格条目缺 {field}：{item.get('id', '(无 id)')}")
        if item.get("source") not in registry.get("sources", {}):
            errors.append(
                f"风格 {item.get('id')} 的来源不在 sources 表里：{item.get('source')}"
            )

    for ghost in sorted(blocked - all_ids):
        errors.append(f"屏蔽清单里写了不存在的风格 id：{ghost}——那条风格会照常出现")

    for topic in mapping.get("topics", []):
        for ref in [topic.get("primary")] + list(topic.get("secondary", [])):
            if ref and ref not in known:
                errors.append(f"映射表 {topic.get('id')} 引了不存在的风格：{ref}")
        primary = topic.get("primary")
        if primary in exec_of and exec_of[primary] != "local-render":
            errors.append(
                f"映射表 {topic.get('id')} 的首选不是本地渲染（{exec_of[primary]}）："
                f"{primary}——「自动走到生成」会断在第一步"
            )

    default = mapping.get("default", {})
    for ref in [default.get("primary")] + list(default.get("secondary", [])):
        if ref and ref not in known:
            errors.append(f"映射表兜底引了不存在的风格：{ref}")

    if (SYSTEM / GALLERY).is_file():
        page = read(GALLERY)
        for ghost in sorted(blocked):
            if f'"{ghost}"' in page:
                errors.append(
                    f"屏蔽的风格还在 gallery.html 里：{ghost}"
                    "——数据改了没重跑 build_gallery.py"
                )


def main() -> int:
    errors = []
    check_skill(errors)
    check_golden_spec(errors)
    check_fit_is_wired(errors)
    check_audio_first(errors)
    check_gaps_are_recorded(errors)
    check_style_registry(errors)

    if errors:
        print("FAIL video-pipeline")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "PASS video-pipeline: 六站判据、竖屏金样本、合身前置、旁白定时长、"
        "缺口留痕、风格库引用闭合齐全、屏蔽生效"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
