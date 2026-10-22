# 计划 4b：出一页海报 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成 out-poster：给作者准备"可用事实清单"，海报写完后跑引擎检查、截图、登记构建，并对页面上的每个数字做回查。

**依据：** 设计 §6.2 out-poster、§6.3、§8.3 第 1 项。写法同计划 2–4a。

## 开发中的发现

1. **onepager 的 `record-build` 只接受 PASS**，静态检查或渲染检查出现 WARN 也会拒绝登记。上游文档写的是"WARN 写明保留理由即可"，以引擎代码的实际行为为准：警告也要修掉。
2. **上游模板里 BigNumber 的大数字用 `bignum-value`，标签用 `bignum-label`。** 第一版回查把整个 `bignum-item` 当成大数字区域，误伤了标签里的年份；改为只看 `bignum-value`。
3. **引擎检查管不到版面空洞**：测试海报的大数字和正文之间有一大块空白，两项检查都判 PASS。这类问题只能靠成品审查员看图发现，已写进 out-poster 说明的验收重点。
4. 截图默认按 2 倍分辨率输出（A2 为 3840×2160），沿用上游默认值。

## 文件

| 文件 | 职责 |
|---|---|
| `tools/bridge/poster_numbers.py` | 海报数字回查 |
| `tools/bridge/MAPPING.md` | 新增 onepager 一节 |
| `out-poster/SKILL.md`、`out-poster/scripts/out_poster.py` | prepare（建项目、事实清单）与 finish（检查、截图、登记、回查、验收） |
| `tools/tests/test_poster_numbers.py`（5）、`out-poster/scripts/tests/test_out_poster.py`（4）、`fixture_poster.html` | 测试与虚构海报 |

## 任务与预期结果

- [ ] **Task 1 数字回查**：`python3 -m unittest tools.tests.test_poster_numbers` → 5 个通过。覆盖：可追溯的数字、年份和编号、千分位、不能进成品的数字、放行、预测类数字要注明身份、BigNumber 限制。
- [ ] **Task 2 out-poster**：`ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s out-poster/scripts/tests -t out-poster/scripts/tests` → 4 个通过。覆盖：
  - 事实清单只收录能进成品的主张；
  - 完成后得到 3840×2160 的 PNG，5 项前置检查通过，验收等待审查；
  - 页面多出未核实的数字时被拦下且不出图；
  - 页面含 Emoji 时被引擎静态检查拦下。
- [ ] **Task 3 收尾**：`tools/selftest.sh` 全部通过；审查记录；路线图。
