import tempfile
import unittest

from tools.bridge import poster_numbers as P
from tools.tests import fixtures as F


def page(body):
    return f"<html><head><style>.x{{width:1920px}}</style><script>var n = 12345;</script></head><body>{body}</body></html>"


class PosterNumbersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        F.make_ledger(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, body, allow=()):
        return P.check(self.tmp.name, page(body), allow)

    def test_traced_numbers_years_ids_and_commas(self):
        r = self.check('<p>2024 年 1,800 万元，2025 年 3200 万元，增长 77.8%。来源 M001，主张 cl-0001。</p><!-- 999 -->')
        self.assertEqual(r["untraced"], [])
        self.assertEqual(r["checked"], 3)
        self.assertEqual(r["years"], ["2024", "2025"])

    def test_untraced_and_not_presentable_numbers(self):
        r = self.check("<p>某渠道 999 万元，另有 1234 个客户</p>")
        self.assertEqual(len(r["untraced"]), 2)
        self.assertIn("999", r["untraced"][0])

    def test_allow_list(self):
        self.assertEqual(self.check("<p>分 3 个阶段推进</p>", allow=["3"])["untraced"], [])
        self.assertEqual(len(self.check("<p>分 3 个阶段推进</p>")["untraced"]), 1)

    def test_forecast_needs_identity_label(self):
        self.assertIn("注明身份", self.check("<p>明年收入 4100 万元</p>")["untraced"][0])
        self.assertEqual(self.check("<p>明年收入预测 4100 万元</p>")["untraced"], [])

    def test_bignum_only_verified_or_single_source(self):
        ok = '<div class="bignum-item"><div class="bignum-value">3200</div><p class="bignum-label">2025 年收入（万元）</p></div>'
        self.assertEqual(self.check(ok)["untraced"], [])
        bad = '<div class="bignum-item"><div class="bignum-value">2025</div></div>'
        self.assertIn("不是任何能进成品的指标", self.check(bad)["untraced"][0])

    def test_report_mode_checks_only_unbound_body_text(self):
        body = ('<section data-page-role="cover"><p>2026-10-23 · v1</p></section>'
                '<section data-page-id="p02"><h1 data-content-key="title">增长 999%</h1>'
                '<svg><text>2024</text><text data-content-key="metric:m-0001">1800 万元</text></svg>'
                '<p>手写说明：毛利 555 万元</p></section>')
        r = P.check(self.tmp.name, page(body), report=True)
        self.assertEqual(r["checked"], 1)                       # 只有手写说明里的 555；年份不计数
        self.assertEqual(len(r["untraced"]), 1)
        self.assertIn("555", r["untraced"][0])


if __name__ == "__main__":
    unittest.main()
