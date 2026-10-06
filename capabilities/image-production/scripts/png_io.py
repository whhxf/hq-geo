#!/usr/bin/env python3
"""纯标准库 PNG 读写。只用 `struct` / `zlib` / `pathlib`。

**为什么不装 Pillow**：`AGENTS.md` 规定新系统只依赖标准库。Pillow 本机装着，
但用了它这套脚本换台机器就跑不起来——而「换机器跑不起来」正是方法无法复用的成因。

**支持范围**（都是真实图片里会遇到的，不是纸面完备性）：

| 颜色类型 | 含义 | 位深 |
|---|---|---|
| 0 | 灰度 | 1 / 2 / 4 / 8 / 16 |
| 2 | RGB | 8 / 16 |
| 3 | 调色板 | 1 / 2 / 4 / 8 |
| 4 | 灰度 + Alpha | 8 / 16 |
| 6 | RGBA | 8 / 16 |

不支持的一律**抛 `PngError` 并说清原因**，绝不静默返回错值——
错色值会让后面整条测量链给出看起来合理的错误答案，那比报错难查得多。

唯一不支持的是**隔行（Adam7）**。它在 2026 年的图片里已很少见，
而代价是要写七遍反滤。遇到就报错，让用户转一道。

**输出统一成 RGB + 独立的 alpha 通道。** 灰度展开成三通道，低位深缩放到 0..255，
16 位取高字节，调色板查表。这样下游只需要认识一种像素格式。

关于 alpha：**透明像素没有颜色，不是黑色。** 所以 alpha 单独留一轨，
由调用方决定阈值，而不是在这里合成到某个背景上——
合成到白色会让透明背景的标志图把整个色板带向白。
"""

import struct
import zlib
from pathlib import Path

_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# 每种颜色类型的通道数（调色板占 1 个索引通道）。
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}

# 每种颜色类型允许的位深。
_VALID_DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}

_COLOR_TYPE_NAMES = {0: "灰度", 2: "RGB", 3: "调色板", 4: "灰度+Alpha", 6: "RGBA"}


class PngError(Exception):
    """PNG 读不了时抛这个。消息要能让用户知道下一步做什么。"""


class PngImage:
    """解码后的图片。`pixels` 与 `alpha` 都是逐像素展开的扁平 `bytearray`。

    `pixels` 长度是 `width * height * 3`（RGB 三通道交错）。
    `alpha` 长度是 `width * height`；**源图没有 alpha 通道时全是 255**，
    这样调用方不用为「有没有 alpha」写两套逻辑。
    """

    __slots__ = ("width", "height", "pixels", "alpha", "source_bpp")

    def __init__(self, width, height, pixels, alpha, source_bpp):
        self.width = width
        self.height = height
        self.pixels = pixels
        self.alpha = alpha
        # 源图的位深，仅用于报告与诊断。展开后的像素一律是 8 位。
        self.source_bpp = source_bpp

    def __len__(self):
        return self.width * self.height

    def __repr__(self):
        return f"<PngImage {self.width}x{self.height} 位深{self.source_bpp}>"

    def pixel(self, index):
        """第 `index` 个像素（行优先）的 (r, g, b, a)。"""
        base = index * 3
        return (
            self.pixels[base],
            self.pixels[base + 1],
            self.pixels[base + 2],
            self.alpha[index],
        )

    def iter_rgb(self, alpha_min=16):
        """逐个吐出 (r, g, b)，**跳过 alpha 低于 `alpha_min` 的像素**。

        默认阈值 16 是为了滤掉「几乎全透明」的像素——它们的颜色在屏幕上
        根本看不到，但会把色板往一个随机方向拽。
        """
        pixels = self.pixels
        alpha = self.alpha
        for index in range(len(alpha)):
            if alpha[index] < alpha_min:
                continue
            base = index * 3
            yield pixels[base], pixels[base + 1], pixels[base + 2]

    def opaque_count(self, alpha_min=16):
        """达到 alpha 阈值的像素数。用来判断「这张图还剩多少可测的内容」。"""
        return sum(1 for value in self.alpha if value >= alpha_min)


# --- 读取 -----------------------------------------------------------------

def read_png(path) -> PngImage:
    """读一个 PNG。失败一律抛 `PngError`，消息里说清是什么问题。"""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PngError(f"读不到文件：{path}（{error.strerror}）") from error

    if not data.startswith(_SIGNATURE):
        raise PngError(
            f"{path.name} 不是 PNG（文件签名不对）。"
            "如果是 JPEG / WEBP，先转成 PNG 再试。"
        )

    header, palette, transparency, idat = _scan_chunks(data, path)
    return _decode(header, palette, transparency, idat, path)


