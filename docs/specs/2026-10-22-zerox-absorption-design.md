# 设计：吸纳 zerox 能力，补齐研究、尽调、故事线与成品输出

- 日期：2026-10-22
- 版本：v3.1（按三轮独立审查修订，审查记录见 `2026-10-22-zerox-absorption-review.md`）
- 状态：已获用户确认（2026-10-22）
- 范围：本仓库（Allen-skills）的后台能力。前端应用（不同系统提示词组合成的产品）不在本次范围。

## 0. 背景与目标

现有系统（router → scene-* → core-* → lib-*）能拆问题、选方法、核实、审查、综合，但有两处短板：

1. **没有成品输出能力**：只能交付 Markdown；正式报告、咨询图表、一页海报都依赖第三方 zerox skill。
2. **研究、公司尽调、材料整理的深度不够**：core-evidence 只做核实；scene-company 的公司画像只有一页；没有"材料 → 故事线 → 逐页内容"这一层。

zerox 的 skill 被直接安装时，描述会和 router 抢着触发；report-forge 自带一整套分析流程，会绕过我们的选方法、核实和审查关口。

目标：

- 把 zerox 6 个 skill 的全部能力吸纳进本仓库。凡是我们没有或不如它的都补齐，在完整实现其已有能力的基础上再优化。
- 吸纳后不再安装 zerox skill，杜绝绕过。
- 呈现风格改为 report-forge 的风格：图表、版式尽可能多样，废除"一页纸、够用就停"的呈现限制。
- 支持 PDF、Word、PPT 和文字要求作为输入。
- 渲染环境在本机（macOS arm64）原生安装并跑通。云端和 Docker 以后再做。
- 设计、开发、运行三个阶段都引入独立子代理审查，保证真实；输出标准只有一份。

## 1. 已确认的关键决定

| # | 决定 | 来源 |
|---|---|---|
| D1 | zerox 能力全部吸纳；没有或不如它的都补强；在完整实现其已有能力的基础上再优化 | 用户 |
| D2 | 有 Apache-2.0 许可的 3 个引擎（consulting-report-forge、thinkcell-charts、onepager）按"方案 C"并入：渲染代码原样复制、固定版本、只打必要补丁；SKILL 说明层由我们自己写 | 用户。onepager 的许可已核实：上游目录有 Apache-2.0 的 `LICENSE.txt`。现有 README 与 zerox.lock 写它"没有许可文件"是错的，本次一并更正 |
| D3 | 没有许可文件的 3 个（deep-research、due-diligence、storyline）按能力从零重写，不复制其文字和代码；细节要完整借鉴，不是只模仿 | 用户 |
| D4 | 呈现风格按 report-forge：图表、版式尽可能多样；废除"一页纸"及呈现条数上限。**只改呈现，不改分析规则**（"每个子问题默认一个方法、够用就停"保留；结论先行保留；核实关口对冲突的处理保留） | 用户（呈现与分析规则均已确认） |
| D5 | 输入为 PDF、Word、PPT 及文字要求；输出格式先按本设计，模板、logo、特定元素以后再加 | 用户 |
| D6 | 渲染环境本机原生安装；Docker 和云端以后再做 | 用户 |
| D7 | 渲染时引擎各自启动浏览器（report-forge 用系统 Chrome，onepager 用 Playwright 自带 Chromium），不用用户的日常浏览器。用户 9222 端口浏览器只在研究抓取兜底时使用：只读、不登录，需登录的站点先问用户 | 设计建议，用户未反对 |
| D8 | 全程引入独立子代理审查；输出标准只写一份，三个输出共用 | 用户 |
| D9 | 改动在 Allen-skills 仓库新分支完成，提 PR 审；entservice（普米）仓库不动 | 设计默认，用户未反对 |

## 2. 整体结构

```
入口      router（定场景、定深度：深度的唯一真源）
场景      scene-company  scene-topic  scene-bp-review  scene-personal
接收(新)  core-intake（PDF / Word / PPT / 文字要求 → 标准结构）
能力      core-framing → core-method-select → 分析 → core-synthesis → core-storyline(新)
            ├ core-evidence（核实；持有来源等级与核实关口的唯一标准）
            ├ core-research(新，开放研究包)
            └ core-diligence(新，公司研究与尽调)
质量      core-review（新增"成品审查员"；持有统一输出标准）
方法库    lib-consulting  lib-management  lib-personal
输出(新)  out-report（HTML + PDF） out-chart（PPTX + PNG + HTML） out-poster（PNG + HTML）
引擎(新)  vendor/report-forge  vendor/thinkcell-charts  vendor/onepager  vendor/vendor.lock  vendor/patches/
公共(新)  tools/lib/（ledger、schema、runtime、快照、检查）  tools/bridge/（三个转换脚本）
          tools/doctor.py  tools/vendor_sync.py  tools/selftest.sh
```

### 2.1 改动清单

| 类别 | 对象 | 改动 |
|---|---|---|
| 新增 | core-intake | §4 |
| 新增 | core-research | §5.1 |
| 新增 | core-diligence | §5.2 |
| 新增 | core-storyline | §5.3 |
| 新增 | out-report / out-chart / out-poster | §6 |
| 新增 | tools/lib、tools/bridge、tools/doctor.py、tools/vendor_sync.py、tools/selftest.sh、vendor/ | §3、§6、§9 |
| 改动 | core-evidence | SKILL.md：台账改为统一证据账（§3），核实关口改用 §3.4 的表（冲突处理规则不变）。`references/source-tiers.md` 改写为统一来源评价标准（§3.3）。`assets/evidence-ledger-template.md` 改为说明文档。与 core-research 的分工写入 SKILL.md |
| 改动 | core-synthesis | 取消一页及条数上限（§7）；输入改为 `03_evidence/`；引用写法改为 §3.6；"交付层（zerox）"改为"core-storyline 与输出层" |
| 改动 | core-review | SKILL.md：新增成品审查员（第 5 个角色）、深度对应的角色表。新增 `references/output-standard.md`（§8.3）。`references/reviewer-prompts.md`：新增成品审查员提示词；把 `03_evidence.md` 改为 `03_evidence/`；决策者视角（只在 L3 开）改读最终成品 report.pdf。`assets/review-log-template.md`：问题编号改为 `RV-0001`，增加成品审查员一节 |
| 改动 | router | SKILL.md：新的深度表（§7.2）；接入 core-intake 的先后顺序（§4.1）；任务文件夹树改为 §3.1。`assets/brief-template.md`：交付物选项改写；新增"用户要求（原文）"一节。`references/system-prompts.md`：路径和交付措辞随之改 |
| 改动 | scene-company、scene-topic、scene-bp-review、scene-personal | 接入 core-intake、新能力和输出层；路径 `03_evidence.md` → `03_evidence/`、`07_deliverables/` → `08_deliverables/`；引用 `[E-xxxx]` 等改为 §3.6；呈现措辞按 §7.1 |
| 改动 | lib-consulting、lib-management | 删除"一页正文""一页格式"措辞（§7.1） |
| 改动 | install.sh | 不再安装 zerox；新增 `--render-deps`，`--forge-deps` 保留为它的别名并提示已弃用；删除 `--no-zerox`；安装 `_allen-runtime`；`--remove-old` 同时清理 `zerox-*`（§9） |
| 改动 | tools/validate.py | 去掉对 zerox.lock 的依赖；新增 vendor 与 schema 检查（§11） |
| 改动 | tools/build-zips.py | 排除 out-*（依赖本机引擎）和 `_allen-runtime`；docstring 去掉 zerox |
| 改动 | .github/workflows/validate.yml | 去掉 `--no-zerox`；试装改为 `./install.sh --target …`（不带 `--render-deps`） |
| 改动 | README.md、INSTALL.md、ARCHITECTURE.md | 新结构、新安装方式、审查角色数、"一页"措辞、onepager 许可更正 |
| 删除 | zerox.lock | 由 `vendor/vendor.lock` 取代 |
| 不变 | core-framing、core-method-select、lib-personal、tests/method-selection-cases.md | 分析规则不改（D4） |

边界沿用 ARCHITECTURE.md 的三条：方法库不带流程；能力 skill 只管一件事、可以单独用；场景只编排、不重复规则。新增 skill 同样遵守。

## 3. 数据流与统一证据账

### 3.1 任务文件夹

```
work/<YYYY-MM-DD>-<主题短名>/
├── 00_brief.md              任务单；含"用户要求（原文）"一节
├── 01_issue-tree.md
├── 02_method-plan.md
├── 03_evidence/             统一证据账（§3.2）
│   ├── ledger/              各表 JSONL：唯一真源
│   │   ├── staging/<线>/    子代理暂存，主线程合并
│   │   └── .backup/         每次写入前的备份
│   ├── ledger.md            脚本生成的可读版，不手改
│   ├── raw/                 存入后只读
│   │   ├── sources/         来源快照 .md（元数据头 + 正文）
│   │   ├── files/           网络来源原件
│   │   └── user/            用户材料（core-intake 产物，§4）
│   ├── data/                extracted/、curated/、datasets.json、dictionary.csv、README.md
│   ├── analysis/            整理层数据的计算方法与脚本（数据记录的 method 指向这里）
│   ├── notes/               证据块可读版（由 ledger render 从 evidence 表生成，不手改）
│   └── search-logs/         检索日志可读版（由 ledger render 生成，不手改）
├── 03r_research/            core-research 工作文件：brief.md、plan.md、tasks/、report.md、qa/
├── 03d_diligence/           core-diligence 工作文件：project.json（project 表导出）、report-content.json、
│                            modules/、request-list.md、interview-outline.md、audit.md、calc/（计算底稿）
├── 04_analysis/
├── 05_review-log.md
├── 06_synthesis.md
├── 07_storyline/            00_story-brief.md、01_materials_index.md、02_info_cards.md（渲染版）、03_storyline.md、
│                            04_manuscript.md、04_manuscript_clean.md、05_storyboard.md、06_slides.md、
│                            slides.json、sidecar.json、07_audit_report.md
│   ├── forge-work/          report-forge 的任务目录（task.json、蓝图、pages.html、.forge/runs/…）
│   └── poster-work/         onepager 的项目目录（manifest、blueprint.json、onepager.ir.json、HTML 草稿）
└── 08_deliverables/         只放交付物：report/、charts/、poster/、speaker-notes.md/.pdf、
                             research-package/<包ID>/ 与 <包ID>.zip、diligence/、acceptance.json
```

L1 快答不建任务文件夹。L1 需要读用户文件时，见 §4.1；L1 用户要求留档时，见 §5.1 的轻量包。过程文件（引擎任务目录、海报项目）一律放在 07_storyline 下，08_deliverables 只放交付物。

### 3.2 统一证据账

上游三套账（deep-research 的快照 + sources.md + notes + 数据包；due-diligence 的 13 张 CSV 与 project-config；storyline 的信息卡片）合成一套，研究、尽调、故事线、输出层都读写同一份。

**原则**：

