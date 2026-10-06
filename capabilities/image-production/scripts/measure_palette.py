#!/usr/bin/env python3
"""从参考图里量出配色。**只测量，不判断。**

这个脚本存在的理由是：**用户说不清自己喜欢的风格，但能给出图。**
隐性知识靠例子传递，不靠描述——所以系统要能从例子里把色板量出来，
而且量出来的必须是**确定性的数字**，不能是某次模型输出的一段话。

一次测量，两个下游都直接吃（见 PRD §3.1a）：

- DashScope `image-generation` 的 `color_palette` 参数（`hex` + `ratio`）
- `styles/image-styles.json` 的 `tokens.palette`（`role` + `hex` + `oklch`）

中间没有转译步骤——转译就是信息损失。

**它刻意不做的事**：不判断「这套配色好不好」，不写进风格库，不给建议。
拿这个 pattern 怎么办是判断，归人和 Agent（宪法 7）。

> **`hex` / `oklch` / `coverage` 是精确测量；`role` 是启发式猜测。**
> 这两者必须分开看。一张纯蓝渐变的图里没有任何文字色，脚本仍然会按
> 「与背景明度差最大」把某个蓝标成 `text`——**标签是猜的，颜色不是**。
> 所以 role 用来让色板可读，不能当成「这张图里真的有这六种角色」的证据。

算法（PRD §3.3）：
  像素 → 5bit/通道量化成桶（累计桶内 RGB 均值与计数）
       → 在桶上跑加权 k-means（距离在 OKLab 里算，中心存 RGB）
       → 按 ΔE00 合并近似中心
       → 按覆盖率与明暗彩度分配 role

**距离在 OKLab 里算**是为了感知均匀——在 sRGB 里算距离会让亮区压过暗区，
这是 k-means 做配色时最常见的错。**中心存 RGB** 是因为加权平均后能直接出 hex，
省掉 OKLab→sRGB 的逆变换，也少一层误差。

用法：

    python3 measure_palette.py 参考图.png
    python3 measure_palette.py 图1.png 图2.jpg -n 6 -o palette.json
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import png_io
from color_math import (
    delta_e_hex,
    format_oklch,
    hex_to_rgb,
    oklab_to_oklch,
    rgb_to_hex,
    srgb_to_oklab,
)

SCHEMA_VERSION = 1

# 采样上限。跨步采样而不是截断前 N 个——截断会让统计偏向画面左上角。
SAMPLE_CAP = 240_000

# alpha 低于这个值的像素没有颜色，不参与统计。
ALPHA_MIN = 16

# 每通道量化位数。5 bit → 32768 个桶，足够细又不至于桶数爆炸。
QUANT_BITS = 5
_QUANT_SHIFT = 8 - QUANT_BITS

# 合并阈值。ΔE00 < 2.5 的两个中心肉眼几乎分不出，留着会让色板虚高。
MERGE_DELTA_E = 2.5

# 初始化时排除「太小」的桶，避免孤立噪点被选成聚类中心。
_SEED_MIN_SHARE = 0.0005

# 稳定性归零的色差尺度：一对颜色差到 ΔE00 = 20，就已经不是同一个颜色了。
_STABILITY_SCALE = 20.0

# 角色分配优先级。前面几个比后面几个重要，颜色不够时先保它们。
_ROLE_ORDER = ("background", "text", "primary", "accent", "muted", "surface")

_DEFAULT_COLORS = 6


class MeasureError(Exception):
    """量不出来时抛这个。消息要说清是哪一步、下一步怎么办。"""


# --- 载入 ------------------------------------------------------------------

def load_image(path):
    """读图。PNG 自己解，其他格式借 macOS 的 `sips` 转一道。"""
    path = Path(path)
    if not path.exists():
        raise MeasureError(f"找不到文件：{path}")

    if path.suffix.lower() == ".png":
        return png_io.read_png(path)

    sips = shutil.which("sips")
    if sips is None:
        raise MeasureError(
            f"{path.name} 不是 PNG，而本机没有 `sips` 可以转换。"
            "请先把图转成 PNG 再试。"
        )

    with tempfile.TemporaryDirectory() as workdir:
        converted = Path(workdir) / (path.stem + ".png")
        result = subprocess.run(
            [sips, "-s", "format", "png", str(path), "--out", str(converted)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not converted.exists():
            reason = (result.stderr or result.stdout or "").strip().splitlines()
            raise MeasureError(
                f"`sips` 转换 {path.name} 失败"
                f"{'：' + reason[-1] if reason else ''}。请手动转成 PNG 再试。"
            )
        return png_io.read_png(converted)


# --- 直方图 ----------------------------------------------------------------

def build_buckets(image, sample_cap=SAMPLE_CAP, alpha_min=ALPHA_MIN):
    """把像素量化进桶，每桶累积 (sum_r, sum_g, sum_b, count)。

    **存的是桶内像素的 RGB 之和，不是桶的中心坐标。** 区别很要紧：
    存中心坐标的话，最终得到的颜色是「量化格子的中心」，是近似值；
    存和的话，最终得到的是**真实像素的加权平均**，量化只影响聚类的分组，
    不影响颜色值本身。这是这套算法精度不掉的原因。
    """
    total = image.width * image.height
    stride = max(1, (total + sample_cap - 1) // sample_cap)
    pixels = image.pixels
    alpha = image.alpha

    buckets = {}
    sampled = 0
    for index in range(0, total, stride):
        if alpha[index] < alpha_min:
            continue
        base = index * 3
        red = pixels[base]
        green = pixels[base + 1]
        blue = pixels[base + 2]
        key = (
            (red >> _QUANT_SHIFT) << (2 * QUANT_BITS)
            | (green >> _QUANT_SHIFT) << QUANT_BITS
            | (blue >> _QUANT_SHIFT)
        )
        entry = buckets.get(key)
        if entry is None:
            buckets[key] = [red, green, blue, 1]
        else:
            entry[0] += red
            entry[1] += green
            entry[2] += blue
            entry[3] += 1
        sampled += 1

    if sampled == 0:
        raise MeasureError(
            "这张图里没有不透明像素可测（全是透明的）。换一张图，"
            "或把透明背景先合成到纯色上。"
        )

    points = []
    for red_sum, green_sum, blue_sum, count in buckets.values():
        red = red_sum / count
        green = green_sum / count
        blue = blue_sum / count
        points.append((red, green, blue, count, srgb_to_oklab(round(red), round(green), round(blue))))

    # 桶的遍历顺序取决于 dict 的插入顺序，本身是确定的；按颜色再排一次，
    # 是为了让输出与「像素扫描顺序」彻底解耦，同色图必得同结果。
    points.sort(key=lambda point: (point[0], point[1], point[2]))
    return points, sampled


# --- 聚类 ------------------------------------------------------------------

def _distance_sq(lab_a, lab_b):
    """OKLab 里的平方欧氏距离。开方只在需要真距离时才做。"""
    dl = lab_a[0] - lab_b[0]
    da = lab_a[1] - lab_b[1]
    db = lab_a[2] - lab_b[2]
    return dl * dl + da * da + db * db


def _seed_centers(points, k):
    """确定性最远点初始化。**不用随机数**——同输入必须同输出，测试才能断言确切值。

    第一颗种子取**最暗的桶**（OKLab 的 L 最小），因为背景/文字的明暗骨架
    通常比某个强调色更能锚定整张图。之后每次加「离已有中心最远」的桶。
    """
    total = sum(point[3] for point in points)
    floor = max(1, round(total * _SEED_MIN_SHARE))
    eligible = [point for point in points if point[3] >= floor] or points

    first = min(eligible, key=lambda point: (point[4][0], point[0], point[1], point[2]))
    centers = [(first[0], first[1], first[2], first[4])]

    while len(centers) < k:
        best = None
        best_distance = -1.0
        for point in eligible:
            nearest = min(_distance_sq(point[4], center[3]) for center in centers)
            if nearest > best_distance:
                best_distance = nearest
                best = point
        if best is None or best_distance <= 0:
            break
        centers.append((best[0], best[1], best[2], best[4]))

    return centers


def kmeans(points, k, max_iterations=24):
    """在桶上跑加权 k-means。返回 [(r, g, b, count)]，按 count 降序。

    迭代成本是「桶数 × k」而不是「像素数 × k」。一张 12MP 的图采样后
    通常只剩几千个非空桶，比逐像素快两个数量级。
    """
    if not points:
        return []
    k = min(k, len(points))
    centers = _seed_centers(points, k)

    assignments = [-1] * len(points)
    for _ in range(max_iterations):
        changed = False
        for index, point in enumerate(points):
            lab = point[4]
            nearest = 0
            nearest_distance = _distance_sq(lab, centers[0][3])
            for slot in range(1, len(centers)):
                distance = _distance_sq(lab, centers[slot][3])
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest = slot
            if assignments[index] != nearest:
                assignments[index] = nearest
                changed = True

        sums = [[0.0, 0.0, 0.0, 0] for _ in centers]
        for index, point in enumerate(points):
            slot = assignments[index]
            bucket = sums[slot]
            weight = point[3]
            bucket[0] += point[0] * weight
            bucket[1] += point[1] * weight
            bucket[2] += point[2] * weight
            bucket[3] += weight

        moved = 0.0
        for slot, bucket in enumerate(sums):
            if bucket[3] == 0:
                continue
            red = bucket[0] / bucket[3]
            green = bucket[1] / bucket[3]
            blue = bucket[2] / bucket[3]
            lab = srgb_to_oklab(round(red), round(green), round(blue))
            moved = max(moved, _distance_sq(centers[slot][3], lab))
            centers[slot] = (red, green, blue, lab)

        if not changed or moved < 1e-10:
            break

    final = [[0.0, 0.0, 0.0, 0] for _ in centers]
    for index, point in enumerate(points):
        slot = assignments[index]
        if slot < 0:
            continue
        bucket = final[slot]
        weight = point[3]
        bucket[0] += point[0] * weight
        bucket[1] += point[1] * weight
        bucket[2] += point[2] * weight
        bucket[3] += weight

    result = []
    for bucket in final:
        if bucket[3] == 0:
            continue
        result.append((bucket[0] / bucket[3], bucket[1] / bucket[3], bucket[2] / bucket[3], bucket[3]))
    result.sort(key=lambda item: (-item[3], item[0], item[1], item[2]))
    return result


def merge_similar(centers, threshold=MERGE_DELTA_E):
    """把 ΔE00 小于阈值的中心合并掉。

    不合并的话，一张有渐变或者有压缩噪声的图会量出好几个「几乎一样」的颜色，
    色板看着有六个其实只有三个——那是**看起来更丰富，实际上更不准**。
    """
    clusters = [
        {"red": red, "green": green, "blue": blue, "count": count, "hex": rgb_to_hex((red, green, blue))}
        for red, green, blue, count in centers
    ]

    while True:
        best_pair = None
        best_distance = threshold
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                distance = delta_e_hex(clusters[i]["hex"], clusters[j]["hex"])
                if distance < best_distance:
                    best_distance = distance
                    best_pair = (i, j)

        if best_pair is None:
            break

        i, j = best_pair
        left, right = clusters[i], clusters[j]
        count = left["count"] + right["count"]
        merged = {
            "red": (left["red"] * left["count"] + right["red"] * right["count"]) / count,
            "green": (left["green"] * left["count"] + right["green"] * right["count"]) / count,
            "blue": (left["blue"] * left["count"] + right["blue"] * right["count"]) / count,
            "count": count,
        }
        merged["hex"] = rgb_to_hex((merged["red"], merged["green"], merged["blue"]))
        clusters = [item for index, item in enumerate(clusters) if index not in (i, j)]
        clusters.append(merged)

    clusters.sort(key=lambda item: (-item["count"], item["hex"]))
    return clusters


# --- 角色判定 --------------------------------------------------------------

def assign_roles(clusters):
    """按覆盖率与明暗彩度给颜色贴 role。

    规则是可解释的，不是学出来的——**任何一条都要能指着说为什么**：

    | role | 判据 |
    |---|---|
    | `background` | 覆盖率最高 |
    | `text` | 与背景明度差 |ΔL| 最大（对比度就是文字可读性） |
    | `primary` | 剩下的里面彩度最高 |
    | `accent` | 再剩下的里面彩度最高 |
    | `muted` | 剩下的里面彩度最低 |
    | `surface` | 剩下的里面明度最接近背景 |

    颜色不够六个时**从后往前砍**（`_ROLE_ORDER` 的逆序）——
    `background`/`text`/`primary` 是骨架，先保住。
    """
    if not clusters:
        return []

    total = sum(cluster["count"] for cluster in clusters)
    remaining = list(clusters)
    chosen = {}

    def take(role, key):
        if not remaining:
            return
        pick = min(remaining, key=key)
        remaining.remove(pick)
        chosen[role] = pick

    take("background", lambda cluster: (-cluster["count"], cluster["hex"]))

    background_lab = srgb_to_oklab(*hex_to_rgb(chosen["background"]["hex"]))

    def lightness_gap(cluster):
        """与背景的 OKLab 明度差，**正值**。取最小/最大由调用方加符号决定。"""
        return abs(srgb_to_oklab(*hex_to_rgb(cluster["hex"]))[0] - background_lab[0])

    def chroma(cluster):
        lab = srgb_to_oklab(*hex_to_rgb(cluster["hex"]))
        return math.hypot(lab[1], lab[2])

    # `take` 取的是 min，所以「要最大」的判据前面加负号。
    take("text", lambda cluster: (-lightness_gap(cluster), chroma(cluster), cluster["hex"]))
    take("primary", lambda cluster: (-chroma(cluster), cluster["hex"]))
    take("accent", lambda cluster: (-chroma(cluster), cluster["hex"]))
    take("muted", lambda cluster: (chroma(cluster), cluster["hex"]))
    take("surface", lambda cluster: (lightness_gap(cluster), -cluster["count"], cluster["hex"]))

    ordered = []
    for role in _ROLE_ORDER:
        cluster = chosen.get(role)
        if cluster is None:
            continue
        coverage = cluster["count"] / total if total else 0.0
        ordered.append(
            {
                "role": role,
                "hex": cluster["hex"],
                "oklch": format_oklch(oklab_to_oklch(srgb_to_oklab(*hex_to_rgb(cluster["hex"])))),
                "coverage": round(coverage, 6),
                "ratio": _format_ratio(coverage),
                "pixels": cluster["count"],
            }
        )
    return ordered


def _format_ratio(coverage):
    """覆盖率转成 DashScope 要的百分比字符串，如 `"41.23%"`。"""
    return f"{coverage * 100:.2f}%"


# --- 多图共识 --------------------------------------------------------------

def consensus(per_image, roles=None):
    """跨图求每个 role 的稳定程度。

    **稳定的维度才是 pattern，不稳定的不是。**「8 张图里背景明度都在
    0.95–0.98」是 pattern；「强调色从橙到蓝都有」不是。这个函数只做这一件
    可计算的事，剩下的判断归人。

    代表色取**中心点（medoid）**——离其他各图该 role 颜色距离之和最小的那一个。
    不取平均，因为色相是环形的，橙（30°）和蓝（220°）平均出来是青（125°），
    一个谁都没用过的颜色。取实际存在的那一个才不会凭空造色。
    """
    roles = roles or _ROLE_ORDER
    entries = []
    for role in roles:
        samples = []
        for image in per_image:
            for item in image["palette"]:
                if item["role"] == role:
                    samples.append(item)
                    break
        if not samples:
            continue

        if len(samples) == 1:
            spread = 0.0
        else:
            spread = max(
                delta_e_hex(left["hex"], right["hex"])
                for index, left in enumerate(samples)
                for right in samples[index + 1:]
            )

        def total_distance(candidate):
            return sum(delta_e_hex(candidate["hex"], other["hex"]) for other in samples)

        medoid = min(samples, key=lambda item: (round(total_distance(item), 6), item["hex"]))
        stability = max(0.0, min(1.0, 1 - spread / _STABILITY_SCALE))

        entries.append(
            {
                "role": role,
                "hex": medoid["hex"],
                "oklch": medoid["oklch"],
                "stability": round(stability, 4),
                "spread_delta_e": round(spread, 2),
                "images_present": len(samples),
                "mean_coverage": round(sum(item["coverage"] for item in samples) / len(samples), 6),
            }
        )
    return entries


def dashscope_palette(entries, limit=10):
    """把共识色板转成 DashScope `color_palette` 参数。

    API 有两条硬约束，这里必须自己保证：**颜色数 3–10，比例合计恰好 100.00%**。
    比例用**最大余数法**分配，而不是各自四舍五入——各自round会得到 99.99%
    或 100.01%，是那种「偶尔失败、看着像玄学」的问题。
    """
    if not entries or len(entries) < 3:
        return None

    chosen = sorted(entries, key=lambda item: (-item["mean_coverage"], item["role"]))[:limit]
    weights = [item["mean_coverage"] for item in chosen]
    hundredths = _largest_remainder(weights, 10000)

    return [
        {"hex": item["hex"], "ratio": f"{value / 100:.2f}%"}
        for item, value in zip(chosen, hundredths)
    ]


def _largest_remainder(weights, total_units):
    """按权重把 `total_units` 个单位整分下去，合计精确等于 `total_units`。"""
    if not weights:
        return []

    total = sum(weights)
    if total <= 0:  # 权重全零时退化成均分，不能递归回自己（空表会无限递归）
        weights = [1] * len(weights)
        total = len(weights)

    exact = [weight / total * total_units for weight in weights]
    floors = [int(math.floor(value)) for value in exact]
    remainder = total_units - sum(floors)
    order = sorted(
        range(len(weights)),
        key=lambda index: (-(exact[index] - floors[index]), index),
    )
    for index in order[:remainder]:
        floors[index] += 1
    return floors


# --- 对外主函数 ------------------------------------------------------------

def measure_image(path, colors=_DEFAULT_COLORS):
    """量一张图，返回可直接落盘的一段结果。"""
    image = load_image(path)
    points, sampled = build_buckets(image)
    centers = kmeans(points, colors)
    clusters = merge_similar(centers)
    palette = assign_roles(clusters)
    return {
        "source": str(path),
        "width": image.width,
        "height": image.height,
        "sampled_pixels": sampled,
        "unique_buckets": len(points),
        "palette": palette,
    }


def measure(paths, colors=_DEFAULT_COLORS):
    """量一批图，返回完整结果。**输出里没有时间戳**——同输入必须同字节，
    不然做不了黄金文件回归，也没法用差异对比判断「是不是真变了」。"""
    per_image = [measure_image(path, colors) for path in paths]
    shared = consensus(per_image)
    return {
        "schema_version": SCHEMA_VERSION,
        "colors_requested": colors,
        "sample_cap": SAMPLE_CAP,
        "merge_delta_e": MERGE_DELTA_E,
        "per_image": per_image,
        "consensus": shared,
        "dashscope_color_palette": dashscope_palette(shared),
    }


# --- 命令行 ----------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="从参考图里量出配色。只测量，不判断，不写风格库。"
    )
    parser.add_argument("images", nargs="+", help="一张或多张参考图")
    parser.add_argument("-n", "--colors", type=int, default=_DEFAULT_COLORS,
                        help=f"要量出几种颜色（默认 {_DEFAULT_COLORS}）")
    parser.add_argument("-o", "--out", help="结果写到这个 JSON 文件；不给就打印到屏幕")
    args = parser.parse_args(argv)

    if args.colors < 1:
        print("--colors 至少要 1", file=sys.stderr)
        return 2

    try:
        result = measure(args.images, args.colors)
    except (MeasureError, png_io.PngError) as error:
        print(f"量不出来：{error}", file=sys.stderr)
        return 1

    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写入 {args.out}")
        for item in result["consensus"]:
            print(f"  {item['role']:11s} {item['hex']}  稳定度 {item['stability']:.2f}  "
                  f"（{item['images_present']} 张图）")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
