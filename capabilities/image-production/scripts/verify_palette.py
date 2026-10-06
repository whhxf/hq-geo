#!/usr/bin/env python3
"""回测：把出出来的图重量一遍，跟预期色板比。

**这是整条链上唯一一个能机器判否的环节。** 站 5 的「像不像」本来只有人看，
不可重复、不可回归，出十次图人就要看十次。回测把其中**可计算的那一半**
——颜色和面积——拿出来自动判，人只需要看剩下那一半（配不配得上那句话）。

**它测不了什么**：测不出「这张图配不配得上那句话」，也测不出构图、质感、
有没有混进不该有的东西。那些仍然归人。回测通过不等于可以发。

匹配方式是**最近色**而不是 role 对 role。原因是 role 是启发式标签
（见 `measure_palette.py` 的说明），同一套配色在参考图和生成图里可能被
贴上不同的 role。逐 role 比会把「标签变了」误报成「颜色漂了」，
而颜色其实没变——那是假警报，假警报多了就没人看结果了。

用法：

    python3 verify_palette.py --expected palette.json --actual 生成图.png
    python3 verify_palette.py --expected palette.json --actual 图.png --max-delta-e 8
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import png_io
from color_math import delta_e_hex
from measure_palette import MeasureError, measure

SCHEMA_VERSION = 1

# 阈值**尚未用真实出图校准**，是起点值（见 PRD §8.1）。
# 在跑够 3–5 次真实出图之前，回测只能说「偏得离谱」和「看着还行」，
# 不能说「合格」。所以输出里带着 `thresholds_calibrated: false`。
DEFAULT_MAX_DELTA_E = 10.0
# 10 的来源是 CIE 的经验刻度：ΔE00 > 10 时两个颜色「几乎不是同一个颜色」。
DEFAULT_MAX_COVERAGE_DELTA = 0.20


class VerifyError(Exception):
    """输入不对时抛这个。"""


def load_expected(path):
    """读预期色板。兼容 `measure_palette.py` 的输出，也接受裸色板列表。

    单张参考图时用 `per_image[0].palette`——那是真实的面积占比；
    多张参考图时用 `consensus`，它的 `mean_coverage` 才是和生成图可比的口径。
    """
    path = Path(path)
    if not path.exists():
        raise VerifyError(f"找不到预期色板文件：{path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerifyError(f"预期色板不是合法 JSON：{path}（{error}）") from error

    if isinstance(data, list):
        palette = data
    elif isinstance(data, dict):
        per_image = data.get("per_image") or []
        if len(per_image) == 1:
            palette = per_image[0].get("palette") or []
        else:
            palette = data.get("consensus") or (per_image[0].get("palette") if per_image else [])
    else:
        raise VerifyError(f"预期色板的结构不认识：{path}")

    if not palette:
        raise VerifyError(f"预期色板是空的：{path}")

    entries = []
    for item in palette:
        if "hex" not in item:
            raise VerifyError(f"预期色板里有条目缺少 `hex` 字段：{item!r}")
        coverage = item.get("coverage", item.get("mean_coverage"))
        if coverage is None:
            raise VerifyError(f"预期色板里有条目缺少覆盖率：{item!r}")
        entries.append(
            {
                "role": item.get("role", ""),
                "hex": item["hex"],
                "coverage": float(coverage),
            }
        )
    return entries


def verify(expected, actual, max_delta_e=DEFAULT_MAX_DELTA_E,
           max_coverage_delta=DEFAULT_MAX_COVERAGE_DELTA):
    """逐个预期色找生成图里最近的那个，比色差和面积差。

    贪心匹配，按覆盖率从大到小走。颜色数不超过十个，贪心和最优分配的差别
    可以忽略，而贪心的好处是**行为可预测、顺序确定**。
    """
    unused = list(actual)
    rows = []
    failures = []

    for item in sorted(expected, key=lambda entry: (-entry["coverage"], entry["hex"])):
        if unused:
            match = min(unused, key=lambda candidate: (delta_e_hex(item["hex"], candidate["hex"]),
                                                       candidate["hex"]))
            unused.remove(match)
            difference = delta_e_hex(item["hex"], match["hex"])
            coverage_delta = abs(item["coverage"] - match["coverage"])
        else:
            match = None
            difference = None
            coverage_delta = None

        row = {
            "role": item["role"],
            "expected_hex": item["hex"],
            "expected_coverage": round(item["coverage"], 6),
            "matched_hex": match["hex"] if match else None,
            "matched_role": match["role"] if match else None,
            "delta_e": round(difference, 2) if difference is not None else None,
            "coverage_delta": round(coverage_delta, 6) if coverage_delta is not None else None,
        }

        if match is None:
            row["note"] = "生成图里没有足够多的颜色可以匹配"
            failures.append(f"{item['role'] or item['hex']}：生成图里找不到对应颜色")
        else:
            if difference > max_delta_e:
                failures.append(
                    f"{item['role'] or item['hex']}：{item['hex']} 变成了 {match['hex']}，"
                    f"色差 ΔE00 {difference:.1f} 超过阈值 {max_delta_e}"
                )
            if coverage_delta > max_coverage_delta:
                failures.append(
                    f"{item['role'] or item['hex']}：面积占比从 "
                    f"{item['coverage'] * 100:.1f}% 变成 {match['coverage'] * 100:.1f}%，"
                    f"差 {coverage_delta * 100:.1f} 个百分点，超过阈值 {max_coverage_delta * 100:.0f}"
                )
        rows.append(row)

    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": "FAIL" if failures else "PASS",
        "thresholds": {
            "max_delta_e": max_delta_e,
            "max_coverage_delta": max_coverage_delta,
            "calibrated": False,
        },
        "rows": rows,
        "failures": failures,
        "unmatched_actual": [
            {"role": item["role"], "hex": item["hex"], "coverage": round(item["coverage"], 6)}
            for item in unused
        ],
    }


def run(expected_path, actual_path, max_delta_e=DEFAULT_MAX_DELTA_E,
        max_coverage_delta=DEFAULT_MAX_COVERAGE_DELTA):
    """从两个文件路径跑到结论。CLI 和测试都走这里。"""
    expected = load_expected(expected_path)
    actual_result = measure([actual_path])
    actual = actual_result["per_image"][0]["palette"]
    report = verify(expected, actual, max_delta_e, max_coverage_delta)
    report["expected_source"] = str(expected_path)
    report["actual_source"] = str(actual_path)
    report["actual_image"] = {
        "width": actual_result["per_image"][0]["width"],
        "height": actual_result["per_image"][0]["height"],
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="回测：把生成图的配色跟预期色板比。只测颜色和面积，不测「像不像」。"
    )
    parser.add_argument("--expected", required=True, help="预期色板 JSON（measure_palette.py 的输出）")
    parser.add_argument("--actual", required=True, help="要回测的图")
    parser.add_argument("--max-delta-e", type=float, default=DEFAULT_MAX_DELTA_E,
                        help=f"单色最大允许色差 ΔE00（默认 {DEFAULT_MAX_DELTA_E}，未校准）")
    parser.add_argument("--max-coverage-delta", type=float, default=DEFAULT_MAX_COVERAGE_DELTA,
                        help=f"单色最大允许面积占比差（默认 {DEFAULT_MAX_COVERAGE_DELTA}，未校准）")
    parser.add_argument("-o", "--out", help="结果写到这个 JSON 文件；不给就打印到屏幕")
    args = parser.parse_args(argv)

    try:
        report = run(args.expected, args.actual, args.max_delta_e, args.max_coverage_delta)
    except (VerifyError, MeasureError, png_io.PngError) as error:
        print(f"测不了：{error}", file=sys.stderr)
        return 2

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写入 {args.out}")

    print(f"{report['verdict']}  {Path(args.actual).name}")
    for row in report["rows"]:
        if row["delta_e"] is None:
            print(f"  {row['role']:11s} {row['expected_hex']} → 无匹配")
        else:
            print(f"  {row['role']:11s} {row['expected_hex']} → {row['matched_hex']}  "
                  f"ΔE {row['delta_e']:6.2f}  面积差 {row['coverage_delta'] * 100:5.1f}pt")
    for note in report["failures"]:
        print(f"  ! {note}")
    print("  注：阈值尚未用真实出图校准（thresholds.calibrated = false），"
          "PASS 目前只能说明「没偏得离谱」。")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
