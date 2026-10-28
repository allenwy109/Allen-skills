import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
QA = ROOT / "out-report" / "scripts" / "a4" / "qa.cjs"
VISUAL = ROOT / "out-report" / "scripts" / "a4" / "visual_regression.py"
EXPORT = ROOT / "out-report" / "scripts" / "a4" / "export.cjs"
PAGE_DIGEST = "c" * 64


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


BASELINE_DIGEST = json_digest({"page-001": PAGE_DIGEST})
CHANGED_PAGE_DIGEST = "e" * 64
CANDIDATE_DIGEST = json_digest({"page-001": CHANGED_PAGE_DIGEST})
EMPTY_DIFFERENCE_DIGEST = json_digest([])
VISUAL_DIFFERENCES = [{"page": "page-001", "kind": "changed", "baseline": PAGE_DIGEST, "candidate": CHANGED_PAGE_DIGEST}]
VISUAL_DIFFERENCE_DIGEST = json_digest(VISUAL_DIFFERENCES)


def load_visual():
    spec = importlib.util.spec_from_file_location("visual_regression", VISUAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def good_evidence():
    return {
        "pagination": {
            "maximumUnusedRatio": 0.55,
            "pageCount": 1,
            "pages": [{
                "id": "page-001", "number": 1, "intentionalBlank": False,
                "role": "body",
                "usedHeightPx": 500, "contentHeightPx": 986,
                "geometry": {"widthMm": 210, "heightMm": 297},
            }],
            "minimumFontPt": 8.5,
        },
        "geometry": {
            "pages": [{
                "id": "page-001", "mediaBoxMm": [210, 297], "overlaps": [],
                "clipped": [], "empty": False,
                "fonts": [{"role": "body", "minimumPt": 8.5}, {"role": "source", "minimumPt": 7.5}],
            }],
        },
        "coverage": {
            "input": {"claims": ["cl-1"], "a_cards": ["A-1"], "panels": ["p-1"], "relations": ["r-1"], "metrics": ["m-1"], "sources": ["s-1"]},
            "output": {"claims": ["cl-1"], "a_cards": ["A-1"], "panels": ["p-1"], "relations": ["r-1"], "metrics": ["m-1"], "sources": ["s-1"]},
        },
        "media": {
            "htmlPages": [{"id": "page-001", "role": "body", "text": "Decision evidence source",
                           "visibleHtml": '<p>Decision evidence <a class="citation-marker" href="#ref-s-1">[1]</a></p>'}],
            "pdfPages": [{"id": "page-001", "text": "Decision evidence source"}],
            "appendixDestinations": ["ref-s-1"],
            "resources": [{"type": "font", "url": "data:font/woff2;base64,AA==", "embedded": True}],
        },
        "regression": {
            "status": "identical", "baselineDigest": BASELINE_DIGEST, "candidateDigest": BASELINE_DIGEST,
            "baselinePages": [{"id": "page-001", "digest": PAGE_DIGEST}],
            "candidatePages": [{"id": "page-001", "digest": PAGE_DIGEST}],
            "differences": [], "differenceDigest": EMPTY_DIFFERENCE_DIGEST, "baselineUpdated": False,
        },
    }


def run_qa(evidence):
    process = subprocess.run(
        ["node", str(QA)], cwd=ROOT, input=json.dumps(evidence),
        capture_output=True, text=True,
    )
    if process.returncode:
        raise AssertionError(process.stderr)
    return json.loads(process.stdout)


def run_node(expression, payload):
    script = f"""
const qa = require({json.dumps(str(QA))});
const payload = JSON.parse(process.argv[1]);
Promise.resolve().then(() => {expression}).then(
  value => process.stdout.write(JSON.stringify({{ok: true, value}})),
  error => process.stdout.write(JSON.stringify({{ok: false, code: error.code, message: error.message}}))
);
"""
    process = subprocess.run(["node", "-e", script, json.dumps(payload)], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(process.stdout)


class A4QualityGateTest(unittest.TestCase):
    def test_nonfunctional_whitespace_and_a4_type_minimums_block_and_worst_page_is_named(self):
        evidence = good_evidence()
        evidence["pagination"]["pages"][0]["usedHeightPx"] = 200
        evidence["geometry"]["pages"][0]["fonts"][0]["minimumPt"] = 8.49
        result = run_qa(evidence)
        codes = {item["code"] for item in result["blocking"]}
        self.assertIn("REPORT_NONFUNCTIONAL_WHITESPACE", codes)
        self.assertIn("REPORT_FONT_TOO_SMALL", codes)
        self.assertEqual("page-001", result["audit"]["worstPage"]["id"])
        self.assertGreater(result["audit"]["worstPage"]["score"], 0)

    def test_intentional_whitespace_is_allowed_only_with_a_specific_reason(self):
        evidence = good_evidence()
        evidence["pagination"]["pages"][0].update(usedHeightPx=450, role="section-divider", whitespaceJustification="section-transition")
        evidence["media"]["htmlPages"][0]["role"] = "section-divider"
        result = run_qa(evidence)
        self.assertNotIn("REPORT_NONFUNCTIONAL_WHITESPACE", {item["code"] for item in result["blocking"]})

        evidence["pagination"]["pages"][0].update(usedHeightPx=207, role="cover", whitespaceJustification="cover-identity")
        evidence["media"]["htmlPages"][0]["role"] = "body"
        result = run_qa(evidence)
        self.assertIn("REPORT_NONFUNCTIONAL_WHITESPACE", {item["code"] for item in result["blocking"]})
        self.assertGreaterEqual(result["audit"]["worstPage"]["score"], .9)

    def test_text_fingerprint_preserves_normalized_reading_order(self):
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0]["text"] = "A B C"
        evidence["media"]["pdfPages"][0]["text"] = "C B A"
        self.assertIn("REPORT_TEXT_MISMATCH", {item["code"] for item in run_qa(evidence)["blocking"]})

        evidence["media"]["htmlPages"][0]["text"] = "First paragraph. Second paragraph."
        evidence["media"]["pdfPages"][0]["text"] = "Second paragraph. First paragraph."
        self.assertIn("REPORT_TEXT_MISMATCH", {item["code"] for item in run_qa(evidence)["blocking"]})
    def test_real_evaluate_rejects_missing_and_mismatched_rendered_exhibits(self):
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0]["visibleHtml"] = (
            '<article data-semantic-type="decision-tree" data-exhibit-required="true" '
            'data-form="svg.custom"><p>Decision evidence source</p></article>'
        )
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertIn("REPORT_EXHIBIT_MISSING", codes)

        evidence["media"]["htmlPages"][0]["visibleHtml"] = (
            '<article data-semantic-type="decision-tree" data-exhibit-required="true" data-form="html.text">'
            '<figure data-exhibit-kind="decision-tree" data-exhibit-family="decision-tree" '
            'data-exhibit-form="svg.custom" data-structure="decision-branch-svg">Decision evidence source</figure></article>'
        )
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertIn("REPORT_EXHIBIT_MISMATCH", codes)

    def test_semantic_alias_resolves_to_canonical_catalog_exhibit(self):
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0]["visibleHtml"] = (
            '<article data-semantic-type="competition" data-exhibit-required="true" data-form="html.table">'
            '<figure data-exhibit-kind="competitor-matrix" data-exhibit-family="matrix" data-exhibit-form="html.table" '
            'data-structure="competitor-criteria-table">Decision evidence source</figure></article>'
        )
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertNotIn("REPORT_EXHIBIT_MISSING", codes)
        self.assertNotIn("REPORT_EXHIBIT_MISMATCH", codes)
    def test_declared_exhibit_family_requires_matching_native_form(self):
        cases = [
            ({"family": "matrix", "form": "html.text"}, "REPORT_EXHIBIT_MISMATCH"),
            ({"family": "timeline"}, "REPORT_EXHIBIT_MISSING"),
            ({"family": "decision-tree", "form": "svg.custom"}, None),
        ]
        for declaration, expected in cases:
            with self.subTest(declaration=declaration):
                result = run_node("qa.validateExhibitDeclaration(payload)", declaration)
                if expected:
                    self.assertFalse(result["ok"])
                    self.assertEqual(expected, result.get("code"), result)
                else:
                    self.assertTrue(result["ok"], result)

    def test_export_rebuilds_internal_links_and_cleans_temporary_pages_in_finally(self):
        source = EXPORT.read_text(encoding="utf-8")
        self.assertNotIn("pdfunite", source)
        self.assertIn("window.__reportPages", source)
        self.assertIn("mkdtempSync", source)
        self.assertIn("link_pdf.swift", source)
        self.assertIn("internal-links.json", source)
        self.assertIn("finally", source)
        self.assertIn("if (browser) await browser.close()", source)
        self.assertIn("rmSync", source)
        self.assertIn("ALLEN_PDF_BACKEND", source)
        self.assertIn("backend === 'chromium'", source)

    def test_chromium_pdf_backend_preserves_links_without_swift(self):
        runtime = Path(os.environ.get("ALLEN_RUNTIME", ROOT))
        if not (runtime / "vendor" / "report-forge" / "node_modules" / "playwright").exists() or any(not shutil.which(name) for name in ("pdftoppm", "pdftotext", "pdftohtml")):
            self.skipTest("A4 export runtime required")
        html = ('<!doctype html><style>@page{size:A4;margin:0}*{box-sizing:border-box}body{margin:0}.page{width:210mm;height:297mm;break-after:page;overflow:hidden}</style>'
                '<section class="page" data-page-id="page-001"><div class="page__body"><a href="#target">Next</a></div></section>'
                '<section class="page" data-page-id="page-002"><div class="page__body"><h1 id="target">Target</h1></div></section>')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "report.html"; build = root / "build"
            source.write_text(html)
            before = set(Path(tempfile.gettempdir()).glob("allen-report-pages-*"))
            env = dict(os.environ, ALLEN_RUNTIME=str(runtime), ALLEN_PDF_BACKEND="chromium")
            process = subprocess.run(["node", str(EXPORT), str(source), str(build)], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertEqual("chromium", json.loads(process.stdout)["backend"])
            xml = root / "report.xml"
            subprocess.run(["pdftohtml", "-xml", "-hidden", str(build / "report.pdf"), str(xml)], check=True, capture_output=True)
            self.assertRegex(xml.read_text(), r'<a href="report\.html#2">Next</a>')
            self.assertEqual(before, set(Path(tempfile.gettempdir()).glob("allen-report-pages-*")))

    def test_visible_body_rejects_raw_url_but_allows_hidden_traceability(self):
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0]["visibleHtml"] = (
            '<span hidden data-source-locator="https://allowed.invalid/source"></span>'
            '<p>Read https://example.invalid/source</p>'
        )
        result = run_qa(evidence)
        self.assertIn("REPORT_BODY_RAW_REFERENCE", {item["code"] for item in result["blocking"]})
        evidence["media"]["htmlPages"][0]["visibleHtml"] = '<span hidden>https://allowed.invalid/source</span><p>Decision</p>'
        self.assertNotIn("REPORT_BODY_RAW_REFERENCE", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_visible_body_rejects_legacy_or_equivalent_reference_band(self):
        for html in (
            '<div class="source-strip">Source A<br>Source B</div>',
            '<footer data-reference-band><p>Source A</p><p>Source B</p></footer>',
        ):
            with self.subTest(html=html):
                evidence = good_evidence()
                evidence["media"]["htmlPages"][0]["visibleHtml"] = html
                self.assertIn("REPORT_BODY_SOURCE_STRIP", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_citation_marker_requires_exactly_one_appendix_destination(self):
        evidence = good_evidence()
        evidence["media"]["appendixDestinations"] = []
        self.assertIn("REPORT_CITATION_MISMATCH", {item["code"] for item in run_qa(evidence)["blocking"]})
        evidence["media"]["appendixDestinations"] = ["ref-s-1", "ref-s-1"]
        self.assertIn("REPORT_CITATION_MISMATCH", {item["code"] for item in run_qa(evidence)["blocking"]})
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0]["visibleHtml"] = '<a href="#ref-s-1" class="citation-marker">[1]</a><span class="citation-marker">[2]</span>'
        self.assertIn("REPORT_CITATION_MISMATCH", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_citation_font_uses_approved_minimum(self):
        evidence = good_evidence()
        evidence["geometry"]["pages"][0]["fonts"].append({"role": "citation", "minimumPt": 7.4})
        self.assertIn("REPORT_FONT_TOO_SMALL", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_split_appendix_row_requires_continuation_header(self):
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0].update(
            role="references", visibleHtml='<div class="ref" data-row-split="continued">continued text</div>'
        )
        self.assertIn("REPORT_PAGE_OVERFLOW", {item["code"] for item in run_qa(evidence)["blocking"]})
        evidence["media"]["htmlPages"][0]["visibleHtml"] = (
            '<div data-continuation-header>References (continued)</div>'
            '<div class="ref" data-row-split="continued">continued text</div>'
        )
        self.assertNotIn("REPORT_PAGE_OVERFLOW", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_clean_evidence_passes_and_emits_page_and_text_manifests(self):
        result = run_qa(good_evidence())
        self.assertEqual([], result["blocking"])
        self.assertEqual("passed", result["status"])
        self.assertEqual(["page-001"], [page["id"] for page in result["pageManifest"]["pages"]])
        self.assertEqual(1, len(result["textManifest"]["pages"]))

    def test_qa_rejects_overflow_and_coverage_loss(self):
        evidence = good_evidence()
        evidence["pagination"]["pages"][0]["usedHeightPx"] = 1200
        evidence["coverage"]["output"]["panels"] = []
        result = run_qa(evidence)
        self.assertEqual(
            {"REPORT_PAGE_OVERFLOW", "REPORT_COVERAGE_MISMATCH"},
            {issue["code"] for issue in result["blocking"]},
        )

    def test_geometry_gates_media_box_overlap_clipping_empty_and_font_sizes(self):
        evidence = good_evidence()
        page = evidence["geometry"]["pages"][0]
        page.update(mediaBoxMm=[209.7, 297], overlaps=[{"a": "chart", "b": "source"}], clipped=["table"], empty=True)
        page["fonts"] = [{"role": "body", "minimumPt": 8.4}, {"role": "source", "minimumPt": 7.4}]
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertEqual({
            "REPORT_MEDIA_BOX", "REPORT_ELEMENT_OVERLAP", "REPORT_CONTENT_CLIPPED",
            "REPORT_EMPTY_PAGE", "REPORT_FONT_TOO_SMALL",
        }, codes)

    def test_text_and_page_manifests_must_match_and_resources_must_be_embedded(self):
        evidence = good_evidence()
        evidence["media"]["pdfPages"][0]["text"] = "different"
        evidence["media"]["resources"].append({"type": "image", "url": "https://example.com/a.png", "embedded": False})
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertEqual({"REPORT_TEXT_MISMATCH", "REPORT_EXTERNAL_RESOURCE"}, codes)

    def test_text_manifest_rejects_pdf_reading_order_changes(self):
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0]["text"] = "左列事实 右列反证"
        evidence["media"]["pdfPages"][0]["text"] = "右列反证 左列事实"
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertIn("REPORT_TEXT_MISMATCH", codes)

    def test_text_manifest_normalizes_pdfkit_cjk_and_punctuation_variants(self):
        evidence = good_evidence()
        evidence["media"]["htmlPages"][0]["text"] = "客户，验长见页角门风齐：｜；2024–2025"
        evidence["media"]["pdfPages"][0]["text"] = "客戶,验⻓⻅⻚⻆⻔⻛⻬:|;2024‒2025"
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertNotIn("REPORT_TEXT_MISMATCH", codes)

    def test_geometry_inventory_and_visual_baseline_cannot_be_omitted(self):
        evidence = good_evidence()
        evidence["geometry"]["pages"] = []
        evidence["regression"] = {}
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertEqual({"REPORT_PAGE_MANIFEST_MISMATCH", "REPORT_VISUAL_BASELINE_MISSING", "REPORT_QA_EVIDENCE_INVALID"}, codes)

    def test_incomplete_or_non_finite_evidence_is_rejected_without_crashing(self):
        mutations = [
            lambda value: value["pagination"]["pages"][0].pop("usedHeightPx"),
            lambda value: value["pagination"]["pages"][0].update(contentHeightPx="NaN"),
            lambda value: value["geometry"]["pages"][0].pop("overlaps"),
            lambda value: value["geometry"]["pages"][0].update(clipped="none"),
            lambda value: value["geometry"]["pages"][0].update(empty="false"),
            lambda value: value["geometry"]["pages"][0].update(fonts=[{"role": "body", "minimumPt": None}]),
            lambda value: value["media"].pop("resources"),
            lambda value: value["media"].pop("appendixDestinations"),
            lambda value: value["media"]["htmlPages"][0].pop("role"),
            lambda value: value["media"]["htmlPages"][0].pop("visibleHtml"),
            lambda value: value["media"]["htmlPages"][0].update(visibleHtml=""),
            lambda value: value["media"]["htmlPages"][0].update(visibleHtml="<span></span>"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                evidence = good_evidence()
                mutate(evidence)
                result = run_qa(evidence)
                self.assertIn("REPORT_QA_EVIDENCE_INVALID", {item["code"] for item in result["blocking"]})

    def test_exported_dom_evidence_drives_all_reference_clutter_gates(self):
        runtime = Path(os.environ.get("ALLEN_RUNTIME", ROOT))
        if not (runtime / "vendor" / "report-forge" / "node_modules" / "playwright").exists() or any(not shutil.which(name) for name in ("pdftoppm", "pdftotext")):
            self.skipTest("A4 export runtime required")
        pages = [
            ("page-001", "body", '<p>Read https://example.invalid/raw</p>'),
            ("page-002", "body", '<div class="source-strip">Source A<br>Source B</div>'),
            ("page-003", "body", '<a class="citation-marker" href="#missing">[9]</a>'),
            ("page-004", "body", '<a class="citation-marker tiny" href="#ref-ok">[1]</a>'),
            ("page-005", "references", '<aside data-component-kind="references-appendix"><div class="ref" id="ref-ok" data-row-split="continued">Reference</div><div class="ref hidden-anchor" id="ref-hidden">Hidden</div></aside>'),
            ("page-006", "references", '<p>Forged role https://example.invalid/forged</p>'),
            ("page-007", "body", '<p class="css-hidden">https://example.invalid/hidden</p><p>Visible body</p>'),
            ("page-008", "body", '<a class="citation-marker" href="#ref-hidden">[8]</a>'),
            ("page-009", "references", '<aside data-component-kind="references-appendix"><div style="width:120mm">Number https://example.invalid/advisory-guidelines-of-cloud-services-and-data-centres</div></aside>'),
        ]
        sections = "".join(
            f'<section class="page" data-page-id="{page_id}" data-page-role="{role}"><div class="page__body">{body}</div></section>'
            for page_id, role, body in pages
        )
        html = ('<!doctype html><style>@page{size:A4;margin:0}*{box-sizing:border-box}body{margin:0}'
                '.page{width:210mm;height:297mm;break-after:page;padding:20mm;font:12pt Arial;overflow-wrap:anywhere}.tiny{font-size:7pt}'
                '.css-hidden,.hidden-anchor{display:none}</style>' + sections)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, build = root / "report.html", root / "build"
            source.write_text(html)
            process = subprocess.run(["node", str(EXPORT), str(source), str(build)], cwd=ROOT,
                                     env=dict(os.environ, ALLEN_RUNTIME=str(runtime)), capture_output=True, text=True)
            self.assertEqual(0, process.returncode, process.stderr)
            media = json.loads((build / "media-manifest.json").read_text())
            geometry = json.loads((build / "geometry-manifest.json").read_text())
            self.assertEqual(["ref-ok"], media["appendixDestinations"])
            self.assertIn("citation-marker", media["htmlPages"][7]["visibleHtml"])
            evidence = good_evidence()
            evidence["pagination"] = {"pageCount": len(pages), "pages": [
                {"id": page_id, "number": index + 1, "intentionalBlank": False,
                 "usedHeightPx": 500, "contentHeightPx": 986, "geometry": {"widthMm": 210, "heightMm": 297}}
                for index, (page_id, _, _) in enumerate(pages)
            ]}
            evidence["geometry"], evidence["media"] = geometry, media
            page_hashes = json.loads((build / "visual-candidate.json").read_text())["artifacts"]["pagePngSha256"]
            candidate_pages = [{"id": page_id, "digest": page_hashes[page_id]} for page_id, _, _ in pages]
            summary = {item["id"]: item["digest"] for item in candidate_pages}
            evidence["regression"].update(
                baselineDigest=json_digest(summary), candidateDigest=json_digest(summary),
                baselinePages=candidate_pages, candidatePages=candidate_pages,
            )
            result = run_qa(evidence)
            codes = {item["code"] for item in result["blocking"]}
            self.assertTrue({"REPORT_BODY_RAW_REFERENCE", "REPORT_BODY_SOURCE_STRIP", "REPORT_CITATION_MISMATCH",
                             "REPORT_FONT_TOO_SMALL", "REPORT_PAGE_OVERFLOW"} <= codes)
            self.assertEqual(["page-001", "page-006"], [item["location"] for item in result["blocking"] if item["code"] == "REPORT_BODY_RAW_REFERENCE"])
            self.assertEqual(["page-003", "page-008"], [item["location"] for item in result["blocking"] if item["code"] == "REPORT_CITATION_MISMATCH"], result)
            self.assertEqual("body", media["htmlPages"][5]["role"])
            self.assertNotIn("example.invalid/hidden", media["htmlPages"][6]["visibleHtml"])
            self.assertEqual(
                [page["text"] for page in media["htmlPages"]],
                [page["text"] for page in media["pdfPages"]],
            )

    def test_html_pdf_and_pagination_page_ids_and_order_must_match(self):
        evidence = good_evidence()
        evidence["pagination"]["pageCount"] = 2
        evidence["pagination"]["pages"].append({
            "id": "page-002", "number": 2, "intentionalBlank": False,
            "usedHeightPx": 300, "contentHeightPx": 986,
            "geometry": {"widthMm": 210, "heightMm": 297},
        })
        evidence["geometry"]["pages"].append({
            "id": "page-002", "mediaBoxMm": [210, 297], "overlaps": [],
            "clipped": [], "empty": False, "fonts": [{"role": "body", "minimumPt": 8.5}],
        })
        evidence["media"]["htmlPages"].append({"id": "page-002", "role": "body", "text": "Second", "visibleHtml": "<p>Second</p>"})
        evidence["media"]["pdfPages"].append({"id": "page-002", "text": "Second"})
        evidence["media"]["htmlPages"].reverse()
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertIn("REPORT_PAGE_MANIFEST_MISMATCH", codes)

    def test_visual_difference_blocks_without_human_disposition(self):
        evidence = good_evidence()
        evidence["regression"].update(status="different", baselineDigest=BASELINE_DIGEST, candidateDigest=CANDIDATE_DIGEST,
                                      candidatePages=[{"id": "page-001", "digest": CHANGED_PAGE_DIGEST}],
                                      differences=VISUAL_DIFFERENCES, differenceDigest=VISUAL_DIFFERENCE_DIGEST)
        result = run_qa(evidence)
        self.assertIn("REPORT_VISUAL_REGRESSION", {item["code"] for item in result["blocking"]})

    def test_human_disposition_allows_difference_but_preserves_audit_warning(self):
        evidence = good_evidence()
        evidence["regression"].update(
            status="different", baselineDigest=BASELINE_DIGEST, candidateDigest=CANDIDATE_DIGEST,
            candidatePages=[{"id": "page-001", "digest": CHANGED_PAGE_DIGEST}],
            differences=VISUAL_DIFFERENCES, differenceDigest=VISUAL_DIFFERENCE_DIGEST,
            disposition={"decision": "accepted", "reviewer": "independent-reviewer", "reason": "Intentional hierarchy improvement", "reviewedAt": "2026-10-27T12:00:00+10:30", "baselineDigest": BASELINE_DIGEST, "candidateDigest": CANDIDATE_DIGEST, "differenceDigest": VISUAL_DIFFERENCE_DIGEST},
        )
        result = run_qa(evidence)
        self.assertEqual([], result["blocking"])
        self.assertEqual("REPORT_VISUAL_DIFFERENCE_ACCEPTED", result["warnings"][0]["code"])
        self.assertEqual(BASELINE_DIGEST, result["audit"]["visualRegression"]["baselineDigest"])

    def test_regression_manifest_and_disposition_are_bound_to_current_diff(self):
        mutations = [
            lambda regression: regression.update(status="unknown"),
            lambda regression: regression.update(baselineDigest="short"),
            lambda regression: regression.update(baselineDigest="0" * 64),
            lambda regression: regression.update(differenceDigest="0" * 64),
            lambda regression: regression.update(baselineUpdated=True),
            lambda regression: regression.update(baselinePages=[]),
        ]
        for mutate in mutations:
            evidence = good_evidence()
            mutate(evidence["regression"])
            self.assertIn("REPORT_QA_EVIDENCE_INVALID", {item["code"] for item in run_qa(evidence)["blocking"]})
        evidence = good_evidence()
        evidence["regression"].update(status="different", candidateDigest=CANDIDATE_DIGEST,
                                      candidatePages=[{"id": "page-001", "digest": CHANGED_PAGE_DIGEST}],
                                      differences=VISUAL_DIFFERENCES, differenceDigest=VISUAL_DIFFERENCE_DIGEST,
                                      disposition={"decision": "accepted", "reviewer": "reviewer", "reason": "accepted", "reviewedAt": "2026-10-27T12:00:00+10:30", "baselineDigest": BASELINE_DIGEST, "candidateDigest": "0" * 64, "differenceDigest": VISUAL_DIFFERENCE_DIGEST})
        self.assertIn("REPORT_VISUAL_REGRESSION", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_regression_differences_are_rederived_and_cannot_be_omitted(self):
        evidence = good_evidence()
        evidence["regression"].update(status="different", candidateDigest=CANDIDATE_DIGEST,
                                      candidatePages=[{"id": "page-001", "digest": CHANGED_PAGE_DIGEST}],
                                      differences=[], differenceDigest=EMPTY_DIFFERENCE_DIGEST)
        self.assertIn("REPORT_QA_EVIDENCE_INVALID", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_regression_derives_added_and_removed_pages_in_stable_order(self):
        evidence = good_evidence()
        baseline_pages = [{"id": "page-000", "digest": "1" * 64}]
        differences = [
            {"page": "page-000", "kind": "removed", "baseline": "1" * 64, "candidate": None},
            {"page": "page-001", "kind": "added", "baseline": None, "candidate": PAGE_DIGEST},
        ]
        evidence["regression"].update(
            status="different", baselinePages=baseline_pages,
            baselineDigest=json_digest({"page-000": "1" * 64}),
            differences=differences, differenceDigest=json_digest(differences),
        )
        result = run_qa(evidence)
        self.assertNotIn("REPORT_QA_EVIDENCE_INVALID", {item["code"] for item in result["blocking"]})

    def test_disposition_timestamp_requires_valid_iso8601_timezone(self):
        for timestamp in ["not-a-date", "2026-10-27T12:00:00"]:
            evidence = good_evidence()
            evidence["regression"].update(
                status="different", candidateDigest=CANDIDATE_DIGEST,
                candidatePages=[{"id": "page-001", "digest": CHANGED_PAGE_DIGEST}],
                differences=VISUAL_DIFFERENCES, differenceDigest=VISUAL_DIFFERENCE_DIGEST,
                disposition={"decision": "accepted", "reviewer": "reviewer", "reason": "accepted", "reviewedAt": timestamp,
                             "baselineDigest": BASELINE_DIGEST, "candidateDigest": CANDIDATE_DIGEST, "differenceDigest": VISUAL_DIFFERENCE_DIGEST},
            )
            self.assertIn("REPORT_VISUAL_REGRESSION", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_duplicate_or_invalid_coverage_and_page_ids_are_rejected(self):
        mutations = [
            lambda value: value["coverage"]["input"].update(claims=["cl-1", "cl-1"]),
            lambda value: value["pagination"]["pages"][0].update(id="bad"),
            lambda value: value["pagination"]["pages"][0].update(number=2),
            lambda value: value["geometry"]["pages"].append(dict(value["geometry"]["pages"][0])),
            lambda value: value["media"]["htmlPages"].append(dict(value["media"]["htmlPages"][0])),
            lambda value: value["media"]["pdfPages"].append(dict(value["media"]["pdfPages"][0])),
        ]
        for mutate in mutations:
            evidence = good_evidence()
            mutate(evidence)
            result = run_qa(evidence)
            self.assertIn("REPORT_QA_EVIDENCE_INVALID", {item["code"] for item in result["blocking"]})
        evidence = good_evidence()
        evidence["coverage"]["output"]["claims"].append("orphan")
        self.assertIn("REPORT_COVERAGE_MISMATCH", {item["code"] for item in run_qa(evidence)["blocking"]})

    def test_result_is_deterministic_and_issues_are_sorted(self):
        evidence = good_evidence()
        evidence["coverage"]["output"] = {key: [] for key in evidence["coverage"]["input"]}
        first = run_qa(evidence)
        second = run_qa(evidence)
        self.assertEqual(first, second)
        self.assertEqual(first["blocking"], sorted(first["blocking"], key=lambda item: (item["code"], item["location"], item["detail"])))

    def test_pdf_media_box_parser_uses_point_geometry(self):
        visual = load_visual()
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "sample.pdf"
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page /MediaBox [0 0 595.276 841.89] >> endobj\n%%EOF")
            self.assertEqual([[210.0, 297.0]], visual.pdf_media_boxes_mm(pdf))

    def test_visual_manifest_never_mutates_baseline(self):
        visual = load_visual()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.bin"
            candidate = root / "candidate.bin"
            baseline.write_bytes(b"approved")
            candidate.write_bytes(b"changed")
            before = baseline.read_bytes()
            result = visual.compare_files(baseline, candidate)
            self.assertEqual(before, baseline.read_bytes())
            self.assertEqual("different", result["status"])
            self.assertNotEqual(result["baselineDigest"], result["candidateDigest"])

    def test_visual_manifest_reports_page_level_differences_without_approval(self):
        visual = load_visual()
        baseline = {"artifacts": {"pagePngSha256": {"page-01.png": "a" * 64, "page-02.png": "b" * 64}}}
        candidate = {"artifacts": {"pagePngSha256": {"page-01.png": "a" * 64, "page-02.png": "c" * 64}}}
        result = visual.compare_manifests(baseline, candidate)
        self.assertEqual([{"page": "page-02.png", "kind": "changed", "baseline": "b" * 64, "candidate": "c" * 64}], result["differences"])
        self.assertNotIn("disposition", result)

    def test_visual_manifests_require_nonempty_exact_pagination_page_set(self):
        visual = load_visual()
        valid = {"artifacts": {"pagePngSha256": {"page-001": "a" * 64}}}
        cases = [
            ({"artifacts": {"pagePngSha256": {}}}, valid, ["page-001"]),
            (valid, {"artifacts": {"pagePngSha256": {}}}, ["page-001"]),
            (valid, {"artifacts": {"pagePngSha256": {"wrong": "a" * 64}}}, ["page-001"]),
            ({"artifacts": {"pagePngSha256": {"page-001": "not-a-hash"}}}, valid, ["page-001"]),
        ]
        for baseline, candidate, pages in cases:
            with self.subTest(baseline=baseline, candidate=candidate):
                result = visual.compare_manifests(baseline, candidate, pages)
                self.assertEqual("invalid", result["status"])
                self.assertTrue(result["errors"])

    def test_visual_compare_added_and_removed_pages_feed_qa_approval_path(self):
        visual = load_visual()
        baseline = {"artifacts": {"pagePngSha256": {
            "page-000": "0" * 64,
            "page-002": "2" * 64,
        }}}
        candidate = {"artifacts": {"pagePngSha256": {
            "page-001": PAGE_DIGEST,
            "page-002": "2" * 64,
        }}}
        regression = visual.compare_manifests(baseline, candidate, ["page-001", "page-002"])
        self.assertEqual(["page-000", "page-002"], [page["id"] for page in regression["baselinePages"]])
        self.assertEqual(["page-001", "page-002"], [page["id"] for page in regression["candidatePages"]])
        self.assertEqual(
            [
                {"page": "page-000", "kind": "removed", "baseline": "0" * 64, "candidate": None},
                {"page": "page-001", "kind": "added", "baseline": None, "candidate": PAGE_DIGEST},
            ],
            regression["differences"],
        )

        evidence = good_evidence()
        evidence["pagination"]["pageCount"] = 2
        evidence["pagination"]["pages"].append({"id": "page-002", "number": 2, "intentionalBlank": False, "role": "section-divider", "usedHeightPx": 450, "contentHeightPx": 986, "whitespaceJustification": "section-transition", "geometry": {"widthMm": 210, "heightMm": 297}})
        evidence["geometry"]["pages"].append({"id": "page-002", "mediaBoxMm": [210, 297], "overlaps": [], "clipped": [], "empty": False, "fonts": [{"role": "body", "minimumPt": 8.5}]})
        evidence["media"]["htmlPages"].append({"id": "page-002", "role": "section-divider", "text": "Second", "visibleHtml": "<p>Second</p>"})
        evidence["media"]["pdfPages"].append({"id": "page-002", "text": "Second"})
        evidence["regression"] = regression
        blocked = run_qa(evidence)
        self.assertNotIn("REPORT_QA_EVIDENCE_INVALID", {item["code"] for item in blocked["blocking"]})
        self.assertIn("REPORT_VISUAL_REGRESSION", {item["code"] for item in blocked["blocking"]})
        regression["disposition"] = {
            "decision": "accepted", "reviewer": "independent-reviewer", "reason": "Intentional pagination change",
            "reviewedAt": "2026-10-27T12:00:00+10:30", "baselineDigest": regression["baselineDigest"],
            "candidateDigest": regression["candidateDigest"], "differenceDigest": regression["differenceDigest"],
        }
        approved = run_qa(evidence)
        self.assertEqual([], approved["blocking"])
        self.assertEqual("REPORT_VISUAL_DIFFERENCE_ACCEPTED", approved["warnings"][0]["code"])


if __name__ == "__main__":
    unittest.main()
