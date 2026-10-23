"""研究采集（research capture，设计 §5.1；能力清单 D1 与 H 节优化 1、2、3、6）。只用标准库。

把一个网页、PDF 或本地文件存进任务文件夹：原件 → 03_evidence/raw/files/（U 前缀放 raw/user/），
快照 → 03_evidence/raw/sources/<ID>-<slug>.md，并在证据账 sources 表登记一条来源。

- 取字节：固定 UA，超时 45 秒；429、5xx 和网络错误按 1、2、4 秒退避重试（最多 3 次）；可选遵守 robots.txt。
  Content-Length 或累计字节超过上限（默认 50MB）时不下载，只登记链接和大小（metadata_only）。
  401、402、403 → 访问受限，停止，不登记（不绕过付费墙和登录）。
- 编码：HTTP 头 charset → HTML meta charset → BOM → UTF-8 → GB18030（覆盖 GBK）。记录 Content-Type 和主要响应头。
- 付费墙和验证码：只在抽出的可见正文上判断一次，综合正文长度和命中标记的个数（谈论付费墙的长文不会被误拦）。
  确认拦截时停止，登记为 metadata_only，access_note 写明命中的标记。
- 正文：HTML 转 Markdown（保留标题、列表、表格、链接、引用）；PDF 用 pdftotext 逐页抽取并加 <!-- p.N --> 页码；
  文本类按编码解码；其他二进制不硬转文字。正文超过上限时截断并标 partial。
- 自动抽取标题、作者、发布日期作为候选值（命令行参数优先）。
- 每个原件单独记 sha256。
- 浏览器（--browser）：通过本机已开的 Chrome（默认 http://127.0.0.1:9222）只读打开原页，存 HTML 和整页截图，
  capture_method=browser。不登录、不填表；需要登录的站点先问用户。
"""
import datetime
import hashlib
import json
import mimetypes
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

from tools.lib import runtime, snapshot
from tools.lib.ledger import Ledger, LedgerError

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 allen-research/1.0"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
PAYWALL = ("subscribe to continue", "sign in to continue", "create an account to continue", "subscription required", "members only",
           "订阅后继续阅读", "付费阅读", "开通会员", "登录后继续", "请登录后阅读全文", "购买后查看")
CAPTCHA = ("captcha", "are you a robot", "verify you are human", "cloudflare ray id", "人机验证", "安全验证", "拖动滑块", "请完成安全验证")
DENIED = {401, 402, 403}
RETRY = {429, 500, 502, 503, 504}
HEADERS_KEPT = ("content-type", "content-length", "last-modified", "etag", "server", "date")


class CaptureError(Exception):
    def __init__(self, code, reason, **extra):
        super().__init__(reason)
        self.code, self.reason, self.extra = code, reason, extra


# ---------- 取字节 ----------

def fetch(url, max_bytes, timeout=45, retries=3, respect_robots=False, opener=None):
    """返回 (字节, HTTP 状态, 响应头 dict, final_url)。超限抛 oversize；访问受限抛 access_denied。"""
    if respect_robots:
        parts = urllib.parse.urlsplit(url)
        rp = urllib.robotparser.RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
        try:
            rp.read()
            if not rp.can_fetch(UA, url):
                raise CaptureError(2, "robots_disallowed", url=url)
        except (urllib.error.URLError, OSError):
            pass
    opener = opener or urllib.request.build_opener()
    delay = 1
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with opener.open(req, timeout=timeout) as r:
                headers = {k.lower(): v for k, v in r.headers.items()}
                length = headers.get("content-length")
                if length and length.isdigit() and int(length) > max_bytes:
                    raise CaptureError(2, "oversize", bytes=int(length), url=url)
                chunks, total = [], 0
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise CaptureError(2, "oversize", bytes=total, url=url)
                    chunks.append(chunk)
                return b"".join(chunks), r.status, headers, r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in DENIED:
                raise CaptureError(2, "access_denied", status=e.code, access_note=f"HTTP {e.code}")
            if e.code in RETRY and attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise CaptureError(2, "http_error", status=e.code)
        except CaptureError:
            raise
        except (urllib.error.URLError, OSError) as e:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise CaptureError(2, "fetch_error", detail=str(e)[:200])


# ---------- 编码与正文 ----------

