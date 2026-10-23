"""测试专用：本地 HTTP 服务和一个虚构的研究任务（星河数据科技收入研究）。内容全部虚构，不访问外网。"""
import contextlib
import functools
import http.server
import json
import pathlib
import sys
import threading

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import research  # noqa: E402,F401  （导入时完成运行时定位）
import rcapture  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

PAGES = {
    "/report.html": ("text/html; charset=utf-8", """<!doctype html><html><head><title>星河数据科技 2025 年年报摘要</title>
<meta name="author" content="星河数据科技"><meta property="article:published_time" content="2026-03-28T09:00:00+08:00"></head>
<body><h1>2025 年经营情况</h1><p>公司全年营业收入 3200 万元，上年为 1800 万元。</p>
<table><tr><th>年份</th><th>收入（万元）</th></tr><tr><td>2024</td><td>1800</td></tr><tr><td>2025</td><td>3200</td></tr></table>
<script>var paywall = "captcha";</script></body></html>""".encode("utf-8")),
    "/news-gbk.html": ("text/html", """<html><head><meta charset="gbk"><title>行业观察：数据服务市场</title></head>
<body><p>行业协会估计，2025 年数据服务市场规模约 120 亿元。</p></body></html>""".encode("gbk")),
    "/paywall.html": ("text/html; charset=utf-8", "<html><body><p>订阅后继续阅读</p><p>付费阅读</p></body></html>".encode("utf-8")),
    "/long-about-paywalls.html": ("text/html; charset=utf-8", ("<html><body><h1>付费墙研究</h1>" + "<p>本文讨论 subscription required 这类提示如何影响读者。" * 200
                                                               + "</p></body></html>").encode("utf-8")),
    "/notes.txt": ("text/plain; charset=utf-8", "纯文本材料：客户续约率未披露。".encode("utf-8")),
    "/denied.html": ("text/html", b""),
    "/big.bin": ("application/octet-stream", b"x" * 4096),
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/denied.html":
            self.send_response(403)
            self.end_headers()
            return
        if self.path == "/flaky.html":
            Handler.flaky = getattr(Handler, "flaky", 0) + 1
            if Handler.flaky < 2:
                self.send_response(503)
                self.end_headers()
                return
            self.path = "/report.html"
        if self.path not in PAGES:
            self.send_response(404)
            self.end_headers()
            return
        ctype, body = PAGES[self.path]
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@contextlib.contextmanager
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()


REPORT = """# 星河数据科技收入研究

日期：2026-10-23；截至：2026-10-22

## 执行摘要

星河数据科技 2025 年营业收入 3200 万元，较上年增长约 77.8%[1]，增速由本次计算得出[数据:M-R0003](../03_evidence/data/curated/M-growth.csv)。所在市场规模约 120 亿元（行业协会估计）[2]，公司份额很小。

## 分歧与不确定性

市场规模只有一家机构的估计[2]。

## 未解问题

客户续约率未披露。

## 方法与局限

只检索了公开网页，2 次检索。

## 参考来源

- [1] 星河数据科技. 星河数据科技 2025 年年报摘要. 2026-03-28. {u1}. 访问 2026-10-23. 来源 ID `M001` 存档 [M001-annual-report.md](../03_evidence/raw/sources/M001-annual-report.md)
- [2] unknown. 行业观察：数据服务市场. unknown. {u2}. 访问 2026-10-23. 来源 ID `M002` 存档 [M002-market-news.md](../03_evidence/raw/sources/M002-market-news.md)
"""


def make_research_task(task, base_url):
    """建一个能通过 research check 的任务文件夹，返回 Ledger。"""
    task = pathlib.Path(task)
    research.main(["init", str(task), "--question", "星河数据科技的收入增长有多快"])
    led = Ledger(task)
    led.patch("project", "project", {"data_status": "available", "data_reason": "年报披露了两年收入", "search_status": "performed",
                                     "search_reason": "需要公开年报和行业估计"})
    rcapture.capture(task, f"{base_url}/report.html", "annual-report", tier="primary", grade="A")
    rcapture.capture(task, f"{base_url}/news-gbk.html", "market-news")
    led.add("search_log", {"searched_at": "2026-10-23T10:00:00+08:00", "tool": "web_search", "query": "星河数据科技 2025 年报 营业收入",
                           "research_line": "M", "status": "found", "results_seen": "前 10 条", "opened_source_ids": ["M001"],
                           "discarded": [{"target": "https://example.com/spam", "reason": "low_quality"}]})
    led.add("search_log", {"searched_at": "2026-10-23T10:05:00+08:00", "tool": "web_search", "query": "数据服务 市场规模 2025",
                           "research_line": "M", "status": "found", "opened_source_ids": ["M002"]})
    led.add("evidence", {"source_id": "M001", "locator": "2025 年经营情况 第 1 段", "excerpt": "公司全年营业收入 3200 万元，上年为 1800 万元。",
                         "attribute": "actual", "numeric": False, "research_line": "M", "claim_text": "两年收入"})
    led.add("evidence", {"source_id": "M002", "locator": "第 1 段", "excerpt": "行业协会估计，2025 年数据服务市场规模约 120 亿元。",
                         "attribute": "estimate", "numeric": False, "research_line": "M", "claim_text": "市场规模"})
    ev = task / "03_evidence"
    data = ev / "data"
    (data / "extracted").mkdir(parents=True, exist_ok=True)
    (data / "curated").mkdir(parents=True, exist_ok=True)
    (ev / "analysis").mkdir(parents=True, exist_ok=True)
    head = "record_id,entity,metric,value,value_type,unit,period,geography,scope,value_origin,status,source_id,source_locator,original_value,input_ids,method,missing_reason\n"
    (data / "extracted" / "M-revenue.csv").write_text(head +
        "M-R0001,星河数据科技,营业收入,1800,number,万元,2024,中国,合并,reported,present,M001,2025 年经营情况 第 1 段,1800 万元,,,\n"
        "M-R0002,星河数据科技,营业收入,3200,number,万元,2025,中国,合并,reported,present,M001,2025 年经营情况 第 1 段,3200 万元,,,\n", encoding="utf-8")
    (data / "curated" / "M-growth.csv").write_text(head +
        "M-R0003,星河数据科技,营业收入增速,77.8,number,%,2025,中国,合并,derived,present,,,,M-R0001;M-R0002,analysis/growth.md,\n", encoding="utf-8")
    (ev / "analysis" / "growth.md").write_text("# 增速\n\n(3200 / 1800 - 1) × 100 = 77.8，保留一位小数。输入：M-R0001、M-R0002。\n", encoding="utf-8")
    (data / "datasets.json").write_text(json.dumps([
        {"id": "revenue", "path": "data/extracted/M-revenue.csv", "stage": "extracted", "grain": "一家公司一年的营业收入", "coverage": "2024–2025", "limitations": "none"},
        {"id": "growth", "path": "data/curated/M-growth.csv", "stage": "curated", "grain": "一家公司一年的收入增速", "coverage": "2025", "limitations": "none"}],
        ensure_ascii=False, indent=1), encoding="utf-8")
    cols = head.strip().split(",")
    desc = {"value": "number"}
    rows = ["dataset_id,field,type,description,unit,missing_rule"]
    for ds in ("revenue", "growth"):
        for c in cols:
            rows.append(f"{ds},{c},{desc.get(c, 'string')},{c} 字段,{'万元' if c == 'value' and ds == 'revenue' else 'n/a'},空字符串表示缺失")
    (data / "dictionary.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (data / "README.md").write_text("# 数据\n\n两张表：提取层收入、整理层增速。\n", encoding="utf-8")
    snaps = {s["id"]: s for s in led.read("sources")}
    (task / "03r_research" / "report.md").write_text(REPORT.format(u1=snaps["M001"]["url"], u2=snaps["M002"]["url"]), encoding="utf-8")
    return led
