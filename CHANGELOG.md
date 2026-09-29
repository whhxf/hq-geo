# 变更日志

只记录对系统的改进。实例层产物（文章、事实包、任务状态）不在此列。

判断方法：改的是**「怎么做」**，写这里；改的是**「做了什么」**，不写。

---

## 2026-09-29

### 创作链路的前端补齐：关键词研究能跑了，选题记录有了五问闸

- **做了什么**：
  - 新增 `capabilities/keyword-research/`——**渠道适配器**架构（一个渠道一个 markdown，front matter 机器读，
    加渠道就是加文件）、两份契约（`research-record.schema.json` 一次采集、`demand-cluster.schema.json` 需求簇）、
    第一个也是唯一 verified 的渠道 `channels/xhs-spotlight.md`、校验器 `scripts/validate_research.py`、
    27 条单测（`tests/test_research_rules.py`）
  - 新增 `capabilities/topic-registry/`——`contracts/topic.schema.json`（v2）、
    校验器 `scripts/validate_topics.py`、迁移脚本 `scripts/migrate_v1.py`、25 条单测
  - 新增 `skills/keyword-research/SKILL.md`——六站：定核心词 → 选渠道 → 采集 → 归一化成需求簇 → **和用户讨论** → 登记选题
  - 新增两个契约套件：`test/suites/test_keyword_research.py`、`test/suites/test_topic_registry.py`
  - 登记：`test_manifest` 18→22、`baseline` 18→22、`canary` 52→64 条
  - 实例层（不算系统改进，一并记录）：`视频画册推广` 的 91 条选题从 v1 迁到 v2；
    `kingsway ai 数字员工` 落了第一份真实研究产物（62 条记录 + 4 个需求簇）
- **为什么**：审计发现**这两样东西都不存在**。`00-meta/content-engine/02-research-and-topic-system.md`
  有 280 行完整设计，但那只是蓝图；`feature_registry` 里 `tri-platform-research` 和 `topic-validation`
  两条都挂着 `planned`，责任路径指向一个文档目录，没有测试。

  而三样容易误认为已有的东西都不是这件事：`geo-research` 问的是「AI 搜索里竞品占了哪些位置」，
  不是「真人在搜什么词」；`sourcing` 的检索路径找的是**事实**，不是**需求**；
  项目里那 91 条选题是**手工列的清单**，没有一条有调研链。

  **关键判断：关键词研究是组合技能，不是流水线。** 同一个问题在小红书、抖音、微信里要用不同方式问，
  拿回来的口径各不相同。所以形状是**可插拔的渠道适配器**——渠道会改版，契约不会；
  平台改界面只改一个渠道文件，记录格式和归一化规则不动。这也是唯一能让它长到五六个渠道而不散架的形状。

  **第二个判断：评估了本机三套现成资产，全部不能直接用。**
  `evidence-first-keyword-research` 平台是 Google（方法论能借，工具层不能）；
  `hq-mtsites/keyword-research` 的**评分公式逻辑是反的**——`搜索量×0.35 + 竞争低×0.40 + 商业价值×0.25`，
  竞争低占最高权重，那是**建站排名**逻辑（新站打不了高 KD 词）。**内容获客要的恰恰是高竞争高意向词。**
  照搬会把人导向「找没人搜的词」。所以抽它的 Method Plugin 架构，丢它的公式，并在 README 里写明为什么丢。
- **影响**：
  - `feature_registry` 里 `tri-platform-research` 和 `topic-validation` **被删除**，
    由 `keyword-research` 和 `topic-registry` 两条 `partial` 取代。删的理由：它们登记的是蓝图，
    责任路径是文档目录、没有测试；现在有了真实现，留着就是同一个能力挂两条
  - 选题记录 **v1 → v2 是破坏性变更**：`stage`/`status`/`progress`/`next_action`/`updated_at`/`artifacts`
    六个字段被移除。理由见 `AGENTS.md` 第 31 行「四层各自独立成文件」——
    选题记录只管「做不做」，做到哪了去 `tasks/` 看。旧文件混着两件事，会让选题记录变成第二个任务表
  - 校验器**跳过 `.bak.json`**。迁移时踩过一次：备份被 glob 命中，产生 638 处假报错
  - `monthly_search_index` 的类型是 `["integer","string","null"]`，**故意允许字符串**——
    平台报「<100」时照抄。换算成 100 是编数，换成 null 是丢信息。谁把它收紧成整数，就是在逼采集的人编数
- **验证**：
  - 门禁在两个项目上跑：`ai-employee` 与 `video-album`，均 **PASS**，22/22 测试、覆盖率 100%
  - 新增 12 条 canary **全部变红**（编词、推断词冒充代表词、跨平台加总、只选 verified 渠道、
    五问半答、混层、迁移替老选题升状态、契约不允许五问为空、`<100` 被收紧、`status` 判据消失、README 丢门槛）
  - 真实数据跑通：`validate_research.py` 在 `ai-employee` 上 PASS（62 条记录、4 个需求簇）；
    `validate_topics.py` 在三个项目上 PASS（91 / 0 / 0 条）

### 图片线从名词变成流水线：ImageBrief 契约、14 套风格、一步出图

- **做了什么**：
  - 新增 `capabilities/image-production/`——`contracts/image-brief.schema.json`（图片制作接口）、
    `styles/image-styles.json`（14 套视觉风格，从 Vidmix 搬来并标注来源）、
    `scripts/validate_image_brief.py`（简报校验器）、
    `scripts/generate_image.py`（组装 prompt → 调 `wan2.7-image-pro` → 存回项目根）、
    `tests/test_image_brief.py`（16 条单测）
  - 新增 `skills/image-pipeline/SKILL.md`——五站：读任务查事实 → 写简报 → 选风格 → 出图 → 验收
  - 新增 `test/suites/test_image_pipeline.py`——盯五站判据在不在、契约必填项、风格库完整性
  - 登记：`test_manifest` 15→18、`feature_registry` 新增 `image-production`、`baseline` 15→18
- **为什么**：Conan 定的一件事和一个一直没人发现的洞。

  定的是：「**图片管线和视频管线本就是独立的两套**，后续中间有没有桥后续再说。我要先走通图片创作，
  这不是传统的编辑图片功能，而是强依赖 AI 生成，调用好的模型一步出图。」
  ——所以图片线不做图层不做涂抹，做的是把「要什么」说清楚、组装 prompt、调模型拿图。

  洞是：`ImageBrief` 在 `AGENTS.md` 里被写成「图片的最低完整交付」，在
  `content-production/README.md` 里被列成契约，**但 `contracts/` 里根本没有它的 schema 文件**。
  它是个占位名词，写了很久没人发现——因为它不报错，只是不存在。

  图片线的核心问题也和文章线不同：文章写错一句话，读者能追问出处；**图不能**——
  一张看起来像产品界面的生成图，读者没有任何办法知道那是模型编的。
  所以这条纪律必须由字段强制，不能靠「写的时候注意」。
- **影响**：
  - `image` 类型的任务不再指向「尚未建立」，`content-orchestrator` 的路由表改指 `image-pipeline`
  - 取材的两张分流图（`capabilities/sourcing/README.md`、`skills/sourcing/SKILL.md`）从两岔改三岔
  - `capabilities/content-production/styles/README.md` 那句「文章、图片、视频三条流水线共用这套机制」
    **是假的**——那套特征集是给文字写的（句长、节奏、人称、常用词），**图片没有「句长」**。
    改成「共用机制、不共用特征集」，并指到图片线自己的视觉特征集
  - `capabilities/creative-handoff/README.md` 写明这是**视频通道**，图片不走这里
  - **旧行为：无。** 图片线此前不存在，没有东西被改掉
