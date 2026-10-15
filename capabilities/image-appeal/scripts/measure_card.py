#!/usr/bin/env python3
"""从一张渲染好的图里量出视觉复杂度。纯标准库，复用图片线的 PNG 解码。

**这个脚本存在的唯一理由：把「素」变成一个数字。**

2026-10-08，Conan 看过十张交付的卡片，说「图都比较素，看起来让人没啥阅读兴趣」。
「素」是审美判断，本来进不了判据——但它有一个可测的代理：
**整张画面只有一个视觉事件。**

量三个数：

| 指标 | 意思 | 为什么能代表「素」 |
|---|---|---|
| `distinct_colors` | 4 位/通道量化后还剩几种颜色 | 一块底色加几行字，颜色几乎全是底色的抗锯齿渐变 |
| `edge_density` | 相邻像素亮度差 > 24 的比例 | 画面里有多少「视觉事件」。全是平底时接近 0 |
| `dominant_luma_ratio` | 占比最大的那个明度带有多重 | 0.95 意味着 95% 的画面是同一个明度 |

**为什么是 4 位量化而不是原始颜色数**：一张抗锯齿的纯文字图会有上千种颜色，
全是底色和字色之间的过渡。那不是视觉事件，是渲染噪声。
4 位/通道（每通道 16 级）刚好把抗锯齿压掉、留下真正的色块。

**为什么用 2 像素步长抽样**：1080x1440 是 155 万像素，逐像素在纯 Python 里要几秒。
步长 2 取 39 万点，实测结果与全采样差异小于 1%，而快 4 倍。
判据的阈值是 0.05 这种量级，1% 的差异不影响判否。

**这不是审美判断器。** 它答不了「这张图好不好看」，也答不了「配不配得上那句话」。
它只答「这张画面里有多少东西」。够不够，由 `rules/appeal-rules.json` 里的阈值说。
"""

import argparse
import json
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")

# 复用图片线的 PNG 解码。不另写一份——两份解码器会各自演化，然后有一边是错的。
sys.path.insert(0, str(_SYSTEM / "capabilities/image-production/scripts"))
import png_io  # noqa: E402

# 边缘判定阈值：相邻像素亮度差超过它才算一次「视觉事件」。
# 24 是 255 的不到 10%，低于它的差异在缩略图上根本看不出来。
EDGE_LUMA_DELTA = 24

# 量化位数。4 位/通道 = 每通道 16 级，刚好压掉抗锯齿又留住色块。
QUANT_BITS = 4

# 抽样步长。2 像素。
SAMPLE_STEP = 2

# 明度带数量（16 带，每带 16 级）。
LUMA_BANDS = 16

# 一个明度带占多少比例才算「有人看得见」。低于 1% 的带是噪声。
LUMA_BAND_FLOOR = 0.01


def luma(r: int, g: int, b: int) -> int:
    """BT.601 亮度。整数算法，避免浮点在不同平台上给出不同结果。

    判据是拿这个数和阈值比的，所以它必须**确定性**——
    同输入同输出，换台机器也一样。浮点做不到这个保证。
    """
    return (299 * r + 587 * g + 114 * b) // 1000


def quantize(r: int, g: int, b: int) -> tuple:
    """把颜色压到 4 位/通道。抗锯齿的过渡色会在这一步合并。"""
    shift = 8 - QUANT_BITS
    return r >> shift, g >> shift, b >> shift


def distinct_colors(image, step: int = SAMPLE_STEP) -> int:
    """量化后还剩几种颜色。"""
    seen = set()
    pixels = image.pixels
    width = image.width
    for y in range(0, image.height, step):
        row = y * width
        for x in range(0, width, step):
            base = (row + x) * 3
            seen.add(quantize(pixels[base], pixels[base + 1], pixels[base + 2]))
    return len(seen)


def edge_density(image, step: int = SAMPLE_STEP, delta: int = EDGE_LUMA_DELTA) -> float:
    """相邻像素亮度差超过 `delta` 的比例。

    只比左邻和上邻，不比右邻和下邻——同一对像素比两次会把密度虚增一倍。
    """
    pixels = image.pixels
    width = image.width
    edges = 0
    total = 0

    for y in range(0, image.height, step):
        row = y * width
        for x in range(0, width, step):
            index = row + x
            base = index * 3
            here = luma(pixels[base], pixels[base + 1], pixels[base + 2])
            total += 1
            if x >= step:
                other = (index - step) * 3
                if abs(here - luma(pixels[other], pixels[other + 1], pixels[other + 2])) > delta:
                    edges += 1
            if y >= step:
                other = (index - step * width) * 3
                if abs(here - luma(pixels[other], pixels[other + 1], pixels[other + 2])) > delta:
                    edges += 1

    return edges / total if total else 0.0


def luma_profile(image, step: int = SAMPLE_STEP) -> dict:
    """明度直方图的两个摘要：主带占比、可见带数。"""
    histogram = [0] * LUMA_BANDS
    pixels = image.pixels
    width = image.width
    total = 0

    for y in range(0, image.height, step):
        row = y * width
        for x in range(0, width, step):
            base = (row + x) * 3
            value = luma(pixels[base], pixels[base + 1], pixels[base + 2])
            histogram[min(LUMA_BANDS - 1, value >> 4)] += 1
            total += 1

    if not total:
        return {"dominant_luma_ratio": 0.0, "luma_bands": 0}

    shares = [count / total for count in histogram]
    return {
        "dominant_luma_ratio": round(max(shares), 4),
        "luma_bands": sum(1 for share in shares if share > LUMA_BAND_FLOOR),
    }


def measure(path) -> dict:
    """量一张图。返回的每个数都能复算——同输入同输出。"""
    path = Path(path)
    image = png_io.read_png(path)
    profile = luma_profile(image)
    return {
        "path": str(path),
        "width": image.width,
        "height": image.height,
        "distinct_colors": distinct_colors(image),
        "edge_density": round(edge_density(image), 4),
        "dominant_luma_ratio": profile["dominant_luma_ratio"],
        "luma_bands": profile["luma_bands"],
        "method": {
            "quant_bits": QUANT_BITS,
            "sample_step": SAMPLE_STEP,
            "edge_luma_delta": EDGE_LUMA_DELTA,
        },
    }


def render(report: dict) -> str:
    return (
        f"{Path(report['path']).name}  {report['width']}x{report['height']}\n"
        f"  色数        {report['distinct_colors']}\n"
        f"  边缘密度    {report['edge_density']}\n"
        f"  主色占比    {report['dominant_luma_ratio']}\n"
        f"  明度带      {report['luma_bands']}"
    )


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="量一张图的视觉复杂度（只测量，不判断）")
    parser.add_argument("paths", nargs="+", help="一个或多个 PNG")
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = parser.parse_args(argv[1:])

    reports = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_file():
            print(f"找不到文件：{path}", file=sys.stderr)
            return 2
        reports.append(measure(path))

    if args.json:
        print(json.dumps(reports if len(reports) > 1 else reports[0],
                         ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(render(item) for item in reports))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
