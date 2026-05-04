#!/usr/bin/env python3
"""
prompt_render.py
模板占位符替换工具。读取模板文件和数据字典，生成最终 prompt。

用法：
  python lib/prompt_render.py --template templates/scenario.md \
      --data '{"BRAND":"Accio","YEAR":"2026","TITLE":"..."}'

或在 Python 代码中调用：
  from lib.prompt_render import render
  result = render("templates/scenario.md", {"BRAND": "Accio", ...})
"""

import argparse
import json
import os
import re
import sys


def load_yaml_simple(path: str) -> dict:
    """
    极简 YAML 解析器（最多 2 层嵌套）。
    不支持列表/锚点/多行字符串。
    """
    result = {}
    current_key = None
    current_dict = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.startswith("#"):
                continue

            # 检查缩进
            indent = len(line) - len(line.lstrip())

            if indent == 0:
                # 顶层键
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if val:
                        result[key] = val
                        current_key = None
                        current_dict = None
                    else:
                        # 嵌套字典开始
                        result[key] = {}
                        current_key = key
                        current_dict = result[key]
            elif indent > 0 and current_dict is not None:
                # 子键
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    key = key.strip().strip("-").strip()
                    val = val.strip().strip('"').strip("'")
                    current_dict[key] = val

    return result


def render(template_path: str, data: dict) -> str:
    """
    读取模板文件，将 {{KEY}} 占位符替换为 data 中对应值。
    未匹配的占位符保持原样。
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    def replace_match(match):
        key = match.group(1)
        return str(data.get(key, match.group(0)))

    return re.sub(r"\{\{(\w+)\}\}", replace_match, content)


def render_from_config(template_path: str, config_path: str) -> str:
    """
    从 YAML 配置文件加载数据，渲染模板。
    """
    config = load_yaml_simple(config_path)
    # 扁平化嵌套字典
    flat_data = {}
    for key, val in config.items():
        if isinstance(val, dict):
            for sub_key, sub_val in val.items():
                flat_data[f"{key.upper()}_{sub_key.upper()}"] = sub_val
        else:
            flat_data[key.upper()] = val
    return render(template_path, flat_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="模板占位符替换工具")
    parser.add_argument("--template", required=True, help="模板文件路径")
    parser.add_argument("--data", default="", help="JSON 格式的数据字典")
    parser.add_argument("--config", default="", help="YAML 配置文件路径（与 --data 二选一）")
    args = parser.parse_args()

    if args.config:
        result = render_from_config(args.template, args.config)
    elif args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(1)
        result = render(args.template, data)
    else:
        print("必须提供 --data 或 --config 参数", file=sys.stderr)
        sys.exit(1)

    print(result)
