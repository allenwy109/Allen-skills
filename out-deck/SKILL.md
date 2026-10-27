---
name: out-deck
description: Use when the requested deliverable is a presentation, pitch deck, roadshow deck, or slide-based consulting narrative in 16:9 or 4:3; do not use for the default A4 reading report.
---

# 出咨询演示稿

用 report-forge 生成自包含 HTML 与同版 PDF 演示稿。正式 A4 阅读报告走 `out-report`；只有用户明确要路演、汇报或演示文稿时才走本技能。

脚本：`python3 <本 skill>/scripts/out_deck.py <子命令> …`，下文简称 `out_deck`。任务目录固定为 `07_storyline/deck-work/`，交付目录固定为 `08_deliverables/deck/`，不会覆盖 A4 报告。

## 不可省略的合同

- 内容来自 `core-storyline` 的 `slides.json`、`sidecar.json` 和证据账；排版引擎不改结论。
- 保留上游 38 种布局、6 种母版、三套主题、16:9/4:3、完整图表与容量合同。
- 图表规划、布局规划、模块填充是三项独立清单，不得合并成一次泛化检查。
- 必须检查代表页、整册缩略图、最坏页，并逐页复核 HTML/PDF。
- 所有会写执行记录的动作经 `out_deck.py` 调用 `report.cjs`；不要直接运行底层脚本绕过 acceptance/package。

先确认锁定能力完整：

```bash
out_deck capabilities --strict
```

## 输入和建任务

输入必须通过 `tools/bridge/to_forge.py` 的映射与数字追溯。`slides.json` 至少包含 deck brief、answer claim refs、cover、arc，以及每页的 proves/adds/density、claim refs、panels/relations、anchor panel、视觉选择理由和口径副标题。

```bash
out_deck init <任务目录> [--allow 3]
```

只有真正不是数据的裸数字才能用 `--allow`；放行会进入验收记录。输入变化后运行：

```bash
out_deck refresh <任务目录>
```

## 三项规划

规划观察必须覆盖全部页面，记录候选、取舍和重复理由，文件放在 deck-work 内：

```bash
out_deck plan <任务> chart-plan <观察.json> --reviewer <主笔> --basis <实际核对依据>
out_deck plan <任务> layout-plan <观察.json> --reviewer <主笔> --basis <实际核对依据>
out_deck plan <任务> module-fill-plan <观察.json> --reviewer <主笔> --basis <实际核对依据>
```

## 制作与浏览器检查

```bash
out_deck step <任务> ready
out_deck step <任务> compile
```

根据 compile 产物制作 `deck-work/pages.html` 和 `page.css`。每页、展品、内容叶节点、收束句必须保留引擎要求的 ID 和 data attributes；只用内联 SVG 与 data: 资源，不用脚本、canvas、外链图片或字体。

```bash
out_deck step <任务> assemble
out_deck step <任务> smoke
out_deck step <任务> iteration --pages 2,5
```

从真实截图选择 2–3 张代表页（核心定量页、最密页、定性或行动页），提交逐模块观察；完成整册后再提交 production：

```bash
out_deck plan <任务> representatives <观察.json> --reviewer <主笔> --basis <依据>
out_deck plan <任务> production <观察.json> --reviewer <主笔> --basis <依据>
out_deck step <任务> acceptance
```

## 作者与独立审查

```bash
out_deck step <任务> review-pack
```

作者填写 `reviews/author.json`。独立成品审查员填写 `reviews/independent.json`，必须实际查看最终 HTML、PDF、逐页图、整册缩略图和最坏页，并覆盖 page、exhibit、annotation、typography、narrative、panel/relation、三项整册规划及告警处置。没有独立审查员时只能交预览，不能伪造审查或正式打包。

```bash
out_deck step <任务> aggregate
out_deck step <任务> snapshot
out_deck step <任务> package [--name <文件名>]
out_deck step <任务> archive
out_deck finish <任务> [--slug main]
```

`archive` 是 report-forge 在实际发送前生成的恢复封存包；它锁定当前 package 收据、审查与执行记录，不代表文件已经交给用户，也不包含之后才产生的 delivery 观察。`finish` 只生成本地交付物、讲者备注并登记 `deck-<slug>` 验收，不代表实际发送。实际交给用户后，最后提交 delivery 观察：

```bash
out_deck plan <任务> delivery <观察.json> --reviewer <主笔> --basis <交付依据>
```

## 中断和修订

- 看状态：`out_deck step <任务> status|next|resume`。
- 修订：更新故事线或证据账 → refresh → 重交受影响清单 → 从 compile 往下重走。
- 残留锁只在确认原进程退出后，按引擎文档恢复；不要直接删执行记录。
- 四个企业应用若要求支撑包，演示稿完成后仍运行 `tools/package_support.py`，主交付和支撑包分别验收。

## 常见错误

| 错误 | 正确处理 |
|---|---|
| 把正式阅读报告做成幻灯片 | 默认使用 `out-report` 的 A4 输出 |
| 三项规划合并为“已检查” | 分别提交逐页图表、布局、模块填充证据 |
| 只看代表页就打包 | 代表页之后仍要整册验收、双媒介逐页审查 |
| 作者填写独立审查 | 停在预览，等待独立审查员 |
| 把 archive 当成发送后的交付日志 | archive 是发送前恢复封存包；实际发送后另交 delivery 观察 |
| 绕过 wrapper 直接运行引擎步骤 | 通过 `out_deck` 保留执行清单和验收记录 |
