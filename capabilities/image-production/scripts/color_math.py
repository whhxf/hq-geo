#!/usr/bin/env python3
"""颜色空间的确定性换算。纯标准库，纯函数，无状态。

为什么要自己写这一层：**颜色不能靠模型的眼睛。** 2026-09-30 实测，
视觉模型报出的色值会向训练分布里的常见色漂移——常见色漂移 ΔE00 < 3，
独有品牌色可达 17（`#ff90e8` 被读成 `#ec4899`）。**越是有辨识度的颜色漂得越狠**，
而辨识度正是要吸收的东西。所以颜色一律在这里算。

三件事：

1. `srgb -> oklch`   —— 给风格库的 `tokens.palette[].oklch` 用
2. `srgb -> cielab`  —— 给色差计算做中间量
3. `delta_e_2000`    —— 判断两个颜色「看起来差多少」

**OKLCH 的字符串格式对齐既有风格库**：`"0.979 0.007 88.6"`，
三位小数、三位小数、一位小数，**不带 `oklch()` 外壳**。
既有 14 套风格里 84 组 (hex, oklch) 是现成的回归语料，见 `tests/test_palette.py`。
"""

import math

# --- sRGB <-> 线性 ---------------------------------------------------------

# sRGB 传输函数的断点与系数（IEC 61966-2-1）。
_SRGB_BREAK = 0.04045
_SRGB_SLOPE = 12.92
_SRGB_ALPHA = 0.055
_SRGB_GAMMA = 2.4


def srgb_channel_to_linear(value: float) -> float:
    """单个 sRGB 通道（0..1）转线性光。

    **必须做这一步。** 直接把 sRGB 值当线性光算，暗部会整体偏亮——
    那是把显示器编码当物理量的经典错误，而它对深色图的伤害最大。
    """
    if value <= _SRGB_BREAK:
        return value / _SRGB_SLOPE
    return ((value + _SRGB_ALPHA) / (1 + _SRGB_ALPHA)) ** _SRGB_GAMMA


def linear_channel_to_srgb(value: float) -> float:
    """线性光转 sRGB 通道（0..1）。写 PNG 和反推用。"""
    if value <= _SRGB_BREAK * _SRGB_SLOPE:
        return value * _SRGB_SLOPE
    return (1 + _SRGB_ALPHA) * (value ** (1 / _SRGB_GAMMA)) - _SRGB_ALPHA


# --- OKLab / OKLCH（Björn Ottosson 的系数） --------------------------------

def linear_rgb_to_oklab(r: float, g: float, b: float) -> tuple:
    """线性 sRGB (0..1) -> OKLab。"""
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    l_ = _cbrt(l)
    m_ = _cbrt(m)
    s_ = _cbrt(s)

    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _cbrt(value: float) -> float:
    """实数立方根。`value ** (1/3)` 对负数返回复数，不能用。"""
    return math.copysign(abs(value) ** (1 / 3), value)


def oklab_to_oklch(lab: tuple) -> tuple:
    """OKLab -> (L, C, H)。H 单位是度，落在 [0, 360)。"""
    lightness, a, b = lab
    chroma = math.hypot(a, b)
    hue = math.degrees(math.atan2(b, a)) % 360
    return lightness, chroma, hue


def srgb_to_oklab(r8: int, g8: int, b8: int) -> tuple:
    """8 位 sRGB -> OKLab。绝大多数调用走这个。"""
    return linear_rgb_to_oklab(
        srgb_channel_to_linear(r8 / 255),
        srgb_channel_to_linear(g8 / 255),
        srgb_channel_to_linear(b8 / 255),
    )


# --- CIELAB ---------------------------------------------------------------

# sRGB 的 D65 白点。
_WHITE_X = 0.9504559270516716
_WHITE_Z = 1.0890577507598784

_LAB_EPSILON = 216 / 24389
_LAB_KAPPA = 24389 / 27


def srgb_to_cielab(r8: int, g8: int, b8: int) -> tuple:
    """8 位 sRGB -> CIELAB (L*, a*, b*)。色差计算的中间量。"""
    r = srgb_channel_to_linear(r8 / 255)
    g = srgb_channel_to_linear(g8 / 255)
    b = srgb_channel_to_linear(b8 / 255)

    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / _WHITE_X
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / _WHITE_Z

    fx = _lab_f(x)
    fy = _lab_f(y)
    fz = _lab_f(z)

    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _lab_f(t: float) -> float:
    if t > _LAB_EPSILON:
        return t ** (1 / 3)
    return (_LAB_KAPPA * t + 16) / 116


# --- 色差 -----------------------------------------------------------------

