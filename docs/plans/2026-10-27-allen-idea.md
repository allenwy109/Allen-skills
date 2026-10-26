# Allen Idea Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `allen-idea` application that clarifies an early startup idea or technology, compares 2–3 enterprise paths, validates demand and latent competitors, and produces a time-horizon outlook report with a decision grade.

**Architecture:** Add one application Skill and one orchestration Scene while reusing the existing evidence, research, method, review, synthesis, storyline, report, and acceptance layers. Extend `app_runtime.py` with two user-confirmed stages (`clarify`, `pathing`) and a research-first application order; keep confirmations in the existing evidence-ledger `reviews` table rather than creating a second state store.

**Tech Stack:** Markdown Agent Skills, Python 3 standard library, JSONL evidence ledger, `unittest`, Bash installer, existing report runtime.

---

## File map

**Create**

- `allen-idea/SKILL.md` — application contract and routing to the new scene.
- `allen-idea/references/system-prompt.md` — role, evidence boundaries, and decision behavior.
- `allen-idea/assets/app.json` — application metadata.
- `scene-idea/SKILL.md` — clarification, path comparison, demand, competition, and outlook workflow.
- `scene-idea/assets/idea-definition-template.md` — confirmed idea/technology definition.
- `scene-idea/assets/venture-paths-template.md` — 2–3 enterprise-path comparison.
- `commands/claude/allen-idea.md` — Claude command entry.
- `commands/codex/allen-idea.md` — Codex prompt entry.
- `tests/idea-evaluation-cases.md` — reusable behavioral cases and baseline/forward-test record.

**Modify**

- `tools/app_runtime.py` — register the application, stages, confirmation validation, and idea order.
- `tools/tests/test_app_runtime.py` — runtime TDD coverage.
- `router/SKILL.md` — prefer `allen-idea` for pre-company ideas and technologies.
- `router/references/system-prompts.md` — expose the fifth app template.
- `install.sh` — install the fifth command/prompt through the existing glob and update help comments only where counts are named.
- `tools/tests/test_install.py` — assert both platform entries are installed.
- `tools/validate.py` — validate application assets/entries if the current generic checks do not already cover them.
- `README.md`, `INSTALL.md`, `ARCHITECTURE.md` — document the fifth app and its flow.
- `tests/method-selection-cases.md` — add idea-path analysis cases only when they test method choice rather than application behavior.

No evidence-ledger schema change is planned.

## Task 1: Establish behavioral RED cases

**Files:**

- Create: `tests/idea-evaluation-cases.md`

- [ ] **Step 1: Write five baseline scenarios before creating the new Skill**

Create the file with these exact cases and acceptance criteria:

```markdown
# 创业点子评估行为测试

测试时把“用户输入”原样交给未加载 allen-idea 的独立 agent，再用验收项检查输出。基线和前向测试使用同一输入。

| ID | 用户输入 | 必须观察的行为 |
|---|---|---|
| I1 | 我有个用 AI 帮制造企业做质量管理的想法，帮我看看前景。 | 先追问客户、场景和现有做法；不得直接写行业报告 |
| I2 | 我们有低成本机器视觉技术，不确定做工厂质检、零售盘点还是农业分选。 | 保留并比较 2–3 条实质不同路径；不得静默选一个 |
| I3 | AI 陪伴很火，社交媒体讨论很多，应该需求很强。 | 不把热度当购买意愿；寻找实际投入、采购、付费或替代成本证据 |
| I4 | 我没找到同类产品，所以这里一定是蓝海。 | 搜索直接竞品、间接竞品、人工/表格/外包/不处理和邻近进入者 |
| I5 | 某项补贴未来两年很高，适合立刻做。 | 分开判断 0–2、3–5、5–10 年，并区分快钱与长期价值 |

## 验收

- 用户事实、系统假设、外部事实和推演结论可区分；
- 需求强度只写强、中、弱或未证实，并列支持和反面证据；
- 最终等级只能是值得推进、有条件推进、建议调整方向、暂不建议；
- 推荐路径带最小验证实验及成功、失败、停止标准。

## 基线记录

逐项记录未加载 allen-idea 时的输出摘要和违反的验收项，不改写原输出结论。

## 前向测试记录

逐项记录加载 allen-idea 后的输出摘要、通过项和残留问题。
```

