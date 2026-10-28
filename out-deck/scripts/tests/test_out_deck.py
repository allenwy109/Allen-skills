"""out-deck 的端到端测试：从证据账和 slides.json 走完 report-forge 统一入口的全部步骤，直到交付和登记验收。
需要 node、Chrome（Playwright）和 LibreOffice。缺依赖时默认跳过；设置 ALLEN_REQUIRE_TOOLS=1 时直接失败。
规划观察、代表页观察和审查稿由 synthetic.py 合成（写明"合成"），只验证流程；证据账和页面都是虚构夹具。"""
import json
import contextlib
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
HERE = SCRIPTS.parents[1] / "out-report" / "scripts" / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))
import out_deck  # noqa: E402,F401  （导入时完成运行时定位）
import synthetic  # noqa: E402
from tools.acceptance import Acceptance, review_digest  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "out_deck.py"), *map(str, args)], capture_output=True, text=True)


def build_a4_report(task):
    script = SCRIPTS.parents[1] / "out-report" / "scripts" / "out_report.py"
    command = lambda *args: subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)  # noqa: E731
    init = command("init", task)
    if init.returncode:
        raise AssertionError(init.stdout + init.stderr)
    render = command("render", task)
    if render.returncode != 1 or "REPORT_VISUAL_REGRESSION" not in render.stdout:
        raise AssertionError(render.stdout + render.stderr)
    work = pathlib.Path(task) / "07_storyline" / "a4-work"
    regression = json.loads((work / "visual-regression.json").read_text(encoding="utf-8"))
    artifacts = json.loads((work / "artifact-manifest.json").read_text(encoding="utf-8"))
    pagination = json.loads((work / "build" / "pagination-manifest.json").read_text(encoding="utf-8"))
    pages = [page["id"] for page in pagination["pages"]]
    author = work / "author-review.json"
    author.write_text(json.dumps({
        "type": "author", "reviewer": "Synthetic author", "reviewedAt": "2026-10-27T12:00:00+10:30",
        "decision": "accepted", "reason": "Synthetic A4 coexistence review",
        "baselineDigest": regression["baselineDigest"], "candidateDigest": regression["candidateDigest"],
        "differenceDigest": regression["differenceDigest"], "artifactDigest": artifacts["artifactDigest"],
        "paginationDigest": artifacts["paginationDigest"],
    }), encoding="utf-8")
    independent = work / "independent-review.json"
    decision = {"reviewer": "Synthetic decision reviewer", "role": "decision-maker-reviewer", "at": "2026-10-27T12:04:00+10:30",
                "answers": {key: "The rendered A4 report gives a concrete executive answer."
                            for key in ("answer_visibility", "executive_summary", "argument_sufficiency", "actions", "ownership", "continue_stop_thresholds")}}
    decision["review_digest"] = review_digest(decision)
    independent_value = {
        "type": "independent", "reviewer": "Synthetic independent reviewer", "role": "visual-design-reviewer",
        "at": "2026-10-27T12:05:00+10:30",
        "conclusion": "Synthetic A4 coexistence review accepted", "issues": [],
        "artifactDigest": artifacts["artifactDigest"], "paginationDigest": artifacts["paginationDigest"],
        "page_ids": pages, "media": ["html", "pdf"], "scales": ["100%", "contact-sheet"],
        "chapter_contact_sheets": [{"chapter": "whole-book", "page_ids": pages,
                                     "observation": "All A4 pages were inspected together for rhythm and hierarchy."}],
        "headline_chain": {"status": "reviewed", "observation": "The A4 headline chain remains coherent."},
        "worst_page": {"page_id": pages[-1], "finding": "The densest page remains legible in both media."},
        "decision_review": decision,
        "observations": [{"page_id": page, "media": ["html", "pdf"], "scale": ["100%", "contact-sheet"],
                           "observation": f"A4 page {page} was inspected in both media and scales.",
                           "reason": "No clipping or semantic omission was observed."} for page in pages],
    }
    independent_value["review_digest"] = review_digest(independent_value)
    independent.write_text(json.dumps(independent_value), encoding="utf-8")
    for role, review in (("author", author), ("independent", independent)):
        result = command("review", task, role, review)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
    package = command("package", task)
    if package.returncode:
        raise AssertionError(package.stdout + package.stderr)
    report_dir = pathlib.Path(task) / "08_deliverables" / "client-report"
    return {name: (report_dir / name).read_bytes() for name in ("report.html", "report.pdf")}


def make_task(root, change=None):
    """完整的故事线包（core-storyline 的产出）作为输入；change 用来改 slides.json 做反例。"""
    task = pathlib.Path(root) / "task"
    F.make_storyline_package(task)
    if change:
        p = task / "07_storyline" / "slides.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        change(doc)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return task


