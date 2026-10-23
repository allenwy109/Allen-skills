# 计划 5：core-storyline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 依据能力清单（`inventory/storyline.md` A–J 节）从零写 core-storyline：七个阶段、四种用法、卡片、故事线方法、内容稿、拆页、审计，以及 `storyline.py` 的机器检查（含设计 §5.3 的 10 项优化）；out-report 把故事线检查作为前置条件，用完整故事线包重跑计划 4 的报告任务。

**依据：** 设计 §5.3、§6.2、§8.3。写法同计划 2–4。不复制上游文字和代码（设计 D3）。

## 开发中的发现

1. **卡片安置只认 04 正文和 06 的正文、可视化建议、讲者备注**（设计 §5.3 优化 5），所以逐页稿的正文和备注里要直接写卡片引用；`sync` 同步到 slides.json 和 sidecar 时机械删掉引用，讲者备注交付物里不出现卡片编号。
2. **slides.json 的文字字段和判断字段分开维护**：页面类型、行动标题、正文、讲者备注、来源、追溯以 06_slides.md 为准，由 `sync` 同步；page_role、panels 等引擎字段由作者写在 slides.json，`sync` 不动。检查脚本重新同步一遍并比对，防止两边走样。
3. **判断类标记要紧挨数字才降级**（优化 3）：句子里有判断词但离数字远，或没写依据，都按错误处理，并给出"要紧挨数字并写明依据"的具体提示。
4. **备用页数量**：设计把"备用页 ≥3"列为机检规则，能力清单又写阅读型可选。脚本对演讲型报错、阅读型只提示。
5. 夹具执行摘要里原有一句没有证据的同行比较，按删词和保真规则删掉——夹具不示范坏写法。

## 文件

| 文件 | 职责 |
|---|---|
| `core-storyline/SKILL.md` | 能力盘点、四种用法、七个阶段与闸门、铁律、不变量、停止、迭代 |
| `core-storyline/references/`：cards、storyline-method、manuscript、slides、audit | 各阶段的方法和规则 |
| `core-storyline/assets/templates/` 7 个模板 | 00、01、03、04、05、06、07 |
| `core-storyline/scripts/storyline.py` | cards、clean、sync、impact、check |
| `tools/tests/fixtures.py` | `make_storyline_package`：完整的故事线包 |
| `core-storyline/scripts/tests/test_storyline.py`（32） | 测试 |
| `out-report/scripts/out_report.py`、`SKILL.md`、`tests/test_out_report.py` | finish 增加故事线检查；端到端改用故事线包 |

## 任务与预期结果

- [ ] **Task 1 storyline.py**：`python3 -m unittest discover -s core-storyline/scripts/tests -t core-storyline/scripts/tests` → 32 个通过。覆盖：完整包通过；按阶段检查；06 先要有 05；仅内容稿模式；简报 7 项、材料未处理和长文档、来源 ID、主线确认点；02 视图过期；性质由主张推出、术语表并入；A 级校准和跳号；派生卡；A 卡只在审计、只在故事线、没有去向，来源字段不算安置；C 卡和悬空引用；库外数字；四舍五入、量级换算、符号翻转；判断标记紧挨并写依据；引错卡和未引注；附录不报未引注；日期、区间、小整数；含义里的数字不进事实库；逐页数字和 --no-numbers；单位识别；清洁版；执行摘要；必备章节和删词；标题长度、页面类型、结尾页；演讲型备用页和页数上限；arc 与故事线模式；sync 漂移；备用页的触发和拉回；命令行输出；影响分析。
- [ ] **Task 2 说明与模板**：`python3 tools/validate.py` → 0 个错误（18 个 skill）。
- [ ] **Task 3 out-report 接入**：`ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s out-report/scripts/tests -t out-report/scripts/tests` → 5 个通过；前置检查 7 项全部通过，第一项是故事线检查；写入独立审查结论后为"通过"。
- [ ] **Task 4 收尾**：`tools/selftest.sh` 全部通过；审查记录；路线图。
