import json
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
            "semantic_type": "comparison",
            "visual": "two-column",
            "slot": "main",
            "span": 2,
        },
    }


class A4ComponentTest(unittest.TestCase):
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
                }, set(contract))
                self.assertTrue(contract["allowed_blocks"])
                self.assertTrue(contract["visual_hierarchy"])
                self.assertTrue(contract["allowed_layouts"])
                self.assertGreaterEqual(contract["capacity_dimensions"]["hard"], contract["capacity_dimensions"]["soft"])
                self.assertTrue(contract["split_strategy"])
                self.assertTrue(contract["failure_conditions"])
                permitted_kind = contract["allowed_blocks"][0]
                rendered = run_node(
                    "component.renderComponent(payload.kind, payload.payload, {})",
                    {"kind": kind, "payload": {
                        "id": "page-1", "title": "标题",
                        "layout_id": contract["allowed_layouts"][0],
                        "blocks": [block(permitted_kind)],
                    }}
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
        self.assertEqual("REPORT_COMPONENT_CAPACITY", over_capacity["code"])

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
            "cover": ("<header ", 'aria-labelledby="page-1-title"'),
            "executive-summary": ("<section ", 'aria-labelledby="page-1-title"'),
        }
        for kind, expected in cases.items():
            with self.subTest(kind=kind):
                contract = run_node("component.COMPONENT_CONTRACTS[payload]", kind)["value"]
                permitted_kind = contract["allowed_blocks"][0]
                result = run_node(
                    "component.renderComponent(payload.kind, payload.payload, {})",
                    {"kind": kind, "payload": {"id": "page-1", "title": "标题", "layout_id": contract["allowed_layouts"][0], "blocks": [block(permitted_kind)]}},
                )
                self.assertIn(expected[0], result["value"])
                self.assertIn(expected[1], result["value"])

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
