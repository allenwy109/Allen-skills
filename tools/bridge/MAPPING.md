# 转换映射表

我们的格式（证据账、slides.json、图表 spec）到三个引擎输入的映射，是转换脚本的唯一依据（设计 §6.3）。每个引擎一节，随对应的输出 skill 一起写定并配测试。目前已写定：媒介无关 report model、thinkcell（out-chart）、onepager（out-poster）、report-forge（out-report），以及尽调内容到故事线母版的转换（core-diligence）。

## 公共规则（所有引擎）

- 数字只来自证据账的指标：取值用 `tools/lib/metrics.py`。公式算法与报告引擎一致；显示按指标的 `decimals` 做十进制半入（中点远离零），不出现 -0。
- 指标能进成品的条件（`metrics.check_presentable`）：
  - 被至少一条主张引用；
  - 状态不是 `missing` 或 `not_applicable`；
  - 引用它的主张里至少有一条是 `verified`、`single_source`，或 `conflicting` 且冲突表已写采信理由。
- 来源说明由 `source_ids` 生成，格式是 `<来源标题>（<来源 ID>）`，多个来源用"；"连接。
- 估算、预测、假设、判断、建议类主张的数值进入成品时，必须注明身份。
- 状态为 `approximate` 的指标进入成品时，必须注明"近似"。

## 媒介无关 report model（`tools/bridge/to_report.py`）

`build(task, slides, sidecar=None)` 返回 `(report, coverage)`。`report` 遵守
`report.schema.json` 1.0.0；它只表达内容、身份与引用关系，不含页宽、坐标或渲染器参数。

| slides.json / 证据账 | report block | 规则 |
|---|---|---|
| 正文页的一个 panel | 一个 block | block ID 为 `p<两位页码>-<panel id>`；`purpose/form/relationship/reason/role/alternative/tradeoff/capacity/semantic_type/visual/slot/span`、relation 与 anchor 原值保留 |
| `svg.custom` | `chart` | 首批支持的图表块 |
| `html.text` | `text` | 首批支持的文字块 |
| `html.kpi` | `metric` | 首批支持的指标块 |
| `html.table` | `table` | 首批支持的表格块 |
| panel 的 claim_refs | `claim_refs`、`identity` | identity 是所引用主张的 kind 集合；未知主张拦下 |
| panel 的 claim_refs + 证据账主张/关系 | `content.claims` | 机械带入 statement、kind、confidence、scope、limitation，以及支持/反证的 evidence excerpt、source_id、locator；正文只显示紧凑证据，完整来源仍只在附录 |
| `semantic_type=pain-demand` + `decision-research.json.pain` | `content.pain_groups` | 只按 claim_refs 连接；带入 segment、trigger、workaround、consequence、purchase_signal、confidence、counter claim statement 和 validation_gap，不复制或改写真源 |
| `semantic_type=competition` + `decision-research.json.competition` | `content.comparison` | 按五层替代方案和共同购买 criteria 生成矩阵；可选 `values` 原样带入，缺项明确显示“待同口径核实”，不暗造评分 |
| 页的 metric_refs 与 panel 主张的 metric_refs 交集 | `metric_refs` | 防止把未在正文声明的指标带入，也防止正文指标在输出消失 |
| 主张 → claim_evidence → evidence | `source_ids`、`source_bindings`、`references` | binding 按 source_id 排序并带排序去重后的 evidence locator；references 汇总正文 evidence locator 与 A 卡 source_refs locator，保留来源标题和 URL；panel 显式 source_ids 一并保留 |
| 正文来源与仅附录来源 | `citation_registry` | 正文按 block/source 首次出现编号并去重；仅附录来源按 source_id 排序追加。每项固定包含 `source_id`、连续 `number` 和 `source-<id>` anchor；完整来源字段只在附录显示 |
| A 级卡片 | `executive_summary.a_card_refs` | A 卡关联的主张必须进入正文，否则覆盖失败 |

coverage 的 `input` 和 `output` 都含排序后的 `claims`、`answer_claims`、`a_cards`、`panels`、`relations`、
`metrics`、`sources` 集合。deck.answer_claim_refs 必须存在于证据账；A 卡必须有 claim_id 且对应主张进入正文。
两侧必须完全相等；ledger 关键表或内容对象的重复 ID、孤儿 panel、relation 内重复 panel、未知引用或集合差异统一报
`REPORT_COVERAGE_MISMATCH`。未列入上表的 form 报 `REPORT_UNSUPPORTED_BLOCK`，不做猜测性降级。

`report.registry` 列出报告内合法的 claim、metric、source、card、panel、relation ID。JSON schema 负责字段结构和
`identity` / `content.form` 枚举；`validate_report(report)` 负责 schema 不能表达的 block ID 唯一性和内部引用完整性，
并先检查引用、references、source bindings 和 locator 列表没有重复，再验证 registry 与报告实际内容集合双向相等；
生成器返回前必须通过该校验。转换前复用 `Ledger.check()` 校验实际依赖的 claims、metrics、sources、cards、evidence、
claim_evidence 六张表，结构错误、重复 ID 和悬空引用都转成带 code 的 `ReportError`，不向调用方泄漏 KeyError。

