# zerox-due-diligence 能力清单（供从零重写用）

**通读范围**：SKILL.md、README.md、agents/openai.yaml、.gitignore；references/ 全部文件（workflow、evidence-standard、quality-gates、scoring-framework、purpose-playbooks、industry-adapters、report-design、visual-examples.json、modules 01–18、sources 下 5 个文件）；schemas 下 2 个文件；templates 下全部文件（13 张 CSV、project-config、financial-input、report-content、两个 md 底稿模板、request-list、interview-outline）；assets 下 css 和 js；scripts 下 14 个 .py 和 README。

**测试**：发布包里没有任何测试文件。.gitignore 排除了 /tests/、/evals/ 等目录，所以"测试覆盖了什么"无法从包内得知。下文 H 节末尾列出了重写时应补的测试点。

以下全部是我用自己的话描述的；字段名、枚举、文件名、参数、平台名照写。

---

## A. 流程

### A1. 范围确认的输入项
| 输入 | 取值 / 要求 |
|---|---|
| target | 目标名称。尽量带法定全称、官网、注册地、统一信用代码或注册号、证券代码 |
| purpose | `company_research`（公司研究，正式目的）或六类专项：`investment`、`acquisition`、`partnership`、`credit`、`supplier`、`competitor`。只有确实不知道用途时才为 `null`，此时 `purpose_status=pending`；有值时必须为 `confirmed`。用户说"全面了解这家公司"就直接定为 company_research，不再追问交易意图 |
| depth | `Quick` / `Standard` / `Deep`，默认 Standard。深度控制覆盖面、历史跨度、拆分粒度和验证强度；访问权限另记，不算深度 |
| geography | 注册地、主要经营地、交易涉及的司法辖区 |
| focus | 约定的研究范围、用户的关键问题和重大性；有具体交易时再记方式和规模 |
| materials | 用户已有的 BP、财报、合同、报告、可用数据库 |
| as_of_date | 信息截止日，按用户时区。要标明是否为历史时点研究；历史研究要隔离截止日之后的资料 |
| constraints | 时限、预算、工具、访问权限（联网、数据库、数据室、访谈、现场、系统、付费分别确认）、输出语言和格式。配置中 `network` 取 unknown/online/offline |

澄清规则：
- 主体有歧义：列出候选，只问最少的必要信息；依赖身份的判断先暂停，不依赖身份的准备工作可以继续。
- 目的有分歧：一次最多问 3 个问题，同时继续做不依赖答案的基础研究。
- 不能擅自假设对方有投资授权、交易安排或授信额度。

### A2. 阶段（每阶段写清输入、动作、产出、完成条件、失败处理；可以回退迭代）
| 阶段 | 动作 | 产出 / 闸门 |
|---|---|---|
| Phase 0 范围与能力 | 定目标、目的、深度、基准日、重大性、必答问题；单独确认访问权限 | 项目配置、约定范围、能力限制；不得虚构联网或数据库能力 |
| Phase 1 实体与控制链 | 锁定法律主体、品牌、集团边界，股权和控制关系，上市状态 | 主体表和控制链；有歧义则冻结依赖身份的结论 |
| Phase 2 研究设计 | 先覆盖共同骨架，再按重要性挑深入问题；制定来源、正反证计划和停止条件；基础扫描后更新 | 检索计划、待验证声明、适用模块、上市研报是否触发；早期假设不当定论 |
| Phase 3 官方与基础资料 | 先确认官网，直接读公司、产品、条款、团队、渠道页；取得登记、披露、财报、监管、司法原件；合法取得真实图片 | 来源和证据台账、原页和图片定位、版本口径；访问失败要登记，不能拿媒体转述冒充官网已读 |
| Phase 4 强制研报 | 上市公司或上市子公司执行模块 18；其他目标按行业相关性检索 | 报告目录、全文获取状态、逐份阅读记录、最新性、覆盖差距 |
| Phase 5 模块分析 | 把历史、组织、业务、行业、竞争、财务串成一条解释链；比较当前解释和替代解释 | 机制解释、关键结论、反证、缺口；不能用行业数据替代公司表现 |
| Phase 6 核验与冲突 | 核对主体、时间、口径、同源；检验目标方声明和研报核心假设 | 声明核验表、冲突表、估算底稿 |
| Phase 7 研究判断 | 复核关键结论、风险、情景和剩余缺口的影响；专项形成决策条件；评分必须显式启用 | 目的适配判断、completion_review、补证条件；关键问题不可判断时保持 limited |
| Phase 8 报告与校验 | 按 1.2 契约编排 11 个主题、时间线、人物章、业务图、图片和矩阵；生成 HTML 和底稿；做结构、理解、事实、视觉复核 | HTML、audit.md、检查结果 |
| Phase 9 交付 | 交付 HTML、底稿、台账、更新触发条件；资料请求和访谈提纲放底稿 | 读者能直接拿到判断和行动条件；核验者能追溯 |

### A3. 实际操作步骤（脚本化）
1. `init_project.py` 在技能包外新建工作区。
2. 填 `entity-map`（一行一个实体）和 `entity-relations`（一行一条边）。区间左闭右开 `[effective_from, effective_to)`；proposed 不算已控制。`control_chain_checked` 和 `control_evidence_ids` 要有实证。登记 events、行业词、语言、模块适用性，再跑 `sync-coverage`。
3. 跑 `search_plan.py` 生成计划，再真实检索。成功、未找到、失败都写入 `search-log.csv`；计划不能当日志。
4. 原件存 `materials/`（图片建议放 `materials/images/`）；用 JSON 批量提交互相引用的记录；每次写入都留 `.ledger-backup-*` 快照。
5. 模块结论写 `modules/NN-名称.md`，同一编号只能有一个文件；资料请求和访谈围绕开放缺口定制；按需跑财务计算；评分要先确认 `scoring_override`。
6. 先为每章列出"读者问题 → 已有事实/数字 → 主视觉 → 不能转图的原因"，再填 `report-content.json`（1.2）。
7. `build_report.py --project --content --output x.html` 同时生成 `x-audit.md`。
8. `check_report.py`；处理 visual_review 的提示；做"只读正文"理解验收；预览桌面、移动、打印。
9. 交付 HTML、底稿、台账、计算底稿、补齐路径和更新触发条件。没有额外授权不建自动监控。

### A4. 三种"完成"互相独立
- `research_gate`：只表示上市研报必读资料的获取、阅读、覆盖情况。取值 complete/partial/incomplete/not_applicable。
- `report_status`：draft / limited / complete。complete 表示"约定范围完成"，必须带 `completion_review`。
- `declared_complete`：所有必需动作都已完成，且没有开放缺口。
- 三者不能互相改写或推导。

### A5. 工具或访问失败时
- 无联网：标"离线材料分析"，只给补查计划。
- 无代码环境：按契约人工处理，并注明未跑自动校验。
- PDF 或扫描件读不了：尝试合法下载或 OCR；仍无法确认的数字和页码不引用。
- 付费墙：记录障碍，找合法替代，列出需用户提供的资料；不绕过登录或付费。
- 工具失败不会取消强制检索，也不会改写阅读状态。

---

## B. 判断边界与硬规则

### B1. 主体、期间、口径
- 集团、母公司单体、子公司、分部、品牌、签约主体不能混用。
- 持股比例不能用来分摊子公司收入；母公司上市不等于提供担保；分部可能包含多家主体，不等于目标子公司。
- 比较或计算前，先对齐主体、合并/单体/分部范围、期间、币种和单位、实际还是预测。发布日、资料期间、访问日分别记录。
- `scope` 枚举：consolidated / standalone / segment / brand / not_applicable。定量数据不能用 not_applicable。
- 集团数据用于子公司结论时，必须有 bridge（桥接说明），且声明标签为【推断】，否则报错。
- `time_scope=retrospective` 是事后补充资料，不能支持或驳回历史时点结论；截止日之后发布或修订的资料若标为 as_of，直接报错。
- 缺失不是 0，也不能用行业均值填补；标"不适用"必须给理由，不能为了覆盖率把未知改成不适用。
- 缺失原因枚举：`not_disclosed`、`not_found`、`access_restricted`、`unreadable`、`not_executed`、`not_applicable`。

### B2. 控制关系
- 关系类型枚举：control、joint_control、significant_influence、minority、brand_of、branch_of、other。
- 关系状态：current / historical / proposed；核验状态：pending / verified。verified 必须有证据。
- 只有 `control`、`brand_of`、`branch_of` 三类边会触发上市追溯，并且要求在基准日生效、已 verified、不是 proposed。参股、联营、合营、同一自然人股东、经销、品牌授权、名称相似都不算控制。
- 生效中的控制图不能有环，也不能自我控制。
- 关系不明时标"待确认"，可以先检索关联上市主体的研报，但不能写成控制已证实。
- 目标本身上市、同时有上市控股股东时，两者分别建档。
- 股转挂牌、发债、拟上市、已退市企业不自动等同交易所上市公司（listing 枚举：listed / unlisted / otc / bond_only / proposed / delisted / unknown）。

### B3. 七类证据身份标签
| 标签 | 用于 |
|---|---|
| 【事实】 | 有资料支持的事件或状态，写明主体和范围 |
| 【数据】 | 可量化的实际数据，带口径、期间、单位、来源 |
| 【推断】 | 本项目基于证据和明确假设作出的推理或估算 |
| 【判断】 | 本项目作出的评价或建议 |
| 【第三方观点】 | 机构或个人的评价、预测、评级、目标价、管理层指引 |
| 【待核实】 | 有线索但支持不足、身份未确认，或冲突未解决 |
| 【缺口】 | 必需信息缺失 |

- 预测数字只能标【第三方观点】或【推断】；标【数据】但 attribute 不是 actual 会报错。由实际数据算出的比率可以标【数据】，但要指向输入证据和公式。
- 【推断】和【判断】必须填 assumptions。
- 标签只打在关键结论、表格行、风险项上，不给标题或说明句机械地加标签。

### B4. 单源确认与独立印证
- 原件在它直接覆盖的范围内可以单源确认事实；争议事项和重大判断尽量找独立印证。
- 转载同一原件不增加独立性：用 `origin_group` 标记同源，`upstream_source_id` 记录二手引用链；检查器对同源组超过 1 条的情况给警告。
- 来源等级 S/A/B/C/D 只是排序起点，可以按具体材料调整并写 `grade_reason`。等级、访问程度、事实核验、置信度是四件不同的事。
  - S：官方登记、监管/司法文件、法定披露、核验过的审计文件
  - A：方法透明、可追溯的调查和统计
  - B：券商研究、商业数据库
  - C：企业宣传、管理层自述、一般报道、访谈
  - D：匿名或无法追溯
- 置信度（high/medium/low/unknown）按每条声明综合判断：是否直接支持、是否原件全文、主体期间口径版本是否匹配、有无独立印证和反证、利益关系和方法局限。禁止用"最高等级 × 来源数"之类的公式。
- 搜索摘要只能证明结果页上出现过某句话；只读首页不能算已读其他页面。
- 来源访问状态为 metadata_only / access_blocked / unreadable 时，不能据此形成正文证据。
- 签了字的合同只能证明合同内容和当事方的表示，不能证明已履行、已付款或已盈利。

### B5. 冲突处理
- 先对齐主体、期间、口径、版本；仍有差异时，记录双方的值和口径、原因分析、采信理由、是否改变决策、决策影响。
- 不能用取平均、删去反证、调低重大性的方式消除冲突。
- 冲突状态 open/resolved；resolved 必须写 `accepted_reason`。
- 存在 open 且 `decision_changing=true` 的冲突时，不能判定范围完成，也不能发布综合分。

### B6. 假设检验与反证
- 每个关键问题都要写"当前解释 → 合理替代解释 → 能区分它们的证据 → 什么情况会改变判断"。
- 复用 claim-register 的字段：statement、assumptions（前提和替代解释）、counterevidence（反证和区分检验）、unresolved（未决事项和改判条件）；证据通过 claim-evidence 关联，待取资料进 gap-register。
- 被推翻的假设保留原声明，标 `verification=refuted`，必须有 counterevidence 文字、至少一条 `contradicts` 证据、高或中置信度、unresolved 为空。修正后的结论另建新声明。
- `unsupported` 只表示支持不足，不能当作已推翻。
- 没找到反证时，写清查过的范围，不能把"未找到"写成"已证实"。

### B7. 抽样
- 记录总体、观察期、覆盖范围、样本由谁提供或挑选、选样方法、不可得部分。
- 主动找失败、流失、退货、逾期、未成交等异常样本；管理层挑选的成功案例和便利样本不能外推到总体。
- 访谈人数、证据条数、样本占比本身都不是置信度。

