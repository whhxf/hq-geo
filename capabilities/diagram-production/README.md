# 信息图生产线（diagram-production）

**建立日期：** 2026-10-10
**状态：** 已接入图片线，可用。尚未在真实任务上跑过。

这条线产出**示意图、流程图、架构图、时间线、图表**这类图。
它和图片线主路不同：**不调模型，不出照片**。产物是自包含的 HTML（内联 SVG），可导 PNG / SVG。

## 它从哪来

| 项 | 值 |
|---|---|
| 来源 | https://github.com/cathrynlavery/diagram-design |
| 版本 | 2.6.73 |
| 提交 | `246d6d71d752245403d2bf28d27f124192584d18`（2026-10-10） |
| 许可 | MIT（Copyright 2025 Cathryn Lavery） |
| 吸收日期 | 2026-10-10 |

**原样 vendored，没有改动。** 位置：`vendor/diagram-design/`。
上游更新时，整目录替换，再改这里的版本与提交号。

为什么不 clone 成子模块：这条线要能离线跑、能进 git、能过门禁。
子模块在门禁里是空目录，`test/suites/test_project_structure.py` 会漏掉它。

## 里面有什么

| 目录 | 内容 |
|---|---|
| `vendor/diagram-design/SKILL.md` | 主文件。44 种图型的选型表、反模式、判据、输出契约 |
| `vendor/diagram-design/references/` | 62 份。每种图型一份，加语义模式、排版、配色、导出、导入 |
| `vendor/diagram-design/assets/` | 211 份 HTML。模板 3 套（浅色 / 深色 / 全版式）+ 每种图型的样例 |
| `vendor/diagram-design/scripts/` | 5 个脚本。drawio / Mermaid / Excalidraw 导入、SVG 导出、自检 |

**只依赖标准库。** 已扫过：无网络请求、无 subprocess、无 eval。可以离线跑。

## 怎么用

主入口是 `vendor/diagram-design/SKILL.md`。先读它，按它的选型表挑图型，
再读对应的 `references/type-*.md`。

自检脚本（生成后跑，验可访问性与单文件安全）：

```bash
python3 capabilities/diagram-production/vendor/diagram-design/scripts/self_check.py <生成的.html>
```

导出 SVG：

```bash
python3 capabilities/diagram-production/vendor/diagram-design/scripts/export_svg.py <生成的.html>
```

## 和其他线怎么接

- **图片线主路**（`skills/image-pipeline/`）出 AI 生成的照片类图。示意图不走那条路，走这条。
- **文章线**（`skills/article-pipeline/`）要配示意图时调这条线，产物放项目根 `assets/diagrams/`。
- **视频线**（`skills/video-pipeline/`）要画结构帧时可以调这条线，出 PNG 再进帧序列。

## 边界

- **不出照片。** 这条线画的是结构、流程、数据。要写实的画面走图片线主路。
- **不调模型。** 产物是手写 SVG，不花生成费用。
- **配色自带一套。** 上游 `references/style-guide.md` 是它自己的配色真源（默认纸色 `#f5f5f5`、墨色 `#2d3142`、强调色 `#bf4520`）。
  **拿它当文章配图时，仍要过 hq-geo 的排版判据**（正文对比度 ≥ 4.5:1 等，见 `capabilities/typography/rules/typography-rules.json`）。
  两套配色不自动对齐——对不上时以上游的 `style-guide.md` 改成 hq-geo 的值。
- **不自动发布。** 出图和预览是内部动作。
- **上游的样例图不是本项目素材。** `assets/example-*.html` 只作样式参考，不进入任何对外产物。
