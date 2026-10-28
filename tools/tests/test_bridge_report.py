import copy
import json
import pathlib
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
        self.ledger.patch("cards", "card-0001", {"source_refs": [{"source_id": "M001", "locator": "附录 A"}]})
        report, coverage = self.build()
        self.assertEqual(report["version"], "1.0.0")
        self.assertEqual(report["metadata"]["title"], "星河数据科技经营概览")
        self.assertEqual(report["metadata"]["bibliography_policy"], "evidence_package")
        self.assertEqual(report["metadata"]["client_citations"], "compact")
        blocks = [b for section in report["sections"] for b in section["blocks"]]
        self.assertEqual([b["id"] for b in blocks], ["p02-bars", "p02-note", "p03-kpi", "p03-steps"])
        self.assertEqual(blocks[0]["kind"], "chart")
        self.assertTrue(blocks[0]["content"]["anchor"])
        self.assertEqual(blocks[0]["panel_refs"], ["bars"])
        self.assertEqual(blocks[0]["relation_refs"], ["bars-note"])
        self.assertEqual(blocks[0]["content"]["role"], "primary")
        self.assertEqual(blocks[0]["content"]["alternative"], "并排数字卡")
        self.assertEqual(blocks[0]["content"]["tradeoff"], "柱形更适合比较绝对规模")
        self.assertEqual(blocks[0]["content"]["capacity"], {"items": 2})
        self.assertEqual(blocks[0]["content"]["semantic_type"], "comparison")
        self.assertEqual(blocks[0]["content"]["visual"], "两年收入柱形")
        self.assertEqual(blocks[0]["content"]["slot"], "main")
        self.assertEqual(blocks[0]["content"]["span"], 2)
        self.assertEqual(blocks[2]["kind"], "metric")
        self.assertEqual(blocks[3]["kind"], "table")
        self.assertEqual(report["sections"][0]["relations"][0]["panel_refs"], ["bars", "note"])
        self.assertEqual(coverage["input"], coverage["output"])
        self.assertEqual(coverage["input"]["panels"], ["bars", "kpi", "note", "steps"])
        self.assertEqual(coverage["input"]["relations"], ["bars-note", "kpi-steps"])
        self.assertEqual(coverage["input"]["a_cards"], ["card-0001"])
        self.assertEqual(coverage["input"]["metrics"], ["m-0001", "m-0002", "m-0003", "m-0007"])
        self.assertEqual(coverage["input"]["sources"], ["M001"])
        self.assertEqual(coverage["input"]["answer_claims"], ["cl-0001"])
        self.assertEqual(blocks[0]["source_bindings"], [{"source_id": "M001", "locators": ["p12"]}])
        self.assertEqual(report["references"][0]["locators"], ["p12", "p30", "附录 A"])

    def test_build_carries_claims_and_decision_research_into_semantic_blocks(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["panels"][0]["semantic_type"] = "pain-demand"
        slides["slides"][2]["panels"][1]["semantic_type"] = "competition"
        evidence_dir = pathlib.Path(self.task) / "03_evidence"
        evidence_dir.mkdir(exist_ok=True)
        (evidence_dir / "decision-research.json").write_text(json.dumps({
            "version": 1,
            "material": {"pain": True, "competition": True, "pricing": False},
            "pain": [{
                "id": "pain-1", "segment": "AI 应用创业公司", "trigger": "流量突增",
                "workaround": "排队或包卡", "consequence": "闲置成本或交付延迟",
                "purchase_signal": "接受带价格试点", "support_claim_refs": ["cl-0001"],
                "counter_claim_refs": ["cl-0002"], "confidence": "medium",
                "validation_gap": "尚无目标客户采购样本",
            }],
            "competition": {
                "layers": {
                    "direct": [{"name": "专业 GPU 云", "claim_refs": ["cl-0002"],
                                "values": {"总拥有成本": "官方价可比", "可靠性": "缺同口径状态数据"}}],
                    "do_nothing": [{"name": "延后任务", "claim_refs": ["cl-0002"]}],
                },
                "criteria": ["总拥有成本", "可靠性"], "claim_refs": ["cl-0002"],
            },
            "methods": [], "critical_claim_refs": [], "claim_risk_assessments": [],
        }, ensure_ascii=False), encoding="utf-8")

        report, _ = self.build(slides)
        blocks = [block for section in report["sections"] for block in section["blocks"]]
        pain = next(block for block in blocks if block["content"].get("semantic_type") == "pain-demand")
        competition = next(block for block in blocks if block["content"].get("semantic_type") == "competition")

        self.assertEqual("收入从 1800 万元增至 3200 万元", pain["content"]["claims"][0]["statement"])
        self.assertEqual("high", pain["content"]["claims"][0]["confidence"])
        self.assertEqual("虚构数据", pain["content"]["claims"][0]["limitation"])
        self.assertEqual("support", pain["content"]["claims"][0]["support_label"])
        self.assertEqual("营业收入 3200 万元，上年 1800 万元", pain["content"]["claims"][0]["support"][0]["excerpt"])
        self.assertEqual("AI 应用创业公司", pain["content"]["pain_groups"][0]["segment"])
        self.assertEqual("尚无目标客户采购样本", pain["content"]["pain_groups"][0]["validation_gap"])
        self.assertEqual(["总拥有成本", "可靠性"], competition["content"]["comparison"]["criteria"])
        self.assertEqual("direct", competition["content"]["comparison"]["alternatives"][0]["layer"])
        self.assertEqual("官方价可比", competition["content"]["comparison"]["alternatives"][0]["values"]["总拥有成本"])
        self.assertEqual("缺同口径状态数据", competition["content"]["comparison"]["alternatives"][0]["values"]["可靠性"])
        recommendation = next(detail for block in blocks for detail in block["content"]["claims"] if detail["id"] == "cl-0004")
        self.assertEqual("indirect_lead", recommendation["support_label"])

    def test_report_matches_schema_and_schema_self_checks(self):
        schema = schema_check.load("report.schema.json")
        self.assertEqual(schema_check.self_check(schema), [])
        report, _ = self.build()
        self.assertEqual(schema_check.check_document(schema, report, "report.json"), [])

    def test_legacy_v1_report_without_citation_registry_remains_valid(self):
        report, _ = self.build()
        report.pop("citation_registry")
        self.assertEqual([], T.validate_report(report))

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

    def test_duplicate_ledger_ids_fail_before_indexing(self):
        for table in ("claims", "metrics", "sources", "cards"):
            with self.subTest(table=table), tempfile.TemporaryDirectory() as task:
                ledger = F.make_report_ledger(task)
                duplicate = ledger.read(table)[0]
                with ledger.path(table).open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(duplicate, ensure_ascii=False) + "\n")
                with self.assertRaises(T.ReportError) as cm:
                    T.build(task, F.report_slides(), F.report_sidecar())
                self.assertEqual(cm.exception.code, "REPORT_COVERAGE_MISMATCH")
                self.assertIn(f"{table} 重复 id", str(cm.exception))

    def test_duplicate_evidence_id_fails(self):
        duplicate = self.ledger.read("evidence")[0]
        with self.ledger.path("evidence").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(duplicate, ensure_ascii=False) + "\n")
        error = self.error(self.slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("evidence 重复 id", str(error))

    def test_duplicate_claim_evidence_id_fails(self):
        duplicate = self.ledger.read("claim_evidence")[0]
        with self.ledger.path("claim_evidence").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(duplicate, ensure_ascii=False) + "\n")
        error = self.error(self.slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("claim_evidence 重复 id", str(error))

    def test_dangling_claim_evidence_fails(self):
        links = self.ledger.read("claim_evidence")
        links[0]["evidence_id"] = "ev-9999"
        self.ledger.path("claim_evidence").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in links), encoding="utf-8")
        error = self.error(self.slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("不存在的 evidence:ev-9999", str(error))

    def test_malformed_claim_is_report_error_not_key_error(self):
        claims = self.ledger.read("claims")
        del claims[0]["kind"]
        self.ledger.path("claims").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in claims), encoding="utf-8")
        error = self.error(self.slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("kind：必填", str(error))

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

    def test_a_card_without_claim_id_fails_coverage(self):
        self.ledger.add("cards", {"type": "background", "content": "核心背景", "meaning": "影响结论",
                                  "value_tier": "A", "topic": "背景", "nature": "fact",
                                  "confidence": "high", "confidence_reason": "虚构测试"})
        error = self.error(self.slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("缺少 claim_id", str(error))

    def test_unknown_answer_claim_reference_fails(self):
        slides = copy.deepcopy(self.slides)
        slides["deck"]["answer_claim_refs"].append("cl-9999")
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("answer_claim_refs 引用了未知 claim：cl-9999", str(error))

    def test_unknown_claim_reference_fails(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["claim_refs"].append("cl-9999")
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("未知 claim", str(error))

    def test_relation_requires_two_distinct_panels(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["relations"][0]["panel_refs"] = ["bars", "bars"]
        error = self.error(slides)
        self.assertEqual(error.code, "REPORT_COVERAGE_MISMATCH")
        self.assertIn("至少两个不同 panel", str(error))

    def test_build_is_deterministic(self):
        first = self.build()
        second = self.build()
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )

    def test_citation_registry_follows_first_body_appearance_then_appendix_order(self):
        report, _ = self.build()
        body_ids = []
        for section in report["sections"]:
            for block in section["blocks"]:
                for source_id in block["source_ids"]:
                    if source_id not in body_ids:
                        body_ids.append(source_id)
        appendix_only = sorted(set(report["registry"]["source_ids"]) - set(body_ids))
        expected = body_ids + appendix_only
        self.assertEqual(expected, [item["source_id"] for item in report["citation_registry"]])
        self.assertEqual(list(range(1, len(expected) + 1)), [item["number"] for item in report["citation_registry"]])
        self.assertEqual([f"source-{source_id}" for source_id in expected],
                         [item["appendix_anchor"] for item in report["citation_registry"]])

    def test_citation_registry_contains_each_source_once(self):
        report, _ = self.build()
        registry_ids = [item["source_id"] for item in report["citation_registry"]]
        self.assertEqual(len(registry_ids), len(set(registry_ids)))

    def test_reference_records_preserve_full_audit_fields(self):
        self.ledger.patch("sources", "M001", {"author_org": "Research team", "publisher": "Exchange",
                                                "conflict_of_interest": "Issuer-authored"})
        report, _ = self.build()
        reference = report["references"][0]
        for field in ("title", "author", "publisher", "published", "accessed", "url", "locators", "grade",
                      "conflict_of_interest"):
            self.assertIn(field, reference)

    def test_full_bibliography_requires_explicit_selection(self):
        report, _ = T.build(self.task, self.slides, F.report_sidecar(), bibliography_policy="full")
        self.assertEqual("full", report["metadata"]["bibliography_policy"])

        with self.assertRaises(T.ReportError) as cm:
            T.build(self.task, self.slides, F.report_sidecar(), bibliography_policy="unexpected")
        self.assertIn("bibliography_policy", str(cm.exception))

    def test_validate_report_rejects_duplicate_and_unknown_internal_refs(self):
        report, _ = self.build()
        cases = []
        bad = copy.deepcopy(report)
        bad["sections"][1]["blocks"][0]["id"] = bad["sections"][0]["blocks"][0]["id"]
        cases.append((bad, "重复 block id"))
        for field, value, message in (
                ("claim_refs", "cl-9999", "未知 claim"),
                ("metric_refs", "m-9999", "未知 metric"),
                ("source_ids", "M999", "未知 source"),
                ("panel_refs", "ghost", "未知 panel"),
                ("relation_refs", "ghost-rel", "未知 relation")):
            bad = copy.deepcopy(report)
            bad["sections"][0]["blocks"][0][field].append(value)
            cases.append((bad, message))
        for bad, message in cases:
            with self.subTest(message=message), self.assertRaises(T.ReportError) as cm:
                T.validate_report(bad)
            self.assertEqual(cm.exception.code, "REPORT_COVERAGE_MISMATCH")
            self.assertIn(message, str(cm.exception))

    def test_validate_report_rejects_unregistered_a_card(self):
        report, _ = self.build()
        report["executive_summary"]["a_card_refs"].append("card-9999")
        with self.assertRaises(T.ReportError) as cm:
            T.validate_report(report)
        self.assertIn("未知 card", str(cm.exception))

    def test_validate_report_rejects_fictitious_registry_items(self):
        additions = {"claim_ids": "cl-9999", "metric_ids": "m-9999", "source_ids": "M999",
                     "panel_ids": "ghost", "relation_ids": "ghost-rel", "card_ids": "card-9999"}
        for field, value in additions.items():
            with self.subTest(field=field):
                report, _ = self.build()
                report["registry"][field].append(value)
                with self.assertRaises(T.ReportError) as cm:
                    T.validate_report(report)
                self.assertIn(f"registry.{field} 与报告实际内容不一致", str(cm.exception))

    def test_validate_report_rejects_duplicate_reference_source(self):
        report, _ = self.build()
        report["references"].append(copy.deepcopy(report["references"][0]))
        with self.assertRaises(T.ReportError) as cm:
            T.validate_report(report)
        self.assertIn("重复 references source id", str(cm.exception))

    def test_validate_report_rejects_duplicate_source_bindings_and_locators(self):
        report, _ = self.build()
        binding = report["sections"][0]["blocks"][0]["source_bindings"][0]
        binding["locators"].append(binding["locators"][0])
        with self.assertRaises(T.ReportError) as cm:
            T.validate_report(report)
        self.assertIn("source binding locator", str(cm.exception))

        report, _ = self.build()
        bindings = report["sections"][0]["blocks"][0]["source_bindings"]
        bindings.append(copy.deepcopy(bindings[0]))
        with self.assertRaises(T.ReportError) as cm:
            T.validate_report(report)
        self.assertIn("source binding", str(cm.exception))

    def test_error_string_contains_code(self):
        slides = copy.deepcopy(self.slides)
        slides["slides"][1]["panels"][0]["form"] = "canvas.magic"
        error = self.error(slides)
        self.assertTrue(str(error).startswith("REPORT_UNSUPPORTED_BLOCK: "))


if __name__ == "__main__":
    unittest.main()
