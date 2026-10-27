"""A4 黄金小册的静态合同。"""
import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "out-report" / "golden"
REQUIRED_ROLES = {
    "cover", "toc", "executive-summary", "section", "quantitative",
    "chart-table", "comparison", "evidence", "risk", "roadmap", "references",
}


class GoldenReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((GOLDEN / "golden-report.json").read_text(encoding="utf-8"))
        cls.html = (GOLDEN / "golden.html").read_text(encoding="utf-8")
        cls.css = (GOLDEN / "golden.css").read_text(encoding="utf-8")
        cls.baseline = json.loads((GOLDEN / "visual-baseline.json").read_text(encoding="utf-8"))

    def test_manifest_pages_and_roles(self):
        pages = self.manifest["pages"]
        self.assertLessEqual(12, len(pages))
        self.assertLessEqual(len(pages), 20)
        self.assertTrue(REQUIRED_ROLES <= {page["role"] for page in pages})
        self.assertEqual(self.manifest["fixtureKind"], "synthetic-example")
        for page in pages:
            self.assertRegex(page["id"], r"^p\d{2}$")
            self.assertIn(f'data-page-id="{page["id"]}"', self.html)
            self.assertIn(f'data-page-role="{page["role"]}"', self.html)

    def test_visual_baseline_is_captured_but_not_approved(self):
        self.assertEqual(self.baseline["status"], "captured")
        self.assertEqual(self.baseline["approval"]["status"], "unapproved")
        self.assertIsNone(self.baseline["approval"]["approvedBy"])
        self.assertIsNone(self.baseline["approval"]["approvedAt"])
        env = self.baseline["environment"]
        for field in ("chromiumRevision", "fontHashes", "viewport", "deviceScaleFactor", "pdf", "rasterDpi"):
            self.assertIn(field, env)
        self.assertEqual(env["rasterDpi"], 144)
        self.assertIn("htmlSha256", self.baseline["artifacts"])
        self.assertIn("pdfSha256", self.baseline["artifacts"])
        self.assertIn("pagePngSha256", self.baseline["artifacts"])

    def test_html_is_self_contained_and_script_free(self):
        self.assertNotRegex(self.html, r'<(?:script|iframe)\b')
        self.assertNotRegex(self.html, r'(?:src|href)=["\']https?://')
        self.assertNotRegex(self.css, r'url\(["\']?https?://')
        self.assertNotIn("@import", self.css)
        self.assertIn("data:font/woff2;base64,", self.css)
        self.assertEqual(len(re.findall(r'<section\b[^>]*data-page-id=', self.html)), len(self.manifest["pages"]))

    def test_a4_and_readability_tokens(self):
        self.assertRegex(self.css, r"@page\s*{[^}]*size:\s*210mm\s+297mm", re.S)
        self.assertRegex(self.css, r"--font-body:\s*10\.75pt")
        self.assertRegex(self.css, r"--font-source:\s*7\.5pt")
        self.assertRegex(self.css, r"\.page\s*{[^}]*width:\s*210mm[^}]*height:\s*297mm", re.S)

    def test_fixture_is_explicitly_synthetic_and_has_no_runtime_network(self):
        self.assertGreaterEqual(self.html.count("合成示例"), len(self.manifest["pages"]))
        self.assertNotRegex(self.html + self.css, r"fetch\s*\(|XMLHttpRequest|WebSocket|EventSource")


if __name__ == "__main__":
    unittest.main()
