"""out-report 的端到端测试：从证据账和 slides.json 走完 report-forge 统一入口的全部步骤，直到交付和登记验收。
需要 node、Chrome（Playwright）和 LibreOffice。缺依赖时默认跳过；设置 ALLEN_REQUIRE_TOOLS=1 时直接失败。
规划观察、代表页观察和审查稿由 synthetic.py 合成（写明"合成"），只验证流程；证据账和页面都是虚构夹具。"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))
import out_report  # noqa: E402,F401  （导入时完成运行时定位）
import synthetic  # noqa: E402
from tools.acceptance import Acceptance  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "out_report.py"), *map(str, args)], capture_output=True, text=True)


def make_task(root, slides=None):
    task = pathlib.Path(root) / "task"
    F.make_report_ledger(task)
    story = F.ensure_dir(task / "07_storyline")
    (story / "slides.json").write_text(json.dumps(slides or F.report_slides(), ensure_ascii=False), encoding="utf-8")
    (story / "sidecar.json").write_text(json.dumps(F.report_sidecar(), ensure_ascii=False), encoding="utf-8")
    return task


def missing():
    need = [t for t in ("node",) if not shutil.which(t)]
    return need + F.missing_tools()


class OutReportPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.need = missing()
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        cls.task = make_task(cls.tmp.name).resolve()
        d = cls.d = cls.task / "07_storyline" / "forge-work"
        cls.log = []

        def step(*args, expect=0):
            p = run(*args)
            cls.log.append((args, p))
            if p.returncode != expect:
                raise AssertionError(f"{args} 退出码 {p.returncode}：{p.stdout[-1500:]}{p.stderr[-1500:]}")
            return p

        def refs():
            return json.loads((d / "execution-plan.json").read_text(encoding="utf-8"))["productionRefs"]

        step("init", cls.task)
        for item, req in (("chart-plan", "chart-diversity"), ("layout-plan", "layout-diversity"), ("module-fill-plan", "module-fill")):
            step("plan", cls.task, item, synthetic.planning(d, item, req), "--reviewer", "合成主笔", "--basis", "合成接收")
        cls.ready = step("step", cls.task, "ready")
        step("step", cls.task, "compile")
        cls.early_finish = run("finish", cls.task)
        pages_json = d / refs()["compile"]["files"]["pages"]["record"]
        parts = [d / "bookend-cover.html", HERE / "fixture_body.html", d / "bookend-references.html", d / "bookend-back.html"]
        (d / "pages.html").write_text("\n".join(f.read_text(encoding="utf-8") for f in parts), encoding="utf-8")
        shutil.copy2(HERE / "fixture_page.css", d / "page.css")
        step("step", cls.task, "assemble")
        step("step", cls.task, "smoke")
        smoke = json.loads((d / ".allen" / "runs.json").read_text(encoding="utf-8"))["smoke"]
        step("plan", cls.task, "representatives", synthetic.representatives(d, smoke), "--reviewer", "合成主笔", "--basis", "合成接收")
        step("plan", cls.task, "production", synthetic.production(d, d / refs()["assemble"]["files"]["html"]["record"]),
             "--reviewer", "合成主笔", "--basis", "合成接收")
        step("step", cls.task, "acceptance")
        step("step", cls.task, "review-pack")
        synthetic.fill_reviews(d, pages_json)
        step("step", cls.task, "aggregate")
        step("step", cls.task, "snapshot")
        step("step", cls.task, "package")
        cls.finish = step("finish", cls.task)

    @classmethod
    def tearDownClass(cls):
        if not cls.need:
            cls.tmp.cleanup()

    def setUp(self):
        if self.need:
            msg = f"缺少：{', '.join(self.need)}"
            if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
                self.fail(msg)
            self.skipTest(msg)

    def test_task_fields_and_bookends(self):
        t = json.loads((self.d / "task.json").read_text(encoding="utf-8"))
        self.assertEqual((t["kind"], t["workMode"], t["policyVersions"]["visual"], t["reviewPolicy"]),
                         ("report", "editorial", "narrative-focus-1", "independent"))
        self.assertIn('data-page-role="cover"', (self.d / "bookend-cover.html").read_text(encoding="utf-8"))
        self.assertIn("星河数据科技 2025 年年报", (self.d / "bookend-references.html").read_text(encoding="utf-8"))
        self.assertIn('"status": "PASS"', self.ready.stdout)

    def test_finish_before_package_is_refused(self):
        self.assertEqual(self.early_finish.returncode, 2)
        self.assertIn("finish 要在 step package 之后运行", self.early_finish.stderr)

    def test_deliverables_and_acceptance(self):
        out = self.task / "08_deliverables"
        self.assertTrue((out / "report" / "星河数据科技经营概览.pdf").is_file())
        self.assertTrue((out / "speaker-notes.pdf").is_file())
        pages = subprocess.run(["pdfinfo", str(out / "report" / "星河数据科技经营概览.pdf")], capture_output=True, text=True).stdout
        self.assertRegex(pages, r"Pages:\s+5")                     # 封面、两页正文、参考资料、封底
        html = (out / "report" / "星河数据科技经营概览.html").read_text(encoding="utf-8")
        self.assertIn("主要客户已签三年合同（待确认）", html)
        self.assertIn("4100 万元（预测）", html)
        e = next(x for x in Acceptance(self.task).load()["deliverables"] if x["id"] == "report-main")
        self.assertEqual([c["result"] for c in e["upstream_checks"]], ["passed"] * 6, self.finish.stdout)
        self.assertEqual(e["number_trace"]["untraced"], [])
        self.assertEqual(len(e["files"]), 4)
        self.assertEqual(e["status"], "failed")                    # 还没有成品审查员结论

    def test_independent_review_passes(self):
        review = self.task / "verdict.json"
        review.write_text(json.dumps({"type": "independent", "reviewer": "成品审查员（合成）", "at": "2026-10-23T10:00:00+08:00",
                                      "conclusion": "合成结论", "issues": []}, ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPTS.parents[1] / "tools" / "acceptance.py"), str(self.task), "review", "report-main", str(review)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        e = next(x for x in Acceptance(self.task).load()["deliverables"] if x["id"] == "report-main")
        self.assertEqual(e["status"], "passed")


class OutReportInitTest(unittest.TestCase):
    def test_bare_number_blocks_init(self):
        slides = F.report_slides()
        slides["slides"][1]["proves"] = "收入从 1800 万元增至 3200 万元，毛利 999 万元"
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(tmp, slides)
            p = run("init", task)
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            self.assertIn("数字 999", p.stderr)
            self.assertFalse((task / "07_storyline" / "forge-work").exists())   # 没通过检查就不建引擎任务


if __name__ == "__main__":
    unittest.main()