- **验证**：
  - 两个项目门禁 **18/18 PASS**（`视频画册推广`、`kingsway-geo`）
  - canary 新增 7 条，全量 **53 条全部变红、还原后复跑干净**
  - 单测另做 4 处手验 canary（去掉「生成图冒充真实题材」检查 / 去掉 `synthetic` 必填 /
    风格不再放 prompt 最前 / 只认新版响应格式），全部变红
  - `--dry-run` 路径不调模型、不花钱，出图前先念 prompt 给用户听

### 三个外部图片仓库：评估结论是一个都不接

- **做了什么**：读完 `coreyhaines31/marketingskills` 的 `skills/image`、
  `liangdabiao/ecom-details-image`、`buluslan/gpt-image2-ecommerce`，结论写进 `BACKLOG.md`。
- **为什么**：Conan 问「接入这个 skill 成不成」。三个都是 MIT，法律上都能用，
  **不接的理由不是许可证，是它们解决的是「怎么出图」，而这一层不是缺口**——
  hq-geo 缺的是「出什么图、凭什么出、出完怎么验收」。而且三个都是电商详情图导向
  （Amazon 白底主图 / A+ 模块 / SKU 换色），和 Kingsway 的内容配图不是一回事。
  顺带发现 `liangdabiao` 是 `buluslan` 的下游改造（它的 README 自己写了致谢），
  真要接也只会接上游那个。
- **影响**：不引入任何外部依赖。值得拿走的是四条做法不是代码，已记进 BACKLOG——
  主图技术预检的思路（白底判定 / 前景占比 / OCR，确定性可测试）、Campaign Style Lock、
  **「AI 会幻觉 UI，产品界面必须用真实截图」**、三不红线（不剥离 C2PA/SynthID、
  不教唆规避 AI 标注、不造假实拍）。**第三条已经变成 `subject_kind` 字段的机器执行版本。**
- **验证**：不需要——这是评估，没有改系统。结论落盘在 BACKLOG，免得下次重新查一遍。

### 新增项目根：Kingsway AI 数字员工

- **做了什么**：用 `init_project.py` 在 `~/kingsway/kingswaywork/05kingsway运营动作/kingsway ai 数字员工`
  建了第三个项目根（slug `ai-employee`），`PLAYBOOK.md` 第二节和第六节同步。
- **为什么**：AI 数字员工是另一条内容线，和前两个不是同一个产品。它也是**第一个从零开始的项目**——
  前两个是搬迁或拆分来的，都带着存量，这个是空目录。
- **影响**：项目数 2→3。`.hq-geo.json` 的 `output_baseline` 六项全 0，下次跑门禁开始比对。
- **验证**：门禁在该项目上跑过，空项目该是绿的（没有产物不是错误）。

---

## 2026-09-28

### canary 会把路径错误伪装成「断言有效」——修掉，并让错路径当场停下

- **做了什么**：`test/tools/canary.py` 在起任何子进程之前把 `--project` 转成绝对路径
  （新函数 `resolve_project()`）；路径指向的目录若没有 `.hq-geo.json`，直接报
  「这里不是 hq-geo 项目根」并返回 1，不再往下跑。
- **为什么**：canary 跑测试时固定 `cwd=系统根`，相对路径会在**系统根**解析，不是在你敲命令
  的地方。2026-09-28 在项目目录里用 `--project .` 跑全量（PLAYBOOK 速查表里写的就是这个
  写法），所有测试都因为找不到项目而退出非零——而 canary 把「非零退出」当成「变红」，
  于是**46 条全部显示「✓ 变红」，全是假红**；末尾复跑同样失败，报出来的是
  「文件可能没恢复干净，去 git status 看一眼」，指向完全错误的方向，白排查了一轮。
  **假红和假绿一样有害**：你会以为断言在守着，其实它什么都没测。
- **影响**：`--project` 现在接受相对路径；路径错误从「一片假红 + 误导性警告」变成一句
  明确的话。`test/suites/test_canary.py` 新增 `ResolveProjectTests`（2 条）。
  PLAYBOOK 速查表的 canary 命令补了说明。
- **验证**：把 `resolve_project()` 退回原样（`return raw`），新断言立刻红（1 failure），
  还原后绿。路径守卫实测：在系统根用 `--project .` → 报错并 `rc=1`；在项目目录里用
  `--project .` 跑全量 → **46 条全部变红、复跑干净、不再有那句警告**。

### 新增取材能力：创作链路的第一环，两条路径由用户选

- **做了什么**：新增 `capabilities/sourcing/`（`README.md` + `interview-method.md` +
  `research-method.md`）和 `skills/sourcing/SKILL.md`。取材把「一个想法或一个主题」变成
  `production-brief.json`，分两条路径——**访谈**（从用户脑子里挖，落 `owner_statement` 事实）
  和**检索**（从外部找，落 `official_source` 事实）。入口先问用户走哪条，**不替他选**。
- **为什么**：2026-09-28 Conan 提的——「有时候我没法表达清楚一些想法的时候，
  你可以不断地追问我问题，通过追问的方式，完成项目的创作任务」；以及
  「**并不是每一次都要访谈，这是可以选的**」。
  系统原来只有**被动**的补料（站 2 按缺口清单问，第一篇文章的四个缺口全是事实型），
  没有主动挖掘的能力。而 `content/briefs/` 和 `production-brief.schema.json` 早就在系统里，
  项目里已经出现过填到一半的 brief，它自己的 README 写着「你的下一次回答会先进入事实包，
  再回填 `evidence-list` 段落」——**那句话描述的正是取材，只是之前没有哪份文档规定怎么问出来。**
- **访谈判据的来源**：借用了 `QianWenFlow/qwskill`（CC BY-NC 4.0）的提问方法，
  **用 hq-geo 自己的语言重写，没有复制文本**。三处关键改造：
  1. 它的「回答用途」改成 **「这个回答会填上哪一格？」**——格子是 brief 的字段、
     事实包的 owner 四类、选题的字段，比抽象判据更可执行
  2. 它产出知识稿，hq-geo 的取材**不写成稿**——成稿走八站和 creative-handoff
  3. 它的「非诱导」对接 hq-geo 宪法第 5 条：`capture_fact.py` 的
     `ALLOWED_OWNER_CATEGORIES` 和校验器的「`inference`/`unknown` 不能 `verified`」
     是这条原则的机器执行版本
- **影响**：
  - 创作链路多了一环，前置于 `article-pipeline`（文章）和 `creative-handoff`（图/视频）
  - `test_project_structure.py` 的 `SYSTEM_REQUIRED` 加 `capabilities/sourcing/interview-method.md`
    和 `skills/sourcing/SKILL.md`；`SYSTEM_LAYER` 加 `capabilities/sourcing`
  - 测试数 14 → 15（`sourcing-contract`），canary 用例 38 → 46，基准 `test/baseline.json` 同步
  - `feature_registry.json` 新增 `sourcing`（`partial`）
- **验证**：两个项目门禁 15/15 `PASS`；8 条新 canary 全部变红并干净还原。
  **过程中结构测试抓到一次真实违规**：`README.md` 里写死了项目标识，加进 `SYSTEM_LAYER`
  之后立刻被拦下（`FAIL project structure - 系统层写死了项目标识`）——
  这正是分根边界该起的作用，也说明新能力确实被约束住了。

### 读者审计的停止条件修了两处：加轮次上限、判红要区分「真退出」和「最想跳过」

- **加轮次上限**：`reader-audit.md` 的「什么时候停」现在第一句是——**最多两轮**。
  第一轮审 → 改 → 第二轮审 → 改 → **交付**，之后不管还剩什么，都记 `BACKLOG.md`，不再审。
