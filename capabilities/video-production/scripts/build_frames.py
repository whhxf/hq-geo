#!/usr/bin/env python3
"""视频分镜 → PNG 帧。

这一站只做一件事：把每个分镜的文案排成一张图。

**渲染不在这里实现。** 帧就是「图片排版」那一个载体，用的是
`capabilities/typography/` 的同一套引擎（TypeSpec → HTML → Chrome → PNG）。
这里只负责把分镜列表展开成逐帧调用。

为什么这样切：排版判据（字号阶梯、对比度、避头尾、中西文间距）已经在
排版线里建好、测好、有金样本。视频帧和封面是同一类东西——**底图加文字层**。
复制一份渲染器等于让两套判据各自漂移。

用法：
    python build_frames.py --script script.json --spec spec.json --out frames/
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[3]
TYPO_SCRIPTS = SYSTEM / "capabilities/typography/scripts"
sys.path.insert(0, str(TYPO_SCRIPTS))

import render as TYPO  # noqa: E402
import check_fit as FIT  # noqa: E402


class FrameError(Exception):
    """分镜或规格不合法。消息写给执行者看，不写给调试器看。"""


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FrameError(f"找不到文件：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FrameError(f"{path} 不是合法 JSON：{exc}") from exc


def scene_content(scene: dict, brand_footer: str) -> dict:
    """分镜的文案 → 排版引擎要的 content 字典。

    顺序即显示顺序。footer 是品牌落款，每一幕都盖同一个，
    所以写在脚本顶层而不是逐幕重复——逐幕写就会有人漏写一幕。
    """
    content = dict(scene.get("content") or {})
    if not content:
        raise FrameError(f"分镜 {scene.get('id')} 没有文案——视频帧不写字，观众在信息流里扫不到它")
    content["footer"] = brand_footer
    return content


def build(script: dict, spec: dict, out_dir: Path) -> list:
    style = script.get('style', 'typographic-cards')
    if style != 'typographic-cards':
        raise FrameError(f'风格 {style!r} 未接通执行端。可运行的是 typographic-cards，不能静默替换风格')
    # 所有素材先检查，避免渲到一半才发现后面的图缺失。
    for scene in script['scenes']:
        if scene.get('background_image'):
            if not scene.get('background_rights'):
                raise FrameError(f"分镜 {scene.get('id')} 底图缺少权利登记 background_rights")
            if not Path(scene['background_image']).is_file():
                raise FrameError(f"分镜 {scene.get('id')} 底图不存在：{scene['background_image']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    brand = script.get("brand_footer", "")
    target = script["target"]
    width, height = int(target["width"]), int(target["height"])

    # 画布尺寸以脚本为准。规格里写死了别的尺寸时，这里会把它改掉——
    # 两份都写尺寸就会出现「规格说 1080×1440、脚本说 9:16」这种漂移。
    canvas = spec["canvas"]
    if (canvas["width"], canvas["height"]) != (width, height):
        canvas["width"], canvas["height"] = width, height

    written = []
    for index, scene in enumerate(script["scenes"], 1):
        scene_id = scene.get("id") or f"scene-{index:02d}"
        content = scene_content(scene, brand)

        # 先量合身，再渲染。放不下的一行会折成孤字，机器不报错——
        # 2026-10-10 就是这样出了一帧「或者遇到敏感问」+「题，」。
        scene_spec = copy.deepcopy(spec)
        if scene.get('background_image'):
            scene_spec['canvas']['background_image'] = Path(scene['background_image']).resolve().as_uri()
            scene_spec['canvas']['scrim'] = scene.get('scrim', 'linear-gradient(0deg, rgba(250,248,243,.96), rgba(250,248,243,.75))')
        problems = FIT.check_content(scene_spec, content, f"[{scene_id}]")
        if problems:
            raise FrameError("分镜文案放不下：\n  - " + "\n  - ".join(problems))

        html = TYPO.render_cover(scene_spec, content)
        html_path = out_dir / f"{index:02d}-{scene_id}.html"
        png_path = out_dir / f"{index:02d}-{scene_id}.png"
        html_path.write_text(html, encoding="utf-8")
        TYPO.render_png(html_path, png_path, width, height)
        written.append(png_path)
        print(f"  {png_path.name}")
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把视频分镜排成 PNG 帧")
    parser.add_argument("--script", required=True, help="视频脚本 JSON（含 scenes）")
    parser.add_argument("--spec", required=True, help="排版规格 JSON（TypeSpec）")
    parser.add_argument("--out", required=True, help="帧输出目录")
    args = parser.parse_args(argv)

    try:
        script = load_json(Path(args.script))
        for scene in script.get('scenes', []):
            if scene.get('background_image'):
                scene['background_image'] = str((Path(args.script).resolve().parent / scene['background_image']).resolve())
        spec = load_json(Path(args.spec))
        frames = build(script, spec, Path(args.out))
    except FrameError as exc:
        print(f"排版失败：{exc}", file=sys.stderr)
        return 1
    except TYPO.RenderError as exc:
        print(f"排版失败：{exc}", file=sys.stderr)
        return 1

    print(f"共 {len(frames)} 帧，已写入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
