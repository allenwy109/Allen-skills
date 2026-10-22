import unittest

from tools.lib import metrics as M


def mets(*records):
    return {r["id"]: r for r in records}


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        self.m = mets({"id": "a", "status": "present", "value": 120}, {"id": "b", "status": "present", "value": 100},
                      {"id": "z", "status": "present", "value": 0}, {"id": "n", "status": "present", "value": -10})

    def calc(self, op, *args):
        self.m["f"] = {"id": "f", "status": "present", "formula": {"op": op, "args": list(args)}}
        return M.evaluate(self.m, "f")

    def test_ops_match_report_engine(self):
        self.assertEqual(self.calc("sum", "a", "b", "a"), 340)
        self.assertEqual(self.calc("multiply", "a", "b"), 12000)
        self.assertEqual(self.calc("subtract", "a", "b"), 20)
        self.assertEqual(self.calc("divide", "a", "b"), 1.2)
        self.assertAlmostEqual(self.calc("percent_change", "a", "b"), 20.0)
        self.assertAlmostEqual(self.calc("share", "b", "a"), 100 / 120 * 100)

    def test_errors(self):
        for op, args, msg in [("divide", ("a", "z"), "零除"), ("percent_change", ("a", "n"), "基期须为正数"), ("bogus", ("a", "b"), "未知运算")]:
            with self.subTest(op):
                with self.assertRaises(M.MetricError) as cm:
                    self.calc(op, *args)
                self.assertIn(msg, str(cm.exception))
        self.m["miss"] = {"id": "miss", "status": "missing"}
        with self.assertRaises(M.MetricError):
            self.calc("sum", "a", "miss")
        self.m["c1"] = {"id": "c1", "status": "present", "formula": {"op": "sum", "args": ["c2"]}}
        self.m["c2"] = {"id": "c2", "status": "present", "formula": {"op": "sum", "args": ["c1"]}}
        with self.assertRaises(M.MetricError):
            M.evaluate(self.m, "c1")
        with self.assertRaises(M.MetricError):
            M.evaluate(self.m, "nope")

    def test_display_half_expand(self):
        self.assertEqual(M.display(0.725, 2), "0.73")
        self.assertEqual(M.display(2.175, 2), "2.18")
        self.assertEqual(M.display(-0.725, 2), "-0.73")
        self.assertEqual(M.display(-0.0001, 2), "0.00")
        self.assertEqual(M.display(77.77777, 1), "77.8")
        self.assertEqual(M.display(3200.0, 0), "3200")


class PresentableTest(unittest.TestCase):
    def test_rules(self):
        m = mets({"id": "ok", "status": "present", "value": 1}, {"id": "miss", "status": "missing"},
                 {"id": "orphan", "status": "present", "value": 1}, {"id": "weak", "status": "present", "value": 1},
                 {"id": "fight", "status": "present", "value": 1})
        claims = [{"id": "c1", "verification": "verified", "metric_refs": ["ok", "miss"]},
                  {"id": "c2", "verification": "unverified", "metric_refs": ["weak"]},
                  {"id": "c3", "verification": "conflicting", "metric_refs": ["fight"]}]
        by = M.claims_by_metric(claims)
        self.assertEqual(M.check_presentable("ok", m, by, set()), [])
        self.assertIn("状态是 missing", M.check_presentable("miss", m, by, set())[0])
        self.assertIn("无法追溯", M.check_presentable("orphan", m, by, set())[0])
        self.assertIn("c2=unverified", M.check_presentable("weak", m, by, set())[0])
        self.assertTrue(M.check_presentable("fight", m, by, set()))
        resolved = M.resolved_conflict_claims([{"status": "resolved", "claim_ids": ["c3"]}, {"status": "open", "claim_ids": ["c2"]}])
        self.assertEqual(resolved, {"c3"})
        self.assertEqual(M.check_presentable("fight", m, by, resolved), [])
        self.assertIn("不存在", M.check_presentable("ghost", m, by, set())[0])


if __name__ == "__main__":
    unittest.main()
