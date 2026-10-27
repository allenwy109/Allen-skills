# A4 Renderer and out-report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate deterministic A4 HTML/PDF from report.json and make it the default out-report path.

**Architecture:** A Python wrapper validates inputs and invokes a small CommonJS renderer. Chromium measures blocks, the paginator creates explicit A4 page sections, and a second pass resolves page numbers and exports matching HTML/PDF.

**Tech Stack:** Python 3, Node.js CommonJS, Playwright Chromium, CSS paged media, unittest.

---

### Task 1: Implement deterministic components

**Files:**
- Create: `out-report/scripts/a4/components.cjs`
- Create: `out-report/scripts/a4/escape.cjs`
- Create: `out-report/scripts/tests/test_a4_components.py`

- [ ] **Step 1: Write failing component snapshots**

```python
def test_comparison_renders_all_bound_references(self):
    html = run_node("components.cjs", fixture="comparison.json")
    self.assertIn('data-panel-id="supply"', html)
    self.assertIn('data-panel-id="demand"', html)
    self.assertIn('data-relation-id="compare-sides"', html)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_a4_components.py' -v`
Expected: FAIL because components do not exist.

- [ ] **Step 3: Implement only the 12 approved component kinds**

Export `renderBlock(block, context)` and reject unknown kinds with `REPORT_UNSUPPORTED_BLOCK`. Escape text by default; allow only renderer-owned SVG markup.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_a4_components.py' -v`
Expected: PASS.

```bash
git add out-report/scripts/a4 out-report/scripts/tests/test_a4_components.py
git commit -m "feat(report): render approved A4 components"
```

### Task 2: Implement two-pass pagination

**Files:**
- Create: `out-report/scripts/a4/paginate.cjs`
- Create: `out-report/scripts/a4/render.cjs`
- Create: `out-report/scripts/tests/test_a4_pagination.py`

- [ ] **Step 1: Write failing pagination tests**

```python
def test_long_table_repeats_header_without_shrinking_type(self):
    result = render_fixture("long-table.json")
    self.assertGreater(result["pageCount"], 1)
    self.assertTrue(all(page["tableHeaderCount"] == 1 for page in result["pagesWithTable"]))
    self.assertGreaterEqual(result["minimumFontPt"], 7.5)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_a4_pagination.py' -v`
Expected: FAIL because paginator does not exist.

- [ ] **Step 3: Implement measure → paginate → resolve navigation**

Use the locked Chromium from `tools.lib.runtime`. Produce one `<section data-page-id>` per page and `pagination-manifest.json` containing block-to-page, anchor-to-page, table continuations, and page geometry.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_a4_pagination.py' -v`
Expected: PASS for normal, boundary, overflow, long table, long source, and chapter-recto fixtures.

```bash
git add out-report/scripts/a4 out-report/scripts/tests/test_a4_pagination.py
git commit -m "feat(report): add deterministic A4 pagination"
```

### Task 3: Add geometry, coverage, and visual-regression QA

**Files:**
- Create: `out-report/scripts/a4/qa.cjs`
- Create: `out-report/scripts/a4/visual_regression.py`
- Create: `out-report/scripts/tests/test_a4_qa.py`

- [ ] **Step 1: Write failing QA tests**

```python
def test_qa_rejects_overflow_and_coverage_loss(self):
    result = qa_fixture("overflow-and-missing-panel.json")
    self.assertEqual({issue["code"] for issue in result["blocking"]}, {"REPORT_PAGE_OVERFLOW", "REPORT_COVERAGE_MISMATCH"})
```

- [ ] **Step 2: Verify RED, implement checks, verify GREEN**

Run before implementation: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_a4_qa.py' -v`
Expected: FAIL.

Check MediaBox within 0.2 mm, overlap, clipping, empty pages, font minimums, content-set equality, page/text manifests, embedded resources, and baseline differences. Diff findings require a human disposition; they never auto-update baselines.

Run after implementation: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_a4_qa.py' -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add out-report/scripts/a4 out-report/scripts/tests/test_a4_qa.py
git commit -m "test(report): enforce A4 output quality gates"
```

### Task 4: Switch out-report to A4

**Files:**
- Modify: `out-report/scripts/out_report.py`
- Modify: `out-report/SKILL.md`
- Modify: `out-report/scripts/tests/test_out_report.py`
- Modify: `core-review/references/output-standard.md`

- [ ] **Step 1: Replace the old expectation with a failing A4 workflow test**

```python
def test_finish_delivers_a4_report_without_author_pages_html(self):
    run_cli("init", self.task)
    self.assertTrue((self.task / "07_storyline/report.json").is_file())
    run_cli("render", self.task)
    self.assertFalse((self.task / "07_storyline/forge-work/pages.html").exists())
    self.assert_a4_pdf(self.task / "08_deliverables/report/report.pdf")
```

- [ ] **Step 2: Verify RED**

Run: `ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s out-report/scripts/tests -t out-report/scripts/tests`
Expected: FAIL because out-report still uses forge-work author pages.

- [ ] **Step 3: Route init/render/review/package through the A4 contracts**

Preserve acceptance semantics. Register coverage, pagination, geometry, visual-regression, author review, and independent review as named upstream checks.

- [ ] **Step 4: Verify GREEN and commit**

Run: `ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s out-report/scripts/tests -t out-report/scripts/tests && tools/selftest.sh --quick`
Expected: PASS.

```bash
git add out-report core-review/references/output-standard.md
git commit -m "feat(out-report): make A4 the default report output"
```
