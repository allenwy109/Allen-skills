import json
import pathlib
import subprocess
import tempfile
import unittest

from tools import acceptance as A

ROOT = pathlib.Path(__file__).resolve().parents[2]


def review(*issues, kind="independent"):
    return {"type": kind, "reviewer": "成品审查员", "at": "2026-10-23T10:00:00+00:00", "conclusion": "看过全部页面",
            "issues": [{"id": f"RV-{i:04d}", "level": lvl, "text": t, "resolved": res} for i, (lvl, t, res) in enumerate(issues, 1)]}


def entry(**over):
    e = {"id": "chart-x", "kind": "chart", "title": "图", "files": [], "number_trace": {"checked": 2, "untraced": []},
         "upstream_checks": [{"name": "tc_validate", "result": "passed"}], "reviewer": review()}
    e.update(over)
    return e


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
