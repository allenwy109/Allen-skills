---
target: Allen-skills A4 report output design vs Zerox consulting-report-forge
total_score: 32
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 0
target_identity: "file:/Users/markjackson/Repos/Allen-skills/docs/specs/2026-10-27-a4-report-output-design.md"
target_fingerprint: "sha256:ad681624b2fe1e9f1b6cf9a24813cc8c787ad4227985ca68737e737e921774cb"
target_path: /Users/markjackson/Repos/Allen-skills/docs/specs/2026-10-27-a4-report-output-design.md
timestamp: 2026-10-27T00-14-30Z
slug: docs-specs-2026-10-27-a4-report-output-design-md
---
Method: dual-agent (A: /root/visual_design_review · B: /root/implementation_evidence_review)

# Allen-skills A4 报告输出设计对标审查

## Verdict

原设计不能保证达到参考仓库视觉水平，只能保证内容完整、排版不坏和风格克制。修订后，设计已经具备阻止平庸成品冒充正式交付的必要门禁，但最终是否达到参考水平仍须由黄金小册和真实匿名 A/B 验证，不能在实现前口头保证。

## 设计保障评分（修订后，非成品评分）

| 维度 | 分数 | 判断 |
|---|---:|---|
| 视觉焦点 | 4/5 | 已规定单一一级焦点和第一眼落点验收 |
| 证据—几何匹配 | 4/5 | 已增加独立 A4 Layout Atlas 合同 |
| 信息密度 | 4/5 | 已定义容量、拆页和禁止缩字 |
| 排印精度 | 4/5 | 已冻结首版字号、行距、边距、基线和断行规则 |
| 图表清晰度 | 4/5 | 已增加 form catalog 和图表视觉语法 |
| 跨页节奏 | 4/5 | 已增加整册 art direction、contact sheet 和逐章审查 |
| 来源整合 | 4/5 | 已定义来源安全区、跨页和可读下限 |
| 整体完成度 | 4/5 | 已增加黄金小册、逐页签署和匿名 A/B 门禁 |
| **总计** | **32/40** | **设计可进入实施计划；成品尚未评分** |

## 参考仓库的关键优势

参考实现的成品质量不来自一个 CSS 主题，而来自布局目录、图表语义、容量合同、代表页、整册缩略图检查、HTML/PDF 双媒介审查和独立复核共同作用。它拥有 38 个布局、6 个 master、三套主题、两种比例和广泛的图表 form，并保存官方 showcase。

## 原设计的主要缺口

1. 只有 12 类组件，没有 A4 专属布局图谱，容易得到统一但机械的卡片报告。
2. 排印只有方向性描述，没有字体、字号、行距、边距、基线、中文禁则和跨页规则。
3. 图表只要求统一风格，没有 relationship → form、排序、基线、标签、预测/估计和容量合同。
4. 黄金样板放在实施末期，工程结构会先于审美标准固化。
5. 像素回归只能发现变化，不能证明美感；缺少与参考成品的人工对标。
6. `report.json`、分页引擎、coverage manifest 和 out-deck 能力保留没有可执行合同。
7. 对 panel 丢失的原因描述不准确：桥接完整，风险在手写页面没有全部渲染。

## 已写入设计的修订

- 明确 `out-deck` 继续直接消费 `slides.json`，避免 deck 专属信息往返丢失。
- 增加 `report.schema.json` 版本、集合级覆盖、稳定错误码和三次确定性构建。
- 增加 A4 Layout Atlas、form catalog、排印合同、装订规则和整册 Art Direction。
- 采用锁定 Chromium 的两阶段显式分页，生成 pagination manifest。
- 锁定 out-deck 的 38 layouts、6 masters、三主题、两比例和上游 QA 合同。
- 把官方 showcase 子集纳入有 commit、许可证和 hash 的视觉基准供应链。
- 把 12–20 页黄金小册提前到组件实现之前。
- 增加逐页 PDF、逐章 contact sheet、标题链和 100%/缩略图双尺度审查。
- 增加八维 1–5 分锚点和匿名 A/B；新成品必须“不劣于”参考，且每维至少 4/5。

## Remaining Risk

设计现在足以约束实现，但尚无真实 A4 页面，不能把 32/40 误写成视觉成品已经达到参考水平。第一个不可跳过的实施里程碑是黄金小册，而不是 schema 或 renderer。只有用户批准黄金小册、匿名 A/B 通过、六类场景整册验证完成后，才能声称最终效果达到目标。

## Questions to Consider

- 黄金小册应优先用 AIDC 真实内容，还是另做一份覆盖更多组件的中性咨询案例？
