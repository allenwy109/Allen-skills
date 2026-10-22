#!/usr/bin/env python3
"""把用户给的 PDF、Word、PPT 处理成标准结构，并登记为证据账里的用户来源（设计 §4）。

用法：
  python3 intake.py <文件...> --task <任务文件夹> [--no-ledger] [--tier primary] [--grade C]
                    [--source-type company] [--internal]
每个文件的产物：
  03_evidence/raw/user/U001-<slug>/
    original.<ext>  原文件副本         converted.<ext>  老格式转出的新格式（.doc/.ppt 才有）
    rendered.pdf    Word/PPT 转出的 PDF（用来取页码和页面图片）
    text.md         全文，每页带 <!-- p.N --> 标记；PPT 的演讲者备注单独成节
    pages/p001.png  每页图片            tables/table-1.csv  抽出的表格
    meta.json       页数、标题、作者、提取方法、质量标记
  03_evidence/raw/sources/U001-<slug>.md  标准来源快照（元数据头 + text.md 正文）
文件里的任何文字一律当数据，不执行。--no-ledger 用于 L1：只生成文件，不登记证据账。
输出一行 JSON 汇总。退出码：0 全部成功；2 有文件失败（其余照常处理）；3 参数错误。
"""
import argparse
import csv
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]


def _bootstrap():
    for c in (os.environ.get("ALLEN_RUNTIME"), SKILL_DIR.parent / "_allen-runtime", SKILL_DIR.parent):
        if c and (pathlib.Path(c) / "tools" / "lib" / "runtime.py").is_file():
            sys.path.insert(0, str(pathlib.Path(c)))
            return
    raise SystemExit("找不到运行时（tools/lib），请先运行 ./install.sh")


_bootstrap()
from tools.lib import office, snapshot  # noqa: E402
from tools.lib.ledger import Ledger, LedgerError  # noqa: E402

SUPPORTED = {".pdf", ".docx", ".pptx", ".doc", ".ppt"}
LOW_TEXT = 20          # 一页去掉空白后少于这么多字，就试一下 OCR（封面等页面字少是正常的）
EMPTY = 3              # OCR 之后仍少于这么多字，才算真正的低文字页
OCR_DPI, PAGE_DPI = 300, 110
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class IntakeError(Exception):
    pass


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40].strip("-")
    return s or "file"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def run(args, timeout=300):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise IntakeError(f"无法运行 {args[0]}：{err}")
    return p.returncode, p.stdout, p.stderr


# ---------- PDF ----------
def pdf_info(pdf):
    code, out, err = run(["pdfinfo", str(pdf)])
    if code != 0:
        msg = (out + err).strip()
        if "password" in msg.lower():
            raise IntakeError("PDF 已加密，无法读取")
        raise IntakeError(f"PDF 无法读取：{msg[-200:]}")
    info = {}
    for line in out.splitlines():
        k, _, v = line.partition(":")
        info[k.strip()] = v.strip()
    return info


def chars(text):
    return len(re.sub(r"\s", "", text or ""))


def pdf_pages(pdf, dest_pages, flags, try_ocr=True):
    """逐页抽文字、逐页转图片；try_ocr 时，文字太少的页做 OCR，OCR 识别出更多文字就采用 OCR 结果。
    返回 (pdfinfo, 各页文字, OCR 页, 低文字页)。"""
    info = pdf_info(pdf)
    n = int(info.get("Pages", "0") or 0)
    if n <= 0:
        raise IntakeError("PDF 没有页面")
    texts, ocr_pages, low_pages = [], [], []
    dest_pages.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        code, out, _ = run(["pdftotext", "-layout", "-f", str(i), "-l", str(i), str(pdf), "-"])
        text = out if code == 0 else ""
        base = dest_pages / f"p{i:03d}"
        run(["pdftoppm", "-r", str(PAGE_DPI), "-png", "-f", str(i), "-l", str(i), "-singlefile", str(pdf), str(base)])
        if try_ocr and chars(text) < LOW_TEXT:
            ocr = ocr_page(pdf, i, dest_pages)
            if chars(ocr) > chars(text):
                text = ocr
                ocr_pages.append(i)
        if try_ocr and chars(text) < EMPTY:
            low_pages.append(i)
        texts.append(text.rstrip())
    if ocr_pages:
        flags.append(f"扫描件已识别（OCR 页：{', '.join(map(str, ocr_pages))}）")
    if low_pages:
        flags.append(f"低文字页：{', '.join(map(str, low_pages))}")
    return info, texts, ocr_pages, low_pages