META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([\w-]+)""", re.I)


def decode(data, content_type=""):
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    candidates = [m.group(1)] if m else []
    meta = META_CHARSET.search(data[:4096])
    if meta:
        candidates.append(meta.group(1).decode("ascii", "ignore"))
    if data.startswith(b"\xef\xbb\xbf"):
        candidates.insert(0, "utf-8-sig")
    candidates += ["utf-8", "gb18030"]
    for enc in candidates:
        enc = {"gb2312": "gb18030", "gbk": "gb18030"}.get(enc.lower(), enc)
        try:
            return data.decode(enc), enc
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", "replace"), "utf-8-replace"


class _Markdown(HTMLParser):
    """HTML → Markdown：保留标题、列表、表格、链接、引用；跳过脚本、样式、svg、head。顺带收集元数据候选值。"""
    SKIP = {"script", "style", "noscript", "svg", "template", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.list_depth, self.href = [], 0, 0, None
        self.row, self.in_cell, self.cell, self.quote = None, False, [], 0
        self.meta, self.in_title, self.title = {}, False, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"].strip())
        if tag == "title":
            self.in_title = True
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "time" and a.get("datetime"):
            self.meta.setdefault("time", a["datetime"])
        if re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "section", "article"):
            self.out.append("\n\n")
        elif tag in ("ul", "ol"):
            self.list_depth += 1
        elif tag == "li":
            self.out.append("\n" + "  " * (self.list_depth - 1) + "- ")
        elif tag == "br":
            self.out.append("\n")
        elif tag == "hr":
            self.out.append("\n\n---\n\n")
        elif tag == "blockquote":
            self.quote += 1
            self.out.append("\n\n> ")
        elif tag == "a":
            self.href = a.get("href")
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.in_cell, self.cell = True, []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("ul", "ol"):
            self.list_depth = max(0, self.list_depth - 1)
            self.out.append("\n")
        elif tag == "blockquote":
            self.quote = max(0, self.quote - 1)
            self.out.append("\n\n")
        elif tag == "a":
            self.href = None
        elif tag in ("td", "th") and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        elif tag == "tr" and self.row is not None:
            self.out.append("\n| " + " | ".join(self.row) + " |")
            self.row = None
        elif re.fullmatch(r"h[1-6]", tag) or tag in ("p", "table"):
            self.out.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.skip:
            return
        text = data if self.in_cell else re.sub(r"\s+", " ", data)
        if self.href and text.strip() and not self.href.startswith(("#", "javascript:")):
            text = f"{text} ({self.href})"
        (self.cell if self.in_cell else self.out).append(text)


def html_to_markdown(text):
    p = _Markdown()
    p.feed(text)
    body = "".join(p.out)
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    meta = p.meta
    cand = {"title": meta.get("og:title") or p.title.strip() or None,
            "author": meta.get("author") or meta.get("article:author") or None,
            "published": (meta.get("article:published_time") or meta.get("pubdate") or meta.get("date") or meta.get("time") or None)}
    return body, cand


def block_kind(body):
    """在可见正文上判断付费墙或验证码：命中标记且正文很短，或命中多个标记且正文不长。返回 (类型, 标记) 或 None。"""
    low = body.lower()
    hits = [("paywall", m) for m in PAYWALL if m in low] + [("captcha", m) for m in CAPTCHA if m in low]
    length = len(body.strip())
    if hits and (length < 1500 or (len({m for _, m in hits}) >= 3 and length < 5000)):
        return hits[0]
    return None


def pdf_text(path):
    try:
        out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return "", "none"
    if out.returncode:
        return "", "none"
    pages = [f"<!-- p.{i} -->\n{pg.strip()}" for i, pg in enumerate(out.stdout.split("\f"), 1) if pg.strip()]
    return ("\n\n".join(pages) + "\n") if pages else "", "pdftotext"


def published_precision(value):
    if not value:
        return None, "unknown"
    m = re.match(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", value)
    if not m:
        return None, "unknown"
    if m.group(3):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "day"
    if m.group(2):
        return f"{m.group(1)}-{m.group(2)}", "month"
    return m.group(1), "year"


# ---------- 浏览器 ----------

BROWSER_SCRIPT = r"""
import json, sys
from playwright.sync_api import sync_playwright
cdp, url, html_out, png_out = sys.argv[1:5]
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(cdp)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    try:
        resp = page.goto(url, wait_until="load", timeout=45000)
        page.wait_for_timeout(800)
        open(html_out, "w", encoding="utf-8").write(page.content())
        page.screenshot(path=png_out, full_page=True)
        print(json.dumps({"status": resp.status if resp else None, "final_url": page.url}))
    finally:
        page.close()
