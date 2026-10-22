"""out-chart 的端到端测试。需要 LibreOffice、Poppler、Tesseract 和虚拟环境（./install.sh --render-deps）。
缺工具时默认跳过；设置 ALLEN_REQUIRE_TOOLS=1 时缺工具直接失败。证据账为虚构的夹具。"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import out_chart  # noqa: E402,F401  （导入时完成运行时定位）
from tools.acceptance import Acceptance  # noqa: E402
from tools.lib import runtime  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402


def run_out_chart(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "out_chart.py"), *map(str, args)], capture_output=True, text=True)


class OutChartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.need = F.missing_tools("pdftoppm", "tesseract")
        if not runtime.venv_python().is_file():
            cls.need.append("虚拟环境")
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        cls.task = pathlib.Path(cls.tmp.name) / "task"
        F.make_ledger(cls.task)
        charts = F.ensure_dir(cls.task / "07_storyline" / "charts")
        cls.good = charts / "revenue.json"
        cls.good.write_text(json.dumps(F.revenue_chart(), ensure_ascii=False), encoding="utf-8")
        cls.bad = charts / "bridge.json"
        cls.bad.write_text(json.dumps({"id": "bridge", "type": "waterfall", "title": "利润桥", "unit": "万元", "source_ids": ["M001"],
                                       "data": {"items": [{"label": "2024", "value": {"metric": "m-0001"}, "kind": "start"},
                                                          {"label": "增长", "value": {"metric": "m-0001"}},
                                                          {"label": "2025", "value": {"metric": "m-0002"}, "kind": "total"}]}},
                                      ensure_ascii=False), encoding="utf-8")
        cls.raw = charts / "raw.json"
        cls.raw.write_text(json.dumps(F.revenue_chart(data={"categories": ["2025"], "series": [{"name": "收入", "values": [3200]}]}),
                                      ensure_ascii=False), encoding="utf-8")
        cls.ok = run_out_chart(cls.task, cls.good, "--name", "revenue")

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

    def test_renders_three_formats(self):
        self.assertEqual(self.ok.returncode, 0, self.ok.stdout + self.ok.stderr)
        out = self.task / "08_deliverables" / "charts"
        for p in ("revenue.pptx", "revenue.html", "png/revenue.png"):
            self.assertTrue((out / p).is_file(), p)

    def test_chinese_title_is_rendered_in_png(self):
        png = self.task / "08_deliverables" / "charts" / "png" / "revenue.png"
        text = subprocess.run(["tesseract", str(png), "-", "-l", "chi_sim+eng"], capture_output=True, text=True).stdout
        self.assertIn("收入两年增长", text.replace(" ", ""))

    def test_acceptance_needs_review_then_passes_and_detects_tamper(self):
        acc = Acceptance(self.task)
        e = next(d for d in acc.load()["deliverables"] if d["id"] == "chart-revenue")
        self.assertEqual([c["result"] for c in e["upstream_checks"]], ["passed", "passed"])
        self.assertEqual(e["number_trace"], {"checked": 2, "untraced": []})
        self.assertEqual(e["status"], "failed")
        self.assertIn("尚未经过成品审查", e["failures"][0])
        review = {"type": "independent", "reviewer": "成品审查员", "at": "2026-10-23T10:00:00+00:00", "conclusion": "标题与数据一致，中文完整",
                  "issues": []}
        self.assertEqual(acc.review("chart-revenue", review)["status"], "passed")
        html = self.task / "08_deliverables" / "charts" / "revenue.html"
        original = html.read_bytes()
        html.write_bytes(original + b"<!-- edited -->")
        try:
            e = next(d for d in acc.check()["deliverables"] if d["id"] == "chart-revenue")
            self.assertEqual(e["status"], "failed")
        finally:
            html.write_bytes(original)
            acc.check()

    def test_unbalanced_waterfall_is_blocked(self):
        p = run_out_chart(self.task, self.bad, "--name", "bridge")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("[failed] tc_validate", p.stdout)
        self.assertIn("瀑布不平", p.stdout)
        self.assertFalse((self.task / "08_deliverables" / "charts" / "bridge.pptx").exists())

    def test_raw_number_is_blocked_before_engine(self):
        p = run_out_chart(self.task, self.raw, "--name", "raw")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("[failed] 转换（to_thinkcell）", p.stdout)
        self.assertNotIn("tc_validate", p.stdout)


if __name__ == "__main__":
    unittest.main()
