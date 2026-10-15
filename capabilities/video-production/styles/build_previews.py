#!/usr/bin/env python3
"""给每个风格生成一张示意图，写进 previews/<style-id>.jpg。

为什么需要：
gallery.html 原来只有文字。风格靠看，不靠读。没有图，人没法从视觉上选。

图从哪来：
不自己画，用上游仓库自己带的样片。六个来源：

1. huashu `assets/全风格总览.jpg` —— 一张 6x6 拼图，35 段艺术风格。
   本脚本按固定网格切开，一段一张。
2. huashu `assets/动画语法/*_总览.jpg` —— 8 个语法，取最左一镜。
3. huashu `assets/角色/花叔形象_对比.jpg` —— 讲解员语法没有单张样片，用这张。
4. lanshu `explainer/gallery/nine-styles-kv-cache.jpg` —— 一张 3x3 拼图，9 种风格。
5. geeklee `examples/scene-01-monkey-mountain.png` —— 一张，整张用。
6. handdrawn `assets/image-manifest.json` 里列的 21 张样例图。
   图不在仓库里，托管在 netlify。清单带 sha256，下载后逐个核。
   2026-10-10 该站整站 503，下不到。那时改用 `previews-src/` 里的本地拼图切。
   拼图是 AI 生成的示意，不是上游样片。上游恢复后自动优先用真图。

现在 76 条全部有图。卡片不再有「无示意图」。

用法：
    python3 build_previews.py                # huashu 从本地克隆读
    python3 build_previews.py --huashu <路径> # 指定 huashu 克隆位置
输出：
    previews/<style-id>.jpg
只用标准库加 ffmpeg。ffmpeg 本来就是视频线的依赖。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "previews"
SRC = HERE / "previews-src"
DEFAULT_HUASHU = pathlib.Path(__file__).resolve().parents[1] / "engines" / "huashu"

# 上游单文件样片的直链。huashu 走本地克隆，这两个走网络。
REMOTE = {
    "lanshu-nine-styles.jpg": "https://raw.githubusercontent.com/cclank/lanshu-create-ai-presenter-video/main/explainer/gallery/nine-styles-kv-cache.jpg",
    "geeklee-whiteboard.png": "https://raw.githubusercontent.com/geeklee/srt-whiteboard-animation/main/examples/scene-01-monkey-mountain-banana.png",
}

# huashu 全风格总览的网格。原图 2936x1940。
# 6 列，列宽 488，内容从 x=4 起，宽 480。
# 6 行，第 1 行 y=36 起（跳过标题），其余行距 312。
COLS = [(i * 488 + 4, 480) for i in range(6)]
ROWS = [(36, 336)] + [(372 + 312 * i, 312) for i in range(5)]

# 网格位置 -> huashu 风格编号。编号来自样片自带的标签。
HUASHU_TILES = [
    (0, 0, 1), (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 20), (0, 5, 34),
    (1, 0, 5), (1, 1, 6), (1, 2, 32), (1, 3, 17), (1, 4, 8), (1, 5, 29),
    (2, 0, 9), (2, 1, 19), (2, 2, 10), (2, 3, 28), (2, 4, 36), (2, 5, 18),
    (3, 0, 11), (3, 1, 12), (3, 2, 22), (3, 3, 33), (3, 4, 23), (3, 5, 24),
    (4, 0, 30), (4, 1, 13), (4, 2, 21), (4, 3, 27), (4, 4, 31), (4, 5, 14),
    (5, 0, 25), (5, 1, 15), (5, 2, 26), (5, 3, 35), (5, 4, 16),
]

# huashu 动画语法样片：语法 id 后缀 -> 文件名
HUASHU_GRAMMAR = {
    "g-t1-3b1b": "t1_3b1b_总览.jpg",
    "g-t2-keynote-ui": "t2_keynote_ui_总览.jpg",
    "g-t3-finance-chart": "t3_finance_chart_总览.jpg",
    "g-y1-kurzgesagt": "y1_kurzgesagt_总览.jpg",
    "g-y2-vox": "y2_vox_总览.jpg",
    "g-y3-whiteboard": "y3_whiteboard_总览.jpg",
    "g-y4-storytime": "y4_storytime_总览.jpg",
    "g-y5-kinetic-type": "y5_kinetic_type_总览.jpg",
}

# lanshu 九风格图 1600x900，3x3。位置顺序就是 v1..v9。
LANSHU_TILE = 533
LANSHU_ROWS = [0, 300, 600]
LANSHU_ORDER = [
    "v1-editorial", "v2-signal", "v3-notebook",
    "v4-paper", "v5-comic", "v6-cinematic",
    "v7-drafting", "v8-chalkboard", "v9-clay",
]

# huashu 讲解员语法没有单张样片。角色对比图里有讲解员，用它当示意。
HUASHU_Y6_SRC = pathlib.Path("assets/角色/花叔形象_对比.jpg")
HUASHU_Y6_ID = "g-y6-presenter-explainer"

# handdrawn 21 条。图不在仓库里，清单给出 netlify 直链和 sha256。
HANDDRAWN_MANIFEST = "https://api.github.com/repos/threerocks/hand-drawn-styles/contents/assets/image-manifest.json"
HANDDRAWN = {
    "hd-01-xkcd": "examples/01-minimal-line.png",
    "hd-02-crayon-kid": "examples/02-crayon.png",
    "hd-03-ghibli": "examples/03-ghibli.png",
    "hd-04-bean-infographic": "examples/04-bean-doodle.png",
    "hd-05-mspaint": "examples/05-ms-paint.png",
    "hd-06-ballpoint-scribble": "examples/06-pen-scribble.png",
    "hd-07-crayon-photo": "examples/07-real-crayon.png",
    "hd-08-ink": "examples/08-ink-wash.png",
    "hd-09-pixel": "examples/09-pixel-art.png",
    "hd-10-soft-wash-sketch": "examples/10-emo-sketch.png",
    "hd-11-watercolor-concept": "examples/11-retro-concept.png",
    "hd-12-warm-concept": "examples/12-sunlit-storybook.png",
    "hd-13-paper-folk": "examples/13-paper-folk.png",
    "hd-14-nordic-storybook": "examples/14-nordic-storybook.png",
    "hd-15-softnose-vinyl": "examples/15-softnose-vinyl.png",
    "hd-16-gouache-spotlight": "examples/16-gouache-spotlight.png",
    "hd-17-inked-storybook": "examples/17-inked-storybook.png",
    "hd-18-warm-flat-storybook": "examples/18-warm-flat-storybook.png",
    "hd-19-roundhead-redline": "assets/style-19/anchor-roundhead-redline.png",
    "hd-20-warm-yellow-ink-story": "assets/style-20/anchor-warm-yellow-ink-story.png",
    "hd-31-crayon-scrawl": "assets/style-3.1/anchor-family.png",
}

# 上游图挂掉时的备用：本地拼图。AI 生成，一张装 9 格或 4 格。
# 每项 = (文件, 列边界, 行边界, 按阅读顺序的风格 id)。
# 边界是本机实测出来的，不是猜的：模型给的网格不是等分的。
HANDDRAWN_SHEETS = [
    ("handdrawn-a.jpg", [0, 512, 1024, 1536], [0, 512, 1024, 1536], [
        "hd-01-xkcd", "hd-02-crayon-kid", "hd-03-ghibli",
        "hd-04-bean-infographic", "hd-05-mspaint", "hd-06-ballpoint-scribble",
        "hd-07-crayon-photo", "hd-08-ink", "hd-09-pixel",
    ]),
    ("handdrawn-b.jpg", [0, 506, 1024, 1536], [0, 478, 990, 1536], [
        "hd-10-soft-wash-sketch", "hd-11-watercolor-concept", "hd-12-warm-concept",
        "hd-13-paper-folk", "hd-14-nordic-storybook", "hd-15-softnose-vinyl",
        "hd-16-gouache-spotlight", "hd-18-warm-flat-storybook", "hd-17-inked-storybook",
    ]),
    ("handdrawn-c.jpg", [0, 764, 1536], [0, 764, 1536], [
        "hd-19-roundhead-redline", "hd-20-warm-yellow-ink-story",
        "hd-31-crayon-scrawl", "presenter-digital-human",
    ]),
]

# 切格时四边各让几像素，免得把邻格的白边切进来。
INSET = 6

MAX_W = 640


def dims(src: pathlib.Path) -> tuple[int, int]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(src)],
                       capture_output=True, text=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def crop(src: pathlib.Path, dst: pathlib.Path, box: tuple[int, int, int, int] | None) -> None:
    """box = (top, left, height, width)。None 表示整张，只缩不放。

    用 ffmpeg 而不是 sips。sips 的 --cropOffset 在本机实测会静默失效：
    同一条命令，有时裁对，有时原图返回。ffmpeg 的 crop 每次都准。
    ffmpeg 本来就是视频线的依赖，见 compose.py。
    """
    if box is None:
        vf = f"scale={MAX_W}:-2"
    else:
        top, left, h, w = box
        h -= h % 2
        w -= w % 2
        vf = f"crop={w}:{h}:{left}:{top},scale={MAX_W}:-2"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                        "-vf", vf, "-q:v", "3", str(dst)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败: {src}\n{r.stderr.strip()}")


def download(url: str, dst: pathlib.Path, tries: int = 3, raw: bool = False) -> pathlib.Path:
    """下载到 dst。失败重试。上游偶发超时，一次失败不代表没有。

    raw=True 走 GitHub 内容接口，要带 Accept 头才拿得到文件正文，
    否则拿到的是带 base64 的 JSON 外壳。
    """
    cmd = ["curl", "-sSL", "--http1.1", "-m", "60", "-o", str(dst)]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    cmd.append(url)
    for i in range(1, tries + 1):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return dst
        print(f"  第 {i} 次失败，重试")
    raise RuntimeError(f"下载失败 {url}")


def fetch(name: str, cache: pathlib.Path) -> pathlib.Path:
    dst = cache / name
    if not dst.exists():
        print(f"  下载 {name}")
        download(REMOTE[name], dst)
    return dst


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def from_netlify(made: set[str]) -> bool:
    """试上游真图。全部成功才返回 True。任何一个拿不到就整体放弃。"""
    cache = pathlib.Path(tempfile.gettempdir())
    man_path = cache / "hd-image-manifest.json"
    try:
        if man_path.exists() and "base_url" not in man_path.read_text(encoding="utf-8")[:200]:
            man_path.unlink()
        if not man_path.exists():
            download(HANDDRAWN_MANIFEST, man_path, raw=True)
        man = json.loads(man_path.read_text(encoding="utf-8"))
        base = man["base_url"].rstrip("/")
    except Exception as exc:  # 网络问题不该让整条链停
        print(f"  清单取不到：{exc}")
        return False
    for sid, key in HANDDRAWN.items():
        meta = man["images"].get(key)
        if not meta:
            print(f"  清单里没有 {key}")
            return False
        dst = cache / ("hd-" + pathlib.Path(key).name)
        try:
            if not dst.exists():
                print(f"  下载 {pathlib.Path(key).name}")
                download(f"{base}/{key}", dst)
            if sha256(dst) != meta["sha256"]:
                dst.unlink()
                download(f"{base}/{key}", dst)
            if sha256(dst) != meta["sha256"]:
                print(f"  sha256 校验不过：{key}")
                return False
        except Exception as exc:
            print(f"  下载失败：{key} {exc}")
            return False
        crop(dst, OUT / f"{sid}.jpg", None)
        made.add(sid)
    return True


def from_sheets(made: set[str]) -> None:
    """用 previews-src/ 里的本地拼图切。"""
    for name, cols, rows, sids in HANDDRAWN_SHEETS:
        src = SRC / name
        if not src.exists():
            print(f"  缺 {src}")
            continue
        per_row = len(cols) - 1
        for i, sid in enumerate(sids):
            r, c = divmod(i, per_row)
            top = rows[r] + INSET
            left = cols[c] + INSET
            h = rows[r + 1] - INSET - top
            w = cols[c + 1] - INSET - left
            crop(src, OUT / f"{sid}.jpg", (top, left, h, w))
            made.add(sid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--huashu", default=str(DEFAULT_HUASHU),
                    help="huashu-art-motion 克隆位置")
    args = ap.parse_args()
    huashu = pathlib.Path(args.huashu)

    reg = json.loads((HERE / "video-styles.json").read_text(encoding="utf-8"))
    ids = {s["id"] for s in reg["styles"]} | {g["id"] for g in reg["grammars"]}
    by_num = {}
    for s in reg["styles"]:
        if s["id"].startswith("h-"):
            by_num[int(s["id"].split("-")[1])] = s["id"]

    if not OUT.exists():
        OUT.mkdir(parents=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()

    made: set[str] = set()

    # 1. huashu 全风格总览
    overview = huashu / "assets" / "全风格总览.jpg"
    if overview.exists():
        print("huashu 全风格总览")
        for row, col, num in HUASHU_TILES:
            sid = by_num.get(num)
            if not sid:
                print(f"  跳过 编号 {num}：video-styles.json 里没有")
                continue
            top, h = ROWS[row]
            left, w = COLS[col]
            crop(overview, OUT / f"{sid}.jpg", (top, left, h, w))
            made.add(sid)
    else:
        print(f"缺 {overview}，跳过 35 段艺术风格", file=sys.stderr)

    # 2. huashu 动画语法样片
    # 原图是一长条，横向并排放 4 个镜头，比例约 5:1。整条塞进卡片会小到看不清。
    # 所以只取最左边一个镜头，再切掉顶部的标题条。
    gram = huashu / "assets" / "动画语法"
    if gram.exists():
        print("huashu 动画语法")
        for sid, fname in HUASHU_GRAMMAR.items():
            src = gram / fname
            if not src.exists():
                print(f"  缺 {fname}")
                continue
            w, h = dims(src)
            top = round(h * 0.09)
            crop(src, OUT / f"{sid}.jpg", (top, 0, h - top, round(w * 0.26)))
            made.add(sid)

    # 3. huashu 讲解员语法。没有单张样片，用角色对比图。
    y6 = huashu / HUASHU_Y6_SRC
    if y6.exists():
        print("huashu 讲解员（角色对比图）")
        crop(y6, OUT / f"{HUASHU_Y6_ID}.jpg", None)
        made.add(HUASHU_Y6_ID)

    # 4. lanshu 九风格
    print("lanshu 九风格")
    lanshu = fetch("lanshu-nine-styles.jpg", pathlib.Path(tempfile.gettempdir()))
    for i, sid in enumerate(LANSHU_ORDER):
        top = LANSHU_ROWS[i // 3]
        left = LANSHU_TILE * (i % 3)
        w = 1600 - left if i % 3 == 2 else LANSHU_TILE
        crop(lanshu, OUT / f"{sid}.jpg", (top, left, 300, w))
        made.add(sid)

    # 5. geeklee 白板
    print("geeklee 白板")
    geek = fetch("geeklee-whiteboard.png", pathlib.Path(tempfile.gettempdir()))
    crop(geek, OUT / "wb-stream-whiteboard.jpg", None)
    made.add("wb-stream-whiteboard")

    # 6. handdrawn 21 条。先试上游真图，拿不到就用本地拼图。
    print("handdrawn 21 条")
    if not from_netlify(made):
        print("  上游不可用，改用本地拼图")
        from_sheets(made)

    missing = sorted(ids - made)
    print(f"\n出图 {len(made)} 张，无图 {len(missing)} 条")
    if missing:
        print("无图条目：", " ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
