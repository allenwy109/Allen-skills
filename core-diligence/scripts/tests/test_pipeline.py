"""尽调报告链路：转母版（tools/bridge/diligence_to_manuscript.py）的测试，以及端到端测试
（尽调 → 转母版 → 拆页 → 故事线检查 → 拆页后复核 → out-report 出正式报告 → 验收通过）。
端到端需要 node、Chrome、LibreOffice；缺依赖时默认跳过，设置 ALLEN_REQUIRE_TOOLS=1 时直接失败。夹具全部虚构。"""
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import diligence_fixture as F  # noqa: E402
import dcontent  # noqa: E402
import diligence  # noqa: E402
from tools.acceptance import Acceptance  # noqa: E402
from tools.bridge import diligence_to_manuscript as B  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402
from tools.tests import fixtures as TF  # noqa: E402

STORYLINE = REPO / "core-storyline" / "scripts" / "storyline.py"
OUT_REPORT = REPO / "out-report" / "scripts" / "out_report.py"


def bridged(root, purpose=None):
    task = pathlib.Path(root) / "task"
    F.make_diligence_task(task)
    if purpose:
        Ledger(task).patch("project", "project", {"purpose": purpose})
    r = B.convert(task)
    return task, r


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task, self.result = bridged(self.tmp.name)
        self.s = self.task / "07_storyline"
        self.led = Ledger(self.task)

    def tearDown(self):
        self.tmp.cleanup()

    def test_block_ids_match_core_diligence(self):
        self.assertEqual([b for b, _, _ in B.block_ids(F.CONTENT)], [b for b, _, _ in dcontent.block_ids(F.CONTENT)])
        bm = json.loads((self.s / "block_map.json").read_text(encoding="utf-8"))
        self.assertEqual(len(bm), self.result["blocks"])
        self.assertEqual(bm[1], {"block_id": "company-profile-2", "section_id": "company-profile", "section_title": F.CONTENT["sections"][0]["title"],
                                 "type": "timeline"})

    def test_supplementary_claims_and_cards(self):
        self.assertEqual(self.result["claims_added"], ["cl-0004", "cl-0005", "cl-0006", "cl-0007", "cl-0008", "cl-0009"])  # ev-0006、ev-0010 共用一条主张
        c7 = self.led.get("claims", "cl-0007")
        self.assertEqual((c7["kind"], c7["verification"], c7["materiality"]), ("fact", "single_source", "major"))
        self.assertEqual(c7["limitation"], "只有公司自己的材料，未经独立核实")
        cards = {c["claim_id"]: c for c in self.led.read("cards")}
        self.assertEqual(cards["cl-0007"]["value_tier"], "A")
        self.assertEqual(cards["cl-0007"]["topic"], "交易流程")
        self.assertEqual([i for i in self.led.check() if i["level"] == "error"], [])

    def test_metrics_block_registers_metrics(self):
        content = copy.deepcopy(F.CONTENT)
        content["sections"][4]["blocks"].append({"type": "metrics", "items": [
            {"label": "员工人数", "value": 85, "unit": "人", "period": "2025 年末", "entity_id": "ENT-0001", "kind": "company_claim", "evidence_ids": ["ev-0011"], "note": "公司口径"},
            {"label": "研发人员", "value": None, "unit": "人", "period": "2025 年末", "entity_id": "ENT-0001", "kind": "company_claim", "evidence_ids": [], "note": "未披露"}]})
        task2 = pathlib.Path(self.tmp.name) / "t2"
        F.make_diligence_task(task2)
        Ledger(task2).add("evidence", F.ev("U002", "第 15 页", "2025 年末员工 85 人"))
        (task2 / "03d_diligence" / "report-content.json").write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        B.convert(task2)
        led = Ledger(task2)
        claim = next(c for c in led.read("claims") if c["statement"].startswith("员工人数"))
        metrics = [led.get("metrics", m) for m in claim["metric_refs"]]
        self.assertEqual([(m["value"] if "value" in m else None, m["status"]) for m in metrics], [(85, "present"), (None, "missing")])

    def test_manuscript_and_storyline_files(self):
        master = (self.s / "04_manuscript.md").read_text(encoding="utf-8")
        self.assertEqual(master.count("<!-- block:"), self.result["blocks"])
        self.assertIn("2025 年毛利率 42.0%〔card-0006｜U003 第 12 页、card-0007｜U003 第 13 页〕。", master)   # 引用在句号之前
        for chapter in ("## 主要风险与未知", "## 补齐路径", "## 方法与局限"):
            self.assertIn(chapter, master)
        self.assertIn("主体：云帆智造科技有限公司", master)
        self.assertEqual((self.s / "04_manuscript_clean.md").read_text(encoding="utf-8"), B.clean_text(master))
        self.assertIn("故事线模式：公司研究", (self.s / "03_storyline.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.s / "sidecar.json").read_text(encoding="utf-8"))["confirmation_points"][0]["status"], "auto_adopted")
        self.assertTrue((self.s / "02_info_cards.md").is_file())

    def test_special_purpose_uses_diligence_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            task, _ = bridged(tmp, purpose="investment")
            self.assertIn("故事线模式：尽调结论", (task / "07_storyline" / "03_storyline.md").read_text(encoding="utf-8"))

    def test_split_passes_storyline_and_after_split_checks(self):
        F.write_split(self.task)
        subprocess.run([sys.executable, str(STORYLINE), "sync", str(self.task)], capture_output=True, text=True, check=True)
        out = subprocess.run([sys.executable, str(STORYLINE), "check", str(self.task), "--json"], capture_output=True, text=True)
        self.assertEqual(json.loads(out.stdout)["errors"], [])
        self.assertEqual(diligence.content_check(self.task, after_split=True, final=True)["errors"], [])
        slides = json.loads((self.s / "slides.json").read_text(encoding="utf-8"))
        slides["slides"][2]["block_ids"].remove("founders-team-1")
        (self.s / "slides.json").write_text(json.dumps(slides, ensure_ascii=False), encoding="utf-8")
        self.assertIn("内容块 founders-team-1 没有落到任何页上", "\n".join(diligence.content_check(self.task, after_split=True)["errors"]))


class DiligenceReportPipelineTest(unittest.TestCase):
    """端到端：一家虚构公司的尽调走完报告链路，验收为通过（路线图对计划 7 的要求）。"""

    @classmethod
    def setUpClass(cls):
        cls.need = [t for t in ("node",) if not shutil.which(t)] + TF.missing_tools()
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        task = cls.task = (pathlib.Path(cls.tmp.name) / "task").resolve()
        F.make_diligence_task(task)
        B.convert(task)
        F.write_split(task)
        subprocess.run([sys.executable, str(STORYLINE), "sync", str(task)], capture_output=True, text=True, check=True)
        d = task / "07_storyline" / "a4-work"

        def run(*args):
            p = subprocess.run([sys.executable, str(OUT_REPORT), *map(str, args)], capture_output=True, text=True)
            if p.returncode:
                raise AssertionError(f"{args[:3]} 失败：{p.stdout[-1500:]}{p.stderr[-1500:]}")
            return p

        run("init", task)
        preview = subprocess.run([sys.executable, str(OUT_REPORT), "render", str(task)], capture_output=True, text=True)
        if preview.returncode != 1:
            raise AssertionError(f"render 应因未审视觉差异失败关闭：{preview.stdout}{preview.stderr}")
        if not (d / "visual-regression.json").is_file():
            raise AssertionError(f"render 未生成视觉回归证据，不是 needs-reapproval 失败：{preview.stdout}{preview.stderr}")
        regression = json.loads((d / "visual-regression.json").read_text(encoding="utf-8"))
        artifacts = json.loads((d / "artifact-manifest.json").read_text(encoding="utf-8"))
        pages = [page["id"] for page in json.loads((d / "build/pagination-manifest.json").read_text(encoding="utf-8"))["pages"]]
        author = d / "author-review.json"
        author.write_text(json.dumps({"type": "author", "reviewer": "合成主笔", "reviewedAt": "2026-10-21T09:00:00+08:00",
                                      "decision": "accepted", "reason": "合成夹具已逐页复核标题、证据、限制、来源和整册阅读节奏。",
                                      "baselineDigest": regression["baselineDigest"], "candidateDigest": regression["candidateDigest"],
                                      "differenceDigest": regression["differenceDigest"], "artifactDigest": artifacts["artifactDigest"],
                                      "paginationDigest": artifacts["paginationDigest"]}, ensure_ascii=False), encoding="utf-8")
        run("review", task, "author", author)
        independent = d / "independent-review.json"
        independent.write_text(json.dumps({"type": "independent", "reviewer": "成品审查员（合成）", "at": "2026-10-21T10:00:00+08:00",
                                           "conclusion": "合成夹具的整册证据、层级和阅读顺序已经逐页复核。", "issues": [],
                                           "artifactDigest": artifacts["artifactDigest"], "paginationDigest": artifacts["paginationDigest"],
                                           "page_ids": pages, "media": ["html", "pdf"], "scales": ["100%", "thumbnail"],
                                           "chapter_contact_sheets": [{"chapter": "whole-book", "page_ids": pages,
                                                                       "observation": "全册缩略图的章节节奏、留白和证据密度已经按顺序检查。"}],
                                           "headline_chain": {"status": "reviewed", "observation": "标题链从公司身份、经营表现逐步收束到风险与补齐动作。"},
                                           "observations": [{"page_id": page, "media": ["html", "pdf"], "scale": ["100%", "thumbnail"],
                                                             "observation": f"{page} 的标题、证据、限制和来源已在两种媒介逐项查看。",
                                                             "reason": "页面信息完整，未发现裁切、遗漏或误导性视觉强调。"} for page in pages]}, ensure_ascii=False), encoding="utf-8")
        run("review", task, "independent", independent)
        cls.finish = subprocess.run([sys.executable, str(OUT_REPORT), "package", str(task)], capture_output=True, text=True)

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

    def test_report_is_delivered_with_all_checks_passed(self):
        self.assertEqual(self.finish.returncode, 0, self.finish.stdout + self.finish.stderr)
        e = next(x for x in Acceptance(self.task).load()["deliverables"] if x["id"] == "report-main")
        names = [c["name"] for c in e["upstream_checks"]]
        self.assertEqual([c["result"] for c in e["upstream_checks"]], ["passed"] * 10, self.finish.stdout)
        for name in ("尽调检查（diligence check）", "尽调内容契约（拆页后复核、22 条人工清单）", "尽调完成状态"):
            self.assertIn(name, names)
        html = next((self.task / "08_deliverables" / "report").glob("*.html")).read_text(encoding="utf-8")
        self.assertIn("5600 万元", html)

    def test_independent_review_makes_it_passed(self):
        verdict = self.task / "verdict.json"
        verdict.write_text(json.dumps({"type": "independent", "reviewer": "成品审查员（合成）", "at": "2026-10-21T10:00:00+08:00",
                                       "conclusion": "合成结论", "issues": []}, ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, str(REPO / "tools" / "acceptance.py"), str(self.task), "review", "report-main", str(verdict)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        e = next(x for x in Acceptance(self.task).load()["deliverables"] if x["id"] == "report-main")
        self.assertEqual(e["status"], "passed")


if __name__ == "__main__":
    unittest.main()
