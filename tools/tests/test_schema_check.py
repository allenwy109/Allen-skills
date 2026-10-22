import unittest

from tools.lib import schema_check as sc

MINI = {
    "version": "t",
    "enums": {"color": {"values": ["red", "blue"], "labels": {"red": "红", "blue": "蓝"}}},
    "tables": {
        "things": {
            "file": "things.jsonl", "id_pattern": "^T-[0-9]{4,}$", "upstream": "test", "changes": [],
            "fields": {
                "id": {"type": "string", "required": True},
                "name": {"type": "string", "required": True},
                "color": {"type": "string", "enum": "color"},
                "count": {"type": "integer", "min": 0, "max": 10},
                "ratio": {"type": "number"},
                "flag": {"type": "boolean"},
                "day": {"type": "date"},
                "at": {"type": "datetime"},
                "tags": {"type": "array", "items": {"type": "string"}, "min_items": 1},
                "box": {"type": "object", "fields": {"w": {"type": "number", "required": True}}},
                "scores": {"type": "map", "key_pattern": "^[a-z]+$", "values": {"type": "integer"}},
                "other": {"type": "string", "ref": "things"},
            },
            "require_if": [{"if": {"field": "flag", "equals": True}, "then": ["ratio"], "message": "flag 时要 ratio"}],
        }
    },
}


def errs(record):
    return sc.check_record(MINI, "things", record)


class CheckRecordTest(unittest.TestCase):
    def test_valid_record(self):
        self.assertEqual(errs({"id": "T-0001", "name": "a", "color": "red", "count": 3, "ratio": 0.5, "flag": False,
                               "day": "2026-10", "at": "2026-10-22T10:00:00+08:00", "tags": ["x"],
                               "box": {"w": 1}, "scores": {"a": 1}, "other": "T-0002"}), [])

    def test_required_and_blank(self):
        self.assertIn("things:T-0001.name：必填", errs({"id": "T-0001"}))
        self.assertIn("things:T-0001.name：必填，不能为空白", errs({"id": "T-0001", "name": "  "}))

    def test_unknown_field_and_bad_id(self):
        e = "\n".join(errs({"id": "X1", "name": "a", "zzz": 1}))
        self.assertIn("zzz：未登记的字段", e)
        self.assertIn("id 格式不符", e)

    def test_enum(self):
        self.assertIn("不在 color 枚举中", "\n".join(errs({"id": "T-0001", "name": "a", "color": "green"})))

    def test_numbers(self):
        e = "\n".join(errs({"id": "T-0001", "name": "a", "count": True}) + errs({"id": "T-0001", "name": "a", "count": 2.5})
                      + errs({"id": "T-0001", "name": "a", "count": 11}) + errs({"id": "T-0001", "name": "a", "ratio": float("nan")}))
        self.assertIn("应为数值", e)
        self.assertIn("应为整数", e)
        self.assertIn("不能大于 10", e)
        self.assertIn("不能是 NaN", e)

    def test_dates(self):
        self.assertEqual(errs({"id": "T-0001", "name": "a", "day": "2026"}), [])
        self.assertTrue(errs({"id": "T-0001", "name": "a", "day": "2026-13"}))
        self.assertTrue(errs({"id": "T-0001", "name": "a", "day": "26-01-01"}))
        self.assertTrue(errs({"id": "T-0001", "name": "a", "at": "2026-10-22T10:00:00"}))
        self.assertEqual(errs({"id": "T-0001", "name": "a", "at": "2026-10-22T10:00:00Z"}), [])

    def test_array_object_map(self):
        e = "\n".join(errs({"id": "T-0001", "name": "a", "tags": [], "box": {"h": 1}, "scores": {"A": "x"}}))
        self.assertIn("至少需要 1 项", e)
        self.assertIn("box.h：未登记的字段", e)
        self.assertIn("box.w：必填", e)
        self.assertIn("键名格式不符", e)
        self.assertIn("scores.A：应为数值", e)

    def test_require_if(self):
        self.assertIn("flag 时要 ratio", "\n".join(errs({"id": "T-0001", "name": "a", "flag": True})))

    def test_null_equals_missing(self):
        self.assertEqual(errs({"id": "T-0001", "name": "a", "color": None}), [])


class SelfCheckTest(unittest.TestCase):
    def test_mini_schema_is_clean(self):
        self.assertEqual(sc.self_check(MINI), [])

    def test_detects_bad_enum_ref_type_and_labels(self):
        bad = {"enums": {"e": {"values": ["a"], "labels": {}}},
               "tables": {"t": {"file": "t.jsonl", "id_pattern": "^t$", "upstream": "", "changes": [],
                                "fields": {"id": {"type": "string"}, "x": {"type": "string", "enum": "nope"},
                                           "y": {"type": "string", "ref": "missing"}, "z": {"type": "weird"}},
                                "require_if": [{"if": {"field": "q", "equals": 1}, "then": ["x"], "message": ""}]}}}
        e = "\n".join(sc.self_check(bad))
        self.assertIn("缺少中文名", e)
        self.assertIn("不存在的枚举 nope", e)
        self.assertIn("不存在的表 missing", e)
        self.assertIn("未知类型", e)
        self.assertIn("不存在的字段 q", e)

    def test_repository_schemas_are_clean(self):
        for name in ("ledger.schema.json", "slides.schema.json", "sidecar.schema.json"):
            with self.subTest(name):
                self.assertEqual(sc.self_check(sc.load(name)), [])


if __name__ == "__main__":
    unittest.main()
