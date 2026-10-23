# 报告内容契约（report-content.json，1.2 版）

主报告的内容写在 `03d_diligence/report-content.json`，`diligence check-content` 校验；之后由 `tools/bridge/diligence_to_manuscript.py` 转成故事线的母版，经 core-storyline 拆页、out-report 渲染。模板 `assets/templates/report-content.json` 里全是占位，故意不能直接用。

## 1. 结构

- 顶层（全部必填，不允许别的字段）：version（"1.2"）、title（写判断）、subtitle、language（zh-CN 或 en）、summary、scope_note、sections。
- 所有文字非空、不残留 `{{ }}` 占位；文字里可以写 `[ev-0001]` 引用证据。
- 章节：id（小写字母开头，只含小写字母、数字、连字符，全文唯一；不能用 main、overview、sources、evidence、report-data、toc-toggle，不能以 chart-、ref-、topic- 开头）、title（不能是"检索日志""资料请求清单"这类过程性标题，那些放底稿）、可选 summary、blocks。
- 推荐顺序：身份与沿革 → 创始人与团队 → 产品、客户、业务运转 → 营收与盈利 → 营销与增长 → 竞争 → 风险与决策。不用"模块 07"这类内部标签。每节"短导读 → 主视觉 → 意义与限制"。会改变决策的反证和限制放在相关分析旁边，不能全部折叠到附录。结尾写推进条件、待确认事项、暂停条件。

## 2. 11 个解释主题（explanation 块，全文各出现一次，放在任意章节）

| topic | 读者应能回答 |
|---|---|
| identity | 这是一家什么公司，研究的是品牌、集团还是法人，三者关系如何 |
| history_team | 何时、由谁、因何创立，哪些团队和变化形成了今天的业务 |
| offering | 具体卖什么，客户得到什么 |
| customers_markets | 谁使用、谁选择、谁付款，在哪、经什么渠道；客户定位和已验证的客户分布有何区别 |
| transaction_flow | 一笔代表性业务如何从需求、下单走到交付、收款、售后 |
| operating_model | 公司自己做什么、合作方做什么，库存、质量、履约等责任归谁 |
| revenue_costs | 怎样收费，主要成本费用，利润和现金受什么机制影响，哪些未验证 |
| differentiation | 客户为何选它，哪些是已观察的特点、哪些是公司说法、哪些待验证 |
| financial_performance | 营收规模、构成、毛利率、净利率分别是多少或为何未知，属于谁、哪一期、什么来源，是否只是 GMV、估计或单体数据 |
| marketing | 通过什么渠道、内容投放、品牌触达客户，如何获客、转化、复购；哪些只是可观察的做法，哪些效果有数据 |
| competition | 主要竞品和替代方案是谁、为何选它们、哪些维度可同口径比较、在什么条件下有差异或被替代 |

status：supported（至少 1 条证据）、partial（至少 1 条证据，并写具体限制）、unknown（写具体限制，可以没有证据）。status 只供检查，不在正文显示，也不代表事实认证；公司自述不能用 supported 暗示已独立核验。

## 3. 13 种内容块

| 块 | 字段 | 规则 |
|---|---|---|
| text | text | |
| bullets | items | 非空文字列表 |
| callout | title、text | |
| table | title、columns、rows、note | 行列等长，单元格非空 |
| metrics | items（label、value、unit、period、entity_id、kind、evidence_ids、note） | kind 为 actual / estimate / forecast / company_claim（不能 mixed）；value 为 null 时显示"未披露" |
| chart | chart_type、title、unit、period、entity_id、kind、evidence_ids、note、points（proportion 另有 scale_max） | 见第 4 节 |
| timeline | title、items（title、text、evidence_ids、date、status），可选 purpose | date 只知道年份就只写年份；status 为 completed / planned；已完成的公司历史事件不能引用预测证据 |
| process | title、items（title、text、evidence_ids、basis），可选 purpose、ordering | ordering：sequence（带箭头编号，只在顺序有依据时用）或 conceptual（只表示关联）；purpose=business_model 的才算业务模式图 |
| people | title、profiles（name、role、period、background、contribution、limitations、evidence_ids） | 人物章不能和 identity 同章 |
| image | role、path、title、alt、caption、source_url、captured_at、usage_note、evidence_ids | 见第 5 节 |
| matrix | title、columns（≥2）、rows（label、cells：text、basis、evidence_ids）、note，可选 purpose | 逐格写依据，不用空白、问号或颜色暗示优劣；矩阵不算定量图 |
| diagram | title、purpose、period、entity_id、note、nodes、edges | 节点 id 小写唯一；边两端是已有节点、不能自连接；flow 为 product / money / information / relationship；边要有 label；没有重复边和孤立节点 |
| explanation | topic、title、text、status、evidence_ids、limitations | 见第 2 节 |

