---
title: 图片参考吸收
type: feature
created: 2026-09-30
status: 已实现（6.1 与 6.2 已闭合；6.3 人工走查未做）
baseline_commit: 0aee46c163d63061820c72c0fb3d0d2481d5d9f6
owner_capability: image-production
---

# PRD：图片参考吸收

## 0. 这份文档

**它是什么。** 图片线的「给样例 → 产同类」能力的规格。写清楚要做什么、不做什么、
怎么验，**后续迭代以它为准**。改了实现不改这里，或者改了这里不改实现，都算没做完。

**为什么放在 `capabilities/image-production/` 而不是 `00-meta/content-engine/`。**
`00-meta/` 的 specs（`spec-creative-production-handoff.md` 等）管的是**跨线协议**；
这一份管的是**单个能力包内部的实现**。`test/feature_registry.json` 里
`image-production` 的 `owner_paths` 是 `capabilities/image-production`——
规格住在它管辖的路径下，登记表里的责任路径才是有意义的。

**状态的读法。** 按 `AGENTS.md` 文档约定，实现状态单独标记（`未实现` / `部分实现` / `已实现`）。
本文件头部 `status` 字段 == 现在做到哪。设计本身不随状态变化。

**2026-09-30 现状**：§5 的落点全部落地，§6.1 的 18 条判据全部绑上了测试，
§6.2 的 canary 逐条确认变红（实际破坏点见该节）。**§6.3 的人工走查还没有做**——
它要花钱出图，得由 Conan 自己决定什么时候走。

---

## 1. 问题

### 1.1 现象

Conan 会说「这几张图我喜欢，以后做类似的」。现在系统接不住这句话。

现有图片线只有一条路：**从 14 套预置风格里选一套**（`styles/image-styles.json`）。
风格库是**封闭集合**，没有收录路径——用户给了图，系统无处安放。

### 1.2 为什么不能靠「让用户描述」

Conan 的原话：**「我要提取图片风格的时候，我不一定能准确描述出来。」**

这不是表达能力问题，是这类知识的性质。波兰尼（Michael Polanyi, *The Tacit Dimension*, 1966）
的说法是「我们所知多于我们所能言说」——隐性知识靠**范例**传递，不靠规则陈述。

**所以正确的工程动作不是「想办法让用户说出来」，而是「让系统不必经过用户的语言」。**
这条判断决定了整个设计方向：把重量放在**系统的测量与回测**上，用户的输入降到「给图」和
「看结果点头」。

### 1.3 为什么不能靠「让模型看」

已经实测（2026-09-30，`qwen3-vl-flash`，一张合成图）：

- **不约束的提示词产出全是套话。** 问「描述这张图片的风格」，答「极简主义」「克制」「高级」
  「呼吸感」，还**编出一个不存在的流派归属**（「北欧简约 / 日系侘寂」）。零可用信息。
- **约束后的提示词可用，但颜色不可信。** 禁止形容词、要求给 hex 之后，几何与布局描述可用；
  但它报的三个色值全部有偏差（实测 CIEDE2000：`#E2603A`→`#E0633F` ΔE00=0.84、
  `#FAF8F3`→`#FAF7F4` ΔE00=1.27、`#2B2926`→`#2D2D2D` ΔE00=2.51）。

对照开源项目 `zanwei/design-dna` 报告的失败案例 `#ff90e8 → #ec4899`：**ΔE00 = 17.0**。

**两者不矛盾，合起来是一条重要结论**：

> **漂移量 ∝ 该颜色在模型训练分布里的稀有度。**
> 常见色（米白、近黑、橙）漂移 < 3；独有品牌色漂移可达 17。

**推论：不能因为某次测色「看起来挺准」就认为语义层的颜色可信。**
越是有辨识度的品牌色——恰恰是最值得吸收的那类——漂得越狠。
**所以：颜色一律由确定性程序测量，语义层的颜色值一律不采信。** 这是本设计的硬线。

### 1.4 现有实现缺什么

| 缺的 | 后果 |
|---|---|
| 没有确定性取色工具 | 色板只能靠模型报数 → 漂移 |
| 出图不吃参考图 | 参考图无处可用，只能转成文字（又一次信息损失） |
| 出图不吃色板参数 | 颜色只能写进 prompt 文本 → 模型从语言里猜颜色 |
| 验收没有机器回测 | 站 5 只有「人看」一道，**「像不像」不可重复验证** |

---

## 2. 边界（不做什么）