def delta_e_2000(lab1: tuple, lab2: tuple) -> float:
    """CIEDE2000 色差。

    **为什么是 2000 版而不是 76 版**：76 版在蓝色区和低饱和度区高估色差，
    而图片线关心的恰恰是「米白和浅灰差多少」这类低饱和判断。
    2000 版加了明度/彩度/色相的加权与旋转项，在低饱和区更接近人眼。

    读法（CIE 常用经验值）：
      < 1    肉眼不可辨
      1 - 2  训练有素的眼睛近距离可辨
      2 - 10 一眼看出不同
      > 10   几乎不是同一个颜色
    """
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2

    c_bar7 = c_bar ** 7
    g = 0.5 * (1 - math.sqrt(c_bar7 / (c_bar7 + 25 ** 7))) if c_bar > 0 else 0.0

    a1p = (1 + g) * a1
    a2p = (1 + g) * a2

    c1p = math.hypot(a1p, b1)
    c2p = math.hypot(a2p, b2)

    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360

    d_lp = l2 - l1
    d_cp = c2p - c1p

    if c1p * c2p == 0:
        d_hp = 0.0
    elif abs(h2p - h1p) <= 180:
        d_hp = h2p - h1p
    elif h2p - h1p > 180:
        d_hp = h2p - h1p - 360
    else:
        d_hp = h2p - h1p + 360

    d_big_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(d_hp) / 2)

    l_bar_p = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2

    if c1p * c2p == 0:
        h_bar_p = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar_p = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar_p = (h1p + h2p + 360) / 2
    else:
        h_bar_p = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar_p - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar_p))
        + 0.32 * math.cos(math.radians(3 * h_bar_p + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar_p - 63))
    )

    d_theta = 30 * math.exp(-(((h_bar_p - 275) / 25) ** 2))
    c_bar_p7 = c_bar_p ** 7
    r_c = 2 * math.sqrt(c_bar_p7 / (c_bar_p7 + 25 ** 7))
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c

    s_l = 1 + (0.015 * (l_bar_p - 50) ** 2) / math.sqrt(20 + (l_bar_p - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t

    return math.sqrt(
        (d_lp / s_l) ** 2
        + (d_cp / s_c) ** 2
        + (d_big_h / s_h) ** 2
        + r_t * (d_cp / s_c) * (d_big_h / s_h)
    )


def delta_e_76(lab1: tuple, lab2: tuple) -> float:
    """CIE76 色差——**只用来对照外部数字，管线内部一律用 `delta_e_2000`。**

    存在的理由是一个真实的坑：`zanwei/design-dna` 公开记录「`#ff90e8` 被模型读成
    `#ec4899`，ΔE ≈ 29」，我按 ΔE00 算同一对色值只有 **17.0**。两个都对，
    是度量不同——ΔE76 在高饱和区严重高估，这对色值上差 **71%**。

    危害在于：ΔE76 和 ΔE00 的刻度不一样，**把外部文档里的阈值直接搬进本管线，
    门禁会静默地松掉或紧掉，而且没有任何报错**。所以这个函数留着，
    专门用于把外部数字翻译成本管线的刻度。
    """
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(lab1, lab2)))


# --- hex 便捷接口 ----------------------------------------------------------

def hex_to_rgb(value: str) -> tuple:
    """`#rrggbb` -> (r, g, b)。也接受不带 `#` 的写法。大小写不敏感。"""
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        raise ValueError(f"不是合法的 hex 色值：{value!r}")
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError as error:
        raise ValueError(f"不是合法的 hex 色值：{value!r}") from error


def rgb_to_hex(rgb: tuple) -> str:
    """(r, g, b) -> `#RRGGBB`。**统一大写**——风格库里是大写。"""
    r, g, b = (max(0, min(255, round(channel))) for channel in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_oklch_string(value: str) -> str:
    """`#RRGGBB` -> `"0.979 0.007 88.6"`。

    格式对齐既有风格库的 `tokens.palette[].oklch`：三位、三位、一位小数，
    不带 `oklch()` 外壳。**格式不一致会让新测的色板和旧风格库拼不到一起。**
    """
    return format_oklch(oklab_to_oklch(srgb_to_oklab(*hex_to_rgb(value))))


def format_oklch(oklch: tuple) -> str:
    """(L, C, H) -> `"0.979 0.007 88.6"`。

    两条规则，都是从既有 84 组 (hex, oklch) 里读出来的，零例外：

    1. **精度按量程配**：L 和 C 各 3 位小数，H 1 位。
       L 落在 0..1、C 落在 0..0.4、H 落在 0..360，各自约 1000/400/3600 级。
    2. **零写成光秃秃的 `0`**：`0.348 0 0` 而不是 `0.348 0.000 0.0`。

    规则 2 不只是好看——**彩度归零时色相是未定义的**。`atan2` 在 a≈b≈0 时
    给出的是浮点残差的方向（实测 `#1C1C1C` 会算出 89.9°，`#3A3A3A` 也是），
    那是噪声不是信息。灰色没有色相，写死成 0 才是对的。
    """
    lightness, chroma, hue = oklch
    if round(chroma, 3) == 0:
        hue = 0.0
    return " ".join(_component(value, digits) for value, digits in ((lightness, 3), (chroma, 3), (hue, 1)))


def _component(value: float, digits: int) -> str:
    """按位数格式化，但恰为零时只写 `0`（见 `format_oklch` 规则 2）。"""
    if round(value, digits) == 0:
        return "0"
    return f"{value:.{digits}f}"


def delta_e_hex(hex1: str, hex2: str) -> float:
    """两个 hex 色值的 CIEDE2000 色差。"""
    return delta_e_2000(srgb_to_cielab(*hex_to_rgb(hex1)), srgb_to_cielab(*hex_to_rgb(hex2)))
