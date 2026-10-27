"""Fixed cross-scene acceptance cases for the A4 report output."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.tests import fixtures as F


ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES_FILE = ROOT / "tests/report-output-cases.json"
OUT_REPORT = ROOT / "out-report/scripts/out_report.py"
CASE_FIELDS = {
    "id", "scene", "input_snapshot", "expected_claims", "expected_panels",
    "expected_relations", "expected_components", "page_range", "expected_status",
    "negative_mutation",
}


def canonical_digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def runtime_root():
    if (ROOT / "vendor/report-forge/node_modules/playwright").is_dir():
        return ROOT
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return (ROOT / common).resolve().parent


def run_cli(*args):
    env = dict(os.environ)
    env["ALLEN_RUNTIME"] = str(runtime_root())
    env["ALLEN_REQUIRE_TOOLS"] = "1"
    return subprocess.run(
        [sys.executable, str(OUT_REPORT), *map(str, args)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    pathlib.Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8",
    )


def apply_snapshot(slides, snapshot):
    payload = snapshot["payload"]
    for field in ("title", "story_mode", "audience", "decision"):
        slides["deck"][field] = payload[field]
    slides["deck"]["cover"]["project"] = payload["title"]
    slides["slides"][0]["action_title"] = payload["title"]
    variant = payload["variant"]
    if variant == "decision-table":
        slides["slides"][1]["panels"][0].update(form="html.table", relationship="decision")
    elif variant == "chart-heavy":
        slides["slides"][1]["panels"][1].update(form="svg.custom", relationship="comparison")
    elif variant == "text-heavy":
        slides["slides"][1]["panels"][0].update(form="html.text", relationship="text")
        slides["slides"][2]["panels"][0].update(form="html.text", relationship="text")
    elif variant != "balanced":
        raise AssertionError(f"unknown fixed variant: {variant}")


def apply_negative(slides, mutation):
    kind = mutation["type"]
    if kind == "unsupported-form":
        slides["slides"][1]["panels"][0]["form"] = "unsupported.form"
    elif kind == "unknown-claim":
        slides["slides"][1]["claim_refs"].append("cl-9999")
    elif kind == "duplicate-panel":
        slides["slides"][2]["panels"][0]["id"] = slides["slides"][1]["panels"][0]["id"]
    elif kind == "duplicate-relation":
        slides["slides"][2]["relations"][0]["id"] = slides["slides"][1]["relations"][0]["id"]
    elif kind == "unknown-metric":
        slides["slides"][1]["metric_refs"].append("m-9999")
    elif kind == "unknown-relation-panel":
        slides["slides"][1]["relations"][0]["panel_refs"][1] = "missing-panel"
    else:
        raise AssertionError(f"unknown negative mutation: {kind}")


def make_case_task(root, case, negative=False):
    task = pathlib.Path(root) / ("negative" if negative else "positive")
    F.make_storyline_package(task)
    slides_file = task / "07_storyline/slides.json"
    slides = read_json(slides_file)
    apply_snapshot(slides, case["input_snapshot"])
    if negative:
        apply_negative(slides, case["negative_mutation"])
    write_json(slides_file, slides)
    return task


class ReportOutputScenarioAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = read_json(CASES_FILE)

    def test_fixture_contract_and_snapshot_hashes_are_locked(self):
        self.assertEqual(6, len(self.cases))
        self.assertEqual(6, len({case["scene"] for case in self.cases}))
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(CASE_FIELDS, set(case))
                self.assertEqual(case["input_snapshot"]["sha256"], canonical_digest(case["input_snapshot"]["payload"]))
                self.assertEqual("awaiting-human-visual-review", case["expected_status"])
                self.assertLessEqual(case["page_range"][0], case["page_range"][1])
                self.assertTrue(case["negative_mutation"]["expected_status"].startswith("REPORT_"))

    def test_every_case_matches_coverage_components_pages_and_status(self):
        for case in self.cases:
            with self.subTest(case=case["id"], path="positive"), tempfile.TemporaryDirectory() as temporary:
                task = make_case_task(temporary, case)
                init = run_cli("init", task)
                self.assertEqual(0, init.returncode, init.stdout + init.stderr)
                work = task / "07_storyline/a4-work"
                coverage = read_json(work / "coverage-manifest.json")
                for side in ("input", "output"):
                    self.assertEqual(set(case["expected_claims"]), set(coverage[side]["claims"]))
                    self.assertEqual(set(case["expected_panels"]), set(coverage[side]["panels"]))
                    self.assertEqual(set(case["expected_relations"]), set(coverage[side]["relations"]))
                document = read_json(work / "render-document.json")
                self.assertEqual(case["expected_components"], [item["kind"] for item in document["components"]])

                render = run_cli("render", task)
                self.assertEqual(1, render.returncode, render.stdout + render.stderr)
                self.assertIn("REPORT_VISUAL_REGRESSION", render.stdout)
                pagination = read_json(work / "build/pagination-manifest.json")
                self.assertLessEqual(case["page_range"][0], pagination["pageCount"])
                self.assertLessEqual(pagination["pageCount"], case["page_range"][1])
                qa = read_json(work / "qa-result.json")
                self.assertEqual({"REPORT_VISUAL_REGRESSION"}, {item["code"] for item in qa["blocking"]})
                status = "awaiting-human-visual-review" if qa["status"] == "failed" else qa["status"]
                self.assertEqual(case["expected_status"], status)
                self.assertTrue((work / "build/report.html").is_file())
                self.assertTrue((work / "build/report.pdf").is_file())

            with self.subTest(case=case["id"], path="negative"), tempfile.TemporaryDirectory() as temporary:
                task = make_case_task(temporary, case, negative=True)
                result = run_cli("init", task)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                expected = case["negative_mutation"]["expected_status"]
                self.assertIn(expected, result.stderr)
                self.assertFalse((task / "07_storyline/a4-work").exists())


if __name__ == "__main__":
    unittest.main()
