import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import allen_compose  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page(pid, relationship, form, claims, metric_refs=None):
    return {
        "id": pid, "sequence": int(pid[1:]), "pageRole": "analysis", "storyBeat": "insight",
        "title": f"{pid} <script>alert(1)</script> 的结论", "subtitle": "同口径验证", "cornerLabel": "01",
        "proves": "证据支持结论", "adds": "读者知道下一步", "claimRefs": claims,
        "metricRefs": metric_refs or [],
        "visual": {"layout": "custom", "readingPath": "标题 → 证据 → 含义", "layoutReason": "证据优先",
                   "regions": [{"slot": "main", "role": "primary", "span": 2, "panelRef": f"{pid}-main"}]},
        "density": {"profile": "balanced", "evidenceUnits": [{"role": "primary", "purpose": "证明结论"}],
                    "spaceIntent": "主证据展开"},
        "exhibit": {"contract": "semantic-exhibit-v1", "semantics": {"composition": {
            "version": 1, "anchorPanel": f"{pid}-main", "readingOrder": [f"{pid}-main"],
            "panels": {f"{pid}-main": {"purpose": "证明结论", "claimRefs": claims, "form": form,
                "selection": {"relationship": relationship, "reason": "匹配证据关系"}, "capacity": {"items": 4}}},
            "relations": []}}},
    }


class AllenComposeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)
        self.bp = self.d / "deck-blueprint.json"
        doc = {
            "schemaVersion": 3,
            "deck": {"title": "证据驱动演示稿", "ratio": "16x9", "audience": "决策者", "decision": "是否推进"},
            "sources": {
                "S1": {"label": "一手访谈", "locator": "访谈纪要:L10-L20"},
                "S2": {"label": "经营数据", "locator": "data.csv:L2-L8"},
            },
            "claims": [
                {"id": "c1", "kind": "data", "statement": "需求强度从 {{metric:m1}} 增至 {{metric:m2}}", "sourceKeys": ["S2"],
                 "period": "2025–2026", "limitation": "样本有限", "metrics": [{"id": "m1", "value": 30, "unit": "%"}, {"id": "m2", "value": 68, "unit": "%"}]},
                {"id": "c2", "kind": "judgment", "statement": "方案 A 在成本与速度上更优", "sourceKeys": ["S1"], "limitation": "需试点"},
                {"id": "c3", "kind": "recommendation", "statement": "先试点，再按门槛扩张", "sourceKeys": ["S1"], "limitation": "停止条件必须执行"},
                {"id": "c4", "kind": "third_party_view", "statement": "客户明确要求两周内上线", "sourceKeys": ["S1"], "limitation": "单一访谈"},
            ],
            "slides": [
                {"id": "p01", "sequence": 1, "pageRole": "cover", "storyBeat": "context", "title": "证据驱动演示稿", "subtitle": "同源 A/B"},
                page("p02", "trend", "svg.custom", ["c1"], ["m1", "m2"]),
                page("p03", "comparison", "html.table", ["c2"]),
                page("p04", "sequence", "html.table", ["c3"]),
                page("p05", "evidence", "html.text", ["c4"]),
                {"id": "p06", "sequence": 6, "pageRole": "close", "storyBeat": "close", "title": "下一步：启动两周试点", "subtitle": "谢谢"},
            ],
        }
        self.bp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        obs = self.d / "obs"
        obs.mkdir()
        for name in ("chart-plan", "layout-plan", "module-fill-plan"):
            (obs / f"{name}.json").write_text(json.dumps({
                "kind": "planning", "requirementRefs": [name],
                "files": [{"record": "../deck-blueprint.json", "sha256": sha(self.bp)}],
            }), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_composes_four_distinct_forms_and_layouts_deterministically(self):
        first = allen_compose.compose(self.d)
        html1 = (self.d / "pages.html").read_bytes()
        second = allen_compose.compose(self.d)
        self.assertEqual(html1, (self.d / "pages.html").read_bytes())
        self.assertEqual(first, second)
        body = [p for p in first["pages"] if p["role"] == "body"]
        self.assertEqual({p["form"] for p in body}, {"trend-bars", "comparison-matrix", "roadmap", "evidence-quote"})
        self.assertEqual(len({p["layout"] for p in body}), 4)
        self.assertNotIn("<script>alert(1)</script>", html1.decode())
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html1.decode())
        self.assertNotIn("deck-analysis-status=preview", html1.decode())

    def test_sources_are_near_evidence_and_multiple_sources_get_references(self):
        manifest = allen_compose.compose(self.d)
        text = (self.d / "pages.html").read_text(encoding="utf-8")
        self.assertIn("访谈纪要:L10-L20", text)
        self.assertIn("data.csv:L2-L8", text)
        self.assertTrue(manifest["referencesPage"])
        self.assertIn('data-page-role="references"', text)

    def test_single_source_references_page_is_a_provenance_audit_not_sparse(self):
        doc = json.loads(self.bp.read_text())
        doc["sources"] = {"S1": doc["sources"]["S1"]}
        for claim in doc["claims"]:
            claim["sourceKeys"] = ["S1"]
        self.bp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        digest = sha(self.bp)
        for plan in (self.d / "obs").glob("*.json"):
            payload = json.loads(plan.read_text())
            payload["files"][0]["sha256"] = digest
            plan.write_text(json.dumps(payload), encoding="utf-8")
        manifest = allen_compose.compose(self.d)
        self.assertTrue(manifest["referencesPage"])
        self.assertFalse(manifest["sparseReferences"])
        text = (self.d / "pages.html").read_text()
        self.assertIn('data-page-role="references"', text)
        self.assertIn("绑定来源的主张", text)

    def test_missing_or_stale_plan_fails_before_writing(self):
        (self.d / "obs" / "layout-plan.json").unlink()
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_MISSING"):
            allen_compose.compose(self.d)
        self.assertFalse((self.d / "pages.html").exists())
        (self.d / "obs" / "layout-plan.json").write_text(json.dumps({"files": [{"record": "../deck-blueprint.json", "sha256": "0" * 64}]}))
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_STALE"):
            allen_compose.compose(self.d)

    def test_capacity_overflow_fails_instead_of_shrinking(self):
        doc = json.loads(self.bp.read_text())
        doc["slides"][1]["exhibit"]["semantics"]["composition"]["panels"]["p02-main"]["capacity"]["items"] = 13
        self.bp.write_text(json.dumps(doc), encoding="utf-8")
        digest = sha(self.bp)
        for plan in (self.d / "obs").glob("*.json"):
            payload = json.loads(plan.read_text())
            payload["files"][0]["sha256"] = digest
            plan.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_CAPACITY"):
            allen_compose.compose(self.d)


if __name__ == "__main__":
    unittest.main()