**这一节比第 3 节重要。** 按宪法第 8 条「满三次重复才自动化，默认减法」，
这个切片**不自动化任何判断**。

### 2.1 明确不做

| 不做 | 为什么 |
|---|---|
| **不自动选风格** | 宪法 7「判断权在人」。选风格是用户的决定 |
| **不自动往 `image-styles.json` 写新风格** | 宪法 8。沉淀成风格库是「自动化决策」，要满三次真实重复。**第一版一条都不写** |
| **不自动决定该不该用参考图** | 同上。用户给了就用，没给就不走这条路 |
| **不训练模型**（LoRA / 微调） | 超出「标准库 + 现有 API」的范围，且几十张图不足以训练 |
| **不引入第三方依赖** | `AGENTS.md` 开发与验证：「新系统只使用标准库，不引入第三方依赖」。PIL / numpy 本机虽有，**不用** |
| **不在测试里调模型** | `AGENTS.md`：测试不得产生广告花费。全部测试走合成图，零联网 |
| **不做图片编辑** | 图片线既有边界，本功能不碰 |

### 2.2 为什么这些「不做」是对的

宪法第 2 条：**「先有能手动交稿的简单系统，再加速。禁止从完整蓝图开工。」**

本切片只交付**三个确定性动作**：测（取色）、传（把测出来的东西喂给模型）、回测（量偏差）。
它们都不是「决定」，是「测量」。**决定仍然全部由人做。**

风格库要不要建、什么时候建——等真实生产跑满三次，用数据说话。

### 2.3 参考图的权利问题

参考图大概率不是自己拍的。**它进项目根就要登记来源。**

- 参考图必须落在项目根 `assets/reference/` 下，不读项目根之外的路径。
- 在简报里登记来源与权利状态（复用既有的 `source_assets` 惯例）。
- **参考图不进入任何对外产物**，只用于内部测量与出图条件。

---

## 3. 设计

三个确定性动作，一条链：

```text
你给图（+ 可选一句话）
      │
      ▼
┌─────────────────────────────────────────────┐
│ 层 1 · 测   measure_palette.py              │
│   纯标准库解码 PNG → 直方图 → 加权 k-means  │
│   → ΔE 合并 → 角色判定 → 覆盖率              │
│   输出：palette[{role, hex, coverage, oklch}]│
└─────────────────────────────────────────────┘
      │
      │  ① 直接作为 DashScope 的 color_palette 参数（hex + ratio）
      │  ② 直接作为 image-styles.json 的 tokens.palette 格式（role + hex + oklch）
      ▼
┌─────────────────────────────────────────────┐
│ 层 2 · 出   generate_image.py（改造）        │
│   content: [{"text": 意图}, {"image": 参考图}...] │
│   parameters.color_palette: [{hex, ratio}]   │
└─────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────┐
│ 层 3 · 回测   verify_palette.py              │
│   对生成图重量一次 → 逐色 ΔE00 + 覆盖率漂移   │
│   输出：PASS / FAIL + 每个 role 的偏差明细    │
└─────────────────────────────────────────────┘
      │
      ▼
   你看：像 / 不像 / 哪里不像        ← 只有这一环非人不可
```

### 3.1 关键设计点

**(a) 色板格式一鱼两吃。** `measure_palette.py` 的输出同时是
DashScope `color_palette` 参数的格式（`hex` + `ratio`）和
`image-styles.json` `tokens.palette` 的格式（`role` + `hex` + `oklch`）。
**一次测量，两个下游都直接吃**，中间没有转译——转译就是信息损失。

**(b) 参考图必须配一句话。** 万相 2.7 的多图参考是**生成+编辑**模型，
不说明意图时它可能把参考图当成「要改的对象」。官方示例里就带着
「参考图片风格生成四季组图」这样的指令。所以契约里
`reference_images` 非空时 `reference_instruction` 必填——**这一条可机器校验**。

**(c) 多张参考图求交集，不写死在脚本里。**
`measure_palette.py` 支持多张输入，输出 `per_image` 与 `consensus`。
`consensus` 只做**一件**可计算的事：对每个 role，量出它在各图之间的稳定程度
（明度/色相的离散度 → `stability` 0..1）。

> 稳定的维度才是 pattern，不稳定的不是。
> 「8 张图里背景明度都在 0.95–0.98」是 pattern；「强调色从橙到蓝都有」不是。

至于「拿这个 pattern 怎么办」——**那是判断，归 Agent 和人**，不归脚本。