- [ ] **Step 2: Run the five cases without `allen-idea`**

Use a fresh independent agent for each case. Do not provide the intended answer or the design document. Give it only the user input and the current repository Skills excluding the not-yet-created `allen-idea` and `scene-idea`.

Expected: at least one case violates an acceptance item; otherwise stop and narrow the proposed Skill because it is not teaching new behavior.

- [ ] **Step 3: Record exact baseline failures**

Append concise observations under `## 基线记录`, including exact rationalizations such as “市场规模说明需求成立” or “没有同名产品所以竞争弱” when they occur.

- [ ] **Step 4: Commit the RED fixture**

```bash
git add tests/idea-evaluation-cases.md
git commit -m "test: add startup idea evaluation scenarios"
```

## Task 2: Add runtime stages and confirmation gates

**Files:**

- Modify: `tools/tests/test_app_runtime.py`
- Modify: `tools/app_runtime.py`

- [ ] **Step 1: Write failing tests for idea order and gates**

Add imports and helpers to `tools/tests/test_app_runtime.py`:

```python
from tools.lib.ledger import Ledger


def confirm_file(task, rel):
    Ledger(task).add("reviews", {
        "type": "user_confirmation",
        "reviewer": "用户",
        "at": "2026-10-27T10:00:00+00:00",
        "covers": {"files": [rel]},
        "conclusion": "已确认",
    })
```

Add these tests to `AppRuntimeTest`:

```python
def test_idea_uses_clarify_pathing_and_research_first(self):
    payload = self.init("allen-idea")
    self.assertEqual(payload["stage"], "intake")
    run = json.loads((self.task / "app-run.json").read_text(encoding="utf-8"))
    self.assertEqual(run["stages"][:6], [
        "intake", "clarify", "pathing", "framing", "research", "method",
    ])

def test_idea_clarify_requires_file_and_user_confirmation(self):
    self.init("allen-idea")
    self.assertEqual(R.advance(self.task)["advanced"], "intake")
    missing = R.advance(self.task)
    self.assertEqual(missing["validation"], "failed")
    self.write("00_idea-definition.md", "# 想法定义")
    missing = R.advance(self.task)
    self.assertIn("confirmation:00_idea-definition.md", missing["missing"])
    confirm_file(self.task, "00_idea-definition.md")
    self.assertEqual(R.advance(self.task)["advanced"], "clarify")

def test_idea_pathing_requires_file_and_user_confirmation(self):
    self.init("allen-idea")
    R.advance(self.task)
    self.write("00_idea-definition.md", "# 想法定义")
    confirm_file(self.task, "00_idea-definition.md")
    R.advance(self.task)
    self.write("00_venture-paths.md", "# 企业化路径")
    missing = R.advance(self.task)
    self.assertIn("confirmation:00_venture-paths.md", missing["missing"])
    confirm_file(self.task, "00_venture-paths.md")
    self.assertEqual(R.advance(self.task)["advanced"], "pathing")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest tools.tests.test_app_runtime.AppRuntimeTest.test_idea_uses_clarify_pathing_and_research_first \
  tools.tests.test_app_runtime.AppRuntimeTest.test_idea_clarify_requires_file_and_user_confirmation \
  tools.tests.test_app_runtime.AppRuntimeTest.test_idea_pathing_requires_file_and_user_confirmation
```

Expected: errors because `allen-idea`, the stages, and confirmation validation do not exist.

- [ ] **Step 3: Add the minimal runtime implementation**

Extend the constants in `tools/app_runtime.py`:

```python
APPS = {
    # existing entries stay unchanged
    "allen-idea": {"title": "创业点子评估", "scene": "scene-idea", "report": "创业点子企业化前景评估报告"},
}

STAGES = {
    # existing entries stay unchanged
    "clarify": {"skill": "scene-idea", "required": ["00_idea-definition.md"]},
    "pathing": {"skill": "scene-idea", "required": ["00_venture-paths.md"]},
    "research": {"skill": "core-research", "required": [
        "03_evidence/ledger/sources.jsonl",
        "03_evidence/ledger/claims.jsonl",
        "03r_research/report.md",
    ]},
}

IDEA_ORDER = [
    "intake", "clarify", "pathing", "framing", "research", "method",
    "analysis", "review", "synthesis", "storyline", "report", "support", "acceptance",
]
```

