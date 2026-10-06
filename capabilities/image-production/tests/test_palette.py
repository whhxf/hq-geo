#!/usr/bin/env python3
"""配色测量、回测与参考吸收的单元测试。

覆盖 PRD §6.1 的四行自动回归：

| 被测 | 断言 |
|---|---|
| 颜色数学 | oklch 格式规则；ΔE00 对标准向量；ΔE76 与 ΔE00 不等价 |
| PNG 解码 | 颜色类型 0/2/3/4/6 与位深 1/2/4/8/16 都能读对；隔行明确报错 |
| 配色测量 | 同输入同字节；比例精确合计 100.00%；透明度被正确排除 |
| 回测 | 同图 PASS；漂移 FAIL；**role 换名不算失败** |
| 出图请求体 | 不带新参数时**逐字节等于**改造前——向后兼容 |
| 简报校验 | 四条新拦截都能红 |

**造图只用 `png_io.write_png` 和本文件里的 `_raw_png`。**
不用 PIL——那是验证阶段的一次性 oracle，交付代码和测试都不依赖它，
否则「零第三方依赖」这条就成了一句只看交付目录的谎话。
"""

import importlib.util
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "capabilities/image-production/scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


color_math = _load("color_math", SCRIPTS / "color_math.py")
png_io = _load("png_io", SCRIPTS / "png_io.py")
measure_palette = _load("measure_palette", SCRIPTS / "measure_palette.py")
verify_palette = _load("verify_palette", SCRIPTS / "verify_palette.py")
generate_image = _load("generate_image", SCRIPTS / "generate_image.py")
validate_image_brief = _load("validate_image_brief", SCRIPTS / "validate_image_brief.py")

STYLE_IDS = {"editorial-minimal", "japanese-fresh"}


# --- 造图工具 -------------------------------------------------------------

def _raw_png(width, height, depth, color_type, raw_rows, palette=None, transparency=None):
    """拼一张任意颜色类型/位深的 PNG。`raw_rows` 是每行**未加滤波字节**。"""
    body = bytearray()
    for row in raw_rows:
        body.append(0)  # 滤波类型 0
        body += row

    parts = [struct.pack(">IIBBBBB", width, height, depth, color_type, 0, 0, 0)]
    if palette is not None:
        parts.append(bytes(palette))
    if transparency is not None:
        parts.append(bytes(transparency))
    parts.append(zlib.compress(bytes(body), 9))

    names = [b"IHDR"] + [b"PLTE"] * (palette is not None) + [b"tRNS"] * (transparency is not None) + [b"IDAT"]
    out = bytearray(png_io._SIGNATURE)
    for name, payload in zip(names, parts):
        out += png_io._chunk(name, payload)
    out += png_io._chunk(b"IEND", b"")
    return bytes(out)


def _write(tmp: Path, name: str, data: bytes) -> Path:
    path = tmp / name
    path.write_bytes(data)
    return path


def _solid(tmp: Path, name: str, rgb, width=8, height=8, alpha=None) -> Path:
    pixels = bytearray(bytes(rgb) * (width * height))
    alphas = None if alpha is None else bytearray(bytes([alpha]) * (width * height))
    path = tmp / name
    png_io.write_png(path, width, height, pixels, alphas)
    return path


def _gradient(tmp: Path, name: str, stops, width=16, height=16) -> Path:
    """按 `stops` 在水平方向铺一条渐变。用来造「有多个色团」的可测图。"""
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            t = x / (width - 1)
            index = min(int(t * (len(stops) - 1)), len(stops) - 2)
            local = t * (len(stops) - 1) - index
            a, b = stops[index], stops[index + 1]
            pixels += bytes(
                round(a[channel] + (b[channel] - a[channel]) * local) for channel in range(3)
            )
    path = tmp / name
    png_io.write_png(path, width, height, pixels)
    return path


