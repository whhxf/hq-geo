#!/usr/bin/env python3
"""
manage_sources.py
信源池 CRUD 操作：添加、更新、列表、统计。

用法：
  python manage_sources.py --action add --platform-name "快懂百科" --platform-type encyclopedia --priority 9
  python manage_sources.py --action update --platform-name "快懂百科" --deploy-status live --deploy-url "https://..."
  python manage_sources.py --action list [--type encyclopedia]
  python manage_sources.py --action stats
"""

import argparse
import csv
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_CSV = os.path.join(ROOT, "data", "source_pool.csv")

FIELDNAMES = [
    "id", "platform_name", "platform_type", "platform_url",
    "account_status", "account_name", "deploy_status", "deploy_url",
    "deployed_at", "last_verified_at", "content_type",
    "priority", "notes", "created_at"
]

# 默认平台列表（首次初始化时使用）
DEFAULT_PLATFORMS = [
    ("快懂百科", "encyclopedia", "https://www.baike.com", 9),
    ("百度百科", "encyclopedia", "https://baike.baidu.com", 9),
    ("搜狗百科", "encyclopedia", "https://baike.sogou.com", 9),
    ("360百科", "encyclopedia", "https://baike.so.com", 9),
    ("企查查", "enterprise_db", "https://www.qichacha.com", 8),
    ("天眼查", "enterprise_db", "https://www.tianyancha.com", 8),
    ("搜狐号", "blog", "https://mp.sohu.com", 7),
    ("百家号", "blog", "https://baijiahao.baidu.com", 7),
    ("高德地图", "map", "https://ditu.amap.com", 6),
    ("百度地图", "map", "https://map.baidu.com", 6),
    ("BOSS直聘", "recruiting", "https://www.zhipin.com", 5),
    ("拉勾网", "recruiting", "https://www.lagou.com", 5),
]