- **字段取并集**：表的字段以三份能力清单为准取并集。改名、合并或删除的字段，在 `tools/lib/schema/ledger.schema.json` 里逐条注明，并写明理由。下表只列每张表的作用和来源；完整字段以 schema 为准，schema 在实施第 2 步定稿。
- **唯一枚举源**：所有枚举的值只在 `ledger.schema.json` 里定义一次，中文显示名也在 schema 里给出。各 skill 文档（包括 source-tiers.md、core-evidence §6）只写含义和处理规则，引用 schema，不重抄枚举值；validate.py 检查文档里出现的枚举值都在 schema 中。引擎专用的枚举值（如 report-forge 的 provided、not_applicable）只出现在转换脚本的输出里，不进入证据账。
- **存储格式**：每张表一个 JSONL 文件，一行一条记录，支持追加。子代理只写 `staging/<线>/`，由主线程 `ledger merge` 合并。

| 表 | 记录什么 | 吸纳自 |
|---|---|---|
| project | 任务级配置与状态：目的、深度、基准日、历史时点标记、重大性、模块适用性及理由、事件、豁免、上市触发、网络与访问约束、三种完成状态、completion_review、completed_actions、评分开关、最近刷新时间 | due-diligence project-config；deep-research package.json 的 data_status / search_status 及理由 |
| sources | 来源。采集元数据：ID、标题、URL、final_url、访问时间、采集方式、完整度、原件路径与逐个哈希、语言、研究线、子问题、supersedes、archive_url、访问说明、权利说明。评价字段：tier、grade、grade_reason、利益冲突、发布日期（含精度）、修订日期、上游来源、同源组、真实性、授权、time_scope、内部标记、origin | deep-research 快照头 21 字段 + due-diligence source-register |
| evidence | 证据：来源 → 证据 → 主张的中间层。字段：所属来源、主体、尽调模块、定位、逐字摘录、解读（推断须标明）、属性（actual / forecast / estimate / opinion）、是否数值、数值、单位、币种、会计口径、范围、期间、地域、局限、贴合度 fit（high / medium / low：只描述这条摘录与原文和论断的贴合程度）、所属研究线、用于（报告引用位置）、交叉来源 | due-diligence evidence-ledger + deep-research notes 证据块（两者合并；notes/*.md 由它生成） |
| claims | 主张（§3.5） | report-forge claims + due-diligence claim-register |
| claim_evidence | 主张与证据的关联：supports / contradicts / context；bridge 说明（集团数据用于子公司时必填）、适用范围、局限 | due-diligence claim-evidence |
| metrics | 指标：数值或公式；状态（present / missing / approximate / not_applicable，非 present 时写原因）；关联数据记录（record_id / input_ids）；计算底稿位置 | report-forge metrics；due-diligence financial_ratios 的输出状态；连接 deep-research 的数据血缘 |
| cards | 故事线信息卡片（§5.3） | storyline |
| entities / relations | 主体，以及带生效区间的控制关系 | due-diligence entity-map / entity-relations |
| research_reports | 研报登记：获取状态与阅读状态、数据截止、预测期、估值日、关键观点、预测变化、supersedes、latest_*_for 反向指针 | due-diligence research-register |
| coverage | 研究覆盖项，以及三个"最新"指针（最新发现、最新全文、最新已读） | due-diligence research-coverage |
| conflicts | 冲突：双方值与口径、原因、采信理由、是否改变决策、决策影响、状态 | 三份清单合并 |
| gaps | 缺口：原因、重大性、优先级 P0–P2、路由（研究 / 用户 / 有界）、阻塞范围、获取路径、负责角色、状态、处置、影响的主张 | report-forge gaps + due-diligence gap-register |
| risks | 风险与红旗：性质、严重度、影响、可能性、时间范围、替代解释、缓解措施、残余风险、关闭条件、负责角色、证据 | due-diligence risk-register |
| scorecard | 评分（默认关闭）：权重、维度、关键维度、分数、置信度、依据 | due-diligence scorecard |
| search_log | 检索记录（同时渲染为 search-logs/*.md） | deep-research 检索日志 + due-diligence search-log |
| reviews | 人工复核记录：类型、复核人、时间、覆盖对象（主张 ID、页、文件）、结论、checks 子结构（每项 passed + evidence，用于导出研究包 review.json 的 4 项检查）、内容指纹。类型的完整清单（只在 schema 定义）：research_review（研究复核）、reading_recap（只读复述）、visual_review（视觉复核）、visual_review_disposition（visual_review 提示的处置）、view_preview（三视图预览）、deliverable_review（成品审查）、user_confirmation（用户确认）、diligence_manual（尽调 22 条人工清单） | deep-research review.json + due-diligence 人工复核（上游没有结构化回填，本设计补上） |

数据表沿用 deep-research 的 CSV 两层结构（提取层 / 整理层，带完整血缘），放在 `03_evidence/data/`。它是数值记录的真源；metrics 通过 record_id 引用其中的记录。

**两处真源的划分**：

- 来源的**采集元数据**以快照头为真源：采集时写入，之后不可改。sources.jsonl 的同名字段由脚本从快照头同步，`ledger check` 检查两者一致。
- 来源的**评价字段**以 sources.jsonl 为真源：快照里不存。
- 卡片以 cards.jsonl 为真源；`07_storyline/02_info_cards.md` 是 `ledger render` 生成的可读版，不手改。
- 证据（逐字摘录）以 evidence.jsonl 为真源；`03_evidence/notes/*.md` 是生成的可读版。
- 检索记录以 search_log.jsonl 为真源；`03_evidence/search-logs/*.md` 是生成的可读版。
- 研究包里的 sources.md、notes、完整快照头，由 `research seal` 在包副本里从证据账生成（§5.1）。

**ID 规则**：

| 对象 | 格式 | 说明 |
|---|---|---|
| 来源 | `[A-Z]\d{3,4}`（先用 3 位，用尽后用 4 位；上游只允许 3 位，这是对上游的放宽） | U = 用户材料；M = 主线程；A、B…（不含 C、U、M）= 研究线。"单个大写字母 + 数字"只给来源用 |
| 证据 | `ev-0001` | |
| 主张 | `cl-0001` | 小写 kebab，可直接用作 report-forge 的主张 ID |
| 指标 | `m-0001` | |
| 卡片 | `card-0001` | |
| 数据记录 | `<线>-R0001` | |
| 主体 / 关系 | `ENT-0001` / `REL-0001` | |
| 研报 | `RR-0001` | |
| 冲突 / 缺口 / 风险 | `X-0001` / `G-0001` / `R-0001` | |
| 审查问题 | `RV-0001` | 05_review-log 里用 |

ID 一经分配不复用、不重编号；采集失败留下的空号不补。

**读写模块** `tools/lib/ledger.py`（只用 Python 标准库）：

- 事务式写入：先写临时文件再原子替换，写入前备份；支持只改指定字段（patch），省略的字段不会被清空。
- `ledger merge`：合并 staging、去重（同 URL 且内容一致或哈希相同 → 只留一个规范 ID）、校验。
- `ledger check`：引用完整性；枚举合法；ID 唯一；血缘无环；缺失不为 0；快照头与 sources 一致；coverage 与 research_reports 的指针双向一致；控制图无环、无自我控制；以及 §5 各节列出的语义校验。
- `ledger render`：生成 ledger.md、02_info_cards.md、search-logs/*.md。
- `ledger export --forge | --thinkcell | --onepager`：供转换脚本调用（§6.3）。

### 3.3 统一来源评价（规则真源：`core-evidence/references/source-tiers.md`；枚举值真源：schema）

等级、访问程度、核实状态、置信度是四件不同的事，各用一个字段：

| 字段 | 枚举 | 说明 |
|---|---|---|
| `tier` | primary / secondary / tertiary | 事实从哪来（按事实，不按载体） |
| `grade` | S / A / B / C / D | S=官方登记、监管和司法文件、法定披露、经核验的审计文件；A=方法透明可复核的调查统计，或附数据和方法的分析；B=券商研究、商业数据库、主流媒体深度报道；C=企业宣传、管理层自述、一般报道、访谈；D=匿名或无法追溯。现有 A/B/C 的对应：旧 A → S 或 A，旧 B → B，旧 C → C 或 D。deep-research 的 A/B/C 评级同此映射 |
| `access`（来源的完整度） | full / partial / summary / snippet_only / metadata_only / blocked / unreadable | 合并 deep-research 的 5 级完整度与 due-diligence 的 access。统一使用下划线 |
| `origin` | user / web / model_memory / derived | 出处 |

规则：关键结论所依赖的主张必须达到 verified（判定标准见 §3.4，§3.4 是这条规则唯一的展开）。C、D 级只当线索。access 不是 full 或 partial 的来源，不能单独支撑关键结论。

### 3.4 核实关口（规则真源：core-evidence §6，以本表替换原表；枚举值真源：schema）

主张的 `verification` 枚举：verified / single_source / conflicting / unverified / refuted。判定标准：

下文"合格来源"指 grade∈{S, A, B} 且 access∈{full, partial} 的来源（§3.3：C、D 级只当线索，低完整度的来源不能单独支撑结论）。

- **verified**：≥2 个相互独立的合格来源支持；或 1 个 tier=primary、grade∈{S, A}、access∈{full, partial} 的来源支持；或者是用户材料主张并经用户确认（见下）。
- **single_source**：只有 1 个合格来源支持，且不满足 verified。
- **conflicting**：有相互矛盾的证据（conflicts 表有对应记录）。
- **unverified**：没有合格来源支持，包括只有模型记忆（origin=model_memory 的来源）或只有 C、D 级来源的主张。
- **refuted**：有 contradicts 证据，且这些反证本身满足 verified 的来源要求。

"用户材料主张"指：一条主张的全部 supports 证据都来自 origin=user 的来源。

`affects_conclusion=true` 的主张在综合前逐条过关：

| 状态 | 处理 |
|---|---|
| verified | 正常使用 |
| single_source | 可以用，正文注明来源，措辞留余地 |
| conflicting | 正文并列写出，说明采用哪个（即 conflicts 表的这一条已写采信理由）。没写采信理由的按 unverified 处理 |
| unverified | 结论改写为"如果……则……"，并列入"需要先确认的问题" |
| refuted | 不得作为支撑；只能作为"被推翻的说法"出现 |

用户材料主张初始为 unverified。用户材料本身就是权威出处的主张（例如用户自己的内部经营数据），由用户确认后改为 verified，并在 reviews 表写一条 `type=user_confirmation`（谁、何时、覆盖了哪些主张）；成品中标"用户提供"。BP 等第三方材料里的说法不适用这一条，必须按上面的标准核实。due-diligence 的 pending / verified / disputed / unsupported / refuted 依次映射为 unverified / verified / conflicting / unverified / refuted。

### 3.5 主张身份（真源：claims.kind）

| kind | 含义 | 上游映射 |
|---|---|---|
| fact | 有资料支持的事件或状态 | DD【事实】；core-evidence 事实；storyline 性质"事实" |
| data | 可量化的实际数据，带口径、期间、单位 | DD【数据】 |
| estimate | 基于证据和明确假设的估算或推理 | DD【推断】（非预测）；core-evidence 估计；storyline"推断" |
| forecast | 对未来的预测 | DD【推断】中的预测 |
| assumption | 假设 | core-evidence 假设；storyline"假设" |
| judgment | 我们作出的评价 | DD【判断】 |
| recommendation | 建议 | core-evidence 判断与建议中的建议 |
| third_party_view | 机构或个人的评价、预测、评级、指引 | DD【第三方观点】；storyline"观点" |

DD 的【待核实】不是身份，用 `verification=unverified` 表示。【缺口】不是主张，记入 gaps 表。storyline 卡片的 12 种"类型"是卡片属性，不映射到 kind。

主张的其余字段：statement、entity、scope、period、population、unit、denominator、calculation、inference、limitation（不适用时写原因，不留空）、metric_refs、verification、confidence（high / medium / low / unknown，附理由）、assumptions、counterevidence、unresolved、affects_conclusion、materiality（critical / major / minor）、module（尽调模块编号）、as_of。

**跨层约束**（由 `ledger check` 执行）：

- 证据属性与主张身份要匹配：kind=data 的主张，supports 证据的 attribute 必须是 actual；kind=forecast 对应 forecast；kind=third_party_view 对应 opinion；kind=estimate 可以引用 actual 或 estimate。由实际数据算出的比率可以是 data，但必须通过 metrics 的公式指向输入。
- 置信度只有一个：关口、卡片、成品一律用 claims.confidence；evidence.fit 只描述单条摘录的贴合度，不参与判断。
- materiality=critical 或 major 的主张，affects_conclusion 必须为 true。
- 与 A 级卡片关联的主张，affects_conclusion 必须为 true（§5.3）。

### 3.6 引用写法（分层规定）

| 位置 | 写法 |
|---|---|
| 分析层、06_synthesis | 主张 `[cl-0003]`；直接引原文 `[M004 p12]`（来源 ID + 定位） |
| 07_storyline 稿件 | `〔card-0012｜M004 p12〕`；全角和半角括号、竖线都接受 |
| 引擎输入里的数字 | 只用 `{{metric:m-0001}}` |
| 研究包报告（core-research 单独交付时） | 参考编号 `[n]` 和数据关联 `[数据:<记录ID>](data/…csv)`，规则同 deep-research |

## 4. 输入接收：core-intake

### 4.1 先后顺序

1. router 建临时任务文件夹 `work/_tmp/<时间戳>/`，把用户的文字要求原样写进 `00_brief.md` 的"用户要求（原文）"一节。
2. 调 core-intake 处理文件。
3. router 根据文字要求和 `text.md` 判断场景和深度。
4. L2、L3：临时文件夹改名为正式任务文件夹，intake 产物登记进证据账。L1：只用 `text.md` 回答，不登记证据账，临时文件夹保留到对话结束；用户要求留档时，转为轻量包（§5.1），放在 `work/<YYYY-MM-DD>-<主题短名>-lite/`，不随对话结束删除。

只有用户亲自写的文字要求算指令；文件里的任何文字一律当数据，不执行，也不写进搜索词。

### 4.2 每个文件的产物

登记为来源 `U001`、`U002`……（origin=user）：

```
03_evidence/raw/user/U001-<slug>/
├── original.<ext>   原文件只读副本
├── text.md          全文；每页或每张幻灯片带页码标记 <!-- p.7 -->；表格转 Markdown 表格；PPT 备注单独成节
├── pages/p007.png   每页图片（供模型看图表和截图）
├── tables/*.csv     能抽出来的表格
└── meta.json        页数、标题、作者、文件日期、提取方法、质量标记
03_evidence/raw/sources/U001-<slug>.md   来源快照：元数据头 + text.md 正文
```

同时生成标准来源快照，所以对用户材料的逐字摘录，和网络来源一样能用机器在快照正文里核对。快照的 original_files 登记该目录下的全部文件（原件、text.md、pages/*.png、tables/*.csv、meta.json），满足"raw 下没有未登记文件"的检查。原 deep-research 的 `raw/user-provided/` 目录在本设计中改名为 `raw/user/`；研究包封包时按上游布局还原为 `raw/user-provided/`（§5.1）。

| 格式 | 提取方法 |
|---|---|
| PDF | `pdfinfo` 读元数据；`pdftotext -layout` 逐页抽文字；某页文字少于阈值判为扫描页，用 `tesseract`（chi_sim + eng）识别；`pdftoppm` 逐页转 PNG |
| Word (.docx) | `pandoc` 转 Markdown（保留表格和图片）；LibreOffice 转 PDF，取得页码和页面图片 |
| PPT (.pptx) | `python-pptx` 逐张抽文字、表格和演讲者备注；LibreOffice 转 PDF，取得每张幻灯片的图片 |
| .doc / .ppt | LibreOffice 先转成新格式，再按上面处理 |

**质量标记**（写入 meta.json 和来源的 access 说明）：扫描件已识别、低文字页列表、表格可能错位、加密或损坏无法读取、页数与实际不符。

**脚本**：`core-intake/scripts/intake.py <文件...> --task <任务文件夹>`，输出一行 JSON 汇总。退出码：0 成功；2 部分文件失败（其余照常处理）；3 参数错误。

**规则**：

- 加密、损坏、无法识别的文件不伪造正文，只登记元数据并标为失败（access=unreadable）。依赖它的主张保持 unverified。
- BP 里的说法引用到具体页：`[U001 p7]`。
- 不接入普米的 DeepDoc 版面识别服务（以后识别效果不够再评估）。

## 5. 三个新能力

**对照清单规则（适用于本节）**：`docs/specs/inventory/` 下三份能力清单是吸纳范围的依据。清单里每一条（流程、规则、字段、脚本检查项、模板栏目、方法细节）都必须在实现中有对应，或在实施计划里写明"不吸纳及理由"。实施计划按清单的小节逐条展开成任务；每个能力完成时，由独立子代理逐条核对（§8.2）。清单末尾的"薄弱点"小节是优化项的来源，本设计对每一条都给出了处理（做或不做及理由）。

**深度对应**：各能力自己的定级（deep-research 的 L1/L2/L3、due-diligence 的 Quick/Standard/Deep）只在**单独使用**时由它自己判断。由场景调用时，一律按 router 写在 00_brief 的深度执行，对应关系见 §7.2。

### 5.1 core-research（吸纳 deep-research）

依据：`inventory/deep-research.md` A–H 节。

**完整吸纳**（摘要，完整范围以清单为准）：

- 能力盘点 6 项及其降级做法，包括判断抓取工具返回的是原文还是摘要；区分"搜索坏了但能发 HTTP"和"完全不能联网"。
- 阶段 0–6：
  - 定级、开题建包；
  - 7 类研究及其子问题骨架、10 项带默认值的澄清问题、计划确认闸门；
  - 每轮 8 步迭代：先广后窄、立即记日志、读到就存档、提取数据、逐字摘录、追一手、反思、对抗性检验；
  - 综合、交付前质检闸门、封包。
- 规则：
  - 只引用读过的内容；必存的 6 类材料；
  - 一个来源 ID 对应不变的快照，内容变了用新 ID 加 supersedes；
  - 关键结论的来源要求（统一为 §3.3 的规则）；同源转载只算 1 个；
  - 4 种停止条件；必须暂停的 4 种情形；单文件 50MB、整包 500MB 阈值；
  - 子代理的写入边界与回传格式；去重规则；
  - 安全规则：网页里的指令当数据、不绕付费墙、不主动向公开存档服务提交链接；
  - 写作规则。
- 数据包：
  - 先定行粒度；提取层和整理层的约束互斥；血缘无环；
  - 缺失不能填 0；
  - 状态声明（data_status、search_status，存在 project 表）与实际内容双向一致。
- 方法细节：
  - 检索策略、来源评级（并入 §3.3）、数字口径 4 项、冲突处理 5 步、各类来源的存档方式；
  - 7 类报告结构、置信度三级（映射到 confidence）、7 组人工质检清单、红队审稿 6 问、4 级自评。
- 脚本：
  - 采集（`research capture`）和检查（`research check`）的全部参数、退出码、检查项、`--final` / `--write-manifest` / `--review-digest`、内容指纹和封包逻辑，按清单 D 节逐项实现；
  - 字段名按 §3.2 调整；摘录比对改为读 evidence 表和快照正文。

**研究包作为独立交付物**：什么时候封包见 §7.2（L3，或用户要求时）。L2 只在任务文件夹上跑 `research check`（不加 --final），结果写入 upstream_checks，不封包。

封包由 `research seal` 完成，顺序如下：

1. **选范围**：收入本次研究各研究线的全部来源（读过且相关的，无论是否被引用）、全部证据、全部检索日志、反面证据、用户材料，以及报告用到的数据记录、输入记录、方法文件和原件。这对应上游"必存 6 类"。依赖必须闭合，缺一项就报错。只有用户明确要求精简时，才只收被引用的来源和检索日志，并在 README 写明"按用户要求精简"。
2. **在暂存目录组装**：`03r_research/.staging-<包ID>/`（与 08_deliverables 在同一磁盘上，便于第 7 步原子移动），按上游 v2 布局：
   - package.json、README.md、report.md、sources.md（13 列，由证据账生成）；
   - raw/sources/（快照：在副本里把评价字段补进快照头，凑齐上游要求的 20 个必填字段；任务文件夹里的原快照不动）、raw/files/、raw/user-provided/；
   - data/（数据记录的 method 路径从 `03_evidence/analysis/` 重写为包内的 `analysis/`）、analysis/；
   - notes/（由 evidence 表生成证据块）、work/（brief、plan、tasks、search-logs）、qa/。
3. **自动检查**：`research check <暂存目录>`，零错误才继续。
4. **人工复核**：复核人在暂存目录的副本上实际复核，结果写入 reviews 表，再导出为 `qa/review.json`。导出时用 `--review-digest` 计算当前副本的内容指纹，写入 reviewed_digest。
5. **写清单**：`research check --write-manifest`，生成 README 统计区、qa/checks.json、manifest-sha256.txt。
6. **最终验证**：`research check --final`。
7. **发布**：暂存目录原子移动为 `08_deliverables/research-package/<包ID>/`，再在包外生成 `<包ID>.zip`。

`research check` 接受两种输入：任务文件夹（读证据账，用于 L2 和封包前的检查），以及研究包（读上游 v2 布局，用于第 3、6 步）。两种输入执行同一套检查规则。

- 任何一步失败都不发布，暂存目录保留供诊断，已发布的包不受影响。
- 封包后的副本不可改。要修订就新建 `<包ID>-r2`，package.json 写 supersedes。
- 内容指纹的排除清单和上游一致：README.md、qa/review.json、qa/checks.json、manifest-sha256.txt。
- `--final` 的结果写入 acceptance.json 的 upstream_checks（§8.3）。

**轻量包**：L1 且用户要求留档时，在 `work/<YYYY-MM-DD>-<主题短名>-lite/` 建只含 `raw/` 和 `answer.md` 的轻量包，用 `research check --profile lite` 检查。

**优化**（对应清单 H 节）：

1. 付费墙和验证码识别：综合 HTTP 状态、正文长度、标记密度判断，只嗅探一次，减少误判。确认是付费墙、登录或验证码时，仍按上游规则停止，记为 metadata_only。
2. 读取 HTML 的 meta charset 和 HTTP 头里的编码，支持 GBK 等中文编码；记录响应头和 Content-Type；自动抽取标题、作者、发布日期作为候选值。
3. 每个原件单独记录哈希（上游只校验第一个）。
4. 来源索引由脚本从快照头和 sources.jsonl 生成，不再按列号手工维护。
5. 正文引用解析支持 `[1-3]`、`[1,3]`，排除行内代码和年份类方括号。
6. 加重试和退避；可按配置遵守 robots.txt。抓取失败或需要执行 JS 时，通过用户本机 9222 端口浏览器打开原页存档，capture_method=browser。规则同 D7。
7. 新增 `--profile lite` 和 `init / resume / revise` 子命令；ZIP 由 `seal` 生成。legacy（v1）包只读诊断，不迁移；本仓库从未产生过 legacy 包，所以不做迁移工具。
8. 弱检查（以警告输出）：
   - 关键结论的来源数，以及有没有 tier=primary、grade∈{S, A} 的来源；
   - 检索日志的时间格式、工具名、弃用原因；
   - "打开并存档"列出的 ID 确实有快照；
   - 体积阈值由脚本检查。
9. 补齐清单列出的全部未测试分支；抓取类测试用本地 HTTP 服务，不依赖外网。
10. 字段契约统一到 `ledger.schema.json`，消除清单 H.2 列出的不一致（必填字段、枚举写法、退出码）。

**与 core-evidence 的分工**：core-evidence 核实一条或几条说法；core-research 做开放问题的研究包。两者写同一个证据账。

### 5.2 core-diligence（吸纳 due-diligence）

依据：`inventory/due-diligence.md` A–L 节。

**完整吸纳**（摘要）：

- 范围输入：target、purpose（company_research 和 6 类专项）、depth、geography、focus、materials、as_of_date、constraints，以及澄清规则。存入 project 表；`03d_diligence/project.json` 是它的可读导出。
- 10 个阶段（Phase 0–9）。三种完成状态（research_gate、report_status、declared_complete）相互独立，加上 completion_review。
- 硬规则：
  - 主体、期间、口径（集团数据用于子公司时，必须写 bridge 并标为推断，由 `ledger check` 校验）；截止日隔离；
  - 控制关系：类型、状态、生效区间左闭右开、环检测；
  - 证据身份（并入 §3.5）；单源确认与独立印证；来源等级（并入 §3.3）；置信度不用公式算；
  - 冲突处理；假设检验与反证（被推翻的保留原声明，标 refuted）；抽样；
  - 红旗分级与停止条件；合规与保密。
- 18 个模块的全部检查项；模块 18 的上市公司研报流程（必读类别、三个"最新"指针、同日多份必须全读、只有 official_interim 可豁免）；7 种目的手册；8 类行业适配。
- 来源清单（中国大陆、港澳、海外）；研报获取方法；访谈方法；资料请求清单；访谈提纲。
- 财务比率计算；评分框架（默认关闭，门槛严格）；检索计划生成。
- **报告内容契约**：
  - 11 个解释主题及其状态；13 种内容块及跨块规则；公司时间线；人物章；
  - 业务模式图（basis 四档、sequence / conceptual）；
  - 真实图片规则（来源、取得日期、权利、大小限制）；
  - 各图型的真实性约束：瀑布图闭合、区间不画中点、比例量尺、预测用虚线、null 不画成 0；
  - visual_review 提示规则；"只读正文能否复述"的 11 问验收；22 条人工清单。
- 交付物：主报告、底稿 audit.md（Quick 10 节、完整版 20 节）、台账导出、计算底稿、资料请求清单、访谈提纲、补齐路径、更新触发条件。

**报告怎么出（改动）**：上游的 HTML 渲染器不再单独维护，尽调报告和其他报告走**同一条链路**：内容稿 → core-storyline 拆页 → out-report 渲染。上游的内容契约不丢，做法是：

1. **写内容**：core-diligence 仍按上游契约产出 `03d_diligence/report-content.json`。`diligence check-content` 执行上游 report_model 的全部校验：11 主题覆盖与状态、13 种内容块及跨块规则、图型真实性、图片规则、业务图规则。
2. **转成母版**：`tools/bridge/diligence_to_manuscript.py` 把通过校验的内容机械转成故事线的输入，不改写结论：
   - `04_manuscript.md`（母版）和 `04_manuscript_clean.md`（清洁版）；
   - `00_story-brief.md`（取自 project 表的目的、受众、基准日）；`01_materials_index.md`（取自 sources）；
   - `03_storyline.md`：只写结构树，按 11 个解释主题组织，并按目的选择故事线模式（见下）；
   - 卡片：为每条事实、数据、观点、风险生成卡片，关联已有主张。
     - 只引用了证据、还没有主张的内容块，先补登主张（kind 按证据属性定）再生成卡片。
     - value_tier 按主张的 materiality 定：critical、major → A；minor → B；只作背景的内容 → C。
     - "含义"取主张的 inference；inference 为空时取该主题 explanation 正文的首句。
   - 块到页的追溯表 `block_map.json`：记录 report-content 的每个内容块 ID 和主题。
3. **拆页**：core-storyline 以"仅拆页"模式（上游已有这种模式）从阶段 5 开始，产出带完整引擎字段的 slides.json，并做阶段 6 审计。上游"仅拆页"要求先诊断结构、给重构建议；在这里诊断只记录，不改结论。
   - `storyline check --mode split-only` 适用：00、01、03 文件由转换生成，所以照常检查存在性。storyline check、A 级卡片检查对尽调报告同样有效。proves、adds、density 这些需要判断的字段，由故事线阶段写出，不靠转换脚本硬凑。
   - **拆页后的契约复核**：拆页可能合并、重排页面，或把内容移进备用页和附录。所以 `diligence check-content --after-split` 用 block_map.json 和 slides.json 重新核对：
     - 每个内容块都落到了页上；11 个主题仍各至少出现一次；
     - 公司时间线仍与 identity 同章，且至少 2 个事件；人物卡不与 identity 同章；
     - 其余跨块规则全部在拆页结果上重跑。

   **故事线模式按目的选择**：
   - purpose=company_research：结构按上游推荐的阅读顺序（身份与沿革 → 创始人与团队 → 产品与客户 → 营收与盈利 → 营销 → 竞争 → 风险与未知），用"行业研究"式的论证，arc=evidence-to-view，不做投资判断（上游规定公司研究不评分、不下投资结论）。
   - 专项目的（investment、acquisition、partnership、credit、supplier、competitor）：用"尽调结论"模式，arc=uncertainty-to-bet。
4. **渲染**：out-report。各内容块的呈现方式：

   | 上游内容块 | visual.form | layout | semanticType |
   |---|---|---|---|
   | timeline | `svg.custom` | custom | flow（有数量时 trend） |
   | people（人物卡） | `html.text`（需要图形时 `svg.custom`） | custom | qualitative |
   | process（含 business_model 用途） | `diagram.process` 或 `kit.processFlow`；sequence 带箭头和编号，conceptual 不带 | 目录布局或 custom | flow |
   | diagram（业务模式图、关系图） | 优先 `diagram.mechanism`；不够用时 `svg.custom` | 目录布局或 custom | flow 或 network |
   | image（真实图片） | `html.text` 内嵌 data: URI，保留来源、取得日期、权利说明和图注 | 目录布局或 custom | qualitative |
   | chart、metrics、table、matrix | report-forge 对应的形式；每张图附可查看的原始数据表（附录页，`html.table`） | 目录布局 | 按图型 |
   | text、bullets、callout、explanation | 正文页组件 | 目录布局 | — |

   上游规定 process 和 diagram 都可以满足"必须有业务模式图"。

5. **渲染后的图型规则**：上游渲染器原来自动保证的规则，现在由模型手写 SVG 实现，所以必须在成品上核对。下面是完整清单，写进 output-standard.md 的尽调专项（§8.3）：
   1. 每张图有元信息行：单位、期间、主体、属性（实际 / 预测 / 估算）。
   2. 数值轴有零基线；截轴必须注明。
   3. null 显示为"未披露"，不画成 0。
   4. 预测用虚线或空心点，与实际区分。
   5. 区间只画上下界，不画中点。
   6. 比例图的灰色轨道注明"只是量尺"，不暗示互补类别。
   7. 堆叠图各期分类一致、不缺类；堆叠图和瀑布图带免责说明；瀑布图首尾闭合。
   8. 业务图、关系图里，推断或未知的节点和边用虚线；资金流按颜色区分并配图例；注明"线宽不表示数量"。
   9. conceptual 流程注明"排列不表示已核实的顺序"；关系图注明"布局不表示层级或顺序"。
   10. 关系图配关系清单和编号徽章。
   11. 矩阵逐格写依据，不用空白、问号或颜色暗示优劣。
   12. 每张图可以展开查看原始数据表。
   13. 证据附录只列正文用到的证据。

   能从蓝图机械判断的（例如引用了 forecast 指标的图，visual 里必须声明预测样式），由转换前检查执行；只能看图判断的，由成品审查员逐项核对。
6. **视图上的取舍**：上游有桌面、移动、打印三种视图；report-forge 是 16:9 阅读版式加 PDF，没有移动端视图。本设计接受这一点：交付桌面 HTML 和 PDF，不做移动版。用户已确认。
7. **人工清单**：上游 check_report 的 22 条人工复核清单由作者在出报告前逐条执行，结果写入 reviews 表（`type=diligence_manual`），`diligence check-content --final` 检查 22 条都有记录。11 问"只读正文复述"由成品审查员在最终成品上执行（§8.3）。

**目的的选择**：

| 场景 | 是否调 core-diligence | purpose |
|---|---|---|
| scene-company：经营诊断、战略方向 | 不调，用 core-evidence 做轻量画像 | — |
| scene-company：用户要求深入了解这家公司 | 调 | company_research |
| scene-company：合作 / 投资或并购 / 供应商准入 / 授信 / 竞品研究 | 调 | partnership / investment 或 acquisition / supplier / credit / competitor |
| scene-bp-review：投资人角度 | 需要了解公司时调 | investment |
| scene-bp-review：合作方角度 | 需要了解公司时调 | partnership |
| scene-bp-review：创始人自查、评审机构 | 需要了解公司时调 | company_research |

评分只在用户要求比较时开启（scorecard 表，scoring_override 由用户确认）。

**优化**（对应清单 L 节）：

1. 补齐测试，测试是一等交付物。
2. 共同控制（joint_control）是否触发上市追溯改为可配置，默认给警告。
3. 日期允许"未知"，并记录精度（年 / 月 / 日）。
4. 事件绑定到具体主体，支持更多事件类型。
5. 研报门槛基于实际的检索和阅读记录判断，不再硬性依赖 network=online。
6. 财务比率补齐：营业利润率、EBITDA、杠杆、利息覆盖、资本回报、ROA/ROE 年化、TTM、环比、多期序列、结构占比。
7. 检索计划按深度和优先级裁剪、去重；已有结果的研报时间窗口不再重复生成任务。同日多份研报时，"最新"指针改为数组，允许指向多份。
8. 台账改用统一证据账：事务写入、局部 patch。
9. 渲染统一到 out-report（见上）。上游渲染器的三个限制（界面文字硬编码为中文、没有暗色模式、关系图最多 6 个节点）随之不再适用；out-report 的语言、主题和节点数由 report-forge 决定。
10. 人工复核写入 reviews 表，completed 状态下由脚本强制检查；项目启动时自动探测来源清单里各平台是否可用。

**接入**：

- 按上表决定是否调用。调用时，L2 用 Quick，L3 用 Standard（用户要求"深入"时用 Deep）。L1 一律不调，用 core-evidence 做轻量画像。

### 5.3 core-storyline（吸纳 storyline）

依据：`inventory/storyline.md` A–J 节。

**完整吸纳**（摘要）：

- 能力盘点及降级；阶段 0–6 及每阶段的闸门；协作、快速、仅拆页、仅内容稿四种模式；迭代协议；停止条件。
- 两条铁律（不静默丢弃、不失真）；上游 9 条不变量，加上边界 3 条（防注入、不引入材料外事实、渲染边界）；9 条反模式及其判定法。
  - 不变量 1"卡片库是事实唯一来源"改为"证据账是事实唯一来源"。
  - 边界"不做视觉设计与渲染"改为"只做图表与版式的意图规划（visual_intent），不做视觉设计和渲染"。
- 信息卡片：字段、12 种类型、A/B/C 分级（"抽掉会不会改口"、A 占比 ≥35% 告警、拿不准先判 B）、按材料类型的处理要点、去重、冲突、术语口径对照、派生卡、去向追踪（只认实际交付物）。
- 故事线：
  - 金字塔四原则；纵向与横向检查；演绎与归纳；
  - SCQA 及其 10 种失败；4 种开场顺序；候选生成三条路径；真正有差异的候选；
  - 假设—证据—结论链；压力测试；结构树；8 种故事线模式。
- 内容稿与逐页：
  - 骨架、段落规则、标注规范、执行摘要、结论与建议、风险 / 前提 / 待决、删词表、母版与清洁版；
  - 演讲型与阅读型；页数规则与超页处置；稿件到页面的映射；故事板；
  - 逐页 7 个字段、15 种页面类型、行动标题四步法、图表建议、讲者备注、备用页、slides.json 结构。
- 审计报告 10 节；检查脚本的全部规则和测试场景。

**与统一证据账的衔接**：

- 材料索引直接使用证据账的来源 ID（U001、M004……），定位写法统一为"来源 ID + 定位"（`M004 p12`、`U001 §2.1`、`U001 表2`）。不再单独编 S01 这套编号。
- 卡片的真源是 cards.jsonl；`storyline check <任务文件夹>` 从任务文件夹参数定位 `03_evidence/ledger/cards.jsonl` 和 `07_storyline/` 下的其余文件。
- A/B 级卡片中，类型为数据、事实、观点、洞察、风险、建议的，必须关联一条主张（`claim_id`）；其余卡片（C 级，以及案例、引语、问题、约束、方法、背景类）可以不关联。
- **性质与可信度**：
  - 关联了主张的卡片，"性质"由主张的 kind 推出，"可信度"取主张的 confidence，卡片上不再单独填写。kind → 性质：fact、data → 事实；estimate、forecast、judgment、recommendation → 推断；third_party_view → 观点；assumption → 假设。
  - 没关联主张的卡片，仍自带"性质"和"可信度"两个字段，规则同上游（缺失时警告）。
  - 上游依赖"性质"的规则（推断、建议、目标类数字可以不在材料里，但必须带标记）照常适用。
- **派生卡**：派生卡对应一条 kind=estimate 的主张。calculation 写算式；metrics 用公式指向输入指标；输入卡对应的主张写进 assumptions。可信度取"输入主张中最低者"和"推算精度"中更低的一个，写入该主张的 confidence 并说明理由。
- 卡片的"价值"字段改名为 `value_tier`（A/B/C），避免和来源 grade 混淆。value_tier=A 的卡片，所关联主张的 affects_conclusion 必须为 true（§3.5），否则 ledger check 报错。

**研究类型、故事线模式、arc、必备章节对照**：

| 研究类型 / 场景 | 故事线模式 | deck.arc | 必备章节（在内容稿骨架之外） |
|---|---|---|---|
| 经营诊断 | 问题诊断→方案 | problem-to-fix | 方法与局限 |
| 方案比选、选型对比 | 方案比选 | opportunity-to-choice | 维持现状方案；方法与局限 |
| 请求批准 | 请求批准 | opportunity-to-choice | 不批的后果 |
| 机会论证、市场进入 | 机会论证 | opportunity-to-choice | 止损线 |
| 行业全景 | 行业研究 | evidence-to-view | 分歧与不确定性；未解问题；方法与局限 |
| 技术深潜 | 行业研究（按"机制→证据→边界"排支撑点） | evidence-to-view | 同上 |
| 文献综述 | 行业研究（按"共识→争议→空白"排支撑点） | evidence-to-view | 同上 |
| 政策法规 | 行业研究（按"条文→生效→影响→待确认"排支撑点） | evidence-to-view | 需向专业人士确认的问题 |
| 事实核查 | 行业研究（按"评级→证据链→口径"排支撑点） | evidence-to-view | 什么证据会改变评级 |
| 公司研究（core-diligence，purpose=company_research，§5.2） | 行业研究式论证，章节按上游阅读顺序 | evidence-to-view | 风险与未知；补齐路径；不做投资判断 |
| 尽调结论（core-diligence 专项目的）、BP 评审 | 尽调结论 | uncertainty-to-bet | 风险与红旗；补齐路径 |
| 进展汇报 | 进展汇报 | other（arcReason 必填） | 请求 |
| 复盘 | 复盘 | other（arcReason 必填） | 要改的机制 |

内容稿骨架新增"方法与局限"一节（所有类型都有），研究类再加"分歧与不确定性""未解问题"。

**优化**（对应清单 J 节）：

1. C 级卡片出现在 `07_storyline/04_manuscript.md` 或 `07_storyline/06_slides.md` 时报错。
2. 数字检查：
   - 支持负号，能检测符号翻转；
   - 万 / 亿换算只在原文带量级单位时才尝试；
   - 补 ‰、bp、元/平方米及英文单位；
   - 区间（如 1200–1500）不被误判为日期；
   - 带引用的句子里，小于 4 位的整数也检查。
3. 判断类标记必须紧挨着所修饰的数字并写明依据，才把错误降为警告。
4. "含义"字段里的数字不进入事实库。
5. 安置只认 `04_manuscript.md` 正文，以及 `06_slides.md` 的正文、图表和备注；故事板和来源字段不算安置。此外，验收脚本在成品上再查一遍：A 级卡片关联的主张，要在最终成品里出现（§8.3）。
6. 文档里的规则全部机器化：
   - 摘要 200–400 字；标题 ≤30 字；结尾页类型；备用页 ≥3；
   - 页数 ≤ 简报里写的上限（没写就不查）；
   - 材料没有"未处理"；长文档有"读至"标注；冲突表存在；
   - A/B 卡缺"含义"由警告升为错误；派生卡格式；ID 跳号；
   - slides.json 符合 schema，并与 06_slides.md 一致。

   注：这些是写作质量规则，不是呈现上限；页数上限只来自用户的要求，默认不设。
7. 清洁版由脚本机械生成（删除追溯标注）后逐字比对；推断标注和【待补充】必须保留。
8. 卡片带结构化字段（period、population、unit、denominator、limitation、metric_refs），导出报告引擎格式时直接取用，不靠模型转写。
9. 解析更稳：
   - 卡片块不会被 `##` 截断；字段名不限长度；
   - 卡片 ID 改为 `card-NNNN`，不再与型号类文本混淆；
   - md 与 jsonl 同时存在时检查一致。
10. 流程补强：
    - 阶段性检查命令（`storyline check --stage 2` 等）；
    - 变更影响分析：改了哪张卡 → 影响哪些段落和页；
    - 确认点的状态可由机器读取；
    - 讲者备注和备用页写入 `sidecar.json`，并有交付形态（§6.2）；
    - 引用同时接受全角和半角写法。

**slides.json 扩展**（schema 在实施第 2 步定稿，放在 `tools/lib/schema/slides.schema.json`；第 4、5 步都以它为准）：在上游结构基础上，每页增加报告引擎需要的字段：

- `page_role`、`story_beat`、`proves`、`adds`；
- `claim_refs`、`metric_refs`；
- `density`：profile、evidence_units、space_intent；
- `visual_intent`：关系、首选图型、备选及取舍、阅读路径、复用理由；
- `chart_spec`：交给 out-chart 时的数据和图型。

页面类型补齐 risk 和 close 两种。拆页时，core-storyline 按 report-forge 的"整册图表与版式规划"做全册规划（§7）；需要选图时，调用 thinkcell 的 tc_advise 取得推荐（§6.2）。

## 6. 输出层

### 6.1 引擎放法

```
vendor/
├── report-forge/       zerox-consulting-report-forge 固定 commit 的完整代码、测试、资产、全部许可与声明文件
├── thinkcell-charts/   zerox-thinkcell-charts，同上
├── onepager/           zerox-onepager，同上
├── patches/            NNNN-<说明>.patch，每个补丁写明原因
└── vendor.lock         上游仓库、commit、每个文件的 sha256
tools/vendor_sync.py    拉取指定 commit → 校验 → 重新打补丁 → 跑引擎自带测试
```

- 起始版本：zerox-skills `ee1f980c8dd7c53408e1a05a084229e6ec03c660`（2026-10-20），即现 zerox.lock 固定的版本。
- 保留的许可与声明文件：
  - report-forge：LICENSE、NOTICE、THIRD_PARTY_NOTICES.md、字体的 SIL OFL 声明；
  - thinkcell：LICENSE、NOTICE（其中写明参考图不在 Apache 范围内，本地副本本来就没有这些图）；
  - onepager：LICENSE.txt。
- 各引擎的 SKILL.md 改名为 `UPSTREAM-SKILL.md` 保留，避免被当成 skill 触发。上游也提醒过副本里不要留第二份 SKILL.md。
- 引擎自带的分析流程文档（report-forge 的 analysis-workflow、analysis-methods、playbooks 等）保留在 vendor 里，方便同步上游；out-* 不引用，也不让模型读。
- 补丁：目前识别出的需求都能在包装层解决，**起始补丁数为 0**。
  - report-forge 的浏览器通道用上游已支持的 `CHROME_CHANNEL` 环境变量设置；
  - onepager 的署名由我们在调用 `project.py record-build` 时显式传 `--F`。

  实施中如果发现必须改引擎，按"一个补丁一个文件、写明原因、跑引擎测试"的规则加。

### 6.2 三个 out-* skill

**共同流程**：

1. 读输入：`07_storyline/slides.json`、`sidecar.json` 和 `03_evidence/`。
2. 转换：`tools/bridge/to_forge.py`、`to_thinkcell.py`、`to_onepager.py` 把我们的格式翻译成引擎输入。来源、主张、指标机械搬运。
3. 转换前检查。以下情况不交给引擎，退回 core-storyline 或分析层：
   - 有台账外的数字；字段缺失；指标公式不闭合；
   - 主张为 unverified、refuted，或 conflicting 且没写采信理由，却要以事实呈现。
4. 渲染。
5. 引擎自检。
6. 统一验收（§8.3）。

**不能以事实呈现的主张，在成品里怎么合法出现**：证据账里的主张保持原样（kind 和 verification 都不改），只在转换脚本输出给引擎时改写：
- unverified 的关键主张（affects_conclusion=true）→ 引擎侧 kind=assumption、verification=not_applicable，statement 加"待确认："前缀，放进"需要先确认的问题"页。非关键的 unverified 主张不进入成品。
- refuted → 引擎侧 kind=assumption、verification=not_applicable，statement 写成"曾认为……，已被推翻"，limitation 写反证来源，放进"被推翻的说法"页。
- 缺口：进风险页，或附录的"补齐路径"。

#### out-report（report-forge）

引擎位置：`_allen-runtime/vendor/report-forge`（由 runtime.py 解析）。任务目录：`07_storyline/forge-work/`。

**一律通过统一入口 `report.cjs` 执行**。新任务默认带 execution-plan-2：生产记录（productionRefs）只有经统一入口执行才会写入；直接调用底层脚本过不了 acceptance 和 package 的门禁。命令顺序：

1. `report.cjs init 07_storyline/forge-work --work-mode editorial --visual narrative-focus-1`
   - 启用 narrative-focus-1，因为我们要用 deck.arc 和 adds；它同时继承 evidence-composition-1 的组合合同。
2. 写入 task 字段（见下），以及转换后的 deck-blueprint.json。
3. `report.cjs plan-update <task> --request activate.json`：激活执行清单。三项固定约束（chart-diversity、layout-diversity、module-fill）独立展示，不得跳过。
4. 完成整册图表与版式规划和模块填充规划，分别用 `plan-update` 提交 chart-plan、layout-plan、module-fill-plan，被接收后才能进入下一步。请求文件的格式以引擎的执行清单协议为准，由我们的包装脚本生成。
5. `deck_blueprint.cjs <蓝图> --task <task> --ready`（ready 校验）。这一步和第 6 步的 `verify_blueprint_pages.cjs` 都是只读校验，不写生产记录，引擎也没有对应的统一入口子命令，所以直接调用；会写生产记录的步骤一律走 `report.cjs`。
6. `report.cjs compile <task>`。compile 返回派生 task（绑定本轮页面），**之后各步都用这个派生 task**。需要单独核对时：`verify_blueprint_pages.cjs <蓝图> <pages.json> --task <派生task>`，pages.json 的路径从 compile 的返回值取（位于 `.forge/runs/<ID>/`）。
7. 作者编写 `pages.html`、`page.css`。静态片段只用内联 SVG 和 data: 资源，不用脚本、canvas、外部资源。
8. `report.cjs assemble <派生task> --pages pages.html --css page.css`
9. 代表页：
   - `report.cjs qa <派生task> --html <deck.html> --tier iteration --pages …` 和 `--tier smoke` 取得预览证据；
   - 实际查看 2–3 张能暴露不同风险的页（核心定量页、最密页、定性或行动页），记录逐模块观察（moduleObservations）；
   - 用 `plan-update` 提交 representatives；批量制作完成后再提交 production。
10. `report.cjs qa <派生task> --html <deck.html> --tier acceptance`
11. `report.cjs review-pack <派生task> --audit <audit.json>`：生成作者稿和独立审查稿（未填写的草稿）。
12. 审查：
    - 作者在作者稿上填写，覆盖每页；
    - 成品审查员在独立审查稿上填写，覆盖每页：
      - coverage：四层 page、exhibit、annotation、typography，加 narrative；
      - narrativeReadings（逐正文页实际读到的收束句）；
      - 每页的截图证据（evidence 的 path 和 sha256）；
      - qualityChecks 三项整册审查（chart-diversity、layout-diversity、module-fill）。
    - panelRefs、relationRefs 等 ID 列在 review-pack.json 的组合检查清单和叙事检查清单里。审查员把它们写进 coverage，并填写实际所见，不需要读蓝图。每条 narrativeReadings 的 observedTakeaway 至少 6 个字。
    - 字段以引擎的审查合同（review_contract）为准。告警的处置用 `report.cjs dispositions` 记录。
13. `report.cjs aggregate <派生task> --audit <audit.json> --reviews '["author.json","independent.json"]'`
14. `report.cjs snapshot <派生task> --audit … --review <review.json>`：冻结审查快照，供以后修订复用。
15. `report.cjs package <派生task> --audit … --review … --name <报告名>`：生成交付文件，复制到 `08_deliverables/report/`。
16. `report.cjs archive <task>`；实际交给用户后，用 `plan-update` 登记 delivery。
17. 中断后用 `report.cjs resume <task>` 查看状态和待办，用 `report.cjs next <task>` 查看下一步。遇到残留锁时，用 `recover-lock` 按引擎规则处理。

- **修订**：storyline 迭代后重新导出时，用 `report.cjs reuse <派生task> --audit <新验收> --snapshot <旧快照>` 准备继承草稿；变化的页和全局判断仍须重新审查。
- **task 字段默认值**：
  - `kind=report`（完整报告，含封面、参考页、封底；模板默认值是 fragment）；
  - `complexity=complex`、`majorConclusion=true`（L2 起都要求独立审查，与 §8.3 一致）；
  - `theme`、`typography` 用引擎默认值（mckinsey、serif-report-bold），以后换品牌模板时改这里；
  - `mode=reading`，`ratio=16x9`。
- **讲者备注与备用页的交付**：
  - 备用页作为 appendix 页进入报告；
  - 讲者备注由 sidecar.json 生成 `08_deliverables/speaker-notes.md` 和 `speaker-notes.pdf`，按页码对应。

#### out-chart（thinkcell-charts）

| 能力 | 用法 |
|---|---|
| tc_advise 推荐 | core-storyline 拆页时调用：给数据和意图，取得首选和 2 个备选。规则引擎不懂业务，由 core-storyline 结合受众判断是否采纳，不采纳时写理由。草稿里空值会被填 0，转换时一律改回缺失，并提示补数 |
| 单图 55 种、dashboard / facet 拼版、decorations（CAGR、total_diff、diff、value_line）、多图 `{"slides":[...]}` | 按 slides.json 的 chart_spec 生成 |
| tc_validate | 渲染前必跑。FAIL（"不能做"）→ 退回补数据或换图；只有用户明确接受折中时，才加 `--force`，并在图注写明折中内容。WARN（"能做但有问题"）不拦渲染，由 core-storyline 按问题修正，或在图注写明局限 |
| tc_render | 交付 PPTX、PNG、可编辑 HTML 三份 |
| 自检 | STYLE_SPEC §11 结论页四件套、§12 易误读护栏；PNG 检查重叠、压字、颜色语义；可编辑 HTML 实测"改字 → 保存 → 重开" |
| 配色 | 默认 consulting_navy；用户可指定其他 7 套主题之一 |

报告里的图表由 out-report 自己用 SVG 画。out-chart 负责单独交付的、可编辑的 PPTX 图表。

#### out-poster（onepager）

onepager 没有"输入 → HTML"的渲染器，HTML 由模型照着骨架模板手写。所以 out-poster 保留上游的完整手工流程，并在生成后加数字回查：

项目目录：`07_storyline/poster-work/`。

1. `project.py init <项目目录> --slug … --title … --source …`：先建项目（目录里已有 manifest 时，init 会拒绝）。
2. 内容理解，产出内容蓝图 `blueprint.json`，写进项目目录。可用的主张按 §3.4 的关口表判定，和报告的规则相同。
3. 配置不再逐项询问用户，按场景给推荐配置，并在回复里说明，用户可以只改其中一项。
   - 企业诊断默认：A2 横向、B7 数据新闻、C2 中密度、T3 信息图、E1、署名由调用方指定；
   - BigNumber（E1）只能用所属主张为 verified 或 single_source 的指标，不足 2 个时改为 E2。这一条有意比 §3.4 严：醒目的大数字不用有争议的值。
4. 内容重构与图表规划，产出 `onepager.ir.json`，写进项目目录。T4 必须写设计意图声明；技术类内容执行语言门控。
5. 按骨架模板生成 HTML。
6. `quality_check.py <html> --style … --size … [--no-bignum] --format json`、`render_check.py <html> --size … --format json`。WARNING 必须写保留理由。
7. `capture.py <html> --output … --width … --height …`：截图尺寸按 A1–A4 对应。
8. `project.py record-build <项目目录> --A … --B … --C … --T … --E … --F <署名> --html … --png … --static-check … --render-check …`，然后 `project.py validate <项目目录> --require-sources`。
9. **数字回查**：从生成的 HTML 抽出全部数字，逐个和证据账的指标比对，对不上就报错。
10. 文件命名与 `-vN` 迭代规则按上游。交付文件复制到 `08_deliverables/poster/`。

### 6.3 转换脚本的映射

`tools/bridge/MAPPING.md` 是完整映射表的真源，在实施第 4 步写定并配测试。要点：

| 我们 | report-forge |
|---|---|
| claims.kind：fact、data → fact；estimate → estimate；forecast → forecast；assumption → assumption；recommendation → recommendation；judgment → recommendation（statement 以"我们判断……"开头，所在页的 cornerLabel 标"判断"，以此在成品中与建议区分，MAPPING.md 配测试）；third_party_view → fact（statement 写成"某机构认为……"） | claims.kind |
| verification：用户材料主张（§3.4）且 reviews 表有覆盖它的 user_confirmation 记录 → provided；其余 verified、single_source → source_checked；unverified 的关键主张、refuted → 按 §6.2 改写为 kind=assumption、not_applicable；conflicting 已写采信理由 → source_checked（正文并列写出两种说法）；conflicting 未写采信理由 → 不得进入 | claims.verification |
| 来源 ID + 原件路径 + 定位 | sources `{label, locator}` |
| 主张字段 period、population、unit、denominator、calculation、inference、limitation | 同名字段 |
| metrics（value 或 formula） | metrics |
| 故事线模式 | deck.arc（对照表见 §5.3；arc=other 时写 arcReason） |
| page_role、story_beat、proves、adds、density、visual_intent | pageRole、storyBeat、proves、adds、density、visual（form、primary、layout、readingPath、selection、capacity） |
| 00_brief（问题、目的、范围、期间、基线、约束、成功标准） | analysis.brief |
| 01_issue-tree 的子问题 | analysis.issues |
| 02_method-plan 的方法计划 | analysis.workItems（method、rationale、counterEvidence 取自压力测试的反例） |
| gaps 表 | analysis.gaps |
| core-synthesis 的方案和"维持现状" | analysis.options（决策型任务必须包含维持现状方案和真实备选。editorial 模式下引擎不查这一条，由我们的转换前检查执行） |
| 中心论点 | analysis.synthesis.answerClaimRefs（必须由某个正文页承担） |
| visual_intent 的图型 | visual.form（映射到 report-forge 的形式库 ID；两边 selection.relationship 枚举的对照写进 MAPPING.md） |

### 6.4 成品防篡改

复用 report-forge 自带的蓝图 / 页面摘要绑定和内容篡改防护，不另起一套。海报和图表按 acceptance.json 记录的文件哈希复检。验收后文件被手改，复检会发现，并要求重新验收。

## 7. 呈现风格切换与深度

### 7.1 呈现措辞改动

| 位置 | 现状 | 改为 |
|---|---|---|
| core-synthesis:37 输出格式 | 正文一页以内；假设和待确认问题 ≤4 条、路线图 ≤6 行、风险 ≤3 条 | 取消页数和条数上限。保留：第一句是答案、SCQA、问题拆解、各子问题结论、路线图、事前验尸、附录。完整论证进正文，过程细节进附录 |
| core-synthesis description | "写成一页正文加附录" | "写成完整正文加附录" |
| lib-consulting:91 | "一页正文" | 删去"一页" |
| lib-management:98 | "一页格式" | 删去"一页" |
| scene-company:34 | "写一页画像" | "写公司画像"（§5.2 接入） |
| scene-company:41 | L2 "交付一页结论（Markdown）" | L2 交付正式报告（§7.2） |
| scene-bp-review:55 及评审意见格式 | "一页格式"；"关键风险（最多 3 条）""问题（最多 8 条）" | 去掉"一页"和条数上限；按重要性排序 |
| scene-topic | "依据：三条左右" | 去掉条数 |
| core-review:22 决策者视角 | "一页内能不能看懂" | "首屏能否读到答案；行动是否具体；是否回答主导问题" |
| router 任务单模板:11 | 交付物选项含"一页结论" | "正式报告 / 图表 / 海报 / 评审意见 / 个人计划" |
| README:3、:45；ARCHITECTURE:63 | "一页结论""一页内能否看懂" | 同步改 |
| 版式与图表 | 无 | core-storyline 做整册图表与版式规划，主动追求不同的图型和版式，每处重复写明理由；out-report 保留引擎的三项固定约束 |

不改：core-method-select:58"每个子问题默认一个方法、够用就停"（管分析，不管呈现）；reviewer-prompts:34 红队"最强反对理由不超过 3 条"（审查提示词，不是呈现）。

### 7.2 深度表（真源：router SKILL.md）

| | L1 快答 | L2 标准（默认） | L3 深度 |
|---|---|---|---|
| 任务文件夹 | 不建 | 建 | 建 |
| 审查 | 作者按红队清单自查 | 事实核查员、红队、成品审查员 | 加方法审查员、决策者视角，共 5 个 |
| core-research | 不用（用 core-evidence） | scene-topic 必用，走 deep-research 的 L2 流程（2–4 条研究线）；只跑 `research check`，不封包 | scene-topic 必用，走 L3 流程（5 条以上研究线、多轮迭代），并封包；scene-company、scene-bp-review 在某个子问题是开放研究时也用 |
| core-diligence | 不用 | Quick（按 §5.2 接入条件） | Standard；用户要求"深入"时用 Deep |
| core-storyline | 不用 | 协作模式 | 协作模式 |
| 交付 | 对话里直接回答 | 正式报告（out-report）；按需加图表、海报；调用了 core-diligence 时加尽调附属交付物 | 同 L2，加研究包（用了 core-research 时） |

用户明确要求时，L2 也可以封包研究包。

注：表中的研究线数量（L2 为 2–4 条，L3 为 5 条以上）沿用 deep-research 阶段 0 对各级的工作量描述；什么问题属于哪一级，仍由 router 按问题范围判定。

scene-personal 的交付保持现状（个人计划，不出正式报告），除非用户要求。

## 8. 审查与统一输出标准

### 8.1 设计阶段

本文档交给用户前，由 3 个互不相通的独立子代理审查：
- 真实性：上游描述逐条回原文件核对；
- 完整性：拿三份清单逐节对照；
- 收口：术语、标准一致。

第一轮审查结果和处理方式见 `2026-10-22-zerox-absorption-review.md`。v2 修订后再做一轮复审，只把改动部分交给原审查角色。

### 8.2 开发阶段

- 每完成 §12 的一步，由未参与开发的子代理审查。审查分两类，用统一的问题级别（阻塞 / 重要 / 轻微）：
  - **符合性**：按对照清单逐条核对本步覆盖的条目；检查有无与上游文本高度相似的段落（D3）。
  - **代码质量**，5 条硬标准：
    - 每个脚本有测试，且测试覆盖错误路径；
    - 只用标准库、vendor 已有的依赖，或 §9 的虚拟环境和 doctor 清单里登记的依赖；
    - 路径一律通过 `tools/lib/runtime.py` 解析；
    - 所有枚举来自 schema；
    - 没有 TODO 和占位。
- 阻塞和重要问题修完，才进入下一步。
- 最后做一次端到端审查：审查员亲自打开生成的 PDF、PNG、PPTX，逐页看，不只看检查脚本的结果。

### 8.3 运行阶段：统一输出标准

**输出标准只写一份**：`core-review/references/output-standard.md`。三个 out-* 共用，所有交付物都按它验收：

1. **可追溯**：成品中每个数字都能追回证据账的指标或主张；每条关键结论有来源。由转换前检查和验收脚本机械核对；海报由数字回查核对；事实核查员抽查。
2. **身份如实**：事实、估计、预测、假设、判断、建议在成品中能区分；未核实的不以事实呈现。
3. **前置检查通过**：
   - 研究：`research check`（封包时为 `--final`）；尽调：research_gate、report_status、declared_complete 与 `diligence check-content --final`；故事线：`storyline check`；
   - 各引擎自检：report-forge 的 qa acceptance 与 aggregate，thinkcell 的 tc_validate，onepager 的 quality_check、render_check、project validate。
   - 结果写入 acceptance.json 的 `upstream_checks`。它们是前置条件，不能单独宣称"完成"。
   - 各检查的"通过"标准：脚本类检查零错误即通过。尽调状态中：research_gate∈{complete, partial, not_applicable}、report_status∈{complete, limited} 视为通过，其中 partial 和 limited 会让最终状态最高只到 conditional；research_gate=incomplete 或 report_status=draft 视为失败。
   - `skipped` 只允许出现在 `fixture=true` 的验收记录里（实施第 4 步的夹具）；正式任务出现 skipped，按失败处理。
   - 警告的处置：report-forge 的警告用它自己的 `dispositions` 记录；其余检查（ledger、storyline、research、diligence、thinkcell、onepager）的警告，处置记入 acceptance.json 的 `dispositions[]`（警告来源、处置、理由）。
4. **视觉验收**：
   - 无溢出、截断、遮挡，无没有用途的大块空白；字号可读；
   - 图表不误读（截轴、比例、颜色语义）；
   - 图表和版式的多样性按 report-forge 的整册多样性验收执行。
5. **成品审查员结论**（见下）。
6. **完整性**：
   - out-report：A 级卡片关联的主张在成品中出现；备用页、讲者备注（speaker-notes）、附录、来源清单齐全；尽调交付物齐全（§5.2）。
   - out-chart、out-poster：来源和署名齐全。
7. **未被篡改**：按 §6.4 复检通过。
8. **尽调专项**（只对尽调类交付物）：
   - 22 条人工清单都有记录（§5.2）；visual_review 提示的处置记录完整；
   - §5.2 第 5 点列出的渲染后图型规则逐项满足；
   - 11 问"只读正文复述"通过。

**谁来核对**：

| 项 | 由谁核对 |
|---|---|
| 1 可追溯 | 转换前检查和验收脚本机械核对；海报用数字回查；事实核查员抽查 |
| 3 前置检查 | 验收脚本读取各检查的结果 |
| 6 中"A 级卡片出现"、7 未被篡改、8 中"22 条有记录""处置记录完整" | 验收脚本（对照 cards.jsonl、reviews 表和文件哈希） |
| 2 身份如实、4 视觉、6 中"齐全"、8 中"图型规则""11 问复述" | 成品审查员看页面判断 |

**成品审查员**（core-review 第 5 个角色，L2 起必开）：
- 只看最终交付物的实际页面（PDF 逐页、PNG、PPTX 预览），不看过程文件；
- 只判断上表中"看页面就能判断"的项，独立列出问题清单；
- 对 out-report，在 review-pack 生成的独立审查稿上填写（§6.2 第 12 步）；
- 提示词写入 `core-review/references/reviewer-prompts.md`。

**验收记录** `08_deliverables/acceptance.json`：每个交付物一条，记录文件路径与哈希、upstream_checks、数字追溯结果、成品审查员结论、未通过项和最终状态。

**状态规则**（全文只有这一套，§10 引用它）：

| 状态 | 条件 |
|---|---|
| failed | 任一前置检查失败；或仍有阻塞问题；或引擎硬错误未清零 |
| conditional | 不满足 failed，但有以下任一情况，条件逐条列出：<br>· 有未修的重要问题或未处置的警告；<br>· 尽调 report_status=limited 或 research_gate=partial，条件写成 completion_review 里各缺口的影响；<br>· 因依赖缺失或渲染失败降级为 Markdown 交付，条件写"未出正式成品"；<br>· 没有子代理，未经独立审查 |
| passed | 其余情况 |

只有 acceptance.json 能判定"已完成"：passed 才能说完成；conditional 必须在回复里列出条件；failed 不能说完成。

**没有子代理的环境**：按同一标准自审，验收记录写明"未经独立审查"，按上表最终状态最高为 conditional。

## 9. 运行环境

**本机现状**（2026-10-22 实测）：

- 已有：
  - macOS 26.5.1 arm64；Docker Desktop 28.4；Node 22.23.1；Python 3.14.6（Homebrew，已带 openpyxl 3.1.5、playwright 1.58）；Google Chrome 155；
  - Poppler（pdfinfo、pdftotext、pdftoppm）、fontconfig、Tesseract 5.5.1（含 chi_sim）、Pandoc 3.10。
- 缺：
  - LibreOffice；python-pptx；
  - report-forge 的 npm 依赖和字体环境；
  - Playwright 自带的 Chromium 版本不匹配：本机只有 chromium-1193，Python playwright 1.58 需要 1208。onepager 的截图因此会失败。
- 磁盘剩余约 36 GB。

**默认安装** `install.sh`（不带参数）：

- 安装本仓库的全部 skill，以及 `_allen-runtime`：
  - 复制模式（默认）：把 `vendor/` 和 `tools/` 复制到 `<目标>/_allen-runtime/`，写入安装标记，按现有 place() 的覆盖规则处理；
  - `--link`：`_allen-runtime` 是指向仓库根目录的软链接；
  - `--target DIR`：放在 DIR 下。
- 不再安装 zerox skill。`--remove-old` 同时清理 `zerox-*`：带本脚本安装标记的目录，以及指向 allen-skills 缓存的软链接。

**`--render-deps` 额外做的事**：

- 用 Homebrew 安装 LibreOffice（cask）；Poppler、Tesseract、Pandoc 缺哪个装哪个。
- 在 `~/.cache/allen-skills/venv` 建独立的 Python 虚拟环境，装 python-pptx、openpyxl、playwright，再用这个环境执行 `python -m playwright install chromium`。系统 Python 已经装了部分包，仍用独立环境，是为了隔离版本、不改动系统 Python。
- 在**安装后的** `_allen-runtime/vendor/report-forge` 里执行 `npm ci` 和 `npm run setup-fonts`。字体环境里有绝对路径，不能先装好再复制。
  - `--link` 模式下，这一步发生在仓库的 `vendor/report-forge` 里：node_modules 和字体产物加入 .gitignore；vendor.lock 只登记上游文件，排除这些生成物。
- 生成 report-forge 的能力探测任务 `probe_capabilities.cjs <目录>`。看图验证不能由 shell 脚本完成，install.sh 只提示下一步：由 Claude 在会话里实际打开图片作答，执行 `--verify`，结果写入 `_allen-runtime/.probe.json`。doctor 检查这个文件。

**路径解析** `tools/lib/runtime.py`，所有脚本统一用它：环境变量 `ALLEN_RUNTIME` → `<skill目录>/../_allen-runtime` → 仓库根目录（开发时）。

**检查** `tools/doctor.py` 逐项检查：
- 命令是否存在、版本是否满足（Node ≥20、Python ≥3.10）；
- 虚拟环境与包；npm 依赖；字体环境；
- 系统 Chrome 能否无头启动；Playwright Chromium 的 executable_path 是否存在；
- LibreOffice 能否转换；Tesseract 是否有 chi_sim；
- report-forge 能力探测是否已验证（`.probe.json`）；
- thinkcell 浏览器测试的两个前提：必须设 `NODE_PATH` 指向 `_allen-runtime/vendor/report-forge/node_modules`（让脚本能加载 Node 版 playwright）；同时设 `TC_BROWSER_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`（否则它会去找没有安装的、与 Node playwright 版本对应的 Chromium）。两项都检查；
- 磁盘剩余空间。

每项输出"通过 / 缺失 / 版本不足"，以及具体的修复命令。

## 10. 出错处理

| 情况 | 处理 |
|---|---|
| 依赖缺失 | 运行前先跑 doctor；缺什么就写明怎么装，不默默跳过；相关交付降级为 Markdown 并说明，状态按 §8.3 判定 |
| 引擎自检不通过 | 按问题修复后重跑，最多 3 轮。仍不通过，按 §8.3 的状态规则判定 |
| 逐页内容出现台账外数字或新推论 | 转换前检查拦截，退回分析层补齐并核实 |
| 渲染崩溃 | 交付 Markdown 版，写明失败步骤、错误信息和修复办法；状态按 §8.3 判定 |
| 输入文件无法读取 | access=unreadable；依赖它的主张保持 unverified |
| 抓取被拦截 | 先排除误判；确认是付费墙或登录墙的，记 metadata_only；需要执行 JS 的，按 D7 用 9222 浏览器；需要登录的，先问用户 |
| 证据账写入中断 | 从 .backup 恢复；`ledger check` 发现不一致时拒绝继续写入 |
| 子代理不可用 | 串行执行；审查降级为按清单自审并注明；状态按 §8.3 判定 |

## 11. 测试

| 层 | 内容 | 位置 |
|---|---|---|
| 公共模块 | ledger 读写、事务、patch、merge、check（含 §3 的全部校验）、render、export；runtime 路径解析；schema 自检 | `tools/lib/tests/` |
| core-research | 按上游 24 个用例的全部场景重写；补上清单 D 节列出的未覆盖分支（符号链接、哈希不一致、未登记附件、列不一致、boolean/NaN、整理层填了来源、method 不在 analysis/、提取层出现 derived、README 标记异常、checks.json 过期、manifest 格式错误等）；capture 的网络、嗅探、PDF、超限、截断、编码用本地 HTTP 服务测试；seal 的依赖闭合、原子发布（失败不留半个包）、复核过期（改动后指纹不符）、已封包拒绝再封、修订副本；lite、init/resume/revise | `core-research/scripts/tests/` |
| core-diligence | 从零写，覆盖清单 H 节末尾"重写至少应覆盖"的全部项：控制图、截止日隔离、bridge、研报三指针与同日多份、三种完成状态、财务比率（含新增）、评分门槛、检索计划裁剪、report-content 全部校验（原上游渲染器的 report_model 约束、媒体安全规则迁到 `diligence check-content` 测试）；22 条人工清单的记录检查；`diligence_to_manuscript` 的转换（每类内容块都有夹具；只有证据的块补登主张；value_tier 和"含义"的生成规则）；`check-content --after-split` 的拆页后复核（块丢失、主题缺失、时间线与人物卡的同章规则）；按目的选择故事线模式。HTML 篡改检测迁到 out-report 测试；渲染后图型规则中能机械判断的部分，在 `tools/bridge/tests/` 测试 | `core-diligence/scripts/tests/` |
| core-storyline | 按上游 47 个用例的全部场景重写；补上优化 1–10 的测试，包括"去掉数字必须报错"类反向用例 | `core-storyline/scripts/tests/` |
| core-intake | 虚构公司 BP 各一份：文字版 PDF、扫描版 PDF、.docx、.pptx（含备注和表格）、加密 PDF、损坏文件；快照摘录比对 | `core-intake/scripts/tests/` |
| 转换脚本 | 正向：证据账 + slides.json → 三种引擎输入，引擎校验器通过；待确认、被推翻主张的改写；judgment 的 cornerLabel。反向（必须拦截）：台账外数字、公式不闭合、unverified 以事实呈现、conflicting 无采信理由、字段缺失、决策型缺维持现状方案、arc=other 缺理由、引用 forecast 指标的图未声明预测样式 | `tools/bridge/tests/` |
| 引擎 | report-forge：`npm test`、`npm run test:render`、`npm run test:upgrade-render`。thinkcell：`tests/run_tests.py`、unittest、`tests/check_html_browser.cjs`（同时设置 NODE_PATH 和 TC_BROWSER_PATH，见 §9）。onepager：`tests/` | selftest 调用 |
| 输出验收 | acceptance.json 状态规则（每种 failed、conditional 条件都有用例）；数字回查；篡改复检；尽调专项的脚本部分 | `core-review/tests/` |
| 端到端冒烟 | 一个虚构任务：文字要求 + 三份文件 → intake → 拆问题 → 证据账 → 综合 → 故事线 → 报告、图表、海报 → acceptance | `tools/selftest.sh --e2e` |
| 选方法 | 保留现有 12 道题 | 手工 |
| 仓库结构 | validate.py：新 skill 的必备小节；vendor 下没有 SKILL.md；vendor.lock 哈希一致；schema 合法；不再依赖 zerox.lock | CI |

测试材料全部虚构，不使用真实企业资料。

## 12. 实施顺序

| 步 | 内容 | 完成标志 |
|---|---|---|
| 1 | 运行环境：`install.sh --render-deps`、`_allen-runtime`、`runtime.py`、doctor、vendor 引入与 vendor.lock | doctor 全部通过；三个引擎自带测试通过；能力探测通过 |
| 2 | 统一证据账：`ledger.schema.json`、`slides.schema.json`、`sidecar.schema.json`、`tools/lib/ledger.py`；core-evidence 迁移（台账、来源评价、核实关口） | 单元测试通过；现有核实关口改读新台账 |
| 3 | core-intake 与 router 的先后衔接 | 测试材料都能处理成标准结构 |
| 4 | 输出层：三个 out-*、转换脚本与 MAPPING.md、统一输出标准、成品审查员 | 用手写的 slides.json 和夹具证据账出三种成品；acceptance 中与 storyline 相关的检查标为 skipped（仅限夹具），其余检查全部通过 |
| 5 | core-storyline | 对照清单逐条完成；测试通过；用真实流程重跑第 4 步的夹具任务，acceptance 为 passed |
| 6 | core-research | 同上 |
| 7 | core-diligence（含 diligence_to_manuscript） | 对照清单逐条完成；测试通过；一个虚构公司的尽调任务走完报告链路，acceptance 为 passed |
| 8 | 呈现风格切换、深度表、router 和 scene 接线、移除 zerox、文档、validate.py、build-zips.py、CI | 端到端冒烟通过；validate.py 通过；CI 通过 |

每步结束后执行 §8.2 的审查。每步提交一次或多次，全部完成后提一个 PR。

## 13. 规模与耗时预期

- 实施预计 8 步，每步都有独立审查，总工作量大。实施计划会把每步拆成能单独验证的小任务。
- 运行时，L2 的一份正式报告要走完 report-forge 的执行清单、代表页、三项固定约束和独立审查，耗时明显长于现在的 Markdown 交付。out-report 的说明里写明耗时预期。
- L2 调用 core-diligence Quick 时，上市公司研报流程仍是强制的（上游规则），会增加检索时间和对网络的依赖。

## 14. 风险与待确认

| 项 | 说明 | 处理 |
|---|---|---|
| 分析规则是否也要改 | D4 只确认了"呈现按 report-forge"。本设计保留"每个子问题默认一个方法、够用就停"，以及核实关口对冲突的现有处理 | 用户已确认：分析规则不变 |
| 尽调报告不做移动版 | 改走 report-forge 后，没有上游的移动端视图；交付桌面 HTML 和 PDF | 用户已确认：不做移动版 |
| L2 默认出正式报告 | 按 D4，L2 起默认交付 out-report，耗时变长（§13） | 用户已确认：接受更长耗时 |
| 磁盘空间 | 剩余约 36 GB，本次约增加 2 GB | 安装前 doctor 提示剩余空间 |
| 上游变化 | 上游升级时补丁可能冲突 | vendor_sync 跑引擎测试兜底；升级是可选动作 |
| 无许可部分的边界 | 能力清单是我们自己的描述；实现只依据清单和公开常识，不打开上游文件复制文字或代码 | 开发阶段的符合性审查检查有无与上游文本高度相似的段落 |
| 清单本身的准确性 | 清单由子代理通读上游生成，可能有遗漏或误读 | 设计阶段的真实性、完整性审查已回到上游原文件核对；实施时有疑问的条目再回原文件确认 |
| claude.ai 上传 | out-* 依赖本机引擎，claude.ai 聊天环境里用不了 | build-zips 排除 out-*；INSTALL.md 写明 claude.ai 只支持到 Markdown 交付 |
