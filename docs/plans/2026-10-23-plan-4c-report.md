# 计划 4c：出正式报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成 out-report：slides.json + 证据账 → report-forge 蓝图（转换前检查），经统一入口 `report.cjs` 走完设计 §6.2 的 17 步，交付 HTML、PDF、讲者备注并登记统一验收。

**依据：** 设计 §6.2 out-report、§6.3、§8.3。写法同计划 2–4b。

## 开发中的发现

1. **上游没有 `kind=report` 的完整流程测试。** 我们先在临时目录用手写蓝图把 `kind=report + narrative-focus-1 + editorial + 独立审查` 走通 17 步，再据此写转换脚本。
2. **narrative-focus-1 要求每个正文页都有组合证据计划**（`exhibit.semantics.composition`：panel 的用途、主张、形式、选型理由；多个 panel 的 relations），以及每页显式的 subtitle、cornerLabel、speakerIntent。slides.json 原来没有这些字段，schema 升到 1.1.0：deck 加 brief、answer_claim_refs、cover，页面加 subtitle、panels、relations、anchor_panel。这些是拆页时的判断，由 core-storyline 写，转换脚本不硬凑。
3. **引擎 ready 校验有缝隙**：自定义布局的 slot 名称到 compile 才报错。转换脚本提前拦下 slot、panel 主张不属于本页、主展品不唯一三类。
4. **规划观察必须覆盖蓝图的每一页**（含封面、封底）；首尾页模板没有 `data-frame-boundary`，装配会拒绝，生成首尾页时补 `space`。
5. **引擎会把审查员填写的收束句和页面实际文字比对**，两页收束句相同也会被拦——审查稿没法照抄蓝图。
6. **引擎会在待确认主张前加"假设："**。设计写的"待确认："前缀会叠成"假设：待确认：……"，改为句尾"（待确认）"。
7. **装配器按蓝图重填所有绑定节点的文字**，所以作者写错的数字和身份标签会被纠正；没有绑定的手写文字（图注、坐标标签）不经过引擎，finish 时用数字回查补上这一环。
8. macOS 临时目录 `/var` 是符号链接，引擎用真实路径比对 task 和 HTML；包装脚本里任务目录一律先解析。

## 文件

| 文件 | 职责 |
|---|---|
| `tools/lib/schema/slides.schema.json` | 1.1.0：报告引擎需要的字段 |
| `tools/bridge/to_forge.py` | 转换前检查与蓝图生成 |
| `tools/bridge/poster_numbers.py` | 新增 report 模式：只查正文页里没有绑定的文字 |
| `tools/bridge/MAPPING.md` | 新增 report-forge 一节 |
| `tools/tests/fixtures.py` | `make_report_ledger`、`report_slides`、`report_sidecar` |
| `out-report/SKILL.md`、`out-report/scripts/out_report.py` | init、refresh、plan、step、finish |
| `tools/tests/test_bridge_forge.py`（12）、`test_poster_numbers.py`（+1）、`out-report/scripts/tests/test_out_report.py`（5） | 测试 |
| `out-report/scripts/tests/synthetic.py`、`fixture_body.html`、`fixture_page.css` | 测试专用的合成观察与审查（写明"合成"）、虚构正文页 |

## 任务与预期结果

- [ ] **Task 1 slides.json 1.1.0**：`python3 tools/validate.py` → 0 个错误；原有单元测试 125 个通过。
- [ ] **Task 2 转换脚本**：`python3 -m unittest tools.tests.test_bridge_forge` → 12 个通过。覆盖：身份和核实状态映射、指标与公式输入、近似值说明不暴露指标编号、数字换成指标引用、待确认和被推翻的改写、用户材料为 provided、裸数字、放行、副标题和讲者备注里的数字、不能呈现的主张、缺失指标上页、引擎晚报的结构问题、缺少报告字段、A 级卡片未上正文。
- [ ] **Task 3 报告模式的数字回查**：`python3 -m unittest tools.tests.test_poster_numbers` → 6 个通过（只查正文页里未绑定的文字；封面日期、绑定的数字、年份不计）。
- [ ] **Task 4 out-report**：`ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s out-report/scripts/tests -t out-report/scripts/tests` → 5 个通过，约 15 秒。覆盖：
  - task 字段（report、editorial、narrative-focus-1、independent）和首尾页；
  - 打包前运行 finish 被拒绝；
  - 交付 5 页 PDF、讲者备注，HTML 里有"（待确认）"和"（预测）"，6 项前置检查通过，等待审查；
  - 写入独立审查结论后为"通过"；
  - 有裸数字时 init 被拦下，不建引擎任务。
- [ ] **Task 5 收尾**：`tools/selftest.sh` 全部通过；审查记录；路线图。
