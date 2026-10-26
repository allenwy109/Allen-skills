import json
import pathlib
import unittest

from tools import doctor

RT = pathlib.Path("/rt")
FORGE = RT / "vendor" / "report-forge"
VENV_PY = "/venv/bin/python"
CHROMIUM = "/pw/chromium-1208/chrome"


class FakeEnv:
    """按"命令行包含的子串"返回预设结果的假环境。"""

    def __init__(self):
        self.commands = {"node", "pdfinfo", "pdftotext", "pdftoppm", "pdffonts", "tesseract", "pandoc"}
        self.paths = {VENV_PY, CHROMIUM, doctor.CHROME, doctor.SOFFICE_APP,
                      str(FORGE / "node_modules/playwright"), str(FORGE / ".font-venv/bin/python"),
                      str(RT / ".probe.json"), str(RT / "vendor" / "vendor.lock")}
        self.files = {
            str(RT / ".probe.json"): json.dumps({"verified": True, "commit": "abc"}),
            str(RT / "vendor" / "vendor.lock"): json.dumps({"commit": "abc"}),
        }
        self.rules = [
            ("node --version", (0, "v22.23.1\n")),
            ("import sys, pptx, openpyxl, playwright", (0, "3.11\n")),
            ("executable_path", (0, CHROMIUM + "\n")),
            ("chromium.launch", (0, "Chromium 123\n")),
            ("--dump-dom", (0, "<html></html>")),
            ("tesseract --list-langs", (0, "List of available languages (3):\nchi_sim\neng\nosd\n")),
            ("executablePath", (0, CHROMIUM + "\n")),
            ("require('playwright')", (0, "")),
        ]
        self.free = 36.0
        self.vendor = []
        self.convert = (True, "转换成功")

    def soffice_convert(self, soffice):
        return self.convert

    def which(self, cmd):
        return f"/usr/bin/{cmd}" if cmd in self.commands else None

    def run(self, args, timeout=60, env=None):
        line = " ".join(str(a) for a in args)
        for needle, res in self.rules:
            if needle in line:
                return res
        return 127, "not found"

    def exists(self, path):
        return str(path) in self.paths

    def read(self, path):
        return self.files[str(path)]

    def free_gb(self, path):
        return self.free

    def vendor_errors(self, rt):
        return self.vendor

    def venv_python(self):
        return VENV_PY


def by_name(results):
    return {r["name"]: r for r in results}


