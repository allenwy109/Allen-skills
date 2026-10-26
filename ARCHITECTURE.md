# 架构

## 为什么这样分层

按功能拆开：流程只写一份（在场景里），选方法、核实、研究、尽调、故事线各成一个能力 skill，事实只记在一个证据账里，成品只经输出层出，最后由独立审查和统一验收把关。

```
应用入口    allen-idea   allen-company   allen-capital   allen-ecosystem   allen-bp-review
             │  锁定系统提示词和场景；app_runtime 状态机防止只摘要后退出
通用入口    router：没有明确点名应用时判断场景，定深度，建任务文件夹
             │
接收        core-intake：用户附的 PDF / Word / PPT → 逐页全文、页面图片、表格，登记进证据账
             │
场景层      scene-idea   scene-company   scene-topic   scene-bp-review   scene-personal
             │  只编排：按什么顺序调哪些能力、交付什么、哪些关口必须过
             │
能力层      core-framing → core-method-select → （按卡片分析）→ core-synthesis → core-storyline
                                                   │
                                                   ├ core-evidence（核实；来源评价和核实关口的唯一标准）
                                                   ├ core-research（开放研究、研究包）
                                                   └ core-diligence（公司研究与尽调）
             │
质量层      core-review（5 个审查角色，含成品审查员；统一输出标准）
             │
方法库      lib-consulting   lib-management   lib-personal（卡片 + 选法表，不带流程）
             │
输出层      out-report（HTML + PDF）  out-chart（PPTX + PNG + HTML）  out-poster（PNG + HTML）
             │
引擎        vendor/report-forge  vendor/thinkcell-charts  vendor/onepager（Apache-2.0，固定版本，只经 out-* 调用）
公共        tools/lib（统一证据账、schema、运行时路径）  tools/app_runtime.py  tools/package_support.py  tools/acceptance.py
```

## 三条边界

1. **方法库不带流程。** 只回答“有哪些方法、什么时候能用、怎么用对”。
2. **能力 skill 只管一件事，可以单独用。** 例如只想核实一篇文章，就只调 core-evidence。
3. **场景 skill 只编排，不重复规则。** 系统提示词只是一层薄壳：角色 + 指向场景 skill + 不可跳过的规则（见 `router/references/system-prompts.md`）。

## 两道关口

| 关口 | 在哪 | 查什么 |
|---|---|---|
| 选方法关口 | core-method-select | 子问题画像；方法前提是否满足（不满足就补信息或降级，不用推断填满）；预演产出能否回答子问题；为什么不用相邻方法 |
| 核实关口 | core-evidence 第 6 节，core-synthesis 开始前 | 影响结论的事实是否已核实；未核实的改写成“如果……则……”并列入待确认问题 |

## 交接文件

skill 之间不靠对话记忆传递，而是通过任务文件夹里的固定文件。换一个 skill、重做一步、另开一个审查者，都不用重讲一遍。

```
work/<日期>-<主题>/
├── 00_brief.md          router（含"用户要求（原文）"）
├── 00_idea-definition.md / 00_venture-paths.md  allen-idea 专用，需用户确认
├── 01_issue-tree.md     core-framing
├── 02_method-plan.md    core-method-select
├── 03_evidence/         统一证据账：ledger/*.jsonl 是事实的唯一真源，raw/ 存来源快照和用户材料
├── 03r_research/        core-research 工作文件
├── 03d_diligence/       core-diligence 工作文件
├── 04_analysis/         按卡片做的分析
├── 05_review-log.md     core-review
├── 06_synthesis.md      core-synthesis
├── 07_storyline/        core-storyline 的稿件、slides.json；引擎过程目录 forge-work/、poster-work/
└── 08_deliverables/     主报告 report/、supporting-package.zip、按需附属交付物、acceptance.json
```

L1 快答不建文件夹，内容直接写在回答里。完整的目录树在 router 第 3 节。

## 一个事实从哪里来、到哪里去

1. 来源（网页快照、用户文件）进 `03_evidence/raw/`，登记为 sources；摘录登记为 evidence；判断登记为 claims，指向支撑它的证据；数字登记为 metrics。
2. 分析和综合引用主张 `[cl-0003]` 或原文定位 `[M004 p12]`。
3. 故事线把主张组织成卡片 `card-0012`，稿件里写 `〔card-0012｜M004 p12〕`。
4. 转换脚本把 slides.json 翻成引擎输入，数字一律写成 `{{metric:m-0001}}` 由引擎绑定；台账外的数字、未核实却以事实呈现的说法会被拦下。
5. 主报告和支撑文件包分别登记进 `08_deliverables/acceptance.json`；两者的前置检查与成品审查都通过后，应用状态机才允许判定“已完成”。

## 审查

| 角色 | 只查什么 | L2 | L3 |
|---|---|---|---|
| 事实核查员 | 影响结论的事实，独立联网重查 | 开 | 开 |
| 红队 | 最强反对理由、其他解释、维持现状基准、强词 | 开 | 开 |
| 方法审查员 | 方法是否选对、前提是否满足、常见误用 | — | 开 |
| 决策者视角 | 只读最终报告：首屏能否读到答案；行动是否具体；是否回答主导问题 | — | 开 |
| 成品审查员 | 只看最终交付物：身份是否如实、视觉问题、中文显示、内容齐全；结论写进 acceptance.json | 开 | 开 |

审查者必须是没参与写作的独立子代理。没有子代理能力的环境降级为按清单自审，并在报告里写明“未经独立审查”。

## 防止绕过

- 正式报告、图表、海报只能经 out-* 出：vendor 引擎目录里没有 SKILL.md，不会被单独触发；场景只指向 core-storyline 和 out-*。
- 引擎的生产记录只能经 report.cjs 统一入口写，否则过不了引擎的验收和打包门禁。
- 只有 acceptance.json 能判定"已完成"，它会重新计算前置检查和成品哈希；成品被改动后状态自动失效。
- 五个应用入口必须经 app_runtime 逐阶段推进；allen-idea 的 clarify 和 pathing 是应用专用确认门禁，其余证据、报告和验收规则共用；缺少阶段文件、用户确认、主报告或支撑文件包时不能提前结束。
- `validate.py` 拦下对不存在的 skill 的引用，场景只能指向本系统的 skill。

## 依赖

三个引擎按 `vendor/vendor.lock` 的固定 commit 和文件哈希放在仓库里，补丁在 `vendor/patches/`，`tools/vendor_sync.py check` 和 validate.py 会核对。出成品要 `install.sh --render-deps` 装好的依赖（Node.js 20+、Python 3.10+ 虚拟环境、Chrome/Chromium、Playwright Chromium、Poppler、Tesseract、Pandoc、LibreOffice），`tools/doctor.py` 全部通过才能出。安装器支持 macOS，并能在 Linux 上检查系统依赖、继续安装 Python 与 Node 依赖。依赖不全时，场景先交综合和故事线稿件，并写明正式报告尚未生成。

## 后续计划

1. 用 `tests/method-selection-cases.md` 跑一次基线，按结果修选法表。
2. 用 1 到 2 份真实 BP 跑通 scene-bp-review，含正式报告。
3. scene-company、scene-topic 各用 2 个真实案例跑通。
4. 把回退记录和审查记录里反复出现的问题，回写到选法表和卡片的“常见误用”。
