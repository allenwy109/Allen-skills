---
name: out-report
description: 出正式报告（自包含 HTML + 同版 PDF，另附讲者备注）：把 core-storyline 产出的 slides.json 和证据账交给 report-forge 引擎，走完它的执行清单、三项固定约束（图表多样性、版式多样性、模块填充）、代表页、正式验收、作者与独立审查和打包，最后登记统一验收。L2 起的默认交付物，企业诊断、行业研究、公司研究、尽调结论都走这一条链路。耗时明显长于 Markdown 交付。单张可编辑图表用 out-chart，一页海报用 out-poster。
---

# 出正式报告

报告的每个数字、每条主张都来自证据账；引擎负责排版、核对绑定和验收，不改结论。**所有会写生产记录的步骤都经 `report.cjs` 统一入口**（本 skill 的脚本已封装好），不要直接调用引擎的底层脚本，否则过不了 acceptance 和 package 的门禁。

脚本：`python3 <本 skill 目录>/scripts/out_report.py <子命令> <任务文件夹> …`，下文简写为 `out_report`。引擎任务目录固定为 `07_storyline/forge-work/`（下称 forge-work）。

## 耗时预期

一份 10 页左右的报告要经过：三项规划 → 代表页 → 批量制作 → 正式验收 → 作者审查 + 成品审查员独立审查 → 打包。比 Markdown 交付慢得多，开始前在回复里告诉用户。

## 0. 输入要求

`07_storyline/slides.json` 除了故事线字段，还要有报告引擎需要的字段（schema 见 `<运行时>/tools/lib/schema/slides.schema.json` 1.1.0）：

| 位置 | 字段 | 说明 |
|---|---|---|
| deck | `brief` | 研究问题、目的（diagnosis/decision/research）、范围、期间、基准、约束、成功标准 |
| deck | `answer_claim_refs` | 核心答案的主张，必须由正文页承担 |
| deck | `cover` | 封面信息，`date` 必填 |
| deck | `arc` | 弧线；`other` 时写 `arc_reason` |
| 正文页 | `proves`、`adds`、`density`、`claim_refs` | `adds` 写读者比上一页多知道什么 |
| 正文页 | `panels`、`relations`、`anchor_panel` | 每件展品的用途、主张、形式、选型理由、区域；多件展品用 relations 说明为何一起看 |
| 正文页 | `subtitle` | 写口径（单位、期间、范围），不重复标题，不写数字 |

`sidecar.json` 的讲者备注会生成 `08_deliverables/speaker-notes.md` 和 `.pdf`。

## 1. 建任务（转换前检查）

```bash
out_report init <任务文件夹> [--allow 3]
```

先跑转换前检查（`tools/bridge/to_forge.py`，规则见 `tools/bridge/MAPPING.md` 报告引擎一节）。不通过就不建引擎任务，按提示退回 core-storyline 或分析层：

- 文字里的数字必须等于进入报告的某个指标的显示值（会自动换成指标引用，由引擎统一显示）；副标题、adds、讲者备注里的数字也要能追回证据账。确实不是数据的数字（如"3 个阶段"）用 `--allow` 放行，放行会写进验收。
- 关键的未核实主张改写为假设，句尾加"（待确认）"；被推翻的写成"曾认为……，已被推翻"；非关键的未核实主张、冲突没写采信理由的主张拦下。

通过后：建引擎任务（editorial 模式、narrative-focus-1）、写 task 字段（kind=report、complex、majorConclusion、independent），生成蓝图 `deck-blueprint.json` 和首尾页 `bookend-cover.html`、`bookend-references.html`、`bookend-back.html`，激活执行清单。

slides.json 或证据账改了以后：`out_report refresh <任务>`。引擎会把受影响的已完成项标为需要重新核实，重新提交即可。

## 2. 三项规划

通读蓝图，按 `<运行时>/vendor/report-forge/references/content-authoring.md` 的"整册图表与版式规划"和 `module-fill.md` 做规划，**主动找没用过、又适配的图型和版式**，重复要写具体理由。把选型写回 slides.json（panels 的 reason、visual_intent 的 layout_reason、repetition_reason）后 refresh。

每项写一份观察 JSON，放在 forge-work 里（格式见 `<运行时>/vendor/report-forge/references/execution-checklist.md` 第 3 节），然后：

```bash
out_report plan <任务> chart-plan forge-work/obs/chart-plan.json --reviewer <主笔> --basis <核对了什么>
out_report plan <任务> layout-plan …
out_report plan <任务> module-fill-plan …      # 观察里要有 modulePlans，逐页逐栏
```

- 观察要覆盖蓝图的**每一页**（含封面、封底），说明考虑过的候选和取舍。
- `--basis` 写实际核对的内容，不写"已检查"。

## 3. 编译与制作

```bash
out_report step <任务> ready       # 蓝图 ready 校验（只读）
out_report step <任务> compile     # 生成本轮页面记录和派生 task
```

作者写 `forge-work/pages.html` 和 `forge-work/page.css`：

