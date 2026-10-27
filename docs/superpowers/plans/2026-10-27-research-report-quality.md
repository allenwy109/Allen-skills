# Research and Report Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce decision-grade pain, competition, method, and fact-check analysis while rendering compact body citations and full evidence only in the A4 appendix.

**Architecture:** Add one lightweight `decision-research.json` contract that references the existing evidence ledger instead of duplicating evidence. Validate it before storyline/report generation, teach the relevant skills to produce and review it, and update the A4 renderer so body blocks display compact source markers linked to the existing full references appendix.

**Tech Stack:** Python 3 standard library, JSON Schema-style repository validators, Node.js CommonJS A4 renderer, `unittest`, Playwright/Chromium through the existing report runtime.

---

### Task 1: Add the decision-research contract and validator

**Files:**
- Create: `tools/lib/schema/decision-research.schema.json`
- Create: `tools/research_quality.py`
- Create: `tools/tests/test_research_quality.py`
- Modify: `tools/selftest.sh`

- [ ] **Step 1: Write failing tests for a complete contract and each blocking omission**

Create fixtures in the test using temporary task folders and the existing ledger schema. Cover these observable behaviors:

```python
def test_material_pain_requires_purchase_signal_and_counterevidence(self):
    contract = valid_contract()
    contract["pain"][0].pop("purchase_signal")
    result = run_quality_check(contract, valid_ledger())
    self.assertIn("QUALITY_PAIN_PURCHASE_SIGNAL", result.stderr)

def test_material_competition_requires_all_substitute_layers(self):
    contract = valid_contract()
    contract["competition"]["layers"].pop("do_nothing")
    result = run_quality_check(contract, valid_ledger())
    self.assertIn("QUALITY_COMPETITION_LAYER", result.stderr)

def test_critical_claim_must_resolve_to_ledger_support_and_adversarial_treatment(self):
    contract = valid_contract()
    contract["critical_claim_refs"] = ["cl-0001"]
    ledger = valid_ledger(counterevidence=False, adversarial_search=False)
    result = run_quality_check(contract, ledger)
    self.assertIn("QUALITY_CRITICAL_CLAIM", result.stderr)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m unittest tools.tests.test_research_quality -v
```

Expected: FAIL because `tools/research_quality.py` and the contract schema do not exist.

- [ ] **Step 3: Implement the smallest contract**

The top-level fields are:

```json
{
  "version": 1,
  "material": {"pain": true, "competition": true, "pricing": true},
  "pain": [],
  "competition": {"layers": {}, "criteria": [], "claim_refs": []},
  "methods": [],
  "critical_claim_refs": []
}
```

Each pain record requires `id`, `segment`, `trigger`, `workaround`, `consequence`, `purchase_signal`, `support_claim_refs`, `counter_claim_refs`, `confidence`, and `validation_gap`. Competition layers require `direct`, `indirect`, `diy`, `adjacent`, and `do_nothing`; each contains at least one named option or an explicit evidence-backed `not_applicable` record. Method records require `question`, `method`, `prerequisites`, `status`, `output`, and `downgrade_reason` when status is not `ready`.

`tools/research_quality.py check <task>` must:

- validate the JSON document;
- resolve every claim reference against `03_evidence/ledger/claims.jsonl`;
- require support for critical claims;
- accept counterevidence through a refuting `claim_evidence` link or a recorded adversarial search in `search_log.jsonl`;
- reject issuer-only support for prevalence, willingness-to-pay, competitive-intensity, causality, or regulatory-obligation claims unless the claim is narrowed and confidence is limited;
- print stable error codes and return non-zero on blocking issues.

- [ ] **Step 4: Verify GREEN and register the test in the quick self-test**

Run:

```bash
python3 -m unittest tools.tests.test_research_quality -v
tools/selftest.sh --quick
```

Expected: PASS with no new warnings.

- [ ] **Step 5: Commit**

```bash
git add tools/lib/schema/decision-research.schema.json tools/research_quality.py tools/tests/test_research_quality.py tools/selftest.sh
git commit -m "feat(research): enforce decision research quality contract"
```

