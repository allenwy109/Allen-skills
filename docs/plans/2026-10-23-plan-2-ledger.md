# 计划 2：统一证据账 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 定稿证据账、slides、sidecar 三个 schema，实现证据账读写模块，并让 core-evidence 改用新证据账。

**Architecture:**
- 三个 schema 用同一种简单的自定义格式（`tools/lib/schema/*.schema.json`），由只用标准库的 `tools/lib/schema_check.py` 校验。
- `tools/lib/ledger.py` 负责证据账（每张表一个 JSONL 文件）的编号、加锁、备份、事务写入、局部修改、子代理暂存合并、检查和渲染。
- core-evidence 的 SKILL.md、来源分级、证据账说明改用新的字段和关口规则。
- validate.py 负责检查 schema 自身，以及文档里写的字段名和枚举值都在 schema 中。

**Tech Stack:** Python 3 标准库（json、re、fcntl、unittest）。

**依据：** 设计 §3（全部）、§5.3 slides.json 扩展、§12 第 2 步；共用约定见路线图。

**关于本计划的写法：** 本计划的全部代码先在仓库的临时副本里写好并跑通（93 个单元测试通过、validate 0 个错误），然后才写成本文档。为了避免文档和代码两份内容对不上，代码以各任务提交的文件为准，本文档写明每个任务的文件、要点、测试和预期结果。执行时每个任务都要在仓库里重新运行测试，确认通过后再提交。

**本计划不做：**
- 快照文件头与 sources 的一致性检查：快照格式在计划 6（core-research）定义，到时再加进 `ledger check`。
- 渲染 `07_storyline/02_info_cards.md`：放在计划 5（core-storyline）。
- 转换成引擎格式（`ledger export`）：放在计划 4（输出层的转换脚本）。
- 其他 skill（core-synthesis、core-review、各 scene）里 `03_evidence.md` 路径的改动：放在计划 8 统一接线。在此之前，这些 skill 还没有安装到 `~/.claude/skills`，不会影响使用。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `tools/lib/schema/ledger.schema.json` | 证据账 17 张表的字段、枚举（60 个，带中文名）、条件必填、相对上游的改名或合并理由 |
| `tools/lib/schema/slides.schema.json` | `07_storyline/slides.json` 的结构 |
| `tools/lib/schema/sidecar.schema.json` | `07_storyline/sidecar.json` 的结构（讲者备注、备用页、确认点） |
| `tools/lib/schema_check.py` | 校验器：字段类型、枚举、正则、范围、未登记字段、条件必填；schema 自检 |
| `tools/lib/ledger.py` | 证据账读写、合并、检查、渲染，以及命令行 |
| `tools/tests/test_schema_check.py` | 校验器测试（12 个） |
| `tools/tests/test_ledger.py` | 证据账测试（34 个） |
| `tools/tests/test_validate.py`（修改） | 新增 2 个测试 |
| `tools/validate.py`（修改） | 第 6 项检查：schema 自检，以及 core-evidence 文档里的字段名、枚举值 |
| `core-evidence/SKILL.md`（修改） | 标签、输出、核实关口（设计 §3.4）、新增第 8 节"证据账怎么写" |
| `core-evidence/references/source-tiers.md`（重写） | 统一的来源评价规则（设计 §3.3） |
| `core-evidence/assets/evidence-ledger-template.md`（重写） | 由表格模板改为证据账使用说明 |
| `core-evidence/references/freshness.md`（修改一句） | "台账备注"改为对应字段 |

---

### Task 1: schema 校验器与三个 schema

**Files:** `tools/lib/schema_check.py`、`tools/lib/schema/ledger.schema.json`、`slides.schema.json`、`sidecar.schema.json`、`tools/tests/test_schema_check.py`

**要点：**
- **字段类型**：string、integer、number、boolean、date、datetime、array、object、map。
  - date 允许精度只到年或月（尽调优化 3）；datetime 必须带时区。
  - 缺失和 null 等价；必填的字符串不能是空白。
  - 出现未登记的字段就报错（与上游"拒绝未知列"一致）。
