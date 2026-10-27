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
        body = [
            ("p02", "trend-bars", "trend", "L01"),
            ("p03", "comparison-matrix", "comparison", "L02"),
            ("p04", "roadmap", "sequence", "L03"),
            ("p05", "evidence-quote", "evidence", "L04"),
        ]
        extras = {
            "chart-plan": {"chartDecisions": [{"pageId": pid, "form": form, "relationship": relationship,
                                                   "reason": "关系与图形匹配"} for pid, form, relationship, _ in body]},
            "layout-plan": {"layoutDecisions": [{"pageId": pid, "layout": layout,
                                                     "readingPath": "标题 → 主证据 → 来源", "regions": ["main"],
                                                     "reason": "版式匹配证据形状"} for pid, _, _, layout in body]},
            "module-fill-plan": {"modulePlans": [{"pageId": pid, "regions": [{"id": "main", "content": "主证据完整呈现",
                                                                                     "layout": layout, "whitespace": "保留来源安全区"}]}
                                                        for pid, _, _, layout in body]},
        }
        for name in ("chart-plan", "layout-plan", "module-fill-plan"):
            (obs / f"{name}.json").write_text(json.dumps({
                "kind": "planning", "reviewer": "测试规划接收人", "basis": "逐页核对蓝图与规划决定",
                "requirementRefs": [name],
                "files": [{"record": "../deck-blueprint.json", "sha256": sha(self.bp)}],
                **extras[name],
            }), encoding="utf-8")
        self._refresh_plan_refs()

    def _refresh_plan_refs(self):
        obs = self.d / "obs"
        (self.d / "execution-plan.json").write_text(json.dumps({"items": [
            {"id": name, "state": "done", "acceptance": {"reviewer": "测试接收人", "basis": "核对当前蓝图和逐页决定"},
             "evidenceRefs": [{"record": f"obs/{name}.json", "sha256": sha(obs / f"{name}.json")}]}
            for name in ("chart-plan", "layout-plan", "module-fill-plan")
        ]}), encoding="utf-8")

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
        self.assertEqual(first["coverage"]["claimRefs"], ["c1", "c2", "c3", "c4"])
        self.assertEqual(first["coverage"]["metricRefs"], ["m1", "m2"])
        self.assertEqual(first["coverage"]["sourceIds"], ["S1", "S2"])

    def test_plan_changes_drive_output_and_incomplete_decisions_fail(self):
        before = allen_compose.compose(self.d)
        plan = self.d / "obs" / "layout-plan.json"
        payload = json.loads(plan.read_text())
        payload["layoutDecisions"][0]["layout"] = "L05"
        payload["layoutDecisions"][0]["readingPath"] = "标题 → 总览 → 细节 → 来源"
        plan.write_text(json.dumps(payload), encoding="utf-8")
        self._refresh_plan_refs()
        after = allen_compose.compose(self.d)
        self.assertNotEqual(before, after)
        self.assertEqual(after["pages"][1]["layout"], "L05")
        self.assertIn("标题 → 总览", (self.d / "pages.html").read_text())
        payload["layoutDecisions"].pop()
        plan.write_text(json.dumps(payload), encoding="utf-8")
        self._refresh_plan_refs()
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_INCOMPLETE"):
            allen_compose.compose(self.d)

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
        self._refresh_plan_refs()
        manifest = allen_compose.compose(self.d)
        self.assertTrue(manifest["referencesPage"])
        self.assertFalse(manifest["sparseReferences"])
        text = (self.d / "pages.html").read_text()
        self.assertIn('data-page-role="references"', text)
        self.assertIn("访谈纪要:L10-L20", text)
        self.assertIn("绑定来源的主张", text)

    def test_missing_or_stale_plan_fails_before_writing(self):
        (self.d / "obs" / "layout-plan.json").unlink()
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_MISSING"):
            allen_compose.compose(self.d)
        self.assertFalse((self.d / "pages.html").exists())
        (self.d / "obs" / "layout-plan.json").write_text(json.dumps({"files": [{"record": "../deck-blueprint.json", "sha256": "0" * 64}]}))
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_STALE"):
            allen_compose.compose(self.d)

    def test_missing_execution_plan_fake_done_wrong_ref_and_layout_injection_fail(self):
        execution = self.d / "execution-plan.json"
        execution.unlink()
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_MISSING"):
            allen_compose.compose(self.d)
        self._refresh_plan_refs()
        plan = json.loads(execution.read_text())
        del plan["items"][1]["acceptance"]
        execution.write_text(json.dumps(plan))
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_NOT_ACCEPTED"):
            allen_compose.compose(self.d)
        self._refresh_plan_refs()
        plan = json.loads(execution.read_text())
        plan["items"][1]["evidenceRefs"][0] = dict(plan["items"][0]["evidenceRefs"][0])
        execution.write_text(json.dumps(plan))
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_WRONG_EVIDENCE"):
            allen_compose.compose(self.d)
        self._refresh_plan_refs()
        layout = self.d / "obs/layout-plan.json"
        payload = json.loads(layout.read_text())
        payload["layoutDecisions"][0]["layout"] = 'L01" onmouseover="alert(1)'
        layout.write_text(json.dumps(payload))
        self._refresh_plan_refs()
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_PLAN_INVALID"):
            allen_compose.compose(self.d)

    def test_capacity_overflow_fails_instead_of_shrinking(self):
        doc = json.loads(self.bp.read_text())
        claim_template = doc["claims"][0]
        for index in range(2, 9):
            clone = dict(claim_template, id=f"c1-{index}", statement=f"补充趋势主张 {index}", metrics=[])
            doc["claims"].append(clone)
            doc["slides"][1]["claimRefs"].append(clone["id"])
            doc["slides"][1]["exhibit"]["semantics"]["composition"]["panels"]["p02-main"]["claimRefs"].append(clone["id"])
        doc["slides"][1]["exhibit"]["semantics"]["composition"]["panels"]["p02-main"]["capacity"]["items"] = 1
        self.bp.write_text(json.dumps(doc), encoding="utf-8")
        digest = sha(self.bp)
        for plan in (self.d / "obs").glob("*.json"):
            payload = json.loads(plan.read_text())
            payload["files"][0]["sha256"] = digest
            plan.write_text(json.dumps(payload), encoding="utf-8")
        self._refresh_plan_refs()
        with self.assertRaisesRegex(allen_compose.ComposeError, "REPORT_DECK_CAPACITY"):
            allen_compose.compose(self.d)


if __name__ == "__main__":
    unittest.main()