class DoctorTest(unittest.TestCase):
    def test_all_good(self):
        results = doctor.run_all(FakeEnv(), RT)
        bad = [r for r in results if r["status"] != doctor.PASS]
        self.assertEqual(bad, [])
        self.assertEqual(doctor.exit_code(results), 0)

    def test_old_node(self):
        e = FakeEnv()
        e.rules.insert(0, ("node --version", (0, "v18.19.0\n")))
        r = by_name(doctor.run_all(e, RT))["Node.js ≥20"]
        self.assertEqual(r["status"], doctor.OLD)
        self.assertEqual(doctor.exit_code(doctor.run_all(e, RT)), 1)

    def test_tesseract_without_chinese(self):
        e = FakeEnv()
        e.rules.insert(0, ("tesseract --list-langs", (0, "List of available languages (1):\neng\n")))
        r = by_name(doctor.run_all(e, RT))["Tesseract（含 chi_sim）"]
        self.assertEqual(r["status"], doctor.MISSING)
        self.assertIn("tesseract-lang", r["fix"])

    def test_missing_chromium_executable(self):
        e = FakeEnv()
        e.paths.discard(CHROMIUM)
        r = by_name(doctor.run_all(e, RT))["Playwright Chromium（海报截图）"]
        self.assertEqual(r["status"], doctor.MISSING)
        self.assertIn("playwright install chromium", r["fix"])

    def test_stale_probe(self):
        e = FakeEnv()
        e.files[str(RT / ".probe.json")] = json.dumps({"verified": True, "commit": "old"})
        r = by_name(doctor.run_all(e, RT))["报告引擎能力探测（看图验证）"]
        self.assertEqual(r["status"], doctor.MISSING)

    def test_low_disk_is_warning_only(self):
        e = FakeEnv()
        e.free = 2.0
        results = doctor.run_all(e, RT)
        self.assertEqual(by_name(results)["磁盘剩余空间"]["status"], doctor.WARN)
        self.assertEqual(doctor.exit_code(results), 0)

    def test_vendor_errors(self):
        e = FakeEnv()
        e.vendor = ["文件被改动：onepager/x"]
        r = by_name(doctor.run_all(e, RT))["vendor 引擎完整性"]
        self.assertEqual(r["status"], doctor.MISSING)
        self.assertIn("文件被改动", r["detail"])

    def test_every_check_reports_its_failure(self):
        """每一项检查都至少有一个失败用例，并且给出修复办法。"""
        venv = "Python 虚拟环境（python-pptx、openpyxl、playwright）"
        probe = "报告引擎能力探测（看图验证）"
        cases = [
            ("node 不存在", lambda e: e.commands.discard("node"), "Node.js ≥20", doctor.MISSING),
            ("虚拟环境不存在", lambda e: e.paths.discard(VENV_PY), venv, doctor.MISSING),
            ("虚拟环境缺包", lambda e: e.rules.insert(0, ("import sys, pptx", (1, "ModuleNotFoundError: pptx"))), venv, doctor.MISSING),
            ("虚拟环境 Python 太旧", lambda e: e.rules.insert(0, ("import sys, pptx", (0, "3.9\n"))), venv, doctor.OLD),
            ("Chrome 启动失败", lambda e: e.rules.insert(0, ("--dump-dom", (1, "crash"))), "Chrome/Chromium 无头启动（报告引擎）", doctor.MISSING),
            ("Chrome 不存在", lambda e: e.paths.discard(doctor.CHROME), "Chrome/Chromium 无头启动（报告引擎）", doctor.MISSING),
            ("缺 pdffonts", lambda e: e.commands.discard("pdffonts"), "Poppler（pdfinfo、pdftotext、pdftoppm、pdffonts）", doctor.MISSING),
            ("缺 tesseract", lambda e: e.commands.discard("tesseract"), "Tesseract（含 chi_sim）", doctor.MISSING),
            ("缺 pandoc", lambda e: e.commands.discard("pandoc"), "Pandoc", doctor.MISSING),
            ("缺 LibreOffice", lambda e: e.paths.discard(doctor.SOFFICE_APP), "LibreOffice（能转换文件并渲染中文）", doctor.MISSING),
            ("LibreOffice 转换失败或中文丢失", lambda e: setattr(e, "convert", (False, "PDF 里没有用上中文字体")), "LibreOffice（能转换文件并渲染中文）", doctor.MISSING),
            ("缺 npm 依赖", lambda e: e.paths.discard(str(FORGE / "node_modules/playwright")), "报告引擎 npm 依赖与字体环境", doctor.MISSING),
            ("缺探测记录", lambda e: e.paths.discard(str(RT / ".probe.json")), probe, doctor.MISSING),
            ("探测未通过", lambda e: e.files.__setitem__(str(RT / ".probe.json"), json.dumps({"verified": False, "commit": "abc"})), probe, doctor.MISSING),
            ("探测记录损坏", lambda e: e.files.__setitem__(str(RT / ".probe.json"), "{"), probe, doctor.MISSING),
            ("NODE_PATH 下没有 playwright", lambda e: e.rules.insert(0, ("require('playwright')", (1, "Cannot find module"))), "thinkcell 浏览器测试前提（NODE_PATH 与 TC_BROWSER_PATH）", doctor.MISSING),
        ]
        for label, mutate, name, status in cases:
            with self.subTest(label):
                e = FakeEnv()
                mutate(e)
                r = by_name(doctor.run_all(e, RT))[name]
                self.assertEqual(r["status"], status)
                self.assertTrue(r["fix"])

    def test_real_soffice_convert_with_missing_binary(self):
        ok, detail = doctor.Env().soffice_convert("/nonexistent/soffice")
        self.assertFalse(ok)
        self.assertTrue(detail)


if __name__ == "__main__":
    unittest.main()
