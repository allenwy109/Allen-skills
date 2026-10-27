# out-deck and Report Output Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the complete upstream deck workflow as out-deck and release both outputs only after capability, scenario, and visual acceptance.

**Architecture:** Move the existing forge wrapper into a dedicated skill without changing engine semantics. Update routing so reports default to A4 and decks are explicit. Close with six fixed scenario fixtures and independent A/B review.

**Tech Stack:** Python 3, report-forge, unittest, acceptance JSON.

---

### Task 1: Create out-deck from the existing forge wrapper

**Files:**
- Create: `out-deck/SKILL.md`
- Create: `out-deck/scripts/out_deck.py`
- Create: `out-deck/scripts/tests/test_out_deck.py`
- Modify: `tools/validate.py`

- [ ] **Step 1: Write a failing deck parity test**

```python
def test_deck_supports_all_locked_capabilities(self):
    result = run_cli("capabilities")
    self.assertEqual(result["layouts"], 38)
    self.assertEqual(result["masters"], 6)
    self.assertEqual(set(result["themes"]), {"mckinsey", "bcg", "accenture"})
    self.assertEqual(set(result["ratios"]), {"16x9", "4x3"})
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest discover -s out-deck/scripts/tests -t out-deck/scripts/tests`
Expected: FAIL because out-deck does not exist.

- [ ] **Step 3: Move the existing forge lifecycle into out-deck**

Retain init, refresh, three plans, compile, assemble, smoke, acceptance, review-pack, aggregate, snapshot, package, finish, delivery, and archive. Do not fork or simplify upstream contracts.

- [ ] **Step 4: Verify GREEN and commit**

Run: `ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s out-deck/scripts/tests -t out-deck/scripts/tests && tools/selftest.sh`
Expected: all upstream and wrapper tests pass with no skips.

```bash
git add out-deck tools/validate.py
git commit -m "feat(out-deck): expose full consulting deck workflow"
```

### Task 2: Route default reports and explicit decks

**Files:**
- Modify: `core-storyline/SKILL.md`
- Modify: `router/SKILL.md`
- Modify: `scene-idea/SKILL.md`
- Modify: `scene-company/SKILL.md`
- Modify: `scene-topic/SKILL.md`
- Modify: `scene-bp-review/SKILL.md`
- Modify: `ARCHITECTURE.md`
- Modify: `README.md`
- Modify: `tools/tests/test_validate.py`

- [ ] **Step 1: Add failing routing assertions**

```python
def test_formal_reports_default_to_out_report_and_decks_are_explicit(self):
    self.assertIn("默认正式报告：out-report", (ROOT / "router/SKILL.md").read_text())
    self.assertIn("路演或演示稿：out-deck", (ROOT / "router/SKILL.md").read_text())
```

- [ ] **Step 2: Verify RED, update only output routing, verify GREEN**

Run before changes: `python3 -m unittest tools.tests.test_validate -v`
Expected: FAIL.

Run after changes: `python3 -m unittest tools.tests.test_validate -v && python3 tools/validate.py`
Expected: PASS, 0 errors.

- [ ] **Step 3: Commit**

```bash
git add core-storyline router scene-* ARCHITECTURE.md README.md tools/tests/test_validate.py
git commit -m "docs: route reports and decks to separate outputs"
```

### Task 3: Add fixed scenario acceptance fixtures

**Files:**
- Create: `tests/report-output-cases.json`
- Create: `tools/e2e/test_report_outputs.py`
- Modify: `tools/selftest.sh`

- [ ] **Step 1: Write six positive and six negative cases**

Each record must include `id`, `scene`, `input_snapshot`, `expected_claims`, `expected_panels`, `expected_relations`, `expected_components`, `page_range`, `expected_status`, and `negative_mutation`.

- [ ] **Step 2: Write the failing parameterized E2E test**

```python
def test_every_case_matches_coverage_and_acceptance(self):
    for case in load_cases():
        result = run_case(case)
        self.assertEqual(set(result.claims), set(case["expected_claims"]))
        self.assertLessEqual(case["page_range"][0], result.pages)
        self.assertLessEqual(result.pages, case["page_range"][1])
        self.assertEqual(result.status, case["expected_status"])
```

- [ ] **Step 3: Verify RED, implement fixture runner, verify GREEN**

Run before fixture runner: `tools/selftest.sh --e2e`
Expected: FAIL.

Run after implementation: `tools/selftest.sh --e2e`
Expected: all 12 cases pass with no skips.

- [ ] **Step 4: Commit**

```bash
git add tests/report-output-cases.json tools/e2e/test_report_outputs.py tools/selftest.sh
git commit -m "test(report): cover six report scenarios end to end"
```

### Task 4: Complete anonymous visual acceptance and release

**Files:**
- Create: `docs/reviews/report-output-visual-acceptance.md`
- Create: `references/report-output-release.json`
- Modify: `references/upstream-capability-matrix.json`

- [ ] **Step 1: Render deck A/B pairs and the approved A4 booklet**

Use the locked environment and identical source content. Randomize labels so independent reviewers cannot identify candidate/reference.

- [ ] **Step 2: Record eight scores with page evidence**

Require `visual_focus`, `evidence_geometry`, `density`, `typography`, `chart_clarity`, `book_rhythm`, `source_integration`, and `finish`. Every dimension must be at least 4/5; deck candidate must beat upstream in at least two and be no worse in the rest.

- [ ] **Step 3: Verify the release gate**

Run: `python3 tools/report_capabilities.py check --strict && tools/selftest.sh && tools/selftest.sh --e2e`
Expected: matrix has no `missing`, `untested`, or `present-not-used`; all tests pass with no skips.

- [ ] **Step 4: Commit the evidence**

```bash
git add docs/reviews/report-output-visual-acceptance.md references/report-output-release.json references/upstream-capability-matrix.json
git commit -m "docs: accept report output overhaul"
```

- [ ] **Step 5: Follow repository PR policy**

Push the topic branch, open a PR to `dev` if that branch exists; otherwise target the repository's maintained development branch. Re-fetch the target branch before merge, synchronize if it advanced, rerun affected tests, squash-merge, and delete the topic branch. Do not target `main` unless the user explicitly authorizes a production release.

