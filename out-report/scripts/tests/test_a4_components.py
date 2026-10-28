import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COMPONENTS = ROOT / "out-report" / "scripts" / "a4" / "components.cjs"


def run_node(expression, payload=None):
    script = f"""
const component = require({json.dumps(str(COMPONENTS))});
const payload = JSON.parse(process.argv[1]);
Promise.resolve().then(() => {expression}).then(
  value => process.stdout.write(JSON.stringify({{ok: true, value}})),
  error => process.stdout.write(JSON.stringify({{ok: false, code: error.code, message: error.message}}))
);
"""
    result = subprocess.run(
        ["node", "-e", script, json.dumps(payload or {}, ensure_ascii=False)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def block(kind="text"):
    return {
        "id": "b-1",
        "kind": kind,
        "claim_refs": ["cl-1"],
        "metric_refs": ["m-1"],
        "source_ids": ["src-1"],
        "source_bindings": [{"source_id": "src-1", "locators": ["p. 4"]}],
        "panel_refs": ["supply", "demand"],
        "relation_refs": ["compare-sides"],
        "identity": ["fact", "forecast"],
        "content": {
            "title": "需求 <增长>",
            "subtitle": "小型客户 & token 服务商",
            "purpose": "比较两侧\"证据\"",
            "form": {"chart": "svg.custom", "text": "html.text", "metric": "html.kpi", "table": "html.table"}[kind],
            "relationship": "comparison",
            "reason": "支持决策",
            "anchor": True,
            "role": "primary",
            "semantic_type": "point_evidence",
            "visual": "two-column",
            "slot": "main",
            "span": 2,
        },
    }


def component_payload(kind, contract):
    permitted_kind = contract["allowed_blocks"][0]
    payload = {
        "id": "page-1", "title": "标题",
        "layout_id": contract["allowed_layouts"][0],
        "blocks": [block(permitted_kind)],
    }
    required = {
        "cover": {"title_groups": [{"title": "标题"}]},
        "toc": {"entries": [{"title": "第一章", "destination": "section-1"}]},
        "executive-summary": {"answers": ["优先验证"], "summary_items": [{"text": "两项付费试点", "qualification": "目标"}]},
        "section-title": {"chapter_claims": ["需求验证"]},
        "claim-evidence": {"claim": "客户存在等待", "evidence_groups": [{"source_id": "s1", "locators": ["interview 1"]}]},
        "data-chart": {"unit": "percent", "period": "2026", "items": [{"label": "A", "value": 1}]},
        "comparison": {"criteria": ["cost"], "alternatives": [{"id": "a", "values": {"cost": 1}}]},
        "pain-demand": {"pain_groups": [{"pain": "交付等待", "observable_behavior": "主动询价"}]},
        "market-trend": {"unit": "GPU-hours", "period": "2026–2028", "series_or_drivers": [{"name": "需求", "values": [1, 2]}]},
        "risk-boundary": {"risks": [{"name": "回款", "priority": "P1"}]},
        "recommendation-roadmap": {"stages": [{"title": "POC", "gate": "two paid pilots"}]},
        "references-appendix": {"references": [{"id": "s1", "locators": ["p. 4"]}]},
    }
    payload.update(required.get(kind, {}))
    return payload


class A4ComponentTest(unittest.TestCase):
    def test_native_consulting_exhibits_have_distinct_accessible_structures(self):
        fixtures = {
            "executive-summary": {"answer": "先验证付费", "reasons": ["需求未证实", "成本可控"]},
            "answer-and-reasons": {"answer": "进入试点", "reasons": ["客户有触发事件", "替代方案昂贵"]},
            "pain-comparison": {"columns": ["现状", "目标"], "rows": [{"label": "等待", "values": ["3 天", "当天"]}]},
            "competitor-matrix": {"columns": ["成本", "速度"], "rows": [{"label": "方案 A", "values": ["低", "快"]}]},
            "decision-tree": {"nodes": [{"id": "n1", "label": "有付费意愿？"}, {"id": "n2", "label": "进入试点"}], "edges": [{"from": "n1", "to": "n2", "label": "是"}]},
            "mechanism-process": {"steps": [{"label": "采集"}, {"label": "判断"}, {"label": "行动"}]},
            "paired-scenarios": {"scenarios": [{"label": "上行情景", "outcome": "扩张"}, {"label": "下行情景", "outcome": "停止"}]},
            "30-60-90-roadmap": {"stages": [{"label": "30 天", "output": "访谈"}, {"label": "60 天", "output": "试点"}, {"label": "90 天", "output": "决策"}]},
            "methods-limitations": {"methods": ["访谈"], "limitations": ["样本较小"]},
        }
        seen = set()
        families = {"executive-summary": "point_evidence", "answer-and-reasons": "point_evidence", "pain-comparison": "matrix", "competitor-matrix": "matrix", "decision-tree": "decision-tree", "mechanism-process": "process", "paired-scenarios": "scenario", "30-60-90-roadmap": "timeline", "methods-limitations": "point_evidence"}
        forms = {kind: ("svg.custom" if kind in {"decision-tree", "mechanism-process"} else "html.table" if kind in {"pain-comparison", "competitor-matrix", "paired-scenarios", "30-60-90-roadmap"} else "html.text") for kind in fixtures}
        for kind, exhibit in fixtures.items():
            with self.subTest(kind=kind):
                item = block({"svg.custom": "chart", "html.table": "table", "html.text": "text"}[forms[kind]])
                item["content"]["semantic_type"] = kind
                item["content"]["exhibit"] = {"kind": kind, "family": families[kind], "form": forms[kind], **exhibit}
                result = run_node("component.renderBlock(payload.block, {})", {"block": item})
                self.assertTrue(result["ok"], result)
                html = result["value"]
                self.assertIn(f'data-exhibit-kind="{kind}"', html)
                self.assertIn('id="b-1-exhibit"', html)
                self.assertRegex(html, r'aria-(?:label|labelledby)=')
                self.assertNotIn("block-purpose", html)
                seen.add(html.split('data-exhibit-kind="', 1)[1].split('>', 1)[0])
        self.assertEqual(len(fixtures), len(seen))

    def test_generic_fallback_is_only_allowed_for_point_evidence(self):
        item = block("text")
        item["content"]["semantic_type"] = "decision-tree"
        missing = run_node("component.renderBlock(payload.block, {})", {"block": item})
        self.assertFalse(missing["ok"])
        self.assertEqual("REPORT_EXHIBIT_MISSING", missing["code"])
        item["content"]["semantic_type"] = "point_evidence"
        fallback = run_node("component.renderBlock(payload.block, {})", {"block": item})
        self.assertTrue(fallback["ok"], fallback)

        for semantic in (None, "unknown-kind", "pain-demand", "competition"):
            item = block("text")
            if semantic is not None:
                item["content"]["semantic_type"] = semantic
            else:
                item["content"].pop("semantic_type", None)
            result = run_node("component.renderBlock(payload.block, {})", {"block": item})
            self.assertFalse(result["ok"], semantic)
            self.assertEqual("REPORT_EXHIBIT_MISSING", result["code"])

    def test_svg_exhibits_draw_resolved_connectors_and_structures_are_distinct(self):
        tree = block("chart")
        tree["content"].update(semantic_type="decision-tree", exhibit={
            "kind": "decision-tree", "family": "decision-tree", "form": "svg.custom",
            "nodes": [{"id": "start", "label": "开始"}, {"id": "go", "label": "继续"}],
            "edges": [{"from": "start", "to": "go", "label": "是"}],
        })
        rendered = run_node("component.renderBlock(payload.block, {})", {"block": tree})
        self.assertTrue(rendered["ok"], rendered)
        self.assertIn('<line id="b-1-edge-1"', rendered["value"])
        self.assertIn('data-from="b-1-node-start"', rendered["value"])
        self.assertIn('data-to="b-1-node-go"', rendered["value"])

        tree["content"]["exhibit"]["nodes"].append({"id": "stop", "label": "停止"})
        tree["content"]["exhibit"]["edges"].append({"from": "start", "to": "stop", "label": "否"})
        rendered = run_node("component.renderBlock(payload.block, {})", {"block": tree})
        self.assertTrue(rendered["ok"], rendered)
        self.assertRegex(rendered["value"], r'id="b-1-edge-1"[^>]*x1="98"[^>]*x2="113"')
        self.assertRegex(rendered["value"], r'id="b-1-edge-2"[^>]*x1="98"[^>]*x2="218"')

        broken = json.loads(json.dumps(tree))
        broken["content"]["exhibit"]["edges"][0]["to"] = "missing"
        result = run_node("component.renderBlock(payload.block, {})", {"block": broken})
        self.assertFalse(result["ok"])
        self.assertEqual("REPORT_EXHIBIT_MISMATCH", result["code"])

        process = block("chart")
        process["content"].update(semantic_type="mechanism-process", exhibit={
            "kind": "mechanism-process", "family": "process", "form": "svg.custom",
            "steps": [{"label": "采集"}, {"label": "判断"}],
        })
        rendered = run_node("component.renderBlock(payload.block, {})", {"block": process})
        self.assertTrue(rendered["ok"], rendered)
        self.assertIn('class="process-connector"', rendered["value"])

    def test_similar_exhibits_use_different_native_structures(self):
        cases = {
            "executive-summary": {"answer": "答", "reasons": ["因"]},
            "answer-and-reasons": {"answer": "答", "reasons": ["因"]},
            "pain-comparison": {"columns": ["前", "后"], "rows": [{"label": "痛", "values": ["A", "B"]}]},
            "competitor-matrix": {"columns": ["价", "速"], "rows": [{"label": "甲", "values": ["低", "快"]}]},
        }
        structures = {}
        families = {"executive-summary": "point_evidence", "answer-and-reasons": "point_evidence", "pain-comparison": "matrix", "competitor-matrix": "matrix"}
        for kind, exhibit in cases.items():
            form = "html.table" if kind in {"pain-comparison", "competitor-matrix"} else "html.text"
            item = block("table" if form == "html.table" else "text")
            item["content"].update(semantic_type=kind, exhibit={"kind": kind, "family": families[kind], "form": form, **exhibit})
            html = run_node("component.renderBlock(payload.block, {})", {"block": item})["value"]
            structures[kind] = re.search(r'data-exhibit-kind="[^"]+"[^>]*data-structure="([^"]+)"', html).group(1)
        self.assertEqual(4, len(set(structures.values())))

    def test_red_components_module_exists(self):
        result = run_node("Object.keys(component).sort()")
        self.assertTrue(result["ok"])

    def test_four_schema_block_kinds_render_with_bound_references(self):
        approved = run_node("component.APPROVED_BLOCK_KINDS")
        self.assertEqual(["chart", "text", "metric", "table"], approved["value"])
        for kind in ("chart", "text", "metric", "table"):
            with self.subTest(kind=kind):
                result = run_node("component.renderBlock(payload.block, payload.context)", {"block": block(kind), "context": {}})
                self.assertTrue(result["ok"], result)
                html = result["value"]
                self.assertIn(f'data-block-kind="{kind}"', html)
                self.assertIn('data-panel-id="supply"', html)
                self.assertIn('data-panel-id="demand"', html)
                self.assertIn('data-relation-id="compare-sides"', html)
                self.assertIn('data-claim-id="cl-1"', html)
                self.assertIn('data-metric-id="m-1"', html)
                self.assertIn('data-source-id="src-1"', html)
                self.assertIn('data-source-locator="p. 4"', html)

    def test_executive_summary_renders_answer_and_qualified_claims(self):
        payload = {
            "id": "summary", "title": "执行摘要", "layout_id": "overview-detail", "blocks": [],
            "answers": ["只批准低成本验证"],
            "summary_items": [{
                "text": "目标客户付费意愿仍未证实", "identity": "judgment", "confidence": "low",
                "qualification": "尚无访谈、订单或愿付价格",
            }],
        }
        rendered = run_node("component.renderComponent('executive-summary', payload, {})", payload)
        self.assertTrue(rendered["ok"], rendered)
        self.assertIn("只批准低成本验证", rendered["value"])
        self.assertIn("目标客户付费意愿仍未证实", rendered["value"])
        self.assertIn("judgment · low", rendered["value"])
        self.assertIn("尚无访谈、订单或愿付价格", rendered["value"])

    def test_semantic_blocks_render_real_claim_pain_and_competition_content(self):
        claim_block = block("text")
        claim_block["content"]["claims"] = [{
            "id": "cl-1", "statement": "目标客户需求频率仍未证实", "identity": "judgment",
            "confidence": "low", "scope": "东南亚滩头市场", "limitation": "没有采购样本",
            "support": [
                {"excerpt": "存在短时容量压力", "source_id": "src-1", "locator": "p1"},
                {"excerpt": "第二条支持", "source_id": "src-2", "locator": "p2"},
                {"excerpt": "第三条支持不应铺满正文", "source_id": "src-3", "locator": "p3"},
            ],
            "counter": [{"excerpt": "按需 API 已可替代", "source_id": "src-2"}],
        }]
        rendered = run_node("component.renderBlock(payload.block, {})", {"block": claim_block})
        self.assertTrue(rendered["ok"], rendered)
        self.assertIn("目标客户需求频率仍未证实", rendered["value"])
        self.assertIn("存在短时容量压力", rendered["value"])
        self.assertIn("按需 API 已可替代", rendered["value"])
        self.assertIn("没有采购样本", rendered["value"])
        self.assertIn("另 2 条见来源附录", rendered["value"])
        self.assertNotIn("第二条支持", rendered["value"])
        self.assertNotIn("第三条支持不应铺满正文", rendered["value"])
        self.assertNotIn('class="block-purpose"', rendered["value"])

        pain_block = block("table")
        pain_block["content"]["semantic_type"] = "pain-demand"
        pain_block["content"]["pain_groups"] = [{
            "segment": "AI 应用创业公司", "trigger": "流量突增", "workaround": "排队或包卡",
            "consequence": "闲置或延期", "purchase_signal": "带价格试点", "evidence_strength": "medium",
            "counter": "成熟 API 可能已足够", "validation_gap": "没有采购样本",
        }]
        pain_block["content"]["exhibit"] = {"kind": "pain-comparison", "family": "matrix", "form": "html.table", "columns": ["当前替代", "后果", "购买信号"], "rows": [{"label": "AI 应用创业公司", "values": ["排队或包卡", "闲置或延期", "带价格试点"]}]}
        rendered = run_node("component.renderBlock(payload.block, {})", {"block": pain_block})
        self.assertTrue(rendered["ok"], rendered)
        for text in ("AI 应用创业公司", "排队或包卡", "闲置或延期", "带价格试点"):
            self.assertIn(text, rendered["value"])
        self.assertNotIn("Relationship", rendered["value"])

        comparison_block = block("table")
        comparison_block["content"]["semantic_type"] = "competition"
        comparison_block["content"]["comparison"] = {
            "criteria": ["总拥有成本", "可靠性"],
            "alternatives": [{"name": "专业 GPU 云", "layer": "direct", "values": {"总拥有成本": "公开价可比", "可靠性": "待同口径核实"}}],
        }
        comparison_block["content"]["exhibit"] = {"kind": "competitor-matrix", "family": "matrix", "form": "html.table", "columns": ["总拥有成本", "可靠性"], "rows": [{"label": "专业 GPU 云", "values": ["公开价可比", "待同口径核实"]}]}
        rendered = run_node("component.renderBlock(payload.block, {})", {"block": comparison_block})
        self.assertTrue(rendered["ok"], rendered)
        for text in ("专业 GPU 云", "总拥有成本", "公开价可比", "可靠性", "待同口径核实"):
            self.assertIn(text, rendered["value"])
        self.assertNotIn("Relationship", rendered["value"])

    def test_body_sources_render_compact_linked_markers_without_reference_strip(self):
        item = block("text")
        item["source_ids"] = ["M002", "M010", "M002"]
        item["source_bindings"] = [
            {"source_id": "M002", "locators": ["p. 4"]},
            {"source_id": "M010", "locators": ["§2"]},
        ]
        context = {"citationRegistry": [
            {"source_id": "M002", "number": 1, "appendix_anchor": "source-M002"},
            {"source_id": "M010", "number": 2, "appendix_anchor": "source-M010"},
        ]}
        result = run_node("component.renderBlock(payload.block, payload.context)", {"block": item, "context": context})
        self.assertTrue(result["ok"], result)
        html = result["value"]
        self.assertIn('<sup class="citation-markers" aria-label="Sources">', html)
        self.assertIn('class="citation-marker" href="#source-M002">[1]</a>', html)
        self.assertIn('class="citation-marker" href="#source-M010">[2]</a>', html)
        self.assertEqual(1, html.count('class="citation-marker" href="#source-M002"'))
        self.assertNotIn("https://", html)
        self.assertNotIn("source-strip", html)

    def test_twelve_semantic_components_are_frozen_and_render(self):
        result = run_node("component.APPROVED_COMPONENT_KINDS")
        self.assertTrue(result["ok"])
        kinds = result["value"]
        self.assertEqual([
            "cover", "toc", "executive-summary", "section-title",
            "claim-evidence", "data-chart", "comparison", "pain-demand",
            "market-trend", "risk-boundary", "recommendation-roadmap",
            "references-appendix",
        ], kinds)
        for kind in kinds:
            with self.subTest(kind=kind):
                contract = run_node("component.COMPONENT_CONTRACTS[payload.kind]", {"kind": kind})["value"]
                self.assertEqual({
                    "allowed_blocks", "visual_hierarchy", "allowed_layouts",
                    "capacity_dimensions", "split_strategy", "failure_conditions",
                    "required_fields", "predicates",
                }, set(contract))
                self.assertTrue(contract["allowed_blocks"])
                self.assertTrue(contract["visual_hierarchy"])
                self.assertTrue(contract["allowed_layouts"])
                self.assertGreaterEqual(contract["capacity_dimensions"]["hard"], contract["capacity_dimensions"]["soft"])
                self.assertTrue(contract["split_strategy"])
                self.assertTrue(contract["failure_conditions"])
                self.assertTrue(contract["required_fields"])
                self.assertTrue(contract["predicates"])
                rendered = run_node(
                    "component.renderComponent(payload.kind, payload.payload, {})",
                    {"kind": kind, "payload": component_payload(kind, contract)}
                )
                self.assertTrue(rendered["ok"], rendered)
                self.assertIn(f'data-component-kind="{kind}"', rendered["value"])
                self.assertIn('aria-labelledby="page-1-title"', rendered["value"])
                self.assertIn(f'data-layout-id="{contract["allowed_layouts"][0]}"', rendered["value"])
                self.assertIn(f'data-capacity-unit="{contract["capacity_dimensions"]["unit"]}"', rendered["value"])
                self.assertIn('data-split-strategy=', rendered["value"])

    def test_component_contract_rejects_invalid_layout_block_and_capacity(self):
        contract = run_node("component.COMPONENT_CONTRACTS['cover']")["value"]
        bad_layout = run_node(
            "component.renderComponent('cover', payload, {})",
            {"id": "c", "title": "C", "layout_id": "decision-matrix", "blocks": [block("text")]},
        )
        self.assertFalse(bad_layout["ok"])
        self.assertEqual("REPORT_COMPONENT_CONTRACT", bad_layout["code"])
        bad_block = run_node(
            "component.renderComponent('cover', payload, {})",
            {"id": "c", "title": "C", "layout_id": contract["allowed_layouts"][0], "blocks": [block("chart")]},
        )
        self.assertFalse(bad_block["ok"])
        self.assertEqual("REPORT_COMPONENT_CONTRACT", bad_block["code"])
        over_capacity = run_node(
            "component.renderComponent('cover', payload, {})",
            {"id": "c", "title": "C", "layout_id": contract["allowed_layouts"][0], "capacity_count": contract["capacity_dimensions"]["hard"] + 1, "blocks": [block("text")]},
        )
        self.assertFalse(over_capacity["ok"])
        self.assertEqual("REPORT_COMPONENT_CONTRACT", over_capacity["code"])

    def test_capacity_is_derived_and_cannot_be_underreported(self):
        contract = run_node("component.COMPONENT_CONTRACTS['comparison']")["value"]
        payload = component_payload("comparison", contract)
        payload["alternatives"] = [{"id": str(index), "values": {"cost": index}} for index in range(5)]
        payload["capacity_count"] = 1
        mismatch = run_node("component.renderComponent('comparison', payload, {})", payload)
        self.assertFalse(mismatch["ok"])
        self.assertEqual("REPORT_COMPONENT_CONTRACT", mismatch["code"])
        del payload["capacity_count"]
        overflow = run_node("component.renderComponent('comparison', payload, {})", payload)
        self.assertFalse(overflow["ok"])
        self.assertEqual("REPORT_COMPONENT_CAPACITY", overflow["code"])

    def test_critical_component_predicates_reject_invalid_content(self):
        cases = {
            "toc": {"entries": [{"title": "No link", "destination": ""}]},
            "data-chart": {"unit": "", "period": "", "items": [{"label": "A", "value": 1}]},
            "comparison": {"criteria": [], "alternatives": [{"id": "a", "values": {}}]},
            "recommendation-roadmap": {"stages": [{"title": "POC", "gate": ""}]},
            "references-appendix": {"references": [{"id": "s1", "locators": []}]},
        }
        for kind, mutation in cases.items():
            with self.subTest(kind=kind):
                contract = run_node("component.COMPONENT_CONTRACTS[payload]", kind)["value"]
                payload = component_payload(kind, contract)
                payload.update(mutation)
                result = run_node("component.renderComponent(payload.kind, payload.payload, {})", {"kind": kind, "payload": payload})
                self.assertFalse(result["ok"])
                self.assertEqual("REPORT_COMPONENT_CONTRACT", result["code"])

    def test_every_remaining_component_enforces_a_failure_condition(self):
        cases = {
            "cover": {"title": "", "title_groups": []},
            "executive-summary": {"answers": [], "summary_items": []},
            "section-title": {"title": "", "chapter_claims": []},
            "claim-evidence": {"claim": "", "evidence_groups": [{"source_id": "s1", "locators": []}]},
            "pain-demand": {"pain_groups": [{"pain": "等待", "observable_behavior": ""}]},
            "market-trend": {"unit": "", "period": "", "series_or_drivers": []},
            "risk-boundary": {"risks": [{"name": "回款", "priority": ""}]},
        }
        for kind, mutation in cases.items():
            with self.subTest(kind=kind):
                contract = run_node("component.COMPONENT_CONTRACTS[payload]", kind)["value"]
                payload = component_payload(kind, contract)
                payload.update(mutation)
                result = run_node("component.renderComponent(payload.kind, payload.payload, {})", {"kind": kind, "payload": payload})
                self.assertFalse(result["ok"])
                self.assertEqual("REPORT_COMPONENT_CONTRACT", result["code"])

    def test_every_component_capacity_uses_its_structured_dimension(self):
        contracts = run_node("component.COMPONENT_CONTRACTS")["value"]
        for kind, contract in contracts.items():
            with self.subTest(kind=kind):
                self.assertNotEqual("blocks", contract["capacity_dimensions"]["field"])
                payload = component_payload(kind, contract)
                result = run_node("component.renderComponent(payload.kind, payload.payload, {})", {"kind": kind, "payload": payload})
                self.assertTrue(result["ok"], result)
                expected = len(payload[contract["capacity_dimensions"]["field"]])
                self.assertIn(f'data-capacity-count="{expected}"', result["value"])

    def test_component_contracts_only_reference_frozen_layouts_and_schema_blocks(self):
        layouts = json.loads((ROOT / "out-report" / "assets" / "layout-atlas" / "catalog.json").read_text())["layouts"]
        schema = json.loads((ROOT / "tools" / "lib" / "schema" / "report.schema.json").read_text())
        layout_ids = {item["id"] for item in layouts}
        block_kinds = set(schema["enums"]["block_kind"]["values"])
        contracts = run_node("component.COMPONENT_CONTRACTS")["value"]
        for kind, contract in contracts.items():
            with self.subTest(kind=kind):
                self.assertLessEqual(set(contract["allowed_layouts"]), layout_ids)
                self.assertLessEqual(set(contract["allowed_blocks"]), block_kinds)

    def test_component_landmarks_are_native_and_heading_is_bound(self):
        cases = {
            "toc": ("<nav ", 'aria-label="Table of contents"'),
            "references-appendix": ("<aside ", 'aria-label="References and appendix"'),
            "cover": ("<section ", 'aria-labelledby="page-1-title"'),
            "executive-summary": ("<section ", 'aria-labelledby="page-1-title"'),
        }
        for kind, expected in cases.items():
            with self.subTest(kind=kind):
                contract = run_node("component.COMPONENT_CONTRACTS[payload]", kind)["value"]
                result = run_node(
                    "component.renderComponent(payload.kind, payload.payload, {})",
                    {"kind": kind, "payload": component_payload(kind, contract)},
                )
                self.assertIn(expected[0], result["value"])
                self.assertIn(expected[1], result["value"])

    def test_component_does_not_nest_header_landmarks(self):
        for kind in ("cover", "section-title"):
            contract = run_node("component.COMPONENT_CONTRACTS[payload]", kind)["value"]
            result = run_node(
                "component.renderComponent(payload.kind, payload.payload, {})",
                {"kind": kind, "payload": component_payload(kind, contract)},
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result["value"].startswith("<section "))
            self.assertEqual(1, result["value"].count("<header>"))

    def test_unknown_kinds_have_stable_error(self):
        result = run_node("component.renderBlock(payload, {})", {"id": "x", "kind": "video"})
        self.assertFalse(result["ok"])
        self.assertEqual("REPORT_UNSUPPORTED_BLOCK", result["code"])
        result = run_node("component.renderComponent('poster', {}, {})")
        self.assertFalse(result["ok"])
        self.assertEqual("REPORT_UNSUPPORTED_COMPONENT", result["code"])

    def test_untrusted_text_and_attributes_are_escaped(self):
        hostile = block()
        hostile["id"] = 'x" onmouseover="alert(1)'
        hostile["content"]["title"] = '<script>alert("x")</script>'
        hostile["source_bindings"][0]["locators"] = ['"><img src=x onerror=alert(1)>']
        result = run_node("component.renderBlock(payload, {})", hostile)
        self.assertTrue(result["ok"])
        html = result["value"]
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertNotIn('" onmouseover=', html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&quot;&gt;&lt;img", html)

    def test_output_is_deterministic_and_input_is_not_mutated(self):
        result = run_node("(() => { const before = JSON.stringify(payload); const a = component.renderBlock(payload, {}); const b = component.renderBlock(payload, {}); return {same: a === b, unchanged: before === JSON.stringify(payload)}; })()", block("chart"))
        self.assertEqual({"same": True, "unchanged": True}, result["value"])

    def test_identity_visual_encoding_is_consumed_with_text_redundancy(self):
        context = {
            "identityEncodings": {
                "fact": {"line": "solid", "fill": "solid", "marker": "circle", "text": "Actual"},
                "forecast": {"line": "dotted", "fill": "hatch", "marker": "diamond", "text": "Forecast"},
            }
        }
        result = run_node("component.renderBlock(payload.block, payload.context)", {"block": block("chart"), "context": context})
        self.assertTrue(result["ok"])
        html = result["value"]
        self.assertIn('data-line="solid"', html)
        self.assertIn('data-fill="hatch"', html)
        self.assertIn('data-marker="diamond"', html)
        self.assertIn(">Forecast<", html)

    def test_renderer_owned_svg_only_for_chart(self):
        result = run_node("component.renderBlock(payload, {})", block("chart"))
        self.assertIn('<svg aria-hidden="true"', result["value"])
        for kind in ("text", "metric", "table"):
            result = run_node("component.renderBlock(payload, {})", block(kind))
            self.assertNotIn("<svg", result["value"])


if __name__ == "__main__":
    unittest.main()
