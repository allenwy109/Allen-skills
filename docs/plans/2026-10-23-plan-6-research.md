# 计划 6：core-research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 依据能力清单（`inventory/deep-research.md` A–H 节）从零写 core-research：能力盘点、七个阶段、规则、并行分工、封包；`research.py` 的采集、检查、封包、轻量包、断点续跑（含 H 节 10 项优化）。证据写进统一证据账，研究包是封包时生成的独立副本。顺带完成两项附带改动：`ledger check` 核对快照头与 sources 一致（设计 §3.2）；core-evidence 第 7 节改为交给 core-research。

**依据：** 设计 §3.2、§5.1、§8.3。写法同计划 2–5。不复制上游文字和代码（设计 D3）。

## 开发中的发现与取舍

1. **任务文件夹和研究包用同一套检查**：两种输入先归一成同一个模型（快照、索引、证据摘录、检索日志、数据、报告、状态声明），再跑同一组检查函数。
2. **数据和方法的路径基准取 `03_evidence/`**：任务文件夹里 method 写 `analysis/x.md`、数据集写 `data/extracted/x.csv`，与包内路径完全相同，封包时不用改写（设计原文写的是从 `03_evidence/analysis/` 改写为 `analysis/`，效果相同、更简单）。只有用户材料目录在包里改名为 `raw/user-provided/`，报告里的链接去掉 `../03_evidence/` 前缀。
3. **研究包快照用我们的枚举值**（access、capture_method 等，下划线写法），不回退到上游的连字符写法，保持"唯一枚举源"。
4. **快照头一致性由 `ledger check` 负责**（唯一实现），研究检查读取证据账检查的错误，不重复实现。
5. **封包分两步**：人工复核必须在暂存副本上做、并绑定副本的内容指纹，所以 `--prepare` 组装并打印指纹，复核人登记 reviews 后再 `--publish`。
6. **本地文件登记 `file:<文件名>` 作为 url**（证据账要求联网来源有 url）；GBK 页面按超集 GB18030 解码。
7. **浏览器存档的测试自己起一个无头 Chrome**（随机端口），不碰用户 9222 端口上的浏览器。
8. 变异检查发现最初没有测试"摘录片段必须按原顺序出现"，已补。

## 文件

| 文件 | 职责 |
|---|---|
| `tools/lib/ledger.py`、`tools/tests/test_ledger.py`（+1） | 快照头与 sources 一致性检查 |
| `core-research/scripts/research.py` | 命令行：init、resume、capture、check、seal、lite |
| `core-research/scripts/rcapture.py` | 采集 |
| `core-research/scripts/rcheck.py` | 检查（任务文件夹、研究包、轻量包）、内容指纹、写清单 |
| `core-research/scripts/rseal.py` | 封包（prepare、publish、修订、精简） |
| `core-research/scripts/tests/test_research.py`（39）、`research_fixture.py` | 测试与夹具（本地 HTTP 服务、虚构研究任务） |
| `core-research/SKILL.md`、`references/`（research-types、search、archiving、data-package、qa）、`assets/templates/`（brief、plan、subagent-task、report、data-readme） | 说明与模板 |
| `core-evidence/SKILL.md` | 第 7 节和描述改为 core-research |
| `core-review/references/reviewer-prompts.md` | 新增"研究包红队" |

## 任务与预期结果

- [ ] **Task 1 快照头一致性**：`python3 -m unittest tools.tests.test_ledger` → 36 个通过。
- [ ] **Task 2 研究工具**：`ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s core-research/scripts/tests -t core-research/scripts/tests` → 39 个通过。覆盖：
  - 采集：HTML 转 Markdown 与元数据候选、逐个原件哈希、响应头；GBK；付费墙登记为 metadata_only；谈论付费墙的长文不误拦；403 不登记；5xx 重试；超限与截断；纯文本、二进制、两页 PDF 的页码；ID、slug、用户材料；轻量包；浏览器存档（HTML + 截图）。
  - 任务文件夹检查：夹具通过；摘录篡改、原件哈希、未登记原件；摘录片段顺序；快照头为真源；检索状态双向一致；检索日志弱检查；缺失不能填 0；数值口径；有限数；记录重复；血缘缺失与循环；提取层与整理层互斥；method 位置；字典与孤立表；数据状态一致；正文引用（区间、年份、行内代码）；未引用条目与零覆盖；参考链接与快照对应；数据关联；关键主张弱检查；符号链接；任务文件夹不能 --final。
  - 研究包：封包发布与 --final、ZIP、shasum 校验、快照补齐评价字段、链接改写、验收登记；没有当前复核不能发布、复核过期；发布后篡改（README 哈希、未覆盖文件、复核过期）、已封包拒绝再封；sources.md 与快照不一致、旧布局；legacy 包；修订版与精简；`--review-digest` 命令行。
- [ ] **Task 3 说明、模板与附带改动**：`python3 tools/validate.py` → 0 个错误（19 个 skill）。
- [ ] **Task 4 收尾**：`tools/selftest.sh` 全部通过；审查记录；路线图。