- **判红第 2 条要区分「真退出」和「相对最想跳过」**：问读者「哪一段你最想跳过」，**他总会挑一段**——
  这是问题的形式决定的，不是文章的问题。判红的是「读到这儿我不读了」，不是「这段相对最没意思」。
  判据写成加粗的一句：**卡了不等于走了**。
- **为什么**：2026-09-28 第一篇稿子审了**十六轮**。前几轮是必要的——建立检查、撞出系统缺口、
  渠道从「先不定」改成今日头条后内容取舍全变。但后十轮里有一半的返工是**改稿自己引入的**：
  第 10—13 轮读者抓到的「新问题」大半是上一轮改稿加段造成的——加一段，下一轮说它重复；
  再补一句，下一轮说它是空话。**改稿本身在制造问题，而审计把每个新问题都当成了新证据。**
  问题层次降到措辞之后，每一轮都还能挑出「可以更好」的地方，因为**这个层次永远有更好的版本**。
- **用户定的线**（原话）：「以后限定一下，最多做 2 轮检查，将发现的问题修复 2 轮即可，
  **文无第一，永远都有最好的版本**。」
- **为什么原有的停止条件拦不住**：判红四条和「看收敛方向」能判断「这一轮有没有问题」，
  判断不了「还该不该继续」。少了轮次上限，审计就没有终点。
- **影响**：「什么时候停」一节重写；`**判红四条**是硬标准，触发就必须改，改完再审一轮` 里的
  「改完再审一轮」删除（和轮次上限冲突）。`test/suites/test_content_assets.py` 新增 4 条断言，
  canary 从 36 增至 38 条。**这次改动顺带验证了一件事**：改规则文本时旧断言立刻变红
  （`content-assets-contract` FAIL，报「读者审计脚本缺失：判红四条…改完再审一轮」）——
  测试真的在守着规则，不是摆设。
- **验证**：新增四条 canary 都能红（38 条全部变红、还原干净）；两个项目门禁 `PASS`。

### 站 6 补第三条改稿规则：补某类读者的内容要给落点

- `reader-audit.md` 的「已知的坑」加一条：**补「照顾某类人」的句子，要给那类人认得出的落点。**
  判据是「把新加的那句读给那类人听，他能说出『那我明天做什么』吗？」
- **为什么**：第十二轮读者指出「让人相信的镜头」一节默认读者有厂（「车间里有活、检测在做」），
  补了半句「没有工厂的，拍你手上正在办的事」。第十三轮读者**正是贸易商**，判词分两半——
  「**是全文唯一戳到我的地方**」（方向对了），「什么叫『手上正在办的事』？拍我验货？跟工厂打电话？
  一个例子都不给。**这是全文最大的空档。**」（落点没有）。那半句把他**包含进来**了，没给他**下一步**。
- **它和已有的「改稿优先删」不是同一条**：那条管新内容和旧内容**重复**，这条管新内容**停在抽象层**。
  对照同一节的写法——另外两个判断后面都跟着读者认得出的动作（「原料怎么进、机器怎么走、质检卡在哪一道」），
  只有新补的这半句没有。**隐性的写法惯例拦不住人**，写下来才算数。
- **和受众复核第五条的关系**：那条问动作对这类人**成不成立**，这条问动作对这类人**够不够具体**——
  同一根线的两端。
- **影响**：站 6 第三道的判据多一条。`test/suites/test_content_assets.py` 新增 2 条断言，canary 34 条。
- **验证**：新增两条 canary 都能红；两个项目门禁 `PASS`。

### 两轮实测补的两条规则：改稿优先删、动作要对得上读者的当前状态

- **`reader-audit.md` 加「改稿优先删，不优先加」**，判据是「给每个新增段落找出它和哪一段说的是同一件事」——找得到就是重复，该做的是替换不是追加。
- **`positioning-and-audience.md` 的受众复核清单加第五条「给的动作，读者现在做得了吗」**。
- **为什么**：第八、九轮读者审计暴露的两个模式，都不是文章写错了，是**改稿手法和定位精度本身有问题**。
  - **重复是我自己加出来的，连着两轮。** 第六轮读者说某段重复，查下来是我在上一轮把内容挪进另一节却忘了删原位；第八轮我又为了呼应账号简介补了一段，和已有的「接住需求不创造需求」撞了。读者抓到的「想跳过」，两次都源自上一轮的追加。**加的内容必然跟已有的争同一个位置。**
  - **文章承诺的动作，对受众的一种状态不成立。** 第八轮读者：「开头问的是『要不要给网站加视频』，结尾唯一能马上做的是『把已经传上去的视频标题改好』。我要是真一条视频都没有呢？那这节我什么都做不了。两个前提对不上。」站 1 的受众坐标只写了「他是谁」，没写「他手上现在有什么」——同一个身份下，有视频和没视频是两种状态。
- **影响**：站 6 两道检查的判据各多一条。`test/suites/test_content_assets.py` 新增 3 条断言，canary 32 条。
- **验证**：新增两条 canary 都能红；两个项目门禁 `PASS`。

### 站 6 加第三道「读者审计」：第一次有门问「读者读不读得下去、拿不拿得走」

- **站 5** 新增产出物：写完正文，逐节（按 `##`）写一句「读者获得」——这一节让读者从什么状态到什么状态。写不出「到什么状态」的节就是凑数，删掉重写。这张表进任务的 `## 交付`，站 6 拿它对照。**此前站 5 只有一句「每一段都要能回答：这段是给谁写的、他读完多知道什么」——规则在，但产出里没有任何东西承载这个答案，自己说「能回答」就过了。**
- **站 6** 从「两道检查」改名「三道检查」，新增第三道**读者审计**：必须用 Agent 工具起一个独立 agent，只给它成稿全文和读者身份，不给任何写作背景。六个问题（点不点 / 哪里想退出 / 逐节多知道了什么 / 能复述什么 / 会不会转 / 打算做什么），逐节对照站 5 的声明，判红四条，红了逐条处理。
- 新增 `capabilities/content-production/reader-audit.md`：提问脚本全文、判红标准、**什么时候停**、抓出来的问题分两类、以及「论证层的问题读者审计在替受众复核补位」。这个文件是审计能不能真问出东西的地方——问法一软，agent 会还你一篇合格的摘要，你会误以为审计通过了。
- **站 5 产出路径**从硬编码 `content/packages/blog/` 改成 `content/packages/<channel>/`，并加规则「渠道定了就要把稿子移过去」。**路径是渠道的登记处**——稿子住在 `blog/` 而实际发头条，系统里就查不到「这篇是给头条的」。
- `test/feature_registry.json` 新增 `reader-audit` 功能；`test/suites/test_content_assets.py` 新增 14 条断言；`test/canary.json` 从 14 条增至 28 条。
- **为什么**：用户在生产现场提出的判断——「**写完之后，我感觉没有一套从用户阅读体验角度的自检**……这似乎是设计的缺陷，而非仅仅是执行的问题」。查下来确实是设计缺陷：站 6 原有的两道检查**全是否定式的，而且都是写稿的人自己审自己**——它们只能防止变差，不能产生变好。用户原话里的「没有灵魂、文字的堆砌」，对应的正是「没有任何一道检查问过读者读到哪儿会走」。
- **为什么必须换人而不是换标准**：2026-09-28 的实测，同一篇稿子交给独立 agent，它抓出六条问题，写稿的人自审**一条都没抓到**。判词是「**这篇文章把我劝住了，但没把我劝动**」。这不是标准不够严，是视角的问题——写稿的人知道每一段想表达什么，所以读不出读者读不到什么。
- **实测的收敛过程**（这是这条规则值钱的地方）：同一篇稿子连审五轮，问题层次逐轮变深——**措辞**（身份交代句是划走点）→ **结构**（「它让我做题，没给我做完题之后的下一步」）→ **论证**（「一百人零询盘不是流量不够」「哪一步要拍新视频了？都不需要」）。上一轮修掉的东西没再出现，说明审计真的在审新版，不是随机挑刺。
- **因此补了「什么时候停」**：判红四条是硬标准，触发就必须改；不触发判红、读者只说「这样更好」的，记进 BACKLOG 或留到下一版，**不阻塞交付**。没有这条线，审计会变成无限循环——读者永远能挑出「可以更好」的地方。同时写明：**如果新一轮又抓出同量级的结构或论证问题，那是这一稿的底子有问题，退回站 5 重写，不要在上面继续糊。**
- **影响**：站 5、站 6 的产出物变了，任务单据的 `## 交付` 区块要多记两项（读者获得表、审计六问与逐条处理）。`PLAYBOOK.md` 八站表同步。
- **验证**：门禁 14/14 `PASS`，在 `ksw-geo` 和 `video-album` 两个项目上各跑一次；canary 28 条全部变红、还原干净。