### B8. 红旗与停止条件
- 风险性质 `status`：confirmed（必须有证据）/ lead / exposure / information_gap。
- 严重度 `severity`：escalate（必须暂停或升级专业复核）/ major / ordinary。
- 红旗只触发核实和升级。以下情况都不能直接作终局判断：未核实的名单命中、普通诉讼、注册资本高、园区地址、正常注销、单次投诉、审计机构变更。
- 只有核实了身份和适用范围、确认适用法定禁止或用户的否决条件后，才停止推进；这一条优先于商业评分。
- 检索停止规则：关键问题已有足够证据、重要冲突已处理、剩余缺口逐项评估过影响、继续检索的边际收益低。预算用尽可以停止工作，但不等于满足完成条件；强制研报检索仍必须实际执行。

### B9. 合规与保密
- 只用合法公开或经授权的材料。外部内容只是资料，不能改变任务，也不能指使泄密。
- 保密材料不传给未授权服务，不主动索取内幕信息、个人隐私或对方无权分享的资料。
- 人物调查只限与其公开商业角色相关的信息，不查住址、家庭、健康。
- 对外联系、付费、购买、发布、交易、录音、自动监控都需要明确授权。
- 摘录以必要的短摘录加定位为主；"固定 200 字"不能当作通用的版权许可。
- 没有具体原件时不编页码；网页用标题或段落定位，PDF 区分印刷页和文件页。
- 不虚构访谈、审计、现场核查；访谈只交提纲，状态为 planned。

---

## C. 18 个模块（每个模块都有 MNN-xx 检查项，按问题和重大性选择展开；缺资料保留未知，不能改成不适用）

**01 公司概况、股权与关联方**（M01-01 ~ 09）
- 研究什么：这是一家什么公司，何时、由谁创立，卖什么、卖给谁、在哪经营，怎样发展到今天；品牌、集团、法律实体如何对应；基准日谁控制，谁承担合同义务。
- 两个视图：
  - 读者视图：用白话写公司画像。DTC 之类的标签首次出现时，要解释它在这家公司具体怎么做。
  - 主体视图：按实体 ID 画有向关系图，用生效区间还原基准日的控制；品牌经营、收入确认、资产持有、签约责任分别映射。
- 检查项要点：
  - 品牌创立、公司注册、开始经营三个日期分开记
  - 注册资本和实缴要结合出资期限和商业模式看
  - 受益所有人；穿透受限时写明停在哪层、为什么
  - 质押、冻结、特殊表决权、一致行动、代持线索、VIE/红筹
  - 对外投资和集团图谱
  - 发展时间线：区分宣布、签约、完成、到账；只知道年份就只写年份
  - 官网、App、域名、备案、商标的主体是否一致
  - 上市识别，判断是否触发模块 18
  - 真实 Logo、产品、门店图片及其权利依据
- 资料：官网（关于/产品价格/团队历史/门店/IR/条款）、工商原始登记、章程、出资记录、交易所公告、品牌备案。
- 产出：画像、主体核验结论、关系台账；正文对应 identity、history_team、offering、customers_markets 四个主题和公司时间线。
- 陷阱：
  - 注册地不等于主要市场；服务可达地区不等于已有销售
  - 发布日期不等于事件日期；融资新闻不等于钱已到账
  - 同名站点或猜测出来的路径不能算官网
  - 门店照片不能证明整个店网
  - 身份冲突可能是曾用名或重组造成的，取得变更原件前冻结相关结论
- Quick 也必须完成消歧和上市触发判断。

**02 创始人、核心团队与治理**（M02-01 ~ 08）
- 研究什么：谁创立、谁共同建设、现在谁负责什么；谁能决策；关键人依赖和激励是否支持本次目的；战略取舍、资源配置和历史兑现。
- 检查项要点：
  - 人物消歧；"合伙人"要分清联合创始人、管理合伙人、商务伙伴
  - 正常注销、创业失败、诉讼、被正式认定失信，四者分开判断
  - 职责与可归属的贡献，必须有事件、期间、依据
  - 激励、稀释、归属和离职条款、投资人权利
  - 董事会、关联交易决策、内控
  - 历次公开声明是否一致（措辞变化不等于造假）
  - 敏感名单命中要先做身份核对
  - 战略链条：目标 → 投入 → 负责人 → 结果 → 纠偏
- 资料：官网团队页（注意可能过期，记录任职时点和访问日）、任职公告、具名访谈、章程、董事会资料、监管记录。
- 产出：独立人物章（姓名、角色期间、背景、贡献、限制）、治理结论。
- 陷阱：
  - 用名校或大厂经历推导经营能力
  - 把职称当贡献，把旧履历当现任
  - 把多人的经历硬分配给某一个人
  - 补写英雄叙事
  - 频繁离任可能是正常交接

**03 商业模式与经营**（M03-01 ~ 07）
- 研究什么：客户为什么选它；一笔业务怎样从需求走到交付、收款、售后；目标和合作方各做什么；收入和成本怎样形成。"机制能解释"和"盈利已被验证"是两件事。
- 方法：沿一笔代表性业务讲清五个环节：
  1. 需求、入口、选择理由（使用者、决策者、付款人分开）
  2. 下单或签约 → 生产或服务 → 交付或验收 → 收费 → 售后、退换、续约
  3. 每个环节由谁承担，自营还是外包，库存、质量、信用风险归谁
  4. 收费方式、主要成本费用
  5. 有同口径数据时才做单位经济，并把订单/GMV/ARR 逐步桥接到收入、利润、现金
- 按模式讲机制：零售/消费品牌、SaaS、平台撮合、制造/项目交付各有一套要讲清的环节。混合业务分别讲。
- 单位经济：CAC、LTV、留存、ARPU、NRR 都要定义分子分母、队列、期间；注明是否已扣补贴、退货、履约、获客成本。代理指标单独标注。
- 区分四个问题：模式是否成立、增长是否快、盈利是否好、现金流是否健康。
- 资料：产品价格页、服务/订购/配送/退货条款、合作方披露、财报附注、获授权合同和订单。
- 产出：正文 transaction_flow、operating_model、revenue_costs、differentiation 四个主题，以及 `purpose=business_model` 的业务图。
- 陷阱：
  - 用"轻资产""小单快反"当解释本身
  - 虚构一笔示例订单
  - 用行业惯例补全目标公司的做法
  - 缺内部财务就说整个模式无法理解
  - 高 ARR 低现金可能是预收节奏问题
  - 写"未知"之前要先检查台账是否已有后来补到的材料

**04 市场、行业与产业链**（M04-01 ~ 08）
- 研究什么：可达市场是否支持业务假设；外部供需和产业链利益分配怎样传导到目标公司。
- 要点：
  - 先定市场口径（产品、客户、地域、期间、收入/出货/GMV）
  - TAM/SAM/SOM：数据够时才做自上而下和自下而上交叉测算，前提不满足就记缺口
  - 统计、协会、官方数据、券商报告交叉核对
  - 历史事实、机构预测、本项目情景分开，并记预测的发布时点
  - 需求拆成存量更新、新增渗透、终端消耗、渠道补库存；供给拆成有效产能、新增爬坡、退出约束
  - 分析利润留在产业链哪一环
  - 只为实际有暴露的宏观变量建"暴露 → 传导 → 滞后 → 缓释"路径
- 陷阱：
  - 把全球全品类市场当可达市场
  - 子行业重复加总
  - 把行业增长当公司增长
  - 把宏观变化机械地映射为同幅度利润变化

**05 竞争与替代**（M05-01 ~ 08）
- 研究什么：客户真实的替代选择是什么、主要对手是谁、在哪些可比维度不同、优势是否有证据、能否持续。主报告必答。
- 要点：
  - 按客户需求、地域、预算、购买场景选对手，不按搜索热度或同行标签
  - 竞品矩阵逐格标证据、期间、范围，缺数据就填未知
  - 份额、CR3/CR5/HHI 只在市场边界和样本足够时计算
  - 分析议价、进入、转换成本、网络效应、牌照、数据、品牌、规模；"拥有专利/数据"不等于"形成壁垒"
  - 追溯"行业第一""无对手"的定义和分母
  - 对手数量由市场结构决定，不凑数
  - 优势写成可检验的机制，用跨期客户行为、可比价格和毛利、输赢记录检验；说明维持优势的代价和可能被侵蚀的途径
- 资料：客户公开采购记录、竞品官网对应页（记录市场、版本、币种、促销、日期）、竞争者披露、合同定价、试用。
- 陷阱：
  - 用主观评分或雷达图把缺口包装成比较结论
  - 官网标价当成交价，集团规模当单产品规模
  - 先说"领先"再在脚注里撤回
  - 编造对手名

**06 阶段与业务痛点**（M06-01 ~ 06）
- 研究什么：每条业务线处于什么验证阶段（验证、PMF、规模化、成熟、转型、衰退，允许同时存在多个阶段），当前症状背后的约束是什么。
- 要点：
  - 用付费、留存、复购、交付、单位经济证明阶段，不按融资轮次或人数
  - 从客户、产品、获客、交付、组织、资金、合规找约束
  - 投诉、员工评论、招聘只算线索，要分析样本偏差
  - 区分症状、根因、短期波动、结构性问题
  - 输出痛点、证据、影响、可缓释性、验证方法、优先级
- 未来情景交给模块 07。
- 陷阱：招聘激增或投诉上升可能只是扩张或样本偏差。

**07 增长空间与瓶颈**（M07-01 ~ 06）
- 研究什么：增长靠哪些可实现条件驱动，最先会卡在哪里。
- 要点：
  - 增长分解树：新客、留存、价格、频次、组合、产能、地域、并购；每个因子先定义，避免对已包含留存的活跃客户数再乘一次留存率
  - 约束：需求、渠道、交付、人才、资金、技术、许可、组织
  - 基准/乐观/悲观情景要给假设、输入来源、敏感性、触发条件和失效条件；围绕少数决定性变量；不随意给概率
  - 没有企业基数时只做定性情景，不伪造收入或利润预测
  - 不能同时假设放量、提价、降本却没有各自依据
- 输出：关键增长条件、最重要瓶颈、可观察的领先指标、反证。

**08 政策与监管**（M08-01 ~ 07）
- 研究什么：哪些规则具体影响经营资格、成本或交易。
- 要点：
  - 识别各辖区的制度和主管部门
  - 许可证核对持证主体、范围、有效期、续期
  - 已生效、已发布待生效、征求意见稿、政策解读分开记
  - 补贴和税惠拆成资格、申请、确认、到账，并检验到期影响
  - 按适用性覆盖出口管制、制裁、反垄断、数据跨境
  - 写出"适用主体 → 义务或许可 → 合规证据 → 收入/成本/现金/交易影响"链条
- 陷阱：命中名单或属于敏感行业，不等于所有交易都被禁止。

**09 商业尽调**（M09-01 ~ 08）
- 研究什么：怎样获客营销、客户怎样转化留存、收入、客户和合同能否兑现。营销是主报告必答内容；本模块验证模块 03 的机制是否真实成立。
- 要点：
  - 客户真实性、付费还是试点、集中度、流失
  - 订单 → 履约 → 验收 → 开票 → 收款能否串成一条可核对的链
  - 营销：渠道、人群、内容和活动实例、转化入口、渠道依赖、续约定价；投入、触达、转化、留存、回款分开看
  - 供应商集中度和替换成本
  - 重大合同条款：排他、控制权变更、终止、赔偿
  - 官网案例要和客户侧信息比对
  - 对重要声明设反证检索
  - 样本覆盖和选择偏差
  - 同一队列看新增、扩购、收缩、流失；区分补贴、压货、短期大单
- 陷阱：
  - 曝光、粉丝、下载当销售实绩
  - Logo 或意向合作当付费关系
  - 没有转化数据却补造点击率、CAC、LTV、ROI
  - 画通用漏斗
- 输出：主报告必须回答"向谁营销、用什么渠道和动作、怎样连接到销售、目前能证明什么效果"。

**10 运营尽调**（M10-01 ~ 07）
- 研究什么：能否按质量和时间持续交付。
- 要点：
  - 用工主体（社保、派遣、外包口径不同）
  - 产能、良率、利用率的分母
  - 交付周期、延期、退货、返工、验收
  - IT、内控、权限分离、业务连续性和灾备
  - 认证的范围、主体、有效期
  - 资产权属、租约、扩产投入
  - 桌面研究、远程演示、现场核查分开记录，没做的不声称做过
  - 设计产能、有效产能、实际产出三者对比
  - 单点依赖的恢复时间要和业务可容忍的中断时间比较
- 陷阱：
  - 有灾备制度不等于演练过
  - 单一工厂或低利用率可能只是扩产爬坡

**11 技术、产品与数据**（M11-01 ~ 08）
- 研究什么：技术权利和能力是否真实、可持续、可转移。
- 要点：
  - 自研、集成、采购、外包、授权的边界
  - 架构和技术债：招聘信息和博客只是有限线索
  - 专利的状态、权属、范围、商业相关性（数量不等于质量）
  - 开源义务按实际使用、修改、分发或服务方式判断
  - 数据来源、授权、隐私、跨境、删除
  - 可复核的基准测试：记录版本、环境、样本、对照、失败情形；同时看效果、成本、延迟、可靠性
  - AI 业务补查模型和算力依赖、推理成本、数据权利、供应商变动
  - 渗透测试、代码扫描须明确授权，否则只形成核验请求
