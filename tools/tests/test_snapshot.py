import pathlib
import tempfile
import unittest

from tools.lib import office, snapshot


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / "raw" / "sources" / "U001-bp.md"

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_keeps_values_and_field_order(self):
        meta = {"id": "U001", "title": "星河 \"BP\": 第一版", "url": "file:bp.pdf", "accessed": "2026-10-22T10:00:00+00:00",
                "capture_method": "user_file", "access": "full", "original_files": [{"path": "raw/user/U001-bp/original.pdf", "sha256": "a" * 64}],
                "subquestions": ["市场"]}
        snapshot.write(self.path, meta, "<!-- p.1 -->\n正文\n")
        got, body = snapshot.read(self.path)
        self.assertEqual(body, "<!-- p.1 -->\n正文\n")
        for k, v in meta.items():
            self.assertEqual(got[k], v)
        self.assertIsNone(got["final_url"])
        header_keys = [line.split(":")[0] for line in self.path.read_text(encoding="utf-8").split("---")[1].strip().splitlines()]
        self.assertEqual(header_keys, snapshot.fields())

    def test_refuses_to_overwrite(self):
        snapshot.write(self.path, {"id": "U001"}, "x\n")
        with self.assertRaises(snapshot.SnapshotError):
            snapshot.write(self.path, {"id": "U001"}, "y\n")
        self.assertEqual(snapshot.read(self.path)[1], "x\n")

    def test_rejects_unknown_fields_and_missing_id(self):
        with self.assertRaises(snapshot.SnapshotError):
            snapshot.write(self.path, {"id": "U001", "grade": "C"}, "x")
        with self.assertRaises(snapshot.SnapshotError):
            snapshot.write(self.path, {"title": "x"}, "x")

    def test_empty_body_gets_placeholder(self):
        snapshot.write(self.path, {"id": "U001"}, "  \n")
        self.assertEqual(snapshot.read(self.path)[1], snapshot.EMPTY_BODY)

    def test_read_errors(self):
        self.path.parent.mkdir(parents=True)
        for text, msg in [("no header", "缺少元数据头"), ("---\nid: \"U001\"\n", "没有结束标记"),
                          ("---\nid \"U001\"\n---\n", "无法识别"), ("---\nid: U001\n---\n", "不是合法 JSON"),
                          ("---\nid: \"a\"\nid: \"b\"\n---\n", "重复的键")]:
            with self.subTest(msg):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaises(snapshot.SnapshotError) as cm:
                    snapshot.read(self.path)
                self.assertIn(msg, str(cm.exception))


class OfficeHelpersTest(unittest.TestCase):
    def test_cjk_font_picks_first_existing(self):
        with tempfile.TemporaryDirectory() as t:
            second = pathlib.Path(t) / "b.ttc"
            second.write_bytes(b"x")
            self.assertEqual(office.cjk_font({str(pathlib.Path(t) / "a.ttc"): "A", str(second): "B"}), (str(second), "B"))
            self.assertEqual(office.cjk_font({str(pathlib.Path(t) / "none.ttc"): "N"}), (None, None))


if __name__ == "__main__":
    unittest.main()
