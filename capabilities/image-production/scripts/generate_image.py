#!/usr/bin/env python3
"""按图片简报出图：组装 prompt → 调模型 → 把图存回项目根。

**这不是图片编辑工具。** 图片线是强依赖 AI 生成的——不做图层、不做涂抹，
做的是把「要什么」说清楚，交给模型一步出图。

模型走 DashScope 的 `wan2.7-image-pro`（异步 HTTP）。密钥来源见 `resolve_api_key()`，
**密钥不进代码，也不读 Vidmix 的数据库**——读那个就是刚要去掉的耦合。

用法：

    # 先看组装出来的 prompt，不花钱
    python3 capabilities/image-production/scripts/generate_image.py --brief <brief.json> --dry-run

    # 真出图
    python3 capabilities/image-production/scripts/generate_image.py --brief <brief.json>

    # 只出某一张
    python3 capabilities/image-production/scripts/generate_image.py --brief <brief.json> --only d1
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
from project import find_project  # noqa: E402

MODEL = "wan2.7-image-pro"
CREATE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
CONFIG_PATH = Path.home() / ".config" / "hq-geo" / "image.json"
STYLE_LIBRARY = _SYSTEM / "capabilities/image-production/styles/image-styles.json"

POLL_INTERVAL = 3
POLL_TIMEOUT = 300


def resolve_api_key() -> str:
    """密钥从哪来。顺序：环境变量 → 本地配置文件。

    报错时要说清楚去哪配，不能只说「没有 key」——那是让用户自己猜。
    """
    for name in ("HQ_GEO_IMAGE_API_KEY", "DASHSCOPE_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    if CONFIG_PATH.is_file():
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("api_key", "").strip()
        if value:
            return value
    raise SystemExit(
        "找不到出图的 API Key。二选一：\n"
        f"  1. 建 {CONFIG_PATH}，内容 {{\"api_key\": \"sk-...\"}}\n"
        "  2. 或者 export HQ_GEO_IMAGE_API_KEY=sk-...\n"
        "密钥不写进代码，也不进 git。"
    )


def load_styles() -> dict:
    library = json.loads(STYLE_LIBRARY.read_text(encoding="utf-8"))
    return {item["id"]: item for item in library["styles"]}


def assemble_prompt(deliverable: dict, style: dict) -> dict:
    """把一条交付物和一套风格组装成模型能吃的 prompt。

    顺序是固定的：**先风格、再画面、最后构图意图**。
    风格放最前面，是因为它管的是「这张图属于哪一套」——
    放后面会被画面描述盖过去，一套图就会漂成十四种样子。
    """
    parts = [
        style["prompt"]["prefix"],
        deliverable["subject"],
    ]
    if deliverable.get("intent"):
        parts.append(deliverable["intent"])
    # 参考图的用法说明排在最后。万相 2.7 的多图参考是**生成+编辑**模型，
    # 不说清「参考它的什么」，它可能把参考图当成待编辑对象——
    # 于是你得到一张「改了一下的参考图」而不是「一张新图」。
    if deliverable.get("reference_instruction"):
        parts.append(deliverable["reference_instruction"])
    negative = style["prompt"].get("negative", "")
    if deliverable.get("avoid"):
        negative = "、".join(filter(None, [negative, deliverable["avoid"]]))
    return {
        "prompt": "\n".join(part for part in parts if part),
        "negative_prompt": negative,
        "style": style.get("image_style_enum", ""),
    }


def _post(url: str, payload: dict, api_key: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-Async": "enable",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(url: str, api_key: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def image_urls(payload: dict) -> list:
    """从任务结果里取图片地址。新旧两种响应格式都要认。

    只认新格式的话，DashScope 换过一次响应结构就会静默返回空列表——
    然后你会以为「模型没出图」，其实是解析没跟上。
    """
    output = payload.get("output", {})
    urls = []
    for choice in output.get("choices", []):
        for item in choice.get("message", {}).get("content", []):
            if item.get("image"):
                urls.append(item["image"])
    for item in output.get("results", []):
        if item.get("url"):
            urls.append(item["url"])
    return urls


def build_payload(prompt: dict, size: str, reference_images=(), color_palette=None) -> dict:
    """组装请求体。**纯函数**，不发网络——这样「向后兼容」才能被测试断言。

    `reference_images` / `color_palette` 缺省时，返回值与没有这个功能时
    逐字节相同：既有简报的行为一点不变。这是本功能最容易被破坏的地方，
    所以它必须有一条能红的测试盯着（见 `tests/test_palette.py`）。
    """
    payload = {
        "model": MODEL,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt["prompt"]}]}]},
        "parameters": {
            "size": size,
            "n": 1,
            "watermark": False,
            "negative_prompt": prompt["negative_prompt"],
        },
    }
    if prompt.get("style"):
        payload["parameters"]["style"] = prompt["style"]
    if reference_images:
        payload["input"]["messages"][0]["content"].extend(
            {"image": data_uri} for data_uri in reference_images
        )
    if color_palette:
        payload["parameters"]["color_palette"] = color_palette
    return payload


def generate_one(prompt: dict, size: str, api_key: str,
                 reference_images: tuple = (), color_palette=None) -> list:
    """调一次模型，等它跑完，返回图片 URL 列表。"""
    payload = build_payload(prompt, size, reference_images, color_palette)

    task = _post(CREATE_URL, payload, api_key)
    task_id = task.get("output", {}).get("task_id")
    if not task_id:
        raise SystemExit(f"创建任务失败：{json.dumps(task, ensure_ascii=False)}")

    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        result = _get(TASK_URL.format(task_id=task_id), api_key)
        status = result.get("output", {}).get("task_status")
        if status == "SUCCEEDED":
            urls = image_urls(result)
            if not urls:
                raise SystemExit(f"任务成功但解析不出图片地址：{json.dumps(result, ensure_ascii=False)}")
            return urls
        if status == "FAILED":
            raise SystemExit(f"出图失败：{json.dumps(result.get('output', {}), ensure_ascii=False)}")
    raise SystemExit(f"等了 {POLL_TIMEOUT} 秒还没出图，task_id={task_id}（它 24 小时内还能查）")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        dest.write_bytes(response.read())


# --- 参考图 ---------------------------------------------------------------

# 参考图的边长下限与上限，来自 DashScope 对输入图的规定。
MIN_REFERENCE_EDGE = 240
MAX_REFERENCE_EDGE = 8000

# 超过这个字节数就先缩一道。一张 8 MB 的图 base64 之后是 11 MB，
# 塞进请求体大概率被拒——而那是在**花了时间之后**才发现。
MAX_REFERENCE_BYTES = 4 * 1024 * 1024
_DOWNSCALE_EDGE = 2048


def _read_size_png(path: Path):
    """只读 PNG 头拿宽高。非 PNG 返回 None（尺寸交给 sips 处理）。"""
    try:
        header = path.read_bytes()[:33]
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    import struct
    return struct.unpack(">II", header[16:24])


def _downscale(path: Path) -> bytes:
    """借 `sips` 缩图，返回缩放后的 PNG 字节。

    参考图是用户随手丢进来的，尺寸和体积都不受控。**把复杂度留在系统里**：
    用户不该为了「图太大」去自己开工具改尺寸。
    """
    sips = shutil.which("sips")
    if sips is None:
        raise SystemExit(
            f"参考图 {path.name} 需要缩小，但本机没有 `sips`。"
            f"请把它压到 {MAX_REFERENCE_BYTES // 1024 // 1024} MB 以内或长边 {_DOWNSCALE_EDGE} 像素以内再试。"
        )
    with tempfile.TemporaryDirectory() as workdir:
        target = Path(workdir) / "scaled.png"
        result = subprocess.run(
            [sips, "-s", "format", "png", "-Z", str(_DOWNSCALE_EDGE), str(path), "--out", str(target)],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not target.exists():
            raise SystemExit(f"`sips` 缩小 {path.name} 失败：{(result.stderr or '').strip()[:200]}")
        return target.read_bytes()


def resolve_reference_images(deliverable: dict, project: Path) -> tuple:
    """把简报里的参考图路径读成 data URI。返回 `(data_uris, notes)`。

    路径按**项目根相对**解析，并且**必须在项目根之内**——参考图大概率不是
    自己拍的，越出项目根去读任意路径既没有权利登记也说不清来源。
    """
    paths = deliverable.get("reference_images") or []
    if not paths:
        return (), []

    root = project.resolve()
    uris = []
    notes = []
    for raw in paths:
        candidate = (root / raw).resolve()
        if not candidate.is_relative_to(root):
            raise SystemExit(f"{deliverable['id']}: 参考图 {raw} 指向项目根之外，不允许。")
        if not candidate.is_file():
            raise SystemExit(f"{deliverable['id']}: 参考图不存在：{raw}")

        size = _read_size_png(candidate)
        if size and (min(size) < MIN_REFERENCE_EDGE or max(size) > MAX_REFERENCE_EDGE):
            raise SystemExit(
                f"{deliverable['id']}: 参考图 {raw} 是 {size[0]}x{size[1]}，"
                f"边长必须落在 {MIN_REFERENCE_EDGE}–{MAX_REFERENCE_EDGE} 之间。"
                f"用 `sips -Z {_DOWNSCALE_EDGE} {raw} --out {raw}` 调一下。"
            )

        payload = candidate.read_bytes()
        if len(payload) > MAX_REFERENCE_BYTES:
            payload = _downscale(candidate)
            notes.append(f"{candidate.name} 超过 {MAX_REFERENCE_BYTES // 1024 // 1024} MB，"
                         f"已在发送前缩小到长边 {_DOWNSCALE_EDGE}")
        uris.append("data:image/png;base64," + base64.b64encode(payload).decode("ascii"))
    return tuple(uris), notes


def load_color_palette(palette_ref: str, project: Path) -> list:
    """从 `measure_palette.py` 的输出里取 DashScope 色板参数。

    `measure_palette.py` 已经把 `dashscope_color_palette` 算好了
    （比例用最大余数法精确合计 100.00%），这里**不重新算**——
    重算就是又一处可能和测量结果对不上的地方。
    """
    path = (project.resolve() / palette_ref).resolve()
    if not path.is_file():
        raise SystemExit(f"palette_ref 指向的文件不存在：{palette_ref}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"palette_ref 不是合法 JSON：{palette_ref}（{error}）")
    palette = data.get("dashscope_color_palette") if isinstance(data, dict) else None
    if not palette:
        raise SystemExit(
            f"{palette_ref} 里没有 `dashscope_color_palette`（颜色少于 3 种时不会有）。"
            "参考图量出的颜色不足 3 种，无法作为 color_palette 参数使用。"
        )
    return palette


def main() -> int:
    parser = argparse.ArgumentParser(description="按图片简报出图")
    parser.add_argument("--brief", required=True, help="图片简报路径")
    parser.add_argument("--only", default="", help="只出某一张（deliverable id）")
    parser.add_argument("--dry-run", action="store_true", help="只打印组装好的 prompt，不调模型")
    args = parser.parse_args()

    brief_path = Path(args.brief).resolve()
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    styles = load_styles()

    targets = [
        item for item in brief["deliverables"]
        if not args.only or item["id"] == args.only
    ]
    if not targets:
        print(f"没有匹配的图：--only {args.only}")
        return 1

    planned = []
    for item in targets:
        style_id = item.get("style_id")
        if style_id not in styles:
            print(f"{item['id']}: 没有 style_id 或不在风格库里（{style_id!r}）。先选风格再出图。")
            return 1
        planned.append((item, assemble_prompt(item, styles[style_id])))

    # 参考图和色板要在 dry-run 阶段就读出来并打印——**钱是在 dry-run 之后花的**，
    # 参考图读不到、色板格式不对这类事必须在这之前暴露。
    project = None
    resolved = {}
    if any(item.get("reference_images") or item.get("palette_ref") for item, _ in planned):
        project = find_project()
        for item, _ in planned:
            uris, notes = resolve_reference_images(item, project)
            palette = load_color_palette(item["palette_ref"], project) if item.get("palette_ref") else None
            resolved[item["id"]] = (uris, notes, palette)

    if args.dry_run:
        for item, prompt in planned:
            print(f"=== {item['id']} · {item['role']} · {item['size']} · {item['style_id']}")
            print(prompt["prompt"])
            print(f"--- 负面：{prompt['negative_prompt']}")
            uris, notes, palette = resolved.get(item["id"], ((), [], None))
            if uris:
                print(f"--- 参考图：{len(uris)} 张（{', '.join(item['reference_images'])}）")
            if palette:
                print("--- 色板：" + "  ".join(f"{c['hex']} {c['ratio']}" for c in palette))
            for note in notes:
                print(f"--- 注意：{note}")
            print()
        print("以上是 dry-run，没有调用模型，没有花钱。")
        return 0

    api_key = resolve_api_key()
    project = project or find_project()
    out_dir = project / "assets" / "generated" / brief["id"]
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {
        "schema_version": 1,
        "brief_id": brief["id"],
        "model": MODEL,
        "outputs": [],
    }

    for item, prompt in planned:
        print(f"出图 {item['id']} · {item['role']} …")
        uris, notes, palette = resolved.get(item["id"], ((), [], None))
        for index, url in enumerate(
            generate_one(prompt, item["size"], api_key, uris, palette), start=1
        ):
            suffix = f"-{index}" if index > 1 else ""
            dest = out_dir / f"{item['id']}{suffix}.png"
            download(url, dest)
            record = {
                "deliverable_id": item["id"],
                "role": item["role"],
                "path": str(dest),
                "style_id": item["style_id"],
                "size": item["size"],
                "synthetic": True,
                "prompt": prompt["prompt"],
                "negative_prompt": prompt["negative_prompt"],
                "model": MODEL,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            # 只在真用了参考图/色板时才写这几个字段——**没用到的简报，
            # 回执与改造前逐字节相同**，不会给旧产物平添噪声。
            if item.get("reference_images"):
                record["reference_images"] = list(item["reference_images"])
                record["reference_instruction"] = item.get("reference_instruction", "")
            if palette:
                record["palette_ref"] = item["palette_ref"]
                record["color_palette"] = palette
            if notes:
                record["reference_notes"] = list(notes)
            manifest["outputs"].append(record)
            print(f"  → {dest}")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(planned)} 张出完，回执写在 {manifest_path}")
    print("**生成的图 synthetic=true，不能当产品界面、客户案例或真实记录用。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
