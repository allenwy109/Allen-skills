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
from tools.acceptance import Acceptance
from tools.lib.ledger import Ledger


ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES_FILE = ROOT / "tests/report-output-cases.json"
OUT_REPORT = ROOT / "out-report/scripts/out_report.py"
CASE_FIELDS = {
    "id", "scene", "input_snapshot", "expected_claims", "expected_panels",
    "expected_relations", "expected_components", "page_range", "expected_status",
    "negative_mutation",
}


def file_digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def task_input_digest(task):
    task = pathlib.Path(task)
    files = sorted((task / "03_evidence/ledger").glob("*.jsonl"))
    files += sorted(path for path in (task / "07_storyline").iterdir() if path.is_file())
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(task).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


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


def snapshot_path(snapshot):
    path = (ROOT / snapshot["path"]).resolve()
    fixtures = (ROOT / "tests/report-output-fixtures").resolve()
    if fixtures not in path.parents:
        raise AssertionError(f"snapshot escapes fixture directory: {path}")
    return path


def apply_negative(slides, mutation):
    kind = mutation["type"]
    if kind == "unsupported-form":
        slides["slides"][1]["panels"][0]["form"] = "unsupported.form"
    elif kind == "unknown-claim":
        slides["slides"][1]["claim_refs"].append("cl-9999")
    elif kind == "duplicate-panel":
        slides["slides"][2]["panels"][0]["id"] = slides["slides"][1]["panels"][0]["id"]
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
    snapshot = read_json(snapshot_path(case["input_snapshot"]))
    slides = snapshot["slides"]
    if negative:
        apply_negative(slides, case["negative_mutation"])
    write_json(slides_file, slides)
    write_json(task / "07_storyline/sidecar.json", snapshot["sidecar"])
    (task / "07_storyline/03_storyline.md").write_text(snapshot["storyline_md"], encoding="utf-8")
    (task / "07_storyline/06_slides.md").write_text(snapshot["slides_md"], encoding="utf-8")
    manuscript = task / "07_storyline/04_manuscript.md"
    manuscript.write_text(snapshot["manuscript"], encoding="utf-8")
    ledger = Ledger(task)
    for table, records in snapshot["ledger_patches"].items():
        for record_id, fields in records.items():
            ledger.patch(table, record_id, fields)
    for command in ("cards", "clean"):
        generated = subprocess.run(
            [sys.executable, str(F.STORYLINE), command, str(task)], capture_output=True, text=True,
        )
        if generated.returncode:
            raise AssertionError(generated.stdout + generated.stderr)
    return task


def approve_and_package(task, work):
    regression = read_json(work / "visual-regression.json")
    artifacts = read_json(work / "artifact-manifest.json")
    pagination = read_json(work / "build/pagination-manifest.json")
    page_ids = [page["id"] for page in pagination["pages"]]
    author = work / "author-review.json"
    write_json(author, {
        "type": "author", "reviewer": "固定场景作者审查员", "reviewedAt": "2026-10-27T14:00:00+10:30",
        "decision": "accepted", "reason": "逐页检查固定场景的层级、证据、来源与分页，未发现阻断交付的问题。",
        "baselineDigest": regression["baselineDigest"], "candidateDigest": regression["candidateDigest"],
        "differenceDigest": regression["differenceDigest"], "artifactDigest": artifacts["artifactDigest"],
        "paginationDigest": artifacts["paginationDigest"],
    })
    result = run_cli("review", task, "author", author)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    independent = work / "independent-review.json"
    write_json(independent, {
        "type": "independent", "reviewer": "固定场景独立审查员", "at": "2026-10-27T14:05:00+10:30",
        "conclusion": "逐页复核 HTML 与 PDF 后，结构、证据绑定和阅读节奏满足固定场景验收要求。", "issues": [],
        "artifactDigest": artifacts["artifactDigest"], "paginationDigest": artifacts["paginationDigest"],
        "page_ids": page_ids, "media": ["html", "pdf"], "scales": ["100%", "contact-sheet"],
        "chapter_contact_sheets": [{"chapter": "whole-book", "page_ids": page_ids,
                                     "observation": "整册缩略图显示章节过渡、信息密度与留白节奏保持一致。"}],
        "headline_chain": {"status": "reviewed", "observation": "标题链从证据推进到判断与行动，论证顺序完整。"},
        "observations": [{"page_id": page_id, "media": ["html", "pdf"], "scale": ["100%", "contact-sheet"],
                          "observation": f"{page_id} 已在两种媒介和两种尺度检查层级、正文、图表与来源。",
                          "reason": "未发现裁切、证据遗漏或会改变结论的视觉强调。"} for page_id in page_ids],
    })
    result = run_cli("review", task, "independent", independent)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return run_cli("package", task)


class ReportOutputScenarioAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = read_json(CASES_FILE)

    def test_fixture_contract_and_snapshot_hashes_are_locked(self):
        self.assertEqual(6, len(self.cases))
        self.assertEqual(6, len({case["scene"] for case in self.cases}))
        self.assertGreaterEqual(len({tuple(case["expected_claims"]) for case in self.cases}), 4)
        self.assertEqual(6, len({tuple(case["expected_panels"]) for case in self.cases}))
        self.assertGreaterEqual(len({tuple(case["expected_relations"]) for case in self.cases}), 4)
        self.assertGreaterEqual(len({tuple(case["expected_components"]) for case in self.cases}), 5)
        assertions = [read_json(snapshot_path(case["input_snapshot"]))["assertions"] for case in self.cases]
        for field in ("domain", "question", "claim_phrase", "source_title", "metric_unit"):
            self.assertEqual(6, len({item[field] for item in assertions}), field)
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(CASE_FIELDS, set(case))
                path = snapshot_path(case["input_snapshot"])
                self.assertTrue(path.is_file())
                self.assertEqual(case["input_snapshot"]["sha256"], file_digest(path))
                self.assertEqual("passed", case["expected_status"])
                self.assertLessEqual(case["page_range"][0], case["page_range"][1])
                self.assertTrue(case["negative_mutation"]["expected_status"].startswith("REPORT_"))
                self.assertTrue(case["negative_mutation"]["expected_detail"])

    def test_every_case_matches_coverage_components_pages_and_status(self):
        for case in self.cases:
            with self.subTest(case=case["id"], path="positive"), tempfile.TemporaryDirectory() as temporary:
                task = make_case_task(temporary, case)
                self.assertEqual(case["input_snapshot"]["inventory_sha256"], task_input_digest(task))
                snapshot = read_json(snapshot_path(case["input_snapshot"]))
                semantic = snapshot["assertions"]
                materialized_slides = read_json(task / "07_storyline/slides.json")
                self.assertEqual(semantic["question"], materialized_slides["deck"]["brief"]["question"])
                self.assertTrue(all(semantic["domain"] in panel["purpose"] for slide in materialized_slides["slides"] for panel in slide.get("panels", [])))
                ledger = Ledger(task)
                self.assertIn(semantic["claim_phrase"], ledger.get("claims", "cl-0001")["statement"])
                self.assertEqual(semantic["source_title"], ledger.get("sources", "M001")["title"])
                self.assertEqual(semantic["metric_unit"], ledger.get("metrics", "m-0001")["unit"])
                self.assertIn(semantic["claim_phrase"], (task / "07_storyline/04_manuscript.md").read_text(encoding="utf-8"))
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
                self.assertTrue((work / "build/report.html").is_file())
                self.assertTrue((work / "build/report.pdf").is_file())
                package = approve_and_package(task, work)
                self.assertEqual(0, package.returncode, package.stdout + package.stderr)
                entry = next(item for item in Acceptance(task).load()["deliverables"] if item["id"] == "report-main")
                self.assertEqual(case["expected_status"], entry["status"])
                self.assertEqual("independent", entry["reviewer"]["type"])

            with self.subTest(case=case["id"], path="negative"), tempfile.TemporaryDirectory() as temporary:
                task = make_case_task(temporary, case, negative=True)
                result = run_cli("init", task)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                expected = case["negative_mutation"]["expected_status"]
                self.assertIn(expected, result.stderr)
                self.assertIn(case["negative_mutation"]["expected_detail"], result.stderr)
                self.assertFalse((task / "07_storyline/a4-work").exists())

    def test_missing_reviews_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = make_case_task(temporary, self.cases[0])
            self.assertEqual(0, run_cli("init", task).returncode)
            self.assertEqual(1, run_cli("render", task).returncode)
            package = run_cli("package", task)
            self.assertEqual(1, package.returncode)
            self.assertIn("author-review", package.stderr)
            self.assertIn("independent-review", package.stderr)


if __name__ == "__main__":
    unittest.main()
