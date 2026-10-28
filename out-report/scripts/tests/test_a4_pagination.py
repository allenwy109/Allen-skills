import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.lib import runtime as runtime_lib


ROOT = Path(__file__).resolve().parents[3]
RENDER = ROOT / "out-report" / "scripts" / "a4" / "render.cjs"


def browser_requirements(env=None):
    env = os.environ if env is None else env
    missing = []
    if not shutil.which("node"):
        missing.append("node")
    try:
        root = runtime_lib.runtime_root(skill_dir=ROOT / "out-report", env=env)
    except runtime_lib.RuntimeNotFound as error:
        return None, [str(error)]
    playwright = root / "vendor/report-forge/node_modules/playwright"
    required = [
        playwright,
        root / "vendor/report-forge/assets/fonts/noto-sans-sc-400.woff2",
        root / "vendor/report-forge/assets/fonts/noto-sans-sc-600.woff2",
        root / "vendor/report-forge/assets/fonts/noto-serif-sc-600.woff2",
    ]
    missing.extend(str(item) for item in required if not item.exists())
    if not missing:
        probe = subprocess.run(
            ["node", "-e", "process.stdout.write(require(process.argv[1]).chromium.executablePath())", str(playwright)],
            capture_output=True, text=True,
        )
        executable = Path(probe.stdout.strip()) if probe.returncode == 0 else None
        if not executable or not executable.is_file():
            missing.append("Playwright Chromium executable")
    return root, missing


def require_browser(test_case, env=None):
    env = os.environ if env is None else env
    root, missing = browser_requirements(env)
    if missing:
        message = "missing A4 browser runtime: " + ", ".join(missing)
        if env.get("ALLEN_REQUIRE_TOOLS") == "1":
            test_case.fail(message)
        test_case.skipTest(message)
    return root


def block(block_id="b-1", kind="text", anchor=True):
    return {
        "id": block_id,
        "kind": kind,
        "claim_refs": [f"cl-{block_id}"],
        "metric_refs": [],
        "source_ids": ["src-1"],
        "source_bindings": [{"source_id": "src-1", "locators": ["p. 1"]}],
        "panel_refs": [f"panel-{block_id}"],
        "relation_refs": [],
        "identity": ["fact"],
        "content": {
            "title": f"Block {block_id}", "purpose": "Evidence " * 12,
            "form": {"text": "html.text", "table": "html.table"}[kind],
            "relationship": "supports", "reason": "Decision support",
            "anchor": anchor, "role": "primary", "slot": "main", "span": 1,
            "semantic_type": "point_evidence",
        },
    }


def component(component_id, kind="claim-evidence", **updates):
    payload = {
        "id": component_id, "title": component_id,
        "layout_id": "full-evidence", "blocks": [block(component_id)],
        "claim": "Demand exists",
        "evidence_groups": [{"source_id": "src-1", "locators": ["interview 1"]}],
    }
    payload.update(updates)
    return {"kind": kind, "payload": payload}