### Task 2: Integrate the contract into method, evidence, scene, and review skills

**Files:**
- Create: `core-evidence/references/decision-research-contracts.md`
- Modify: `core-method-select/SKILL.md`
- Modify: `core-method-select/assets/method-plan-template.md`
- Modify: `core-evidence/SKILL.md`
- Modify: `core-research/references/qa.md`
- Modify: `core-review/references/reviewer-prompts.md`
- Modify: `core-review/references/output-standard.md`
- Modify: `scene-idea/SKILL.md`
- Modify: `scene-company/SKILL.md`
- Modify: `scene-topic/SKILL.md`
- Modify: `scene-bp-review/SKILL.md`
- Create: `tests/research-quality-cases.md`
- Modify: `tools/tests/test_research_quality.py`

- [ ] **Step 1: Add failing integration tests for skill instructions**

Tests must verify behavior-bearing invariants, not exact paragraphs:

```python
def test_research_scenes_route_material_questions_through_shared_contract(self):
    for path in SCENE_PATHS:
        text = path.read_text(encoding="utf-8")
        self.assertIn("decision-research.json", text)
        self.assertIn("research_quality.py", text)

def test_method_plan_requires_prerequisite_status_and_downgrade(self):
    text = METHOD_TEMPLATE.read_text(encoding="utf-8")
    for field in ("前提状态", "产出", "降级理由"):
        self.assertIn(field, text)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest tools.tests.test_research_quality -v
```

Expected: FAIL because the skills do not yet route through the new contract.

- [ ] **Step 3: Write the shared judgment guide**

`decision-research-contracts.md` defines:

- pain chain: segment → trigger → workaround → consequence → purchase/switch signal → evidence boundary;
- competition layers and purchase-decision comparison criteria;
- method coverage questions for 3C, Five Forces/substitutes, STP, pricing triangle, customer journey, and KSF/capability gap;
- critical-claim verification fields and stricter treatment of high-risk claim types;
- examples that distinguish phenomenon evidence from prevalence or willingness-to-pay evidence.

Keep method selection conditional. Explicitly forbid “all frameworks on every task.”

- [ ] **Step 4: Wire the guide and validator into the existing flow**

For L2/L3 tasks, scene skills create `03_evidence/decision-research.json` whenever pain or competition is material and run:

```bash
python3 <运行时>/tools/research_quality.py check <任务文件夹>
```

before synthesis. `core-review` repeats the check and independently challenges issuer bias, missing substitute layers, unsupported strength language, and method names without executed outputs.

- [ ] **Step 5: Add realistic pressure cases**

`tests/research-quality-cases.md` must include:

1. startup idea supported only by vendor case studies;
2. company analysis listing three direct competitors but ignoring self-build and no-buy;
3. BP claiming market demand from a large TAM forecast;
4. regulated market where guidance is incorrectly described as a legal obligation;
5. L1 answer where the full contract is proportionately unnecessary.

- [ ] **Step 6: Verify GREEN and validate all modified skills**

Run:

```bash
python3 -m unittest tools.tests.test_research_quality -v
for skill in core-method-select core-evidence core-research core-review scene-idea scene-company scene-topic scene-bp-review; do
  python3 /Users/markjackson/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"
done
```

Expected: PASS for the focused tests and every skill validator.

- [ ] **Step 7: Commit**

```bash
git add core-method-select core-evidence core-research core-review scene-idea scene-company scene-topic scene-bp-review tests/research-quality-cases.md tools/tests/test_research_quality.py
git commit -m "feat(skills): deepen pain competition and fact review"
```

### Task 3: Render compact body citations and a full evidence appendix

**Files:**
- Modify: `tools/lib/schema/report.schema.json`
- Modify: `tools/bridge/to_report.py`
- Modify: `tools/bridge/MAPPING.md`
- Modify: `out-report/scripts/a4/components.cjs`
- Modify: `out-report/scripts/a4/render.cjs`
- Modify: `out-report/scripts/tests/test_a4_components.py`
- Modify: `out-report/scripts/tests/test_out_report.py`

- [ ] **Step 1: Write failing citation tests**

