import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
QA = ROOT / "out-report" / "scripts" / "a4" / "qa.cjs"
VISUAL = ROOT / "out-report" / "scripts" / "a4" / "visual_regression.py"


def load_visual():
    spec = importlib.util.spec_from_file_location("visual_regression", VISUAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def good_evidence():
    return {
        "pagination": {
            "pageCount": 1,
            "pages": [{
                "id": "page-001", "number": 1, "intentionalBlank": False,
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
            "htmlPages": [{"id": "page-001", "text": "Decision evidence source"}],
            "pdfPages": [{"id": "page-001", "text": "Decision evidence source"}],
            "resources": [{"type": "font", "url": "data:font/woff2;base64,AA==", "embedded": True}],
        },
        "regression": {"baselineDigest": "abc", "candidateDigest": "abc", "differences": []},
    }


def run_qa(evidence):
    process = subprocess.run(
        ["node", str(QA)], cwd=ROOT, input=json.dumps(evidence),
        capture_output=True, text=True,
    )
    if process.returncode:
        raise AssertionError(process.stderr)
    return json.loads(process.stdout)


class A4QualityGateTest(unittest.TestCase):
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

    def test_geometry_inventory_and_visual_baseline_cannot_be_omitted(self):
        evidence = good_evidence()
        evidence["geometry"]["pages"] = []
        evidence["regression"] = {}
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertEqual({"REPORT_PAGE_MANIFEST_MISMATCH", "REPORT_VISUAL_BASELINE_MISSING"}, codes)

    def test_incomplete_or_non_finite_evidence_is_rejected_without_crashing(self):
        mutations = [
            lambda value: value["pagination"]["pages"][0].pop("usedHeightPx"),
            lambda value: value["pagination"]["pages"][0].update(contentHeightPx="NaN"),
            lambda value: value["geometry"]["pages"][0].pop("overlaps"),
            lambda value: value["geometry"]["pages"][0].update(clipped="none"),
            lambda value: value["geometry"]["pages"][0].update(empty="false"),
            lambda value: value["geometry"]["pages"][0].update(fonts=[{"role": "body", "minimumPt": None}]),
            lambda value: value["media"].pop("resources"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                evidence = good_evidence()
                mutate(evidence)
                result = run_qa(evidence)
                self.assertIn("REPORT_QA_EVIDENCE_INVALID", {item["code"] for item in result["blocking"]})

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
        evidence["media"]["htmlPages"].append({"id": "page-002", "text": "Second"})
        evidence["media"]["pdfPages"].append({"id": "page-002", "text": "Second"})
        evidence["media"]["htmlPages"].reverse()
        codes = {item["code"] for item in run_qa(evidence)["blocking"]}
        self.assertIn("REPORT_PAGE_MANIFEST_MISMATCH", codes)

    def test_visual_difference_blocks_without_human_disposition(self):
        evidence = good_evidence()
        evidence["regression"] = {"baselineDigest": "old", "candidateDigest": "new", "differences": [{"page": 1, "ratio": 0.04}]}
        result = run_qa(evidence)
        self.assertIn("REPORT_VISUAL_REGRESSION", {item["code"] for item in result["blocking"]})

    def test_human_disposition_allows_difference_but_preserves_audit_warning(self):
        evidence = good_evidence()
        evidence["regression"] = {
            "baselineDigest": "old", "candidateDigest": "new", "differences": [{"page": 1, "ratio": 0.04}],
            "disposition": {"decision": "accepted", "reviewer": "independent-reviewer", "reason": "Intentional hierarchy improvement", "reviewedAt": "2026-10-27T12:00:00+10:30"},
        }
        result = run_qa(evidence)
        self.assertEqual([], result["blocking"])
        self.assertEqual("REPORT_VISUAL_DIFFERENCE_ACCEPTED", result["warnings"][0]["code"])
        self.assertEqual("old", result["audit"]["visualRegression"]["baselineDigest"])

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
        baseline = {"artifacts": {"pagePngSha256": {"page-01.png": "aaa", "page-02.png": "bbb"}}}
        candidate = {"artifacts": {"pagePngSha256": {"page-01.png": "aaa", "page-02.png": "ccc"}}}
        result = visual.compare_manifests(baseline, candidate)
        self.assertEqual([{"page": "page-02.png", "baseline": "bbb", "candidate": "ccc"}], result["differences"])
        self.assertNotIn("disposition", result)

    def test_visual_manifests_require_nonempty_exact_pagination_page_set(self):
        visual = load_visual()
        valid = {"artifacts": {"pagePngSha256": {"page-001": "a"}}}
        cases = [
            ({"artifacts": {"pagePngSha256": {}}}, valid, ["page-001"]),
            (valid, {"artifacts": {"pagePngSha256": {}}}, ["page-001"]),
            (valid, {"artifacts": {"pagePngSha256": {"wrong": "a"}}}, ["page-001"]),
            ({"artifacts": {"pagePngSha256": {"page-001": "a", "page-002": "b"}}}, valid, ["page-001"]),
        ]
        for baseline, candidate, pages in cases:
            with self.subTest(baseline=baseline, candidate=candidate):
                result = visual.compare_manifests(baseline, candidate, pages)
                self.assertEqual("invalid", result["status"])
                self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
