# Upstream Report Capability Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the complete official showcase and make every upstream report-forge capability mechanically auditable.

**Architecture:** Vendor the full pinned upstream tree, then derive a checked capability manifest from upstream assets and tests. A capability is `parity` only when its files, test, and visual evidence all exist.

**Tech Stack:** Python 3, JSON, git vendoring, upstream npm tests.

---

### Task 1: Restore the full upstream showcase

**Files:**
- Modify: `vendor/vendor.config.json`
- Modify: `vendor/vendor.lock`
- Modify: `tools/tests/test_vendor_sync.py`

- [ ] **Step 1: Write the failing test**

```python
def test_report_forge_does_not_exclude_showcase(self):
    config = json.loads((ROOT / "vendor/vendor.config.json").read_text())
    self.assertNotIn("docs/showcase/", config["engines"]["report-forge"]["exclude"])
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tools.tests.test_vendor_sync -v`
Expected: FAIL because `docs/showcase/` is excluded.

- [ ] **Step 3: Remove only the showcase exclusion**

Set the report-forge entry to:

```json
"report-forge": {"upstream": "zerox-consulting-report-forge", "exclude": []}
```

- [ ] **Step 4: Re-vendor the pinned commit and verify**

Run: `python3 tools/vendor_sync.py sync && python3 tools/vendor_sync.py check`
Expected: showcase files appear under `vendor/report-forge/docs/showcase/`; check exits 0.

- [ ] **Step 5: Run upstream tests and commit**

Run: `tools/selftest.sh`
Expected: all suites pass with no skips.

```bash
git add vendor tools/tests/test_vendor_sync.py
git commit -m "chore(vendor): restore report-forge showcase"
```

### Task 2: Add a machine-readable capability matrix

**Files:**
- Create: `references/upstream-capability-matrix.json`
- Create: `tools/report_capabilities.py`
- Create: `tools/tests/test_report_capabilities.py`
- Modify: `tools/validate.py`

- [ ] **Step 1: Write a failing inventory test**

```python
def test_inventory_requires_expected_upstream_capabilities(self):
    result = report_capabilities.inspect(ROOT)
    self.assertEqual(result["layout_count"], 38)
    self.assertEqual(result["master_count"], 6)
    self.assertEqual(set(result["themes"]), {"mckinsey", "bcg", "accenture"})
    self.assertEqual(set(result["ratios"]), {"16x9", "4x3"})
    self.assertTrue(result["showcase_files"])
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tools.tests.test_report_capabilities -v`
Expected: FAIL because `report_capabilities` does not exist.

- [ ] **Step 3: Implement the minimal inspector**

```python
def inspect(root):
    root = pathlib.Path(root)
    catalog = json.loads((root / "vendor/report-forge/assets/layout-atlas/catalog.json").read_text())
    themes = (root / "vendor/report-forge/assets/deck-themes.js").read_text()
    return {
        "layout_count": len(catalog["layouts"]),
        "master_count": len(catalog["masters"]),
        "themes": [name for name in ("mckinsey", "bcg", "accenture") if name in themes],
        "ratios": [name for name in ("16x9", "4x3") if name in themes],
        "showcase_files": sorted(str(p.relative_to(root)) for p in (root / "vendor/report-forge/docs/showcase").rglob("*") if p.is_file()),
    }
```

- [ ] **Step 4: Generate the checked matrix**

Each entry must contain `id`, `upstream_ref`, `local_ref`, `test`, `visual_evidence`, and `status`. Allowed statuses are `parity`, `missing`, `untested`, `present-not-used`, and `superseded`.

- [ ] **Step 5: Make validation reject incomplete parity**

Add `report_capabilities.check(ROOT)` to `tools/validate.py`; it must emit an error for every `missing` or unknown capability and for every matrix reference whose file does not exist.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3 -m unittest tools.tests.test_report_capabilities -v && python3 tools/validate.py`
Expected: PASS, 0 errors.

```bash
git add references/upstream-capability-matrix.json tools/report_capabilities.py tools/tests/test_report_capabilities.py tools/validate.py
git commit -m "test(report): enforce upstream capability parity"
```

### Task 3: Lock visual baseline provenance

**Files:**
- Create: `references/visual-baseline.schema.json`
- Create: `references/upstream-visual-baseline.json`
- Modify: `tools/report_capabilities.py`
- Modify: `tools/tests/test_report_capabilities.py`

- [ ] **Step 1: Add a failing provenance test**

```python
def test_visual_baseline_records_provenance(self):
    baseline = json.loads((ROOT / "references/upstream-visual-baseline.json").read_text())
    self.assertEqual(baseline["upstream_commit"], "ee1f980c8dd7c53408e1a05a084229e6ec03c660")
    self.assertEqual(baseline["license"], "Apache-2.0")
    self.assertTrue(all(item["sha256"] for item in baseline["artifacts"]))
```

- [ ] **Step 2: Verify RED, implement manifest generation, and verify GREEN**

Run before implementation: `python3 -m unittest tools.tests.test_report_capabilities.ReportCapabilitiesTest.test_visual_baseline_records_provenance -v`
Expected: FAIL because the manifest is absent.

Generate hashes only from locked showcase files; never fetch `main` during validation.

Run after implementation: `python3 -m unittest tools.tests.test_report_capabilities.ReportCapabilitiesTest.test_visual_baseline_records_provenance -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add references/visual-baseline.schema.json references/upstream-visual-baseline.json tools/report_capabilities.py tools/tests/test_report_capabilities.py
git commit -m "test(report): lock upstream visual baselines"
```

