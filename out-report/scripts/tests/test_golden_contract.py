"""A4 黄金小册的源、渲染与候选基准合同。"""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "out-report" / "golden"
BUILD = GOLDEN / "build"
REQUIRED_ROLES = {"cover", "toc", "executive-summary", "section", "quantitative", "chart-table", "comparison", "evidence", "risk", "roadmap", "references"}
FONT_FILES = {"__FONT_NOTO_SANS_SC_400__": "noto-sans-sc-400.woff2", "__FONT_NOTO_SANS_SC_600__": "noto-sans-sc-600.woff2", "__FONT_NOTO_SERIF_SC_600__": "noto-serif-sc-600.woff2"}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def run_render(golden=GOLDEN, expect=0):
    runtime = os.environ.get("ALLEN_RUNTIME", "/Users/markjackson/Repos/Allen-skills")
    env = dict(os.environ, ALLEN_RUNTIME=runtime, GOLDEN_DIR=str(golden))
    p = subprocess.run(["node", str(golden / "render.cjs")], capture_output=True, text=True, env=env)
    if p.returncode != expect: raise AssertionError(p.stdout + p.stderr)
    return p

class GoldenReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((GOLDEN / "golden-report.json").read_text())
        cls.source_html = (GOLDEN / "golden.html").read_text()
        cls.source_css = (GOLDEN / "golden.css").read_text()
        cls.baseline = json.loads((GOLDEN / "visual-baseline.json").read_text())

    def test_manifest_pages_and_roles_share_the_same_section_node(self):
        pages = self.manifest["pages"]
        self.assertLessEqual(12, len(pages)); self.assertLessEqual(len(pages), 20)
        self.assertTrue(REQUIRED_ROLES <= {p["role"] for p in pages})
        for p in pages:
            self.assertRegex(self.source_html, rf'<section\b(?=[^>]*data-page-id="{p["id"]}")(?=[^>]*data-page-role="{p["role"]}")[^>]*>')

    def test_maintenance_sources_are_small_and_have_exact_placeholders(self):
        self.assertLess((GOLDEN / "golden.html").stat().st_size, 100_000)
        self.assertLess((GOLDEN / "golden.css").stat().st_size, 50_000)
        self.assertEqual(self.source_html.count("__GOLDEN_CSS__"), 1)
        for placeholder in FONT_FILES: self.assertEqual(self.source_css.count(placeholder), 1)
        self.assertNotIn("data:font/woff2;base64,", self.source_css)

    def test_source_semantics_and_chart_structures(self):
        self.assertEqual(self.source_html.count("<main"), 1)
        self.assertGreaterEqual(self.source_html.count("<figure"), 4)
        self.assertGreaterEqual(self.source_html.count("<figcaption"), 4)
        self.assertIn("<blockquote", self.source_html)
        heatmap = re.search(r'<div class="heatmap"[^>]*data-rows="3"[^>]*data-cols="3"[^>]*>(.*?)</div><table class="visually-hidden">', self.source_html, re.S)
        self.assertIsNotNone(heatmap)
        self.assertEqual(len(re.findall(r'<div\b', heatmap.group(1))), 16)
        steps = [(float(a), float(b)) for a, b in re.findall(r'data-waterfall-step[^>]*data-start="([\d.-]+)"[^>]*data-end="([\d.-]+)"', self.source_html)]
        self.assertEqual(steps, [(0, 8.6), (8.6, 3.2), (3.2, 2.5), (2.5, 2.1), (0, 2.1)])

    def test_approval_record_is_separate_and_records_user_approval(self):
        self.assertEqual(self.baseline["status"], "approved")
        self.assertEqual(self.baseline["approvedBy"], "user")
        self.assertRegex(self.baseline["approvedAt"], r"^2026-10-27T\d{2}:\d{2}:\d{2}\+10:30$")
        self.assertEqual(self.baseline["changeReason"], "用户确认：这个排版结构我认可")
        self.assertRegex(self.baseline["candidateDigest"], r"^[0-9a-f]{64}$")
        self.assertNotIn("artifacts", self.baseline); self.assertNotIn("environment", self.baseline)

    def test_source_is_script_free_and_declares_a4_readability(self):
        self.assertNotRegex(self.source_html, r'<(?:script|iframe)\b|(?:src|href)=["\']https?://')
        self.assertNotRegex(self.source_css, r'url\(["\']?https?://|@import')
        self.assertRegex(self.source_css, r"@page\s*{[^}]*size:\s*210mm\s+297mm")
        self.assertRegex(self.source_css, r"--font-body:\s*10\.75pt"); self.assertRegex(self.source_css, r"--font-source:\s*7\.5pt")

class GoldenRenderIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if any(not shutil.which(x) for x in ("node", "pdftoppm", "pdfinfo", "pdftotext")): raise unittest.SkipTest("render tools required")
        cls.source_hashes = {n: sha(GOLDEN / n) for n in ("golden.html", "golden.css", "visual-baseline.json")}
        run_render(); cls.first = json.loads((BUILD / "visual-candidate.json").read_text())
        cls.first_html = sha(BUILD / "golden-report.html"); cls.first_png = dict(cls.first["artifacts"]["pagePngSha256"])
        (BUILD / "page-99.png").write_bytes(b"stale")
        run_render(); cls.second = json.loads((BUILD / "visual-candidate.json").read_text())

    def test_render_is_stable_and_does_not_mutate_sources(self):
        self.assertEqual(self.source_hashes, {n: sha(GOLDEN / n) for n in self.source_hashes})
        self.assertEqual(self.first_html, sha(BUILD / "golden-report.html")); self.assertEqual(self.first_png, self.second["artifacts"]["pagePngSha256"])
        self.assertEqual(self.first, self.second)

    def test_clean_rebuild_has_exact_artifacts_and_pdf_summary(self):
        expected = [f"page-{n:02}.png" for n in range(1, 17)]
        self.assertEqual(sorted(p.name for p in BUILD.glob("page-*.png")), expected)
        self.assertEqual(len(expected), len(self.manifest_pages()))
        self.assertEqual(self.second["pdfSummary"], {"pages": 16, "pageSize": "A4", "textPages": 16, "geometry": "594.96x841.92pt"})
        self.assertNotIn("pdfSha256", self.second["artifacts"])

    def test_compiled_html_is_self_contained_and_font_mapping_is_exact(self):
        html = (BUILD / "golden-report.html").read_text()
        self.assertNotRegex(html, r"__[A-Z0-9_]+__|<(?:script|iframe)\b|(?:src|href)=[\"\']https?://|@import")
        self.assertEqual(html.count("data:font/woff2;base64,"), len(FONT_FILES))
        self.assertEqual(self.second["environment"]["fontHashes"], {"NotoSansSC-400": "758dff09a5625dd659ea4c529ffdb7741bdbc182b54957a7007f1cfcfd450820", "NotoSansSC-600": "722d2f69f1b0f494148dd6a492f7efcfcc9ba9b6c0a203b39987feea076a6064", "NotoSerifSC-600": "f6e3c090225ed5372d7ca7175e4148b8f4fb676be73f932891f64a91512c7a5a"})

    def test_geometry_has_no_overflow_or_source_footer_overlap(self):
        qa = self.second["layoutQa"]
        self.assertEqual(qa["overflowPageIds"], []); self.assertEqual(qa["sourceFooterOverlapPageIds"], []); self.assertEqual(qa["pageCount"], 16)

    def test_candidate_is_captured_with_separate_approval_and_tagging_limit_is_honest(self):
        baseline = json.loads((GOLDEN / "visual-baseline.json").read_text())
        self.assertEqual(self.second["status"], "captured"); self.assertEqual(self.second["approvalStatus"], baseline["status"])
        self.assertEqual(self.second["candidateDigest"], baseline["candidateDigest"])
        self.assertFalse(self.second["accessibility"]["pdfTagged"]); self.assertIn("Chromium", self.second["accessibility"]["limitation"])

    def test_approved_baseline_refuses_changed_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / "golden"; shutil.copytree(GOLDEN, copy, ignore=shutil.ignore_patterns("build"))
            b = json.loads((copy / "visual-baseline.json").read_text()); b.update({"status": "approved", "approvedBy": "Test", "approvedAt": "2026-10-27T00:00:00Z", "candidateDigest": "wrong"})
            (copy / "visual-baseline.json").write_text(json.dumps(b))
            self.assertIn("approved baseline does not match", run_render(copy, expect=2).stderr)

    def test_approved_baseline_accepts_the_identical_candidate_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / "golden"; shutil.copytree(GOLDEN, copy, ignore=shutil.ignore_patterns("build"))
            run_render(copy)
            digest = json.loads((copy / "build" / "visual-candidate.json").read_text())["candidateDigest"]
            approved = {"schemaVersion": "1.0", "status": "approved", "approvedBy": "Test reviewer", "approvedAt": "2026-10-27T00:00:00Z", "candidateDigest": digest, "changeReason": "Test approval"}
            original = json.dumps(approved, ensure_ascii=False, sort_keys=True)
            (copy / "visual-baseline.json").write_text(json.dumps(approved, ensure_ascii=False))
            run_render(copy)
            after = json.loads((copy / "visual-baseline.json").read_text())
            candidate = json.loads((copy / "build" / "visual-candidate.json").read_text())
            self.assertEqual(json.dumps(after, ensure_ascii=False, sort_keys=True), original)
            self.assertEqual(candidate["candidateDigest"], digest)
            self.assertEqual(candidate["approvalStatus"], "approved")

    @staticmethod
    def manifest_pages(): return json.loads((GOLDEN / "golden-report.json").read_text())["pages"]

if __name__ == "__main__": unittest.main()
