"""项目根解析。

系统和项目分成两个根之后，这是唯一知道「项目在哪」的地方。
所有要读写实例层的脚本都从这里取路径，不自己拼。

优先级：显式参数 > 环境变量 `HQ_GEO_PROJECT` > 从当前目录向上找标记文件。

## 脚本怎么用

系统层的脚本和测试可能从任何位置被调用（门禁、直接跑、子进程），
`sys.path[0]` 不一定是系统根，所以每个要碰实例层的脚本自己带这段引导：

    import sys
    from pathlib import Path

    _SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
    if _SYSTEM is None:
        raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
    sys.path.insert(0, str(_SYSTEM))
    from project import find_project  # noqa: E402

**不要在 import 时调用 find_project()。** 放到真正要读实例层的函数里调用——
否则单测 import 一个纯函数，也得先存在一个项目。
"""

import os
from pathlib import Path


SYSTEM_ROOT = Path(__file__).resolve().parent
MARKER = ".hq-geo.json"

USAGE = (
    "找不到项目根。三种办法：\n"
    "  1. cd 到项目目录再跑\n"
    "  2. 加参数 --project <项目目录>\n"
    "  3. 设环境变量 HQ_GEO_PROJECT=<项目目录>"
)


def is_project(path: Path) -> bool:
    return (path / MARKER).is_file()


def find_project(explicit=None) -> Path:
    """返回项目根。找不到就停下来说清楚下一步，不抛裸异常让人猜。"""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not is_project(path):
            raise SystemExit(
                f"不是 hq-geo 项目（缺少 {MARKER}）：{path}\n"
                f"新建项目：python3 {SYSTEM_ROOT}/capabilities/project-scaffold/scripts/init_project.py {path}"
            )
        return path

    raw = os.environ.get("HQ_GEO_PROJECT")
    if raw:
        return find_project(raw)

    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if is_project(candidate):
            return candidate

    raise SystemExit(f"{USAGE}\n"
                     f"新建项目：python3 {SYSTEM_ROOT}/capabilities/project-scaffold/scripts/init_project.py <目标目录>")