def _scan_chunks(data, path):
    """走一遍 chunk，只取需要的四样：IHDR / PLTE / tRNS / IDAT。"""
    header = None
    palette = None
    transparency = None
    idat = []

    position = len(_SIGNATURE)
    total = len(data)
    while position < total:
        if position + 8 > total:
            raise PngError(f"{path.name} 在 chunk 头部截断，文件不完整。")

        (length,) = struct.unpack_from(">I", data, position)
        chunk_type = data[position + 4:position + 8]
        body_start = position + 8
        body_end = body_start + length
        if body_end + 4 > total:
            raise PngError(f"{path.name} 的 {chunk_type!r} chunk 数据截断，文件不完整。")

        body = data[body_start:body_end]

        # CRC 能抓出传输损坏。逐个 chunk 校验，坏掉的文件不会一路算出一个错色板。
        (stored_crc,) = struct.unpack_from(">I", data, body_end)
        if (zlib.crc32(chunk_type + body) & 0xFFFFFFFF) != stored_crc:
            raise PngError(f"{path.name} 的 {chunk_type!r} chunk CRC 校验失败，文件已损坏。")

        if chunk_type == b"IHDR":
            header = body
        elif chunk_type == b"PLTE":
            palette = body
        elif chunk_type == b"tRNS":
            transparency = body
        elif chunk_type == b"IDAT":
            idat.append(body)
        elif chunk_type == b"IEND":
            break

        position = body_end + 4

    if header is None:
        raise PngError(f"{path.name} 没有 IHDR，不是有效的 PNG。")
    if not idat:
        raise PngError(f"{path.name} 没有 IDAT，里面没有图像数据。")
    return header, palette, transparency, idat