Select the order explicitly in `init_task`:

```python
if args.app == "allen-bp-review":
    order = BP_ORDER
elif args.app == "allen-idea":
    order = IDEA_ORDER
else:
    order = COMPANY_ORDER
```

Add these focused helpers above `validate_stage`:

```python
CONFIRMED_FILES = {
    "clarify": "00_idea-definition.md",
    "pathing": "00_venture-paths.md",
}


def confirmed_files(task):
    ledger = Ledger(task)
    confirmed = set()
    for review in ledger.read("reviews"):
        if review.get("type") == "user_confirmation":
            confirmed.update(review.get("covers", {}).get("files", []))
    return confirmed
```

Extend `validate_stage` after checking required files:

```python
required_confirmation = CONFIRMED_FILES.get(stage)
if required_confirmation and required_confirmation not in confirmed_files(task):
    missing.append(f"confirmation:{required_confirmation}")
```

Update the module docstring from “四个应用” to “应用入口”.

- [ ] **Step 4: Run runtime tests and verify GREEN**

Run:

```bash
python3 -m unittest tools.tests.test_app_runtime -v
```

Expected: all runtime tests pass, including existing applications.

- [ ] **Step 5: Commit runtime support**

```bash
git add tools/app_runtime.py tools/tests/test_app_runtime.py
git commit -m "feat: add idea evaluation runtime stages"
```

## Task 3: Create application and scene Skills

**Files:**

- Create: `allen-idea/SKILL.md`
- Create: `allen-idea/references/system-prompt.md`
- Create: `allen-idea/assets/app.json`
- Create: `scene-idea/SKILL.md`
- Create: `scene-idea/assets/idea-definition-template.md`
- Create: `scene-idea/assets/venture-paths-template.md`

- [ ] **Step 1: Create the application metadata**

`allen-idea/assets/app.json`:

```json
{
  "id": "allen-idea",
  "title": "创业点子评估",
  "scene": "scene-idea",
  "report_title": "创业点子企业化前景评估报告"
}
```

- [ ] **Step 2: Write the application Skill**

Create `allen-idea/SKILL.md` with this structure and requirements:

```markdown
---
name: allen-idea
description: 评估尚未注册企业、没有完整 BP 的创业想法或技术。用户希望先澄清想法，再比较多种产品、客户或商业模式落地路径，验证真实痛点、需求强度、竞品和未来发展前景时使用。已有明确经营主体且要评估实际经营时使用 allen-company，不使用本入口。
---

# 创业点子与技术企业化前景评估

先完整读取 `references/system-prompt.md`。应用 ID 固定为 `allen-idea`，主场景固定为 `../scene-idea/`，不得重新交给 router 猜场景。

## 启动与控制

L2、L3 必须使用 `<运行时>/tools/app_runtime.py`。先通过多轮提问生成并让用户确认 `00_idea-definition.md`；再生成并确认 `00_venture-paths.md`。确认前调用 `wait`，不得提前研究或写报告。

## 强制覆盖

- 并列比较 2–3 条实质不同的企业化路径；确实只有一条时说明原因；
- 验证真实痛点、需求频率、严重性、紧迫性、现有投入和预算信号；
- 搜索直接竞品、间接竞品、现状替代、邻近进入者和潜在新进入者；
- 分别判断 0–2、3–5、5–10 年前景；
- 区分窗口型快钱、现金流生意、长期复利型、高风险规模赌注和伪机会；
- 给出值得推进、有条件推进、建议调整方向或暂不建议，以及最小验证实验。

## 证据边界

严格区分用户确认、系统假设、外部事实和推演。讨论热度、搜索量和市场规模不能单独证明需求或付费意愿；没有访谈、订单、采购或持续付费证据时，不得声称付费意愿已验证。

## 交付

L2、L3 交付 HTML + PDF 主报告和 `supporting-package.zip`，二者登记进 `acceptance.json` 并接受成品审查。
```

- [ ] **Step 3: Write the system prompt**