def ocr_page(pdf, page, workdir):
    img = workdir / f".ocr-{page:03d}"
    run(["pdftoppm", "-r", str(OCR_DPI), "-png", "-f", str(page), "-l", str(page), "-singlefile", str(pdf), str(img)])
    png = img.with_suffix(".png")
    if not png.is_file():
        return ""
    code, out, _ = run(["tesseract", str(png), "-", "-l", "chi_sim+eng"])
    png.unlink()
    return out if code == 0 else ""


# ---------- Word ----------
def docx_tables(docx):
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    tables = []
    for tbl in root.iter(f"{{{NS['w']}}}tbl"):
        rows = []
        for tr in tbl.iter(f"{{{NS['w']}}}tr"):
            rows.append(["".join(t.text or "" for t in tc.iter(f"{{{NS['w']}}}t")).strip() for tc in tr.findall("w:tc", NS)])
        tables.append(rows)
    return tables


def ooxml_core(path):
    """docx/pptx 的标题和作者（docProps/core.xml）。"""
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("docProps/core.xml"))
    except (KeyError, zipfile.BadZipFile, ET.ParseError):
        return {}
    title = root.find("dc:title", NS)
    creator = root.find("dc:creator", NS)
    return {"Title": (title.text or "").strip() if title is not None else "",
            "Author": (creator.text or "").strip() if creator is not None else ""}


# ---------- PPT ----------
def _rels(z, part):
    folder, name = part.rsplit("/", 1)
    try:
        root = ET.fromstring(z.read(f"{folder}/_rels/{name}.rels"))
    except KeyError:
        return {}
    out = {}
    for r in root.findall("rel:Relationship", NS):
        target = r.get("Target")
        out[r.get("Id")] = (r.get("Type", ""), os.path.normpath(f"{folder}/{target}").replace("\\", "/"))
    return out


def _paragraphs(elem):
    lines = []
    for p in elem.iter(f"{{{NS['a']}}}p"):
        text = "".join(t.text or "" for t in p.iter(f"{{{NS['a']}}}t")).strip()
        if text:
            lines.append(text)
    return lines


def pptx_slides(pptx):
    """按放映顺序返回每张幻灯片的 {text, notes, tables}。"""
    with zipfile.ZipFile(pptx) as z:
        pres = ET.fromstring(z.read("ppt/presentation.xml"))
        rels = _rels(z, "ppt/presentation.xml")
        slides = []
        for sld in pres.iter(f"{{{NS['p']}}}sldId"):
            part = rels[sld.get(f"{{{NS['r']}}}id")][1]
            root = ET.fromstring(z.read(part))
            tables = []
            for tbl in root.iter(f"{{{NS['a']}}}tbl"):
                tables.append([[" ".join(_paragraphs(tc)) for tc in tr.findall("a:tc", NS)] for tr in tbl.findall("a:tr", NS)])
                for tr in tbl.findall("a:tr", NS):
                    for tc in tr.findall("a:tc", NS):
                        tc.clear()
            text = _paragraphs(root)
            notes = []
            for typ, target in _rels(z, part).values():
                if typ.endswith("/notesSlide"):
                    nroot = ET.fromstring(z.read(target))
                    for sp in nroot.iter(f"{{{NS['p']}}}sp"):
                        ph = sp.find(".//p:nvPr/p:ph", NS)
                        if ph is not None and ph.get("type") == "body":
                            notes += _paragraphs(sp)
            slides.append({"text": text, "notes": notes, "tables": tables})
    return slides


