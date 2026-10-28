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
EXHIBIT_GOLDEN = GOLDEN / "native-exhibits.json"
EXHIBIT_BASELINE = GOLDEN / "native-exhibits-baseline.json"
EXHIBIT_RENDER = ROOT / "out-report" / "scripts" / "a4" / "render.cjs"
BUILD = GOLDEN / "build"
REQUIRED_ROLES = {"cover", "toc", "executive-summary", "section", "quantitative", "chart-table", "comparison", "evidence", "risk", "roadmap", "references"}
FONT_FILES = {"__FONT_NOTO_SANS_SC_400__": "noto-sans-sc-400.woff2", "__FONT_NOTO_SANS_SC_600__": "noto-sans-sc-600.woff2", "__FONT_NOTO_SERIF_SC_600__": "noto-serif-sc-600.woff2"}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def dependency_runtime():
    explicit = os.environ.get("ALLEN_DEPENDENCY_RUNTIME")
    if explicit:
        return pathlib.Path(explicit).resolve()
    if (ROOT / "vendor/report-forge/node_modules/playwright").is_dir():
        return ROOT
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT,
                            check=True, capture_output=True, text=True).stdout.strip()
    return (ROOT / common).resolve().parent

def run_render(golden=GOLDEN, expect=0):
    env = dict(os.environ, ALLEN_DEPENDENCY_RUNTIME=str(dependency_runtime()), GOLDEN_DIR=str(golden))
    env.pop("ALLEN_RUNTIME", None)
    p = subprocess.run(["node", str(golden / "render.cjs")], capture_output=True, text=True, env=env)
    if p.returncode != expect: raise AssertionError(p.stdout + p.stderr)
    return p