- 顺序：`bookend-cover.html` 的内容 → 正文各页 → `bookend-references.html` → `bookend-back.html`。
- 正文页：`<section class="slide reading" data-page-id="p02" data-frame-boundary="line">`，id 是 `p` 加两位页码。
- 每件展品的根节点写 `data-panel-id`，与 slides.json 的 panel id 一致。
- 标题、主张、限制、指标、来源放进带 `data-content-key` 的叶节点（键名和标准文本见编译结果 `pages.json` 和 `content-snippets.html`）。装配时引擎会按蓝图重填这些节点，所以数字和身份标签不会写错。
- 每个正文页恰好一个 `data-reading-role="takeaway"` 的收束句，写本页要读者记住的一件事，不复述标题。
- 只用内联 SVG 和 data: 资源，不用脚本、canvas、外部图片和字体。图表自己用 SVG 画；手写的图注、坐标标签里的数字会在 finish 时回查。
- 正文字号不要大过标题；声明为 primary 的展品要是页面上最大的展品。

```bash
out_report step <任务> assemble
out_report step <任务> smoke                     # 或 iteration --pages 2,3
```

## 4. 代表页与正式验收

1. 选 2–3 张能暴露不同风险的页（核心定量页、最密的页、定性或行动页），**实际打开截图看**。截图在 smoke 审计目录里（路径记在 `forge-work/.allen/runs.json`）。
2. 写代表页观察：`kind=visual`，`audit` 绑定这次 smoke 的审计文件，`files` 列出看过的截图，`moduleObservations` 覆盖这些页审计里枚举的全部区域，写实际所见和修改或保留的判断。发现问题先改 pages.html 再重来。
3. `out_report plan <任务> representatives <观察>`；全部页面做完后写制作记录，`out_report plan <任务> production <观察>`（files 写装配出的 HTML）。
4. `out_report step <任务> acceptance`。

## 5. 审查

```bash
out_report step <任务> review-pack
```

作者稿和独立审查稿复制到 `forge-work/reviews/`：

- **作者**填 `author.json`，覆盖每页。
- **成品审查员**（core-review 第 5 个角色，必须是独立的子代理）填 `independent.json`，只看最终 HTML 和 PDF：
  - coverage 的 layers 写 page、exhibit、annotation、typography、narrative；
  - `panelRefs`、`relationRefs` 照 `review-pack.json` 的组合清单逐项核对后填入；
  - `narrativeReadings` 逐正文页写**页面上实际读到的**收束句，引擎会和页面文字比对；
  - qualityChecks 的三项整册审查（chart-diversity、layout-diversity、module-fill）逐页、逐区域写实际观察；
  - 告警按组处置（`warning-decisions.json`），或在 warningReview 里逐条写 accepted/fixed 和理由。
- 字段以引擎的审查合同为准（`<运行时>/vendor/report-forge/references/static-html-pdf.md` "最终验收与交付"一节）。

没有子代理时，独立审查稿不能由作者冒充填写，引擎也不会放行打包：停在这里，把正式验收产生的 HTML 和 PDF（验收审计里的 htmlArtifact、pdfArtifact）明确标为**预览**交给用户，并说明未经独立审查、不是正式交付。

```bash
out_report step <任务> aggregate
out_report step <任务> snapshot
out_report step <任务> package [--name <文件名>]
```

## 6. 交付与验收

```bash
out_report finish <任务> [--slug main]
```

- 复制 HTML、PDF 到 `08_deliverables/report/`，生成讲者备注。
- 回查正文页里作者手写（没有内容绑定）的文字中的数字。
- 尽调报告（任务里有 `03d_diligence/report-content.json`）另加 3 项：尽调检查、内容契约（拆页后复核、22 条人工清单）、完成状态（research_gate 为 partial 或 report_status 为 limited 时记为有限完成，验收最高为有条件通过）。
- 登记验收条目 `report-<slug>`，前置检查 7 项：故事线检查（`core-storyline` 的 `storyline check` 零错误）、转换前检查、A 级卡片出现在正文、引擎正式验收、作者与独立审查、执行清单、手写文字数字回查。

此时验收状态是"不通过（尚未经过成品审查）"。成品审查员按 `../core-review/references/output-standard.md` 写结论 JSON（我们自己的八项标准，含讲者备注和附录是否齐全），用 `<运行时>/tools/acceptance.py <任务> review report-<slug> <结论.json>` 写入。

实际交给用户后，写 delivery 观察（加 `destination`、`deliveredAt`），`out_report plan <任务> delivery <观察>`，再 `out_report step <任务> archive`。

## 7. 中断与修订

- 中断后：`out_report step <任务> resume`（只读，看待办、阻塞和需要重新核实的项），`step next` 看下一步。
- 引擎遇到残留锁会明确报错；确认原进程已退出后，按引擎文档用 `report.cjs recover-lock` 处理。
- 修订：改 slides.json 或证据账 → refresh → 重新提交受影响的清单项 → 从 compile 往下重走。已完成的审查快照可以用引擎的 `reuse` 准备继承草稿，变化的页仍要重新审查。