**(d) 颜色一律走测量，不走语义层。** 硬线，见 1.3。

### 3.2 纯标准库怎么解 PNG

`AGENTS.md` 禁第三方依赖，所以要自己解 PNG。可行：

```
签名 8 字节 → 循环读 chunk（length/type/data/crc）
IHDR → 宽高、位深、颜色类型、interlace
IDAT → zlib.decompress 拼接
扫描线 → 每行首字节是 filter 类型，还原：None/Sub/Up/Average/Paeth
```

支持范围：**颜色类型 0(灰度)/2(RGB)/3(调色板)/4(灰度+A)/6(RGBA)，
位深 1/2/4/8/16，非隔行**。超出范围明确报错，不静默给错值。

**为什么范围比第一版宽**：初稿只写了位深 8 的 0/2/4/6，理由是「够用了」。
实现时发现这个判断错了——**调色板 PNG（类型 3）和低位深 PNG 在网页图片、
截图、优化过的插画里极常见**，而参考图的主要来源正是这些。用户把自己喜欢的
图丢进来却收到「不支持这种 PNG」，就得自己去转格式，等于是**系统把自己能做的
事推回给用户**，而这违反交互原则里的「系统承担复杂性」。

多出来的成本是有界的：低位深只是拆位，16 位只是取高字节，调色板只是查
`PLTE` 表。三样加起来几十行，换来的是**用户给的图基本上都能直接吃**。
真正不支持的（隔行 PNG）才报错——隔行在 2026 年的图片里已经很少见。

非 PNG 参考图（JPEG / WEBP）走 macOS 自带的 `sips` 转一道；
没有 `sips` 就明确报错，告诉用户转成 PNG。

**为什么不用 PIL**：本机装着，但 `AGENTS.md` 的规则是系统只依赖标准库。
用 PIL 会让这套脚本换台机器就跑不起来——那正是「第二个项目无法复用第一套方法」的成因。

### 3.3 k-means 在纯 Python 里怎么跑得动

朴素做法：对每个像素 × 每个中心 × 每轮迭代算距离。2048² × 8 × 24 ≈ 30 亿次，纯 Python 跑不动。

**改用「先直方图、再加权聚类」**：

1. 每个像素量化到 5 bit/通道（32³ = 32768 桶），累积每桶的 `(sum_r, sum_g, sum_b, count)`
2. 在**桶**上跑 k-means，权重是 `count`，中心是加权平均
3. 迭代成本从「像素数 × k」降到「非空桶数 × k」，通常小两个数量级

**精度不丢**：每个桶记的是**该桶内像素的均值**而不是桶的中心坐标，
所以最终中心是真实像素的加权平均，不是量化后的近似值。

初始化用**确定性最远点**（从最暗的桶起，每次加离最近中心最远的桶），
保证同输入同输出——**测试要能断言确切值，就不能有随机数**。

采样上限 24 万像素（按步长跨采样，不是截断前 N 个），保证大图也快且统计代表性好。

---

## 4. 契约变更

### 4.1 `contracts/image-brief.schema.json`

在 `deliverables_items` 下**新增三个可选字段**（不破坏既有简报）：

| 字段 | 类型 | 必填条件 |
|---|---|---|
| `reference_images` | `array<string>` | 可选。项目根相对路径，指向 `assets/reference/` |
| `reference_instruction` | `string` | **`reference_images` 非空时必填** |
| `palette_ref` | `string` | 可选。指向 `measure_palette.py` 输出文件的路径 |

**为什么 `reference_instruction` 是条件必填而不是无条件必填**：
没有参考图时这句话没有意义，强制填会变成新的形式主义（宪法 8 的「默认减法」）。

### 4.2 校验器 `scripts/validate_image_brief.py`

新增拦截：

| 拦的 | 不拦会怎样 |
|---|---|
| 有 `reference_images` 但没有 `reference_instruction` | 模型不知道参考什么，可能把参考图当成待编辑对象 |
| `reference_images` 指向项目根之外 | 路径纪律失效；参考图未登记来源 |
| `reference_images` 文件不存在 | 出图时才报错，钱已经花了 |
| `palette_ref` 文件不存在或格式不对 | 静默不出色板，图和预期两样 |

### 4.3 出图脚本 `scripts/generate_image.py`

`assemble_prompt()` 保持不变（**顺序仍是先风格、再画面、最后意图**）；
新增在 `generate_one()`：