### 站 3 加第二条判断标准：关键词不许有歧义

- 站 3 原来只有一条判断标准——「只读开头，读者以为这篇文章要讲什么？」它管的是**判断有没有传出去**。
- 新增第二条：**核心判断里的关键词，读者理解的和你说的是不是一回事？** 把每个关键词单独拿出来问「一个没读过前文的人看到这个词会想到什么」。产出物：每个关键词写一句「读者会怎么理解它」，进任务的 `## 交付`。
- **为什么**：2026-09-28 六轮读者审计里，**有两轮独立卡在同一句上**——核心判断「视频改的不是转化率，是客户『看懂』和『相信』这两步的成本」。「转化率」作者指的是「询盘除以访客这个比值」，读者读成「客户从看到到下单的整个过程」，于是这句话被他读成「视频对成交没用」；而下一段又说视频能让人看懂和相信，**在他看来就是自相矛盾**。站 3 原来的检查一条都没拦住：它只问「传出去了没有」，不问「传出去的是不是那个意思」。
- **影响**：站 3 的产出多一行。`test/suites/test_content_assets.py` 新增 2 条断言。
- **验证**：canary 两条新增破坏点都能红（总 30 条全部变红、还原干净）；两个项目门禁 `PASS`。

### 修掉渠道包统计口径：产出统计必须跟着路径约定走

- `test/run_quality_gate.py` 的 `channel_packages` 从「数 `copy.md`」改成「数渠道包目录」（含 `article.md` 或 `copy.md` 的 `<channel>/<idea>/<topic>/` 目录）。
- **为什么**：旧口径建立在「主稿固定住 `blog/`」的假设上——它数的是「派生了几个其他渠道版本」。同一天站 5 把主稿路径改成按渠道参数化，主稿住进目标渠道目录之后，这个口径就数不到它了：项目里明明有一个 `toutiao` 渠道包，门禁报 **`渠道包: 1 → 0`**。
- **这类 bug 的形状**：和 `CLAUDE.md` 里记的「新增隔离字段必须追溯所有写入路径」同源——**改了路径约定，统计口径没跟上，数据在库里但报表看不见**。不报错、不抛异常，只是数字静默变少。而「产出变少判 FAIL」这条信号本来就是为「产物消失不报错」设计的，口径一旦失真，它自己就成了那个不报错的地方。
- **影响**：`video-album` 的 `output_baseline.channel_packages` 6 → 8——不是新产物，是两个只有 `article.md` 的包被正确数出来了，note 里写明原因。
- **验证**：新增 2 条单元测试（三种包形态都要数到、删掉包数字要跟着掉）；canary 把代码改回旧口径能红；两个项目门禁 `PASS`。

### 八站接入受众坐标：第一次有门问「有人愿意读完吗」

- 文章流水线八站接入**已有的**定位卡机制（`positioning.json` + `validate_positioning.py`），没有新造一套：
  - **站 1** 改名为「读任务，查事实，定受众坐标」。品牌/产品内容先看事实包里有没有定位卡，没有就按 `positioning-and-audience.md` 建草案并跑校验器；有就复用并检查 `revision`。新增四个必答问题（他是谁 / 他卡在哪 / 他读完会做什么 / 他现在相信什么错的），每一问都标了用在后面哪一站。
  - **站 3** 核心判断的三半必须从站 1 的受众坐标来。「读者现在以为」来自「他现在相信什么错的」，「实际上」来自「他卡在哪、你要把他带到哪」。
  - **站 5** 新增三条：每段都要能回答「这段是给谁写的、他读完多知道什么」；**事实纪律要求的是「不夸大」，不是「写免责声明」**——先给读者能用的，来源标注一句带过；正文写完后生成**至少 3 个**标题候选，每个写明押的是受众坐标里的哪一项，关键词原文照抄不算做标题。
  - **站 6** 改名为「作者化检查与受众复核」，新增第二道检查。作者化检查问「像不像 AI」，全是否定式的，只能防止变差；受众复核问「有没有人愿意读」，复用定位方法的复核清单。结果登记进定位卡的 `applications`，含 `artifact_sha256`。
  - **站 7** 交付列表补上受众坐标、标题（选定 + 落选）、受众复核结论。
- 外部顾问清单从 3 行扩到 5 行，补上**求好**类的两站（站 4 借 `dbs-hook` 看开头留不留得住人、站 5 借 `dbs-spread` / `dbs-resonate` 看标题和正文点不点得进去）。原先只有站 1、3、6 三行，全是防错。
- `test/suites/test_content_assets.py` 新增 `check_audience_coordinate()`，`advisor_map()` 改成支持一站借多个顾问（站 5 同时借两个）。
- 顺手修掉两个**接上去才发现**的缺陷，都是「照着文档敲必然失败」的那种：
  - `capabilities/geo/scripts/validate_positioning.py` 的 `--root` 默认指向**系统根**，但定位卡和它引用的事实包都在**项目根**——意味着站 1 那条校验命令照着文档敲一定 FAIL，而文档是对的、错的是默认值。改成运行时调 `find_project()` 解析（不在 import 时调，否则单测 import 这个模块也得先存在一个项目）。新增测试 `test_cli_finds_project_root_without_root_flag` 守住它。
  - `positioning.schema.json` 把 `boundaries` 描述成普通字符串数组，但校验器按 **fact_ids** 处理（`references(..., boundary=True)`，允许 `prohibited_claim` 作为边界依据）。契约说错了，下一个写定位卡的人——或 Agent——还会踩同一个坑。**第一次写这张卡就踩了**：8 条边界全被当成「找不到的事实」。schema 描述改成说明它是 fact ID 列表，并写清为什么（文本留在 facts.jsonl，单一真源）。
- **为什么**：2026-09-28 第一篇真实文章写出来后暴露的偏差——八站里**没有一站问过「写给谁看」**。受众只在站 5 的一句话里出现过，没有产物、没有检查、没有停机点。结果是所有门都是「不许犯错」的门：事实包防说错、站 3 防跑偏、站 6 防像 AI——**没有一扇门问「有人愿意读完吗」**。具体表现是讲 Roger Wu 案例那段：标注齐全、免责声明到位、完全合规，但读者读完不知道自己能拿走什么。
- **为什么复用定位卡而不是新造「受众卡」**：`positioning.json` 的 schema、校验器、测试**早就存在**，只是文章流水线从未接入。再建一套会产生两个真源——Agent 读哪个都能自圆其说。宪法第 3 条：不许建立第二套事实。
- **影响**：站 1、3、5、6、7 的产出物变了，任务单据的 `## 交付` 区块要多记三项。旧任务不受影响，但下次推进时会多问受众坐标。`PLAYBOOK.md` 第三节八站表、第五节 dbs 表同步更新。
- **验证**：门禁 14/14 `PASS`，在 `ksw-geo` 和 `video-album` 两个项目上各跑一次。

