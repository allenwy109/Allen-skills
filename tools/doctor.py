#!/usr/bin/env python3
"""检查出成品所需的本机环境（设计 §9）。

用法：python3 tools/doctor.py [--json]
每项给出：通过 / 缺失 / 版本不足 / 警告，以及修复办法。
有任何一项是"缺失"或"版本不足"时，以状态 1 退出；"警告"不影响退出状态。
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import vendor_sync  # noqa: E402
from tools.lib import office, runtime  # noqa: E402

CHROME = runtime.CHROME
SOFFICE_APP = runtime.SOFFICE_APP
MIN_FREE_GB = 5
PASS, MISSING, OLD, WARN = "通过", "缺失", "版本不足", "警告"
RENDER_FIX = "./install.sh --render-deps"


class Env:
    """真实环境；测试时用假对象代替。"""

    def which(self, cmd):
        return shutil.which(cmd)

    def run(self, args, timeout=60, env=None):
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
            return p.returncode, (p.stdout or "") + (p.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as e:
            return 127, str(e)

    def exists(self, path):
        return pathlib.Path(path).exists()

    def read(self, path):
        return pathlib.Path(path).read_text(encoding="utf-8")

    def free_gb(self, path):
        return shutil.disk_usage(path).free / 1e9

    def vendor_errors(self, rt):
        return vendor_sync.check(pathlib.Path(rt) / "vendor")

    def venv_python(self):
        return str(runtime.venv_python())

    def soffice_convert(self, soffice):
        """用 LibreOffice 把一段中文转成 PDF，并确认 PDF 里用上了中文字体。返回 (是否通过, 说明)。"""
        font, expected = office.cjk_font()
        if not font:
            return False, "找不到系统中文字体（冬青黑体、华文黑体或 Noto Sans CJK），中文会渲染不出来"
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "t.txt"
            src.write_text("星河数据科技 2025 年营业收入 3200 万元\n", encoding="utf-8")
            try:
                pdf = office.convert(src, "pdf", tmp, timeout=180, soffice=soffice)
            except office.OfficeError as err:
                return False, str(err)
            _, out = self.run(["pdffonts", str(pdf)])
            if expected not in out:
                return False, f"转换成功，但 PDF 里没有用上中文字体 {expected}，中文会丢失"
            return True, f"转换成功，中文字体：{expected}"

def version(text):
    m = re.search(r"(\d+)\.(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def result(name, status, detail, fix=""):
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def check_node(e, rt):
    name = "Node.js ≥20"
    if not e.which("node"):
        return result(name, MISSING, "找不到 node", "安装 Node.js 20 或更高版本（例如 fnm install 22）")
    _, out = e.run(["node", "--version"])
    v = version(out)
    if not v or v < (20, 0):
        return result(name, OLD, out.strip(), "升级到 Node.js 20 或更高版本")
    return result(name, PASS, out.strip())


def check_venv(e, rt):
    name = "Python 虚拟环境（python-pptx、openpyxl、playwright）"
    py = e.venv_python()
    if not e.exists(py):
        return result(name, MISSING, f"{py} 不存在", RENDER_FIX)
    code, out = e.run([py, "-c", "import sys, pptx, openpyxl, playwright; print('%d.%d' % sys.version_info[:2])"])
    if code != 0:
        return result(name, MISSING, out.strip()[-200:], RENDER_FIX)
    v = version(out)
    if not v or v < (3, 10):
        return result(name, OLD, out.strip(), f"删除 {pathlib.Path(py).parent.parent} 后重新运行 {RENDER_FIX}")
    return result(name, PASS, f"Python {out.strip()}")


def check_playwright_chromium(e, rt):
    name = "Playwright Chromium（海报截图）"
    py = e.venv_python()
    if not e.exists(py):
        return result(name, MISSING, "虚拟环境不存在", RENDER_FIX)
    code, out = e.run([py, "-c", "from playwright.sync_api import sync_playwright\nwith sync_playwright() as p: print(p.chromium.executable_path)"])
    path = out.strip().splitlines()[-1] if out.strip() else ""
    if code != 0 or not path or not e.exists(path):
        return result(name, MISSING, path or out.strip()[-200:], f"{py} -m playwright install chromium")
    return result(name, PASS, path)


def check_chrome(e, rt):
    name = "Chrome/Chromium 无头启动（报告引擎）"
    if not e.exists(CHROME):
        return result(name, MISSING, CHROME, "安装 Google Chrome 或 Chromium，或设置 ALLEN_CHROME")
    if runtime.chrome_channel() == "chromium":
        node_modules = runtime.engine_path(rt, "report-forge") / "node_modules"
        if not e.exists(str(node_modules / "playwright")):
            return result(name, MISSING, "Chromium 环境需要报告引擎的 Playwright", f"cd {node_modules.parent} && npm ci && npx playwright install chromium")
        script = ("const {chromium}=require('playwright');"
                  "(async()=>{const b=await chromium.launch({channel:'chromium',headless:true});"
                  "console.log(b.version());await b.close()})().catch(e=>{console.error(e);process.exit(1)})")
        code, out = e.run(["node", "-e", script], timeout=60, env=dict(os.environ, NODE_PATH=str(node_modules)))
    else:
        code, out = e.run([CHROME, "--headless=new", "--disable-gpu", "--dump-dom", "about:blank"], timeout=60)
    if code != 0:
        return result(name, MISSING, out.strip()[-200:], "确认 Chrome/Chromium 能无头启动，必要时设置 ALLEN_CHROME")
    return result(name, PASS, f"{CHROME}（{runtime.chrome_channel()}）")


def check_poppler(e, rt):
    name = "Poppler（pdfinfo、pdftotext、pdftoppm、pdffonts）"
    missing = [c for c in ("pdfinfo", "pdftotext", "pdftoppm", "pdffonts") if not e.which(c)]
    if missing:
        return result(name, MISSING, "缺 " + "、".join(missing), "brew install poppler")
    return result(name, PASS, "四个命令都在")


def check_tesseract(e, rt):
    name = "Tesseract（含 chi_sim）"
    if not e.which("tesseract"):
        return result(name, MISSING, "找不到 tesseract", "macOS：brew install tesseract tesseract-lang；Debian/Ubuntu：sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim")
    _, out = e.run(["tesseract", "--list-langs"])
    if "chi_sim" not in out.split():
        return result(name, MISSING, "缺少中文简体语言包 chi_sim", "macOS：brew install tesseract-lang；Debian/Ubuntu：sudo apt-get install tesseract-ocr-chi-sim")
    return result(name, PASS, "chi_sim 可用")


def check_pandoc(e, rt):
    name = "Pandoc"
    if not e.which("pandoc"):
        return result(name, MISSING, "找不到 pandoc", "brew install pandoc")
    return result(name, PASS, "可用")


def check_soffice(e, rt):
    name = "LibreOffice（能转换文件并渲染中文）"
    path = SOFFICE_APP if e.exists(SOFFICE_APP) else e.which("soffice")
    if not path:
        return result(name, MISSING, "找不到 soffice", "brew install --cask libreoffice")
    ok, detail = e.soffice_convert(path)
    if not ok:
        return result(name, MISSING, detail, "重新安装 LibreOffice，并确认能在终端里运行 soffice --headless")
    return result(name, PASS, f"{path}：{detail}")


def check_forge_deps(e, rt):
    name = "报告引擎 npm 依赖与字体环境"
    forge = runtime.engine_path(rt, "report-forge")
    missing = [x for x in ("node_modules/playwright", ".font-venv/bin/python") if not e.exists(str(forge / x))]
    if missing:
        return result(name, MISSING, "缺 " + "、".join(missing), f"cd {forge} && npm ci && npm run setup-fonts")
    return result(name, PASS, str(forge))


def check_a4_pdf_backend(e, rt):
    name = "A4 PDF 导出后端"
    if sys.platform == "darwin" and e.which("swift"):
        return result(name, PASS, "macOS PDFKit（逐页导出并重建内部链接）；Chromium 整册后端作为跨平台备用")
    return result(name, PASS, "Chromium 整册导出（保留原生内部链接）")


def check_probe(e, rt):
    name = "报告引擎能力探测（看图验证）"
    fix = f"{RENDER_FIX}，然后在 Claude Code 或 Codex 会话里完成看图验证（tools/record_probe.py）"
    probe = pathlib.Path(rt) / ".probe.json"
    if not e.exists(str(probe)):
        return result(name, MISSING, "还没有验证记录", fix)
    try:
        data = json.loads(e.read(str(probe)))
        lock = json.loads(e.read(str(pathlib.Path(rt) / "vendor" / "vendor.lock")))
    except (OSError, ValueError) as err:
        return result(name, MISSING, f"验证记录或 vendor.lock 无法读取：{err}", fix)
    if not data.get("verified"):
        return result(name, MISSING, "上次验证没有通过", fix)
    if data.get("commit") != lock.get("commit"):
        return result(name, MISSING, "验证记录对应的引擎版本已过期", fix)
    return result(name, PASS, f"已验证（{data.get('at', '')}）")


def check_node_playwright(e, rt):
    name = "thinkcell 浏览器测试前提（NODE_PATH 与 TC_BROWSER_PATH）"
    node_modules = runtime.engine_path(rt, "report-forge") / "node_modules"
    code, out = e.run(["node", "-e", "const p=require('playwright').chromium.executablePath(); console.log(p)"],
                      env=dict(os.environ, NODE_PATH=str(node_modules)))
    if code != 0:
        return result(name, MISSING, "NODE_PATH 下加载不到 playwright", f"cd {node_modules.parent} && npm ci")
    browser = out.strip().splitlines()[-1] if runtime.chrome_channel() == "chromium" and out.strip() else CHROME
    if not e.exists(browser):
        return result(name, MISSING, f"浏览器不存在：{browser}", f"cd {node_modules.parent} && npx playwright install chromium")
    return result(name, PASS, f"NODE_PATH={node_modules}；浏览器={browser}")


def check_disk(e, rt):
    name = "磁盘剩余空间"
    gb = e.free_gb(str(rt))
    if gb < MIN_FREE_GB:
        return result(name, WARN, f"剩余 {gb:.1f} GB，低于 {MIN_FREE_GB} GB", "清理磁盘空间")
    return result(name, PASS, f"剩余 {gb:.1f} GB")


def check_vendor(e, rt):
    name = "vendor 引擎完整性"
    errors = e.vendor_errors(rt)
    if errors:
        return result(name, MISSING, "；".join(errors[:5]) + ("……" if len(errors) > 5 else ""), "python3 tools/vendor_sync.py sync")
    return result(name, PASS, "与 vendor.lock 一致")


CHECKS = [check_vendor, check_node, check_venv, check_playwright_chromium, check_chrome, check_poppler,
          check_tesseract, check_pandoc, check_soffice, check_forge_deps, check_a4_pdf_backend, check_probe, check_node_playwright, check_disk]


def run_all(e, rt):
    return [c(e, rt) for c in CHECKS]


def exit_code(results):
    return 1 if any(r["status"] in (MISSING, OLD) for r in results) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="检查出成品所需的本机环境")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        rt = runtime.runtime_root()
    except runtime.RuntimeNotFound as err:
        print(f"[{MISSING}] 运行时：{err}")
        return 1
    results = run_all(Env(), rt)
    if a.json:
        print(json.dumps({"runtime": str(rt), "results": results}, ensure_ascii=False, indent=1))
    else:
        print(f"运行时：{rt}")
        for r in results:
            line = f"[{r['status']}] {r['name']}：{r['detail']}"
            if r["status"] != PASS and r["fix"]:
                line += f"\n        修复：{r['fix']}"
            print(line)
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
