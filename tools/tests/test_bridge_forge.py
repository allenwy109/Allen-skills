import copy
import tempfile
import unittest

from tools.bridge import to_forge as T
from tools.tests import fixtures as F


class BuildTest(unittest.TestCase):
    """slides.json + 证据账 → report-forge 蓝图：正向映射与必须拦截的情况（设计 §6.2 第 3 步）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = self.tmp.name
        self.led = F.make_report_ledger(self.task)
        self.slides = F.report_slides()

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, slides=None, sidecar=None, allow=()):
        return T.build(self.task, slides or self.slides, sidecar, allow)

    def problems(self, slides=None, sidecar=None):
        with self.assertRaises(T.BridgeError) as cm:
            self.build(slides, sidecar)
        return "\n".join(cm.exception.problems)

    def page(self, slides, n):
        return next(s for s in slides["slides"] if s["page"] == n)

    def test_claims_metrics_and_identity(self):
        r = self.build(sidecar=F.report_sidecar())
        claims = {c["id"]: c for c in r["blueprint"]["claims"]}
        self.assertEqual(list(claims), ["cl-0001", "cl-0003", "cl-0004", "cl-0005"])
        self.assertEqual(claims["cl-0001"]["kind"], "fact")            # data → fact
        self.assertEqual(claims["cl-0001"]["verification"], "source_checked")
        self.assertEqual(claims["cl-0001"]["statement"], "收入从 {{metric:m-0001}}增至 {{metric:m-0002}}")
        self.assertEqual([m["id"] for m in claims["cl-0001"]["metrics"]], ["m-0001", "m-0002", "m-0003"])  # 缺失的 m-0004 不进入
        self.assertEqual(claims["cl-0001"]["metrics"][2]["formula"], {"op": "percent_change", "args": ["m-0002", "m-0001"]})
        self.assertIn("单一来源", claims["cl-0003"]["limitation"])
        self.assertIn("近似值（管理层指引）", claims["cl-0003"]["limitation"])
        self.assertNotIn("m-0007", claims["cl-0003"]["limitation"])   # 页面上不出现指标编号
        self.assertEqual((claims["cl-0005"]["kind"], claims["cl-0005"]["verification"]), ("assumption", "not_applicable"))
        self.assertEqual(claims["cl-0005"]["statement"], "主要客户已签三年合同（待确认）")
        self.assertEqual(r["blueprint"]["sources"]["M001"]["locator"], "https://example.com/report · p12、p30")
        self.assertEqual(r["references"][0]["url"], "https://example.com/report")
        self.assertEqual(r["a_cards"], {"checked": 1, "missing": []})
        self.assertEqual(r["blueprint"]["analysis"]["synthesis"]["answerClaimRefs"], ["cl-0001"])

    def test_slides_and_composition(self):
        bp = self.build(sidecar=F.report_sidecar())["blueprint"]
        self.assertEqual([s["id"] for s in bp["slides"]], ["p01", "p02", "p03", "p04"])
        p2 = bp["slides"][1]
        self.assertEqual(p2["title"], "收入两年增长 {{metric:m-0003}}，规模仍小")
        self.assertEqual(p2["cornerLabel"], "01 收入")
        self.assertTrue(p2["speakerIntent"].startswith("先看两年柱形"))
        comp = p2["exhibit"]["semantics"]["composition"]
        self.assertEqual(comp["readingOrder"], ["bars", "note"])
        self.assertEqual(comp["panels"]["bars"]["selection"]["relationship"], "comparison")
        self.assertEqual(p2["visual"]["regions"][0], {"slot": "main", "role": "primary", "span": 2, "panelRef": "bars"})
        self.assertEqual(bp["slides"][2]["exhibit"]["semantics"]["composition"]["panels"]["kpi"]["capacity"], {"items": 1})
        self.assertEqual(bp["deck"]["arc"], "evidence-to-view")
        self.assertNotIn("arcReason", bp["deck"])

    def test_refuted_claim_is_rewritten(self):
        self.led.add("sources", {"origin": "web", "title": "行业协会通报", "url": "https://example.com/notice", "published": "2026-05-01",
                                 "published_precision": "day", "accessed": "2026-10-22T10:00:00+08:00", "tier": "secondary", "grade": "A",
                                 "capture_method": "script", "access": "full"}, line="M")
        self.led.add("evidence", {"source_id": "M002", "locator": "第 2 段", "excerpt": "该公司不是行业第一", "attribute": "actual", "numeric": False})
        self.led.add("claims", F.claim(kind="fact", statement="公司是行业第一", verification="refuted", unit="不适用：定性", calculation="不适用：定性",
                                     counterevidence="行业协会通报否认"))
        self.led.add("claim_evidence", {"claim_id": "cl-0006", "evidence_id": "ev-0003", "relation": "contradicts", "applicable_scope": "全国"})
        slides = copy.deepcopy(self.slides)
        self.page(slides, 3)["claim_refs"].append("cl-0006")
        c = next(c for c in self.build(slides)["blueprint"]["claims"] if c["id"] == "cl-0006")
        self.assertEqual(c["statement"], "曾认为公司是行业第一，已被推翻")
        self.assertEqual(c["kind"], "assumption")
        self.assertEqual(c["limitation"], "反证：行业协会通报（M002）")

    def test_user_material_is_provided(self):
        self.led.patch("sources", "M001", {"origin": "user"})
        claims = self.build()["blueprint"]["claims"]
        self.assertEqual(claims[0]["verification"], "provided")

    def test_only_web_links_reach_references(self):
        self.led.patch("sources", "M001", {"origin": "user", "url": "file:星河-年报摘要.pdf"})
        ref = self.build()["references"][0]
        self.assertNotIn("url", ref)
        self.assertEqual(ref["kind"], "用户提供材料")
        self.assertEqual(self.build()["blueprint"]["sources"]["M001"]["locator"], "用户提供材料 · p12、p30")
        self.led.patch("sources", "M001", {"origin": "web", "url": "ftp://example.com/a.pdf"})
        self.assertNotIn("url", self.build()["references"][0])

    def test_blocks_bare_number(self):
        slides = copy.deepcopy(self.slides)
        self.page(slides, 2)["proves"] = "收入从 1800 万元增至 3200 万元，毛利 999 万元"
        self.assertIn("数字 999 不是任何进入报告的指标的显示值", self.problems(slides))

    def test_allow_lets_number_through(self):
        slides = copy.deepcopy(self.slides)
        self.page(slides, 2)["proves"] = "收入从 1800 万元增至 3200 万元，分 3 个阶段"
        r = self.build(slides, allow=["3"])
        self.assertEqual(r["trace"]["allowed"], ["3"])

    def test_blocks_number_in_subtitle_and_notes(self):
        slides = copy.deepcopy(self.slides)
        self.page(slides, 2)["subtitle"] = "单位：万元｜样本 120 家"
        side = F.report_sidecar()
        side["speaker_notes"][0]["text"] = "毛利率 35%"
        text = self.problems(slides, side)
        self.assertIn("第 2 页副标题：数字 120 追溯不到证据账", text)
        self.assertIn("讲者备注第 2 页：数字 35 追溯不到证据账", text)

    def test_blocks_claims_that_cannot_be_presented(self):
        slides = copy.deepcopy(self.slides)
        self.led.patch("claims", "cl-0002", {"affects_conclusion": False})
        self.page(slides, 3)["claim_refs"].append("cl-0002")
        self.assertIn("主张 cl-0002（unverified）不能进入报告：未核实且不影响结论", self.problems(slides))
        self.led.patch("claims", "cl-0002", {"verification": "conflicting"})
        self.assertIn("冲突没有写采信理由", self.problems(slides))

    def test_blocks_missing_metric_on_page(self):
        slides = copy.deepcopy(self.slides)
        self.page(slides, 2)["metric_refs"].append("m-0004")
        self.assertIn("metric_refs 里的 m-0004 不在报告的指标里", self.problems(slides))

    def test_blocks_structure_the_engine_checks_late(self):
        slides = copy.deepcopy(self.slides)
        p2 = self.page(slides, 2)
        p2["panels"][1]["slot"] = "side"
        p2["panels"][1]["claim_refs"] = ["cl-0003"]
        p2["panels"][1]["role"] = "primary"
        text = self.problems(slides)
        self.assertIn("panel note 的 slot 须为", text)
        self.assertIn("主张 cl-0003 不在本页 claim_refs 里", text)
        self.assertIn("必须恰好有一个 role=primary 的 panel", text)

    def test_blocks_missing_report_fields(self):
        slides = copy.deepcopy(self.slides)
        del slides["deck"]["brief"]
        del self.page(slides, 2)["adds"]
        text = self.problems(slides)
        self.assertIn("deck.brief 缺失", text)
        self.assertIn("第 2 页（正文）缺少 adds", text)

    def test_reports_a_card_not_on_body_pages(self):
        slides = copy.deepcopy(self.slides)
        self.led.add("cards", {"type": "fact", "content": "核心团队来自头部企业", "meaning": "执行力有保障", "value_tier": "A",
                               "topic": "团队", "claim_id": "cl-0004"})
        self.page(slides, 3)["claim_refs"].remove("cl-0004")
        self.page(slides, 3)["panels"][1]["claim_refs"] = ["cl-0005"]
        self.assertEqual(self.build(slides)["a_cards"]["missing"], ["card-0003（核心团队来自头部企业）"])


if __name__ == "__main__":
    unittest.main()