## thinkcell（`tools/bridge/to_thinkcell.py`，用于 out-chart）

| 我们的图表 spec | thinkcell spec | 规则 |
|---|---|---|
| `data` 里的 `{"metric": "m-…"}` | 同位置的数值 | 按上面的公共规则取值、半入。指标不能进成品就拦下 |
| `data` 里的裸数字 | — | 拦下：追溯不到证据账 |
| `data.axis_break`、`format`、`delta_format`、`scale_max`、`decimals`、`font_size` | 原样 | 版式和格式参数，允许写数字 |
| `decorations[].value`（value_line） | 数值 | 必须是指标引用 |
| `decorations[].from` / `to`、`highlight`、`callouts` 里的位置数字 | 原样 | 位置参数 |
| `source_ids` | `source` | 拼成来源说明；写了 `source` 就拦下 |
| `footnote` | `footnote` | 有近似值时追加"部分数值为近似值"；有非事实数值时追加"含……数值，不是实际数据" |
| 其余字段（`type`、`title`、`subtitle`、`unit`、`theme`、`palette`、`highlight`、`callouts`） | 原样 | `type`、`title`、`unit`、`data`、`source_ids` 必填 |

测试：`tools/tests/test_bridge_thinkcell.py`（正向 5 例；反向 10 例：裸数字、缺失指标、未核实主张、无人引用的指标、不存在的指标、不存在的来源、缺来源、手写来源、缺标题、装饰写裸数字）；端到端测试在 `out-chart/scripts/tests/test_out_chart.py`。

## onepager（`out-poster/scripts/out_poster.py`、`tools/bridge/poster_numbers.py`）

onepager 没有"输入 → HTML"的渲染器，海报 HTML 由作者手写，所以这里不是逐字段转换，而是"给作者的事实清单 + 成品回查"。

| 我们 | onepager | 规则 |
|---|---|---|
| 能进成品的主张（公共规则） | `source/<slug>-facts.json`（项目 source 目录） | 每条主张给出陈述、身份、核实状态、指标显示值和单位、来源说明 |
| 事实或数据类、已核实或单一来源主张的指标 | BigNumber 候选（`bignum_candidates`） | E1 只能用候选；不足 2 个改 E2 |
| 来源说明 | 页面上的来源文字；IR 和蓝图的 `source_refs` 写来源 ID | `project.py validate --require-sources` 检查 |
| 海报 HTML 上的数字 | — | 回查：必须等于某个能进成品的指标的显示值；年份（1900–2100 的 4 位整数）和编号除外；`--allow` 显式放行的要写进验收 |
| 非事实身份的指标 | 页面文字 | 数字前后 20 字内要有"估算、预测、假设、判断、建议、约、预计"之一 |
| `bignum-value` 元素里的数字 | BigNumber | 只能用已核实或单一来源主张的指标 |

测试：`tools/tests/test_poster_numbers.py`（5 例）；端到端测试在 `out-poster/scripts/tests/test_out_poster.py`（4 例）。

## report-forge（`tools/bridge/to_forge.py`，用于 out-report）

报告引擎的内容真源是蓝图（schemaVersion 3）。转换只做机械搬运，判断类字段（proves、adds、panels 的用途和选型理由）由 core-storyline 写进 slides.json。

