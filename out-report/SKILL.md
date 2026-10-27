---
name: out-report
description: Use when verified analysis must be delivered as a formal reading report in self-contained A4 HTML and matching PDF, with evidence coverage, pagination, visual QA, author review, independent review, and acceptance records. Use out-deck for presentations, out-chart for one editable chart, and out-poster for a one-page visual.
---

# 出正式 A4 报告

把 `core-storyline` 的 `slides.json` 和证据账投影为媒介中立的 `report.json`，再由批准的 A4 设计系统自动排版。报告与演示文稿是两条链路：本 skill 不制作 PPT，也不要求作者手写页面 HTML。

入口：

```bash
python3 <本 skill>/scripts/out_report.py <命令> <任务文件夹>
```

## 工作流

1. `init`：同时运行原有数字追溯检查与 `report.json` 覆盖合同；生成 `07_storyline/report.json`、`a4-work/coverage-manifest.json` 和渲染文档。检查失败时不创建任务。
2. `render`：用锁定字体和 Chromium 两遍分页，生成 A4 HTML、PDF、逐页 PNG、pagination、geometry、media、visual-regression 和 QA 记录。首次报告与批准黄金样册通常存在视觉差异，因此会失败关闭，但仍留下可审查预览。
3. 作者逐页查看 PDF/PNG 后提交 `review <任务> author <review.json>`。作者记录必须接受并绑定当前 `baselineDigest`、`candidateDigest`、`differenceDigest`，不能复用旧审批。
4. 成品审查员独立查看最终 HTML/PDF，只把结论写入 `review <任务> independent <review.json>`。未解决问题不能通过。
5. `package`：仅在 QA、作者审查和独立审查均通过后复制正式成品与全部审计清单到 `08_deliverables/report/`，并登记统一验收。

故事线或证据变化后运行 `refresh`，再从渲染与审查重新开始。视觉差异只允许人工处置，脚本永不自动更新批准基线。

## 审查记录

作者记录：

```json
{"type":"author","reviewer":"主笔","reviewedAt":"2026-10-27T12:00:00+10:30","decision":"accepted","reason":"逐页检查后的判断","baselineDigest":"…","candidateDigest":"…","differenceDigest":"…"}
```

独立记录遵循 `core-review/references/output-standard.md`：`type=independent`，包含 reviewer、带时区时间、结论和问题；所有问题必须已解决。没有独立审查时只能向用户说明预览位置，不能运行正式打包或宣称完成。

## 输出门禁

系统机械检查 A4 MediaBox、溢出、遮挡、裁切、空页、最小字号、内嵌资源、HTML/PDF 页序与文字清单、claim/A 卡/panel/relation/metric/source 覆盖集合和逐页视觉哈希。缺测量证据本身就是失败。

四个企业应用完成主报告后，仍需运行 `tools/package_support.py <任务>` 生成并验收支撑文件包。
