import argparse
import json
import pathlib
import tempfile
import unittest

from tools import app_runtime as R
from tools.acceptance import Acceptance


def reviewer():
    return {
        "type": "independent",
        "reviewer": "test-reviewer",
        "at": "2026-10-23T10:00:00+00:00",
        "conclusion": "文件完整",
        "issues": [],
    }


def confirm_file(task, rel):
    R.confirm(task, rel)


class AppRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name) / "task"

    def tearDown(self):
        self.tmp.cleanup()

    def init(self, app="allen-company", files=None, urls=None):
        args = argparse.Namespace(
            task=str(self.task), app=app, request="请分析", request_file=None,
            file=files or [], url=urls or [], depth="L2",
        )
        return R.init_task(args)

    def write(self, rel, content="ok"):
        path = self.task / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_app_is_locked_and_bp_uses_evidence_first(self):
        payload = self.init("allen-bp-review")
        self.assertEqual(payload["app_id"], "allen-bp-review")
        self.assertEqual(payload["stage"], "intake")
        run = json.loads((self.task / "app-run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["stages"][1:3], ["evidence", "framing"])
        with self.assertRaises(R.AppError):
            self.init("allen-company")

    def test_idea_uses_clarify_pathing_and_research_first(self):
        payload = self.init("allen-idea")
        self.assertEqual(payload["stage"], "intake")
        run = json.loads((self.task / "app-run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["stages"][:6], [
            "intake", "clarify", "pathing", "framing", "research", "method",
        ])

    def test_idea_clarify_requires_file_and_user_confirmation(self):
        self.init("allen-idea")
        self.assertEqual(R.advance(self.task)["advanced"], "intake")
        missing = R.advance(self.task)
        self.assertEqual(missing["validation"], "failed")
        self.write("00_idea-definition.md", "# 想法定义")
        missing = R.advance(self.task)
        self.assertIn("confirmation:00_idea-definition.md", missing["missing"])
        confirm_file(self.task, "00_idea-definition.md")
        self.assertEqual(R.advance(self.task)["advanced"], "clarify")

    def test_idea_pathing_requires_file_and_user_confirmation(self):
        self.init("allen-idea")
        R.advance(self.task)
        self.write("00_idea-definition.md", "# 想法定义")
        confirm_file(self.task, "00_idea-definition.md")
        R.advance(self.task)
        self.write("00_venture-paths.md", "# 企业化路径")
        missing = R.advance(self.task)
        self.assertIn("confirmation:00_venture-paths.md", missing["missing"])
        confirm_file(self.task, "00_venture-paths.md")
        self.assertEqual(R.advance(self.task)["advanced"], "pathing")

    def test_idea_confirmation_expires_when_file_changes(self):
        self.init("allen-idea")
        R.advance(self.task)
        self.write("00_idea-definition.md", "# 第一版")
        confirm_file(self.task, "00_idea-definition.md")
        self.write("00_idea-definition.md", "# 第二版")
        result = R.advance(self.task)
        self.assertEqual(result["validation"], "failed")
        self.assertIn("confirmation:00_idea-definition.md", result["missing"])

    def test_idea_can_rewind_to_pathing_and_requires_new_confirmation(self):
        self.init("allen-idea")
        R.advance(self.task)
        self.write("00_idea-definition.md", "# 想法定义")
        confirm_file(self.task, "00_idea-definition.md")
        R.advance(self.task)
        self.write("00_venture-paths.md", "# 第一版路径")
        confirm_file(self.task, "00_venture-paths.md")
        R.advance(self.task)
        self.write("01_issue-tree.md")
        R.advance(self.task)

        result = R.rewind(self.task, "pathing")
        self.assertEqual(result["stage"], "pathing")
        stale = R.advance(self.task)
        self.assertEqual(stale["validation"], "failed")
        self.assertIn("confirmation:00_venture-paths.md", stale["missing"])
        self.write("00_venture-paths.md", "# 第二版路径")
        confirm_file(self.task, "00_venture-paths.md")
        self.assertEqual(R.advance(self.task)["advanced"], "pathing")

    def test_file_input_requires_registered_source(self):
        self.init(files=["company.pdf"])
        result = R.advance(self.task)
        self.assertEqual(result["validation"], "failed")
        self.assertIn("03_evidence/ledger/sources.jsonl", result["missing"])

    def test_url_is_collected_by_evidence_stage_not_file_intake(self):
        self.init(urls=["https://example.com"])
        result = R.advance(self.task)
        self.assertEqual(result["advanced"], "intake")

    def test_wait_and_block_require_resume(self):
        self.init()
        R.set_state(self.task, "waiting_user", "缺财务口径")
        with self.assertRaises(R.AppError):
            R.advance(self.task)
        self.assertEqual(R.resume(self.task)["status"], "running")
        R.set_state(self.task, "blocked", "来源不可访问")
        with self.assertRaises(R.AppError):
            R.advance(self.task)

    def test_full_gate_requires_both_reviewed_deliverables(self):
        self.init()
        self.assertEqual(R.advance(self.task)["stage"], "framing")
        required = {
            "framing": "01_issue-tree.md",
            "evidence": "03_evidence/ledger/sources.jsonl",
            "method": "02_method-plan.md",
            "analysis": "04_analysis/result.md",
            "review": "05_review-log.md",
            "synthesis": "06_synthesis.md",
            "storyline": "07_storyline/slides.json",
        }
        for stage, rel in required.items():
            self.write(rel, "{}" if rel.endswith(".json") else "ok")
            if stage == "evidence":
                self.write("03_evidence/ledger/claims.jsonl", "")
            result = R.advance(self.task)
            self.assertEqual(result["advanced"], stage)

        self.write("08_deliverables/report/main.pdf")
        self.write("08_deliverables/report/main.html")
        self.assertEqual(R.advance(self.task)["advanced"], "report")
        self.write("08_deliverables/supporting-package.zip")
        self.assertEqual(R.advance(self.task)["advanced"], "support")

        acc = Acceptance(self.task)
        report = acc.record({
            "id": "report-main", "kind": "report", "title": "主报告",
            "files": ["08_deliverables/report/main.pdf", "08_deliverables/report/main.html"],
            "upstream_checks": [], "number_trace": {"checked": 0, "untraced": []},
        })
        support = acc.record({
            "id": "support-company", "kind": "support_package", "title": "支撑包",
            "files": ["08_deliverables/supporting-package.zip"],
            "upstream_checks": [], "number_trace": {"checked": 0, "untraced": []},
        })
        self.assertEqual(report["status"], "failed")
        self.assertEqual(support["status"], "failed")
        failed = R.advance(self.task)
        self.assertEqual(failed["validation"], "failed")
        acc.review("report-main", reviewer())
        acc.review("support-company", reviewer())
        self.assertEqual(R.advance(self.task)["advanced"], "acceptance")
        self.assertEqual(R.finish(self.task)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