```python
content = [{"text": prompt["prompt"]}]
for data_uri in prompt.get("reference_images", []):
    content.append({"image": data_uri})
payload["input"]["messages"][0]["content"] = content

if prompt.get("color_palette"):
    payload["parameters"]["color_palette"] = prompt["color_palette"]
```

**向后兼容**：没有新字段时，payload 与今天完全一致。既有简报行为不变。

`manifest.json` 回执新增记录 `reference_images`、`color_palette`、`palette_ref`，
**让每张图都能追溯到「它是参考什么出出来的」**。

---

## 5. 落点

| 文件 | 动作 |
|---|---|
| `capabilities/image-production/PRD-reference-absorption.md` | **新建**（本文件） |
| `capabilities/image-production/scripts/png_io.py` | 新建：纯标准库 PNG 读写（写只给测试用） |
| `capabilities/image-production/scripts/color_math.py` | 新建：sRGB→OKLCH、CIEDE2000 ΔE |
| `capabilities/image-production/scripts/measure_palette.py` | 新建：取色 |
| `capabilities/image-production/scripts/verify_palette.py` | 新建：回测 |
| `capabilities/image-production/scripts/generate_image.py` | 改造：参考图 + 色板参数 |
| `capabilities/image-production/scripts/validate_image_brief.py` | 改造：四条新拦截 |
| `capabilities/image-production/contracts/image-brief.schema.json` | 改造：三个可选字段 |
| `capabilities/image-production/README.md` | 改造：文件表 + 一节说明 |
| `capabilities/image-production/tests/test_palette.py` | 新建：单测 |
| `skills/image-pipeline/SKILL.md` | 改造：站 3 / 站 4 / 站 5 各加判据 |
| `test/suites/test_image_pipeline.py` | 改造：契约检查加新判据与新字段 |
| `test/feature_registry.json` | 改造：登记新功能 |
| `test/test_manifest.json` | 改造：登记新测试 |
| `test/canary.json` | 改造：加破坏点 |
| `CHANGELOG.md` | 改造：记改进 |
| `PLAYBOOK.md` | 改造：手册同步 |

**系统根里不出现实例层目录**（`test/suites/test_project_structure.py` 强制）。
本 PRD 不新建任何 `tasks/` `facts/` `assets/` 等。

---

## 6. 验收判据

**宪法 6：没有可重复验证方式的部件视为未完成。** 所以判据必须可机器验证。

### 6.1 自动回归（本切片交付的）

| 判据 | 验证方式 | 层级 |
|---|---|---|
| ΔE00 数学正确 | 已知色对的 ΔE 与手算值一致 | unit |
| sRGB→OKLCH 转换正确 | 已知 sRGB → 已知 OKLCH 字符串 | unit |
| PNG 解码正确 | 合成 PNG → 读出确切像素值 | unit |
| PNG 解码不静默出错 | 不支持的位深/颜色类型 → **报错**，不是给错值 | unit |
| k-means 确定性 | 同输入跑两次，输出字节相同 | unit |
| k-means 恢复已知色板 | 合成一张已知配色的图 → 测回的 hex 落在容差内 | unit |
| ΔE 合并生效 | 两个 ΔE<2.5 的近似色 → 合并成一个 | unit |
| 角色判定正确 | 合成图里最大面积的是 `background`，高对比的是 `text` | unit |
| 覆盖率合计 | `sum(coverage) ≈ 1.0` | unit |
| 多图 consensus | 稳定的维度 `stability` 高，不稳定的低 | unit |
| 回测能判否 | 明显偏色的图 → `FAIL`；同色图 → `PASS` | unit |
| **回测不是空转** | 见 6.2 canary | unit |
| 出图 payload 兼容 | 无新字段时 payload 与改造前一致 | unit |
| 出图 payload 带参考图 | 有 `reference_images` 时 content 含 `{"image": ...}` | unit |
| 简报校验四条新拦截 | 缺 instruction / 越界路径 / 文件不存在 / palette_ref 无效 | unit |
| 五站判据仍在 | `test/suites/test_image_pipeline.py` | contract |
| 风格库仍是 14 套 | 同上（防止误改） | contract |
| 门禁在两个项目上 PASS | `run_quality_gate.py`，含一个脚手架空项目 | release |

**「测回的 hex 落在容差内」这条要特别说明**：合成的测试图颜色是已知的，
但 k-means + 量化的结果不会**逐位**相等。容差定为 **ΔE00 ≤ 3**
（对应「肉眼几乎不可辨」到「专业人士可辨」之间）。
**为什么是 3 而不是 0**：定 0 会因为量化误差永远红，然后就会有人去放宽它——
那才是真的没测。定 3 是「测量工具的精度承诺」，可辩护。