- 陷阱：
  - 演示不等于生产可用
  - 用单一榜单代表商业适配
  - 专利或招聘多不等于产品能力强

**12 财务尽调**（M12-01 ~ 12）
- 研究什么：营收多大、由什么构成、利润率如何、盈利质量、资金和债务情况。营收规模、结构、利润率是正文必答。
- 要点：
  - 资料真实性、审计范围和意见、合并还是单体
  - 原则上覆盖近三年加最新一期
  - 三表联动、收入确认、总额法还是净额法、季节性
  - 毛利率、营业利润率、净利率分别用对应利润除以同主体同期营收
  - 结构占比只在分项和总额可比时计算，不把缺失类别补成"其他"凑满 100%
  - 应收账龄、合同资产、存货、营运资本、现金转换周期
  - 有息债务、租赁、担保、受限现金、表外安排
  - 资本开支、研发资本化、商誉减值、少数股东
  - 现金跑道要区分经营消耗和总体消耗
  - 关联交易、税务、审计机构变更、重述
  - 金融等行业改用专门指标
  - Altman、Beneish 只在版本、行业、变量都齐备时用，信号不等于舞弊或破产概率
- 四条分析线：
  - 可持续盈利：从报表利润出发调整，双向调整并保留桥接
  - 现金与再投资：区分维持性和增长性投入，区分受限和可用资金
  - 资金约束：按时间排出现金最低点和集中到期
  - 投入产出：可靠时才算资本回报
- 陷阱：
  - 用网站 GMV、融资额、下载量、门店数代替营收
  - 子公司亏损写成集团亏损
  - 把"九位数"这类模糊说法擅自收窄为精确金额
  - 利润增长而回款弱，不直接认定舞弊

**13 法律与合规**（M13-01 ~ 10）
- 研究什么：当前法律状态如何影响具体经营或交易。
- 要点：
  - 主体资格和交易授权
  - 案件要素：角色、案号、请求、金额、阶段、裁判、执行、和解、履行
  - 同一争议的一审、二审、执行记录要去重，不能简单加总
  - 被执行、失信、限制消费、终本分别解释
  - 行政调查、处罚、刑事线索、起诉、定罪分开
  - 抵押、质押、冻结、担保、知识产权
  - 劳动、隐私、消费者、反贿赂、反洗钱、竞争合规按相关性选
  - 制裁名单核对身份、辖区、限制范围、所有权和控制规则
  - 披露数据库的局限（仲裁保密、撤下）
  - 列出需律师确认的具体问题
- 陷阱：仲裁没公开不等于不存在；普通涉诉可能已经履行。

**14 ESG**（M14-01 ~ 05）
- 研究什么：重要的 ESG 问题怎样影响现金、许可和供给。
- 要点：
  - 按行业重大性筛选议题
  - 承诺、制度、投入、结果、第三方验证五层分开
  - 处罚、事故、整改记录时间和当前状态
  - 外部评级写明机构、日期、方法，不跨体系比较或平均
  - 区分物理中断和转型成本
  - 治理部分和模块 02 共用，不重复计入风险
- 陷阱：高评级和事故并存，可能是评级时点或范围不同。不相关的议题写理由，避免装饰性章节。

**15 风险与红旗**（M15-01 ~ 06，所有目的必需）
- 研究什么：哪些风险和未知会改变理解或决策，影响沿什么路径发生，何时升级、何时关闭。
- 要点：
  - 风险库覆盖：主体/控制、治理、客户、供应、技术、财务、法律、监管、数据、交易、上市关联、ESG/运营
  - 每条写：信号、检测方法、来源、替代解释、确证条件、影响、缓释、关闭条件
  - 区分 confirmed / lead / exposure / information_gap
  - 三级严重度
  - 同一根因只建一条主风险并注明传导路径，不重复扣分
  - 相关风险组成压力情景，但不机械相加概率或损失
- 内置 12 行"可执行风险库"，每行给出信号 → 检测方法 → 替代解释 → 确认条件 → 缓释与关闭条件。例如：签约方和品牌主体不同、关键人退出、高集中且有流失、单一供应、技术不能复现、利润和现金背离、诉讼冻结、许可过期或名单命中、数据授权不明、交易权属不清、把集团支持当担保、事故和整改不一致。

**16 估值与交易**（M16-01 ~ 09，只在明确需要估值或交易分析时用）
- 研究什么：价格和条款是否被现金和权利支持。
- 要点：
  - 方法选择（可比公司/交易、PE、PS、EV/EBITDA、DCF、行业方法）及适用前提
  - 统一估值日、币种、股本、预测期、会计口径、控制权和流动性折溢价
  - EV 到股权价值的桥接（净债务、少数股东）
  - 亏损企业不套 PE；没有可支持的预测不做 DCF
  - 历史融资估值区分投前投后、轮次权利、时点
  - 并购：交易范围、营运资本调整、业绩承诺、回购、优先权、交割、整合成本；独立价值和协同分开，避免协同重复计入
  - 给区间、敏感变量、失效条件；券商目标价不是确定价值
  - 用当前价格反推隐含的增长、利润、现金要求
  - 具体投资方案：持有期、追加出资、稀释、分配顺序、退出；输入可靠才算 IRR/MOIC，并检验回报是否主要靠倍数扩张

**17 信用与履约**（M17-01 ~ 06，授信和供应商必需）
- 研究什么：谁付款或谁交付，承诺能否兑现。
- 要点：
  - 明确交易方向：客户信用风险和供应商履约风险分开
  - 现金、短债、历史付款、订单交付记录
  - 集团支持只按真实的法律或资金安排计入，不默认母公司兜底
  - 条件与风险匹配：客户侧缩短账期、增信；供应侧减少预付、验收后付款、里程碑、备选供应
  - 额度、比例、账期必须有输入依据，否则不编数字
  - 观察指标、违约和退出触发、需法务落实的条款
  - 按交易和期间计算实际暴露；检验缓释措施的启用速度是否早于风险发生

**18 上市主体、子公司与研报** → 见 D 节。

---

## D. 上市公司研报流程（模块 18）

**触发条件**（任意一条）：
1. 目标本身在交易所上市（含不同上市地或证券类别）
2. 目标是上市公司直接、间接或协议控制的子公司
3. 品牌、分支、业务单元能映射到上市主体或其控制企业

无论 Quick/Standard/Deep 都必须执行。四个子项：M18-01 映射与流程、M18-02 母公司支持和风险传导、M18-03 官方事实/公司指引/券商预测/本项目判断四者分开、M18-04 三个指针、相关章节、利益披露、缺口。

**实体映射必须记录**：目标法定名、注册号、业务名、曾用名；上市主体、交易所、代码、类别；控制链、比例、依据、证据、生效日；基准日是否仍受控（是否处于拟收购、已出售、分拆、重组、出表）。

**必读类别**（机器枚举 `category`）：
| 枚举 | 含义 | 何时必需 |
|---|---|---|
| `official_annual` | 最新年报 | 总是 |
| `official_interim` | 最新中期/季度报告 | 总是；只有它可以在制度不适用或尚无该期时，用 `category_exemptions`（reason + evidence_ids）豁免 |
| `company_update` | 最新公司跟踪、业绩点评、事件点评；子公司没有单独覆盖时找母公司的 | 总是 |
| `company_deep` | 最新深度、首次覆盖、业务专题 | 总是 |
| `industry` | 最新细分行业报告 | 总是 |
| `official_event`、`event_update` | 重大事件公告及更正、事件后研究 | 存在事件时 |
| `peer` | 可比/上下游研究 | `peer_required=true` 时 |

- 券商研报和官方披露都必须在研究设计中出现，不能互相替代。
- "公司报告"要区分三种分别登记：券商公司研报、公司自己发的年报公告、评级机构信用报告。
- 每个会改变决策的核心业务，尽量覆盖两家独立机构以识别分歧；只有一家时记录限制。这不是硬配额，只有一家不阻止 gate 完成。

**"最新"的定义**：
- 从 as_of 往前，按类别分别排序。
- 公司跟踪和事件研究按 90 天 → 180 天 → 12 个月 → 更早的顺序找；深度和行业框架可以回溯更久，但要标注历史用途。窗口只是检索顺序，不是合格线。
- 报告日期早于最近重大事件时，必须补查事件后的报告；没找到就记"未发现覆盖该事件的报告"，用官方资料自行补充分析，并保留缺口。
- 首发日、修订日、平台收录日、上传日、访问日分开；不能按上传日把旧报告当新报告。
- 报告内的数据截止日、预测期、估值基准日分别记录。
- 同名同日不同版本，用 `supersedes_id` 标明替代关系（替代方必须同机构、同覆盖主体、日期不早于被替代方）。
- 交付前复查一次，记录 `last_refresh_at`。
- 只能说"截至某日在列明渠道中发现的最新报告"。

**检索与获取**：
- 渠道优先级：原始机构 → 用户授权终端 → 合法公开平台。
- 关键词组合：名称/简称/代码 + 深度/首次覆盖/点评；母公司 + 子公司/品牌/分部；细分行业 + 深度/供需/价格；重大事件 + 名称 + 研报；海外加英文词（equity research、initiation、earnings update、sector report、industry outlook）；配合 site: 和 filetype:pdf，使用真实年份。
- 步骤：
  1. 建候选目录，按相关性、时间、事件覆盖、原始性、独立性挑选
  2. 打开原页核对标题、机构、作者、日期、证券、页数
  3. 有权限才保存原文件和校验值
  4. 阅读全文、图表、脚注、假设、风险提示、利益披露
  5. 拿不到全文时尝试公开版、原机构页、授权渠道或请用户提供，并记录尝试
  6. 旧全文只能作补充

**两套状态**：
- 获取状态 `access`：full_text / partial_text / abstract_only / metadata_only / access_blocked / unreadable。覆盖表中的"not_found"不对应任何实际报告。
- 阅读状态 `reading`：unread / partial / analyzed。只有 full_text 才能标 analyzed。
- 没找到报告时只建覆盖行和缺口，不创建报告记录。

**每份报告要提取**：身份信息、数据截止日、预测期、估值日、核心结论和假设、业务拆分、预测及与前次的变动原因、估值方法、目标价和评级（仅报告实际提供时）、风险、利益冲突、子公司相关段落及适用范围、哪些被官方支持哪些是券商估计、对本项目结论的影响。正文引用时写成"某机构某日基于某假设预计"。

**子公司专项核验**：控制和合并范围、子公司对集团的收入/利润/资产贡献、内部交易抵销、资金归集、担保、商誉和业绩承诺、剥离计划、资质和合同归属、分离后能否独立经营。

**研报观点比较表**：机构、日期、实际/预测口径、假设、分歧、支持和反对证据、采信理由。同一公告的数字被多家引用，仍只算一个事实来源。不平均不同口径的数字。历史预测误差只在数据足够时评估。

**research_gate 的含义与规则**：
- 它只表示资料覆盖，不代表研究范围是否完成。
- 每个类别的覆盖状态（`coverage_state`）：
  - complete 需同时满足：
    - 截至基准日最新那一日的所有候选报告（去掉被替代版本）都是 full_text、analyzed、relevance=direct
    - 事件类类别覆盖了所有事件日期
    - `search_status=found`，且有 search_ids 和 latestness_checked_at
    - `event_coverage` 为 covered 或 not_applicable
    - 关联缺口已关闭
  - 有任一份已读全文 → partial；否则 incomplete。
- 整体 gate：
  - 无必需项：主体或控制链待定为 incomplete，否则 not_applicable
  - 全部类别 complete、主体链已确认、且 `network=online` → complete
  - 有任一 complete 或 partial → partial
  - 否则 incomplete
- 硬规则：
  - 已知有更新的相关报告但没拿到或没读，不能标完成
  - 不能以"旧报告够用"为由豁免
  - 因相关性不足排除必须写理由（`relevance=excluded` + exclusion_reason），不能只因难拿到就排除
  - 未完成的类别必须挂一个开放缺口
  - 没有研报覆盖时，也不能写"已完成最新研报研究"
  - 资料不足时仍交付结果，首页说明限制、列出报告名、机构、日期、障碍、补齐路径
  - 缺研报不代表公司风险高

---

## E. 目的手册

**共同骨架**（所有目的都复用）：
- 公司与演变：边界、起源、转折、战略选择、组织
- 业务与经济机制：产品、使用者/决策者/付款人、获客、交付、收费、成本、利润、现金
- 外部位置：市场边界、产业链、供需、替代选择、优势的形成和持续条件
- 经营结果与约束：分业务线表现、财务质量、依赖、增长条件、风险和未知

**模块使用规则**：01–12 是主要素材；13–15 按重大性扫描后展开；16 只在需要估值或交易时用；17 只在信用或履约相关时用；18 按上市关系触发。

