import json
import hashlib
import pathlib
import subprocess
import tempfile
import unittest

from tools import acceptance as A

ROOT = pathlib.Path(__file__).resolve().parents[2]


def expected_digest(value):
    def clean(item):
        if isinstance(item, dict):
            return {key: clean(child) for key, child in item.items() if key not in ("review_digest", "digest")}
        if isinstance(item, list):
            return [clean(child) for child in item]
        return item
    payload = json.dumps(clean(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def review(*issues, kind="independent"):
    return {"type": kind, "reviewer": "成品审查员", "at": "2026-10-23T10:00:00+00:00", "conclusion": "看过全部页面",
            "issues": [{"id": f"RV-{i:04d}", "level": lvl, "text": t, "resolved": res,
                        "reviewer": "Visual reviewer"} for i, (lvl, t, res) in enumerate(issues, 1)]}


def entry(**over):
    e = {"id": "chart-x", "kind": "chart", "title": "图", "files": [], "number_trace": {"checked": 2, "untraced": []},
         "upstream_checks": [{"name": "tc_validate", "result": "passed"}], "reviewer": review()}
    e.update(over)
    return e


def report_review(*issues, author="Report author", visual_reviewer="Visual reviewer", decision_reviewer="Decision reviewer"):
    value = review(*issues)
    value.update({
        "author": author,
        "reviewer": visual_reviewer,
        "role": "visual-design-reviewer",
        "worst_page": {"page_id": "page-004", "finding": "The dense matrix is still readable, but has the weakest hierarchy in the report."},
        "decision_review": {
            "reviewer": decision_reviewer,
            "role": "decision-maker-reviewer",
            "answers": {key: "Page-specific answer with enough detail for an executive decision."
                        for key in ("answer_visibility", "executive_summary", "argument_sufficiency", "actions", "ownership", "continue_stop_thresholds")},
        },
    })
    value["decision_review"]["review_digest"] = expected_digest(value["decision_review"])
    value["review_digest"] = expected_digest(value)
    return value


class StatusRuleTest(unittest.TestCase):
    """设计 §8.3 状态规则：每个 failed / conditional 条件都有用例。"""

    def status(self, fixture=False, **over):
        return A.compute_status(entry(**over), fixture)

    def test_passed(self):
        self.assertEqual(self.status(), ("passed", [], []))

    def test_failed_conditions(self):
        cases = {
            "前置检查失败": dict(upstream_checks=[{"name": "tc_validate", "result": "failed", "detail": "瀑布不平"}]),
            "正式任务不允许跳过检查": dict(upstream_checks=[{"name": "storyline check", "result": "skipped"}]),
            "追溯不到证据账": dict(number_trace={"checked": 3, "untraced": ["data.values[0]"]}),
            "未解决的阻塞问题": dict(reviewer=review(("blocking", "标题与数据矛盾", False))),
            "尚未经过成品审查": dict(reviewer=None),
        }
        for msg, over in cases.items():
            with self.subTest(msg):
                status, failures, _ = self.status(**over)
                self.assertEqual(status, "failed")
                self.assertIn(msg, "；".join(failures))

    def test_conditional_conditions(self):
        cases = {
            "未处置的警告": dict(upstream_checks=[{"name": "tc_validate", "result": "warnings", "detail": "类别太多"}]),
            "有限完成": dict(upstream_checks=[{"name": "diligence", "result": "limited", "detail": "research_gate=partial"}]),
            "未解决的重要问题": dict(reviewer=review(("major", "图注缺口径", False))),
            "未经独立审查": dict(reviewer=review(kind="self")),
            "降级为 Markdown 交付": dict(downgraded=True),
        }
        for msg, over in cases.items():
            with self.subTest(msg):
                status, _, conditions = self.status(**over)
                self.assertEqual(status, "conditional")
                self.assertIn(msg, "；".join(conditions))

    def test_resolved_issues_disposed_warnings_and_fixture_skips(self):
        self.assertEqual(self.status(reviewer=review(("blocking", "x", True), ("major", "y", True)))[0], "passed")
        disposed = dict(upstream_checks=[{"name": "tc_validate", "result": "warnings"}],
                        dispositions=[{"source": "tc_validate", "warning": "类别太多", "decision": "保留", "reason": "用户要看全部类别"}])
        self.assertEqual(self.status(**disposed)[0], "passed")
        self.assertEqual(self.status(fixture=True, upstream_checks=[{"name": "storyline check", "result": "skipped"}])[0], "passed")

    def test_report_rejects_open_major_and_incomplete_final_reviews(self):
        base = dict(kind="report", reviewer=report_review())
        cases = {
            "未解决的重要问题": report_review(("major", "第 3 页论据不足", False)),
            "最差页": {**report_review(), "worst_page": None},
            "六个高管问题": {**report_review(), "decision_review": {**report_review()["decision_review"], "answers": {}}},
            "独立审查者与作者不能相同": report_review(author="Same person", visual_reviewer="Same person"),
            "视觉与决策审查者必须独立": report_review(visual_reviewer="Same reviewer", decision_reviewer="Same reviewer"),
            "报告作者身份不能为空": report_review(author=""),
            "审查摘要与内容不匹配": {**report_review(), "review_digest": "a" * 64},
        }
        for message, reviewer in cases.items():
            with self.subTest(message):
                status, failures, _ = self.status(**{**base, "reviewer": reviewer})
                self.assertEqual("failed", status)
                self.assertIn(message, "；".join(failures))

    def test_report_requires_digest_and_closure_evidence_for_resolved_major_issue(self):
        issue = ("major", "第 3 页论据不足", True)
        incomplete = report_review(issue)
        status, failures, _ = self.status(kind="report", reviewer=incomplete)
        self.assertEqual("failed", status)
        self.assertIn("补救证据和一次复审", "；".join(failures))

        complete = report_review(issue)
        complete["issues"][0].update({
            "reviewer": "Decision reviewer",
            "remedy": "Rewrote the claim and added the missing comparison.",
            "remedy_evidence": ["page-003"],
            "re_review": {"reviewer": "Decision reviewer", "at": "2026-10-23T11:00:00+00:00",
                          "evidence": ["page-003"], "digest": ""},
        })
        complete["issues"][0]["re_review"]["digest"] = expected_digest(complete["issues"][0]["re_review"])
        complete["decision_review"]["review_digest"] = expected_digest(complete["decision_review"])
        complete["review_digest"] = expected_digest(complete)
        self.assertEqual("passed", self.status(kind="report", reviewer=complete)[0])

        wrong_reviewer = json.loads(json.dumps(complete))
        wrong_reviewer["issues"][0]["re_review"]["reviewer"] = "Replacement reviewer"
        wrong_reviewer["issues"][0]["re_review"]["digest"] = expected_digest(wrong_reviewer["issues"][0]["re_review"])
        wrong_reviewer["review_digest"] = expected_digest(wrong_reviewer)
        status, failures, _ = self.status(kind="report", reviewer=wrong_reviewer)
        self.assertEqual("failed", status)
        self.assertIn("原审查者", "；".join(failures))

        missing_owner = json.loads(json.dumps(complete))
        missing_owner["issues"][0]["reviewer"] = ""
        missing_owner["review_digest"] = expected_digest(missing_owner)
        status, failures, _ = self.status(kind="report", reviewer=missing_owner)
        self.assertEqual("failed", status)
        self.assertIn("问题审查者", "；".join(failures))

    def test_digest_cli_uses_canonical_review_content(self):
        value = report_review()
        with tempfile.TemporaryDirectory() as temporary:
            source = pathlib.Path(temporary) / "review.json"
            source.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            result = subprocess.run(["python3", str(ROOT / "tools/acceptance.py"), "digest", str(source)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected_digest(value), result.stdout.strip())


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name)
        (self.task / "08_deliverables").mkdir()
        self.file = self.task / "08_deliverables" / "a.png"
        self.file.write_bytes(b"png")
        self.acc = A.Acceptance(self.task)

    def tearDown(self):
        self.tmp.cleanup()

    def rec(self, **over):
        return self.acc.record(entry(files=["08_deliverables/a.png"], reviewer=None, **over))

    def test_record_review_and_tamper(self):
        e = self.rec()
        self.assertEqual(e["files"][0]["sha256"], A.sha256(self.file))
        self.assertEqual(e["status"], "failed")
        self.assertEqual(self.acc.review("chart-x", review())["status"], "passed")
        self.file.write_bytes(b"changed")
        doc = self.acc.check()
        self.assertEqual(doc["deliverables"][0]["status"], "failed")
        self.assertIn("验收后文件被改动", doc["deliverables"][0]["failures"][0])

    def test_re_record_keeps_review_only_if_files_unchanged(self):
        self.rec()
        self.acc.review("chart-x", review())
        self.assertEqual(self.rec()["status"], "passed")
        self.file.write_bytes(b"new version")
        self.assertEqual(self.rec()["status"], "failed")

    def test_missing_file_and_unknown_deliverable(self):
        with self.assertRaises(A.AcceptanceError):
            self.acc.record(entry(files=["08_deliverables/none.png"]))
        with self.assertRaises(A.AcceptanceError):
            self.acc.review("nope", review())

    def test_invalid_entry_is_rejected(self):
        with self.assertRaises(A.AcceptanceError):
            self.rec(kind="video")
        self.assertFalse(self.acc.path.exists())

    def test_fixture_flag_recomputes(self):
        self.rec(upstream_checks=[{"name": "storyline check", "result": "skipped"}])
        self.acc.review("chart-x", review())
        self.assertEqual(self.acc.load()["deliverables"][0]["status"], "failed")
        self.acc.set_fixture(True)
        self.assertEqual(self.acc.load()["deliverables"][0]["status"], "passed")

    def test_cli_exit_codes(self):
        cli = lambda *a: subprocess.run(["python3", str(ROOT / "tools" / "acceptance.py"), str(self.task), *a], capture_output=True, text=True)
        e = self.task / "e.json"
        e.write_text(json.dumps(entry(files=["08_deliverables/a.png"], reviewer=None), ensure_ascii=False), encoding="utf-8")
        self.assertEqual(cli("record", str(e)).returncode, 0)
        p = cli("check")
        self.assertEqual(p.returncode, 1)
        self.assertIn("尚未经过成品审查", p.stdout)
        r = self.task / "r.json"
        r.write_text(json.dumps(review(("major", "图注缺口径", False)), ensure_ascii=False), encoding="utf-8")
        self.assertEqual(cli("review", "chart-x", str(r)).returncode, 0)
        p = cli("check")
        self.assertEqual(p.returncode, 0)
        self.assertIn("[有条件通过]", p.stdout)
        self.assertEqual(cli("review", "nope", str(r)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