### 6.2 Canary（断言不能是空转的）

新增断言必须做 canary——**故意破坏被测对象，确认测试变红，再还原**。
`test/canary.json` 里这一组的**实际**破坏点，逐条确认变红：

| 破坏 | 变红的测试 |
|---|---|
| 删掉 SKILL 里「色板的 role 是猜的」免责说明 | `image-pipeline-contract` |
| 允许色板自动沉淀进风格库 | `image-pipeline-contract` |
| 允许把参考图当素材拼进去 | `image-pipeline-contract` |
| 从契约里删掉 `palette_ref` 字段 | `image-pipeline-contract` |
| ΔE 合并阈值从 2.5 改成 999（等于不合并） | `image-palette-tooling` |
| ΔE 合并阈值改成 0（等于不合并） | `image-palette-tooling` |
| 共识稳定性恒为 1（不稳定的也说成 pattern） | `image-palette-tooling` |
| 共识代表色改成取平均（凭空造一个没人用过的色） | `image-palette-tooling` |
| 出图请求体无条件多塞一个字段 | `image-palette-tooling` |
| 参考图拦截整段失效 | `image-palette-tooling` |
| ΔE00 恒返回 0 | `image-palette-tooling` |
| 灰度的色相不再归零 | `image-palette-tooling` |
| 回测改回逐 role 匹配（制造假警报） | `image-palette-tooling` |
| 调色板低位深取样偏移一位 | `image-palette-tooling` |

**这张表第一次写的时候是「计划」，落地的过程中它被改过一次**：验收判据里的
「ΔE 合并不再发生」「多图 consensus」「角色判定正确」三条当初没有测试，
是照 §6.1 自查时补的，补完再各加一条 canary。**先写判据、再照判据查缺口**——
顺序反过来（先写测试再补判据）就会漏掉「判据说要有、但没人测」的那一类。

**这批 canary 上线时踩到一个工具 bug**：「ΔE 合并不再发生」被误报成空转。
真因不在断言，在 canary 自己——它还原源码后留下了被破坏版本的字节码。
详见 `test/tools/canary.py` 的 `invalidate_bytecode` 长注释，以及根目录
`CHANGELOG.md` 2026-09-30 第一条。**这条记在这里，是因为它说明「canary 报空转」
不等于「断言是空的」——工具本身也在被怀疑之列。**

### 6.3 人工走查（自动回归通过之后）

自动回归只能证明**代码按规格跑**，证明不了**这条路真的有用**。
所以 6.1 全绿之后，交给 Conan 走查：

1. **给图。** 拿 1–3 张真的喜欢的图，放进项目根 `assets/reference/`。
2. **看测量。** 跑 `measure_palette.py`，看测出来的色板**是不是这么回事**——
   不需要准确描述，只需要说「对 / 不对」。
3. **真出一次图。** 带参考图 + 色板出图（**这一步要花钱，要 Conan 明确授权**）。
4. **看回测。** 跑 `verify_palette.py`，看 PASS/FAIL 和偏差明细。
5. **看图。** 「像 / 不像 / 哪里不像」。

**第 5 步是唯一不可自动化的判据，也是最终判据。**
ΔE 能测「像不像」，测不了「好不好」。

---

## 7. 宪法对照

| 宪法 | 本设计怎么满足 |
|---|---|
| 1 价值等于署名产物 | 交付的是能用的取色/回测脚本，不是文档 |
| 2 先能手动，再加速 | 只做测量，不做决策；风格库一条不写 |
| 3 四层分文件 | 方法在 `capabilities/`，判据在 `skills/`，实例在项目根 |
| 4 先流程后单据后功能 | 先定 `reference_images` / `palette_ref` 三个字段，再实现 |
| 5 缺料停机 | 参考图不存在 → 报错停机，不代填 |
| 6 契约 + 验收清单 | 第 4 节契约、第 6 节判据；无验证方式的部件不交付 |
| 7 判断权在人 | 选风格、定好坏、授权出图，全部在人 |
| 8 满三次才自动化，默认减法 | 第 2 节「不做」清单；风格库零写入 |

---

## 8. 已知限制与未决

**必须写在这里，否则后续迭代会以为它们已经解决了。**