- **ledger schema 的 17 张表**：project、sources、evidence、claims、claim_evidence、metrics、cards、entities、relations、research_reports、coverage、conflicts、gaps、risks、scorecard、search_log、reviews。
  - 字段取三份清单的并集，每张表的 `changes` 写明相对上游的改名、合并或删除及理由。
  - 已用脚本逐列核对：尽调 13 张表的每一列、深度研究快照头的 21 个字段，都能对应到 schema 里的字段或写明的改名。
- **slides schema**：上游的 slides.json 结构，加上设计 §5.3 的逐页引擎字段。thinkcell 图表 spec 是嵌套 JSON，所以改为引用 `07_storyline/charts/*.json` 文件（`chart_spec_file`）。
- **sidecar schema**：讲者备注、备用页（含触发条件和拉回主线的方式）、确认点状态。

- [ ] **Step 1: 写测试 `tools/tests/test_schema_check.py`，运行确认失败**

Run: `python3 -m unittest tools.tests.test_schema_check`
Expected: `ImportError`（schema_check 不存在）

- [ ] **Step 2: 写 `schema_check.py` 和三个 schema 文件，运行测试**

Run: `python3 -m unittest tools.tests.test_schema_check -v`
Expected: 12 个测试全部 ok，其中 `test_repository_schemas_are_clean` 证明三个 schema 自检干净。

- [ ] **Step 3: 提交** `feat(schema): add ledger, slides and sidecar schemas with validator`

### Task 2: ledger.py

**Files:** `tools/lib/ledger.py`、`tools/tests/test_ledger.py`

**要点：**
- **编号**：
  - 来源用研究线字母加 3 位数字（U、M、A、B……，不能用 C），用尽后扩到 4 位；
  - 其余表按 `id_pattern` 自动推出前缀和位数（如 `ev-0001`）。
- **写入**：
  - 加锁（`fcntl.flock`）；原文件备份到 `.backup/`，每张表最多保留 20 份；写临时文件后用 `os.replace` 原子替换；
  - add 校验整条记录；
  - patch 只改给出的字段，传 None 表示删除该字段，然后校验合并后的记录；不能改 id；
  - 校验失败时文件保持不变。
- **merge**：
  - 读取 `staging/<研究线>/`。来源保留原 ID，其余表重新编号，并改写暂存记录之间的引用；
  - 同一 URL 且第一个原件哈希相同的来源，标为 `duplicate_of`；
  - 来源 ID 与已有记录冲突时拒绝合并，暂存目录保留不动。
- **check**：先做 schema 校验、id 唯一、引用存在，再做语义检查：
  - 证据属性与主张身份匹配；
  - 无法读取的来源不能形成证据；
  - 历史时点研究里，事后资料不能用来支持或反驳结论；
  - 跨主体的支持必须写 bridge，且主张为 estimate；
  - 已推翻的主张必须有 contradicts 证据；有冲突的主张必须在冲突表登记；
  - 关键或重要的主张必须影响结论；
  - 卡片规则（指定类型的 A/B 卡必须关联主张、A/B 卡必须写含义、A 卡关联的主张必须影响结论、A 卡不能"确认不用"、C 卡不能进交付物、没关联主张的卡片要自带性质和可信度）；
  - 指标规则（value 和 formula 二选一、有值的指标必须有值、缺失的指标不能填值、公式不能循环）；
  - 关系规则（不能自己控制自己、生效区间左闭右开、现行且已核实的控制关系不能有环、共同控制是否算控制可配置）；
  - 研报三个"最新"指针双向一致；
  - 日期先后顺序；来源字段不能自引用。
- **render**：生成 `03_evidence/ledger.md`（各表记录数、主张、未关闭的缺口、未处理的冲突）、`notes/<研究线>.md`（按上游证据块格式）、`search-logs/<研究线>.md`。
- **命令行**：init、check（`--json`；有错误时以 1 退出）、render、merge、next-id。参数错误或证据账错误以 2 退出。

