# 证据台账

**检索方式：** 按项目规则，所有联网核验均优先通过 `ego-browser`（跑不通时退回 `web-access`）（CDP 直连本地 Chrome，携带登录态） 完成。  
**本轮检索日期：** 2026-09-09  
**分级：** A=法律/现行官方规则或当前官方 UI；B=官方指南/官方产品说明；C=原始论文/权威出版社；D=专业二手历史材料；E=本次设计推断。

## 1. 平台与法律

| 等级 | 来源 | 本轮用于支持 | 适用范围与备注 | 下次复核 |
|---|---|---|---|---|
| A | [《人工智能生成合成内容标识办法》](https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm) | AI 文本、图像、音频、视频的显式/隐式标识；用户主动声明；不得删改隐匿 | 2025-09-01 施行，跨平台 | 2026-12-09 |
| A | [微信视频号运营规范](http://short.weixin.qq.com/cgi-bin/readtemplate?lang=zh_CN&t=weixin_agreement&s=video) | 真实、广告识别、禁止诱导/作弊/虚假误导、AI/非真实内容标识 | 动态规则文件 | 2026-10-09 |
| A | [视频号发表视频/图文有什么格式要求？](https://findeross.weixin.qq.com/cgi-bin/mmfindernodelivecrmwebbroker-bin/helper-center/pages/Yhdpjlq2RIkcmnQu) | 图片数量/比例、视频时长/大小/比例/清晰度、GIF/HDR/H.265 限制 | 当前官方帮助页 | 2026-10-09 |
| B | [视频号作品如何获得更多推荐流量？](https://findeross.weixin.qq.com/cgi-bin/mmfindernodelivecrmwebbroker-bin/helper-center/pages/LHcP1QLoRHXEBvKl) | 原创、人格化、前 10 秒、真人、稳定更新、关键词、评论和数据诊断 | 推荐建议，不是发布硬门槛 | 2026-12-09 |
| B | [视频号助手](https://channels.weixin.qq.com/login.html) | 内容上传管理、互动与数据查询入口 | 需登录 | 2026-10-09 |
| A | [抖音社区自律公约](https://lf3-cdn-tos.draftstatic.com/obj/ies-hotsoon-draft/douyin_creator/40db1b96-0eb0-4754-a052-16e8325af350.html) | 真实性、原创、反诱导、反导流、反低质/搬运，以及真人讲解等建议 | 全社区公约 | 2026-10-09 |
| A（限范围） | [抖音短视频创作者管理规范](https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/operation/platform-capabilities/video/video-creator-promote-mount-mgmt-spec) | 数据真实、音画一致、禁止绝对承诺、拼接搬运、机械配音和重复作品 | 直接适用于挂载小程序短视频，不能无条件泛化 | 2026-10-09 |
| B | [抖音创作者中心](https://creator.douyin.com/) | 作品发布管理、数据分析、创作灵感洞察功能存在 | 当前未登录，具体字段待核验 | 2026-10-09 |
| B | [抖音指数（原巨量算数）](https://trendinsight.oceanengine.com/arithmetic-index/) | 当前官方趋势产品入口 | 入口会跳转抖音创作者中心 | 2026-10-09 |
| B | [巨量算数移动端官方介绍](https://www.oceanengine.com/insight/juliang-suanshu-yidongduan) | 历史上提供热词趋势、飙升热点、关联分析、画像和榜单 | 旧产品说明；当前字段必须以抖音指数为准 | 仅作历史证据 |
| 过期参考 | [抖音开放平台视频上传旧文档](https://open.douyin.com/platform/resource/docs/openapi/video-management/douyin/create/upload/) | 旧 API 大小、分片和格式信息 | 页面标注 2022-09-06 后停止更新，不进入现行硬规则 | 不复核，等当前 UI |
| A | [小红书社区规范](https://agree.xiaohongshu.com/h5/terms/ZXXY20221213003/-1) | 真实体验、禁止导流/水印/标题党/虚假宣传/机器作弊 | 页面显示 2021-12-17 更新、2021-12-24 生效 | 2026-10-09 |
| A | [小红书创作服务平台：视频发布](https://creator.xiaohongshu.com/publish/publish?target=video) | 当前视频 4 小时、20GB、格式与清晰度提示 | 2026-09-09 已登录 UI 直接核验 | 2026-10-09 |
| A | [小红书创作服务平台：图文发布](https://creator.xiaohongshu.com/publish/publish?target=image) | 当前图片 32MB、格式、动图、比例与分辨率提示 | 2026-09-09 已登录 UI 直接核验 | 2026-10-09 |
| B | [小红书创作服务平台](https://creator.xiaohongshu.com/new/home) | 数据看板、笔记灵感、创作话题、创作学院；话题参与与浏览字段 | 账号当前登录；具体话题值会变 | 每次研究 |
| B（限商品） | [商家热搜词发布攻略](https://fe.xiaohongshu.com/apps/vincent/barley?fullscreen=true&id=ba0aee82139d40739ee31731406736b6&naviHidden=yes) | 热搜词表达消费需求；热度飙升/社区最热/成交最高；关键词与内容相关 | 商品笔记指南，不泛化为所有创作规则 | 2026-12-09 |
| A（限商业） | [小红书蒲公英内容审核规范](https://pgy.xiaohongshu.com/help/detail?id=6495c527d1eedeeb48fb18b1f875650e&userType=4) | 禁止保证性承诺、商业内容审核与部分品类规则 | 商业合作内容 | 2026-10-09 |
| A | [小红书生成式人工智能服务协议](https://agree.xiaohongshu.com/h5/terms/ZXXY20240103002/-1) | AI 输出不确定性、用户核验、不得删改隐匿标识 | 小红书生成式 AI 服务 | 2026-12-09 |

## 2. 理论与方法

| 等级 | 来源 | 本轮用于支持 | 边界 |
|---|---|---|---|
| C | [Berger & Milkman, “What Makes Online Content Viral?”, 2012](https://journals.sagepub.com/doi/10.1509/jmr.10.0353)；[作者存档 PDF](https://jonahberger.com/wp-content/uploads/2013/02/ViralityB.pdf) | 实用价值、趣味/惊奇、高激活情绪与传播的关系 | 原研究对象含《纽约时报》文章和实验，不直接保证中国短视频平台结果 |
| C | [Loewenstein, “The Psychology of Curiosity”, 1994](https://www.cmu.edu/dietrich/sds/docs/loewenstein/PsychologyofCuriosity.pdf)；[APA 记录](https://psycnet.apa.org/record/1994-41058-001) | 信息缺口与好奇心机制 | 解释注意机制，不等于支持标题党 |
| C | [Alexander et al., *A Pattern Language*, OUP, 1977](https://global.oup.com/academic/product/a-pattern-language-9780195019193) | 把反复问题保存为含情境、讨论和解法的模式 | 原领域是建筑与环境设计；用于系统设计类比，不是内容效果证据 |
| D | [姚金刚：《GEO到底该投多少钱？1.3万字讲透效果归因与ROI（附10种标记方法）》](https://x.com/yaojingang/status/2104049279996219883) | GEO 商业效果链路断裂；直接标记、交叉验证、对照实验三层方法；小范围词根试点；概率化监测 | 2026-09-27 从业者公开课总结。方法可形成待验证实验设计；文中的固定比例、报价、ROI 阈值和因果表述不是独立验证事实，不进入系统默认值 |

## 3. 历史同构

| 等级 | 来源 | 本轮用于支持 | 边界 |
|---|---|---|---|
| D | [Marketing Society：Account planning: back to the future?](https://www.marketingsociety.com/the-library/account-planning-back-future)；[4As 广告史时间线](https://www.aaaa.org/about/timeline/) | 1960 年代 Stephen King 与 Stanley Pollitt 路线把消费者研究带入创意工作 | 专业组织历史材料；不证明某套个人创作流程必然成功 |
| B | [Walt Disney Animation Studios：Story](https://disneyanimation.com/process/story/)；[Walt Disney Family Museum：Storyboarding](https://www.waltdisney.org/education/field-trips/storyboarding) | 故事板在昂贵制作前表达、检查和迭代创意 | 电影制作流程，只支持“先低成本预演”的结构类比 |
| B | [Google：High-quality sites algorithm launched in additional languages](https://search.googleblog.com/2011/08/high-quality-sites-algorithm-launched.html) | 平台质量机制会压制低质量规模化内容 | 搜索排序案例，不直接等同于三家社交平台推荐算法 |

## 4. 本次设计推断

以下结论不是平台公开算法事实：

- 三平台应保存原始信号、用平台内百分位和跨平台复现度判断，而非合并绝对指数；
- 微信指数是微信生态代理信号，不是视频号专属搜索量；
- 受约束随机比无条件随机更适合策略加载；
- 跨平台母稿应作为观点和事实真源；
- “停在发布按钮前”是第一版比自动发布更合适的权限边界；
- 先实现研究到选题的最小链路，比先做素材生成或发布自动化更能验证产品价值。

这些推断要通过后续真实使用、失败样本和账号数据修正。
