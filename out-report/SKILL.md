---
name: out-report
description: Use when verified analysis must be delivered as a formal reading report in self-contained A4 HTML and matching PDF, with evidence coverage, pagination, visual QA, author review, independent review, and acceptance records. Use out-deck for presentations, out-chart for one editable chart, and out-poster for a one-page visual.
---

# 出正式 A4 报告

把 `core-storyline` 的 `slides.json` 和证据账投影为媒介中立的 `report.json`，再由批准的 A4 设计系统自动排版。报告与演示文稿是两条链路：本 skill 不制作 PPT，也不要求作者手写页面 HTML。

关键展品不得退化为占位图或通用“Relationship / Evidence”表。`semantic_type=pain-demand` 的 panel 必须从 `decision-research.json` 显示完整痛点链；`semantic_type=competition` 必须显示替代层与共同购买维度；其余决策性 block 至少显示主张正文、身份、置信度、支持/反证、适用范围和限制。正文只用紧凑引用标记，完整 URL 与来源字段只放来源附录。

入口：

```bash
python3 <本 skill>/scripts/out_report.py <命令> <任务文件夹>
```

## 工作流

1. `init`：同时运行原有数字追溯检查与 `report.json` 覆盖合同；生成 `07_storyline/report.json`、`a4-work/coverage-manifest.json` 和渲染文档。检查失败时不创建任务。
2. `render`：用锁定字体和 Chromium 两遍分页，生成 A4 HTML、PDF、逐页 PNG、pagination、geometry、media、visual-regression 和 QA 记录。首次报告与批准黄金样册通常存在视觉差异，因此会失败关闭，但仍留下可审查预览。
3. 作者逐页查看 PDF/PNG 后提交 `review <任务> author <review.json>`。作者记录必须接受并绑定当前 `baselineDigest`、`candidateDigest`、`differenceDigest` 和 `artifactDigest`，不能复用旧审批。
4. 成品审查员独立查看最终 HTML/PDF，只把结论写入 `review <任务> independent <review.json>`。记录必须绑定当前 artifact 与 pagination digest，逐页覆盖 HTML/PDF，同时记录 100% 和整册缩略图尺度、章节 contact sheet、标题链、具体观察和理由；“PASS”“正常”等泛化文字无效。未解决问题不能通过。
5. `package`：仅在 QA、作者审查和独立审查均通过后，把正式成品写入 `08_deliverables/client-report/`，并把完整来源、快照、证据账、数据与计算、检索日志、审查和清单封装到 `08_deliverables/evidence-package/` 及同名 ZIP，再登记统一验收。旧任务的 `08_deliverables/report/` 只作读取兼容；新任务不会重复写两份报告。

故事线或证据变化后运行 `refresh`，再从渲染与审查重新开始。视觉差异只允许人工处置，脚本永不自动更新批准基线。

PDF 导出有两个正式后端：macOS 且可用 Swift 时默认逐页打印并用 PDFKit 重建内部链接；Linux/cloud 或没有 Swift 时使用 Chromium 整册导出，保留原生目录与引用链接。可用 `ALLEN_PDF_BACKEND=chromium|pdfkit` 显式选择；`pdfkit` 仅在 macOS + Swift 上有效。两条路径都必须通过页数、A4 MediaBox、文本、裁切与 PDF 内链 QA。

## 审查记录

作者记录：

```json
{"type":"author","reviewer":"主笔","reviewedAt":"2026-10-27T12:00:00+10:30","decision":"accepted","reason":"逐页检查标题、证据、限制和来源后的具体判断","baselineDigest":"…","candidateDigest":"…","differenceDigest":"…","artifactDigest":"…","paginationDigest":"…"}
```

独立记录遵循 `core-review/references/output-standard.md`：`type=independent`，包含 reviewer、带时区时间、结论、artifact/pagination digest、page_ids、media、scales、chapter_contact_sheets、headline_chain、逐页 observations 和 issues；所有问题必须已解决。没有独立审查时只能向用户说明预览位置，不能运行正式打包或宣称完成。

## 输出门禁

系统机械检查 A4 MediaBox、溢出、遮挡、裁切、空页、最小字号、内嵌资源、HTML/PDF 页序与文字清单、claim/A 卡/panel/relation/metric/source 覆盖集合和逐页视觉哈希。审查时锁定 HTML、PDF、逐页 PNG、report/render document，以及 coverage、pagination、geometry、media/page-text、visual candidate 这些原始 QA 输入；打包前重新计算，任何篡改都失败。`qa-evidence`、visual-regression 和 QA result 含作者处置，处置本身又绑定 artifact digest，因此不放进同一 digest，避免哈希循环；它们进入证据包后由 checksum manifest 锁定。证据包保留审计清单，但不复制逐页渲染缓存。缺测量证据本身就是失败。

默认 `bibliography_policy=evidence_package`、`client_citations=compact`：客户版只显示紧凑编号、source ID 与 locator 锚点，不显示 URL、来源等级、抓取时间或内部研究元数据；这些字段进入证据包。只有调用方明确选择 `bibliography_policy=full` 时才在客户版渲染完整书目。正文引用标记由 renderer 根据 `source_ids` 和 `source_bindings` 自动生成；作者不得手写 URL、引用编号、`.source-strip` 或其他多行页底来源带。

需要完整客户版书目时，在 `init` 或 `refresh` 显式传 `--bibliography-policy full`。

四个企业应用的 `package` 会同时生成证据包；也可单独运行 `tools/package_support.py <任务>` 重建并验收。
