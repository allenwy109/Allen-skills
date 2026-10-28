import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import consulting_project


ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "consulting_project.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def valid_project(task):
    write_json(task / "consulting-project.json", {"version": 1, "depth": "L3"})
    write_json(task / "research-coverage.json", {
        "version": 1,
        "subquestions": [{
            "id": "SQ-1", "question": "Is the pain material?", "material_pain": True,
            "first_party_sources": ["SRC-1"], "user_voice": ["SRC-2"],
            "behavioral": ["SRC-3"], "transaction": [], "counter_evidence": ["SRC-4"],
            "geography": "Australia", "time_period": "2025-2026", "saturated": False,
            "limitations": ["No completed purchase data"], "unresolved_gaps": ["Price sensitivity"],
        }],
    })
    write_json(task / "skill-usage-manifest.json", {
        "version": 1,
        "skills": [
            {"skill": "core-research", "method_cards": ["market-sizing"], "prerequisites": ["source data"],
             "status": "adopted", "inputs": ["brief.md"], "outputs": ["research-coverage.json"],
             "project_manager_disposition": "accepted"},
            {"skill": "lib-consulting", "method_cards": ["five-forces"], "prerequisites": [],
             "status": "rejected", "inputs": ["brief.md"], "outputs": [],
             "project_manager_disposition": "rejected"},
        ],
    })
    write_json(task / "review-closure.json", {
        "version": 1,
        "issues": [{
            "id": "REV-1", "reviewer": "fact-reviewer", "severity": "major", "location": "finding 1",
            "remedy": "Narrowed the claim", "remedy_evidence": ["CLM-1"],
            "re_reviewer": "fact-reviewer", "status": "closed",
        }],
    })
    for line in ("pain", "competition"):
        write_json(task / "research-handoffs" / f"{line}.json", {
            "version": 1, "line_id": line, "role": f"{line}-researcher", "summary": f"{line} findings",
            "source_ids": [f"SRC-{line}"], "data_files": [f"data/{line}.csv"],
            "supported_claims": [f"CLM-{line}"], "counter_evidence": [f"counter-{line}"],
            "limitations": [f"limited {line} sample"], "unresolved_questions": [f"next {line} question"],
            "next_search_recommendation": f"search more {line}", "project_manager_disposition": "accepted",
        })


class ConsultingProjectTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(["python3", str(CLI), *map(str, args)], capture_output=True, text=True)

    def mutate_project(self, mutate):
        temp = tempfile.TemporaryDirectory()
        task = pathlib.Path(temp.name) / "task"
        valid_project(task)
        mutate(task)
        return temp, task

    def test_valid_l3_project_passes_and_summary_reports_quality_state(self):
        with tempfile.TemporaryDirectory() as temp:
            task = pathlib.Path(temp) / "task"
            valid_project(task)
            result = self.run_cli("validate", task)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OK", result.stdout)

            summary = self.run_cli("summary", task)
            self.assertEqual(summary.returncode, 0, summary.stdout + summary.stderr)
            self.assertIn("Research lines: 2", summary.stdout)
            self.assertIn("Coverage gaps: Price sensitivity", summary.stdout)
            self.assertIn("Used skills: core-research, lib-consulting", summary.stdout)
            self.assertIn("Adopted skills: core-research", summary.stdout)
            self.assertIn("Open reviews: 0", summary.stdout)

    def test_l3_rejects_missing_independent_research_lines(self):
        temp, task = self.mutate_project(lambda task: (task / "research-handoffs" / "competition.json").unlink())
        with temp:
            result = self.run_cli("validate", task)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("RESEARCH_LINES_MIN", result.stdout)

    def test_l3_rejects_material_pain_without_two_signal_classes(self):
        def mutate(task):
            path = task / "research-coverage.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["subquestions"][0]["behavioral"] = []
            write_json(path, doc)

        temp, task = self.mutate_project(mutate)
        with temp:
            result = self.run_cli("validate", task)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PAIN_SIGNAL_CLASSES", result.stdout)

    def test_l3_rejects_handoff_without_project_manager_disposition(self):
        def mutate(task):
            path = task / "research-handoffs" / "pain.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            del doc["project_manager_disposition"]
            write_json(path, doc)

        temp, task = self.mutate_project(mutate)
        with temp:
            result = self.run_cli("validate", task)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("HANDOFF_DISPOSITION", result.stdout)

    def test_l3_rejects_claimed_skill_without_output(self):
        def mutate(task):
            path = task / "skill-usage-manifest.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["skills"][0]["outputs"] = []
            write_json(path, doc)

        temp, task = self.mutate_project(mutate)
        with temp:
            result = self.run_cli("validate", task)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SKILL_OUTPUT_REQUIRED", result.stdout)

    def test_l3_rejects_open_blocking_or_major_review_issue(self):
        for severity in ("blocking", "major"):
            with self.subTest(severity=severity):
                def mutate(task):
                    path = task / "review-closure.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    doc["issues"][0]["severity"] = severity
                    doc["issues"][0]["status"] = "open"
                    write_json(path, doc)

                temp, task = self.mutate_project(mutate)
                with temp:
                    result = self.run_cli("validate", task)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("REVIEW_OPEN_MAJOR", result.stdout)

    def test_invalid_project_depth_fails_closed(self):
        def mutate(task):
            write_json(task / "consulting-project.json", {"version": 1, "depth": "TYPO"})

        temp, task = self.mutate_project(mutate)
        with temp:
            result = self.run_cli("validate", task)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PROJECT_DEPTH_INVALID", result.stdout)

    def test_closed_blocking_or_major_review_requires_closure_evidence(self):
        for severity in ("blocking", "major"):
            with self.subTest(severity=severity):
                def mutate(task):
                    path = task / "review-closure.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    issue = doc["issues"][0]
                    issue.update({"severity": severity, "status": "closed", "remedy": "", "remedy_evidence": [], "re_reviewer": ""})
                    write_json(path, doc)

                temp, task = self.mutate_project(mutate)
                with temp:
                    result = self.run_cli("validate", task)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("REVIEW_CLOSURE_INCOMPLETE", result.stdout)

    def test_closed_major_review_rejects_whitespace_and_empty_evidence_items(self):
        def mutate(task):
            path = task / "review-closure.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            issue = doc["issues"][0]
            issue.update({
                "severity": "major", "status": "closed", "remedy": "  ",
                "remedy_evidence": [""], "re_reviewer": "\t",
            })
            write_json(path, doc)

        temp, task = self.mutate_project(mutate)
        with temp:
            result = self.run_cli("validate", task)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("REVIEW_CLOSURE_INCOMPLETE", result.stdout)

    def test_closed_minor_review_does_not_require_re_review_evidence(self):
        def mutate(task):
            path = task / "review-closure.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            issue = doc["issues"][0]
            issue.update({"severity": "minor", "status": "closed", "remedy": "", "remedy_evidence": [], "re_reviewer": ""})
            write_json(path, doc)

        temp, task = self.mutate_project(mutate)
        with temp:
            result = self.run_cli("validate", task)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_init_creates_artifact_families_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            task = pathlib.Path(temp) / "task"
            task.mkdir()
            existing = {"version": 1, "subquestions": [{"sentinel": True}]}
            write_json(task / "research-coverage.json", existing)
            result = self.run_cli("init", task, "--depth", "L3")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((task / "research-coverage.json").read_text(encoding="utf-8")), existing)
            self.assertTrue((task / "consulting-project.json").is_file())
            self.assertTrue((task / "skill-usage-manifest.json").is_file())
            self.assertTrue((task / "review-closure.json").is_file())
            self.assertTrue((task / "research-handoffs").is_dir())

    def test_exclusive_create_preserves_file_when_precheck_is_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "existing.json"
            path.write_text("original\n", encoding="utf-8")
            with mock.patch.object(pathlib.Path, "exists", return_value=False):
                consulting_project.write_new(path, {"replacement": True})
            self.assertEqual(path.read_text(encoding="utf-8"), "original\n")


if __name__ == "__main__":
    unittest.main()