Create `allen-idea/references/system-prompt.md` with explicit instructions to ask one high-value clarification at a time, stop clarification only when the definition card can be completed, compare paths before recommending one, search by customer problem rather than product name, and never convert assumptions into facts. Include the four decision grades and five opportunity types verbatim from the design spec.

- [ ] **Step 4: Write both templates**

`scene-idea/assets/idea-definition-template.md`:

```markdown
# 想法定义卡

## 用户已确认的信息
- 技术或想法：
- 目标客户候选：
- 使用场景候选：
- 当前做法与成本：
- 创始人资源：
- 地域与行业范围：
- 不可改变的约束：

## 系统分析假设
| ID | 假设 | 为什么需要 | 如何验证 |
|---|---|---|---|

## 仍未知且可能改变结论的问题
| 问题 | 影响的判断 | 获取方式 |
|---|---|---|
```

`scene-idea/assets/venture-paths-template.md`:

```markdown
# 企业化路径

| 路径 | 目标客户 | 使用场景 | 核心产品 | 价值主张 | 收费方式 | 获客方式 | 关键能力 | 主要假设 |
|---|---|---|---|---|---|---|---|---|
| P1 | | | | | | | | |
| P2 | | | | | | | | |

## 路径差异检查

每两条路径至少在客户、场景、产品形态、商业模式或进入方式上有一项关键差异。若只有一条合理路径，在这里记录原因。
```

- [ ] **Step 5: Write `scene-idea/SKILL.md`**

Keep the scene as orchestration rather than duplicating other Skills. Its sections must be: “先澄清”, “企业化路径”, “研究要求”, “分析与时间前景”, “证据边界”, “审查与交付”. Route research to `core-research` and `core-evidence`, methods to `core-method-select`/`lib-consulting`, and delivery to existing review/synthesis/storyline/report Skills.

Include this competition taxonomy exactly:

```markdown
1. 直接竞品：相近客户、问题和产品；
2. 间接竞品：不同技术或服务解决同一问题；
3. 现状替代：人工、表格、外包、内部系统和“不处理”；
4. 邻近进入者：已有客户、渠道、数据或技术能力的企业；
5. 潜在新进入者：科研成果、开源项目、新融资团队、专利方向和大厂新产品。
```

- [ ] **Step 6: Run structural validation**

Run:

```bash
python3 tools/validate.py
```

Expected: 0 errors. Existing three method-card source warnings may remain.

- [ ] **Step 7: Commit the Skills**

```bash
git add allen-idea scene-idea
git commit -m "feat: add startup idea evaluation skills"
```

## Task 4: Wire routing and explicit commands

**Files:**

- Create: `commands/claude/allen-idea.md`
- Create: `commands/codex/allen-idea.md`
- Modify: `router/SKILL.md`
- Modify: `router/references/system-prompts.md`

- [ ] **Step 1: Add both command entries**

Use the same content for both command files:

```markdown
---
description: 澄清并评估创业点子或技术的企业化前景
argument-hint: <创业想法、技术和已知约束，可同时附文件>
---
<!-- installed-by-allen-skills -->

调用 `allen-idea` skill 执行“创业点子评估”应用。用户要求是：$ARGUMENTS

把本条消息所附文件和网址一并作为输入。必须先多轮澄清并获得用户对想法定义和企业化路径的确认；L2、L3 必须用 app_runtime 推进，直到 completed、waiting_user 或 blocked，不得跳过确认直接写报告。
```

- [ ] **Step 2: Write a failing validation test for application completeness**

Add to `tools/tests/test_validate.py`:

```python
def test_missing_application_entry_fails(self):
    with tempfile.TemporaryDirectory() as t:
        copy = pathlib.Path(t) / "repo"
        copy_repo(copy)
        (copy / "commands" / "codex" / "allen-idea.md").unlink()
        p = self.run_validate(copy)
        self.assertEqual(p.returncode, 1)
        self.assertIn("allen-idea：缺少 Codex 入口", p.stdout)
```

Run:

```bash
python3 -m unittest tools.tests.test_validate.ValidateTest.test_missing_application_entry_fails -v
```

Expected: FAIL because `tools/validate.py` does not yet check application completeness.

- [ ] **Step 3: Update router precedence**

Add this row before existing-company routing in the fixed application table:

