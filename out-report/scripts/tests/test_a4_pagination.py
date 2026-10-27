import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RENDER = ROOT / "out-report" / "scripts" / "a4" / "render.cjs"


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
    env.setdefault("ALLEN_RUNTIME", "/Users/markjackson/Repos/Allen-skills")
    result = subprocess.run(
        ["node", str(RENDER)], cwd=ROOT, env=env,
        input=json.dumps(document, ensure_ascii=False), capture_output=True, text=True,
    )
    if result.returncode:
        raise AssertionError(f"render failed ({result.returncode}): {result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


class A4PaginationTest(unittest.TestCase):
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

    def test_boundary_places_next_component_on_new_page_without_overflow(self):
        components = [component(f"c-{index}") for index in range(1, 9)]
        result = render({"title": "Boundary", "components": components})
        self.assertGreater(result["manifest"]["pageCount"], 1)
        self.assertTrue(all(page["usedHeightPx"] <= page["contentHeightPx"] + 1 for page in result["manifest"]["pages"]))

    def test_unsplittable_overflow_fails_instead_of_clipping_or_shrinking(self):
        huge = component("huge")
        huge["payload"]["blocks"][0]["content"]["purpose"] = "very long evidence " * 20000
        env = dict(os.environ)
        env.setdefault("ALLEN_RUNTIME", "/Users/markjackson/Repos/Allen-skills")
        process = subprocess.run(
            ["node", str(RENDER)], cwd=ROOT, env=env,
            input=json.dumps({"title": "Overflow", "components": [huge]}),
            capture_output=True, text=True,
        )
        self.assertNotEqual(0, process.returncode)
        self.assertIn("REPORT_PAGE_OVERFLOW", process.stderr)

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

    def test_chapter_openers_begin_on_recto_and_output_is_deterministic(self):
        opener = component(
            "chapter-2", "section-title", layout_id="overview-detail",
            blocks=[block("chapter-2")], chapter_claims=["Prove demand"],
        )
        doc = {"title": "Recto", "components": [component("intro"), opener]}
        first = render(doc)
        second = render(doc)
        self.assertEqual(first, second)
        self.assertEqual(1, first["manifest"]["blockToPage"]["chapter-2"] % 2)
        self.assertTrue(any(page["intentionalBlank"] for page in first["manifest"]["pages"]))

    def test_file_mode_writes_html_and_pagination_manifest(self):
        doc = {"title": "Artifacts", "components": [component("finding")]}
        env = dict(os.environ)
        env.setdefault("ALLEN_RUNTIME", "/Users/markjackson/Repos/Allen-skills")
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


if __name__ == "__main__":
    unittest.main()