basis（process、matrix、diagram 共用）：evidence（资料支持）、company_claim（公司口径）、inference（分析示意）、unknown（待核实，可以没有引用）。entity_id 必须在主体表里，行业数据写 industry。

## 4. 图型与真实性

kind：actual / estimate / forecast / company_claim；图级可以写 mixed，此时每个点自带 kind；图级不是 mixed 时，点上的 kind 要一致。实际数据点不能引用预测或估算证据。点标签唯一；数值要么是数字要么是 null（缺失不能写 0 或文字）。

| 图型 | 用于 | 规则 |
|---|---|---|
| bar（横向）/ column / line | 规模比较、趋势（同一口径） | 2–24 点，至少 2 个已知值；只有 column 允许负值 |
| donut | 构成（完整分母、互斥分类） | 2–6 项，不能缺失或为负，总和大于 0 |
| range | 价格带、区间 | 每点 low、high 同为 null 或同为数字且 low ≤ high；不画中点 |
| proportion | 有明确量尺的比例 | 要写 scale_max；单位是百分比时必须是 100；最多 8 点 |
| waterfall | 收入到利润的完整桥接 | 2–12 点；首点 start、末点 total、中间只有 delta 或 total；total 必须等于累计值（高精度校验） |
| stacked_bar | 可比的构成 | 2–8 组，每组 2–6 个分项，全图最多 24 段；各组分项一致、非负、不缺失；不自动归一化 |

禁止：不同数据商、主体、口径的数据连成曲线；截断零基线；缺项或重叠分类却画成完整百分比；0 和缺失混用；给不可评分的项目编综合分；用布局暗示控制或担保关系；把计划事件当已完成；年化运行率、网站 GMV、集团收入放在同一根轴上；把"九位数中段"变成精确中点；没有转化数据却画漏斗；用无依据的二维坐标或热力颜色表示竞争地位。

业务模式图：顺序有据才用 sequence；只知道流向用 diagram；连方向都未知就用 conceptual；示意不能冒充真实订单；只有交易机制整体未知时才能不画。图片、人物卡、指标卡、结构图、定量图分别统计，不以图的数量代替判断。

## 5. 图片

只用项目内真实的 PNG、JPEG、WebP 文件（按文件头判断），每张 ≤5 MiB、合计 ≤15 MiB；不用 SVG、远程图片；path 是项目内相对路径（不能绝对路径、不能含 ..，解析后不能逃出项目目录）；source_url 为空（本地材料，并通过证据关联）或不带用户名密码的 http(s) 网址；captured_at 写本次取得日期（晚于基准日会提示）；alt、caption、usage_note、evidence_ids 必填。没取得图片就删掉图片块，不留空框。截图只证明页面当时的样子，不验证宣传内容、人物身份或经营实绩。原始 SVG Logo 可以截图转成位图，保留出处，不能重新生成。

## 6. 跨块规则

- 11 个主题齐全且不重复。
- transaction_flow 不是 unknown 时，至少一张业务模式图。
- 有公司时间线（timeline.purpose=company_history）时，必须和 identity 同章、至少 2 个事件；没有时，history_team 必须是 partial 或 unknown 并写限制。
- 人物卡不能和 identity 同章。缺人物卡、缺图片、没有定量图、全部主题 unknown 都会提示。

## 7. 编排提示（visual_review，只提示不阻断）

连续文字块累计超过约 600 字；本章第一张分析图之前已有 3 段以上解释；financial_performance、marketing、competition 所在章没有合适的图；数字只出现在文字里却没有定量图；表格很密但本章没有分析图；全稿 3 张以上定量图全是同一种。处置写进 reviews 表（type=visual_review_disposition）。

## 8. 渲染到 out-report 时的对应

| 内容块 | 页面上的形式 |
|---|---|
| timeline | svg.custom（custom 布局），有数量时按趋势 |
| people | html.text（需要图形时 svg.custom） |
| process（含业务模式） | diagram.process 或 kit.processFlow；sequence 带箭头和编号，conceptual 不带 |
| diagram | 优先 diagram.mechanism，不够用时 svg.custom |
| image | html.text 内嵌 data: URI，保留来源、取得日期、权利说明和图注 |
| chart、metrics、table、matrix | 对应的形式；每张图附可查看的原始数据表（附录页 html.table） |
| text、bullets、callout、explanation | 正文页组件 |

渲染后的图型规则（零基线、null 显示未披露、预测虚线、区间不画中点、比例量尺说明、堆叠和瀑布的免责说明、推断用虚线、关系清单与编号徽章、矩阵逐格依据、可展开数据表、证据附录只列用到的证据）由成品审查员按 `../../core-review/references/output-standard.md` 的尽调专项核对。拆页由 core-storyline 完成，每页的 block_ids 记录落在这页的内容块；拆页后用 `diligence check-content --after-split` 复核。