- [ ] **Step 1: 写测试 `tools/tests/test_ledger.py`，运行确认失败**

Run: `python3 -m unittest tools.tests.test_ledger`
Expected: `ImportError`

- [ ] **Step 2: 写 `ledger.py`，运行测试**

Run: `python3 -m unittest tools.tests.test_ledger -v`
Expected: 34 个测试全部 ok。

- [ ] **Step 3: 变异检查（证明测试不是空跑）**

临时把"有冲突必须登记"和"C 卡不能进交付物"两条规则改成 `if False:`，重新运行测试，应有 3 个失败（两条规则各自的测试，加上依赖其中一条的命令行测试）；复原后全部通过。

- [ ] **Step 4: 提交** `feat(ledger): add unified evidence ledger with checks and rendering`

### Task 3: validate.py 第 6 项检查

**Files:** `tools/validate.py`、`tools/tests/test_validate.py`

**要点：**
- 对 `tools/lib/schema/*.schema.json` 逐个做自检。
- core-evidence 的 SKILL.md 和 references 里，用反引号写出的小写词，必须是 ledger schema 的字段名、表名、枚举值，或 ledger.py 的子命令。这样文档和 schema 不会各说各的（设计 §3.2 的"唯一枚举源"）。

- [ ] **Step 1: 加两个测试**（文档里出现未知的词时报错；schema 引用了不存在的枚举时报错），运行确认失败
- [ ] **Step 2: 修改 validate.py，运行**

Run: `python3 -m unittest tools.tests.test_validate -v && python3 tools/validate.py | tail -1`
Expected: 5 个测试 ok；`错误 0 个`。（Task 4 改写文档之前，旧文档里没有反引号写出的字段名，所以这里也应为 0。）

- [ ] **Step 3: 提交** `feat(validate): check schemas and ledger vocabulary in core-evidence docs`

### Task 4: core-evidence 改用新证据账

**Files:** `core-evidence/SKILL.md`、`references/source-tiers.md`、`references/freshness.md`、`assets/evidence-ledger-template.md`

**要点：**
- **SKILL.md**：
  - description 和输出改为 `03_evidence/` 统一证据账；正文引用改为 `[cl-0003]` 或 `[M004 p12]`；
  - 第 1 节：标签改为主张的 kind 和来源的 origin；用户材料里的说法初始为未核实；
  - 第 6 节：换成设计 §3.4 的判定标准（合格来源）和关口表（冲突的处理保留原规则），加上用户确认的规则和 `ledger.py check` 的作用；
  - 新增第 8 节"证据账怎么写"；
  - 第 7 节（交给 zerox-deep-research）暂不改动，到计划 6 再改。
- **source-tiers.md**：tier、grade、access、origin 四个字段的含义；S–D 五级等级及与旧 A/B/C 的对应关系；访问程度规则；独立性规则；每个来源查四项；数字口径。
- **evidence-ledger-template.md**：由表格模板改为证据账使用说明（命令行与 Python 写法）。

- [ ] **Step 1: 改写四个文件**
- [ ] **Step 2: 运行**

Run: `grep -rn "台账" core-evidence || echo 没有残留; python3 tools/validate.py | tail -1`
Expected: `没有残留`；`错误 0 个`。

- [ ] **Step 3: 提交** `docs(core-evidence): switch to unified evidence ledger`

### Task 5: 整体检查与收尾

- [ ] **Step 1:** `tools/selftest.sh --quick` → 单元测试 93 个全部 OK，validate 0 个错误
- [ ] **Step 2:** 按设计 §8.2 自审（用户要求本会话不使用子代理），把审查记录写进 `docs/plans/2026-10-23-plan-2-review.md`，并更新路线图的状态
- [ ] **Step 3: 提交** `docs(plans): complete plan 2 ledger`
