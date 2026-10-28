"""A4 out-report workflow tests using a synthetic storyline and evidence ledger."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCRIPTS))
import out_report  # noqa: E402
from tools.acceptance import Acceptance  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402


def runtime_root():
    if (ROOT / "vendor/report-forge/node_modules/playwright").is_dir():
        return ROOT
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT,
                            check=True, capture_output=True, text=True).stdout.strip()
    return (ROOT / common).resolve().parent


def run(*args):
    env = dict(os.environ)
    env.setdefault("ALLEN_RUNTIME", str(runtime_root()))
    return subprocess.run([sys.executable, str(SCRIPTS / "out_report.py"), *map(str, args)],
                          capture_output=True, text=True, env=env)


def make_task(root, change=None):
    task = pathlib.Path(root) / "task"
    F.make_storyline_package(task)
    if change:
        source = task / "07_storyline/slides.json"
        doc = json.loads(source.read_text(encoding="utf-8"))
        change(doc)
        source.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return task


def missing():
    return [name for name in ("node", "pdfinfo", "pdftohtml", "pdftoppm", "pdftotext") if not shutil.which(name)] + F.missing_tools()


class A4OutReportPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.need = missing()
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        cls.task = make_task(cls.tmp.name).resolve()
        cls.story = cls.task / "07_storyline"
        cls.work = cls.story / "a4-work"

    @classmethod
    def tearDownClass(cls):
        if not cls.need:
            cls.tmp.cleanup()

    def setUp(self):
        if self.need:
            message = "missing: " + ", ".join(self.need)
            if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
                self.fail(message)
            self.skipTest(message)

    def command(self, *args, expected=0):
        result = run(*args)
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        return result

    def test_render_document_preserves_semantic_component_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            slides = json.loads((task / "07_storyline/slides.json").read_text(encoding="utf-8"))
            report, _ = out_report.to_report.build(task, slides)
            report["sections"][0]["blocks"][0]["content"]["semantic_type"] = "pain-demand"
            report["sections"][0]["blocks"][0]["content"]["pain_groups"] = [{
                "segment": "AI 应用创业公司", "trigger": "流量突增", "workaround": "排队或包卡",
                "consequence": "闲置或延期", "purchase_signal": "带价格试点", "evidence_strength": "medium",
                "counter": "成熟 API 可替代", "validation_gap": "没有采购样本",
            }]
            report["sections"][1]["blocks"][1]["content"]["semantic_type"] = "competition"
            report["sections"][1]["blocks"][1]["content"]["comparison"] = {
                "criteria": ["总拥有成本"],
                "alternatives": [{"name": "专业 GPU 云", "layer": "direct", "values": {"总拥有成本": "待同口径核实"}}],
            }

            document = out_report.render_document(report, task)
            summary = next(item for item in document["components"] if item["kind"] == "executive-summary")
            pain = next(item for item in document["components"] if item["kind"] == "pain-demand")
            comparison = next(item for item in document["components"] if item["kind"] == "comparison")
            references = next(item for item in document["components"] if item["kind"] == "references-appendix")
            self.assertEqual(["收入从 1800 万元增至 3200 万元"], summary["payload"]["answers"])
            self.assertEqual("data", summary["payload"]["summary_items"][0]["identity"])
            self.assertEqual("high", summary["payload"]["summary_items"][0]["confidence"])
            self.assertNotEqual("cl-0001", summary["payload"]["summary_items"][0]["text"])
            self.assertEqual("AI 应用创业公司", pain["payload"]["pain_groups"][0]["segment"])
            self.assertEqual("专业 GPU 云", comparison["payload"]["alternatives"][0]["name"])
            self.assertEqual([], references["payload"]["blocks"])

    def test_render_document_allows_executive_summary_without_answer_claims(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            slides = json.loads((task / "07_storyline/slides.json").read_text(encoding="utf-8"))
            report, _ = out_report.to_report.build(task, slides)
            report["executive_summary"]["answer_claim_refs"] = []
            report["executive_summary"]["question"] = "应否进入该市场？"
            document = out_report.render_document(report, task)
            summary = next(item for item in document["components"] if item["kind"] == "executive-summary")
            self.assertEqual(["应否进入该市场？"], summary["payload"]["answers"])
            self.assertEqual([], summary["payload"]["summary_items"])

    def test_a4_workflow_is_default_and_packages_audited_outputs(self):
        self.command("init", self.task)
        self.assertTrue((self.story / "report.json").is_file())
        report = json.loads((self.story / "report.json").read_text(encoding="utf-8"))
        self.assertEqual([1], [item["number"] for item in report["citation_registry"]])
        self.assertEqual("source-M001", report["citation_registry"][0]["appendix_anchor"])
        self.assertTrue((self.work / "coverage-manifest.json").is_file())
        self.assertFalse((self.story / "forge-work/pages.html").exists())

        preview = self.command("render", self.task, expected=1)
        self.assertIn("REPORT_VISUAL_REGRESSION", preview.stdout)
        self.assertTrue((self.work / "build/report.html").is_file())
        html = (self.work / "build/report.html").read_text(encoding="utf-8")
        self.assertIn("收入从 1800 万元增至 3200 万元", html)
        self.assertNotIn('<li class="summary-item">cl-0001</li>', html)
        body = html.split('aria-label="References and appendix"')[0]
        self.assertIn('class="citation-marker" href="#source-M001">[1]</a>', body)
        self.assertNotIn("https://", body)
        self.assertNotIn("source-strip", body)
        self.assertEqual(1, html.count('id="source-M001"'))
        pdf = self.work / "build/report.pdf"
        self.assertTrue(pdf.is_file())
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        self.assertRegex(info, r"Page size:\s+594\.96 x 841\.92 pts \(A4\)")
        pdf_text = unicodedata.normalize("NFKC", subprocess.run(
            ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True
        ).stdout)
        self.assertIn("收入从 1800 万元增至 3200 万元", pdf_text)
        with tempfile.TemporaryDirectory() as links_dir:
            xml = pathlib.Path(links_dir) / "report.xml"
            subprocess.run(["pdftohtml", "-xml", "-hidden", str(pdf), str(xml)],
                           capture_output=True, text=True, check=True)
            annotations = xml.read_text(encoding="utf-8")
            self.assertRegex(annotations, r'<a href="report\.html#2">')
            self.assertRegex(annotations, r'<a href="report\.html#\d+">\[1\]</a>')
        self.assertFalse((self.story / "forge-work/pages.html").exists())

        regression = json.loads((self.work / "visual-regression.json").read_text(encoding="utf-8"))
        artifacts = json.loads((self.work / "artifact-manifest.json").read_text(encoding="utf-8"))
        pagination_digest = artifacts["paginationDigest"]
        artifact_digest = artifacts["artifactDigest"]
        self.assertTrue({"coverage-manifest.json", "build/geometry-manifest.json", "build/media-manifest.json"}.issubset(artifacts["artifacts"]))
        author = self.work / "author-review.json"
        author.write_text(json.dumps({
            "type": "author", "reviewer": "Synthetic author", "reviewedAt": "2026-10-27T12:00:00+10:30",
            "decision": "accepted", "reason": "Synthetic fixture visually reviewed",
            "baselineDigest": regression["baselineDigest"], "candidateDigest": regression["candidateDigest"],
            "differenceDigest": regression["differenceDigest"], "artifactDigest": artifact_digest,
            "paginationDigest": pagination_digest,
        }), encoding="utf-8")
        self.command("review", self.task, "author", author)

        independent = self.work / "independent-review.json"
        independent.write_text(json.dumps({
            "type": "independent", "reviewer": "Synthetic independent reviewer",
            "at": "2026-10-27T12:05:00+10:30", "conclusion": "Synthetic fixture accepted", "issues": [],
            "artifactDigest": artifact_digest, "paginationDigest": pagination_digest,
            "page_ids": [page["id"] for page in json.loads((self.work / "build/pagination-manifest.json").read_text())["pages"]],
            "media": ["html", "pdf"], "scales": ["100%", "contact-sheet"],
            "chapter_contact_sheets": [{"chapter": "whole-book", "page_ids": [page["id"] for page in json.loads((self.work / "build/pagination-manifest.json").read_text())["pages"]],
                                         "observation": "The booklet rhythm and chapter transitions were inspected as a complete sequence."}],
            "headline_chain": {"status": "reviewed", "observation": "The headline sequence forms a coherent evidence-to-decision argument."},
            "observations": [{"page_id": page["id"], "media": ["html", "pdf"], "scale": ["100%", "contact-sheet"],
                              "observation": f"Page {page['id']} hierarchy, evidence and footer were inspected in both media.",
                              "reason": "No clipping, semantic omission or misleading emphasis was observed."}
                             for page in json.loads((self.work / "build/pagination-manifest.json").read_text())["pages"]],
        }), encoding="utf-8")
        invalid = self.work / "invalid-independent.json"
        invalid.write_text(json.dumps({"type": "independent", "reviewer": "Reviewer", "at": "2026-10-27T12:05:00+10:30",
                                       "conclusion": "PASS", "issues": [], "artifactDigest": artifact_digest,
                                       "paginationDigest": pagination_digest, "page_ids": [], "media": ["html"], "scales": ["100%"],
                                       "chapter_contact_sheets": [], "headline_chain": {"status": "reviewed", "observation": "正常"},
                                       "observations": []}), encoding="utf-8")
        invalid_result = run("review", self.task, "independent", invalid)
        self.assertEqual(1, invalid_result.returncode)
        self.assertIn("REPORT_REVIEW_INVALID", invalid_result.stderr)
        self.command("review", self.task, "independent", independent)

        valid_author = json.loads(author.read_text(encoding="utf-8"))
        for mutation in (
            lambda value: value.pop("artifactDigest"),
            lambda value: value.update(artifactDigest="0" * 64),
            lambda value: value.update(decision="pending"),
        ):
            changed = dict(valid_author)
            mutation(changed)
            author.write_text(json.dumps(changed), encoding="utf-8")
            rejected = run("package", self.task)
            self.assertEqual(1, rejected.returncode)
            self.assertIn("REPORT_REVIEW_INVALID", rejected.stderr)
        author.write_text(json.dumps(valid_author), encoding="utf-8")

        for target in (self.work / "build/report.html", self.work / "build/report.pdf", next((self.work / "build").glob("page-*.png")),
                       self.work / "coverage-manifest.json", self.work / "build/geometry-manifest.json", self.work / "build/media-manifest.json"):
            original = target.read_bytes()
            target.write_bytes(original + b"tampered")
            rejected = run("package", self.task)
            self.assertEqual(1, rejected.returncode, target.name)
            self.assertIn("REPORT_ARTIFACT_MISMATCH", rejected.stderr)
            target.write_bytes(original)
        package = self.command("package", self.task)
        self.assertIn("passed", package.stdout)

        out = self.task / "08_deliverables/client-report"
        for name in ("report.html", "report.pdf"):
            self.assertTrue((out / name).is_file(), name)
        self.assertEqual([], list(out.glob("page-*.png")))
        client_html = (out / "report.html").read_text(encoding="utf-8")
        self.assertIn('class="citation-marker"', client_html)
        for forbidden in ("https://", "Grade A", "2026-01-15T", "conflict_of_interest"):
            self.assertNotIn(forbidden, client_html)
        entry = next(item for item in Acceptance(self.task).load()["deliverables"] if item["id"] == "report-main")
        names = [check["name"] for check in entry["upstream_checks"]]
        self.assertEqual(names, ["storyline", "coverage", "pagination", "geometry", "visual-regression", "author-review", "independent-review"])
        self.assertEqual([check["result"] for check in entry["upstream_checks"]], ["passed"] * 7)
        self.assertEqual("passed", entry["status"])
        self.assertEqual("independent", entry["reviewer"]["type"])
        recorded_paths = [item["path"] if isinstance(item, dict) else item for item in entry["files"]]
        self.assertEqual(["08_deliverables/client-report/report.html", "08_deliverables/client-report/report.pdf"], recorded_paths)

    def test_package_fails_closed_before_both_reviews(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            self.assertEqual(0, run("init", task).returncode)
            self.assertEqual(1, run("render", task).returncode)
            result = run("package", task)
            self.assertEqual(1, result.returncode)
            self.assertIn("author-review", result.stderr)
            self.assertIn("independent-review", result.stderr)


class A4OutReportContractTest(unittest.TestCase):
    def test_atomic_delivery_replaces_ten_pages_with_eight_without_residue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            destination = root / "report"
            first = root / "first"; first.mkdir()
            second = root / "second"; second.mkdir()
            first_sources = {}
            second_sources = {}
            for index in range(1, 11):
                page = first / f"page-{index:03d}.png"; page.write_bytes(str(index).encode())
                first_sources[page.name] = page
            for index in range(1, 9):
                page = second / f"page-{index:03d}.png"; page.write_bytes(f"new-{index}".encode())
                second_sources[page.name] = page
            out_report.replace_delivery(destination, first_sources)
            self.assertEqual(10, len(list(destination.glob("page-*.png"))))
            out_report.replace_delivery(destination, second_sources)
            self.assertEqual([f"page-{index:03d}.png" for index in range(1, 9)], sorted(path.name for path in destination.glob("page-*.png")))

    def test_delivery_reader_accepts_legacy_report_without_creating_new_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = pathlib.Path(temporary)
            legacy = task / "08_deliverables/report"
            legacy.mkdir(parents=True)
            (legacy / "report.html").write_text("legacy", encoding="utf-8")
            self.assertEqual(legacy.resolve(), out_report.client_report_dir(task, for_write=False))
            self.assertFalse((task / "08_deliverables/client-report").exists())

    def test_skill_routes_reports_to_a4_not_forge_author_pages(self):
        text = (ROOT / "out-report/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("A4", text)
        self.assertNotIn("forge-work/pages.html", text)
        self.assertNotIn("作者写 `forge-work/pages.html`", text)

    def test_invalid_storyline_does_not_create_a4_work(self):
        def change(doc):
            doc["slides"][1]["panels"][0]["form"] = "unsupported.form"
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary, change)
            result = run("init", task)
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertIn("REPORT_UNSUPPORTED_BLOCK", result.stderr)
            self.assertFalse((task / "07_storyline/a4-work").exists())

    def test_renderer_rejects_body_marker_without_appendix_target(self):
        if missing():
            self.skipTest("missing renderer tools")
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            self.assertEqual(0, run("init", task).returncode)
            document_path = task / "07_storyline/a4-work/render-document.json"
            document = json.loads(document_path.read_text(encoding="utf-8"))
            document["components"][-1]["payload"]["references"] = []
            document_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            result = run("render", task)
            self.assertEqual(1, result.returncode)
            self.assertIn("REPORT_CITATION_MISMATCH", result.stderr)

    def test_renderer_rejects_source_binding_without_declared_source_id(self):
        if missing():
            self.skipTest("missing renderer tools")
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            self.assertEqual(0, run("init", task).returncode)
            document_path = task / "07_storyline/a4-work/render-document.json"
            document = json.loads(document_path.read_text(encoding="utf-8"))
            body = next(component for component in document["components"] if component["payload"].get("blocks"))
            body["payload"]["blocks"][0]["source_ids"] = []
            document_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            result = run("render", task)
            self.assertEqual(1, result.returncode)
            self.assertIn("REPORT_CITATION_MISMATCH", result.stderr)

    def test_renderer_rejects_source_id_without_binding(self):
        if missing():
            self.skipTest("missing renderer tools")
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            self.assertEqual(0, run("init", task).returncode)
            document_path = task / "07_storyline/a4-work/render-document.json"
            document = json.loads(document_path.read_text(encoding="utf-8"))
            body = next(component for component in document["components"] if component["payload"].get("blocks"))
            body["payload"]["blocks"][0]["source_bindings"] = []
            document_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            result = run("render", task)
            self.assertEqual(1, result.returncode)
            self.assertIn("REPORT_CITATION_MISMATCH", result.stderr)

    def test_renderer_derives_deterministic_citations_for_legacy_v1_document(self):
        if missing():
            self.skipTest("missing renderer tools")
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            self.assertEqual(0, run("init", task).returncode)
            report_path = task / "07_storyline/report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report.pop("citation_registry")
            document_path = task / "07_storyline/a4-work/render-document.json"
            document = out_report.render_document(report, task)
            document_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            result = run("render", task)
            self.assertEqual(1, result.returncode)
            html = (task / "07_storyline/a4-work/build/report.html").read_text(encoding="utf-8")
            self.assertIn('class="citation-marker" href="#source-M001">[1]</a>', html)
            self.assertEqual(1, html.count('id="source-M001"'))

    def test_unsafe_reference_url_is_auditable_text_but_never_a_link(self):
        if missing():
            self.skipTest("missing renderer tools")
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            self.assertEqual(0, run("init", task).returncode)
            document_path = task / "07_storyline/a4-work/render-document.json"
            document = json.loads(document_path.read_text(encoding="utf-8"))
            reference = document["components"][-1]["payload"]["references"][0]
            reference["url"] = "javascript:alert(1)"
            document_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            result = run("render", task)
            self.assertEqual(1, result.returncode)
            html = (task / "07_storyline/a4-work/build/report.html").read_text(encoding="utf-8")
            self.assertIn("javascript:alert(1)", html)
            self.assertFalse('href="javascript:' in html)


if __name__ == "__main__":
    unittest.main()