### 定位卡复核补三处硬校验：登记了不等于核过了

- **做了什么**：`capabilities/geo/scripts/validate_positioning.py` 的 `applications` 校验改了三处：
  1. **按产物路径去重，不再按渠道**——原来同一个 `channel` 只能登记一篇成稿，同渠道发第二篇会被判重复；
     现在唯一键是 `artifact_path`，重复的**产物**才拒绝。
  2. **复核绑定实际文件的 SHA-256**——`review.artifact_sha256` 必须等于当前文件算出来的哈希，
     正文改一个字，复核结论立刻失效，要重审。
  3. **证据类型走显式白名单**——`evidence_type` 必须在 `EVIDENCE_TYPES` 里；缺 `source_id` /
     `source_locator` / `verified_at` 的、以及越界的 `owner_statement`（`category` 不在四类 owner 里）
     都进不了 `ready`。
- **为什么**：独立检查发现的三个漏洞，共同点是**校验器把「登记了」当成了「核过了」**。
  按渠道去重直接**阻止同渠道多篇创作**——一个渠道本来就该能有多篇不同产物，这是把数据模型写窄了；
  复核只记 status / reviewer / note，**和实际文件没有任何绑定**，改完正文旧复核照样放行；
  证据类型没有任何校验，写个不存在的类型也算数。三条都会让「已复核」这个状态失去意义。
- **影响**：`validate_positioning.py` + `capabilities/geo/tests/test_positioning.py`（新增 4 条：
  同渠道多篇、正文变化使复核失效、未知证据类型与缺来源定位、`owner_statement` 越界）。
  定位卡的 `applications[]` 现在要求 `artifact_path` 指向项目内已存在的文件。
  **草案行为不变**：不带 `--require-ready` 时缺 `artifact_path` 只算 unresolved，草案照样能存。
  `00-meta/content-engine/spec-positioning-writing.md` 状态从 `in-review` 改成 `done`。
- **验证**：29 项 GEO 单测全过；两个项目门禁 15/15 `PASS`。两张存量定位卡实测——
  `ksw-geo` 那张 `--require-ready` 仍通过；`video-album` 那张是 `draft` + 复核 `pending`，
  不带 `--require-ready` 时 `errors: []`（草案可保存），带 `--require-ready` 被正确拦下。

### canary 工具：把「测试必须能失败」从人工手敲变成可重跑

- 新增 `test/tools/canary.py` 和 `test/canary.json`。逐条破坏被测对象、跑测试、确认变红、还原；还原后复跑一次，确认没把文件改坏。
- 破坏点写在 `test/canary.json` 里，和断言放在一起维护。一条破坏点可以跨文件（去掉一个概念，要在它出现的每个地方都去掉）。
- 新增 `test/suites/test_canary.py`（5 条），守住 canary 自己的核心逻辑：**替换所有出现，不是第一次**。
- 测试数 13 → 14，`test/baseline.json` 同步更新。
- **为什么**：这套系统一直有「写完测试要做 canary」的规则，但每次都是临时手敲一段 bash，跑完就没了——**同一个脚本敲第三遍就是浪费**。更关键的是，手敲的版本**第一次就写错了**。
- **它第一次跑就抓到了什么**：9 条 canary 里 5 条是空转的。原因是断言查的是**关键词是否出现**，而那个关键词在被断言的那一节里出现了两次（比如站 1 既有「**定受众坐标。**」又有「受众坐标必须能回答四个问题」）——删掉定义行还剩一次，断言照样绿。改成断言**整行定义**后 13 条全红。**测试文件里第 136 行早就写着这条教训**（「关键词在别处也有，那种断言删掉定义行也不会红」），我还是犯了——说明光有规则不够，得有工具。
- **它还抓到了第二个错**：修完断言后跑 canary，13 条全红，但**还原后复跑失败**。查出来是站 6 那条断言自己写错了（`` `shasum -a 256` `` 末尾多了一个反引号，原文里反引号包的是整个 `` `shasum -a 256 <成稿路径>` ``）。canary 那条之所以变红，是因为整行被删掉了——**破坏过头会掩盖断言的错**。还原后复跑这一步就是为了抓这种。
- **为什么不做成门禁的一部分**：它故意把文件改坏再还原，不该在每次提交时跑。它是「写断言的人」的工具，用在写完之后、提交之前。

### 第二个项目根建起来：从旧系统的工作副本里拆出 `Kingsway GEO 内容`

- `~/kingsway/kingswaywork/05kingsway运营动作/hq-geo-ksw` 原来是一份**旧系统**（HQ-GEO Engine v2.8，提交 `9421059`）的工作副本，配成 Kingsway 实例。`00-meta/` 到 `07-prepublish/` 加 `lib/`、`test/`、`logs/` 全是系统层代码，另有 46 项未提交的本地改动。现在拆开：系统层代码全部删除，实例层素材保留，跑脚手架建成正式项目根（slug `ksw-geo`，名 `Kingsway GEO 内容`）。
- 保留下来的素材搬进 `research/raw/legacy-hq-geo-ksw/`：102 行关键词研究、720 行平台采集、17 行竞品引用监测、32 篇内容索引、**28 篇从没发布过的草稿**，以及旧系统自己的 `README` 和 `TEST_PLAN`。
- 删除前把整份工作副本（含 `.git` 和那份带 API key 的 `.env`）归档到 `/Users/conan/project/hq-geo-ksw-archive-20260928.tar.gz`（71MB / 3746 条，gzip 校验通过，抽查 5 个关键路径全在）。
- **为什么拆**：这个目录要当**创作项目**用，不是当系统用。但旧副本整个是系统层目录，`test_project_structure.py` 会直接判红——项目根里不许出现 `capabilities/`、`skills/`、`test/`、`00-meta/`。
- **为什么 28 篇草稿不进 `content/packages/`**：它们不是这套八站跑出来的。混进去会污染 `output_baseline`，而那个基准正是用来量「同一套系统在不同项目上表现如何」的——混了旧系统的产出，这个数就不准了。它们现在是 `research/raw/` 里的**素材**。
- **为什么删掉 `.git` 重新 `init` 而不是沿用**：旧仓库的远端 `github.com/whhxf/hq-geo` 是**公开**的，而且和系统根共用同一个远端。留着它等于给这个项目根留一条把内容推到公开仓库的通道。
- 拆完紧接着把文件夹从 `hq-geo-ksw` 改名为 **`kingsway-geo`**。旧名字里带着系统名 `hq-geo`，而这个目录现在是项目——名字本身就在制造「这到底是系统还是项目」的歧义，本次会话已经被它绊了一次。
- **影响**：系统层代码一行没改。`PLAYBOOK.md` 第二节（项目数量）和第六节（第二个项目的状态、系统验证结论）同步更新。项目根新增 `CLAUDE.md`、`.hq-geo.json`、`LEARNING.md` 和全套实例层目录。
- **改名为什么几乎零成本**：门禁报告按 `.hq-geo.json` 的 slug 存（上一轮刚改的），项目里也没有任何一处写死自己的路径。改名后重跑，报告仍落在 `test/reports/ksw-geo/`，历史没丢——这正是上一轮那个改动的价值。
- **验证**：门禁 13/13 `PASS`，产出基准自动建立（6 项），报告按 slug 写进 `test/reports/ksw-geo/`。**这是分根之后第一次在第二个真实项目上跑门禁。**

### 第一个项目搬进 Kingsway 工作区，门禁报告改用 slug