| purpose | 关注重点与增量问题 | 重点模块 | 优先证据与边界 | 默认评分权重（总 100）/ 关键维度 |
|---|---|---|---|---|
| company_research | 全面理解公司、解释经营机制和变化，不默认作投资、交易或授信判断 | 01–12 | 不评分，用分项理解、关键未知和置信度表达 | 禁止评分 |
| investment | 增长和回报靠什么；价格要求兑现什么；失败会损失什么 | 05/07/12/15/16 | 经营财务驱动、资本需求、价格与权利、可比；给成立和推翻条件，输入不足不强行量化 | business20 growth20 governance10 financial20 compliance10 technology10 operations5 deal5；关键：business、financial、compliance |
| acquisition | 买到什么权利和业务、隐含负担、协同整合能否实现 | 01/02/09/10/12/13/16 | 权属合同、净债务和营运资本、控制变更；独立价值和协同分开；形成交割条件 | 15/10/10/25/10/5/10/15；关键：financial、compliance、deal |
| partnership | 资源是否互补，双方怎样交付、分利、担责 | 03/09/10/11/13/17 | 合作合同、IP/数据许可、交付记录；给里程碑、责任、退出；默认不估值 | 20/5/10/15/15/15/20/0；关键：business、operations、compliance |
| credit | 付款方能否按期偿付，增信能否执行 | 09/12/13/15/17 | 现金、到期债务、付款验收、担保；按承担主体和时间匹配；不强定额度或账期 | 10/0/10/40/20/0/15/5；关键：financial、compliance |
| supplier | 供应是否连续，质量和预付款是否可控 | 09/10/11/12/13/17 | 产能、质量、交付、许可、备援、现金；形成验收付款、替代供应、退出条件 | 10/0/10/20/15/10/35/0；关键：operations、financial、compliance |
| competitor | 客户为何选它、相对优势如何变化、什么可能改变竞争 | 03/04/05/07/09/11 | 同场景的产品、价格、渠道、客户、跨期表现；不转成交易或信用审批 | 25/20/5/15/5/20/10/0；关键：business、technology |

（权重列顺序：business / growth / governance / financial / compliance / technology / operations / deal）

每个目的在每个维度上都有评价主题（criteria），例如投资的 deal 维度是"估值和下行保护"，授信的 operations 维度是"验收和历史回款"。评分框架还给出了确定"不可缺维度"时的优先考虑，例如：投资方面增长驱动价值时 growth 不可缺；评价具体价格时 deal 不可缺。

**深度差异**：
- Quick：简要画像、关键变化、重大风险和未知；只取基础原件，看显著反证；没展开的主题记"未开展"，不能改成不适用。
- Standard：对 18 个模块全部判断适用性；重点业务展开；关键声明交叉验证；评估剩余缺口。
- Deep：沿关键问题加历史跨度和粒度，做对照、情景、抽样、敏感性；只用公开资料也可以做 Deep，但不能声称做过内部核查。
- 三种深度都保留实体、时间、重大风险和研报要求。搜索次数和篇幅不代表深度。

---

## F. 来源清单

### F1. 中国大陆、香港、澳门（构建核验日 2026-10-20；各条注明了实际访问结果）
| 类别 | 平台 / 机构 | 适用资料 | 局限 | 原件核验状态 |
|---|---|---|---|---|
| 登记 | 国家企业信用信息公示系统 gsxt.gov.cn | 登记、年报、异常 | 申报不等于核验，不含完整受益所有权 | 访问返回 403 |
| 信用 | 信用中国、地方市场监管 | 行政公示 | 不等于完整征信 | 未核验 |
| 聚合 | 企查查、天眼查、启信宝、爱企查 | 工商、司法、股权线索 | 滞后、同名、付费；必须回溯原件 | 未核验 |
| 司法 | 中国裁判文书网、中国执行信息公开网、法院公告及地方法院 | 案件、执行 | 不公开、撤下、仲裁保密 | 未核验 |
| 交易所 | 上交所 sse.com.cn | 定期报告、公告 | — | 首页已读 |
| 交易所 | 深交所 szse.cn | 定期报告、公告 | — | 访问失败 |
| 交易所/监管 | 北交所、全国股转系统、证监会 | 公告、招股书、问询、挂牌 | 挂牌不等于上市 | 未核验 |
| 披露 | 巨潮资讯 cninfo.com.cn | 法定披露原件 | — | 访问超时 |
| 披露 | 港交所披露易 hkexnews.hk | 发行人公告 | 仅验证首页导航 | 首页导航已读 |
| 债务 | 债券披露平台、募集说明书、评级机构 | 债务条款、担保、评级 | 评级是观点，注意发行人付费关系 | 未核验 |
| 主管机关 | 税务、市场监管、生态环境、海关、网信、工信 | 处罚、许可、政策 | 纳税资料不公开，不能用信用等级推收入 | 未核验 |
| 知识产权 | 国家知识产权局 cnipa.gov.cn | 专利、商标 | — | 首页已读 |
| 许可认证 | 版权、行业许可证、认证查询 | 主体、范围、有效期 | 证书图片需核真 | 未核验 |
| 采购 | 中国政府采购网 ccgp.gov.cn | 采购公告和结果 | 中标不等于收入或回款 | 首页已读 |
| 采购 | 招标投标公共服务、地方公共资源交易 | 招投标线索 | 公告、结果、合同、履约要分开 | 未核验 |
| 研报 | 券商研究所、Wind、Choice、iFinD | 研究和数据 | 需授权，技能未接入 | 未核验 |
| 研报平台 | 东方财富研报、慧博、萝卜投研、发现报告 | 研报发现和摘要 | 上传日不是发布日，转载不等于合法全文 | 未核验 |
| 统计 | 统计机关、行业协会、研究机构 | 原始统计 | 协会样本可能不覆盖总体 | 未核验 |
| 融资 | 企业/投资方公告、IT桔子、投中、清科 | 融资并购线索 | 宣布、签约、完成、变更、到账不同 | 未核验 |
| 经营线索 | 招聘、应用商店、流量、GitHub | 产品、技术线索 | 流量不是收入，招聘不是员工数 | 未核验 |
| 舆情 | 媒体、投诉、社交、员工评价 | 争议线索 | 偏差大，不能凭单条定性 | 未核验 |
| 港澳登记 | 香港公司注册处、澳门商业登记 | 法定主体 | 部分付费；港交所公告不等于公司登记 | 未核验 |

### F2. 海外
| 类别 | 平台 | 核验状态 |
|---|---|---|
| 证券披露 | SEC EDGAR（10-K/10-Q/8-K、20-F/6-K、S-1/F-1） | 检索说明已读 |
| 公司登记 | 美国各州公司注册及当地注册处 | 未核验 |
| 公司登记 | Companies House（英国） | 检索页已读 |
| 公司登记 | ACRA（新加坡） | 服务入口已读 |
| 司法 | PACER 及当地法院 | 未核验 |
| 司法 | CourtListener（Free Law Project） | 访问失败 |
| 制裁 | 各辖区官方制裁和出口管制系统（聚合命中只是线索） | 未核验 |
| 知识产权 | USPTO、EPO | 未核验 |
| 知识产权 | WIPO | 返回空正文 |
| 知识产权 | Google Patents（需回原机关确认） | 未核验 |
| 融资数据库 | Crunchbase、PitchBook、CB Insights、Dealroom（不等于到账证明） | 未接入 |
| 金融终端 | Bloomberg、LSEG、S&P Capital IQ、FactSet、券商原始渠道 | 未接入 |
| 统计 | 官方统计、World Bank、OECD、行业协会 | 未核验 |
| 行业研究 | Gartner、IDC、Forrester（摘要不等于全文，不同口径不能相加） | 未接入 |
| 人员 | LinkedIn、Glassdoor、Indeed | 未核验 |
| 产品与流量 | Similarweb、Sensor Tower、GitHub、G2/Capterra | 未核验 |
| 媒体 | Reuters、Bloomberg、FT、WSJ（付费；不能只凭媒体品牌采信） | 未核验 |

每个来源条目都按以下字段写：运营方、地域、适用事实、入口/查询方式/更新频率、权限费用和局限、回溯原件、最后核验。每个项目启动时重新核验；不虚构深层 URL。

### F3. 来源策略
- 顺序：官方/授权原件 → 专业研究和方法透明的统计 → 有归属的媒体和自述 → 匿名线索。
- 用户提供的合同或审计报表按真实性评级，不统一降级为宣传。
- 关键词按主体/别名、业务场景、问题、地域语言、来源、时间组合，不机械展开全部组合；正证、反证、澄清、当前状态一起查；名称无结果时换别名和权威路径。
- 各类资料更新机制不同，不设统一有效期。
- 工具或访问失败时记录：渠道、时间、查询、错误、已试的替代、剩余限制。

### F4. 官网基础阅读（所有目标的共同任务，不因模块裁剪而消失）
- 先确认官网归属：依据可以是用户提供的入口、登记披露的链接、App 发行方信息、可靠的双向关联；不能凭同名、搜索排名或站点自称确认，也不猜域名或 /about 路径。
- 确认后逐项判断 8 类页面是否存在、可否读取：about、products_pricing、founders_team、history_news、locations_channels、investor_relations、terms_identity、visual_assets。
- 每页记录：实际 URL、标题、真实性及依据、发布日、信息适用期、访问日、可访问程度、定位。动态内容或付费内容如实标注；离线时只分析已有存档。

### F5. 真实视觉素材
- 记录来源页、原图地址、权利人或授权依据、允许的用途、素材日期、对象和地区、署名、裁切范围。
- 公开可见不等于可以随意复制再发布。不能生成假 Logo、人物、产品或门店图。

### F6. 研报获取方法（broker-research-guide）
- 用证券、母公司、子公司/品牌/分部、真实细分行业构造检索。
- 先核原始机构、作者、日期、版本、证券、URL。
- 读全文的相关部分，摘要不能标 analyzed。
- 逐类别写相关性；比较预测、口径、假设、估值、风险。
- 子公司要定位母公司研报中的目标段落。
- 拿不到新报告时建开放缺口；完全没有报告时不建假报告 ID。
- 事件后补查。
- 观点比较笔记的字段：机构/报告 ID、日期、目标范围、actual/forecast/estimate、预测期、币种单位、假设、与上版变动、支持和反对证据、利益披露、采信与不采信理由、对结论影响。
- 把机构观点拆成可验证的假设，与独立证据比对；"多家结论一致"不等于假设成立。
- 一般公司研究不强制给目标价或评级。

### F7. 访谈方法
- 问题围绕关键问题和能区分解释的开放缺口；不为凑人数而访谈；默认只交提纲。
- 六类角色各自能回答的问题和交叉验证方式：
  - 创始人/管理层：战略为何这样选、怎么执行、哪些结果偏离预期；用决议、预算与实际差异验证，自述需要其他角色佐证
  - 财务：收入到回款的差异、受限资金、到期债务安排；用明细账、附注、授权银行税务资料验证
  - 客户：选择、续用、拒绝、流失的原因，试点转付费、验收、替代品；覆盖新老客户、流失和未成交样本
  - 供应商：需求预测、结算、质量、产能替代记录
  - 前员工：只问其任职期间和职责范围内的事；不要求其带出保密文件
  - 行业专家：市场口径和关键假设是否成立、可能推翻判断的反例；注意利益关系
- 抽样：说明总体、观察期、名单来源和选样方，检查管理层筛选、幸存者偏差、不回应偏差。不设固定人数或机械的正反配额。
- 每次访谈记录：planned/completed、日期、角色类别、知情范围、利益关系、匿名约定、获准保存范围、问题、要点、与其他证据的一致性、后续核验。
- 模板 interview-outline.md：
  - 头部：对应的 claim_id/gap_id、角色、目的、样本来源、总体、需补的异常样本
  - 三个通用问题：在您负责的主体和期间内的事实及可分享依据；与已有证据的差异来自范围、时间还是业务变化；哪些可观察事实能区分两种解释
  - 状态表默认 planned、"尚未访谈"

### F8. 资料请求清单模板（request-list.md）
- 列：优先级、文件/字段、主体与期间、用途/关联缺口、可接受替代、敏感性与权限、责任角色/完成标准。
- P0：工商/章程/股权原件；财报、附注、债务担保、受限资金；最新研报全文及授权。
- P1：客户供应商合同、订单验收回款及流失线索；融资治理、诉讼、重要合同；人员、技术/IP/数据许可、运营交付；子公司与集团往来、抵销、资金归集。
- P2：非关键补充。
- 发送需用户授权。

---

## G. 数据契约与模板

### G1. 编码规则（data-contract.json, version 1.0.0）
- CSV：UTF-8、逗号分隔、表头顺序固定；空单元格为 null，0 不是 null。
- list/ids/dates：JSON 数组字符串，元素为非空字符串且不能重复；object：JSON 对象字符串。
- bool 只能是小写 true/false。
- date 为 YYYY-MM-DD；datetime 为带时区的 ISO 8601。
- number 为有限数，禁止 bool、NaN、Infinity。
- 拒绝未知列和未知字段。
- ID 前缀至少四位数字：ENT- / REL- / Q- / S- / E- / C- / CE- / R- / RC- / F- / G- / K- / SC-。
- module 字段只能是 "01"–"18"。
- 通用日期顺序检查：period_start≤period_end、effective_from≤effective_to、listing_start≤listing_end、published_date≤revised_date。