def render(document):
    env = dict(os.environ)
    result = subprocess.run(
        ["node", str(RENDER)], cwd=ROOT, env=env,
        input=json.dumps(document, ensure_ascii=False), capture_output=True, text=True,
    )
    if result.returncode:
        raise AssertionError(f"render failed ({result.returncode}): {result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


class A4PaginationTest(unittest.TestCase):
    def setUp(self):
        require_browser(self)

    def test_normal_document_has_explicit_pages_and_two_pass_navigation(self):
        doc = {
            "title": "A4 report",
            "components": [
                component("toc", "toc", entries=[{"title": "Finding", "destination": "finding"}]),
                component("finding"),
                component("risk", "risk-boundary", layout_id="decision-matrix",
                          risks=[{"name": "Cash", "priority": "P1"}]),
            ],
        }
        result = render(doc)
        self.assertEqual(result["manifest"]["pageCount"], result["html"].count("data-page-id="))
        self.assertEqual(1, result["manifest"]["blockToPage"]["finding"])
        self.assertEqual(1, result["manifest"]["anchorToPage"]["finding"])
        self.assertNotIn("{{PAGE:", result["html"])
        self.assertIn('data-cross-reference="finding">1</span>', result["html"])

    def test_cover_and_toc_share_authoritative_cover_toc_role_and_whitespace_reason(self):
        cover = {"kind": "cover", "payload": {"id": "cover", "title": "Report", "layout_id": "overview-detail",
                  "title_groups": [{"title": "Report"}], "blocks": []}}
        toc = {"kind": "toc", "payload": {"id": "toc", "title": "目录", "layout_id": "full-evidence",
                "entries": [{"title": "第一章", "destination": "cover"}], "blocks": []}}
        result = render({"title": "Cover TOC", "components": [cover, toc]})
        first = result["manifest"]["pages"][0]
        self.assertEqual("cover-toc", first["role"])
        self.assertEqual("cover-identity", first["whitespaceJustification"])

    def test_boundary_places_next_component_on_new_page_without_overflow(self):
        components = [component(f"c-{index}", repeat_reason="Repeated evidence cards exercise the physical page boundary only", repeat_approved=True) for index in range(1, 9)]
        result = render({"title": "Boundary", "components": components})
        self.assertGreater(result["manifest"]["pageCount"], 1)
        self.assertTrue(all(page["usedHeightPx"] <= page["contentHeightPx"] + 1 for page in result["manifest"]["pages"]))

    def test_unsplittable_overflow_fails_instead_of_clipping_or_shrinking(self):
        huge = component("huge")
        huge["payload"]["blocks"][0]["content"]["purpose"] = "very long evidence " * 20000
        env = dict(os.environ)
        process = subprocess.run(
            ["node", str(RENDER)], cwd=ROOT, env=env,
            input=json.dumps({"title": "Overflow", "components": [huge]}),
            capture_output=True, text=True,
        )
        self.assertNotEqual(0, process.returncode)
        self.assertIn("REPORT_PAGE_OVERFLOW", process.stderr)

    def test_two_claim_fact_boundary_fits_without_shrinking_or_placeholder_chart(self):
        item = block("fact-boundary", "text")
        item["content"]["claims"] = [{
            "id": f"cl-{index}", "statement": "决策主张需要支持、反证、范围与限制" * 2,
            "identity": "judgment", "confidence": "medium", "scope": "目标细分与滩头市场",
            "limitation": "公开证据不能证明普遍性或付费意愿" * 2,
            "support": [{"excerpt": "一手来源支持限定现象" * 3, "source_id": "src-1", "locator": "p. 1"} for _ in range(3)],
            "counter": [],
        } for index in range(2)]
        result = render({"title": "Fact boundary", "components": [component("fact-boundary", blocks=[item])]})
        self.assertEqual(1, result["manifest"]["pageCount"])
        self.assertNotIn('<svg aria-hidden="true"', result["html"])

    def test_long_table_repeats_header_without_shrinking_type(self):
        refs = [{"id": f"src-{i}", "title": f"Source {i}", "locators": [f"p. {i}"]} for i in range(1, 24)]
        table_block = block("sources", "table")
        source_component = component(
            "sources", "references-appendix", layout_id="continued-table",
            blocks=[table_block], references=refs,
        )
        result = render({"title": "Sources", "components": [source_component]})
        pages = result["manifest"]["pagesWithTable"]
        self.assertGreater(result["manifest"]["pageCount"], 1)
        self.assertTrue(all(page["tableHeaderCount"] == 1 for page in pages))
        self.assertGreaterEqual(result["manifest"]["minimumFontPt"], 7.5)
        self.assertEqual(23, sum(item["rowCount"] for item in result["manifest"]["tableContinuations"]))

    def test_long_competition_matrix_splits_by_capacity_and_repeats_headers(self):
        criteria = ["cost", "reliability"]
        alternatives = [{"name": f"Option {index}", "layer": "direct", "values": {key: "pending" for key in criteria}}
                        for index in range(1, 8)]
        matrix_block = block("competition", "table")
        matrix_block["content"].update(semantic_type="competition", comparison={"criteria": criteria, "alternatives": alternatives})
        matrix_block["content"]["exhibit"] = {
            "kind": "competitor-matrix", "family": "matrix", "form": "html.table", "columns": criteria,
            "rows": [{"label": item["name"], "values": [item["values"][key] for key in criteria]} for item in alternatives],
        }
        matrix = component("competition", "comparison", layout_id="comparison-columns", blocks=[matrix_block],
                           criteria=criteria, alternatives=alternatives)
        result = render({"title": "Competition", "components": [matrix]})
        self.assertEqual(2, result["html"].count('data-exhibit-kind="competitor-matrix"'))
        self.assertEqual(2, result["html"].count('<th scope="col">比较项</th>'))
        self.assertEqual(7, sum(result["html"].count(f'<th scope="row">Option {index}</th>') for index in range(1, 8)))

    def test_long_sources_split_at_record_boundaries_and_keep_locators(self):
        refs = [{"id": f"src-{i}", "title": "Evidence " + "detail " * 20, "locators": [f"§{i}"]} for i in range(1, 18)]
        source_component = component(
            "appendix", "references-appendix", layout_id="continued-table",
            blocks=[block("appendix", "table")], references=refs,
        )
        result = render({"title": "Appendix", "components": [source_component]})
        self.assertEqual(17, result["html"].count("data-source-record="))
        self.assertEqual(17, sum(result["html"].count(f">§{index}<") for index in range(1, 18)))
        self.assertTrue(all(item["startRow"] <= item["endRow"] for item in result["manifest"]["tableContinuations"]))

    def test_few_very_long_rows_split_by_measured_height_not_fixed_row_count(self):
        refs = [
            {"id": f"long-{index}", "title": "Long record " + "detail " * 700, "locators": [f"§{index}"]}
            for index in range(1, 4)
        ]
        source_component = component(
            "long-sources", "references-appendix", layout_id="continued-table",
            blocks=[block("long-sources", "table")], references=refs,
        )
        result = render({"title": "Measured rows", "components": [source_component]})
        continuations = result["manifest"]["tableContinuations"]
        self.assertGreater(len(continuations), 1)
        self.assertEqual(3, sum(item["rowCount"] for item in continuations))
        self.assertEqual(len(continuations) - 1, result["html"].count("data-table-continuation=\"true\""))
        self.assertTrue(all(page["usedHeightPx"] <= page["contentHeightPx"] + 1 for page in result["manifest"]["pages"]))

    def test_locked_fonts_are_embedded_loaded_and_never_fall_back(self):
        result = render({"title": "Fonts", "components": [component("finding")]})
        self.assertEqual({"NotoSansSC:400", "NotoSansSC:600", "NotoSerifSC:600"}, set(result["manifest"]["loadedFonts"]))
        self.assertEqual(3, result["html"].count("data:font/woff2;base64,"))
        self.assertNotIn("src:local(", result["html"])

    def test_chapter_openers_begin_on_fresh_page_without_blank_page_and_output_is_deterministic(self):
        opener = component(
            "chapter-2", "section-title", layout_id="overview-detail",
            blocks=[block("chapter-2")], chapter_claims=["Prove demand"],
        )
        doc = {"title": "Recto", "components": [component("intro"), opener]}
        first = render(doc)
        second = render(doc)
        self.assertEqual(first, second)
        self.assertEqual(1, first["manifest"]["blockToPage"]["chapter-2"])
        self.assertFalse(any(page["intentionalBlank"] for page in first["manifest"]["pages"]))

    def test_compatible_components_and_section_heading_compose_continuously(self):
        heading = component(
            "chapter-2", "section-title", layout_id="overview-detail",
            blocks=[block("chapter-2")], chapter_claims=["Prove demand"],
        )
        result = render({"title": "Continuous", "components": [heading, component("finding")]})
        self.assertEqual(1, result["manifest"]["pageCount"])
        self.assertEqual(1, result["manifest"]["blockToPage"]["chapter-2"])
        self.assertEqual(1, result["manifest"]["blockToPage"]["finding"])

    def test_duplicate_titles_and_unjustified_repeated_primary_structures_fail(self):
        first = component("one")
        second = component("two")
        second["payload"]["blocks"][0]["content"]["title"] = "  BLOCK one  "
        duplicate = [first, second]
        process = subprocess.run(
            ["node", str(RENDER)], cwd=ROOT, input=json.dumps({"title": "Duplicate", "components": duplicate}),
            capture_output=True, text=True,
        )
        self.assertNotEqual(0, process.returncode)
        self.assertIn("REPORT_DUPLICATE_TITLE", process.stderr)

        repeated = [component("one"), component("two")]
        process = subprocess.run(
            ["node", str(RENDER)], cwd=ROOT, input=json.dumps({"title": "Repeated", "components": repeated}),
            capture_output=True, text=True,
        )
        self.assertNotEqual(0, process.returncode)
        self.assertIn("REPORT_REPEATED_PRIMARY_STRUCTURE", process.stderr)

        repeated[1]["payload"]["repeat_reason"] = "Same decision matrix continued across a semantic table boundary"
        repeated[1]["payload"]["repeat_approved"] = True
        self.assertEqual(1, render({"title": "Approved repeat", "components": repeated})["manifest"]["pageCount"])

        non_adjacent = [component("one"), component("middle", "risk-boundary", layout_id="decision-matrix",
                        risks=[{"name": "Cash", "priority": "P1"}]), component("three")]
        process = subprocess.run(
            ["node", str(RENDER)], cwd=ROOT, input=json.dumps({"title": "A-B-A", "components": non_adjacent}),
            capture_output=True, text=True,
        )
        self.assertNotEqual(0, process.returncode)
        self.assertIn("REPORT_REPEATED_PRIMARY_STRUCTURE", process.stderr)

    def test_file_mode_writes_html_and_pagination_manifest(self):
        doc = {"title": "Artifacts", "components": [component("finding")]}
        env = dict(os.environ)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "document.json"
            output = root / "build"
            source.write_text(json.dumps(doc, ensure_ascii=False))
            result = subprocess.run(
                ["node", str(RENDER), str(source), str(output)], cwd=ROOT, env=env,
                capture_output=True, text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("data-page-id=", (output / "report.html").read_text())
            manifest = json.loads((output / "pagination-manifest.json").read_text())
            self.assertEqual(1, manifest["pageCount"])


class A4PaginationCapabilityTest(unittest.TestCase):
    def test_heading_css_reserves_cjk_glyph_ascent(self):
        source = RENDER.read_text(encoding="utf-8")
        self.assertIn(".report-component>h1,.report-component>h2{padding-top:1.5mm}", source)

    def test_missing_runtime_skips_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = {"ALLEN_RUNTIME": temporary}
            with self.assertRaises(unittest.SkipTest):
                require_browser(unittest.TestCase(), env)

    def test_missing_runtime_fails_when_tools_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = {"ALLEN_RUNTIME": temporary, "ALLEN_REQUIRE_TOOLS": "1"}
            with self.assertRaises(AssertionError) as raised:
                require_browser(unittest.TestCase(), env)
            self.assertIn("missing A4 browser runtime", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