def _blocks(tmp: Path, name: str, colors, width=24, height=8) -> Path:
    """等面积纯色块。

    跨图共识的测试要用这个而不是渐变：渐变图里每个颜色只占很窄一条，
    k-means 在不同图上会挑到不同的点，于是**同一张图量两次都能不重合**——
    那样测的是 k-means 的选点，不是共识机制。
    """
    pixels = bytearray()
    per = max(1, width // len(colors))
    for _ in range(height):
        for color in colors:
            pixels += bytes(color) * per
    path = tmp / name
    png_io.write_png(path, width, height, pixels)
    return path


# --- 颜色数学 -------------------------------------------------------------

class ColorMathTests(unittest.TestCase):
    def test_oklch_three_digits_for_lightness_and_chroma(self):
        """L 与 C 三位小数、H 一位——精度按各自量程配。

        注意 `#FFFFFF` 的 L 是 `1.000` 而不是 `1`：**补零只针对「恰为 0」**，
        非零值一律写满位数，否则 `1` 和 `1.000` 会在库里变成两种写法。
        """
        self.assertEqual(color_math.hex_to_oklch_string("#FFFFFF"), "1.000 0 0")
        self.assertRegex(color_math.hex_to_oklch_string("#FF90E8"), r"^0\.\d{3} 0\.\d{3} \d+\.\d$")

    def test_gray_has_no_hue(self):
        """彩度归零时色相未定义，必须写 0。

        这条守的是一个真实的坑：`atan2` 在 a≈b≈0 时给出的是浮点残差的
        方向，实测 `#1C1C1C` 会算出 89.9°。那是噪声不是信息——
        灰色没有色相。
        """
        for gray in ("#000000", "#1C1C1C", "#3A3A3A", "#808080", "#FFFFFF"):
            with self.subTest(gray=gray):
                self.assertTrue(color_math.hex_to_oklch_string(gray).endswith(" 0 0"),
                                color_math.hex_to_oklch_string(gray))

    def test_zero_components_are_bare_not_padded(self):
        """0.000 写成 0——风格库里 84 组数据零例外的写法。"""
        self.assertEqual(color_math.format_oklch((0.0, 0.0, 0.0)), "0 0 0")
        self.assertEqual(color_math.format_oklch((0.348, 0.260, 120.4)), "0.348 0.260 120.4")

    def test_zero_chroma_forces_hue_to_zero(self):
        """彩度归零时**色相一并写 0**，哪怕调用方传了个有意义的数字。

        没有这条，`#1C1C1C` 会带上 89.9° 这种由浮点残差编出来的色相，
        一条「灰色」在库里就成了有色相的颜色。
        """
        self.assertEqual(color_math.format_oklch((0.348, 0.0, 120.4)), "0.348 0 0")
        self.assertEqual(color_math.format_oklch((0.348, 0.0004, 120.4)), "0.348 0 0")

    def test_delta_e_2000_matches_standard_vectors(self):
        """CIEDE2000 对 Sharma 等（2005）标准向量。

        选这组是因为它专门覆盖色相均值与色相和的边界（第 9–24 行），
        那正是实现里最容易写错的分支。容差 1e-4——比任何真实用途都紧。
        """
        vectors = [
            ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
            ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
            ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
            ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
            ((50.0000, -1.1848, -84.8006), (50.0000, 0.0000, -82.7485), 1.0000),
            ((50.0000, -0.9009, -85.5211), (50.0000, 0.0000, -82.7485), 1.0000),
            ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
            ((50.0000, -1.0000, 2.0000), (50.0000, 0.0000, 0.0000), 2.3669),
            ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
            ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0010), 7.1792),
            ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0011), 7.2195),
            ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0012), 7.2195),
            ((50.0000, -0.0010, 2.4900), (50.0000, 0.0009, -2.4900), 4.8045),
            ((50.0000, -0.0010, 2.4900), (50.0000, 0.0010, -2.4900), 4.8045),
            ((50.0000, -0.0010, 2.4900), (50.0000, 0.0011, -2.4900), 4.7461),
            ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
            ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
            ((50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
            ((50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
            ((50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
            ((50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
            ((50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
            ((50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
            ((50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
            ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
            ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
            ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
            ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
            ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
            ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
            ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
            ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
            ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
            ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
        ]
        for index, (lab1, lab2, expected) in enumerate(vectors):
            with self.subTest(case=index):
                self.assertAlmostEqual(
                    color_math.delta_e_2000(lab1, lab2), expected, places=4
                )

    def test_delta_e_76_and_2000_are_different_scales(self):
        """ΔE76 与 ΔE00 **不是同一把尺**，外部阈值不能直接搬。

        `zanwei/design-dna` 记录「#ff90e8 被模型读成 #ec4899，ΔE≈29」，
        那是 ΔE76；同一对色值按 ΔE00 只有 17.0。两个都对，是度量不同。
        危害在于差值达 71%——把外部文档的阈值直接抄进本管线，
        门禁会**静默地**松掉或紧掉，不报错。
        """
        lab1 = color_math.srgb_to_cielab(*color_math.hex_to_rgb("#ff90e8"))
        lab2 = color_math.srgb_to_cielab(*color_math.hex_to_rgb("#ec4899"))
        e76 = color_math.delta_e_76(lab1, lab2)
        e00 = color_math.delta_e_2000(lab1, lab2)
        self.assertAlmostEqual(e76, 29.43, places=1)
        self.assertAlmostEqual(e00, 17.0, places=1)
        self.assertGreater(e76 / e00, 1.5)

    def test_hex_roundtrip_is_uppercase(self):
        """库里 hex 全大写。大小写不一致会让同一颜色有两种写法。"""
        self.assertEqual(color_math.rgb_to_hex((255, 144, 232)), "#FF90E8")
        self.assertEqual(color_math.hex_to_rgb("#ff90e8"), (255, 144, 232))


# --- PNG 解码 -------------------------------------------------------------

class PngDecodeTests(unittest.TestCase):
    def test_rgb_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _solid(Path(tmp), "a.png", (10, 20, 30))
            image = png_io.read_png(path)
            self.assertEqual((image.width, image.height), (8, 8))
            self.assertEqual(image.pixel(0), (10, 20, 30, 255))
            self.assertEqual(list(image.alpha), [255] * 64)

    def test_rgba_preserves_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _solid(Path(tmp), "a.png", (10, 20, 30), alpha=7)
            image = png_io.read_png(path)
            self.assertEqual(image.pixel(0), (10, 20, 30, 7))
            self.assertEqual(image.opaque_count(alpha_min=16), 0)

    def test_gray_expands_to_three_channels(self):
        """灰度只有一个采样值，展开时三通道要铺成同一个字节。

        写成 `red, green, blue = samples[:3]` 会在 1 元组上抛 ValueError——
        这是实现时真踩到的坑，所以留一条测试盯着。
        """
        raw = _raw_png(2, 1, 8, 0, [bytes([40, 200])])
        with tempfile.TemporaryDirectory() as tmp:
            image = png_io.read_png(_write(Path(tmp), "g.png", raw))
            self.assertEqual(image.pixel(0), (40, 40, 40, 255))
            self.assertEqual(image.pixel(1), (200, 200, 200, 255))

    def test_gray_alpha_splits_channels(self):
        raw = _raw_png(2, 1, 8, 4, [bytes([40, 128, 200, 64])])
        with tempfile.TemporaryDirectory() as tmp:
            image = png_io.read_png(_write(Path(tmp), "ga.png", raw))
            self.assertEqual(image.pixel(0), (40, 40, 40, 128))
            self.assertEqual(image.pixel(1), (200, 200, 200, 64))

    # 调色板：索引 0 = 红，索引 1 = 蓝。下面几条都靠这个约定读期望值。
    RED_OR_BLUE = [255, 0, 0, 0, 0, 255]

    def test_palette_depth_2(self):
        """调色板 PNG + 2 位深。

        `0b01000000` 的高两位是索引 1（蓝），低两位是索引 0（红）——
        所以像素顺序是 (蓝, 红)。高低位顺序写反了这条会红。
        """
        raw = _raw_png(2, 1, 2, 3, [bytes([0b01000000])],
                       palette=self.RED_OR_BLUE + [0, 255, 0])
        with tempfile.TemporaryDirectory() as tmp:
            image = png_io.read_png(_write(Path(tmp), "p2.png", raw))
            self.assertEqual(image.pixel(0), (0, 0, 255, 255))
            self.assertEqual(image.pixel(1), (255, 0, 0, 255))

    def test_palette_depth_1(self):
        """1 位深调色板——每字节 8 个像素，是最容易被位运算写错的一档。"""
        raw = _raw_png(4, 1, 1, 3, [bytes([0b01010000])], palette=self.RED_OR_BLUE)
        with tempfile.TemporaryDirectory() as tmp:
            image = png_io.read_png(_write(Path(tmp), "p1.png", raw))
            self.assertEqual(
                [image.pixel(i)[:3] for i in range(4)],
                [(255, 0, 0), (0, 0, 255), (255, 0, 0), (0, 0, 255)],
            )

    def test_palette_transparency_key_makes_pixel_transparent(self):
        """调色板 + tRNS：索引 0 的像素要是透明的。

        tRNS 给调色板时是**每个调色板条目一个 alpha 字节**。低位深下
        比较的是「采样值」而不是字节，写错成字节比较会永远为假——
        于是透明像素被当成不透明**静默**混进色板，没有报错，只有结果偏。
        """
        raw = _raw_png(2, 1, 8, 3, [bytes([1, 0])],
                       palette=self.RED_OR_BLUE, transparency=[0, 255])
        with tempfile.TemporaryDirectory() as tmp:
            image = png_io.read_png(_write(Path(tmp), "pt.png", raw))
            self.assertEqual(image.pixel(0), (0, 0, 255, 255))   # 索引 1，不透明
            self.assertEqual(image.pixel(1), (255, 0, 0, 0))     # 索引 0，透明

    def test_16bit_gray_uses_high_byte(self):
        raw = _raw_png(2, 1, 16, 0, [bytes([0x12, 0x34, 0xAB, 0xCD])])
        with tempfile.TemporaryDirectory() as tmp:
            image = png_io.read_png(_write(Path(tmp), "g16.png", raw))
            self.assertEqual(image.pixel(0)[0], 0x12)
            self.assertEqual(image.pixel(1)[0], 0xAB)
            self.assertEqual(image.source_bpp, 16)

    def test_interlaced_is_rejected_loudly(self):
        """隔行图必须**明确报错**，不能静默给一张错的图。

        静默出错的表现是「参考图量出来的配色和肉眼看到的不一样」——
        没有任何异常，只能靠人肉发现，是这类 bug 里最难查的一种。
        """
        header = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 1)  # interlace=1
        body = bytearray(png_io._SIGNATURE)
        for name, payload in (
            (b"IHDR", header),
            (b"IDAT", zlib.compress(b"\x00" + b"\x00" * 24, 9)),
            (b"IEND", b""),
        ):
            body += png_io._chunk(name, payload)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "i.png", bytes(body))
            with self.assertRaises(png_io.PngError) as caught:
                png_io.read_png(path)
            self.assertIn("隔行", str(caught.exception))

    def test_broken_crc_is_caught(self):
        """逐块校验 CRC。跳过它的话，位翻转会变成一张颜色乱掉的图。"""
        with tempfile.TemporaryDirectory() as tmp:
            raw = bytearray(_raw_png(2, 1, 8, 2, [bytes([1, 2, 3, 4, 5, 6])]))
            raw[30] ^= 0xFF
            with self.assertRaises(png_io.PngError):
                png_io.read_png(_write(Path(tmp), "c.png", bytes(raw)))


# --- 配色测量 -------------------------------------------------------------

class MeasureTests(unittest.TestCase):
    def test_same_input_same_bytes(self):
        """同输入必须同字节——不然黄金文件回归和 diff 都做不了。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = _gradient(Path(tmp), "g.png", [(0, 0, 0), (255, 255, 255), (255, 0, 128)])
            first = json.dumps(measure_palette.measure([path]), sort_keys=True)
            second = json.dumps(measure_palette.measure([path]), sort_keys=True)
            self.assertEqual(first, second)

    def test_output_has_no_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _solid(Path(tmp), "a.png", (12, 34, 56))
            self.assertNotIn("time", json.dumps(measure_palette.measure([path])).lower())

    def test_dashscope_ratios_sum_to_exactly_100(self):
        """万相要求 ratio 精确合计 100.00%，两位小数——差 0.01 就整单被拒。

        用最大余数法分配，不能各算各的百分比。
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = _gradient(
                Path(tmp), "g.png",
                [(10, 20, 30), (240, 240, 230), (200, 40, 90), (30, 30, 40), (90, 120, 200)],
                width=41, height=37,
            )
            palette = measure_palette.measure([path])["dashscope_color_palette"]
            # ratio 是带百分号的字符串，万相接口就这么收。
            total = sum(float(item["ratio"].rstrip("%")) for item in palette)
            self.assertAlmostEqual(total, 100.00, places=6)
            for item in palette:
                self.assertRegex(item["ratio"], r"^\d+\.\d{2}%$")
                self.assertRegex(item["hex"], r"^#[0-9A-F]{6}$")

    def test_single_image_uses_real_coverage_not_consensus_mean(self):
        """单张参考图时用 `per_image[0]`，那是真实面积占比。

        用 consensus 的 mean_coverage 会让单图配色拿去做回测时口径对不上。
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = _solid(Path(tmp), "a.png", (200, 60, 60))
            result = measure_palette.measure([path])
            self.assertEqual(len(result["per_image"]), 1)
            coverage = sum(entry["coverage"] for entry in result["per_image"][0]["palette"])
            self.assertAlmostEqual(coverage, 1.0, places=3)

    def test_transparent_pixels_do_not_enter_palette(self):
        """近乎全透明的像素颜色看不见，但会把色板往一个随机方向拽。"""
        pixels = bytearray()
        alphas = bytearray()
        for _ in range(16):
            pixels += bytes((255, 0, 0))
            alphas.append(0)
            pixels += bytes((0, 0, 128))
            alphas.append(255)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.png"
            png_io.write_png(path, 32, 1, pixels, alphas)
            image = png_io.read_png(path)
            self.assertEqual(image.opaque_count(), 16)
            seen = set(image.iter_rgb())
            self.assertNotIn((255, 0, 0), seen)

    def test_largest_area_becomes_background_and_high_contrast_becomes_text(self):
        """角色判定的正向断言：最大面积的是 `background`，与它明度差最大的是 `text`。"""
        with tempfile.TemporaryDirectory() as tmp:
            pixels = bytearray()
            # 米白占 3/4，近黑占 1/4——大面积的是背景，高对比的是文字色。
            for _ in range(12):
                pixels += bytes((247, 244, 236)) * 32
            for _ in range(4):
                pixels += bytes((20, 20, 26)) * 32
            path = Path(tmp) / "roles.png"
            png_io.write_png(path, 32, 16, pixels)

            palette = measure_palette.measure([path], colors=2)["per_image"][0]["palette"]
            by_role = {entry["role"]: entry for entry in palette}
            self.assertIn("background", by_role)
            self.assertIn("text", by_role)
            self.assertEqual(by_role["background"]["hex"], "#F7F4EC")
            self.assertGreater(by_role["background"]["coverage"], by_role["text"]["coverage"])
            self.assertTrue(by_role["text"]["hex"].startswith("#1"))

    def test_gray_image_still_gets_role_labels(self):
        """纯灰图里没有任何彩色。

        脚本仍然会按规则贴上 primary / accent——**标签是猜的，颜色不是**。
        这条测试把「猜」这件事固定下来：不是断言它对，是断言它不假装。
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = _gradient(Path(tmp), "gray.png", [(0, 0, 0), (255, 255, 255)])
            palette = measure_palette.measure([path])["per_image"][0]["palette"]
            roles = {entry["role"] for entry in palette}
            self.assertTrue(roles <= set(measure_palette._ROLE_ORDER))
            self.assertIn("background", roles)

    def test_recovers_a_known_palette_within_tolerance(self):
        """合成一张配色已知的图，量回来的 hex 要落在 ΔE00 ≤ 3 以内。

        **容差为什么是 3 而不是 0**（PRD §6.1 已说明，这里再钉一次）：
        定 0 会因为量化误差永远红，然后就会有人去放宽它——那才是真的没测。
        定 3 是「测量工具的精度承诺」，可辩护。

        匹配用最近色，且必须**一一对应**：量出 4 个颜色，就要对上 4 个不同的
        已知色。允许两个量出色对上同一个已知色，等于允许漏掉一种颜色。
        """
        known = ["#F7F4EC", "#14141A", "#D8464E", "#2A5DA8"]
        with tempfile.TemporaryDirectory() as tmp:
            pixels = bytearray()
            # 四块等面积色带，每块 8 列
            for _ in range(16):
                for hex_value in known:
                    pixels += bytes(color_math.hex_to_rgb(hex_value)) * 8
            path = Path(tmp) / "known.png"
            png_io.write_png(path, 32, 16, pixels)

            palette = measure_palette.measure([path], colors=4)["per_image"][0]["palette"]
            recovered = [entry["hex"] for entry in palette]

            matched = set()
            for expected in known:
                best = min(recovered, key=lambda value: color_math.delta_e_hex(expected, value))
                distance = color_math.delta_e_hex(expected, best)
                with self.subTest(expected=expected):
                    self.assertLessEqual(
                        distance, 3.0,
                        f"{expected} 量成了 {best}，ΔE00 {distance:.2f} 超过容差 3",
                    )
                matched.add(best)
            self.assertEqual(len(matched), len(known), f"量出的颜色有重复：{recovered}")

    def test_nearly_identical_colours_get_merged(self):
        """ΔE00 < 2.5 的两个中心必须合并成一个。

        不合并的话，一张有渐变或压缩噪声的图会量出好几个「几乎一样」的颜色，
        色板看着有六个其实只有三个——**看起来更丰富，实际上更不准**。
        """
        self.assertTrue(color_math.delta_e_hex("#FFFFFF", "#FEFEFE") < 2.5)
        centers = [(255, 255, 255, 100), (254, 254, 254, 100), (20, 20, 26, 50)]
        merged = measure_palette.merge_similar(centers)
        self.assertEqual(len(merged), 2, [item["hex"] for item in merged])
        self.assertEqual(merged[0]["count"], 200)  # 合并后计数相加

    def test_merge_keeps_colours_further_apart_than_threshold(self):
        """超过阈值的两个中心不能被合并——否则色板会被压扁成一种颜色。"""
        self.assertGreater(color_math.delta_e_hex("#FFFFFF", "#14141A"), 2.5)
        centers = [(255, 255, 255, 100), (20, 20, 26, 100)]
        self.assertEqual(len(measure_palette.merge_similar(centers)), 2)

    def test_consensus_is_stable_for_matching_images_and_unstable_otherwise(self):
        """跨图共识：**稳定的才是 pattern，不稳定的不是。**

        两张配色挺像的图 → 各 role 的 stability 高；
        两张配色差很远的图 → 漂的那个 role stability 低。
        这是站 3 「一套图共用一个色板」这条判据的机器依据。
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            warm = [(247, 244, 236), (20, 20, 26), (216, 70, 78)]
            warm_shifted = [(246, 243, 234), (22, 22, 28), (214, 68, 76)]
            cold = [(12, 24, 40), (232, 238, 245), (40, 90, 200)]

            warm_a = _blocks(tmp, "wa.png", warm)
            warm_b = _blocks(tmp, "wb.png", warm_shifted)
            cold_c = _blocks(tmp, "c.png", cold)

            alike = measure_palette.measure([warm_a, warm_b])
            mixed = measure_palette.measure([warm_a, cold_c])

            def worst(result):
                return min(entry["stability"] for entry in result["consensus"])

            self.assertGreater(worst(alike), worst(mixed))
            self.assertGreater(worst(alike), 0.8)
            # 代表色必须取实际存在的那个，不能是平均出来的中间色。
            for entry in alike["consensus"]:
                self.assertRegex(entry["hex"], r"^#[0-9A-F]{6}$")

    def test_consensus_medoid_is_a_real_colour_not_an_average(self):
        """色相是环形的，橙（30°）和蓝（220°）平均出来是青（125°）——
        一个谁都没用过的颜色。代表色必须取实际存在的那个。"""
        per_image = [
            {"palette": [{"role": "primary", "hex": "#E8641E", "oklch": "0.6 0.2 30",
                          "coverage": 0.5}]},
            {"palette": [{"role": "primary", "hex": "#2A5DA8", "oklch": "0.5 0.15 250",
                          "coverage": 0.5}]},
        ]
        entry = measure_palette.consensus(per_image)[0]
        self.assertIn(entry["hex"], {"#E8641E", "#2A5DA8"})

    def test_roles_are_all_distinct_colours(self):
        """每个 role 只能落在一个色团上，不能两个 role 指向同一个 hex。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = _gradient(
                Path(tmp), "g.png",
                [(250, 248, 240), (20, 20, 24), (220, 70, 70), (40, 90, 200), (120, 120, 118)],
                width=32, height=32,
            )
            palette = measure_palette.measure([path])["per_image"][0]["palette"]
            hexes = [entry["hex"] for entry in palette]
            self.assertEqual(len(hexes), len(set(hexes)))


# --- 回测 -----------------------------------------------------------------

class VerifyTests(unittest.TestCase):
    def _expected(self, path):
        return measure_palette.measure([path])["per_image"][0]["palette"]

    def test_identical_image_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _gradient(Path(tmp), "g.png", [(250, 248, 240), (20, 20, 24), (220, 70, 70)])
            report = verify_palette.verify(self._expected(path), self._expected(path))
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["failures"], [])

    def test_drifted_image_fails(self):
        """配色漂了必须红，而且要说清哪个色漂到哪去了。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = _gradient(Path(tmp), "a.png", [(250, 248, 240), (20, 20, 24), (220, 70, 70)])
            moved = _gradient(Path(tmp), "b.png", [(250, 248, 240), (20, 20, 24), (20, 180, 60)])
            report = verify_palette.verify(
                self._expected(base), self._expected(moved), max_delta_e=5.0
            )
            self.assertEqual(report["verdict"], "FAIL")
            self.assertTrue(any("ΔE00" in note for note in report["failures"]))

    def test_role_relabel_is_not_a_failure(self):
        """role 换名不算失败——这是回测的核心设计决定。

        role 是启发式标签，同一套配色在参考图和生成图里可能被贴上不同的
        role。逐 role 比会把「标签变了」误报成「颜色漂了」，而颜色其实没变。
        假警报多了就没人看结果了，回测也就白做。
        """
        expected = [
            {"role": "background", "hex": "#F7F4EC", "coverage": 0.5},
            {"role": "text", "hex": "#14141A", "coverage": 0.3},
            {"role": "accent", "hex": "#D8464E", "coverage": 0.2},
        ]
        actual = [
            {"role": "surface", "hex": "#F7F4EC", "coverage": 0.5},
            {"role": "primary", "hex": "#14141A", "coverage": 0.3},
            {"role": "muted", "hex": "#D8464E", "coverage": 0.2},
        ]
        report = verify_palette.verify(expected, actual)
        self.assertEqual(report["verdict"], "PASS", report["failures"])

    def test_coverage_delta_fails_even_when_colour_matches(self):
        """颜色对但面积差太多也是漂——一大块主色缩成一小条，观感完全不同。"""
        expected = [{"role": "background", "hex": "#F7F4EC", "coverage": 0.8},
                    {"role": "text", "hex": "#14141A", "coverage": 0.2}]
        actual = [{"role": "background", "hex": "#F7F4EC", "coverage": 0.3},
                  {"role": "text", "hex": "#14141A", "coverage": 0.7}]
        report = verify_palette.verify(expected, actual, max_delta_e=3.0,
                                       max_coverage_delta=0.20)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("面积占比" in note for note in report["failures"]))

    def test_thresholds_are_reported_as_uncalibrated(self):
        """阈值没拿真实出图校准过就必须自己说出来。

        不说的话，PASS 会被当成「合格」，而它现在只能说明「没偏得离谱」。
        """
        report = verify_palette.verify(
            [{"role": "a", "hex": "#000000", "coverage": 1.0}],
            [{"role": "a", "hex": "#000000", "coverage": 1.0}],
        )
        self.assertIs(report["thresholds"]["calibrated"], False)

    def test_load_expected_accepts_bare_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            path.write_text(json.dumps([{"role": "a", "hex": "#000000", "coverage": 1.0}]))
            self.assertEqual(verify_palette.load_expected(path)[0]["hex"], "#000000")

    def test_load_expected_rejects_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            path.write_text(json.dumps({"whatever": 1}))
            with self.assertRaises(verify_palette.VerifyError):
                verify_palette.load_expected(path)

    def test_single_image_output_is_usable_as_expected(self):
        """`measure_palette.py` 的输出要能**原样**喂回回测，不经手工整理。"""
        with tempfile.TemporaryDirectory() as tmp:
            reference = _gradient(Path(tmp), "ref.png", [(247, 244, 236), (20, 20, 26), (216, 70, 78)])
            out = Path(tmp) / "palette.json"
            out.write_text(json.dumps(measure_palette.measure([reference])))

            generated = _gradient(Path(tmp), "gen.png", [(247, 244, 236), (20, 20, 26), (216, 70, 78)])
            report = verify_palette.run(out, generated)
            self.assertEqual(report["verdict"], "PASS", report["failures"])


# --- 出图请求体 -----------------------------------------------------------

class PayloadTests(unittest.TestCase):
    PROMPT = {"prompt": "一句话\n画面", "negative_prompt": "模糊", "style": "<photography>"}

    def test_payload_unchanged_without_new_arguments(self):
        """不带参考图/色板时，请求体必须与改造前**逐字节相同**。

        这是本功能最容易被破坏的地方——顺手往 parameters 里加个字段，
        所有既有简报的出图行为就悄悄变了，而且没有任何测试会红。
        所以这条比的是完整字典，不是抽查几个键。
        """
        self.assertEqual(
            generate_image.build_payload(self.PROMPT, "1024*1024"),
            {
                "model": generate_image.MODEL,
                "input": {"messages": [{"role": "user",
                                        "content": [{"text": "一句话\n画面"}]}]},
                "parameters": {
                    "size": "1024*1024",
                    "n": 1,
                    "watermark": False,
                    "negative_prompt": "模糊",
                    "style": "<photography>",
                },
            },
        )

    def test_payload_without_style_omits_style_key(self):
        prompt = dict(self.PROMPT, style="")
        payload = generate_image.build_payload(prompt, "1024*1024")
        self.assertNotIn("style", payload["parameters"])

    def test_reference_images_come_after_text(self):
        """参考图排在文字之后。万相按顺序读 content 数组，图片在前会改变语义。"""
        payload = generate_image.build_payload(
            self.PROMPT, "1024*1024", ("data:image/png;base64,AAA", "data:image/png;base64,BBB")
        )
        content = payload["input"]["messages"][0]["content"]
        self.assertEqual(len(content), 3)
        self.assertIn("text", content[0])
        self.assertEqual(content[1]["image"], "data:image/png;base64,AAA")
        self.assertEqual(content[2]["image"], "data:image/png;base64,BBB")

    def test_color_palette_lands_in_parameters(self):
        palette = [{"hex": "#F7F4EC", "ratio": "60.00"}, {"hex": "#14141A", "ratio": "40.00"}]
        payload = generate_image.build_payload(self.PROMPT, "1024*1024", color_palette=palette)
        self.assertEqual(payload["parameters"]["color_palette"], palette)

    def test_reference_instruction_is_appended_last(self):
        """参考说明排在最后——风格仍优先，参考不覆盖风格。"""
        prompt = generate_image.assemble_prompt(
            {"subject": "一张封面", "intent": "要克制",
             "reference_instruction": "只参考它的配色和留白"},
            {"prompt": {"prefix": "编辑风", "negative": "杂乱"}, "image_style_enum": "<x>"},
        )
        self.assertTrue(prompt["prompt"].endswith("只参考它的配色和留白"))
        self.assertLess(prompt["prompt"].index("编辑风"), prompt["prompt"].index("只参考它的配色和留白"))


# --- 参考图解析 -----------------------------------------------------------

class ReferenceResolutionTests(unittest.TestCase):
    def _project(self, tmp: Path) -> Path:
        root = tmp / "proj"
        (root / "assets" / "reference").mkdir(parents=True)
        (root / ".hq-geo.json").write_text("{}")
        return root

    def test_missing_palette_raises_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            with self.assertRaises(SystemExit):
                generate_image.load_color_palette("assets/reference/none.json", root)

    def test_palette_without_dashscope_entries_explains_why(self):
        """颜色少于 3 种时没有 `dashscope_color_palette`。

        报错要说清原因，不能只说「字段缺失」——用户不知道自己该做什么。
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            path = root / "assets" / "reference" / "p.json"
            path.write_text(json.dumps({"per_image": [], "consensus": []}))
            with self.assertRaises(SystemExit) as caught:
                generate_image.load_color_palette("assets/reference/p.json", root)
            self.assertIn("3", str(caught.exception))

    def test_reference_outside_project_is_refused(self):
        """参考图越出项目根必须拒绝——那些图没有权利登记。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            with self.assertRaises(SystemExit) as caught:
                generate_image.resolve_reference_images(
                    {"id": "d1", "reference_images": ["../../../etc/hosts"]}, root
                )
            self.assertIn("项目根之外", str(caught.exception))


# --- 简报校验的新拦截 -----------------------------------------------------

def _brief(**overrides) -> dict:
    brief = {
        "schema_version": 1, "id": "img-001", "topic_id": "t1", "title": "示例",
        "status": "draft", "objective": "o", "audience": "a", "core_thesis": "c",
        "fact_refs": ["F-001"], "platform": "xhs", "prohibited_claims": [],
        "acceptance_criteria": ["无错别字"],
        "deliverables": [{
            "id": "d1", "role": "封面", "size": "1024*1024", "subject": "一张封面",
            "subject_kind": "concept", "synthetic": True, "source_assets": [],
            "style_id": "editorial-minimal", "status": "planned",
        }],
    }
    brief["deliverables"][0].update(overrides)
    return brief


class ReferenceInterceptTests(unittest.TestCase):
    """PRD §4.2 的四条新拦截。每一条都对应一种「不拦就会出事」。"""

    def _run(self, deliverable_overrides, files=()):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".hq-geo.json").write_text("{}")
            (root / "assets" / "reference").mkdir(parents=True)
            for name, content in files:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            brief_dir = root / "content" / "briefs" / "b1"
            brief_dir.mkdir(parents=True)
            path = brief_dir / "image-brief.json"
            path.write_text(json.dumps(_brief(**deliverable_overrides), ensure_ascii=False))
            return validate_image_brief.validate(path, STYLE_IDS, root)

    def test_reference_without_instruction_is_rejected(self):
        """有参考图却没说要参考什么——模型可能把参考图当成待编辑对象。"""
        errors = self._run(
            {"reference_images": ["assets/reference/a.png"]},
            files=[("assets/reference/a.png", "x")],
        )
        self.assertTrue(any("必须写 reference_instruction" in e for e in errors), errors)

    def test_reference_outside_project_root_is_rejected(self):
        errors = self._run(
            {"reference_images": ["../../外面.png"], "reference_instruction": "参考配色"},
        )
        self.assertTrue(any("指向项目根之外" in e for e in errors), errors)

    def test_missing_reference_file_is_rejected(self):
        """文件不在就要在**校验时**拦下。出图时才报错，钱已经花了。"""
        errors = self._run(
            {"reference_images": ["assets/reference/没有这张.png"],
             "reference_instruction": "参考配色"},
        )
        self.assertTrue(any("参考图不存在" in e for e in errors), errors)

    def test_broken_palette_ref_is_rejected(self):
        """`palette_ref` 格式不对时，出图会**静默不出色板**——图和预期两样。"""
        errors = self._run(
            {"palette_ref": "assets/reference/bad.json"},
            files=[("assets/reference/bad.json", '{"foo": 1}')],
        )
        self.assertTrue(any("不是 measure_palette.py 的输出" in e for e in errors), errors)

    def test_missing_palette_ref_file_is_rejected(self):
        errors = self._run({"palette_ref": "assets/reference/none.json"})
        self.assertTrue(any("palette_ref 指向的文件不存在" in e for e in errors), errors)

    def test_valid_reference_and_palette_pass(self):
        errors = self._run(
            {"reference_images": ["assets/reference/a.png"],
             "reference_instruction": "参考它的配色和留白",
             "palette_ref": "assets/reference/p.json"},
            files=[("assets/reference/a.png", "x"),
                   ("assets/reference/p.json", '{"per_image": [], "consensus": []}')],
        )
        self.assertEqual(errors, [])

    def test_brief_without_new_fields_still_passes(self):
        """没用参考图的既有简报，行为一点不变。"""
        self.assertEqual(self._run({}), [])

    def test_no_instruction_required_when_no_reference(self):
        """没有参考图时不强求 `reference_instruction`——宪法 8：默认减法。"""
        self.assertEqual(self._run({"reference_instruction": ""}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