### G2. 全部枚举
- purpose：company_research / investment / acquisition / partnership / credit / supplier / competitor
- depth：Quick / Standard / Deep
- label：七类中文标签
- confidence：high / medium / low / unknown
- access：full_text / partial_text / abstract_only / metadata_only / access_blocked / unreadable
- reading：unread / partial / analyzed
- gate：complete / partial / incomplete / not_applicable
- attribute：actual / forecast / estimate / opinion / not_applicable
- category：official_annual / official_interim / official_event / company_update / company_deep / industry / event_update / peer
- gap_reason：not_disclosed / not_found / access_restricted / unreadable / not_executed / not_applicable
- materiality：critical / major / minor
- scope：consolidated / standalone / segment / brand / not_applicable
- listing：listed / unlisted / otc / bond_only / proposed / delisted / unknown
- relation：control / joint_control / significant_influence / minority / brand_of / branch_of / other
- search_status：not_executed / found / not_found / access_blocked / failed
- dimension：business / growth / governance / financial / compliance / technology / operations / deal
- gap_disposition：non_blocking / limits_conclusion / blocks_completion
- 表内枚举：
  - entity_type：legal_entity / group / segment / brand / branch
  - identity_status：pending / resolved / ambiguous
  - relations.state：current / historical / proposed；relations.verification：pending / verified
  - source_type：official / broker / rating / database / company / media / interview / other
  - grade：S / A / B / C / D
  - authenticity：checked / pending / uncertain
  - time_scope：as_of / retrospective
  - claim.verification：pending / verified / disputed / unsupported / refuted
  - claim-evidence.relation：supports / contradicts / context
  - research.relevance：direct / limited / excluded
  - coverage.event_coverage：pending / covered / lagging / not_applicable
  - conflict.status：open / resolved
  - gap.priority：P0 / P1 / P2；gap.status：open / closed
  - risk.status：confirmed / lead / exposure / information_gap；risk.severity：escalate / major / ordinary
  - scorecard.applicability：applicable / not_applicable；scorecard.coverage_status：sufficient / missing
- research 配置：
  - base_categories：official_annual、official_interim、company_update、company_deep、industry
  - event_categories：official_event、event_update；peer_category：peer
  - control_relations：control、brand_of、branch_of
  - 各类别中文名、gate 状态中文名
- scoring：minimum_coverage 0.8（注明只是内部管理门槛）；各目的的 weights、critical_dimensions、criteria；1–5 分量尺定义。
- semantic_rules：6 条（访问完整度不等于真实性；集团数据用于子公司需桥接并标推断；获取和阅读分别记录；同源组只用于判断独立性；历史研究隔离事后资料；not_found 不创建报告）。
- purpose_labels：各目的的中文名。

### G3. 13 张 CSV 的列（* 表示必填，→ 表示引用的表；条件必填单列）
1. **entity-map**：entity_id*、legal_name*、registration_id、aliases(list)、geography、entity_type*、identity_status*、listing_status*、exchange、security_code、security_class、listing_start、listing_end、evidence_ids(→evidence)、identity_notes。条件：resolved 时必须有 registration_id 和 evidence_ids；listed 时必须有 exchange 和 security_code。
2. **entity-relations**：relation_id*、parent_id*→entity、child_id*→entity、relation_type*、ownership_percent(0–100)、control_basis*、effective_from*、effective_to、state*、verification*、evidence_ids。条件：verified 时必须有证据。
3. **search-log**：search_id*、searched_at*(datetime)、channel*、query*、entity_id*、period_start、period_end、purpose*(string)、status*(search_status)、source_ids→source、limitations。
4. **source-register**：source_id*、title*、source_type*、publisher*、author、published_date*、revised_date、accessed_date*、locator*、grade*、grade_reason、origin_group*、upstream_source_id→source、access_status*、authenticity*、authorization*、time_scope*、checksum。
5. **evidence-ledger**：evidence_id*、source_id*、entity_id*、module*、locator*、excerpt*、period_start、period_end、geography、currency、unit、accounting_basis、scope*、attribute*、numeric*(bool)、value(number)、limitations。条件：numeric=true 时 period_start、period_end、geography、currency、unit、accounting_basis、value 全部必填。
6. **claim-register**：claim_id*、statement*、label*、entity_id*、module*、materiality*、verification*、confidence*、attribute*、numeric*、scope*、assumptions、counterevidence、unresolved。条件：【推断】或【判断】必须有 assumptions；refuted 必须有 counterevidence。
7. **claim-evidence**：link_id*、claim_id*、evidence_id*、relation*、applicable_scope*、bridge、limitations。
8. **research-register**（33 列）：research_id*、source_id*、publisher*、author、title*、categories*(list of category)、category_relevance*(object)、target_id*、coverage_entity_id*、security_code、report_date*、version*、supersedes_id→research、data_cutoff、forecast_periods(list)、valuation_date、access_status*、reading_status*、relevant_sections、interests、key_views、assumptions、forecast_changes、valuation、risks、decision_impact、event_dates(dates)、relevance*、exclusion_reason、limitations、latest_discovered_for / latest_fulltext_for / latest_read_for（覆盖 ID 数组）。条件：analyzed 时 relevant_sections、interests、key_views、assumptions、risks、decision_impact 必填；excluded 时必须有 exclusion_reason。
9. **research-coverage**（17 列）：coverage_id*、target_id*、research_entity_id*、category*、required*(bool)、reason*、search_status*、search_ids→search-log、latest_discovered_id / latest_fulltext_id / latest_read_id →research、latestness_checked_at(datetime)、event_dates、event_coverage*、gate_status*、gap_id→gap、limitations。
10. **conflict-register**：conflict_id*、claim_ids*、evidence_ids*、left_value_scope*、right_value_scope*、analysis*、status*、accepted_reason、decision_changing*(bool)、decision_impact*。条件：resolved 时必须有 accepted_reason。
11. **gap-register**：gap_id*、needed*、module*、entity_id*、reason*(gap_reason)、materiality*、affected_claims→claim、acquisition_path*、priority*、owner_role*、status*、resolution。条件：closed 时必须有 resolution。
12. **risk-register**：risk_id*、description*、entity_id*、status*、severity*、evidence_ids、impact*、likelihood*、time_horizon*、alternative_explanations*、mitigation*、residual_risk*、closure_condition*、owner_role*。条件：confirmed 时必须有证据。
13. **scorecard**：score_id*、purpose*、dimension*、weight*(≥0)、applicability*、score(1–5)、anchor、evidence_ids、confidence*、coverage_status*、reason。条件：not_applicable 时必须有 reason；sufficient 时 score、anchor、evidence_ids 必填。

### G4. project-config.json 字段
contract_version("1.0.0")、target、target_id("ENT-0001")、purpose、purpose_status、depth、geography、focus、materials[]、as_of_date、timezone("Asia/Shanghai")、historical、constraints{network(unknown/online/offline)、budget、deadline、permissions}、identity_status、listing_trigger(pending/triggered/not_triggered)、control_chain_checked、control_evidence_ids[]、industry_keywords[]、languages(["zh","en"])、events[{date、entity_id、description}]（日期不能晚于 as_of）、peer_required、category_exemptions[{entity_id、category、reason、evidence_ids}]、scoring_threshold(0.8，取值 0–1)、scoring_override(null 或 {reason、weights（全部 8 维）、critical_dimensions})、report_status(draft/limited/complete)、research_gate、declared_complete、published_score、version、confidentiality、module_scope{"01".."18":{status:pending/applicable/not_applicable、reason}}、last_refresh_at、completed_actions[{action、status:completed/planned、evidence_ids、output_locator}]、scoring_enabled、completion_review(null 或 {scope、key_claim_ids[C-…]、gap_assessments[{gap_id、impact、disposition}]、reviewed_at})。
- 配置字段集合必须和模板完全一致。旧配置读取时只补 scoring_enabled 和 completion_review 两个默认值，不写回文件。

### G5. financial-input.json
- 字段：synthetic、entity_id、scope、period_start/end、days、currency、unit、accounting_basis、attribute、audited、source_ids、values{}、input_evidence{字段→[E-]}、prior(同结构或 null)。
- options：allow_end_balance、allow_revenue_proxy、allow_cost_proxy、quick_deductions["inventory","prepayments"]、near_zero_profit 0.01、capex_sign positive_outflow/negative_outflow。
- cash_burn_basis：basis、cash_excludes_restricted、includes_capex、includes_debt_service、includes_committed_spend、limitations。
- thresholds[{metric、operator(lt/gt)、value、scope、source}]。

### G6. report-content.json（version "1.2"）
- 顶层：version、title、subtitle、language(zh-CN/en)、summary、scope_note、sections[]（全部必填，不允许额外字段）。
- 所有 text 必须非空、非纯空白、不含 `{{`/`}}`；文字里可以写 [E-xxxx] 引用。
- section：
  - id：小写字母开头，只含小写字母、数字、连字符，全文唯一
  - 禁用保留 ID：main、overview、sources、evidence、report-data、toc-toggle；禁用前缀 chart-、ref-、topic-
  - 标题不能是过程性标题（检索日志、模块适用、研究完成范围、评分覆盖、完整声明核验、访谈提纲、资料请求清单、research coverage、search log）
  - 字段：title、可选 summary、blocks[]

**13 种 block**：
1. `text{text}`
2. `bullets{items[]}`
3. `callout{title,text}`
4. `table{title,columns,rows,note}`：行列等长，单元格非空
5. `metrics{items[{label,value,unit,period,entity_id,kind,evidence_ids,note}]}`：kind 不能为 mixed
6. `chart{chart_type,title,unit,period,entity_id,kind,evidence_ids,note,points,[scale_max]}`
7. `timeline{title,items[{title,text,evidence_ids,date,status:completed/planned}],purpose?}`
8. `process{title,items[{title,text,evidence_ids,basis?}],purpose?,ordering?}`
9. `people{title,profiles[{name,role,period,background,contribution,limitations,evidence_ids}]}`
10. `image{role,path,title,alt,caption,source_url,captured_at,usage_note,evidence_ids}`
11. `matrix{title,columns(≥2),rows[{label,cells[{text,basis,evidence_ids}]}],note,purpose?}`
12. `diagram{title,purpose,period,entity_id,note,nodes(2–6),edges(1–10)}`
13. `explanation{topic,title,text,status,evidence_ids,limitations}`

**11 个 explanation 主题**（全文各出现一次，可以放在任意章节）：
| topic | 读者应能回答的问题 |
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

**explanation 字段规则**：
- status 取 supported / partial / unknown
- supported 和 partial 至少有 1 个证据；partial 和 unknown 的 limitations 必须非空且具体
- supported 的 limitations 可以为空；unknown 可以没有证据
- status 只供检查用，不在正文显示，不代表事实认证；公司自述不能用 supported 暗示已独立核验

**各类 purpose 枚举**：
- process.purpose：business_model / recommendation / other
- timeline.purpose：company_history / other
- diagram.purpose：business_model / ownership / marketing / other
- matrix.purpose：competition / marketing / financial / other
- 只有 business_model 的 process 或 diagram 才满足"业务机制图"要求。
- process.ordering：sequence（默认，带箭头和编号，只在顺序有依据时用）/ conceptual（无箭头无编号，只表示关联）。模板默认 conceptual。

**basis 枚举**（process、matrix、diagram 的节点和边共用）：evidence / company_claim / inference / unknown。只有 unknown 可以没有引用。渲染显示为"资料支持 / 公司口径 / 分析示意 / 待核实"。

**数据属性 kind**：actual / estimate / forecast / company_claim；图级还可以用 mixed，此时每个点或分项必须自带 kind；图级 kind 不是 mixed 时，点上的 kind 必须与图级一致。

**chart_type 共 8 种**：bar（横向）、line、donut、column、proportion、range、waterfall、stacked_bar。各自约束：
- bar / line / column：至少 2 点、至少 2 个已知值、最多 24 点；允许 null；column 允许负值
- donut：2–6 项，不能缺失或为负，总和大于 0
- range：每点 low/high 要么都为 null 要么都为数，low≤high，至少 1 组已知；不画中点
- proportion：必须有 scale_max>0；单位含 %、％ 或"百分比"时 scale_max 必须为 100；值在 0 到 scale_max 之间；最多 8 点；至少 1 个已知值；只有 proportion 允许带 scale_max
- waterfall：2–12 点；每点 role 为 start/delta/total；首点 start、末点 total、中间不能再有 start；total 必须等于累计值（误差 1e-9，用高精度 Decimal 计算）；增减带符号
- stacked_bar：2–8 组，每组 2–6 个分项；各组分项标签和顺序一致；值非负、无缺失；全图最多 24 段；不自动归一化
- 所有图：点标签唯一；有 actual 属性的点不能引用 forecast 或 estimate 证据；entity_id 必须存在于实体表，或为 "industry"

