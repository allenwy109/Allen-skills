"""core-intake 的测试。

端到端测试需要 pandoc、LibreOffice、Poppler、Tesseract。缺工具时默认跳过（例如 CI 的 Ubuntu）；
设置 ALLEN_REQUIRE_TOOLS=1 时缺工具直接算失败（本机完整自检会这样设置，不允许空过）。
测试材料全部现场生成，内容虚构。
"""
import hashlib
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
import intake  # noqa: E402
from tools.lib import office, snapshot  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

BP_MD = """# 星河数据科技 商业计划书

## 公司概况

星河数据科技成立于 2021 年，2025 年营业收入 3200 万元。

| 指标 | 2024 | 2025 |
|---|---|---|
| 收入（万元） | 1800 | 3200 |
| 客户数 | 45 | 80 |

## 市场

目标市场规模 500 亿元，年增长 30%。

::: notes
这里强调增长来自制造业客户。
:::
"""


def missing_tools():
    need = [t for t in ("pandoc", "pdfinfo", "pdftotext", "pdftoppm", "tesseract") if not shutil.which(t)]
    try:
        office.soffice_path()
    except office.OfficeError:
        need.append("soffice")
    return need


def require_tools(test_case):
    need = missing_tools()
    if need:
        msg = f"缺少工具：{', '.join(need)}"
        if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
            test_case.fail(msg)
        test_case.skipTest(msg)


def run_intake(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "intake.py"), *map(str, args)], capture_output=True, text=True)