1. **回测阈值没有实测校准。** `max_delta_e` / `max_coverage_delta` 是起点值，
   **不是从数据来的**。用真实出图校准之前，回测只能说「偏得离谱」和「看着还行」，
   **不能说「合格」**。校准是后续迭代第一项。
2. **`color_palette` 在有图片输入时是否生效未验证。** 官方文档只说了
   「仅当关闭组图模式（`enable_sequential=false`）时可用」，
   **没说有参考图输入时可不可用**。第一次真实出图要专门验这一条。
3. **多图参考对上位概念（风格）的保真度未知。** 官方示例是
   「参考图片风格生成四季组图」，但那是官方挑选的演示。
   **「像不像」只能人看。**
4. **语义层没有接入。** 本切片只做颜色。构图、光线、质感、排版仍要靠
   站 2 的 `subject` 人工写。**这是有意的**——语义层的颜色已经证明不可信，
   其余维度还没验证过，不先接。
5. **非 PNG 依赖 `sips`。** 换机（Linux / Windows）需要另找转换工具。
   **第一版不解决**，因为系统根现有项目都在 macOS 上。
6. **`verify_palette.py` 只测颜色。** 它测不了「这张图配不配得上那句话」——
   那条仍然只能人看（既有站 5 判据，不变）。
7. **解码耗时随图片内容浮动 4 倍，热点在 `_unfilter` 不在 `_expand`。**
   实测 12MP PNG：连续色调的照片型 **1.3 秒**，高熵合成图 **5.2 秒**。
   cProfile 显示 `_unfilter` 占累计时间的 **99%**（其中 33M 次调用的
   None/Up 滤波生成式是最大头），而我当初优化的 `_expand_fast` 已经掉出前六。

   **这条要写下来，因为当初的判断是反的。** 12MP 解码最初 5.0 秒时
   cProfile 显示 `_unfilter` 2.6 秒 / `_expand` 3.1 秒，于是优化了 `_expand`；
   优化之后 `_unfilter` 就成了唯一的热点，但**没人重新量过**——
   如果留下的是「已经优化过了」的印象，下一轮迭代会直接跳过去。
   参考图是用户随手丢的，尺寸和内容都不受控，这个耗时是真会遇到的上界。

---

## 9. 后续迭代

按优先级，**每一条都要先有真实生产证据才启动**（宪法 8）：

1. **用 3–5 次真实出图校准 ΔE / 覆盖率阈值。** 没有这一步，回测的 PASS 不可信。
2. **验 `color_palette` 与参考图是否可共存**（第 8 节第 2 条）。
3. **语义层接入**——如果颜色这条路跑通且用户认可，再考虑把构图/光线
   也做成可回测的量。**前提是先找到不漂移的度量方式**，否则重复 1.3 的错。
4. **风格库收录路径**——真实生产重复满三次之后，再讨论
   `measure_palette.py` 的输出要不要沉淀成 `image-styles.json` 的一条。
   **现在不做。**
5. **多图参考的取舍**——如果真实数据显示「带参考图」和「只带色板」
   出图效果差不多，那参考图这条路就该删掉（默认减法）。

---

## 附：为什么不用现成的开源方案

调研于 2026-09-30。

| 候选 | 判定 | 理由 |
|---|---|---|
| `zanwei/design-dna`（1.9k★, MIT） | **借方法，不搬代码** | 它是 UI 域的（schema 全是 spacing/elevation/motion，产物是 HTML/CSS/JS）。**但它有两个可取处**：公开测出了 1.3 的漂移现象（`#ff90e8→#ec4899`，ΔE≈17），以及 `measure-colors.mjs` 的 k-means+ΔE 合并 + `verify.mjs` 的回测闭环。**本设计借的正是这两点思路**，用 Python 标准库重写。它的 Node 依赖不符合 `AGENTS.md` |
| `pharmapsychotic/clip-interrogator`（3k★） | **不用** | 最后更新 2024-05-15，已停滞；产出是 Stable Diffusion 的 tag 串，不对口万相的 API；依赖 torch |
| SigLIP2 | **不用** | 依赖 torch，且它解决的是「从哪里找证据」（检索），本切片不做检索 |
| `qwen3-vl-flash` | **本切片不用** | 颜色不可信（1.3 实测）。**保留为后续语义层的候选**，但必须先找到不漂移的度量方式 |

**结论：没有可以直接引用的现成方案。** 因为这件事的闭环绑死在各自的生成 API 上——
万相的 `color_palette` 参数、多图参考的语义、PNG 输出，都是本系统独有的组合。