**diagram 约束**：
- 节点：id 小写、唯一；label、text、basis、evidence_ids
- 边：source/target 必须是已有节点，不能自连接；flow 取 product / money / information / relationship；label 必填；不能有完全重复的边（同 source、target、flow、label）；不能有孤立节点
- inference 和 unknown 用虚线；线宽不表示数量

**image 约束**：
- role：logo / website / product / store / people / other
- path：项目内相对路径
- source_url：空串（本地材料）或安全的 http(s) URL（不带用户名密码）
- captured_at：YYYY-MM-DD，表示本次取得日期；晚于 as_of 时给警告

**跨块规则（运行时检查）**：
- 11 个主题齐全且不重复
- 若 transaction_flow 不是 unknown，至少要有 1 个 business_model 图
- 若有 company_history 时间线，必须和 identity 在同一章，且至少 2 个事件；没有这条时间线时，history_team 必须是 partial/unknown 且有限制说明（同时给警告）
- people 块不能和 identity 同章；缺 people 给警告；缺图片给警告；没有定量图给警告；全部主题都是 unknown 给警告
- 已完成的 company_history 事件不能引用 forecast 证据
- 1.0/1.1 版只能在 draft 模式下读取，并提示升级；新建 HTML 和 completed 模式只接受 1.2；people / image / matrix / diagram 和扩展图型只在 1.2 中可用

**模板骨架（templates/report-content.json）**：
- 12 章：company-profile（identity、company_history 时间线、website 图片、history_team）→ founders-team（people）→ products-customers（offering、产品-需求矩阵、customers_markets）→ business-model（transaction_flow、4 步 conceptual 业务流程、operating_model、revenue_costs）→ financial-performance（financial_performance、bar 图、可选 waterfall）→ marketing-growth（marketing、渠道矩阵）→ competitive-landscape（competition、竞争矩阵、differentiation）→ scale-growth / finance-fulfillment / material-risks / decision（四章为 text 占位）
- 所有值都是 `{{待填写…}}` 或 null，故意不能直接构建。

**visual-examples.json**：6 个可复制的单块配方，每个都写了要回答的问题、适用情形、禁用情形、编辑要点：
- horizontal-comparison（column）
- observed-ranges（range）
- profit-or-change-bridge（waterfall）
- comparable-composition（stacked_bar）
- known-percentage（proportion）
- business-and-relationship-map（diagram）

---

## H. 脚本行为（Python 3.10+，只用标准库，不联网）

通用约定：
- 退出码：0 成功或结构通过；1 校验或检查发现硬错误；2 参数、输入、文件、权限错误（错误以 JSON 输出到 stderr）。
- 写文件默认独占创建，不覆盖；显式覆盖时先写临时文件再原子替换。
- 输出 JSON 时禁止 NaN。

**common.py（共享核心）**
- `decode` / `record`：按契约逐字段解码；拒绝未知字段；检查必填（空数组、空对象也算缺）、条件必填、日期顺序。
- `read_table`：表头必须和契约完全一致；列数错误报错。
- `load_config`：校验 G4 的全部字段类型；contract_version 必须匹配；purpose 和 purpose_status 必须一致；company_research 不能启用评分；completion_review 的结构（key_claim_ids 非空、不重复、格式为 C-；gap_assessments 中 gap_id 不重复、impact 非空、disposition 合法；reviewed_at 带时区）；18 个模块都要有，标 not_applicable 必须写理由；event 必须有三个字段且日期不晚于 as_of。
- `structural_errors`：重复主键、引用不存在、target_id 或控制链证据或事件主体不存在。
- `listed_entities`：从 target 沿生效、已核实、非 proposed 的 control/brand_of/branch_of 边向上找；listing_start/end 要覆盖 as_of（delisted 需有起止日期）。遇到以下情况标 pending：主体身份不是 resolved、listing_status 为 unknown、存在未核实的生效边、控制链未勾选或没有控制证据。
- `project_events`：配置里的事件，加上台账中"已知官方披露日期晚于最新 company_update"时自动补一个事件。
- `requirements`：每个上市主体生成 5 个基础类别；只要项目有任意事件，就加两个事件类别；peer_required 时加 peer；official_interim 可按豁免剔除。
- `candidates`：同 target、同覆盖主体、包含该类别、不是 excluded、报告日不晚于 as_of、来源为 as_of 的报告；去掉被替代版本后按日期倒序。
- `coverage_state` / `research_gate`：规则见 D 节。
- `completion_errors`：
  - 必须有 completion_review，purpose 不能为空，主体链不能 pending
  - 每个 key claim：存在、verified、高或中置信、标签不是【缺口】或【待核实】、至少一条 supports 证据
  - 所有 critical 声明，要么列入 key claim，要么是"有效 refuted"
  - 没有会改变决策的开放冲突
  - review 中列的缺口必须是当前开放的缺口；每个开放缺口都要被评估；blocks_completion 或 critical 缺口直接阻断
  - 每个必需覆盖项都要有真实执行的检索记录（不能 not_executed）和 latestness_checked_at
  - 若 declared_complete=true：不能有开放缺口，所有动作都是 completed
- `semantic_errors`：
  - 来源：访问日早于发布或修订日；as_of 资料晚于截止日
  - 证据：来源不可读却形成证据；定量证据没有 scope；actual 证据的期间结束晚于截止日
  - 声明：【数据】但不是 actual；定量声明没有 scope；verified 但没有 supports 证据；refuted 不满足条件；主体未 resolved 却形成 verified/refuted 结论；用 retrospective 资料支持；actual 声明引用 forecast/estimate 证据；定量声明与证据的主体或范围不一致，又没有 bridge 加【推断】
  - 研报：与来源的 access_status 不一致；report_date 不等于来源的修订日或发布日；analyzed 但不是全文；category_relevance 的键和 categories 不一致或值为空；data_cutoff 晚于报告日；supersedes 关系不合理
  - 关系：自我控制；生效控制图有环
  - 豁免：只允许 official_interim，且必须有理由和真实证据
- `research_errors`：
  - 必读类别的覆盖行缺失或重复；强制类别被标为可选
  - latestness 复查时间早于已发现的最新报告
  - 三个 latest 指针必须指向同日期最新的适用报告，并与 research-register 中三个 *_for 数组双向一致
  - gate_status 与推导结果不一致；未完成的类别没有挂开放缺口
  - search_status 不是 not_executed 却没有 search_ids；引用的日志是 not_executed
  - 配置 research_gate=complete 但推导结果不是；declared_complete 但 gate 不是 complete 或 not_applicable
- `sync_coverage`：为缺失的必读类别新建 G-（P0、major、not_executed、owner 研究负责人）和 RC-（required、未检索、incomplete）；清空并重算三个指针（每类只指向排序第一的那份）；重算每行 gate_status；更新 listing_trigger 和 research_gate。不检索、不关闭缺口。
- `save_project`：先把现有文件全部快照到 `.ledger-backup-*` 临时目录，再逐个原子覆盖。不是事务。

**init_project.py**
- 参数：`--output`(必填，必须不存在)、`--target`(必填)、`--purpose`、`--enable-scoring`、`--depth`(默认 Standard)、`--as-of`、`--timezone`(Asia/Shanghai)、`--registration-id`、`--geography`、`--listing-status`(默认 unknown)、`--exchange`、`--security-code`。
- 行为：
  - 校验：目标非空、purpose 和 depth 合法；company_research 不能启用评分；时区不可用时报错并提示改用 UTC
  - historical = as_of 早于今天
  - 建 ENT-0001（pending，注明是用户输入的待核实身份）
  - 启用评分时按契约默认权重建 8 行 SC-（unknown、missing）
  - 执行一次 sync_coverage
  - 写 13 张 CSV 和配置；复制 financial-input、report-content、request-list、interview-outline 四个模板；建 materials、modules、reports 目录
- 输出 status、path、research_gate，并说明只做了初始化。

**evidence_ledger.py**
- `--project` 加子命令：
  - `add --input [--replace]`：输入为 {表名: [完整记录]}；同批次重复主键报错；已有主键需 --replace（整行替换，省略的字段变空）；写入前跑结构和语义检查；输出备份路径
  - `query --table [--field --value]`：字符串相等过滤
  - `export --output`：导出配置和全部表
  - `validate`：结构 + 语义 + 研报检查；有错误返回 1
  - `sync-coverage`：先检查结构和语义，再同步并保存

**search_plan.py**
- 参数：`--project`、`--output`。只输出计划，所有任务 status=not_executed，不写日志。
- 任务顺序：
  1. claim_verification：completion_review 里的 key claim 和所有 critical/major 声明。排序：选中的优先，其次 critical。优先级：critical 为 P0，否则 P1，再与关联缺口的优先级取最小。带上已有的 assumptions、counterevidence、unresolved、关联缺口的所需信息和获取路径。
  2. gap_resolution：未被声明关联的开放缺口，按优先级排序。
  3. 官网任务：1 个 official_site_identity（不依赖其他任务）加 8 个 official_site_page（依赖 identity），每个带 goal、record_fields 和完成标准。
  4. keyword_candidate：每个实体 × 每个别名（含证券代码）× 18 个模块中非 not_applicable 的模块 × 每种语言。每个模块有固定中文关键词和来源提示；英文语言追加英文后缀。
  5. 研报任务：每个必需类别 × 4 个窗口（90、180、365 天、不限）。查询串为"上市主体名 + 目标名 + 类别中文名 + 英文研报词 + filetype:pdf"。
  6. 行业词任务。
  7. 事件后点评任务。
- 输出：type=plan_only、listed_entities、network、tasks、stop_rule、warning。

**financial_ratios.py**（`--input`、`--output`）
- 输入校验：
  - 13 个口径字段必填
  - scope 只能是 consolidated/standalone/segment；attribute 只能是 actual/forecast/estimate
  - days 必须等于结束日减开始日加 1，且大于 0
  - values 只接受 25 个白名单字段：revenue、cost、net_profit、operating_cashflow、current_assets、current_liabilities、inventory、prepayments、assets_begin/end、equity_begin/end、receivables_begin/end、inventory_begin/end、payables_begin/end、credit_sales、purchases、capex、available_cash、monthly_net_burn、total_debt、total_assets
  - 每个非空值必须在 input_evidence 中有非空证据数组
  - 未知 option 报错；quick_deductions 只能是 inventory/prepayments 的非空不重复子集；near_zero_profit 不能为负
- 通用规则：
  - 输入缺失 → status=missing（不补 0）
  - 分母 ≤0 → not_applicable
  - 使用了期末余额或代理分母 → approximate
  - 每项输出 value、status、formula、inputs、evidence_ids、reason、attribute、applicability(scope)
  - 平均余额 = (期初+期末)/2；只有 allow_end_balance 时才允许用期末余额近似
- 比率与公式：
  1. gross_margin = (revenue − cost) / revenue
  2. net_margin = net_profit / revenue
  3. current_ratio = current_assets / current_liabilities
  4. quick_ratio = (current_assets − Σquick_deductions) / current_liabilities；任一扣除项缺失则整项缺失
  5. roa = net_profit / 平均总资产（不年化）
  6. roe = net_profit / 平均净资产（不年化）
  7. receivable_days = 平均应收 / credit_sales × days；缺 credit_sales 且 allow_revenue_proxy 时用 revenue（approximate）
  8. inventory_days = 平均存货 / cost × days
  9. payable_days = 平均应付 / purchases × days；缺 purchases 且 allow_cost_proxy 时用 cost
  10. cash_conversion_cycle = 应收天数 + 存货天数 − 应付天数；任一子项缺失则缺失；子项有近似则整项为 approximate
  11. cash_profit_ratio = operating_cashflow / net_profit；净利润 ≤ near_zero_profit（默认 0.01）时为 not_applicable
  12. simplified_fcf = operating_cashflow − |capex|（注明不是 FCFF/FCFE）；capex 的正负号必须与声明的 capex_sign 一致，否则报错
  13. cash_runway_months = available_cash / monthly_net_burn
      - available_cash 为负报错
      - cash_burn_basis 的四个布尔口径必须都明确
      - basis 为空，或未剔除受限现金 → missing
      - burn ≤0 → not_applicable（注明"当前未消耗不代表永久安全"）
      - 结果 attribute 改为 estimate
  14. revenue_growth = revenue / prior.revenue − 1。可比条件：主体、scope、币种、单位、会计口径都相同；天数差 ≤1；上期结束早于本期开始；起止日期的月日相同；两期都是 actual。不满足或上期收入 ≤0 时不计算。输出 prior_revenue 和上期证据。
- thresholds：metric 必须是已有指标，operator 为 lt/gt，scope 和 source 必填；触发时输出 alert，注明只是核查线索。
- total_debt 和 total_assets 只保留输入，不计算杠杆比率。