class GoldenReportContractTest(unittest.TestCase):
    def test_native_exhibit_golden_covers_all_kinds_and_actually_renders(self):
        fixture = json.loads(EXHIBIT_GOLDEN.read_text())
        expected = {"executive-summary", "answer-and-reasons", "pain-comparison", "competitor-matrix", "decision-tree", "mechanism-process", "paired-scenarios", "30-60-90-roadmap", "methods-limitations"}
        kinds = {block["content"]["exhibit"]["kind"] for component in fixture["components"] for block in component["payload"]["blocks"]}
        self.assertEqual(expected, kinds)
        env = dict(os.environ, ALLEN_RUNTIME=str(dependency_runtime()))
        process = subprocess.run(["node", str(EXHIBIT_RENDER), str(EXHIBIT_GOLDEN)], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(0, process.returncode, process.stderr)
        rendered = json.loads(process.stdout)
        self.assertGreaterEqual(rendered["manifest"]["pageCount"], 1)
        for kind in expected:
            self.assertIn(f'data-exhibit-kind="{kind}"', rendered["html"])
        baseline = json.loads(EXHIBIT_BASELINE.read_text())
        self.assertEqual("approved", baseline["status"])
        self.assertEqual(sha(EXHIBIT_GOLDEN), baseline["fixtureSha256"])
        self.assertRegex(baseline["candidateDigest"], r"^[0-9a-f]{64}$")
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

    def test_toc_chapter_pages_match_first_running_header(self):
        toc = re.search(r'<section[^>]*data-page-id="p02".*?</section>', self.source_html, re.S).group(0)
        toc_entries = dict(re.findall(r'<strong>(\d{2})\s+[^<]+</strong><span>(\d{2})</span>', toc))
        first_running_pages = {}
        for section in re.findall(r'<section\b.*?</section>', self.source_html, re.S):
            page = re.search(r'data-page-id="p(\d{2})"', section)
            chapter = re.search(r'(?:class="section-no">|class="running"><span>)(\d{2})', section)
            if page and chapter:
                first_running_pages.setdefault(chapter.group(1), page.group(1))
        self.assertEqual(toc_entries, {"01": "04", "02": "06", "03": "10", "04": "15"})
        self.assertEqual(toc_entries, {chapter: first_running_pages[chapter] for chapter in toc_entries})

    def test_visible_copy_distinguishes_original_approval_from_revision_capture(self):
        visible = re.sub(r'<[^>]+>', ' ', self.source_html)
        for stale in ("黄金小册候选", "UNAPPROVED", "Unapproved", "未批准", "设计候选"):
            self.assertNotIn(stale, visible)
        self.assertIn("黄金小册基准 v1.0", visible)
        self.assertIn("原版结构已批准 / Original approved", visible)
        self.assertIn("当前修订待确认 / Revision pending", visible)
        self.assertNotIn("已批准 / Approved", visible)
        self.assertIn("批准人：user", visible)
        self.assertIn("批准日期：2026-10-27", visible)
        self.assertIn("current digest: needs-reapproval", visible)
        self.assertEqual(self.baseline["status"], "approved")
        self.assertEqual(self.baseline["candidateDigest"], "f2f2c00c81b58e7043932e1b6fc85ad90df6ebff3e454a5c2f370b823baaf841")

    def test_approval_record_is_separate_and_records_user_approval(self):
        self.assertEqual(self.baseline["status"], "approved")
        self.assertEqual(self.baseline["approvedBy"], "user")
        self.assertRegex(self.baseline["approvedAt"], r"^2026-10-27T\d{2}:\d{2}:\d{2}\+10:30$")
        self.assertEqual(self.baseline["changeReason"], "Task 4：正文来源带改为 appendix-linked citation markers；逐页与 contact sheet 已检查")
        self.assertRegex(self.baseline["candidateDigest"], r"^[0-9a-f]{64}$")
        approval = self.baseline["contentApproval"]
        self.assertEqual(approval["status"], "approved")
        self.assertEqual(approval["approvedBy"], "user")
        self.assertRegex(approval["approvedAt"], r"^2026-10-27T\d{2}:\d{2}:\d{2}\+10:30$")
        self.assertEqual(approval["changeReason"], "用户确认：这个排版结构我认可")
        self.assertRegex(approval["candidateDigest"], r"^[0-9a-f]{64}$")
        self.assertEqual([event["type"] for event in self.baseline["auditTrail"]],
                         ["approval", "revision", "revision", "approval", "baseline-update", "policy-classification"])
        approval = self.baseline["auditTrail"][-2]
        classification = self.baseline["auditTrail"][-1]
        self.assertEqual(approval["reason"], self.baseline["changeReason"])
        self.assertEqual(approval["observedPages"], ["p02-p14 body markers", "p12 densest", "p15-p16 references", "whole-book contact sheet"])
        self.assertEqual(classification["candidateDigest"], self.baseline["candidateDigest"])
        self.assertIn("explicit full-bibliography", classification["reason"])
        self.assertNotIn("artifacts", self.baseline); self.assertNotIn("environment", self.baseline)

    def test_source_is_script_free_and_declares_a4_readability(self):
        self.assertNotRegex(self.source_html, r'<(?:script|iframe)\b|(?:src|href)=["\']https?://')
        self.assertNotRegex(self.source_css, r'url\(["\']?https?://|@import')
        self.assertRegex(self.source_css, r"@page\s*{[^}]*size:\s*210mm\s+297mm")
        self.assertRegex(self.source_css, r"--font-body:\s*10\.75pt"); self.assertRegex(self.source_css, r"--font-source:\s*7\.5pt")

    def test_renderer_separates_worktree_sources_from_dependency_runtime(self):
        renderer = (GOLDEN / "render.cjs").read_text(encoding="utf-8")
        self.assertIn('process.env.ALLEN_DEPENDENCY_RUNTIME', renderer)
        self.assertIn('process.env.GOLDEN_DIR', renderer)
        self.assertNotRegex(renderer, r'path\.join\(runtime,\s*["\']out-report["\']')
        self.assertIn('document.fonts.ready', renderer)
        self.assertIn('document.fonts.load', renderer)
        self.assertIn('page.reload', renderer)
        self.assertEqual(ROOT, GOLDEN.parents[1])

    def test_body_pages_use_compact_markers_and_full_references_stay_in_appendix(self):
        self.assertEqual("full", self.manifest["metadata"]["bibliography_policy"])
        self.assertEqual("compact", self.manifest["metadata"]["client_citations"])
        sections = re.findall(r'<section\b.*?</section>', self.source_html, re.S)
        body = "".join(section for section in sections if 'data-page-role="references"' not in section)
        appendix = "".join(section for section in sections if 'data-page-role="references"' in section)
        visible_body = re.sub(r'<[^>]+hidden[^>]*>.*?</[^>]+>', '', body, flags=re.S)
        self.assertNotRegex(visible_body, r'https?://|class="(?:source-strip|source)"|data-reference-band')
        markers = re.findall(r'class="citation-marker"[^>]*href="#([^"]+)"', body)
        self.assertTrue(markers)
        self.assertTrue(all(appendix.count(f'id="{target}"') == 1 for target in markers))
        self.assertRegex(appendix, r'https?://')

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
        self.assertNotEqual(self.second["candidateDigest"], baseline["contentApproval"]["candidateDigest"])
        self.assertFalse(self.second["accessibility"]["pdfTagged"]); self.assertIn("Chromium", self.second["accessibility"]["limitation"])

    def test_current_review_contact_sheets_bind_current_page_hashes(self):
        review = json.loads((BUILD / "current-review" / "manifest.json").read_text())
        self.assertEqual(review["status"], "approved")
        self.assertEqual(review["candidateDigest"], self.second["candidateDigest"])
        self.assertEqual(review["sourcePageHashes"], self.second["artifacts"]["pagePngSha256"])
        self.assertEqual({sheet["id"] for sheet in review["contactSheets"]}, {"whole-book", "chapter-1", "chapter-2", "chapter-3", "chapter-4"})
        seen = set()
        for sheet in review["contactSheets"]:
            path = BUILD / "current-review" / sheet["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(sha(path), sheet["sha256"])
            expected = {f"page-{page_id[1:]}.png": self.second["artifacts"]["pagePngSha256"][f"page-{page_id[1:]}.png"] for page_id in sheet["pageIds"]}
            self.assertEqual(sheet["inputPageSha256"], expected)
            seen.update(sheet["pageIds"])
        self.assertEqual(seen, {f"p{n:02}" for n in range(1, 17)})

    def test_approved_baseline_refuses_changed_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / "golden"; shutil.copytree(GOLDEN, copy, ignore=shutil.ignore_patterns("build"))
            b = json.loads((copy / "visual-baseline.json").read_text())
            previous = b["contentApproval"]
            b.update({"status": "approved", "approvedBy": previous["approvedBy"], "approvedAt": previous["approvedAt"], "candidateDigest": previous["candidateDigest"]})
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
