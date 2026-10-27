# A4 Report Contracts and Golden Booklet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the A4 content, layout, chart, typography, and visual-approval contracts before implementing the reusable renderer.

**Architecture:** Convert existing storyline data into a versioned medium-neutral report model. Use a hand-authored but contract-compliant golden booklet to approve the visual system, then derive tokens and catalogs from it.

**Tech Stack:** Python schema validation, JSON, HTML/CSS/SVG, Playwright screenshots.

---

### Task 1: Define report.json and coverage contracts

**Files:**
- Create: `tools/lib/schema/report.schema.json`
- Create: `tools/bridge/to_report.py`
- Create: `tools/tests/test_bridge_report.py`
- Modify: `tools/bridge/MAPPING.md`
- Modify: `tools/tests/fixtures.py`

- [ ] **Step 1: Write failing tests for mapping and loss detection**

```python
def test_all_panels_relations_claims_metrics_and_sources_are_covered(self):
    result = to_report.build(self.task, fixtures.report_slides(), None)
    self.assertEqual(set(result["coverage"]["input"]["panels"]), set(result["coverage"]["output"]["panels"]))
    self.assertEqual(set(result["coverage"]["input"]["relations"]), set(result["coverage"]["output"]["relations"]))

def test_unsupported_panel_fails_with_stable_code(self):
    slides = fixtures.report_slides()
    slides["slides"][0]["panels"][0]["form"] = "unknown.form"
    with self.assertRaisesRegex(to_report.ReportError, "REPORT_UNSUPPORTED_BLOCK"):
        to_report.build(self.task, slides, None)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tools.tests.test_bridge_report -v`
Expected: FAIL because `to_report` and schema are absent.

- [ ] **Step 3: Implement schema 1.0.0 and deterministic conversion**

The root fields are `version`, `metadata`, `executive_summary`, `sections`, `references`, and `appendix`. Every block requires `id`, `kind`, `claim_refs`, `metric_refs`, `source_ids`, `panel_refs`, `relation_refs`, `identity`, and `content`.

- [ ] **Step 4: Emit `report.json` and `coverage-manifest.json`**

Use sorted keys and stable ordering. Reject duplicates, unknown references, missing A-card claims, and set inequality with stable error codes.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python3 -m unittest tools.tests.test_bridge_report -v && python3 tools/validate.py`
Expected: PASS, 0 errors.

```bash
git add tools/lib/schema/report.schema.json tools/bridge/to_report.py tools/tests/test_bridge_report.py tools/bridge/MAPPING.md tools/tests/fixtures.py
git commit -m "feat(report): add A4 content and coverage contracts"
```

### Task 2: Create the golden booklet fixture and approval contract

**Files:**
- Create: `out-report/golden/golden-report.json`
- Create: `out-report/golden/golden.html`
- Create: `out-report/golden/golden.css`
- Create: `out-report/golden/visual-baseline.json`
- Create: `out-report/scripts/tests/test_golden_contract.py`

- [ ] **Step 1: Write the failing contract test**

```python
def test_golden_booklet_has_required_page_roles(self):
    manifest = json.loads(BASELINE.read_text())
    required = {"cover", "toc", "executive-summary", "section", "quantitative", "chart-table", "comparison", "evidence", "risk", "roadmap", "references"}
    self.assertTrue(required <= {page["role"] for page in manifest["pages"]})
    self.assertGreaterEqual(len(manifest["pages"]), 12)
    self.assertLessEqual(len(manifest["pages"]), 20)
```

- [ ] **Step 2: Verify RED, author the booklet, and render both media**

Run before authoring: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_golden_contract.py' -v`
Expected: FAIL because assets are absent.

Use real but redistributable synthetic evidence. Include long Chinese title, bilingual text, long URL, dense table, sparse conclusion, extreme labels, continued table, and grayscale pages.

- [ ] **Step 3: Obtain explicit user approval**

Present the complete HTML and PDF, not isolated screenshots. Record approval timestamp, reviewer, Chromium revision, font hashes, viewport, device scale, 144-DPI page hashes, and the eight visual scores in `visual-baseline.json`.

- [ ] **Step 4: Verify and commit**

Run: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_golden_contract.py' -v`
Expected: PASS only after approval fields are populated.

```bash
git add out-report/golden out-report/scripts/tests/test_golden_contract.py
git commit -m "design(report): approve A4 golden booklet"
```

### Task 3: Derive tokens, layout atlas, and form catalog

**Files:**
- Create: `out-report/assets/report-tokens.css`
- Create: `out-report/assets/layout-atlas/catalog.json`
- Create: `out-report/assets/layout-atlas.html`
- Create: `out-report/assets/form-catalog.json`
- Create: `out-report/scripts/tests/test_design_catalogs.py`

- [ ] **Step 1: Write failing catalog tests**

```python
def test_layouts_have_decision_contracts(self):
    catalog = json.loads(LAYOUTS.read_text())
    self.assertGreaterEqual(len(catalog["layouts"]), 10)
    for layout in catalog["layouts"]:
        self.assertTrue({"reader_task", "reading_path", "ratio", "allowed_blocks", "capacity", "tradeoff", "avoid", "split", "whitespace"} <= set(layout))
```

- [ ] **Step 2: Verify RED, implement catalogs from the approved booklet, verify GREEN**

Run: `python3 -m unittest discover -s out-report/scripts/tests -p 'test_design_catalogs.py' -v`
Expected before implementation: FAIL; after implementation: PASS.

- [ ] **Step 3: Commit**

```bash
git add out-report/assets out-report/scripts/tests/test_design_catalogs.py
git commit -m "feat(report): add A4 visual design system"
```