**scoring.py**（`--project`、`--output`）
- project_score 依次判断：
  - purpose 为 null → purpose_pending（此时 published_score 必须为空）
  - company_research → not_applicable（不能启用评分或发布分数）
  - 未启用 → disabled
  - 没有 override → criteria_pending
  - override 必须有非空 reason、完整 8 维 weights、非空不重复的 critical_dimensions
  - 评分行的 purpose 必须与项目一致；跑结构和语义检查；打了分的维度不能引用 retrospective 证据
- calculate：
  - 门槛在 0–1 之间；关键维度必须有权重；评分行维度不重复，且与 weights 的维度集合完全一致；每行 weight 必须等于 override 中的权重
  - 分数在 1–5；not_applicable 行必须有理由且不能打分
  - 打了分的行必须是 sufficient、有证据和锚点、置信度为高或中
  - 没打分的行必须写理由，且不能标 sufficient
  - 全部不适用 → not_applicable；适用权重和必须大于 0
  - coverage = Σ已评分权重 / Σ适用权重
  - partial_score = Σ(权重 × 分数) / Σ已评分权重
  - 发布条件：coverage + 1e-12 ≥ 门槛，且关键维度全部已评分，且没有会改变决策的开放冲突；此外存在 critical 开放缺口时强制不发布
  - 输出 status(complete/insufficient_evidence)、coverage、partial_score、overall_score、missing_critical、各维度归一化权重、critical_gaps、configuration_reason、research_gate、风险说明

**build_report.py / reader_report.py**
- 参数：`--project`、`--output`、`--content`、`--sections`、`--overwrite`。
- 输出为 `.md` 时走旧版底稿路径（不能同时带 --content）。
- 输出为 `.html` 时：必须有 content 且 version=1.2，不能带 sections；项目有结构或语义错误则拒绝；HTML 或 audit 已存在且未加 --overwrite 则拒绝；父目录必须存在。
- 生成顺序：先 render 并校验 → 跑 visual_review → 在临时目录生成 audit 并附上"逐章可视化编辑复核"表（列：章节、数据图、结构图、指标、图片/人物、提示）→ 写 audit → 写 HTML。
- 返回 chart_count、warnings、reader_coverage、visual_review、report_status、next。

**build_audit_report.py**（旧版 Markdown 底稿）
- 参数：`--project`、`--output`、`--sections`、`--overwrite`。sections 只允许 7 个键：summary、highlights、recommendation、research_comparison、data_bridge、judgment、next_steps，值为字符串。
- 按 depth 选模板：Quick 用 report-quick.md（10 节），其他用 report-full.md（20 节）。
- 填充内容：元信息、完成范围（gate、离线说明、completion_review 表、模块适用性表）、主体和关系表、覆盖表、评分摘要和评分表、声明和关联表、风险和冲突表、缺口表、请求清单和访谈提纲原文、证据和来源表、研报目录表、检索日志表、方法局限。
- 每个模块读 modules/NN-*.md；同一编号多于一个文件报错；不适用的写理由；缺文件的写【缺口】。
- 未替换的占位符改写为"【缺口：xxx 尚未填写】"。
- 枚举值显示为中文（DISPLAY 映射）。

**report_model.validate_content**：执行 G6 的全部规则。返回 used_evidence、chart_count、warnings，以及 reader_coverage（各主题的状态和所在章节、业务图数、时间线数、人物块数、图片数、矩阵数、关系图数）。

**report_html.render**
- 先 validate_content 和 validate_media。
- 所有作者输入都做 HTML 转义；只支持 `**粗体**` 和 `[E-xxxx]` 两种标记，后者转成指向 `#ref-E-xxxx` 的链接。
- 页面结构：
  - 顶栏：品牌、基准日、目录按钮、打印按钮
  - 侧栏目录：概览、各章节、来源与底稿
  - hero：eyebrow 显示目的、标题、副标题、基准日、状态标签（draft→草稿 / limited→"公开材料研究·结论有条件" / complete→研究报告）、summary、scope_note。gate 不是 complete 或 not_applicable 时，自动在 scope_note 后追加"最新相关研报尚未取得或读完"的提示
  - 各章节带 2 位编号
  - 证据附录（折叠）：只列正文实际用到的证据；来源 locator 是安全的 http(s) 时显示为链接；显示机构、日期、定位、限制
  - 底稿链接
- explanation 渲染为普通小标题加段落；正文未内联引用的证据补一行"来源"；有限制时显示限制段落。
- 每张图：figure 编号、结论标题、元信息（单位·期间·主体·属性）、内嵌 SVG（有 title 和 desc 便于无障碍）、note、来源行、可展开的数据表（项目、数值、单位、期间、属性、证据）。stacked_bar 和 waterfall 额外附免责说明。
- 关系图：编号徽章链接到下方的关系清单，有角色说明和逐条依据表，注明线宽不表示数量。
- conceptual 流程注明"排列不表示已核实的顺序"。
- 内容和项目快照（target_id、as_of_date、purpose、report_status）、audit 文件名、media 以 JSON 写入 `<script id="report-data">`，其中 < > & 转义为 unicode。
- CSS 和 JS 全部内联；`color-scheme: light`。

**report_charts.py**（SVG 绘制规则）
- bar：零基线，刻度取 1/2/2.5/3/5/10 × 10ⁿ 的整齐间隔；null 显示"未披露"；forecast 用淡色加虚线边框并标"预测"；标签按全角宽度换行。
- line：null 处断线；连接 forecast 的线段用虚线，forecast 点为空心。
- donut：标签显示数值和占比，中心显示总量。
- column：宽度随点数增加；保留正负和零线；刻度取 4 位有效数字。
- waterfall：delta 正值为绿、负值为红，start/total 为蓝；相邻柱之间有虚线连接；标注角色。
- stacked：顶部图例；每行显示合计和分项摘要。
- range：只画上下界的线段和端点；不画中点。
- proportion：灰色轨道加蓝色填充，注明灰色只是量尺。
- diagram：2 个节点左右排列，3–6 个节点环形排列；同一对节点的多条边用曲线错开；箭头颜色按 flow 区分（产品蓝、资金绿、信息紫、关系灰）；inference/unknown 的节点和边用虚线；编号徽章沿曲线避开节点和其他徽章；节点标签最多 3 行；底部有图例并注明布局不表示层级或顺序。
- chart_rows：数据表只放原始值，不放中点或推算出的互补值。

**report_media.py**
- 收集所有 image 的 path。path 必须是相对路径：不能为绝对路径或带盘符，不能含 `..`，不能含空字符。
- 解析后的真实路径必须在项目目录内（防止符号链接逃逸），且必须是普通文件。
- 单个文件 ≤5 MiB，总计 ≤15 MiB（读取时多读 1 字节，防止检查后文件变大）。
- 按文件头识别类型：PNG、JPEG、WebP（RIFF…WEBP）；其他类型（含 SVG）拒绝。
- 生成 {mime、base64 数据、sha256}。
- validate_media：媒体包的路径必须与正文完全一致；只能有三个字段；Base64 必须是规范编码；MIME 和 sha256 必须与内容一致。

**check_report.py**（`--project`、`--report`、`--mode template|draft|completed`、`--output`）
- template 模式：只要求提供 report，允许占位符。
- 其他模式：
  - 结构 → 语义 → 研报检查
  - HTML 报告调用 inspect_html
  - 评分：published_score 必须等于计算出的 overall_score（误差 1e-8）
  - 配置的 identity_status 必须与实体表一致
- "完成态"在以下任一条件下触发：mode=completed、report_status=complete、declared_complete=true。完成态额外要求：
  - completion_errors 全部通过
  - 必须提供报告文件
  - identity resolved；没有 pending 的模块
  - 有 last_refresh_at
  - 不残留占位符、"尚未填写】"、"未提供模块分析"等文字
  - HTML 报告时，每个 applicable 模块都有唯一的非空 modules 文件
- completed_actions：每项要有 action 和 status；completed 的项必须有证据或 output_locator；证据必须存在。
- 报告中每个 [E-…] 必须存在，格式必须是 E-加至少 4 位数字。
- Markdown 底稿必须有 7 个结构章节：元信息、执行摘要、研究完成范围、研报覆盖、信息缺口、下一步、证据附录。
- gate 未完成时，正文出现"研报…：已完成"之类的行报错；正文写了"综合评分：数字"但没有可发布分数报错。
- Markdown 中含数字但无引用的行给警告；以下情况豁免：标题、表格、代码、列表、引用块，以及以日期/基准日/版本/公式/方法/时区/期间/元信息/目的/深度/主体开头的行，纯编号行。
- 同源组警告；gate 为 partial/incomplete 时给警告。
- financial-input 有 values 时实际运行 calculate，并核对来源和证据 ID 是否存在。
- 输出 status(structure_passed/invalid)、errors、warnings、research_gate、score、manual_review（22 条人工清单）、visual_review、reading_review（11 个问题，状态为 requires_independent_reading）、meaning。

**check_html_report.inspect_html**
- 用解析器分离可见文本和脚本样式。
- 必须恰好有一个 report-data；封装的键必须是 {content、project、audit_file[、media]}；1.2 版必须有 media。
- project 快照必须与配置一致；重新跑 validate_content 和 review_visuals。
- 完成态必须是 1.2。
- text/callout 段落中含数字但没有 [E-] 引用时给警告。
- 可见 `figure.chart` 的数量必须等于 chart_count；所有锚点 ID 唯一；每个章节都有锚点。
- audit 文件名必须是"<stem>-audit.md"且文件存在。
- **用内嵌的 content 和 media 重新渲染一遍，比较可见文本、SVG 签名、img 签名，必须完全一致**（防止有人手改 HTML）。
- 出现外部资源报错：`<script src>`、`<link rel=stylesheet>`、非 data: 的 img 或带 srcset 的 img。

**visual_review.py**（只给提示，不阻断）
- 清洗规则：去掉引用、URL、各类 ID、日期、年份、列表编号后，再统计数字。
- 每章统计：quantitative_charts、data_points、known_data_points、numeric_values、metric_blocks/items、diagram/process/timeline/matrix 块数、images、people_blocks/profiles、tables、explanations、text_blocks。
- 提示规则：
  - long_prose_run：连续的文字块（explanation/text/bullets/callout）累计 ≥600 个汉字或 ≥120 个英文词
  - late_analytical_visual：本章第一个分析块（chart/diagram/process/timeline/matrix）之前已有 ≥3 个非 unknown 的 explanation
  - topic_without_analytical_visual：financial_performance 所在章没有定量图或矩阵；marketing 所在章没有任何结构图或定量图；competition 所在章没有定量图、关系图或矩阵（对应主题为 unknown 时不提示）
  - numbers_only_in_prose：文字中数字线索 ≥3 个、本章没有含已知值的定量图，且没有触发上一条（unknown 主题内的数字不计）
  - dense_table_without_synthesis：表格行数 ≥5、或单元格 ≥16、或总字数 ≥450，且本章没有分析块
  - 全稿 single_chart_type：≥3 张定量图且全部同一类型
- 输出 rows、summary（含计数说明）、findings、warnings。

**assets/report.js**：目录按钮切换 nav-open；打印按钮；Esc 关闭目录；点击锚点时自动展开所在的 details 并收起目录；hashchange 时展开对应引用；IntersectionObserver 高亮当前章节（aria-current）。关闭 JS 时正文仍可读。

**assets/report.css**：
- 色板 token：白底、蓝 #007aff，辅助色紫、绿、橙；系统字体栈（含 PingFang SC），不用在线字体。
- 断点：1100px 收窄侧栏；767px 隐藏侧栏改为抽屉，图表 SVG 最小宽度 600 可横向滚动，流程改单列。
- 尊重 prefers-reduced-motion。
- 打印：A4、页边距 17/16/18mm；隐藏顶栏、侧栏、按钮；避免图表和卡片被分页截断；强制展开 details；参考来源另起一页；保留打印颜色。
- 没有暗色模式。

**测试**：包内没有测试。重写时至少应覆盖：
- 契约解码：枚举、条件必填、日期顺序
- 引用完整性
- 控制追溯：生效区间、proposed、未核实边
- coverage_state 和 gate 的全部分支
- completion_errors 的每一条规则
- 财务的每个比率，包括缺失、分母为 0 或负、近似、跑道口径、同比可比性
- 评分的门槛和关键维度
- report_model 的每一条约束
- 媒体安全：路径逃逸、符号链接、大小、文件头
- HTML 篡改检测
- visual_review 的阈值

---

## I. 质量门槛与报告设计规则

### I1. 三层验收
1. **构建验收**：检查文件、两份契约、CLI 和边界行为；HTML 包含正文、图表、有效引用、底稿；渲染资源随包安装。只证明技能包能运行。
2. **研究执行验收**：硬错误清单（悬空或重复 ID、非法日期或枚举、占位符残留、预测被标为实际、gate 或 declared_complete 虚报、必读类别没有覆盖行、只有摘要却标已读、旧报告被当最新、子公司数据缺少范围、违规评分、范围完成条件不足、主题缺失或重复、用合作流程代替业务图、时间线规则、图片规则、矩阵规则、各图型的算术规则）加上必须人工做的语义复核（证据是否支持原句、实体时间是否匹配、同源、假设、替代解释、样本外推、遗漏的反证、是否越出约定范围）。含数字未引用只算警告，扫描通过率不能当作真实性评分。
3. **决策证据验收**：逐条追问关键解释需要什么事实、证据是否直接支持、有没有替代解释、反证或未知会不会推翻判断、必要的专业核查是否真的做了。法定禁止或否决条件优先。局部证据够就作局部判断。