class HelperTest(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(intake.slugify("Star BP v2"), "star-bp-v2")
        self.assertEqual(intake.slugify("星河商业计划书"), "file")
        self.assertEqual(len(intake.slugify("a" * 80)), 40)

    def test_md_table_pads_and_escapes(self):
        self.assertEqual(intake.md_table([["a", "b|c"], ["1"]]), "| a | b\\|c |\n|---|---|\n| 1 |  |")
        self.assertEqual(intake.md_table([]), "")

    def test_next_user_id_without_ledger(self):
        with tempfile.TemporaryDirectory() as t:
            task = pathlib.Path(t)
            (task / "03_evidence" / "raw" / "user" / "U001-a").mkdir(parents=True)
            (task / "03_evidence" / "raw" / "user" / "U007-b").mkdir()
            self.assertEqual(intake.next_user_id(task, use_ledger=False), "U008")

    def test_unsupported_and_missing_files_are_not_registered(self):
        with tempfile.TemporaryDirectory() as t:
            task = pathlib.Path(t) / "task"
            note = pathlib.Path(t) / "note.txt"
            note.write_text("x", encoding="utf-8")
            p = run_intake(note, pathlib.Path(t) / "nope.pdf", "--task", task)
            self.assertEqual(p.returncode, 2)
            out = json.loads(p.stdout)
            self.assertEqual(out["failed"], 2)
            self.assertIn("不支持的格式：.txt", out["files"][0]["error"])
            self.assertEqual(out["files"][1]["error"], "文件不存在")
            self.assertFalse((task / "03_evidence" / "raw" / "user").exists())

    def test_bad_arguments(self):
        self.assertEqual(run_intake("x.pdf").returncode, 3)


class EndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.need = missing_tools()
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(cls.tmp.name)
        src = base / "src"
        src.mkdir()
        md = src / "bp.md"
        md.write_text(BP_MD, encoding="utf-8")
        subprocess.run(["pandoc", str(md), "-o", str(src / "Star-BP.docx")], check=True)
        subprocess.run(["pandoc", str(md), "-o", str(src / "Star-Deck.pptx")], check=True)
        text_pdf = office.convert(src / "Star-BP.docx", "pdf", src / "pdf")
        cls.text_pdf = text_pdf.rename(src / "Star-Text.pdf")
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-f", "1", "-l", "1", "-singlefile", str(cls.text_pdf), str(src / "scan")], check=True)
        cls.scan_pdf = office.convert(src / "scan.png", "pdf", src / "scanpdf").rename(src / "Star-Scan.pdf")
        img_md = src / "img.md"
        img_md.write_text(f"# 第一页\n\n文字页\n\n---\n\n![]({src / 'scan.png'})\n", encoding="utf-8")
        subprocess.run(["pandoc", str(img_md), "-o", str(src / "Star-Image.pptx")], check=True)
        enc = 'pdf:writer_pdf_Export:{"EncryptFile":{"type":"boolean","value":"true"},"DocumentOpenPassword":{"type":"string","value":"x"}}'
        cls.enc_pdf = office.convert(src / "Star-BP.docx", enc, src / "enc").rename(src / "Star-Locked.pdf")
        cls.legacy = office.convert(src / "Star-BP.docx", "doc", src / "legacy")
        cls.corrupt = src / "Star-Broken.pdf"
        cls.corrupt.write_bytes(b"not a pdf at all")
        cls.task = base / "task"
        cls.files = [src / "Star-Text.pdf", cls.scan_pdf, src / "Star-BP.docx", src / "Star-Deck.pptx", src / "Star-Image.pptx",
                     cls.enc_pdf, cls.corrupt, cls.legacy]
        cls.proc = run_intake(*cls.files, "--task", cls.task)
        cls.out = json.loads(cls.proc.stdout)
        cls.by_name = {pathlib.Path(f["file"]).name: f for f in cls.out["files"]}
        cls.ev = cls.task / "03_evidence"

    @classmethod
    def tearDownClass(cls):
        if not cls.need:
            cls.tmp.cleanup()

    def setUp(self):
        require_tools(self)

    def result(self, name):
        return self.by_name[name]

    def user_dir(self, name):
        return next((self.ev / "raw" / "user").glob(f"{self.result(name)['source_id']}-*"))

    def text(self, name):
        return (self.user_dir(name) / "text.md").read_text(encoding="utf-8")

    def test_summary_and_exit_code(self):
        self.assertEqual(self.proc.returncode, 2, self.proc.stderr)
        self.assertEqual(self.out["failed"], 2)
        self.assertEqual([f["source_id"] for f in self.out["files"]], [f"U00{i}" for i in range(1, 9)])

    def test_text_pdf(self):
        r = self.result("Star-Text.pdf")
        self.assertEqual((r["status"], r["access"]), ("ok", "full"))
        t = self.text("Star-Text.pdf")
        self.assertTrue(t.startswith("<!-- p.1 -->\n"))
        self.assertIn("2025 年营业收入 3200 万元", t)
        self.assertTrue((self.user_dir("Star-Text.pdf") / "pages" / "p001.png").is_file())
        self.assertIn("可能错位", "；".join(r["flags"]))

    def test_scanned_pdf_is_ocrd(self):
        self.assertEqual(intake.chars(subprocess.run(["pdftotext", str(self.scan_pdf), "-"], capture_output=True, text=True).stdout), 0)
        r = self.result("Star-Scan.pdf")
        self.assertEqual(r["access"], "full")
        self.assertIn("扫描件已识别（OCR 页：1）", r["flags"])
        t = self.text("Star-Scan.pdf")
        self.assertIn("3200", t)
        self.assertIn("营业收入", t)
        meta = json.loads((self.user_dir("Star-Scan.pdf") / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["extraction"]["ocr_pages"], [1])
        self.assertEqual(meta["extraction"]["text"], "ocr+pdftotext")

    def test_docx_tables_and_rendering(self):
        d = self.user_dir("Star-BP.docx")
        rows = (d / "tables" / "table-1.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(rows[1], "收入（万元）,1800,3200")
        self.assertTrue((d / "rendered.pdf").is_file())
        self.assertIn("<!-- p.1 -->", self.text("Star-BP.docx"))

    def test_cjk_is_rendered_in_page_images_source(self):
        fonts = subprocess.run(["pdffonts", str(self.user_dir("Star-BP.docx") / "rendered.pdf")], capture_output=True, text=True).stdout
        _, expected = office.cjk_font()
        self.assertIn(expected, fonts)

    def test_pptx_slides_notes_tables(self):
        r = self.result("Star-Deck.pptx")
        self.assertEqual((r["status"], r["access"], r["flags"]), ("ok", "full", []))
        t = self.text("Star-Deck.pptx")
        self.assertIn("<!-- p.3 -->\n## 第 3 张", t)
        self.assertIn("### 演讲者备注\n\n这里强调增长来自制造业客户。", t)
        self.assertIn("| 收入（万元） | 1800 | 3200 |", t)
        self.assertEqual(len(list((self.user_dir("Star-Deck.pptx") / "pages").glob("p*.png"))), 3)
        self.assertTrue((self.user_dir("Star-Deck.pptx") / "tables" / "table-1.csv").is_file())

    def test_image_only_slide_is_ocrd(self):
        r = self.result("Star-Image.pptx")
        self.assertIn("图片页已识别（OCR 页：2）", r["flags"])
        self.assertIn("营业收入", self.text("Star-Image.pptx").split("<!-- p.2 -->")[1])

    def test_encrypted_and_corrupt_are_registered_as_unreadable(self):
        for name in ("Star-Locked.pdf", "Star-Broken.pdf"):
            with self.subTest(name):
                r = self.result(name)
                self.assertEqual((r["status"], r["access"]), ("failed", "unreadable"))
                self.assertEqual(self.text(name), "")
                self.assertEqual(Ledger(self.task).get("sources", r["source_id"])["access"], "unreadable")
        self.assertIn("已加密", self.result("Star-Locked.pdf")["error"])

    def test_legacy_doc_is_converted(self):
        r = self.result(self.legacy.name)
        self.assertEqual(r["status"], "ok")
        self.assertIn("老格式已转为 .docx", r["flags"])
        self.assertTrue((self.user_dir(self.legacy.name) / "converted.docx").is_file())

    def test_ledger_and_snapshot_agree(self):
        led = Ledger(self.task)
        issues = led.check()
        self.assertEqual([i for i in issues if i["level"] == "error"], [])
        for f in self.out["files"]:
            src = led.get("sources", f["source_id"])
            self.assertEqual((src["origin"], src["capture_method"], src["research_line"], src["grade"]), ("user", "user_file", "U", "C"))
            meta, body = snapshot.read(self.ev / src["snapshot"])
            for k in snapshot.fields():
                if meta.get(k) not in (None, []):
                    self.assertEqual(src.get(k), meta[k], k)
            d = next((self.ev / "raw" / "user").glob(f"{f['source_id']}-*"))
            if f["status"] == "ok":
                self.assertEqual(body, (d / "text.md").read_text(encoding="utf-8"))
            on_disk = {p.relative_to(self.ev).as_posix() for p in d.rglob("*") if p.is_file()}
            self.assertEqual({o["path"] for o in src["original_files"]}, on_disk)
            for o in src["original_files"]:
                self.assertEqual(o["sha256"], hashlib.sha256((self.ev / o["path"]).read_bytes()).hexdigest())

    def test_no_ledger_mode(self):
        task = pathlib.Path(self.tmp.name) / "l1"
        p = run_intake(self.text_pdf, "--task", task, "--no-ledger")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue((task / "03_evidence" / "raw" / "user" / "U001-star-text" / "text.md").is_file())
        self.assertFalse((task / "03_evidence" / "ledger").exists())


if __name__ == "__main__":
    unittest.main()
