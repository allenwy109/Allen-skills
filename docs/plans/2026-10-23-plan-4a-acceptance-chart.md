# 计划 4a：统一验收与出图表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立统一验收（acceptance.json 与唯一状态规则）、统一输出标准和成品审查员，并完成第一个输出 skill out-chart（图表）。

**为什么拆成 4a、4b、4c：** 设计 §12 第 4 步含三个引擎、统一验收、转换脚本和映射表，一份计划装不下。4a 做验收机制和最简单的图表引擎；4b 做海报（out-poster）；4c 做报告（out-report）。

**写法：** 与计划 2、3 相同，代码先在临时副本里写好并跑通，本文写任务、要点、测试和预期结果。

**依据：** 设计 §6.1–§6.3、§8.3、§10、§11、§12 第 4 步。

## 开发中的发现

1. **thinkcell 导出 PNG 时中文消失**（计划 3 已预见）：引擎直接调用 PATH 里的 `soffice`。解决：新增 `tools/bin/soffice` 包装脚本，出图时放在 PATH 最前面，由它带上中文字体再调用真正的 LibreOffice。引擎代码不改，用户的 LibreOffice 设置不受影响。实测对比：用包装脚本时 OCR 能完整读出中文标题；不用时标题整段消失。
2. **tc_validate 的致命问题级别叫 `fatal`**，不是想当然的 `fail`。端到端测试（不平的瀑布图）发现了这个问题：校验没有拦下，走到渲染一步才被引擎自己挡住。现在同时按 `fatal` 级别和整体结论"不能做"两处判断。

## 文件

| 文件 | 职责 |
|---|---|
| `tools/lib/metrics.py` | 指标取值（与报告引擎同一套公式和半入规则）；判断指标能否进成品 |
| `tools/lib/schema/acceptance.schema.json`、`tools/acceptance.py` | 验收记录：登记、写入审查、标记夹具、检查（含文件哈希复检）；唯一的状态规则 |
| `tools/bridge/to_thinkcell.py`、`tools/bridge/MAPPING.md` | 图表 spec → 引擎输入；映射表的公共规则和 thinkcell 一节 |
| `tools/bin/soffice`、`tools/lib/office.py`（加 `passthrough`，`soffice_path` 跳过包装脚本） | 带中文字体的 soffice |
| `out-chart/SKILL.md`、`out-chart/scripts/out_chart.py` | 出图表：转换 → 校验 → 渲染 → 登记验收 |
| `core-review/references/output-standard.md` | 统一输出标准（8 项）、状态规则、成品审查员 |
| `core-review/SKILL.md`、`references/reviewer-prompts.md`、`assets/review-log-template.md` | 第 5 个角色"成品审查员"；问题编号改为 RV-0001 |
| `tools/tests/fixtures.py` | 虚构公司"星河数据科技"的证据账夹具与工具检查（4b、4c 复用） |
| 测试：`tools/tests/test_metrics.py`（5）、`test_acceptance.py`（9）、`test_bridge_thinkcell.py`（6）、`out-chart/scripts/tests/test_out_chart.py`（5） | |

## 任务与预期结果

- [ ] **Task 1 指标与验收**：先写测试并确认失败，再实现。验收状态规则的每个"不通过"条件（5 个）和"有条件通过"条件（5 个）都有用例。
  - Run: `python3 -m unittest tools.tests.test_metrics tools.tests.test_acceptance` → 14 个通过。
  - 变异检查：去掉"尚未经过成品审查"这条规则，应有 4 个失败。
- [ ] **Task 2 转换与映射表**：Run: `python3 -m unittest tools.tests.test_bridge_thinkcell` → 6 个通过。
  - 变异检查：不再拦截裸数字，应有 2 个失败。
- [ ] **Task 3 out-chart 与 soffice 包装**：
  - Run: `ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s out-chart/scripts/tests -t out-chart/scripts/tests` → 5 个通过。覆盖：三种格式产出；PNG 经 OCR 能读出中文标题；验收先为"不通过（尚未审查）"，审查后"通过"，改动文件后"不通过"；不平的瀑布图被引擎校验拦下且不出图；裸数字在转换阶段就被拦下。
  - 人工：成品审查员实际看过 PNG，中文标题、单位、来源完整。
- [ ] **Task 4 core-review**：输出标准、成品审查员角色和提示词、审查记录模板。`python3 tools/validate.py` → 15 个 skill，0 个错误。
- [ ] **Task 5 收尾**：`tools/selftest.sh` 全部通过；写审查记录；更新路线图。