Add assertions that:

```python
def test_body_sources_are_compact_markers_and_resolve_to_appendix(self):
    html = render_report(source_ids=["M002", "M010"])
    self.assertIn('class="citation-marker" href="#source-M002"', html)
    self.assertIn('class="citation-marker" href="#source-M010"', html)
    body = html.split('aria-label="References and appendix"')[0]
    self.assertNotIn("https://", body)
    self.assertNotIn("source-strip", body)
    self.assertIn('id="source-M002"', html)
```

Also test deterministic numeric display order, duplicate suppression within a block, identical numbering in HTML/PDF input, and rejection of a marker whose source is absent from the appendix.

- [ ] **Step 2: Run the component and workflow tests and verify RED**

Run:

```bash
python3 -m unittest out-report.scripts.tests.test_a4_components out-report.scripts.tests.test_out_report -v
```

Expected: FAIL because body source bindings are hidden and do not render linked compact markers.

- [ ] **Step 3: Extend the medium-neutral report model**

Add a deterministic citation registry to `report.json`:

```json
"citation_registry": [
  {"source_id": "M002", "number": 1, "appendix_anchor": "source-M002"}
]
```

`to_report.py` assigns numbers by first appearance in content, followed by appendix-only records sorted by source ID. It preserves existing `source_ids`, `source_bindings`, locators, titles, URLs, grades, and access dates.

- [ ] **Step 4: Render markers in the body and full records only in the appendix**

`components.cjs` renders one marker group per evidence-bearing block:

```html
<sup class="citation-markers" aria-label="Sources">
  <a class="citation-marker" href="#source-M002">[1]</a>
</sup>
```

The references appendix renders `id="source-M002"`, the same number, title, author/publisher, date, URL, locator, grade, and conflict-of-interest note. Raw URLs never appear in body components.

- [ ] **Step 5: Add a renderer-level integrity check**

Before export, verify that the set of body marker source IDs equals the set of evidence-bearing body source IDs and every marker target exists exactly once. Raise `REPORT_CITATION_MISMATCH` otherwise.

- [ ] **Step 6: Verify GREEN**

Run:

```bash
python3 -m unittest out-report.scripts.tests.test_a4_components out-report.scripts.tests.test_out_report -v
```

Expected: PASS, including the full init → render → review → package fixture.

- [ ] **Step 7: Commit**

```bash
git add tools/lib/schema/report.schema.json tools/bridge/to_report.py tools/bridge/MAPPING.md out-report/scripts/a4/components.cjs out-report/scripts/a4/render.cjs out-report/scripts/tests
git commit -m "feat(report): move full references to evidence appendix"
```

### Task 4: Add A4 readability and citation-regression gates

**Files:**
- Modify: `out-report/scripts/a4/qa.cjs`
- Modify: `out-report/scripts/a4/visual_regression.py`
- Modify: `out-report/scripts/tests/test_a4_qa.py`
- Modify: `out-report/scripts/tests/test_golden_contract.py`
- Modify: `out-report/golden/golden.html`
- Modify: `out-report/golden/approved-page-baseline.json`
- Modify: `out-report/golden/visual-baseline.json`
- Modify: `out-report/SKILL.md`

- [ ] **Step 1: Write failing QA tests**

Add fixtures that reject:

- a raw URL on a non-reference page;
- `.source-strip` or an equivalent multi-line bottom reference band;
- citation text below the approved minimum size;
- a citation marker without an appendix destination;
- an appendix row split across pages without its continuation header.

Expected stable codes are `REPORT_BODY_RAW_REFERENCE`, `REPORT_BODY_SOURCE_STRIP`, `REPORT_CITATION_MISMATCH`, and the existing pagination/typography codes.

- [ ] **Step 2: Run QA tests and verify RED**

Run:

```bash
python3 -m unittest out-report.scripts.tests.test_a4_qa out-report.scripts.tests.test_golden_contract -v
```

Expected: FAIL on the new body-reference rules.

- [ ] **Step 3: Implement the QA checks and update authoring instructions**