def _decode(header, palette, transparency, idat, path):
    """校验参数 → 解压 → 反滤 → 展开成 RGB + alpha。"""
    if len(header) < 13:
        raise PngError(f"{path.name} 的 IHDR 长度不对。")

    width, height, depth, color_type, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", header[:13]
    )

    if width == 0 or height == 0:
        raise PngError(f"{path.name} 的宽或高为 0。")

    if color_type not in _CHANNELS:
        raise PngError(
            f"{path.name} 的颜色类型 {color_type} 不是 PNG 规范里的值"
            f"（合法值 0/2/3/4/6）。"
        )
    if depth not in _VALID_DEPTHS[color_type]:
        allowed = "/".join(str(item) for item in _VALID_DEPTHS[color_type])
        raise PngError(
            f"{path.name} 是{_COLOR_TYPE_NAMES[color_type]}，位深 {depth} 不合法"
            f"（该类型允许 {allowed}）。"
        )
    if interlace != 0:
        raise PngError(
            f"{path.name} 是隔行（Adam7）PNG，暂不支持。"
            "用预览或 `sips -s format png` 重新导出一张非隔行的即可。"
        )
    if compression != 0 or filter_method != 0:
        raise PngError(f"{path.name} 用了未知的压缩或滤波方式，无法解码。")

    channels = _CHANNELS[color_type]
    row_bytes = (width * channels * depth + 7) // 8
    # 滤波器按「像素的字节宽度」寻址，低位深时最小是 1。
    bpp = max(1, channels * depth // 8)

    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as error:
        raise PngError(f"{path.name} 的图像数据解压失败，文件可能损坏（{error}）。") from error

    if len(raw) < height * (row_bytes + 1):
        raise PngError(
            f"{path.name} 解压后只有 {len(raw)} 字节，"
            f"但按尺寸需要 {height * (row_bytes + 1)} 字节，数据不完整。"
        )

    rows = _unfilter(raw, width, height, bpp, row_bytes)
    pixels, alpha = _expand(rows, width, height, depth, color_type, palette, transparency)
    return PngImage(width, height, pixels, alpha, depth)


# --- 反滤 -----------------------------------------------------------------

def _paeth(a, b, c):
    """PNG 规范里的 Paeth 预测器。选 a/b/c 中离 p 最近的那个。"""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw, width, height, bpp, row_bytes):
    """把带滤波的扫描线还原成逐行原始字节。

    每行首字节是滤波类型，对行内每个字节做可逆还原。五种滤波都要实现——
    编码器会逐行挑最省字节的那一种，所以任何一张真实图片都会混着出现。
    """
    rows = []
    previous = None
    position = 0

    for _ in range(height):
        filter_type = raw[position]
        position += 1
        line = raw[position:position + row_bytes]
        position += row_bytes

        if filter_type == 0:  # None
            row = bytearray(line)
        elif filter_type == 1:  # Sub：减去左边
            row = bytearray(line)
            for index in range(bpp, row_bytes):
                row[index] = (row[index] + row[index - bpp]) & 0xFF
        elif filter_type == 2:  # Up：减去上边
            if previous is None:
                row = bytearray(line)
            else:
                # zip + 推导式比下标循环快一大截，这一行是整条链的热点。
                row = bytearray((value + above) & 0xFF for value, above in zip(line, previous))
        elif filter_type == 3:  # Average：减去左右均值
            row = bytearray(line)
            for index in range(row_bytes):
                left = row[index - bpp] if index >= bpp else 0
                above = previous[index] if previous is not None else 0
                row[index] = (row[index] + (left + above) // 2) & 0xFF
        elif filter_type == 4:  # Paeth
            row = bytearray(line)
            for index in range(row_bytes):
                left = row[index - bpp] if index >= bpp else 0
                above = previous[index] if previous is not None else 0
                corner = previous[index - bpp] if (previous is not None and index >= bpp) else 0
                row[index] = (row[index] + _paeth(left, above, corner)) & 0xFF
        else:
            raise PngError(f"遇到未知的滤波类型 {filter_type}，只允许 0..4。")

        rows.append(row)
        previous = row

    return rows


# --- 展开成 RGB + alpha ----------------------------------------------------

def _expand(rows, width, height, depth, color_type, palette, transparency):
    """把各种位深/颜色类型统一成 8 位 RGB + 独立 alpha 轨。

    **8 位且没有颜色键时走快路径**：这几种格式占了真实图片的绝大多数，
    而且它们的展开本质上是「按固定步长拆通道」，可以用步长切片赋值在 C 层整块搬。
    逐像素 Python 循环比它慢一个数量级——实测 12MP 的 RGB 图，快路径把
    展开发从 3.1 秒压到 0.02 秒。剩下的位深和颜色键才是真需要逐像素的。
    """
    count = width * height
    key = _transparency_key(transparency, color_type, depth)

    if depth == 8 and key is None:
        fast = _expand_fast(rows, width, height, count, color_type)
        if fast is not None:
            return fast

    pixels = bytearray(count * 3)
    alpha = bytearray(b"\xff" * count)

    palette_rgb, palette_alpha = _build_palette(palette, transparency, color_type)
    max_value = (1 << depth) - 1

    out = 0
    for y in range(height):
        row = rows[y]
        for x in range(width):
            if depth == 8:
                samples = _samples_depth8(row, x, color_type)
            elif depth == 16:
                samples = _samples_depth16(row, x, color_type)
            else:
                samples = None

            if samples is None:
                index = _unpack_index(row, x, depth)
                if color_type == 3:
                    if index >= len(palette_rgb):
                        raise PngError(
                            f"调色板索引 {index} 超出 PLTE 表的 {len(palette_rgb)} 项，文件不一致。"
                        )
                    red, green, blue = palette_rgb[index]
                    a = palette_alpha[index]
                else:
                    # 低位深灰度：把 0..max 拉伸到 0..255。
                    level = index * 255 // max_value
                    red = green = blue = level
                    # key 恒为元组，比的是原始样本值，不是拉伸后的 level。
                    a = 0 if key is not None and (index,) == key else 255
            else:
                if color_type == 3:
                    if samples[0] >= len(palette_rgb):
                        raise PngError(
                            f"调色板索引 {samples[0]} 超出 PLTE 表的 {len(palette_rgb)} 项，文件不一致。"
                        )
                    red, green, blue = palette_rgb[samples[0]]
                    a = palette_alpha[samples[0]]
                elif color_type == 0:
                    red = green = blue = samples[0]
                    a = 255
                elif color_type == 4:
                    red = green = blue = samples[0]
                    a = samples[1]
                elif color_type == 6:
                    red, green, blue, a = samples
                else:  # 颜色类型 2：RGB
                    red, green, blue = samples
                    a = 255

                if key is not None and samples[:len(key)] == key:
                    a = 0

            pixels[out] = red
            pixels[out + 1] = green
            pixels[out + 2] = blue
            alpha[out // 3] = a
            out += 3

    return pixels, alpha


def _expand_fast(rows, width, height, count, color_type):
    """8 位、无颜色键时用步长切片整块展开。不适用则返回 `None`。

    步长切片赋值（`target[0::3] = source`）在 CPython 里是 C 层实现，
    比逐像素循环快一个数量级。代价是它**要求两边长度严格相等**，
    所以长度算错的后果是 `ValueError` 而不是静默错位——这正是想要的。
    """
    if color_type not in (0, 2, 4, 6):
        return None

    flat = bytes().join(rows)
    alpha = bytearray(b"\xff" * count)
    pixels = bytearray(count * 3)

    if color_type == 2:  # RGB：解出来的就是成品，直接搬
        pixels[:] = flat
    elif color_type == 6:  # RGBA：按 4 拆
        pixels[0::3] = flat[0::4]
        pixels[1::3] = flat[1::4]
        pixels[2::3] = flat[2::4]
        alpha[:] = flat[3::4]
    elif color_type == 0:  # 灰度：一个字节铺成三通道
        pixels[0::3] = flat
        pixels[1::3] = flat
        pixels[2::3] = flat
    else:  # 颜色类型 4：灰度 + Alpha，按 2 拆
        gray = flat[0::2]
        pixels[0::3] = gray
        pixels[1::3] = gray
        pixels[2::3] = gray
        alpha[:] = flat[1::2]

    return pixels, alpha


def _samples_depth8(row, x, color_type):
    """8 位时每个像素的样本值，直接就是字节。"""
    if color_type == 0:
        return (row[x],)
    if color_type == 2:
        base = x * 3
        return (row[base], row[base + 1], row[base + 2])
    if color_type == 3:
        return (row[x],)
    if color_type == 4:
        base = x * 2
        return (row[base], row[base + 1])
    base = x * 4
    return (row[base], row[base + 1], row[base + 2], row[base + 3])


def _samples_depth16(row, x, color_type):
    """16 位时取**高字节**。

    丢掉低 8 位对色板测量没有影响：8 位量化本来就只有 256 级，
    而 16 位图里的低字节落在量化台阶之内。留一个 `>> 8` 比引一套
    16 位色差计算划算得多。
    """
    if color_type == 0:
        return (row[x * 2],)
    if color_type == 2:
        base = x * 6
        return (row[base], row[base + 2], row[base + 4])
    if color_type == 4:
        base = x * 4
        return (row[base], row[base + 2])
    base = x * 8
    return (row[base], row[base + 2], row[base + 4], row[base + 6])


def _unpack_index(row, x, depth):
    """低位深时取出第 `x` 个样本。样本按位打包，不跨字节。"""
    per_byte = 8 // depth
    byte = row[x // per_byte]
    shift = 8 - depth * (x % per_byte + 1)
    return (byte >> shift) & ((1 << depth) - 1)


def _build_palette(palette, transparency, color_type):
    """把 PLTE 和 tRNS 变成 (rgb 表, alpha 表)。非调色板图返回空表。"""
    if color_type != 3:
        return [], []
    if palette is None:
        raise PngError("调色板 PNG 缺少 PLTE chunk，文件不完整。")

    count = len(palette) // 3
    rgb = [(palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2]) for i in range(count)]

    alphas = [255] * count
    if transparency:
        for index, value in enumerate(transparency[:count]):
            alphas[index] = value
    return rgb, alphas


def _transparency_key(transparency, color_type, depth):
    """灰度和 RGB 的 tRNS 是「某个颜色值代表透明」，不是 alpha 表。

    返回值要和 `_samples_*` / `_unpack_index` 给出的样本**同刻度**，
    否则比较永远不成立、透明像素被当成不透明，而且不会有任何报错：
    16 位比高字节，8 位比低字节，低位深比原始样本值。
    """
    if not transparency:
        return None
    if color_type == 0:
        if len(transparency) < 2:
            return None
        (value,) = struct.unpack(">H", transparency[:2])
        if depth == 16:
            return (value >> 8,)
        if depth == 8:
            return (value & 0xFF,)
        return (value,)
    if color_type == 2 and len(transparency) >= 6:
        values = struct.unpack(">HHH", transparency[:6])
        if depth == 16:
            return tuple(item >> 8 for item in values)
        return tuple(item & 0xFF for item in values)
    return None


# --- 写出（只给测试造合成图用） --------------------------------------------

def write_png(path, width, height, pixels, alpha=None):
    """写一张 8 位 PNG。**只用于测试造图**，生产链路不写 PNG。

    所有行都用滤波类型 0（None），这样输出字节完全确定，
    测试可以断言精确的哈希而不用担心编码器版本差异。
    """
    if len(pixels) != width * height * 3:
        raise PngError(f"像素数据长度 {len(pixels)} 与 {width}x{height} 的 RGB 需求不符。")
    if alpha is not None and len(alpha) != width * height:
        raise PngError(f"alpha 长度 {len(alpha)} 与 {width}x{height} 不符。")

    if alpha is None:
        color_type = 2
        stride = width * 3
        raw = bytearray()
        for y in range(height):
            raw.append(0)
            raw += pixels[y * stride:(y + 1) * stride]
    else:
        color_type = 6
        raw = bytearray()
        for y in range(height):
            raw.append(0)
            for x in range(width):
                base = (y * width + x) * 3
                raw += pixels[base:base + 3]
                raw.append(alpha[y * width + x])

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    body = (
        _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    Path(path).write_bytes(_SIGNATURE + body)


def _chunk(chunk_type, payload):
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )
