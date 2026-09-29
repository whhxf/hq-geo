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
import json
import os
import sys
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


def generate_one(prompt: dict, size: str, api_key: str) -> list:
    """调一次模型，等它跑完，返回图片 URL 列表。"""
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

    if args.dry_run:
        for item, prompt in planned:
            print(f"=== {item['id']} · {item['role']} · {item['size']} · {item['style_id']}")
            print(prompt["prompt"])
            print(f"--- 负面：{prompt['negative_prompt']}\n")
        print("以上是 dry-run，没有调用模型，没有花钱。")
        return 0

    api_key = resolve_api_key()
    project = find_project()
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
        for index, url in enumerate(generate_one(prompt, item["size"], api_key), start=1):
            suffix = f"-{index}" if index > 1 else ""
            dest = out_dir / f"{item['id']}{suffix}.png"
            download(url, dest)
            manifest["outputs"].append({
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
            })
            print(f"  → {dest}")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(planned)} 张出完，回执写在 {manifest_path}")
    print("**生成的图 synthetic=true，不能当产品界面、客户案例或真实记录用。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