```markdown
| 澄清并评估尚未成立企业的创业想法或技术 | `../allen-idea/SKILL.md` |
```

Add this disambiguation rule:

```markdown
用户给的是创业想法、技术能力或拟议产品，尚无可评估的经营主体时，用 allen-idea。已经存在明确企业并要判断实际经营、合作或投资时，才用 allen-company 或其他企业应用。只研究行业本身、不构造假想企业时用 scene-topic。
```

Update “四个固定应用” to “五个固定应用” and add the idea system prompt to `router/references/system-prompts.md` without copying the full scene workflow.

Then add this generic check to `tools/validate.py` after the per-Skill loop:

```python
for app in sorted(s for s in skills if s.name.startswith("allen-")):
    required = {
        "应用元数据": app / "assets" / "app.json",
        "Claude 入口": ROOT / "commands" / "claude" / f"{app.name}.md",
        "Codex 入口": ROOT / "commands" / "codex" / f"{app.name}.md",
    }
    for label, path in required.items():
        if not path.is_file():
            errors.append(f"{app.name}：缺少 {label}：{path.relative_to(ROOT)}")
```

Update the validator docstring with “7. 每个 allen-* 应用都有 app.json 及 Claude/Codex 入口。”

- [ ] **Step 4: Validate references and commands**

Run:

```bash
python3 tools/validate.py
```

Expected: 0 errors and 26 Skills total (`allen-idea` plus `scene-idea`).

- [ ] **Step 5: Commit routing**

```bash
git add commands/claude/allen-idea.md commands/codex/allen-idea.md router/SKILL.md router/references/system-prompts.md tools/validate.py tools/tests
git commit -m "feat: route startup ideas to allen-idea"
```

## Task 5: Verify installation on both platforms

**Files:**

- Modify: `tools/tests/test_install.py`
- Modify: `install.sh` only if named counts or help text require it

- [ ] **Step 1: Add failing installer assertions**

Extend `test_codex_uses_codex_home`:

```python
self.assertTrue((codex_home / "skills" / "allen-idea").is_symlink())
self.assertTrue((codex_home / "skills" / "scene-idea").is_symlink())
self.assertTrue((codex_home / "prompts" / "allen-idea.md").is_symlink())
```

Extend `test_both_installs_two_platforms`:

```python
self.assertTrue((fake_home / ".claude" / "commands" / "allen-idea.md").is_symlink())
self.assertTrue((codex_home / "prompts" / "allen-idea.md").is_symlink())
```

- [ ] **Step 2: Run installer tests and verify expected state**

Run:

```bash
python3 -m unittest tools.tests.test_install -v
```

Expected: tests pass without installer logic changes because `install.sh` discovers Skill and command directories by glob. If they fail, make only the smallest change needed to the existing generic loops.

- [ ] **Step 3: Update stale count comments and user-facing text in `install.sh`**

Replace only explicit references to four application entries or 24 Skills. Do not add a dedicated `allen-idea` branch to the installer.

- [ ] **Step 4: Commit installer coverage**

```bash
git add tools/tests/test_install.py install.sh
git commit -m "test: cover allen-idea installation"
```

## Task 6: Run GREEN behavioral forward tests

**Files:**

- Modify: `tests/idea-evaluation-cases.md`
- Modify: `allen-idea/SKILL.md`, `allen-idea/references/system-prompt.md`, or `scene-idea/SKILL.md` only when a forward test exposes a real gap

- [ ] **Step 1: Run the original five cases with the new Skill**

Use a fresh independent agent for each case. Provide only the user input and instruct it to use `$allen-idea` from the working tree. Do not provide intended answers or baseline findings.

Expected:

- I1 asks one high-value clarification instead of writing a report;
- I2 retains multiple paths;
- I3 refuses to infer purchase intent from popularity;
- I4 searches substitute and latent competition;
- I5 separates three horizons and opportunity type.

- [ ] **Step 2: Record outcomes under `## 前向测试记录`**

Record pass/fail per acceptance item and link failures to the exact Skill instruction that needs adjustment.

- [ ] **Step 3: Close only observed instruction gaps**

Make the smallest wording change supported by a failed forward test. Re-run only the affected case plus one adjacent case to ensure the fix does not over-trigger.