"""


def browser_capture(url, cdp, workdir):
    py = runtime.venv_python()
    if not py.is_file():
        raise CaptureError(2, "browser_unavailable", detail="没有虚拟环境里的 Playwright（./install.sh --render-deps）")
    html_out, png_out = pathlib.Path(workdir) / "page.html", pathlib.Path(workdir) / "page.png"
    p = subprocess.run([str(py), "-c", BROWSER_SCRIPT, cdp, url, str(html_out), str(png_out)], capture_output=True, text=True, timeout=120)
    if p.returncode:
        raise CaptureError(2, "browser_error", detail=(p.stderr or p.stdout)[-300:])
    info = json.loads(p.stdout.strip().splitlines()[-1])
    if info.get("status") in DENIED:
        raise CaptureError(2, "access_denied", status=info["status"], access_note=f"HTTP {info['status']}（浏览器）")
    return html_out.read_bytes(), png_out.read_bytes(), info


# ---------- 主流程 ----------

def _ext(name, mime):
    suffix = pathlib.Path(urllib.parse.urlsplit(name).path).suffix.lower()
    if suffix and len(suffix) <= 8:
        return suffix
    return mimetypes.guess_extension((mime or "").split(";")[0].strip()) or ".bin"


def capture(task, source, slug, line="M", sid=None, title=None, author=None, published=None, lang=None, tier="secondary", grade="B",
            coi=None, subquestions=None, supersedes=None, archive_url=None, rights_note=None, access_note=None, access=None,
            max_bytes=50 * 1024 * 1024, max_chars=400000, browser=False, cdp="http://127.0.0.1:9222", respect_robots=False, opener=None,
            lite=False):
    """返回结果 dict（ok、id、snapshot、original_files、access、…）。失败抛 CaptureError。
    lite=True 时 task 是轻量包目录（raw/ + answer.md）：只存快照和原件，不登记证据账。"""
    if not SLUG.match(slug):
        raise CaptureError(3, "bad_slug")
    ev = pathlib.Path(task) if lite else pathlib.Path(task) / "03_evidence"
    led = None if lite else Ledger(task)
    if not sid:
        if lite:
            used = [int(f.name[1:].split("-")[0]) for f in (ev / "raw" / "sources").glob(f"{line}*-*.md") if f.name[1:].split("-")[0].isdigit()]
            sid = f"{line}{max(used, default=0) + 1:03d}"
        else:
            sid = led.next_id("sources", line)
    if not re.fullmatch(r"[ABD-Z]\d{3,4}", sid):
        raise CaptureError(3, "bad_id")
    if (led and led.get("sources", sid)) or list((ev / "raw").rglob(f"{sid}-*")):
        raise CaptureError(3, "id_already_exists", id=sid)
    is_url = re.match(r"https?://", source)
    if not is_url and not pathlib.Path(source).is_file():
        raise CaptureError(3, "source_not_found")
    accessed = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
    meta_note, headers, files, status, final_url = None, {}, [], None, source
    body, cand, method, mime = "", {}, "script", ""

    def register(access_value, note, original=()):
        stored = []
        for name, data in original:
            dest_dir = ev / "raw" / ("user" if sid.startswith("U") else "files")
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / name
            with open(dest, "xb") as f:
                f.write(data)
            stored.append({"path": str(dest.relative_to(ev)), "sha256": hashlib.sha256(data).hexdigest()})
        pub, prec = published_precision(published or cand.get("published"))
        row = {"id": sid, "origin": "user" if sid.startswith("U") else "web", "title": title or cand.get("title") or slug,
               "url": source if is_url else f"file:{pathlib.Path(source).name}", "final_url": final_url if is_url else None,
               "author_org": author or cand.get("author"), "published": pub, "published_precision": prec, "accessed": accessed,
               "language": lang, "tier": tier, "grade": grade, "conflict_of_interest": coi or "none",
               "capture_method": method, "access": access_value, "original_files": stored, "research_line": line,
               "subquestions": subquestions or [], "supersedes": supersedes, "archive_url": archive_url,
               "access_note": access_note or note or "正常", "rights_note": rights_note or "none"}
        row = {k: v for k, v in row.items() if v not in (None, [], "")} | {"original_files": stored}
        snap = ev / "raw" / "sources" / f"{sid}-{slug}.md"
        snapshot.write(snap, {k: row.get(k) for k in snapshot.fields()}, body)
        row["snapshot"] = str(snap.relative_to(ev))
        if led is None:
            return row
        try:
            led.add("sources", row, line=None)
        except LedgerError:
            snap.unlink()
            for s in stored:
                (ev / s["path"]).unlink()
            raise
        return row

    if not is_url:
        data = pathlib.Path(source).read_bytes()
        if len(data) > max_bytes:
            raise CaptureError(2, "oversize", bytes=len(data))
        mime = mimetypes.guess_type(source)[0] or ""
        originals = [(f"{sid}-{slug}{_ext(source, mime)}", data)]
        method = "user_file" if sid.startswith("U") else "script"
    else:
        try:
            if browser:
                with tempfile.TemporaryDirectory() as tmp:
                    data, png, info = browser_capture(source, cdp, tmp)
                method, mime, final_url, status = "browser", "text/html", info.get("final_url") or source, info.get("status")
                originals = [(f"{sid}-{slug}.html", data), (f"{sid}-{slug}-01.png", png)]
            else:
                data, status, headers, final_url = fetch(source, max_bytes, respect_robots=respect_robots, opener=opener)
                mime = headers.get("content-type", "")
                originals = [(f"{sid}-{slug}{_ext(final_url, mime)}", data)]
        except CaptureError as e:
            if e.reason == "oversize":
                method = "metadata_only"
                row = register("metadata_only", f"oversize: {e.extra.get('bytes')} bytes，未下载")
                return {"ok": False, "reason": "oversize", "id": sid, "registered": True, "snapshot": row["snapshot"], **e.extra}
            raise
    kind = mime.split(";")[0].strip().lower()
    head = data[:512].lower()
    looks_html = kind in ("text/html", "application/xhtml+xml") or head.lstrip().startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
    extractor = "none"
    with tempfile.TemporaryDirectory() as tmp:
        if kind == "application/pdf" or originals[0][0].endswith(".pdf"):
            tmpf = pathlib.Path(tmp) / "x.pdf"
            tmpf.write_bytes(data)
            body, extractor = pdf_text(tmpf)
        elif looks_html:
            text, enc = decode(data, mime)
            body, cand = html_to_markdown(text)
            extractor = f"html({enc})"
            blocked = block_kind(body)
            if blocked:
                body, method = "", "metadata_only"
                row = register("metadata_only", f"{blocked[0]}: {blocked[1]}（停止，不绕过）")
                return {"ok": False, "reason": "access_blocked", "block_kind": blocked[0], "marker": blocked[1], "id": sid,
                        "registered": True, "snapshot": row["snapshot"]}
        elif kind.startswith("text/") or kind in ("application/json", "application/xml") or originals[0][0].endswith((".txt", ".md", ".csv", ".json")):
            body, enc = decode(data, mime)
            extractor = f"text({enc})"
        else:
            meta_note = f"binary:{kind or 'unknown'}"
    if access:
        access_value = access
    elif not body.strip() or extractor == "none":
        access_value = "metadata_only"
    elif len(body) > max_chars:
        body = body[:max_chars] + f"\n\n[...]（正文超过 {max_chars} 字符，已截断；全文见原件）\n"
        access_value = "partial"
    else:
        access_value = "full"
    note = meta_note
    if headers:
        kept = "；".join(f"{k}={headers[k]}" for k in HEADERS_KEPT if k in headers)
        note = "；".join(x for x in (note, f"HTTP {status}；{kept}") if x)
    row = register(access_value, note, originals)
    return {"ok": True, "id": sid, "snapshot": row["snapshot"], "original_files": row["original_files"], "access": access_value,
            "status": status, "content_type": mime, "final_url": final_url, "extractor": extractor, "body_chars": len(body),
            "title": row["title"], "candidates": cand}