def missing():
    need = [t for t in ("node",) if not shutil.which(t)]
    return need + F.missing_tools()


class OutDeckCapabilityTest(unittest.TestCase):
    def test_deck_supports_all_locked_capabilities(self):
        p = run("capabilities", "--strict")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result["layouts"], 38)
        self.assertEqual(result["masters"], 6)
        self.assertEqual(set(result["themes"]), {"mckinsey", "bcg", "accenture"})
        self.assertEqual(set(result["ratios"]), {"16x9", "4x3"})
        self.assertTrue(all(result[key] for key in ("charts", "capacityContracts", "htmlPdfReview", "officialShowcase", "independentReview")))
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["matrixErrors"], [])
        self.assertEqual(result["probeFailures"], [])
        self.assertTrue({"form-catalog", "form-capacity", "narrative", "composition", "review-reuse", "evidence-binding",
                         "showcase-build-scripts", "screenshot-manifest"}.issubset(result["contractProbes"]))

    def test_skill_routes_only_explicit_decks(self):
        text = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("presentation, pitch deck, roadshow deck", text)
        self.assertIn("正式 A4 阅读报告走 `out-report`", text)
        self.assertIn("chart-plan", text)
        self.assertIn("layout-plan", text)
        self.assertIn("module-fill-plan", text)

    def test_strict_capabilities_reject_live_probe_regression(self):
        altered = {"layout_count": 37, "master_count": 5, "themes": ["mckinsey"], "ratios": ["16x9"],
                   "contract_probes": {"form-catalog": {"ok": True, "errors": []}}}
        output = io.StringIO()
        with mock.patch.object(out_deck, "_probe_capabilities", return_value=altered), contextlib.redirect_stdout(output):
            code = out_deck.cmd_capabilities(SimpleNamespace(strict=True))
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual({item["field"] for item in result["mismatches"]}, {"layouts", "masters", "themes", "ratios"})

    def test_strict_capabilities_reject_static_matrix_failure(self):
        output = io.StringIO()
        with mock.patch.object(out_deck.report_capabilities, "check", return_value=["form-capacity: status missing"]), \
                contextlib.redirect_stdout(output):
            code = out_deck.cmd_capabilities(SimpleNamespace(strict=True))
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["matrixErrors"], ["form-capacity: status missing"])

    def test_strict_capabilities_reject_contract_probe_failure(self):
        live = out_deck._probe_capabilities()
        live["contract_probes"] = dict(live["contract_probes"])
        live["contract_probes"]["narrative"] = {"ok": False, "errors": ["validate export missing"]}
        output = io.StringIO()
        with mock.patch.object(out_deck, "_probe_capabilities", return_value=live), contextlib.redirect_stdout(output):
            code = out_deck.cmd_capabilities(SimpleNamespace(strict=True))
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result["probeFailures"], ["narrative"])

    def test_documented_delivery_order_matches_vendor_contract(self):
        requirements = out_deck.engine() / "scripts" / "execution_requirements.cjs"
        script = ("const R=require(process.argv[1]);"
                  "const xs=R.items({workMode:'editorial',policyVersions:{workflow:'execution-plan-2'}});"
                  "process.stdout.write(JSON.stringify(Object.fromEntries(xs.map(x=>[x.id,x.dependsOn]))));")
        p = subprocess.run(["node", "-e", script, str(requirements)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        dependencies = json.loads(p.stdout)
        self.assertEqual(dependencies["archive"], ["package"])
        self.assertEqual(dependencies["delivery"], ["package", "archive"])
        skill = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(skill.index("out_deck step <任务> package"), skill.index("out_deck step <任务> archive"))
        self.assertLess(skill.index("out_deck step <任务> archive"), skill.index("out_deck finish <任务>"))
        self.assertLess(skill.index("out_deck finish <任务>"), skill.index("out_deck plan <任务> delivery"))

class OutDeckPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.need = missing()
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        cls.task = make_task(cls.tmp.name).resolve()
        cls.a4_artifacts = build_a4_report(cls.task)
        d = cls.d = cls.task / "07_storyline" / "deck-work"
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
        step("refresh", cls.task)
        for item, req in (("chart-plan", "chart-diversity"), ("layout-plan", "layout-diversity"), ("module-fill-plan", "module-fill")):
            step("plan", cls.task, item, synthetic.planning(d, item, req), "--reviewer", "合成主笔", "--basis", "合成接收")
        cls.ready = step("step", cls.task, "ready")
        step("step", cls.task, "compile")
        cls.early_finish = run("finish", cls.task)
        pages_json = d / refs()["compile"]["files"]["pages"]["record"]
        step("compose", cls.task)
        step("step", cls.task, "assemble")
        step("step", cls.task, "smoke")
        step("step", cls.task, "iteration", "--pages", "2")
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
        step("step", cls.task, "archive")
        cls.finish = step("finish", cls.task)
        package_html = d / refs()["package"]["files"]["html"]["record"]
        delivery = synthetic._write(d, "delivery.json", {
            "kind": "delivery", "reviewer": synthetic.WHO, "basis": "合成交付记录", "requirementRefs": [],
            "destination": "合成测试收件箱", "deliveredAt": "2026-10-27T12:00:00+10:30",
            "files": [{"record": os.path.relpath(package_html, d / "obs"), "sha256": synthetic.sha(package_html)}],
        })
        step("plan", cls.task, "delivery", delivery, "--reviewer", "合成主笔", "--basis", "合成交付")
        cls.final_status = step("step", cls.task, "status")

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

    def test_complete_lifecycle_is_archived_and_delivered(self):
        plan = json.loads((self.d / "execution-plan.json").read_text(encoding="utf-8"))
        status = json.loads(self.final_status.stdout)
        states = {item["id"]: item.get("status") for item in status["items"]}
        self.assertEqual(states["archive"], "done")
        self.assertEqual(states["delivery"], "done")
        archive = plan["productionRefs"]["archive"]["files"]["manifest"]["record"]
        manifest = json.loads((self.d / archive).read_text(encoding="utf-8"))
        receipt_sha = plan["productionRefs"]["package"]["files"]["receipt"]["sha256"]
        self.assertIn(receipt_sha, {item["sha256"] for item in manifest["files"]})

    def test_finish_before_package_is_refused(self):
        self.assertEqual(self.early_finish.returncode, 2)
        self.assertIn("finish 要在 step package 之后运行", self.early_finish.stderr)

    def test_deliverables_and_acceptance(self):
        out = self.task / "08_deliverables"
        self.assertTrue((out / "deck" / "星河数据科技经营概览.pdf").is_file())
        self.assertTrue((out / "deck" / "speaker-notes.pdf").is_file())
        pages = subprocess.run(["pdfinfo", str(out / "deck" / "星河数据科技经营概览.pdf")], capture_output=True, text=True).stdout
        self.assertRegex(pages, r"Pages:\s+5")                     # 单一来源以证据审计填实参考页
        html = (out / "deck" / "星河数据科技经营概览.html").read_text(encoding="utf-8")
        self.assertIn("主要客户已签三年合同（待确认）", html)
        self.assertIn("4100 万元（预测）", html)
        e = next(x for x in Acceptance(self.task).load()["deliverables"] if x["id"] == "deck-main")
        self.assertEqual(e["kind"], "deck")
        self.assertEqual([c["result"] for c in e["upstream_checks"]], ["passed"] * 7, self.finish.stdout)
        self.assertEqual(e["upstream_checks"][0]["name"], "故事线检查（storyline check）")
        self.assertEqual(e["number_trace"]["untraced"], [])
        self.assertEqual(len(e["files"]), 4)
        self.assertEqual(e["status"], "failed")                    # 还没有成品审查员结论

    def test_a4_report_and_deck_coexist_without_overwrite(self):
        out = self.task / "08_deliverables"
        self.assertTrue((out / "client-report" / "report.pdf").is_file())
        self.assertTrue((out / "deck" / "星河数据科技经营概览.pdf").is_file())
        for name, content in self.a4_artifacts.items():
            self.assertEqual((out / "client-report" / name).read_bytes(), content)
        entries = {item["id"]: item for item in Acceptance(self.task).load()["deliverables"]}
        self.assertIn("report-main", entries)
        self.assertIn("deck-main", entries)
        self.assertEqual(entries["report-main"]["kind"], "report")
        self.assertEqual(entries["deck-main"]["kind"], "deck")

    def test_independent_review_passes(self):
        review = self.task / "verdict.json"
        review.write_text(json.dumps({"type": "independent", "reviewer": "成品审查员（合成）", "at": "2026-10-23T10:00:00+08:00",
                                      "conclusion": "合成结论", "issues": []}, ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPTS.parents[1] / "tools" / "acceptance.py"), str(self.task), "review", "deck-main", str(review)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        e = next(x for x in Acceptance(self.task).load()["deliverables"] if x["id"] == "deck-main")
        self.assertEqual(e["status"], "passed")


class OutDeckInitTest(unittest.TestCase):
    def test_bare_number_blocks_init(self):
        def change(doc):
            doc["slides"][1]["proves"] = "收入从 1800 万元增至 3200 万元，毛利 999 万元"
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(tmp, change)
            p = run("init", task)
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            self.assertIn("数字 999", p.stderr)
            self.assertFalse((task / "07_storyline" / "deck-work").exists())   # 没通过检查就不建引擎任务


if __name__ == "__main__":
    unittest.main()
