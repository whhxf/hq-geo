# 项目级 Skills

Skill 属于系统层：判断、路由和交互在这里，方法正文不在这里。它们不安装到用户全局目录，随仓库一起走。

| Skill | 作用 |
|---|---|
| `content-orchestrator` | 自然对话总入口，判断社交内容、GEO 或混合流程 |
| `geo-research` | AI 搜索意图、当前答案、引用与内容空白研究 |
| `geo-content-brief` | 把 GEO 研究转为网站内容蓝图 |
| `geo-website-renderer` | 从母内容/蓝图生成网站版本及可选机器结构 |
| `geo-prepublish-core` | 网站 GEO 内容发布前审计的内部方法入口 |
| `geo-monitor` | AI 回答中的品牌、竞品、引用和变化监控 |
| `geo-attribution` | 归因标记、去重与增量贡献估算 |

GEO 方法唯一真源位于 `capabilities/geo/`。Skill 只负责触发、编排、输入输出和用户交互，不复制方法论正文。

Skill 不写死任何项目标识。项目的事实、选题和产物在**项目根**（`data/ideas/`、`facts/`、`topics/`、`content/`），Skill 通过 `project.py` 拿到当前项目根再读这些目录，而不是把项目名写进自己。
