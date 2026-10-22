"""out-poster 的端到端测试。需要虚拟环境里的 Playwright 和 Chromium（./install.sh --render-deps）。
缺依赖时默认跳过；设置 ALLEN_REQUIRE_TOOLS=1 时直接失败。海报和证据账都是虚构的夹具。"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import out_poster  # noqa: E402,F401  （导入时完成运行时定位）
from tools.acceptance import Acceptance  # noqa: E402
from tools.lib import runtime  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixture_poster.html"


def run_poster(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "out_poster.py"), *map(str, args)], capture_output=True, text=True)


def write_blueprint_and_ir(d, title):
    bp = {"schema_version": 1, "goal": "一眼看懂收入规模与增长", "audience": "投资经理", "core_claim": "收入两年增长近八成，规模仍小",
          "logic": "narrative", "missing": [],
          "modules": [{"id": "bignum", "role": "evidence", "title": "收入", "summary": "两年收入与增长率", "source_refs": ["M001"]}]}
    ir = {"schema_version": 1, "project": {"slug": d.name, "title": title, "created_at": "2026-10-23T00:00:00Z"}, "blueprint": bp,
          "configuration": {"A": "A2", "B": "B7", "C": "C2", "T": "T3", "E": "E1", "F": "测试"},
          "modules": [{"id": "bignum", "role": "evidence", "content": {"title": "收入", "body": "两年收入与增长率"}, "source_refs": ["M001"],
                       "visual_priority": 1, "locked": {"content": True, "layout": False}}],
          "design_intent": {"visual_language": "border-rhythm", "color_role": "spice", "type_ratio": 9}}
    (d / "blueprint.json").write_text(json.dumps(bp, ensure_ascii=False), encoding="utf-8")
    (d / "onepager.ir.json").write_text(json.dumps(ir, ensure_ascii=False), encoding="utf-8")


class OutPosterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.need = [] if runtime.venv_python().is_file() else ["虚拟环境"]
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        cls.task = pathlib.Path(cls.tmp.name) / "task"
        F.make_ledger(cls.task)
        cls.prep = run_poster("prepare", cls.task, "--slug", "xinghe", "--title", "星河数据科技经营概览")
        cls.dir = cls.task / "07_storyline" / "poster-work" / "xinghe"
        write_blueprint_and_ir(cls.dir, "星河数据科技经营概览")
        cls.html = cls.dir / "xinghe-A2-B7-20261023.html"
        shutil.copy2(FIXTURE, cls.html)
        cls.ok = run_poster("finish", cls.task, "--slug", "xinghe", "--html", cls.html,
                            "--A", "A2", "--B", "B7", "--C", "C2", "--T", "T3", "--E", "E1", "--F", "测试")

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

    def test_prepare_writes_only_presentable_facts(self):
        self.assertEqual(self.prep.returncode, 0, self.prep.stdout + self.prep.stderr)
        facts = json.loads((self.dir / "source" / "xinghe-facts.json").read_text(encoding="utf-8"))
        self.assertEqual([c["claim"] for c in facts["claims"]], ["cl-0001", "cl-0003"])
        self.assertEqual([m["display"] for m in facts["claims"][0]["metrics"]], ["1800", "3200", "77.8"])
        self.assertEqual([b["metric"] for b in facts["bignum_candidates"]], ["m-0001", "m-0002", "m-0003"])

    def test_finish_produces_png_and_records_acceptance(self):
        self.assertEqual(self.ok.returncode, 0, self.ok.stdout + self.ok.stderr)
        out = self.task / "08_deliverables" / "poster"
        self.assertTrue((out / "xinghe-A2-B7-20261023.png").is_file())
        size = subprocess.run(["file", str(out / "xinghe-A2-B7-20261023.png")], capture_output=True, text=True).stdout
        self.assertIn("3840 x 2160", size)  # A2 画布 1920×1080，截图默认 2 倍
        e = next(d for d in Acceptance(self.task).load()["deliverables"] if d["id"] == "poster-xinghe")
        self.assertEqual(e["title"], "星河数据科技经营概览")
        self.assertEqual([c["result"] for c in e["upstream_checks"]], ["passed"] * 5)
        self.assertEqual(e["number_trace"]["checked"], 3)
        self.assertEqual(e["status"], "failed")

    def test_untraced_number_blocks_poster(self):
        bad = self.dir / "xinghe-bad.html"
        bad.write_text(FIXTURE.read_text(encoding="utf-8").replace("增长主要来自新客户。", "增长主要来自新客户，某渠道 999 万元。"), encoding="utf-8")
        p = run_poster("finish", self.task, "--slug", "xinghe", "--html", bad,
                       "--A", "A2", "--B", "B7", "--C", "C2", "--T", "T3", "--E", "E1", "--F", "测试")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("[failed] 数字回查", p.stdout)
        self.assertFalse((self.task / "08_deliverables" / "poster" / "xinghe-bad.png").exists())

    def test_engine_check_failure_blocks_poster(self):
        bad = self.dir / "xinghe-emoji.html"
        bad.write_text(FIXTURE.read_text(encoding="utf-8").replace("<h1>", "<h1>🚀"), encoding="utf-8")
        p = run_poster("finish", self.task, "--slug", "xinghe", "--html", bad,
                       "--A", "A2", "--B", "B7", "--C", "C2", "--T", "T3", "--E", "E1", "--F", "测试")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("[failed] quality_check", p.stdout)


if __name__ == "__main__":
    unittest.main()