- 项目根从 `/Users/conan/project/hq-video-album` 搬到 `/Users/conan/kingsway/kingswaywork/05kingsway运营动作/视频画册推广`。51 个内容文件按校验和逐个核对后搬迁，`git init` 新建仓库（旧目录的 `.git` 没有任何提交，无历史可丢）。
- 目标目录**本来就有东西**：`AGENTS.md`（工作区自己的规则）、`研究/`、`选题库/`，2026-09-08 建的。这些**原样保留**，系统不往里写。
- `test/run_quality_gate.py` 的 `report_dir()` 改用 `.hq-geo.json` 的 slug，不再用文件夹名。slug 读不到时退回文件夹名。
- `load_json()` 在标记文件损坏时报可读错误并停机，不再抛 traceback。
- 系统文档里指向旧路径的四处同步更新（`README.md` ×2、`CLAUDE.md`、`PLAYBOOK.md`、`BACKLOG.md`）。
- **为什么搬**：项目根放哪是项目自己的事，不是系统的。这个项目的内容属于 Kingsway 运营，就该和 Kingsway 的其他资料住在一起，而不是在 `~/project/` 下和一堆无关代码项目做邻居。分根的价值就在这里——搬的时候系统一行没改。
- **为什么报告改用 slug**：刚搬完一次就发现，文件夹名当报告目录名意味着**每次搬项目都会丢报告历史**。slug 存在项目标记里，跟项目走。
- **为什么标记损坏要停机而不是降级**：降级成「没有基准」会让门禁按当前状态重建一次产出基准，而当前状态可能正是被删空的那个——那等于用一次静默重建盖掉「稿子没了」这个信号，而这条信号正是产出基准存在的理由。报错文案给出下一步命令，不让人对着 traceback 猜。
- **影响**：项目位置变了，所有 `--project` 参数和文档里的路径要跟着改。系统层代码只有 `report_dir`/`load_json` 两处改动。旧目录 `hq-video-album` 已删除（内容全部迁走并核对过）。
- **验证**：门禁 13/13 `PASS`，三种调用方式各跑一次（`--project` 绝对路径、在项目根里不带参数、在项目子目录里不带参数）。另建全新空项目跑一次作对照。`report_dir` 四条 canary 全过：slug 存在进 slug 目录、slug 缺失退回文件夹名、标记损坏判失败且无 traceback、还原后回正常。

### 新建项目改成一句话，不用记命令

- `skills/content-orchestrator/SKILL.md` 新增路由分支「从零开始（还没有项目）」：用户说「我有个新项目」时，先确认目录、跑脚手架、切到项目根，再继续内容路由；并明确「不要在系统根里建任务或稿子」。Skill 的 frontmatter description 同步加上这个触发词，否则 Skill 根本不会被唤起。
- `PLAYBOOK.md` 第二节「新建一个项目」改成先说人话、命令降为备选。
- **为什么**：分根之后新建项目成了常规动作，但入口只写在文档的命令行里——用户得先知道有 `init_project.py` 这个脚本、知道它叫什么、知道系统根在哪，才能建项目。这是把系统的复杂性推给了用户。系统已经有一个自然对话总入口，这件事本该由它接住。
- **影响**：只影响新项目的创建路径，已有项目的读写不受影响。系统根和项目根的分根规则不变。
- **验证**：门禁 13/13 `PASS`，在 `hq-video-album`（产出 6 项与基准一致）和脚手架新建的空项目（产出基准自动建立）上各跑一次。

### 路由表里的路径现在会被校验

- `test/suites/test_content_routing.py` 新增两条断言：① 编排器必须保留脚手架入口；② 六个创作入口里出现的每个 `capabilities/`、`skills/`、`test/`、`00-meta/` 路径都必须真实存在。
- **为什么**：Agent 照着路由表跑，路径写错时失败现场在用户的对话里，不在这个仓库里——没人会回来修文档。同一类问题这次会话已经出现过一次：系统让 Agent 用 `ego-browser`，而本机根本没有这个工具，7 个文件都写着它。
- **影响**：以后在 Skill 里写错一个文件路径，门禁直接变红。改文档时如果引用了还没建的文件，也会被拦住。
- **验证**：新增断言各做一次 canary——删掉编排器里的脚手架引用（红）、把 `check_authorial.py` 改成不存在的 `check_authored.py`（红）；另做一条真对照，新增一条指向真实存在文件的引用（绿，不误报）。

### 系统与项目分成两个根

- 新增根目录 `project.py`：项目根解析唯一入口。优先级是「显式参数 > 环境变量 `HQ_GEO_PROJECT` > 从当前目录向上找 `.hq-geo.json`」，找不到时打印三种给法和新建项目的命令，不抛裸异常。
- 新增 `capabilities/project-scaffold/scripts/init_project.py`：建项目根。**已存在的文件一律不动**，只报告跳过——覆盖不可逆，跳过可恢复。同时拒绝把系统根当项目根。
- 新增 `capabilities/fact-packs/`：`facts/scripts`、`facts/tests`、`facts/schemas` 整体搬进来。
- 新增 `capabilities/content-production/tasks/`：`tasks/README.md` 和 `_template.md` 搬进来（格式约定是系统层的，任务单据才是项目层的）。
- 新增 `capabilities/content-production/learning-loop.md`：学习闭环的完整约定。项目根的 `LEARNING.md` 只留格式和记录，约定指向系统。
- 项目根 `/Users/conan/project/hq-video-album` 建立，实例层整体迁入：`tasks/`、`facts/`、`topics/`、`content/`、`assets/`、`data/`、`research/`、`LEARNING.md`。系统根里这些目录**全部消失**。
- `test/run_quality_gate.py` 加 `--project`，并通过 `HQ_GEO_PROJECT` 传给每个测试子进程；报告改为按项目分目录写 `test/reports/<项目名>/`。
- `test/baseline.json` 升到 schema 2：只留 `health`。产出基准搬到各项目自己 `.hq-geo.json` 的 `output_baseline`，首次运行建立、之后不自动更新。
- `test/suites/test_project_structure.py` 重写为分根边界检查，两条新不变量：**系统根不得出现实例层目录**、**项目根不得出现系统层目录**。
- **为什么**：用户要「从根上分开，这样可以在不同项目里测试这个系统的可靠性和有效性」。混在一个目录里，第二个项目的数据会和第一个挤在一起，分不清是方法的问题还是这一个项目的问题。分根之后，两次跑出来的差异只可能来自项目。
- **顺带被逼着修掉的两个老问题**（分根让它们从「应该改」变成「不改就跑不起来」）：`facts/` 里的系统层代码必须搬家，否则每个项目各存一份校验器；`tasks/README.md` 是跨项目约定，不能只存在于某一个项目里。
- **新发现并修掉的三处**：① 新项目开局就红——`validate_deliverables.py` 和 `validate_fact_pack.py` 把「没有产物」当成了「产物有错」。改成空集合 `PASS`，因为校验器的职责是「存在的都要合法」。② 上面这个改动会丢掉「数据被删光」的信号，所以补上**产出比基准变少直接判 `FAIL`**——产物消失通常不报错、页面就是空的，门禁要是还绿着就没人会发现。③ `test_tasks.py` 里 `test_template_and_readme_are_skipped` 是空转测试（读真实目录，目录本来就是空的），改成用临时目录，`task_files()` 也因此改为接收目录参数。
- **一个刻意的设计**：`find_project()` **不在 import 时调用**，只在真正要读实例层的函数里调用。否则单测 import 一个纯函数，也得先存在一个项目。
- **影响**：`AGENTS.md` 分层规则重写（两个根）；`CLAUDE.md` 加第〇节「这是系统根，不是项目根」；`PLAYBOOK.md` 新增第二节「系统在哪，项目在哪」并顺延后续各节；`README.md` 目录结构拆成系统根/项目根两张图；`TEST_PLAN.md`、`test/README.md`、`BACKLOG.md`、`skills/README.md`、`skills/article-pipeline`、`skills/content-orchestrator`、`skills/geo-monitor`、`capabilities/creative-handoff/README.md` 同步路径。门禁命令从 `python3 test/run_quality_gate.py` 变成必须带 `--project`（在项目根里跑可省略）。
- **验证**：门禁 13/13 `PASS`，在**有真实产物的 hq-video-album** 和**全新空项目**上各跑一次，产出 6 项与基准一致。**28 条 canary 全部能红**：7 个实例层目录出现在系统根、`LEARNING.md` 出现在系统根、4 个系统层目录出现在项目根、系统根缺 `project.py`/`init_project.py`、项目根缺 `facts/`/`.hq-geo.json`/`LEARNING.md`、5 个系统层文件里写入项目标识、删一份制作简报、产出基准调高、学习库格式定义被删；以及两条**该绿必须绿**的对照——产出基准调低（产出变多不是问题）和门禁报告里出现项目名（生成物不算系统层写死标识）。另单独验了 `init_project.py` 的三条安全路径：已存在的文件跳过且报出来、已是项目根时拒绝、系统根不能当项目根。

