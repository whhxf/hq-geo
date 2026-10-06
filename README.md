# HQ Content Engine

> 文件夹即应用，对话即操作，Markdown 即产物。

把对话里冒出来的想法，变成能署名发出去的稿子。

当前分发渠道：微信视频号、抖音、小红书、自有博客、新闻网站或行业媒体。

## 这是什么 / 不是什么

- **是**：一套跑在本地的、可复制的创作方法。方法在 `capabilities/`，Skill 在 `skills/`。
- **不是**：SaaS、数据库、任务队列、自动发布工具。
- **主入口**：跟 Claude 说话。
- **运行时依赖**：Python 3 标准库。没有 `pip install`，没有 `npm install`。

## 系统和项目是两个根

**这个仓库是系统，不是项目。** 它只放方法、流程和校验器，一份，所有项目共用。

内容和事实住在**项目根**里——每个项目一个文件夹，位置随便你放，靠根目录的 `.hq-geo.json` 认出来。
现有项目：`/Users/conan/kingsway/kingswaywork/05kingsway运营动作/视频画册推广`。

分开的理由：只有在不同项目里跑同一套系统，才看得出哪些是方法的问题、哪些是这一个项目的问题。

```bash
# 新建一个项目
python3 capabilities/project-scaffold/scripts/init_project.py <目标目录>
```

已经存在的文件一律不动，只报告跳过。所以在一个已经有东西的目录里跑也是安全的。

## 设计否决规则

八条宪法在 `AGENTS.md` 顶部，优先级高于其余全部条款。最常被违反的两条：

- **价值等于署名产物。** 系统的价值是能交出去的稿子，不是系统本身。
- **满三次重复才自动化，默认减法。** 只做一次的事不要写代码。

## 快速开始

不需要配置环境。**cd 到项目根**，然后直接说：

- "我有个想法：……"
- "推进 tasks/xxx"
- "跑门禁"

**完整使用方法、系统的自我迭代结构和当前进度，见 [PLAYBOOK.md](PLAYBOOK.md)。** 本文件只讲项目是什么。

编排器 `skills/content-orchestrator/SKILL.md` 会判断走哪条流程。普通社交内容不加载完整 GEO 流程。

联网搜索、网页读取和平台操作**优先用 `ego-browser`**，跑不通时退回 `web-access`（CDP 直连本地 Chrome，携带登录态）。

## 目录结构

**系统根**（本仓库）——不出现任何具体项目标识，也不出现任何实例层目录，由
`test/suites/test_project_structure.py` 强制检查：

```text
hq-geo/
├── AGENTS.md              ← 宪法、分层规则、项目规则真源
├── project.py             ← 项目根解析唯一入口，所有脚本从这里取路径
├── capabilities/          ← 跨项目复用的方法、契约、校验器
│   ├── geo/               ← GEO 能力唯一真源（方法 + 契约 + 校验器）
│   ├── content-production/← 文章、视频简报、图片简报的契约与校验
│   ├── fact-packs/        ← 事实包契约、校验器与补录工具
│   ├── creative-handoff/  ← 与外部媒体制作系统的 CreativeJob → ProductionReceipt 协议
│   └── project-scaffold/  ← 新建项目根的脚手架（不覆盖已有文件）
├── skills/                ← 判断与路由，不复制方法论正文
├── test/                  ← 质量门禁、功能登记、测试套件
│   └── reports/<项目名>/   ← 门禁报告，按项目分开
├── 00-meta/               ← 产品定义、架构与研究结论（设计文档，不是执行入口）
└── workbench/             ← 已冻结（2026-09-28），不接入门禁，不再扩建
```

**项目根**（每个项目一个，位置随意）：

```text
<hq-geo 项目>/
├── .hq-geo.json           ← 项目标记 + 这个项目自己的产出基准
├── CLAUDE.md              ← 指回系统根的三份必读
├── LEARNING.md            ← 这个项目的学习记录
├── tasks/                 ← 任务单据，一次生产请求一个文件
├── data/ideas/            ← 创意对象，一个想法一个文件
├── facts/                 ← 事实包，创作上下文的唯一事实真源
├── topics/                ← 选题假设与测试状态
├── research/              ← raw 只追加，normalized 可重算
├── content/briefs/        ← 供外部制作系统执行的制作简报
├── content/packages/      ← 按渠道组织的发布包（文章成稿在 blog 包内）
├── content/styles/        ← 风格示例 HTML，给你看样选风格
└── assets/generated/      ← 外部制作系统回传的成品 manifest
```

## 质量门禁

```bash
python3 test/run_quality_gate.py --project <项目根>
```

在项目根里跑时可以省掉 `--project`。只有这一条命令，全部测试一秒内跑完。
门禁结论不是 `PASS`，就不得宣称可发布。

**产出比基准变少会直接判 `FAIL`。** 稿子消失通常不报错，页面就是空的——门禁要是还绿着，就没人会发现。
确实是有意清理，就去改项目根 `.hq-geo.json` 的 `output_baseline` 并写明原因。

- `test/feature_registry.json` — 功能实现状态与测试覆盖关系的真源
- `test/test_manifest.json` — 可执行测试清单的真源
- `test/baseline.json` — 系统健康基准（测试数、覆盖率）
- `test/reports/<项目名>/latest.json` / `latest.md` — 该项目最近一次结果

需要更短的反馈时加 `--changed`，但它不能替代完整门禁。

## 当前真实进度

按宪法第 1 条，这里只列已经交出去的东西。**这些在项目根 `视频画册推广` 里，不在本仓库。**

| 选题 | 载体 | 状态 |
|---|---|---|
| G1-02 | 视频简报 + 文章 + 四渠道发布包 | 已产出，简报因缺素材标记 `blocked` |
| P1-06 | 视频简报 + 四渠道发布包 | 已产出 |
| P1-01 | 视频简报 + 外部制作交接 | 已产出 |

三条。其余能力状态见 `test/feature_registry.json`——`planned` 的项目不能对外承诺。

## 归档

2026-09-28 把 01–08 编号管线、`lib/`、Playwright profile、`test_fusion.py` 移出仓库，存于 `../hq-geo-retired-20260928/`。移出原因：它们操作的是占位数据，会生成含"测试信源"的假周报，且 `test_fusion.py` 会写真实 `data/` 目录。

归档不等于删除，需要时可以从该目录取回任何文件。
