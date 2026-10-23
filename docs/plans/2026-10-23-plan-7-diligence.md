# 计划 7：core-diligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 依据能力清单（`inventory/due-diligence.md` A–L 节）从零写 core-diligence：范围确认、十个阶段、三种完成状态、硬规则、18 个模块、上市研报流程、目的手册、来源与访谈、行业适配、报告内容契约、质量门槛；`diligence.py` 的推导和检查；`tools/bridge/diligence_to_manuscript.py` 把尽调内容转成故事线母版，尽调报告和其他报告走同一条链路（core-storyline 拆页 → out-report）。一个虚构公司的尽调走完报告链路，验收为通过。

**依据：** 设计 §5.2、§6.2、§8.3。写法同计划 2–6。不复制上游文字和代码（设计 D3）。

## 开发中的发现与取舍

1. **数据层在计划 2 已经就绪**：project、entities、relations、research_reports、coverage、risks、scorecard、reviews 等表和大部分硬规则（控制环、覆盖指针双向一致、集团数据桥接、事后资料隔离、推翻规则、条件必填）已由证据账检查负责；本计划只补跨表推导和尽调专属的语义检查。
2. **22 条人工清单的内容清单原文没有列出**，按 I 节的质量门槛自己定义为 D01–D22（写进 `references/quality.md` 和 `dcontent.MANUAL_ITEMS`），结果记在 reviews 表（type=diligence_manual）。
3. **内容块 ID** 用"章节 ID-序号"；拆页后复核靠 slides.json 已有的 `block_ids` 字段，转母版在每个块前写 `<!-- block:ID -->`。
4. **转母版时补登主张**：同一证据被多个块引用时只补登一次（内存里的关联表要随写入更新，第一版漏了这点，会重复补登）；指标卡和图表的数值同时登记为证据账指标，否则报告转换时追溯不到。补登主张的期间、单位取自证据，限制按来源等级写清是公司自述还是原始文件。
5. **故事线目录里的简报文件名改为 `00_story-brief.md`**（设计 §3.1 的写法，避免与任务根目录的路由简报混淆）。计划 5 实现成了 `00_brief.md`，本计划一并改正。
6. **故事线检查的数字规则调整**：句子只按 。！？ 切分（"；"分句会让引用只覆盖最后一个分句，误报"未引用"）；剔除主体、主张、证据、来源等编号，不当数字。转母版把卡片引用放在句末标点之前。
7. **report-forge 的长度规则提前拦**：panel 选型理由 ≥12 字、用途 ≥8 字、adds ≥12 字、关系理由 ≥12 字等，引擎要到执行清单的 analysis 项才报，现在转换前检查就拦下。
8. **研报门槛不依赖联网标志**（优化 5），最新指针改为数组（优化 7），事件绑定到具体主体（优化 4），共同控制可配置并给警告（优化 2），关系图不再限 6 个节点（优化 9）。
9. out-report 的 finish 对尽调报告加查 3 项：尽调检查、内容契约（拆页后复核与人工清单）、完成状态（partial、limited 记为有限完成）。

## 文件

| 文件 | 职责 |
|---|---|
| `core-diligence/scripts/diligence.py` | 命令行：init、sync、status、plan、ratios、score、check、check-content、audit |
| `core-diligence/scripts/dcore.py` | 上市追溯、必读类别、候选研报与最新指针、覆盖状态、研报门槛、同步覆盖、语义检查、研报检查、完成条件 |
| `core-diligence/scripts/dratios.py`、`dscore.py`、`dplan.py`、`dcontent.py`、`daudit.py` | 财务比率、评分、检索计划、报告内容契约、底稿 |
| `tools/bridge/diligence_to_manuscript.py` | 尽调内容 → 故事线母版 |
| `core-diligence/SKILL.md`、`references/`（modules、listed-research、purposes、sources、interviews、industry、report-content、quality）、`assets/templates/`（report-content.json、financial-input.json、request-list.md、interview-outline.md） | 说明与模板 |
| `core-diligence/scripts/tests/`：test_diligence.py（36）、test_pipeline.py（8）、diligence_fixture.py、gen_pages.cjs、fixture_page.css | 测试与虚构夹具 |
| `core-storyline/`（简报改名、数字规则）、`tools/bridge/to_forge.py`（长度规则）、`out-report/scripts/out_report.py`（尽调检查）、`core-review/references/`（尽调专项、提示词）、`tools/bridge/MAPPING.md` | 配套改动 |

## 任务与预期结果

- [ ] **Task 1 配套改动**：简报改名、故事线数字规则、to_forge 长度规则 → `core-storyline` 32 个、`tools/tests` 139 个测试通过。
- [ ] **Task 2 尽调工具**：`python3 -m unittest discover -s core-diligence/scripts/tests -t core-diligence/scripts/tests -p test_diligence.py` → 36 个通过。覆盖：上市追溯（已核实控制触发；拟议、区间外、参股不触发；身份、未核实边、控制链未核对时 pending；共同控制可配置；退市窗口）；必读类别、事件、可比、豁免；覆盖状态三档、同日多份、被替代和基准日后排除、事后资料、事件覆盖；门槛不依赖联网；同步覆盖；完成条件；完成态的模块文件和复查时间；语义错误；身份不一致；财务比率（核心、新增、缺失与近似、跑道、同比可比、序列、结构、阈值、输入校验）；评分（状态、发布与不足、无效行与发布分不一致）；内容契约（图型规则、属性、关系图、图片安全、跨块、结构、编排提示、拆页后复核、人工清单）；检索计划裁剪；底稿节数与模块错误。
- [ ] **Task 3 转母版与端到端**：`ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s core-diligence/scripts/tests -t core-diligence/scripts/tests` → 44 个通过（约 16 秒）。端到端：尽调完成态 → 转母版 → 拆页 → 故事线检查零错误 → 拆页后复核 → out-report 10 项前置检查全部通过 → 写入独立审查后为"通过"。
- [ ] **Task 4 说明与模板**：`python3 tools/validate.py` → 0 个错误（20 个 skill）。
- [ ] **Task 5 收尾**：`tools/selftest.sh` 全部通过；审查记录；路线图。