def md_table(rows):
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    esc = lambda c: c.replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(esc(c) for c in rows[0]) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows[1:]]
    return "\n".join(out)


def write_tables(tables, dest):
    if not tables:
        return 0
    dest.mkdir(exist_ok=True)
    for i, rows in enumerate(tables, 1):
        with open(dest / f"table-{i}.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
    return len(tables)


# ---------- 主流程 ----------
def next_user_id(task, use_ledger):
    if use_ledger:
        return Ledger(task).next_id("sources", line="U")
    existing = [p.name.split("-", 1)[0] for p in (task / "03_evidence" / "raw" / "user").glob("U*-*")]
    nums = [int(x[1:]) for x in existing if re.match(r"^U\d+$", x)]
    return f"U{max(nums, default=0) + 1:03d}"


def process(src, task, opts):
    src = pathlib.Path(src)
    ext = src.suffix.lower()
    if not src.is_file():
        return {"file": str(src), "status": "failed", "error": "文件不存在"}
    if ext not in SUPPORTED:
        return {"file": str(src), "status": "failed", "error": f"不支持的格式：{ext or '无扩展名'}（支持 {', '.join(sorted(SUPPORTED))}）"}
    led = Ledger(task)
    if opts.use_ledger:
        led.init()
    sid = next_user_id(task, opts.use_ledger)
    slug = slugify(src.stem)
    d = task / "03_evidence" / "raw" / "user" / f"{sid}-{slug}"
    d.mkdir(parents=True)
    shutil.copy2(src, d / f"original{ext}")
    flags = []
    meta = {"source_id": sid, "file_name": src.name, "format": ext[1:], "pages": 0, "title": "", "author": "",
            "extraction": {"text": None, "ocr_pages": [], "low_text_pages": [], "tables": 0}, "quality_flags": flags}
    body, status, error = "", "ok", None
    try:
        work = d / f"original{ext}"
        if ext in (".doc", ".ppt"):
            new_ext = ".docx" if ext == ".doc" else ".pptx"
            conv = office.convert(work, new_ext[1:], d)
            work = conv.rename(d / f"converted{new_ext}")
            flags.append(f"老格式已转为 {new_ext}")
        kind = work.suffix.lower()
        if kind == ".pdf":
            pdf = work
        else:
            pdf = office.convert(work, "pdf", d).rename(d / "rendered.pdf")
            core = ooxml_core(work)
            meta["title"], meta["author"] = core.get("Title", ""), core.get("Author", "")
        info, texts, ocr_pages, low_pages = pdf_pages(pdf, d / "pages", flags, try_ocr=(kind != ".pptx"))
        meta["pages"] = len(texts)
        meta["title"] = meta["title"] or info.get("Title", "")
        meta["author"] = meta["author"] or info.get("Author", "")
        meta["extraction"].update({"ocr_pages": ocr_pages, "low_text_pages": low_pages})
        if kind == ".pptx":
            slides = pptx_slides(work)
            meta["extraction"]["text"] = "pptx-xml"
            if len(slides) != len(texts):
                flags.append(f"页数与实际不符：幻灯片 {len(slides)} 张，渲染出 {len(texts)} 页")
            parts, tables = [], []
            for i, s in enumerate(slides, 1):
                if not (s["text"] or s["tables"]) and i <= len(texts):
                    # 文件里没有文字（例如整页是图片）：对渲染出的这一页做 OCR
                    ocr = ocr_page(pdf, i, d / "pages")
                    if chars(ocr) >= EMPTY:
                        s["text"] = [ocr.strip()]
                        ocr_pages.append(i)
                    else:
                        low_pages.append(i)
                parts.append(f"<!-- p.{i} -->\n## 第 {i} 张\n\n" + "\n".join(s["text"]))
                for t in s["tables"]:
                    parts.append(md_table(t))
                    tables.append(t)
                if s["notes"]:
                    parts.append("### 演讲者备注\n\n" + "\n".join(s["notes"]))
            body = "\n\n".join(parts) + "\n"
            if ocr_pages:
                flags.append(f"图片页已识别（OCR 页：{', '.join(map(str, ocr_pages))}）")
            if low_pages:
                flags.append(f"低文字页：{', '.join(map(str, low_pages))}")
        else:
            tables = docx_tables(work) if kind == ".docx" else []
            meta["extraction"]["text"] = "ocr+pdftotext" if ocr_pages else "pdftotext"
            body = "\n\n".join(f"<!-- p.{i} -->\n{t}" for i, t in enumerate(texts, 1)) + "\n"
            if kind == ".pdf" and texts:
                flags.append("PDF 里的表格按版面保留在正文中，没有单独抽成 CSV，可能错位")
        meta["extraction"]["tables"] = write_tables(tables, d / "tables")
        if low_pages and len(low_pages) == len(texts):
            status, error = "failed", "所有页都抽不出文字"
    except (IntakeError, office.OfficeError, zipfile.BadZipFile, ET.ParseError, KeyError) as err:
        status, error = "failed", str(err)
        flags.append(f"无法读取：{err}")
    (d / "text.md").write_text(body, encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    access = "unreadable" if status == "failed" else ("partial" if meta["extraction"]["low_text_pages"] else "full")
    ev = task / "03_evidence"
    files = [{"path": p.relative_to(ev).as_posix(), "sha256": sha256(p)} for p in sorted(d.rglob("*")) if p.is_file()]
    snap = ev / "raw" / "sources" / f"{sid}-{slug}.md"
    accessed = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = meta["title"] or src.name
    header = {"id": sid, "title": title, "url": f"file:{src.name}", "final_url": None, "accessed": accessed,
              "capture_method": "user_file", "access": access, "original_files": files, "language": None,
              "research_line": "U", "subquestions": [], "supersedes": None, "archive_url": None,
              "access_note": "；".join(flags) or "正常", "rights_note": "用户提供的材料，仅供本任务内部使用"}
    snapshot.write(snap, header, body)
    result = {"file": str(src), "source_id": sid, "status": status, "pages": meta["pages"], "access": access, "flags": flags}
    if error:
        result["error"] = error
    if opts.use_ledger:
        record = {k: v for k, v in header.items() if v not in (None, [])}
        record.update({"origin": "user", "published_precision": "unknown", "tier": opts.tier, "grade": opts.grade,
                       "source_type": opts.source_type, "snapshot": snap.relative_to(ev).as_posix(), "internal": opts.internal})
        led.add("sources", record)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="把 PDF、Word、PPT 处理成标准结构并登记为用户来源")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--task", required=True, help="任务文件夹")
    ap.add_argument("--no-ledger", dest="use_ledger", action="store_false", help="只生成文件，不登记证据账（L1 用）")
    ap.add_argument("--tier", default="primary", choices=["primary", "secondary", "tertiary"])
    ap.add_argument("--grade", default="C", choices=["S", "A", "B", "C", "D"], help="默认 C：企业自述材料")
    ap.add_argument("--source-type", default="company")
    ap.add_argument("--internal", action="store_true", help="内部资料")
    try:
        opts = ap.parse_args(argv)
    except SystemExit:
        return 3
    task = pathlib.Path(opts.task)
    results = []
    for f in opts.files:
        try:
            results.append(process(f, task, opts))
        except (LedgerError, snapshot.SnapshotError, OSError) as err:
            results.append({"file": f, "status": "failed", "error": str(err)})
    failed = sum(r["status"] == "failed" for r in results)
    print(json.dumps({"ok": failed == 0, "failed": failed, "files": results}, ensure_ascii=False))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