### 修掉一个不存在的工具名：`ego-browser` → `web-access`

- `AGENTS.md`、`capabilities/geo/README.md`、`capabilities/geo/methods/evidence-and-entity-policy.md`、`skills/geo-monitor`、`skills/geo-research`、`skills/geo-website-renderer`、`00-meta/content-engine/sources.md` 共 8 处把联网操作指向 `ego-browser`。
- **为什么**：本机没有这个工具。真实可用的联网通道是 `web-access`（CDP 直连本地 Chrome，携带登录态）。系统在教 agent 用一个不存在的东西——真跑到需要联网的那一站才会暴露。
- **影响**：只改工具名，不改任何流程判断。
- **验证**：全仓库 grep `ego-browser` 零命中；门禁 13/13 `PASS`。

### 外部顾问：把 dbs 从「要不要整合」变成「什么时候借」

- 新增 `capabilities/content-production/external-advisors.md`：外部顾问登记表。写明三条铁律（不依赖 / 输出是线索不是依据 / 不搬文本）、三站可借清单、禁用项、以及为什么它只能是顾问不能是部件。
- `skills/article-pipeline/SKILL.md` 站 3 新增**开头约定**——核心判断的「实际上 ___」必须出现在开头，判断标准是「只读开头，读者以为这篇文章要讲什么」；站 5 新增回头核对；新增「外部顾问（可选）」一节。
- `PLAYBOOK.md` 新增第四节「什么时候借 dbs」，原四、五、六节顺延为五、六、七节。
- `BACKLOG.md` 新增「dbs 能力：已调研，等触发」一节，7 条缺口各带触发条件；`00-meta/content-engine/01-product-definition-and-assessment.md` 第 6 节加「本节是待办，不是现状」标注。
- `test/suites/test_content_assets.py` 新增 `check_opening_convention`、`check_external_advisors`；`test/feature_registry.json` 新增功能 `external-advisors`，并修正 `article-pipeline` 的名称（七站 → 八站）。
- **为什么**：用户要求「定义什么时候可以借用 dbs 的能力辅助创作，且每个项目都能触发」。调研 13 个 dbs skill 后确认**没有东西可以整合**——创作技巧类全部零代码，是给模型看的说明书，不是 API；被宣传的词表资产在公开仓库里不存在；CC BY-NC 4.0 商业主体署名也不能搬。真正该做的是**划清借用边界**，不是集成。
- **同时补上一个真缺口**：八站、策略库、`check_authorial.py` 三处对「开头」零命中——系统只知道开头**不能**写成什么样（Gate D 抓「钩子—痛点—承诺」套路），从不知道**该**写成什么样。两个调研 agent 从不同 skill 独立指到这里。**这个问题必须先存在，第一次生产才可能把它记成卡点。**
- **影响**：机制放在 `skills/article-pipeline/` 和 `capabilities/content-production/`，**不在任何单个项目里**——所有项目走八站时自动生效，不需要逐项目配置。dbs 没装、改名、升级后行为变了，hq-geo 照常跑完八站。
- **验证**：门禁 13/13 `PASS`；15 条断言逐个 canary 全部能红（删站 3 约定、删判断标准、删站 5 核对、删三条铁律、删禁令、删覆盖文件名说明、断流水线指针、删八站站 6 行、删手册站 4 行、改登记表站 3 指向、删手册触发条件句、删手册禁令、整体移走登记表）。**第一次 canary 时「手册指向登记表」那条没红**——手册里提到了登记表两次，删掉一处另一处还在。改为**三处借用清单的映射一致性断言**后能红，顺带把「三份清单会各自漂移」这个隐患也堵上了。

### 补上下半圈（自行车版本）

- 新增根目录 `LEARNING.md`：学习库。每次生产交付后追加一条，三个字段——**这次**（发生了什么）、**下次**（怎么做）、**去向**（`BACKLOG` / 策略库 / 只是记着）。
- **「去向」是这一版的关键设计**：它让学习记录有明确出口，写什么就真的去做什么。没有它，学习库只是记录，不会变成改进。
- `tasks/README.md` 新增「分发登记怎么填」：明确记五列（日期 / 渠道 / 链接 / 效果 / 备注），效果可以后补，**「没效果」也要写**。`_template.md` 的表格同步加「效果」列。
- `skills/article-pipeline/SKILL.md` 从七站扩到八站：站 8 写学习记录。**前七站产出一篇稿子，站 8 才让这次生产对下次有用。**
- `test/suites/test_content_assets.py` 新增 `check_learning_loop`：校验分发登记约定、学习库格式定义整行、流水线站 1—8 连续且站 8 指向学习库。
- `test/feature_registry.json` 新增功能 `learning-loop`（`partial`——约定建好但从未跑过）。
- **为什么**：用户要求「补全下半圈，先弄个自行车版本」。此前系统能证明自己没坏，但不能证明自己有用；宪法第 7 条要求的「写回积累」没有落点。
- **影响**：`tasks_delivered` 从 0 变 1 时，`LEARNING.md` 会写下第一条。根目录文档形成分工——`CHANGELOG` 记改了什么，`LEARNING` 记为什么改，`BACKLOG` 记还要改什么。
- **验证**：门禁 13/13 `PASS`；5 个新断言逐个 canary 全部能红（移走学习库、删格式定义行、改站 8 标题、删站 5、断开站 8 与学习库的引用）。**第一次 canary 时其中 2 个没红**——`"站 8"` 能匹配 `"站 8x"`，「去向」这个词在文件别处也有；改成断言完整格式行 + 按站号逐个检查后能红。

### 高级测试人员验收

- 对全部 13 个测试做 canary：逐个故意破坏被测对象，确认变红，再还原。**13/13 都能真的变红，不存在永远为绿的测试。**
- 同时记录每个测试**守不住**什么，形成遗留清单：
  - 四处「对象整体消失时不红」——`task-contract` 空目录直接 `PASS`、`creative-handoff-contract` glob 命中 0 时空转、`quality-gate-unit` 用内联 fixture 不加载真实 registry、`fact-pack-contract` 删必填槽位仍 `PASS`
  - `content-deliverable-unit` 的词表是存在性断言——8 个程度词砍到只剩 1 个，只要断言用到的那 1 个还在就不会红
  - `capture_fact.py` 的 5 条校验分支无测试覆盖
  - 13 个测试里 0 个 `workflow` 级——流程类功能只有 `static` 级字符串检查
