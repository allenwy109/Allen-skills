import tempfile
import unittest

from tools.bridge import to_thinkcell as T
from tools.tests import fixtures as F


class BuildTest(unittest.TestCase):
    """正向用例和反向用例（必须拦截的情况，设计 §11）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = self.tmp.name
        F.make_ledger(self.task)

    def tearDown(self):
        self.tmp.cleanup()

    def problems(self, chart):
        with self.assertRaises(T.BridgeError) as cm:
            T.build(self.task, chart)
        return "\n".join(cm.exception.problems)

    def test_resolves_metrics_and_sources(self):
        spec, trace = T.build(self.task, F.revenue_chart())
        self.assertEqual(spec["data"]["series"][0]["values"], [1800.0, 3200.0])
        self.assertEqual(spec["source"], "星河数据科技 2025 年年报（M001）")
        self.assertNotIn("source_ids", spec)
        self.assertEqual(trace, {"checked": 2, "untraced": []})

    def test_formula_metric_is_rounded_like_report_engine(self):
        chart = F.revenue_chart(type="bar", data={"categories": ["增长率"], "series": [{"name": "增长", "values": [{"metric": "m-0003"}]}]})
        spec, _ = T.build(self.task, chart)
        self.assertEqual(spec["data"]["series"][0]["values"], [77.8])

    def test_layout_numbers_are_allowed(self):
        chart = F.revenue_chart()
        chart["data"]["axis_break"] = {"from": 100, "to": 1000}
        chart["callouts"] = [{"text": "新客户", "category": "2025", "dx": 0, "dy": 2}]
        spec, trace = T.build(self.task, chart)
        self.assertEqual(spec["data"]["axis_break"], {"from": 100, "to": 1000})
        self.assertEqual(trace["untraced"], [])

    def test_forecast_and_approximate_get_footnote(self):
        chart = F.revenue_chart(footnote="四舍五入")
        chart["data"]["categories"].append("2026E")
        chart["data"]["series"][0]["values"].append({"metric": "m-0007"})
        spec, _ = T.build(self.task, chart)
        self.assertEqual(spec["footnote"], "四舍五入；部分数值为近似值；含预测数值，不是实际数据")

    def test_rejections(self):
        cases = {
            "裸数字 3200 追溯不到证据账": F.revenue_chart(data={"categories": ["2025"], "series": [{"name": "收入", "values": [3200]}]}),
            "状态是 missing": F.revenue_chart(data={"categories": ["x"], "series": [{"name": "s", "values": [{"metric": "m-0004"}]}]}),
            "都不能以事实呈现（cl-0002=unverified）": F.revenue_chart(data={"categories": ["x"], "series": [{"name": "s", "values": [{"metric": "m-0005"}]}]}),
            "没有被任何主张引用": F.revenue_chart(data={"categories": ["x"], "series": [{"name": "s", "values": [{"metric": "m-0006"}]}]}),
            "指标 m-9999 不存在": F.revenue_chart(data={"categories": ["x"], "series": [{"name": "s", "values": [{"metric": "m-9999"}]}]}),
            "不存在的来源：M009": F.revenue_chart(source_ids=["M009"]),
            "缺少 source_ids": F.revenue_chart(source_ids=[]),
            "不要直接写 source": F.revenue_chart(source="手写来源"),
            "缺少 title": F.revenue_chart(title=""),
        }
        for msg, chart in cases.items():
            with self.subTest(msg):
                self.assertIn(msg, self.problems(chart))

    def test_value_line_decoration_must_use_metric(self):
        chart = F.revenue_chart(decorations=[{"type": "value_line", "value": 2500, "label": "目标"}])
        self.assertIn("decorations[0].value：裸数字 2500", self.problems(chart))
        chart["decorations"][0]["value"] = {"metric": "m-0002"}
        spec, _ = T.build(self.task, chart)
        self.assertEqual(spec["decorations"][0]["value"], 3200.0)


if __name__ == "__main__":
    unittest.main()
