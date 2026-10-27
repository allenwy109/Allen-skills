import copy
import json
import tempfile
import unittest

from tools.bridge import to_report as T
from tools.lib import schema_check
from tools.tests import fixtures as F


class ReportContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = self.tmp.name
        self.ledger = F.make_report_ledger(self.task)
        self.slides = F.report_slides()

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, slides=None):
        return T.build(self.task, slides or self.slides, F.report_sidecar())

    def error(self, slides):
        with self.assertRaises(T.ReportError) as cm:
            self.build(slides)
        return cm.exception

    def test_build_preserves_panels_relations_anchor_and_coverage(self):
        report, coverage = self.build()
        self.assertEqual(report["version"], "1.0.0")
        self.assertEqual(report["metadata"]["title"], "星河数据科技经营概览")
        blocks = [b for section in report["sections"] for b in section["blocks"]]
        self.assertEqual([b["id"] for b in blocks], ["p02-bars", "p02-note", "p03-kpi", "p03-steps"])
        self.assertEqual(blocks[0]["kind"], "chart")
        self.assertTrue(blocks[0]["content"]["anchor"])
        self.assertEqual(blocks[0]["panel_refs"], ["bars"])
        self.assertEqual(blocks[0]["relation_refs"], ["bars-note"])
        self.assertEqual(blocks[2]["kind"], "metric")
        self.assertEqual(blocks[3]["kind"], "table")
        self.assertEqual(report["sections"][0]["relations"][0]["panel_refs"], ["bars", "note"])
        self.assertEqual(coverage["input"], coverage["output"])
        self.assertEqual(coverage["input"]["panels"], ["bars", "kpi", "note", "steps"])
        self.assertEqual(coverage["input"]["relations"], ["bars-note", "kpi-steps"])
        self.assertEqual(coverage["input"]["a_cards"], ["card-0001"])
        self.assertEqual(coverage["input"]["metrics"], ["m-0001", "m-0002", "m-0003", "m-0007"])
        self.assertEqual(coverage["input"]["sources"], ["M001"])

    def test_report_matches_schema_and_schema_self_checks(self):
        schema = schema_check.load("report.schema.json")
        self.assertEqual(schema_check.self_check(schema), [])
        report, _ = self.build()
        self.assertEqual(schema_check.check_document(schema, report, "report.json"), [])

    def test_unknown_form_has_stable_error_code(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["panels"][0]["form"] = "canvas.magic"
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_UNSUPPORTED_BLOCK")
        self.assertIn("canvas.magic", str(error))

    def test_duplicate_panel_id_fails(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][2]["panels"][0]["id"] = "bars"
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("重复 panel id", str(error))

    def test_unknown_and_orphan_panel_references_fail(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["relations"][0]["panel_refs"][1] = "ghost"
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("未知 panel", str(error))

        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["relations"] = []
        error = self.error(slides)
        self.assertIn("孤儿 panel", str(error))

    def test_missing_a_card_claim_fails_coverage(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["claim_refs"] = []
        slides["slides"][1]["metric_refs"] = []
        slides["slides"][1]["panels"] = []
        slides["slides"][1]["relations"] = []
        slides["slides"][1].pop("anchor_panel")
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("A 级卡片", str(error))

    def test_unknown_claim_reference_fails(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["claim_refs"].append("cl-9999")
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("未知 claim", str(error))

    def test_build_is_deterministic(self):
        first = self.build()
        second = self.build()
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