- 发现覆盖率算法的弱点：`coverage_percent` 的判据是「`test_ids` 非空」，绑一个不测该功能的测试照样 100%。`article-pipeline` 就是实例——它绑的测试只检查 `SKILL.md` 里有没有那几行字。
- **为什么**：用户要求「作为高级测试人员验收系统，看看每个功能组件是否都恰如其分在工作，可被验收」。全绿不等于有效——**测试必须能失败才算测试**。
- **影响**：确认门禁里没有假测试，同时暴露 6 处覆盖边界，全部记入 `BACKLOG.md`。
- **验证**：每次破坏后文件哈希与备份逐一比对一致；终态门禁 13/13 `PASS`。

### 建立使用手册与遗留清单

- 新增根目录 `PLAYBOOK.md`：三个入口（发布任务 / 推进任务 / 检查系统）、系统的两个循环、当前进度、第一次生产验证怎么做。
- 新增根目录 `BACKLOG.md`：遗留清单。系统建设待办**不放** `tasks/`——那是内容生产单据，`stage` 从 `intake` 走到 `distributed`，混在一起会让任务状态失去含义。
- `CLAUDE.md` 新增第三条硬规则：系统变了就同步 `PLAYBOOK.md`，并写明什么情况必须改、什么情况不用改。
- 补上 `content/styles/` 目录与说明。此前 `AGENTS.md`、`README.md`、`article-pipeline` 三处声称它存在，实际不存在——`REQUIRED_PATHS` 只检查到 `content` 这一层。
- `test/suites/test_project_structure.py` 的 `REQUIRED_PATHS` 加入 `content/styles` 和 `tasks`。后者是实例层入口，此前被误删不会报警。
- 门禁的基准对比改为「无差异也要说一句」——此前产出与基准一致时完全静默，会被读成「没检查」。
- `README.md` 快速开始指向 `PLAYBOOK.md`，避免两处各写一份使用方法。
- **为什么**：用户要求把使用方法落成 playbook 并随版本同步；同时需要一份遗留清单，才能「一个一个 done 掉」。
- **影响**：`PLAYBOOK.md` 成为唯一的使用说明真源，`README.md` 只讲项目是什么。
- **验证**：门禁 13/13 `PASS`；`content/styles` 与 `tasks` 两个新断言 canary 能红（移走目录即 `FAIL`）；基准对比 canary 能报差异（改基准数字后打印 `articles: 0 → 2 (+2)`）。

### 建立变更日志与验收基准

- 新增根目录 `CLAUDE.md`，定义两条硬规则：改进必须写 CHANGELOG，改进必须可验收。
- 新增 `test/baseline.json`。基准分两类：`health`（测试数、覆盖率、耗时）下降即退步；`output`（任务、文章、渠道包、简报、事实包）只增不减才算系统在干活。
- 质量门禁每次运行追加一行到 `test/reports/history.jsonl`，并自动与基准对比。
- **为什么**：没有历史就没有趋势，没有基准就分不清改进和退步。宪法第 7 条要求判断权在人，但人要判断总得有数字。
- **影响**：`test/run_quality_gate.py` 新增产出统计、基准对比、历史追加三个环节。
- **验证**：门禁 13/13 PASS，耗时 0.56s。

### 建立文章流水线

- 新增 `tasks/` 任务单据：`README.md` 定义格式与区块归属，`_template.md` 供复制。一次生产请求一个文件，是实例层的入口。
- 新增 `capabilities/content-production/scripts/validate_tasks.py`，校验 frontmatter 字段、文件名一致性、区块完整性、状态枚举合法性。
- 新增 `capabilities/content-production/strategies/creative-strategies.md`：把 `00-meta` 里躺着的 10 个创作模式（P01—P10）落盘成可加载策略，每个模式补上「需要的素材」字段用于自动筛选。全部标注 `experimental`。
- `00-meta/content-engine/04-creative-strategy-library.md` 改为指针，只保留理论依据与历史同构，模式正文不再重复。
- 新增 `capabilities/content-production/styles/README.md`：风格靠看 HTML 示例选，不靠文字描述。含「吸星大法」——从外部样本提取风格特征存成条目，边界是**吸特征不吸文本**。
- 新增 `capabilities/content-production/scripts/check_authorial.py`：实现 `07-authorial-quality-system.md` 的 Gate C（模糊修饰语）与 Gate D（机器化模式）的确定性部分。只诊断不改写，不输出人类概率，不判定成败。Gate E 因缺作者语料固定报 `blocked`。
- 新增 `skills/article-pipeline/SKILL.md`：从任务到成稿的七站流程，每站有命名单据。
- 新增 `test/suites/test_content_assets.py`，校验策略库 10 个模式字段完整、风格约定的版权边界存在、任务约定区块完整。
- 删除 `content/articles/`——空壳目录，文章成稿实际落在 `content/packages/blog/` 内。
- **为什么**：用户要的工作模式是「在文件夹里发布任务 → Agent 提问补料 → 按流程产出 → 登记分发」。此前没有任务单据，没有策略落地，去 AI 味只有一份研究文档。
- **影响**：`content-orchestrator` 新增按任务路由；`feature_registry` 新增 4 个功能（task-intake、article-pipeline、authorial-check、style-selection）；测试从 11 个增至 13 个。
- **验证**：42 个单元测试通过；对策略库契约做 canary（删掉 P05 的「机制」字段）确认能红；作者化检查在真实文章 G1-02 上跑出 3 处命中。

### 重构质量门禁与分层边界

- 门禁从 3 个 profile（quick/full/release）改为 1 条命令。**为什么**：三档差别只有 3 个测试，全部跑完不到 1 秒；分档只会让人挑便宜的那档跑，然后误以为通过了。
- 新增 `test/suites/test_project_structure.py`：系统层（`capabilities/`、`skills/`、`test/`）不得出现任何项目标识，实例名从 `topics/` 和 `data/ideas/` 自动发现。
- `test_creative_handoff.py` 与 `test_deliverables.py` 去掉硬编码的 `video-album` 路径，改为自动发现 + 合成 fixture。
- `test_manifest.json` 与 `feature_registry.json` 升级到 schema 2；新增 `frozen` 字段记录已冻结但保留的功能。
- **为什么**：`video-album` 曾硬编码在 11 处，第二个项目无法复用同一套方法（宪法第 3 条）。
- **验证**：canary——往 `capabilities/geo/` 写入含 `video-album` 的文件，门禁变红；删除后恢复 PASS。

### 归档 01—08 编号管线

- 整体移出仓库到 `../hq-geo-retired-20260928/`：`01-intent` 至 `07-prepublish`、`lib/`、`test_fusion.py`、Playwright profile。共 4,820 行 Python、682 行 SKILL、993 行模板与规则。
- GEO 岛的 Skill 改为纯方法说明，去掉对老脚本的引用；`capabilities/geo/manifest.json` 新增 `execution_boundary` 声明不再附带执行器。
- 清理 `venv/`（283M）、`workbench/node_modules`（416M）、开发截图、Next.js 自动生成的 agent 文件、空壳 `skills/geo-prepublish/`。
- **为什么**：老管线操作的是占位数据（`brand.csv` 里是 `[你的品牌名称]`），当天真的生成过一份含「GEO 测试关键词 B」「测试信源 → https://test.com」的假周报；`test_fusion.py` 会写真实 `data/` 目录并留下测试数据的 `.bak`。
- **影响**：仓库从 760M 降到 8.8M。归档不等于删除，需要时可以从该目录取回任何文件。
- **验证**：`test_content_routing.py` 增加反向断言，老模块重新出现即失败。