| 我们 | report-forge 蓝图 | 规则 |
|---|---|---|
| 主张 kind：fact、data、third_party_view | `fact` | 第三方观点的陈述本身要写明"某某认为" |
| 主张 kind：estimate、judgment | `estimate` | 引擎没有"判断"；页面上显示为"估计" |
| 主张 kind：forecast、assumption、recommendation | 同名 | 引擎在陈述前加身份，指标后加"（预测）"等 |
| 可以呈现的主张，支持证据的来源全部 origin=user | `verification: provided` | |
| 可以呈现的主张，其他来源 | `source_checked` | single_source 在限制里加"单一来源"；冲突已处理的加采信理由 |
| 没有来源的建议、假设 | `not_applicable` | 没有来源的事实、估计、预测拦下 |
| 未核实且 affects_conclusion=true | `assumption` + `not_applicable`，陈述句尾加"（待确认）" | 引擎会在句首加"假设："，所以不用前缀，避免两层叠加 |
| refuted | `assumption` + `not_applicable`，"曾认为……，已被推翻" | 限制写反证来源 |
| 未核实且不影响结论；冲突未处理 | — | 拦下 |
| 指标 | 挂在第一个引用它的主张下；公式的输入挂在公式所属主张下 | 运算名和参数原样；missing、not_applicable 不进入；approximate 在所属主张限制里注明"近似值" |
| 主张的陈述、分母、计算、推论、限制，页面标题、proves 里的数字 | `{{metric:id}}` | 数字后紧跟的单位一并替换；优先匹配本主张或本页引用的指标；找不到或有歧义就拦下；4 位年份、编号除外；`--allow` 放行的写进验收 |
| 副标题、adds、讲者备注里的数字 | 原样 | 引擎不解析这些位置的指标引用，所以只核对：必须等于某个指标的显示值 |
| 来源 | `sources[来源 ID] = {label: 标题, locator: 网址 · 本报告用到的证据定位}` | 参考资料页（bookends.references）用同一份来源，带作者、日期、网址 |
| deck.brief、answer_claim_refs | `analysis.brief`；一个已回答的 issue、一个 editorial 的 workItem；`synthesis.answerClaimRefs` | 分析和核实在我们的层完成，引擎用 editorial 模式，不做前置分析审查；缺口不进 analysis.gaps（在风险页或附录列出） |
| 页面 | `id = p + 两位页码`；`pageRole`、`storyBeat` 原样；`title`=action_title；`cornerLabel`=section；`speakerIntent`=讲者备注 | 页面角色和故事节拍两边枚举一致 |
| panels | `exhibit.semantics.composition.panels` + `visual.regions` | relationship、reason、alternative、tradeoff → selection；slot、role、span → region；阅读顺序 = panels 顺序 |
| relations | composition.relations | 多个 panel 必须有 |
| deck.cover | 封面、封底（bookends.cover / backCover） | 首尾页补 `data-frame-boundary="space"`（引擎要求每页声明，模板没写） |

引擎 ready 校验不查、要到 compile 才报的项，转换时提前拦下：自定义布局的 slot（main/left/right/top/bottom/aside/full）、panel 的主张不属于本页、主展品不唯一。

成品回查（out-report finish，`poster_numbers.check(report=True)`）：只查正文页里没有 `data-content-key` 的文字。绑定的文字由引擎对照蓝图核对，作者手写的图注、坐标标签不经过引擎。

测试：`tools/tests/test_bridge_forge.py`（12 例）；端到端测试在 `out-report/scripts/tests/test_out_report.py`（5 例，走完统一入口的全部步骤）。

## 尽调内容 → 故事线（`tools/bridge/diligence_to_manuscript.py`，用于 core-diligence）

不是引擎转换，而是把通过校验的 `03d_diligence/report-content.json` 机械转成 core-storyline 的输入，不改写结论。

| report-content | 故事线 | 规则 |
|---|---|---|
| 内容块 | 母版里 `<!-- block:<章节ID>-<序号> -->` 标记 + 渲染后的文字；block_map.json 一行 | ID 规则与 core-diligence 的 `dcontent.block_ids` 相同（有测试保证） |
| 块引用的证据 | 证据支持的主张 → 卡片引用〔card-…｜来源 定位〕，放在句末标点之前 | 同一主张只建一张卡；卡片 value_tier 按主张 materiality（critical、major → A；minor → B） |
| 只引用了证据、没有主张的块 | 补登主张：kind 按证据属性（actual → fact，数值证据 → data；forecast → forecast；estimate → estimate；opinion → third_party_view）；verification 按独立来源组数（≥2 → verified，否则 single_source） | 期间、单位取自证据；限制按来源等级写（只有 C、D 级时写"只有公司自己的材料，未经独立核实"）；estimate、forecast 写 assumptions |
| 指标卡、图表里的数值 | 补登主张时同时登记证据账指标（null → missing，不填 0），写进主张的 metric_refs | 小数位按数值本身 |
| explanation | "### 标题" + 正文 + "限制：…" | 卡片的"含义"取主张 inference，为空时取该主题解释的首句 |
| 图、表、矩阵、关系图、流程、时间线、人物卡、图片 | 母版里的表格或列表（图写单位、期间、主体名称、图型和数据表；流程注明是否按顺序；关系图注明布局不表示层级） | 拆页时由作者决定页面形式（out-report 的形式对应见 core-diligence/references/report-content.md 第 8 节） |
| project 表 | 00_story-brief.md（7 项，没有的标"假设"） | |
| sources | 01_materials_index.md | 处理状态按 access：full → 读完；partial → 读至部分 |
| 章节和主题 | 03_storyline.md 的结构树；故事线模式：公司研究 → "公司研究"，其他目的 → "尽调结论" | 主线确认点记为 auto_adopted（由内容契约决定） |
| 风险、缺口、scope_note | 缺少时补"风险与未知"（专项为"风险与红旗"）、"补齐路径"、"方法与局限"三节 | |

拆页后复核：`diligence check-content --after-split` 用 block_map.json 和 slides.json 的 block_ids 核对每个块都落到页上、时间线与公司身份同章、人物卡不与公司身份同章，并重跑全部内容规则。

测试：`core-diligence/scripts/tests/test_pipeline.py`（转母版 6 例；端到端 2 例：尽调 → 转母版 → 拆页 → 故事线检查 → 拆页后复核 → out-report → 验收通过）。