The QA pass inspects only visible rendered body content; hidden traceability bindings remain allowed. `out-report/SKILL.md` must state that references belong in the appendix and that body markers are renderer-owned, so authors do not manually type URLs or source bands.

- [ ] **Step 4: Regenerate and inspect the golden report**

Run:

```bash
node out-report/golden/render.cjs
```

Inspect representative body pages, the densest page, the worst page reported by QA, the contact sheet, and both reference pages. Update baselines only after recording the observed intended difference.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python3 -m unittest discover -s out-report/scripts/tests -t out-report/scripts/tests -v
tools/selftest.sh --quick
```

Expected: PASS; body pages contain compact markers without full references, and the appendix remains complete.

- [ ] **Step 6: Commit**

```bash
git add out-report
git commit -m "test(report): prevent reference clutter regressions"
```

### Task 5: Install locally and run the AIDC end-to-end regression

**Files:**
- Modify only if failures reveal a general defect: files from Tasks 1–4
- Regenerate outside the repository: `/Users/markjackson/Repos/entservice/work/aidc-gpu-pool-2026-10-27/`
- Create: `docs/superpowers/reviews/2026-10-27-research-report-quality-acceptance.md`

- [ ] **Step 1: Install the branch build into the local Codex skills directory**

Run the repository-supported installer in non-destructive update mode. Verify installed marker files point to this repository revision and that `allen-idea`, `core-evidence`, `core-method-select`, `core-review`, `core-storyline`, and `out-report` match the branch contents.

- [ ] **Step 2: Rebuild the AIDC research contract and report through the normal workflow**

Do not add AIDC-specific renderer code. Create the decision-research contract, deepen the evidence ledger and analysis, rerun research/method/fact/red-team reviews, regenerate storyline inputs, and produce A4 HTML/PDF through `out-report`.

- [ ] **Step 3: Verify content regressions**

The report must visibly include:

- pain chains with trigger, workaround, consequence, purchase signal, evidence strength, counterevidence, and validation gap;
- competition layers covering direct GPU clouds, marketplaces, serverless/token services, hyperscalers, self-build, adjacent entrants, and no-buy/delay;
- method execution and downgrade reasons rather than framework names alone;
- critical claims with narrower wording where public evidence cannot prove prevalence or willingness to pay.

- [ ] **Step 4: Verify visual regressions**

Inspect HTML and PDF at 100%, a whole-book contact sheet, representative pages, and the QA-selected worst page. Confirm no body page contains a full reference band or raw URL; compact markers resolve to the appendix; table text remains readable; page rhythm matches the approved A4 baseline.

- [ ] **Step 5: Run independent reviews and record acceptance**

Run fact, method, red-team, and final-product reviews required by the skills. Record exact artifacts, checks, remaining limitations, and reviewer dispositions in `docs/superpowers/reviews/2026-10-27-research-report-quality-acceptance.md`.

- [ ] **Step 6: Run full verification**

Run:

```bash
python3 -m unittest tools.tests.test_research_quality -v
python3 -m unittest discover -s out-report/scripts/tests -t out-report/scripts/tests -v
tools/selftest.sh --quick
git diff --check
```

Expected: all tests pass, the AIDC artifacts pass their acceptance workflow, and the worktree contains only intended changes.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/reviews/2026-10-27-research-report-quality-acceptance.md
git commit -m "test: accept research and A4 report quality gates"
```

### Task 6: Push, open the PR, synchronize, and merge

**Files:**
- No product files beyond verified Tasks 1–5

- [ ] **Step 1: Push the short-lived branch and create a Pull Request**

Target the repository's maintained default branch because this repository has no remote `dev` branch. Include the design, test evidence, AIDC regression links, and visual-review result in the PR body.

- [ ] **Step 2: Check whether the target branch advanced**

Fetch the remote and compare the current target SHA with the PR base SHA used for validation. If it advanced, merge the target into this branch and rerun the affected tests and visual acceptance.

- [ ] **Step 3: Squash-merge after checks pass and delete the topic branch**

Do not merge if independent review or AIDC regression remains incomplete. After merge, reinstall from the merged revision and run the quick self-test once more.
