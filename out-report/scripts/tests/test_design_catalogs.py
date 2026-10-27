"""Contracts for the approved A4 design tokens, layouts, and forms."""
import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
ASSETS = ROOT / "out-report" / "assets"
GOLDEN = ROOT / "out-report" / "golden"
LAYOUT_IDS = {
    "full-evidence", "chart-sidebar", "chart-table", "comparison-columns",
    "small-multiples", "decision-matrix", "process-roadmap", "prose-aside",
    "continued-table", "overview-detail",
}
FORM_IDS = {
    "metric-stack", "waterfall", "comparison-table", "heatmap", "risk-matrix",
    "timeline", "evidence-quote", "dense-table",
}
LAYOUT_FIELDS = {
    "id", "reader_task", "reading_path", "ratio", "allowed_blocks", "capacity",
    "tradeoff", "avoid", "split", "whitespace", "golden_page_refs",
}
FORM_FIELDS = {
    "id", "status", "relationship", "priority", "avoid", "min_plot", "labels",
    "baseline", "sort", "identity_encodings", "value_encodings", "missing_zero_negative",
    "capacity", "grayscale", "golden_page_refs",
}


class DesignAssetPresenceTest(unittest.TestCase):
    def test_design_assets_exist(self):
        expected = [
            ASSETS / "report-tokens.css",
            ASSETS / "layout-atlas" / "catalog.json",
            ASSETS / "layout-atlas.html",
            ASSETS / "form-catalog.json",
        ]
        self.assertEqual([path.name for path in expected if not path.is_file()], [])


class DesignCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layouts_doc = json.loads((ASSETS / "layout-atlas" / "catalog.json").read_text())
        cls.forms_doc = json.loads((ASSETS / "form-catalog.json").read_text())
        cls.layouts = cls.layouts_doc["layouts"]
        cls.forms = cls.forms_doc["forms"]
        cls.atlas = (ASSETS / "layout-atlas.html").read_text()
        cls.css = (ASSETS / "report-tokens.css").read_text()
        cls.baseline = json.loads((GOLDEN / "visual-baseline.json").read_text())
        cls.schema = json.loads((ROOT / "tools" / "lib" / "schema" / "report.schema.json").read_text())

    def test_catalogs_record_the_approved_baseline_digest(self):
        digest = self.baseline["candidateDigest"]
        self.assertEqual(self.baseline["status"], "approved")
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(self.layouts_doc["approved_baseline_digest"], digest)
        self.assertEqual(self.forms_doc["approved_baseline_digest"], digest)

    def test_layout_catalog_has_required_unique_layouts_and_fields(self):
        ids = [item["id"] for item in self.layouts]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(LAYOUT_IDS <= set(ids))
        for item in self.layouts:
            self.assertTrue(LAYOUT_FIELDS <= set(item), item["id"])
            self.assertTrue(item["reader_task"] and item["reading_path"] and item["ratio"])
            self.assertTrue(item["tradeoff"] and item["avoid"] and item["split"] and item["whitespace"])
            self.assertLessEqual(item["capacity"]["soft"], item["capacity"]["hard"])

    def test_layout_blocks_match_report_schema_and_refs_are_real_pages(self):
        block_kinds = set(self.schema["enums"]["block_kind"]["values"])
        for item in self.layouts:
            self.assertTrue(item["allowed_blocks"])
            self.assertTrue(set(item["allowed_blocks"]) <= block_kinds, item["id"])
            self.assertTrue(item["golden_page_refs"])
            for ref in item["golden_page_refs"]:
                self.assertRegex(ref, r"^p(?:0[1-9]|1[0-6])$")

    def test_form_catalog_has_required_unique_complete_approved_forms(self):
        ids = [item["id"] for item in self.forms]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(FORM_IDS <= set(ids))
        identities = set(self.schema["enums"]["claim_identity"]["values"])
        required_identity_keys = {"actual", "estimate", "forecast", "target"}
        for item in self.forms:
            self.assertTrue(FORM_FIELDS <= set(item), item["id"])
            self.assertEqual(item["status"], "approved-design")
            self.assertTrue(item["relationship"] and item["priority"] and item["avoid"])
            self.assertTrue(item["min_plot"] and item["labels"] and item["baseline"] and item["sort"])
            self.assertEqual(set(item["identity_encodings"]), required_identity_keys)
            self.assertTrue(set(item["identity_encodings"].values()) <= identities | {"target"})
            self.assertTrue(item["value_encodings"])
            self.assertEqual(set(item["missing_zero_negative"]), {"missing", "zero", "negative"})
            self.assertLessEqual(item["capacity"]["soft"], item["capacity"]["hard"])
            self.assertTrue(item["grayscale"] and item["golden_page_refs"])
            for ref in item["golden_page_refs"]:
                self.assertRegex(ref, r"^p(?:0[1-9]|1[0-6])$")

    def test_css_freezes_approved_core_values_without_page_recipes(self):
        required = {
            "--a4-width: 210mm", "--a4-height: 297mm", "--page-margin-top: 18mm",
            "--page-margin-right: 17mm", "--page-margin-bottom: 18mm", "--page-margin-left: 20mm",
            "--font-sans: NotoSansSC, Arial, sans-serif", "--font-serif: NotoSerifSC, serif",
            "--weight-regular: 400", "--weight-semibold: 600", "--font-body: 10.75pt",
            "--line-body: 1.58", "--font-source: 7.5pt", "--baseline: 2.7mm",
            "--paper: #f7f5ef", "--ink: #262d31", "--muted: #667176",
            "--rule: #bdc5c3", "--tint: #e9eeeb", "--accent: #0b6b66",
            "--accent-soft: #d8e7e3", "--rule-hairline: .35pt", "--source-bottom: 14mm",
            "--footer-bottom: 3mm",
        }
        for declaration in required:
            self.assertIn(declaration, self.css)
        self.assertRegex(self.css, r"@page\s*{[^}]*size:\s*var\(--a4-width\)\s+var\(--a4-height\)")
        self.assertNotRegex(self.css, r"gradient|box-shadow|border-radius\s*:\s*(?:[1-9]\d|\d{3,})px")
        self.assertNotRegex(self.css, r"https?://|@import|\.page\b|\.chart-|\.matrix\b|\.roadmap\b")

    def test_atlas_is_self_contained_and_covers_every_layout(self):
        self.assertNotRegex(self.atlas, r"<(?:script|iframe)\b|(?:src|href)=[\"']https?://|@import")
        self.assertIn("布局决策图谱", self.atlas)
        rendered_ids = re.findall(r'data-layout-id="([^"]+)"', self.atlas)
        self.assertEqual(set(rendered_ids), {item["id"] for item in self.layouts})
        self.assertEqual(len(rendered_ids), len(set(rendered_ids)))
        cards = re.findall(r'<article class="card" data-layout-id="([^"]+)">(.*?)</article>', self.atlas, re.S)
        for layout_id, card in cards:
            for label in ("Reader task", "Reading path", "Capacity", "Trade-off", "Avoid", "Split", "Whitespace"):
                self.assertIn(label, card, layout_id)


if __name__ == "__main__":
    unittest.main()