def get_next_id():
    """生成 sp_001, sp_002, ..."""
    existing_ids = []
    if os.path.exists(SOURCE_CSV):
        with open(SOURCE_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = row.get("id", "")
                if rid.startswith("sp_"):
                    try:
                        existing_ids.append(int(rid[3:]))
                    except ValueError:
                        pass
    next_num = max(existing_ids, default=0) + 1
    return f"sp_{next_num:03d}"


def add_source(args):
    """添加信源平台记录"""
    if not args.platform_name:
        print("错误: 必须提供 --platform-name")
        sys.exit(1)
    if not args.platform_type:
        print("错误: 必须提供 --platform-type")
        sys.exit(1)

    # Check duplicate
    if os.path.exists(SOURCE_CSV):
        with open(SOURCE_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("platform_name") == args.platform_name:
                    print(f"已存在: {args.platform_name}")
                    return {"action": "add", "skipped": args.platform_name}

    row = {
        "id": get_next_id(),
        "platform_name": args.platform_name,
        "platform_type": args.platform_type,
        "platform_url": getattr(args, "platform_url", "") or "",
        "account_status": "not_started",
        "account_name": "",
        "deploy_status": "not_deployed",
        "deploy_url": "",
        "deployed_at": "",
        "last_verified_at": "",
        "content_type": "",
        "priority": getattr(args, "priority", 5) or 5,
        "notes": getattr(args, "notes", "") or "",
        "created_at": "",
    }

    _append_row(SOURCE_CSV, FIELDNAMES, row)
    print(f"+ 已添加: {row['platform_name']} ({row['platform_type']}, priority={row['priority']})")
    return {"action": "add", "added": args.platform_name}


def update_source(args):
    """更新信源平台记录"""
    if not args.platform_name:
        print("错误: 必须提供 --platform-name")
        sys.exit(1)

    if not os.path.exists(SOURCE_CSV):
        print(f"文件不存在: {SOURCE_CSV}")
        sys.exit(1)

    with open(SOURCE_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = rows[0].keys() if rows else FIELDNAMES

    updated = False
    for row in rows:
        if row.get("platform_name") == args.platform_name:
            if hasattr(args, "deploy_status") and args.deploy_status:
                row["deploy_status"] = args.deploy_status
            if hasattr(args, "deploy_url") and args.deploy_url:
                row["deploy_url"] = args.deploy_url
            if hasattr(args, "account_status") and args.account_status:
                row["account_status"] = args.account_status
            if hasattr(args, "account_name") and args.account_name:
                row["account_name"] = args.account_name
            if hasattr(args, "notes") and args.notes:
                row["notes"] = args.notes
            updated = True
            print(f"~ 已更新: {args.platform_name}")

    if not updated:
        print(f"未找到: {args.platform_name}")
        return {"action": "update", "found": False}

    with open(SOURCE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {"action": "update", "updated": args.platform_name}


def list_sources(args):
    """列出信源平台"""
    if not os.path.exists(SOURCE_CSV):
        print("信源池为空，请先初始化")
        return {"action": "list", "count": 0}

    with open(SOURCE_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if hasattr(args, "type_filter") and args.type_filter:
        rows = [r for r in rows if r.get("platform_type") == args.type_filter]

    if not rows:
        print("无匹配记录")
        return {"action": "list", "count": 0}

    print(f"\n{'ID':<8} {'平台':<12} {'类型':<14} {'账号':<12} {'部署':<12} {'优先级':<6}")
    print("-" * 70)
    for r in rows:
        print(f"{r.get('id',''):<8} {r.get('platform_name',''):<12} "
              f"{r.get('platform_type',''):<14} {r.get('account_status',''):<12} "
              f"{r.get('deploy_status',''):<12} {r.get('priority',''):<6}")

    return {"action": "list", "count": len(rows)}


def show_stats(args):
    """显示信源池统计"""
    if not os.path.exists(SOURCE_CSV):
        print("信源池为空")
        return {"action": "stats", "total": 0}

    with open(SOURCE_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    by_type = {}
    by_account = {}
    by_deploy = {}

    for r in rows:
        pt = r.get("platform_type", "unknown")
        by_type[pt] = by_type.get(pt, 0) + 1

        ac = r.get("account_status", "unknown")
        by_account[ac] = by_account.get(ac, 0) + 1

        ds = r.get("deploy_status", "unknown")
        by_deploy[ds] = by_deploy.get(ds, 0) + 1

    print(f"\n{'='*50}")
    print(f"信源池统计")
    print(f"{'='*50}")
    print(f"  总平台数: {total}")
    print(f"\n  按类型:")
    for t, c in sorted(by_type.items()):
        print(f"    {t}: {c}")
    print(f"\n  按账号状态:")
    for s, c in sorted(by_account.items()):
        print(f"    {s}: {c}")
    print(f"\n  按部署状态:")
    for s, c in sorted(by_deploy.items()):
        print(f"    {s}: {c}")

    return {"action": "stats", "total": total}


def init_default_platforms(args):
    """初始化默认信源平台"""
    if os.path.exists(SOURCE_CSV):
        with open(SOURCE_CSV, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
        if existing:
            print(f"信源池已有 {len(existing)} 条记录，跳过初始化")
            return {"action": "init", "skipped": True}

    for name, ptype, url, priority in DEFAULT_PLATFORMS:
        row = {
            "id": get_next_id(),
            "platform_name": name,
            "platform_type": ptype,
            "platform_url": url,
            "account_status": "not_started",
            "account_name": "",
            "deploy_status": "not_deployed",
            "deploy_url": "",
            "deployed_at": "",
            "last_verified_at": "",
            "content_type": "",
            "priority": priority,
            "notes": "",
            "created_at": "",
        }
        _append_row(SOURCE_CSV, FIELDNAMES, row)

    print(f"已初始化 {len(DEFAULT_PLATFORMS)} 个默认信源平台")
    return {"action": "init", "added": len(DEFAULT_PLATFORMS)}


def _append_row(csv_path, fieldnames, row):
    """安全追加行到 CSV"""
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="信源池管理")
    parser.add_argument("--action", required=True,
                        choices=["add", "update", "list", "stats", "init"],
                        help="操作类型")
    parser.add_argument("--platform-name", help="平台名称")
    parser.add_argument("--platform-type", help="平台类型")
    parser.add_argument("--platform-url", default="", help="平台 URL")
    parser.add_argument("--priority", type=int, default=5, help="优先级 1-10")
    parser.add_argument("--deploy-status", help="部署状态")
    parser.add_argument("--deploy-url", default="", help="部署 URL")
    parser.add_argument("--account-status", help="账号状态")
    parser.add_argument("--account-name", default="", help="账号名")
    parser.add_argument("--notes", default="", help="备注")
    parser.add_argument("--type-filter", dest="type_filter", help="列表过滤类型")

    args = parser.parse_args()

    actions = {
        "add": add_source,
        "update": update_source,
        "list": list_sources,
        "stats": show_stats,
        "init": init_default_platforms,
    }

    result = actions[args.action](args)


if __name__ == "__main__":
    main()