### I2. 约定范围完成复核
- 填 completion_review：scope、key_claim_ids、gap_assessments（每个开放缺口都要写具体 impact 和 disposition）、reviewed_at。
- non_blocking 和 limits_conclusion 都必须写具体影响和理由，不能只写"不重要"。
- critical 缺口、会改变决策的冲突、任何 blocks_completion，都会让状态保持 limited。
- 不能事后缩小范围；可以写"约定范围已完成，资料覆盖仍受限"，不能写"全部资料已阅读"。

### I3. "只读正文"理解验收
- 评审者不看底稿，只读主报告，用自己的话回答 11 个问题（对应 11 个主题）。
- 在底稿里记录：实际复述、对应的章节或段落、误解或缺失、处理结果。
- 以下情况不算通过：只重复术语、只引用图表标题、需要作者口头补充。
- 真正未知的主题，读者应能准确说出"什么未知、有什么影响"。
- 复述正确之后，还要另行检查事实依据。

### I4. 可读性与编排
- 交付分层：
  - 主 HTML：画像、产品客户、交易和经营机制、收入成本、关键数据、市场竞争、重大风险、决策条件、关键限制
  - 折叠附录：引用出处
  - audit.md：台账、模块、覆盖、评分、声明核验、桥接、冲突、缺口、日志、请求、访谈
  - CSV/JSON/原件
- 首屏说明研究谁、截至何时、回答什么决策、核心判断是什么；不放流程状态面板、台账行数、覆盖百分比。
- 推荐顺序：身份与沿革 → 创始人 → 产品、客户、业务运转 → 营收盈利 → 营销增长 → 竞争 → 风险决策。不使用"模块07"这类内部标签。
- 每节采用"短导读 → 主视觉 → 意义与限制"；写长文之前先做"读者问题 / 已有材料 / 图形选择 / 不画的具体原因"四列规划，记录在底稿。
- 会改变决策的反证和限制要放在相关分析旁边，不能全部折叠或移到附录。
- 结尾写推进条件、待确认事项、暂停条件，不放问卷或计划。
- Quick 缩短篇幅，但阅读结构不变。

### I5. 图表真实性规则
- 每张图要有：结论标题、单位、期间或时点、主体范围、实际/预测/估算/自述属性、证据、口径说明、数据表。
- 选图：
  - 趋势用 line（同一口径）
  - 规模用 bar/column（零基线、统一单位）
  - 构成用 donut/stacked（完整分母、互斥分类）
  - 单值用指标卡
  - 价格带用 range
  - 有明确量尺的比例用 proportion
  - 收入到利润用 waterfall（完整桥接）
  - 关系和资金流用 diagram
  - 事件用 timeline
  - 定性比较用 matrix
- 禁止：
  - 不同数据商、主体、口径的数据连成曲线
  - 截断零基线
  - 缺项或重叠分类却画成完整百分比
  - 0 和缺失混用
  - 给不可评分的项目编综合分
  - 用布局暗示控制或担保关系
  - 把计划事件当已完成
  - 年化运行率、网站 GMV、集团收入放在同一根轴上
  - 把"九位数中段"变成精确中点
  - 没有转化数据却画有宽度的漏斗
  - 用无依据的二维坐标或热力颜色表示竞争地位
- 业务机制图：
  - 顺序有据才用 sequence；只知道流向用 diagram；连方向都未知就用 conceptual
  - 机制示意不能冒充真实订单
  - 只有交易机制整体未知时才能免画
- 矩阵逐格写依据，不用空白、问号或颜色暗示优劣；矩阵不算定量图，不能因此少画数据图。
- 图片、人物卡、指标卡、结构图、定量图分别统计，不以图的数量代替判断。
- 交付前做三视图预览（桌面、移动、打印）；无法预览的项如实记录。
- HTML、内容模型、audit.md 三者要一致；证据更新后，涉及的正文和图要一起复核。

### I6. 图片规则
- 只能用项目内真实的 PNG/JPEG/WebP 文件，每张 ≤5 MiB、合计 ≤15 MiB，构建时内嵌为离线内容。
- 禁止：运行时 SVG、运行时远程图片、把 URL 填作 path、路径越界、符号链接越界。
- 原始 SVG Logo 可以用可信方式渲染或截图转成位图，保留原出处，不能重新生成。
- 必填：alt、caption、source_url（本地材料用空串，并通过证据关联）、captured_at（本次取得日期）、usage_note、evidence_ids。
- 没取得图片就删掉图片块，不留空框。
- 截图只证明页面当时的样子，不验证宣传内容、人物身份或经营实绩。
- 图片取得日期晚于截止日时给警告。

---

## J. 行业适配（8 类，可以组合；只是起点，不是上限）

| 行业 | 重点指标与检查 | 首选证据 | 常见误判 |
|---|---|---|---|
| 软件/SaaS/AI | ARR 到收入的桥接；GRR/NRR 按同一队列；CAC 回收用毛利计算；推理和算力单价、模型依赖、数据权利、评测、SLA | 合同、订阅队列、账单、成本明细、许可、可复核评测 | ARR 不是收入；LTV 需要稳定的流失假设；演示不等于生产可靠；要分清模型自研还是集成 |
| 制造/硬件 | 产能、产出、良率、利用率、采购周期、库存、保修退货、关键设备、扩产 | 生产台账、BOM、质检、订单验收、设备权属、现场授权记录 | 设计产能不等于有效产能；出货不等于收入；爬坡期和长期低效要分开 |
| 消费/平台 | GMV 与佣金或自营净额、退货、复购、渠道费、补贴、获客队列 | 交易结算、退货、商家和用户队列、总额净额政策 | GMV 不是净收入；下载和流量不是付费用户；补贴驱动的增长要检验持续性 |
| 金融 | 按银行/保险/资管/支付分别看监管资本、流动性、资产质量、期限错配、赔付、AUM 费率；利率、信用、赎回暴露如何影响收益和资本约束 | 监管披露、审计附注、持牌范围、风险暴露 | 不套一般企业的流动比率或跑道阈值；需要行业专业复核；存款不是营收 |
| 医药/医疗 | 注册和临床阶段、试验设计和终点、审批、IP、医保支付、商业化、生产质量 | 注册机关、试验登记和论文原文、授权合同、财报 | 获批、可报销、已上市销售是三件事；阶段成功率不能无依据套用；医疗判断需专业人员 |
| 项目制服务 | 在手订单、履约义务、完工进度、验收、应收和合同资产、人员利用率、项目毛利；拆分获客、交付、回款周期 | 项目合同、工时、里程碑、验收回款、收入确认政策 | 中标不等于签约或收入；毛利受跨期估计影响；项目负荷不等于人数 |
| 资源/周期品 | 有效供给、成本曲线、价格和价差、库存、投产和退出、品位和资源寿命、维持性资本开支 | 产销、储量、成本披露、行业库存价格、开发和环保许可 | 周期高点的利润不可持续；储量、产能、可销售产量要分开 |
| 重资产/基础设施 | 建设和爬坡、利用率、维持和扩张投入、特许权和收费机制、合同期限、融资结构 | 工程和运营记录、资产权利、收费和采购合同、债务期限、资本开支 | 规划投资不等于已投产；会计利润不等于可分配现金；受监管回报和合同保底要核实条件 |

跨行业共同规则：
- 只追踪有实际暴露的利率、汇率、原料、能源、政策变量，说明传导、滞后和合同缓释。
- 成熟期看效率和再投资，扩张期看产能和资金是否匹配，早期看需求和单位经济验证；不用融资轮次代替业务阶段。
- 没有对应专业能力时，写明哪些结论无法形成、还需要什么材料和专家；不能把通用脚本的输出当成行业模型结论。

---

## K. 做得特别好的细节（10 条）
1. **三种"完成"互不覆盖**：research_gate、report_status、declared_complete 分开，配合 completion_review 对每个开放缺口做影响评估，既防止"资料没读完就宣称完成"，也避免"缺一份研报整个研究就不能结束"。
2. **研报的三个"最新"指针**：最新发现、最新全文、最新已读分开记录，并与报告表双向一致；同日多份报告必须全部读完；没找到只建缺口不建假报告；豁免只开放给 official_interim。这套设计能有效防止拿旧报告冒充最新。
3. **控制链按时点有向追溯**：左闭右开的生效区间，proposed 和未核实的边不触发，有环检测，并把未锁定的身份传导为 pending，堵住"参股或拟收购被当成控制"的漏洞。
4. **语义硬校验把常见造假路径变成机器错误**：截止日后的资料、预测或估算冒充实际、集团数据套到子公司（必须有 bridge 加【推断】）、不可读来源形成证据、报告日期用平台收录日、主体未锁定却形成确定结论。
5. **HTML 防篡改**：用内嵌的 content 和 media 重新渲染，比对可见文本、SVG、img 签名，同时检查外部资源；手改 HTML 会被发现，也保证了离线可读。
6. **图型级别的数据真实性约束**：瀑布图用高精度 Decimal 校验累计、区间不画中点、比例的量尺不暗示互补类别、堆叠的分类必须一致且不能缺失、null 不变成 0、forecast 有专门的虚线样式、点级属性必须与证据属性一致。
7. **业务图的证据属性**：basis 分四档，ordering 区分 sequence 和 conceptual；关系图不允许孤立节点和自连接，推断或未知用虚线；明确"示意不是真实订单"。
8. **11 个理解主题加只读复述验收**：把"把公司讲清楚"变成可检查的结构（有证据的状态必须引用，部分或未知必须写限制），同时明确机器检查无法证明讲清楚了，必须有人复述。
9. **财务计算的保守设计**：缺失不补 0；分母 ≤0 标不适用；期末余额和代理分母必须显式允许并标 approximate；跑道必须声明是否剔除受限现金等口径并标为 estimate；同比要求严格可比；阈值告警只算线索。
10. **评分默认关闭且门槛严格**：公司研究禁止评分；专项必须给出项目级的权重、关键维度和理由；关键维度不能通过标"不适用"消失；评分只计高或中置信度的维度；有 critical 缺口或会改变决策的冲突时不发布；分数、风险、证据充分度分别呈现。

## L. 薄弱点和可优化之处（10 条）
1. **没有测试**：发布包里没有任何测试，大量规则（coverage_state、completion_errors、render 一致性）的正确性无法回归验证。重写时应把测试作为一等交付物。
2. **joint_control 不触发上市研报**：control_relations 只包含 control、brand_of、branch_of，共同控制的上市股东不会被追溯，和"多边控制图"的说法不一致。应把它设为可配置项，或至少对 joint_control 给出警告。
3. **"日期未知就保留未知"无法落地**：source-register 的 published_date 是必填的 date 类型，research report_date 也必填，实际上会迫使人编日期。应允许 null 加精度字段（年、月、日）。
4. **事件触发过粗或过窄**：只要项目有任意一个事件，所有上市主体都会增加两个事件类别；自动识别事件只靠"官方披露晚于最新 company_update"这一种情况。应把事件绑定到具体主体，并支持更多事件类型。
5. **gate 完成硬性依赖 `network=online`**：用户提供了全部全文、离线也读完了，仍然永远无法 complete。应把门槛改为基于"实际检索和阅读记录"判断，而不是网络标志。
6. **财务指标不全**：模块 12 要求的营业利润率、EBITDA、杠杆、利息覆盖、资本回报都没有计算（total_debt 和 total_assets 只接收不计算）；ROA/ROE 不年化，可能被误读；同比只支持同季同长度，不支持 TTM、环比或多期序列；缺少分部或结构占比的计算。
7. **search_plan 会生成过量任务**：别名 × 18 模块 × 语言的组合会产生几百条关键词任务，缺少按 depth 或优先级裁剪和去重的机制；研报任务的 4 个时间窗口也不考虑是否已找到结果。
8. **台账写入不是事务，且只能整行替换**：省略字段会被清空，容易误删数据；多文件写入中断要手动恢复。可以改用 SQLite 或 JSONL 加事务，并支持局部 patch。
9. **展示层有硬编码和约束**：界面文字大多写死中文（虽然 language 可选 en）；没有暗色模式；关系图最多 6 个节点；最新指针每类只指向一份报告（同日多份时只能从 gate 状态间接体现）；没有独立的 PDF 导出。
10. **人工复核没有结构化回填**：理解复述、visual_review 的处理理由、三视图预览结果都要求"记录在底稿"，但没有对应的字段或台账，机器无法检查它们是否真的做过。来源目录中大量条目标"待验证或访问失败"，也缺少在项目启动时自动重新探测可用性的机制。建议为人工复核建表，并在 completed 模式下强制要求存在。