- [ ] **Step 4: Commit verified behavior**

```bash
git add tests/idea-evaluation-cases.md allen-idea scene-idea
git commit -m "test: verify allen-idea behavior"
```

## Task 7: Update product documentation

**Files:**

- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `ARCHITECTURE.md`
- Modify: `tests/method-selection-cases.md` only if a method-selection case is warranted

- [ ] **Step 1: Update README**

Change “四个企业应用” to “五个应用” and add:

```markdown
| 验证创业点子 | `/allen-idea` | `/prompts:allen-idea` 或 `$allen-idea` | 多轮澄清、路径比较、需求与潜在竞品、短中长期前景 |
```

Add `allen-idea` and `scene-idea` to the directory table. Add one usage example:

```markdown
- “我有一项低成本机器视觉技术，想比较几种创业方向并判断是快钱还是长期机会。”
```

- [ ] **Step 2: Update INSTALL**

Document five entry commands, update installed Skill count from 24 to 26, and state that `allen-idea` pauses twice for confirmation before research. Preserve all existing platform capability caveats.

- [ ] **Step 3: Update ARCHITECTURE**

Add `allen-idea` to the application layer and `scene-idea` to the scene layer. Update the invariant from “四个应用入口” to “五个应用入口”. Document that `clarify` and `pathing` are application-specific gates, while evidence and report rules remain shared.

- [ ] **Step 4: Add a method case only if it tests selection**

If used, add this row to `tests/method-selection-cases.md`:

```markdown
| M13 | 一项机器视觉技术可落地到工厂质检、零售盘点或农业分选，应如何选择创业方向？ | 加权决策矩阵 + 情景规划 | 多方案比较且长期不确定性高 |
```

Do not duplicate the five application behavior cases here.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md INSTALL.md ARCHITECTURE.md tests/method-selection-cases.md
git commit -m "docs: document startup idea evaluation app"
```

## Task 8: Full verification and local deployment

**Files:**

- Modify only files required by failing checks caused by this feature

- [ ] **Step 1: Run focused tests**

```bash
python3 -m unittest tools.tests.test_app_runtime tools.tests.test_install -v
```

Expected: all pass.

- [ ] **Step 2: Run repository validation**

```bash
python3 tools/validate.py
```

Expected: 26 Skills, 0 errors. The three pre-existing “没有出处一节” notices may remain.

- [ ] **Step 3: Run the full self-test**

```bash
tools/selftest.sh
```

Expected: all tests pass. If the existing Chrome-isolation test fails because a real Chrome installation is detected, verify that no feature code changed that check, record it separately, and do not claim the full suite passed.

- [ ] **Step 4: Test a clean temporary installation**

```bash
tmp_target=$(mktemp -d /tmp/allen-idea-install.XXXXXX)
./install.sh --target "$tmp_target"
test -f "$tmp_target/allen-idea/SKILL.md"
test -f "$tmp_target/scene-idea/SKILL.md"
```

Expected: exit 0 for all commands.

- [ ] **Step 5: Deploy to local Codex only after verification**

Run from the repository root:

```bash
./install.sh --codex --render-deps
python3 "${CODEX_HOME:-$HOME/.codex}/skills/_allen-runtime/tools/doctor.py"
```

Expected: `allen-idea`, `scene-idea`, and `/prompts:allen-idea` are installed; doctor reports every check as “通过”. Complete the image probe only if reinstalling the copied runtime invalidates the prior probe.

- [ ] **Step 6: Verify the worktree and commit any verification-only fix**

```bash
git status --short
git diff --check
```

Expected: clean worktree. If a feature-caused verification fix was required, commit it with a focused message and rerun the failed command.

- [ ] **Step 7: Push and open a pull request**

```bash
git push -u origin codex/allen-idea-design
gh pr create --base main --head codex/allen-idea-design \
  --title "Add startup idea evaluation app" \
  --body "Adds allen-idea and scene-idea, confirmation-gated idea clarification, multi-path demand and competition research, time-horizon outlooks, tests, and documentation."
```

Before merge, fetch `origin/main`; if it advanced, merge it into the branch and rerun Tasks 8.1–8.4. Do not merge until the user explicitly approves the PR.
