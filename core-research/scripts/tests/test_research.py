"""core-research 的测试：采集（本地 HTTP 服务，不访问外网）、任务文件夹检查、研究包封包与检查。夹具全部虚构。"""
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import research_fixture as RF  # noqa: E402
import rcapture  # noqa: E402
import rcheck  # noqa: E402
import research  # noqa: E402
import rseal  # noqa: E402
from tools.acceptance import Acceptance  # noqa: E402
from tools.lib import runtime, snapshot  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

SERVER = RF.server()
BASE = SERVER.__enter__()
TEMPLATE = tempfile.TemporaryDirectory()
TASK_TEMPLATE = pathlib.Path(TEMPLATE.name) / "task"
RF.make_research_task(TASK_TEMPLATE, BASE)
REVIEW = {k: {"passed": True, "evidence": "测试复核"} for k in ("questions_answered", "evidence_support", "data_semantics", "limitations")}


def valid_handoff(code="A"):
    return {
        "version": 1, "line_id": code, "role": "market-and-data", "summary": "市场证据摘要",
        "source_ids": [f"{code}001"], "data_files": [f"03_evidence/data/extracted/{code}-market.csv"],
        "supported_claims": ["市场存在"], "counter_evidence": ["样本偏小"],
        "limitations": ["缺少成交数据"], "unresolved_questions": ["价格敏感度"],
        "next_search_recommendation": "补充采购记录",
    }


def tearDownModule():
    SERVER.__exit__(None, None, None)
    TEMPLATE.cleanup()


def minimal_pdf(pages):
    """两页的最小 PDF（只用标准库生成），用来测 pdftotext 页码标记。"""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids = []
    for i, text in enumerate(pages):
        page_no, content_no = 3 + 2 * i, 4 + 2 * i
        kids.append(f"{page_no} 0 R")
        stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_no} 0 R /Resources << /Font << /F1 {3 + 2 * len(pages)} 0 R >> >> >>")
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name).resolve() / "task"
        shutil.copytree(TASK_TEMPLATE, self.task)
        self.led = Ledger(self.task)
        self.ev = self.task / "03_evidence"

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, target=None, **kw):
        return rcheck.run(target or self.task, **kw)

    def errors(self, r):
        return "\n".join(r["errors"])

    def replace(self, path, old, new):
        p = pathlib.Path(path)
        text = p.read_text(encoding="utf-8")
        self.assertIn(old, text)
        p.write_text(text.replace(old, new, 1), encoding="utf-8")

    def seal(self, **kw):
        r = rseal.prepare(self.task, slug="xinghe-revenue", **kw)
        self.led.add("reviews", {"type": "research_review", "reviewer": "复核员（测试）", "at": "2026-10-23T12:00:00+08:00",
                                 "conclusion": "测试复核", "checks": REVIEW, "digest": r["digest"]})
        return r, rseal.publish(self.task, r["package_id"])


class WorkstreamTest(Base):
    def test_add_creates_task_metadata_and_staging(self):
        self.assertEqual(research.main([
            "workstream", "add", str(self.task), "A", "--role", "market-and-data",
            "--question", "市场是否足够大？",
        ]), 0)
        task_file = self.task / "03r_research" / "tasks" / "A.md"
        metadata = json.loads((self.task / "03r_research" / "tasks" / "A.json").read_text(encoding="utf-8"))
        self.assertIn("市场是否足够大？", task_file.read_text(encoding="utf-8"))
        self.assertEqual((metadata["code"], metadata["role"], metadata["status"]),
                         ("A", "market-and-data", "awaiting_handoff"))
        self.assertEqual(metadata["kind"], "research_workstream")
        self.assertTrue((self.task / "03_evidence" / "ledger" / "staging" / "A").is_dir())

    def test_add_rejects_duplicate_code(self):
        args = ["workstream", "add", str(self.task), "A", "--role", "market-and-data", "--question", "市场？"]
        self.assertEqual(research.main(args), 0)
        self.assertNotEqual(research.main(args), 0)

    def test_add_with_preexisting_staging_prefix_leaves_no_partial_files(self):
        staging = self.task / "03_evidence" / "ledger" / "staging" / "A"
        staging.mkdir(parents=True)
        result = research.main([
            "workstream", "add", str(self.task), "A", "--role", "market-and-data", "--question", "市场？",
        ])
        self.assertNotEqual(result, 0)
        self.assertFalse((self.task / "03r_research" / "tasks" / "A.md").exists())
        self.assertFalse((self.task / "03r_research" / "tasks" / "A.json").exists())

    def test_add_and_decide_reject_blank_fields(self):
        for flag in ("--role", "--question"):
            args = ["workstream", "add", str(self.task), "A", "--role", "market", "--question", "question"]
            args[args.index(flag) + 1] = "   "
            self.assertNotEqual(research.main(args), 0)
        research.main(["workstream", "add", str(self.task), "A", "--role", "market", "--question", "question"])
        handoff = pathlib.Path(self.tmp.name) / "A.json"
        handoff.write_text(json.dumps(valid_handoff()), encoding="utf-8")
        research.main(["workstream", "handoff", str(self.task), "A", str(handoff)])
        self.assertNotEqual(research.main([
            "workstream", "decide", str(self.task), "A", "--status", "accepted", "--reason", "  ",
        ]), 0)

    def test_handoff_update_rolls_back_and_retry_succeeds_after_second_replace_fails(self):
        research.main(["workstream", "add", str(self.task), "A", "--role", "market-and-data", "--question", "市场？"])
        handoff = pathlib.Path(self.tmp.name) / "A.json"
        handoff.write_text(json.dumps(valid_handoff()), encoding="utf-8")
        real_replace = research.os.replace
        calls = 0

        def fail_second(src, dst):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected")
            return real_replace(src, dst)

        with mock.patch.object(research.os, "replace", side_effect=fail_second):
            self.assertNotEqual(research.main(["workstream", "handoff", str(self.task), "A", str(handoff)]), 0)
        self.assertFalse((self.task / "research-handoffs" / "A.json").exists())
        metadata = json.loads((self.task / "03r_research" / "tasks" / "A.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["status"], "awaiting_handoff")
        self.assertEqual(research.main(["workstream", "handoff", str(self.task), "A", str(handoff)]), 0)

    def test_decide_update_rolls_back_and_retry_succeeds_after_second_replace_fails(self):
        research.main(["workstream", "add", str(self.task), "A", "--role", "market-and-data", "--question", "市场？"])
        handoff = pathlib.Path(self.tmp.name) / "A.json"
        handoff.write_text(json.dumps(valid_handoff()), encoding="utf-8")
        research.main(["workstream", "handoff", str(self.task), "A", str(handoff)])
        real_replace = research.os.replace
        calls = 0

        def fail_second(src, dst):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected")
            return real_replace(src, dst)

        with mock.patch.object(research.os, "replace", side_effect=fail_second):
            self.assertNotEqual(research.main([
                "workstream", "decide", str(self.task), "A", "--status", "accepted", "--reason", "reviewed",
            ]), 0)
        stored = json.loads((self.task / "research-handoffs" / "A.json").read_text(encoding="utf-8"))
        self.assertNotIn("project_manager_disposition", stored)
        self.assertEqual(research.main([
            "workstream", "decide", str(self.task), "A", "--status", "accepted", "--reason", "reviewed",
        ]), 0)

    def test_handoff_validates_schema_and_cannot_set_disposition(self):
        research.main(["workstream", "add", str(self.task), "A", "--role", "market-and-data", "--question", "市场？"])
        handoff = pathlib.Path(self.tmp.name) / "handoff.json"
        bad = valid_handoff()
        del bad["summary"]
        handoff.write_text(json.dumps(bad), encoding="utf-8")
        self.assertNotEqual(research.main(["workstream", "handoff", str(self.task), "A", str(handoff)]), 0)
        bad = valid_handoff()
        bad["project_manager_disposition"] = "accepted"
        handoff.write_text(json.dumps(bad), encoding="utf-8")
        self.assertNotEqual(research.main(["workstream", "handoff", str(self.task), "A", str(handoff)]), 0)

        handoff.write_text(json.dumps(valid_handoff()), encoding="utf-8")
        self.assertEqual(research.main(["workstream", "handoff", str(self.task), "A", str(handoff)]), 0)
        stored = json.loads((self.task / "research-handoffs" / "A.json").read_text(encoding="utf-8"))
        self.assertNotIn("project_manager_disposition", stored)

    def test_each_project_manager_disposition_is_recorded_separately(self):
        for code, status in (("A", "accepted"), ("B", "needs_revision"), ("D", "rejected")):
            research.main(["workstream", "add", str(self.task), code, "--role", "market-and-data", "--question", "市场？"])
            handoff = pathlib.Path(self.tmp.name) / f"{code}.json"
            handoff.write_text(json.dumps(valid_handoff(code)), encoding="utf-8")
            research.main(["workstream", "handoff", str(self.task), code, str(handoff)])
            self.assertEqual(research.main([
                "workstream", "decide", str(self.task), code, "--status", status, "--reason", "PM review",
            ]), 0)
            stored = json.loads((self.task / "research-handoffs" / f"{code}.json").read_text(encoding="utf-8"))
            metadata = json.loads((self.task / "03r_research" / "tasks" / f"{code}.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["project_manager_disposition"], status)
            self.assertEqual((metadata["status"], metadata["decision_reason"]), (status, "PM review"))


class CaptureTest(Base):
    def cap(self, path, slug, **kw):
        return rcapture.capture(self.task, BASE + path, slug, **kw)

    def test_html_to_markdown_with_metadata_and_hashes(self):
        r = self.cap("/report.html", "report-copy")
        meta, body = snapshot.read(self.ev / r["snapshot"])
        self.assertIn("# 2025 年经营情况", body)
        self.assertIn("| 2025 | 3200 |", body)
        self.assertNotIn("var paywall", body)                           # 脚本里的 captcha 字样不误拦
        row = self.led.get("sources", r["id"])
        self.assertEqual((row["title"], row["author_org"], row["published"], row["published_precision"]),
                         ("星河数据科技 2025 年年报摘要", "星河数据科技", "2026-03-28", "day"))
        self.assertEqual(len(row["original_files"][0]["sha256"]), 64)
        self.assertIn("content-type=text/html", row["access_note"])

    def test_gbk_page_is_decoded(self):
        r = self.cap("/news-gbk.html", "gbk-copy")
        self.assertIn("数据服务市场规模约 120 亿元", snapshot.read(self.ev / r["snapshot"])[1])
        self.assertEqual(r["extractor"], "html(gb18030)")     # GBK 按超集 GB18030 解码

    def test_paywall_is_registered_as_metadata_only(self):
        r = self.cap("/paywall.html", "paywall")
        self.assertEqual((r["ok"], r["reason"], r["block_kind"]), (False, "access_blocked", "paywall"))
        row = self.led.get("sources", r["id"])
        self.assertEqual((row["access"], row["original_files"]), ("metadata_only", []))
        self.assertIn("不绕过", row["access_note"])

    def test_long_article_about_paywalls_is_not_blocked(self):
        self.assertEqual(self.cap("/long-about-paywalls.html", "long-article")["access"], "full")

    def test_access_denied_registers_nothing(self):
        with self.assertRaises(rcapture.CaptureError) as cm:
            self.cap("/denied.html", "denied")
        self.assertEqual((cm.exception.code, cm.exception.reason), (2, "access_denied"))
        self.assertEqual(len(self.led.read("sources")), 2)

    def test_retry_after_server_error(self):
        RF.Handler.flaky = 0
        self.assertTrue(self.cap("/flaky.html", "flaky")["ok"])

    def test_oversize_and_truncation(self):
        r = self.cap("/big.bin", "big", max_bytes=1000)
        self.assertEqual((r["reason"], self.led.get("sources", r["id"])["access"]), ("oversize", "metadata_only"))
        r = self.cap("/long-about-paywalls.html", "short", max_chars=500)
        self.assertEqual(r["access"], "partial")
        self.assertIn("已截断", snapshot.read(self.ev / r["snapshot"])[1])

    def test_text_binary_and_pdf(self):
        self.assertIn("续约率", snapshot.read(self.ev / self.cap("/notes.txt", "notes")["snapshot"])[1])
        local = pathlib.Path(self.tmp.name) / "blob.bin"
        local.write_bytes(b"\x00\x01")
        r = rcapture.capture(self.task, str(local), "blob")
        self.assertEqual(r["access"], "metadata_only")
        self.assertIn("binary:", self.led.get("sources", r["id"])["access_note"])

    def test_pdf_pages_are_marked(self):
        if not shutil.which("pdftotext"):
            if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
                self.fail("缺少：pdftotext")
            self.skipTest("缺少：pdftotext")
        pdf = pathlib.Path(self.tmp.name) / "two.pdf"
        pdf.write_bytes(minimal_pdf(["Page one revenue", "Page two margin"]))
        body = snapshot.read(self.ev / rcapture.capture(self.task, str(pdf), "two-pages")["snapshot"])[1]
        self.assertIn("<!-- p.1 -->", body)
        self.assertIn("<!-- p.2 -->", body)
        self.assertIn("Page two margin", body)

    def test_ids_slugs_and_user_files(self):
        before = (self.ev / "raw/files/M001-annual-report.html").read_bytes()
        for kw, reason in (({"sid": "M001"}, "id_already_exists"), ({"sid": "m1"}, "bad_id")):
            with self.assertRaises(rcapture.CaptureError) as cm:
                self.cap("/report.html", "again", **kw)
            self.assertEqual((cm.exception.code, cm.exception.reason), (3, reason))
        self.assertEqual((self.ev / "raw/files/M001-annual-report.html").read_bytes(), before)
        with self.assertRaises(rcapture.CaptureError) as cm:
            self.cap("/report.html", "Bad Slug")
        self.assertEqual(cm.exception.reason, "bad_slug")
        user = pathlib.Path(self.tmp.name) / "plan.txt"
        user.write_text("用户提供的计划书", encoding="utf-8")
        r = rcapture.capture(self.task, str(user), "user-plan", line="U")
        row = self.led.get("sources", r["id"])
        self.assertEqual((r["id"], row["origin"], row["capture_method"]), ("U001", "user", "user_file"))
        self.assertTrue(row["original_files"][0]["path"].startswith("raw/user/"))

    def test_lite_package(self):
        research.main(["lite", self.tmp.name, "--slug", "quick", "--question", "收入是多少"])
        lite = next((pathlib.Path(self.tmp.name) / "work").glob("*-quick-lite"))
        r = rcapture.capture(lite, BASE + "/report.html", "report", lite=True)
        (lite / "answer.md").write_text(f"2025 年收入 3200 万元（{r['id']}）。\n", encoding="utf-8")
        self.assertEqual(rcheck.run(lite, profile="lite")["errors"], [])
        (lite / "answer.md").write_text("见 M009。\n", encoding="utf-8")
        self.assertIn("M009 没有快照", "\n".join(rcheck.run(lite, profile="lite")["errors"]))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class BrowserCaptureTest(Base):
    def test_browser_capture_saves_html_and_screenshot(self):
        need = [x for x, ok in (("Chrome", pathlib.Path(runtime.CHROME).exists()), ("虚拟环境", runtime.venv_python().is_file())) if not ok]
        if need:
            if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
                self.fail(f"缺少：{'、'.join(need)}")
            self.skipTest(f"缺少：{'、'.join(need)}")
        port = free_port()
        profile = tempfile.mkdtemp()
        chrome = subprocess.Popen([runtime.CHROME, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
                                   "--no-first-run", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                    break
                except OSError:
                    time.sleep(0.2)
            r = rcapture.capture(self.task, BASE + "/report.html", "browser-copy", browser=True, cdp=f"http://127.0.0.1:{port}")
        finally:
            chrome.terminate()
            chrome.wait(10)
            shutil.rmtree(profile, ignore_errors=True)
        row = self.led.get("sources", r["id"])
        self.assertEqual(row["capture_method"], "browser")
        self.assertEqual([pathlib.Path(o["path"]).suffix for o in row["original_files"]], [".html", ".png"])
        self.assertIn("营业收入 3200 万元", snapshot.read(self.ev / r["snapshot"])[1])


class TaskCheckTest(Base):
    def test_fixture_passes(self):
        r = self.check()
        self.assertEqual((r["status"], r["errors"]), ("PASS_AUTOMATED", []))
        self.assertEqual((r["stats"]["quotes_checked"], r["stats"]["data_records"], r["stats"]["report_data_links"]), (2, 3, 1))

    def test_tampered_excerpt_hash_and_unregistered_file(self):
        rows = self.led.read("evidence")
        rows[0]["excerpt"] = rows[0]["excerpt"].replace("3200", "3300")
        (self.ev / "ledger/evidence.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
        (self.ev / "raw/files/M002-market-news.html").write_bytes(b"changed")
        (self.ev / "raw/files/stray.pdf").write_bytes(b"x")
        text = self.errors(self.check())
        self.assertIn("摘录在 M001 的快照正文里找不到", text)
        self.assertIn("哈希与登记不一致", text)
        self.assertIn("原件没有被任何快照登记：raw/files/stray.pdf", text)

    def test_excerpt_fragments_must_keep_order(self):
        self.assertEqual(rcheck.quote_matches("营业收入 3200 万元[...]上年为 1800", "公司全年营业收入 3200 万元，上年为 1800 万元。"), (2, True))
        self.assertEqual(rcheck.quote_matches("上年为 1800[...]营业收入 3200 万元", "公司全年营业收入 3200 万元，上年为 1800 万元。")[1], False)
        self.assertEqual(rcheck.quote_matches("“营业收入”：3200", "营业收入\"：3200"), (1, False))
        self.assertTrue(rcheck.quote_matches("**营业收入** 3200 万元（合并）", "营业收入 3200 万元(合并)")[1])   # 标记和全半角标点归一

    def test_snapshot_is_the_source_of_truth(self):
        self.led.patch("sources", "M002", {"title": "改过的标题"})
        self.assertIn("证据账 sources:M002：title 与快照头不一致", self.errors(self.check()))

    def test_search_status_both_directions(self):
        self.led.patch("project", "project", {"search_status": "not_applicable"})
        self.assertIn("有实际检索，但 search_status 声明为 not_applicable", self.errors(self.check()))
        (self.ev / "ledger/search_log.jsonl").write_text("", encoding="utf-8")
        self.led.patch("project", "project", {"search_status": "performed"})
        self.assertIn("没有任何检索记录", self.errors(self.check()))

    def test_search_log_weak_checks(self):
        self.led.add("search_log", {"searched_at": "2026-10-23T11:00:00+08:00", "tool": "web_search", "query": "补充检索",
                                    "research_line": "M", "status": "found", "opened_source_ids": ["M009"]})
        self.assertIn("「打开并存档」里的 M009 没有快照", "\n".join(self.check()["warnings"]))

    def data(self, name, old, new):
        self.replace(self.ev / "data" / name, old, new)
        return self.errors(self.check())

    def test_missing_value_cannot_be_zero(self):
        self.assertIn("不能填 0", self.data("extracted/M-revenue.csv", "1800,number,万元,2024,中国,合并,reported,present", "0,number,万元,2024,中国,合并,reported,missing"))

    def test_numeric_context_and_types(self):
        self.assertIn("缺少口径字段 unit", self.data("extracted/M-revenue.csv", "3200,number,万元,", "3200,number,,"))

    def test_nan_and_unit_mixed_values(self):
        self.assertIn("不是有限数", self.data("extracted/M-revenue.csv", "3200,number,万元", "3200万,number,万元"))

    def test_duplicate_record_and_lineage(self):
        text = self.data("curated/M-growth.csv", "M-R0003,", "M-R0002,")
        self.assertIn("record_id 在全包范围内重复", text)

    def test_missing_input_cycle_and_layer_rules(self):
        self.assertIn("输入 M-R0009 不存在", self.data("curated/M-growth.csv", "M-R0001;M-R0002", "M-R0009;M-R0002"))
        self.replace(self.ev / "data/curated/M-growth.csv", "M-R0009;M-R0002", "M-R0003")
        self.assertIn("循环依赖", self.errors(self.check()))

    def test_extracted_and_curated_are_mutually_exclusive(self):
        self.assertIn("提取层不能有派生字段", self.data("extracted/M-revenue.csv", "1800 万元,,,", "1800 万元,M-R0002,analysis/growth.md,"))
        self.replace(self.ev / "data/extracted/M-revenue.csv", "1800 万元,M-R0002,analysis/growth.md,", "1800 万元,,,")
        self.assertIn("整理层不能直接写来源", self.data("curated/M-growth.csv", "present,,,,M-R0001", "present,M001,,,M-R0001"))

    def test_method_must_live_in_analysis(self):
        self.assertIn("method 必须指向 analysis/", self.data("curated/M-growth.csv", "analysis/growth.md", "notes/growth.md"))
        self.replace(self.ev / "data/curated/M-growth.csv", "notes/growth.md", "analysis/../ledger/x.md")
        self.assertIn("路径非法或不存在", self.errors(self.check()))

    def test_dictionary_and_orphan_tables(self):
        (self.ev / "data/extracted/orphan.csv").write_text("record_id\nX\n", encoding="utf-8")
        self.replace(self.ev / "data/dictionary.csv", "revenue,missing_reason,string,missing_reason 字段,n/a,空字符串表示缺失\n", "")
        text = self.errors(self.check())
        self.assertIn("孤立数据表", text)
        self.assertIn("字段 missing_reason 没有在 dictionary.csv 登记", text)

    def test_data_status_must_match_content(self):
        self.led.patch("project", "project", {"data_status": "not_applicable"})
        self.assertIn("data_status=not_applicable，但 data 下有数据文件", self.errors(self.check()))

    def report(self, old, new):
        self.replace(self.task / "03r_research/report.md", old, new)
        return self.check()

    def test_citations(self):
        r = self.report("公司份额很小。", "公司份额很小[3]；2024 年的数字见 [2024]，范围见[1-2]，代码 `[9]` 不算。")
        self.assertEqual([e for e in r["errors"] if "[" in e], ["正文引用了参考列表里没有的 [3]"])

    def test_unreferenced_entry_and_zero_coverage(self):
        r = self.report("较上年增长约 77.8%[1]", "较上年增长约 77.8%")
        self.assertIn("参考条目 [1] 没有被正文引用", "\n".join(r["warnings"]))
        self.report("（行业协会估计）[2]", "（行业协会估计）")
        r = self.report("一家机构的估计[2]", "一家机构的估计")
        self.assertIn("正文没有任何引用", self.errors(r))

    def test_reference_link_must_match_snapshot(self):
        r = self.report("[M001-annual-report.md](../03_evidence/raw/sources/M001-annual-report.md)", "[x](../03_evidence/raw/files/M001-annual-report.html)")
        self.assertIn("链接与来源 M001 的快照不对应", self.errors(r))

    def test_data_links(self):
        r = self.report("[数据:M-R0003]", "[数据:M-R0099]")
        self.assertIn("数据关联 M-R0099：记录不存在", self.errors(r))
        r = self.report("[数据:M-R0099](../03_evidence/data/curated/M-growth.csv)", "")
        self.assertIn("报告正文没有任何 [数据:记录ID](路径) 关联", self.errors(r))

    def test_key_claim_weak_check(self):
        self.led.add("claims", {"kind": "estimate", "statement": "市场规模约 120 亿元", "scope": "consolidated", "period": "2025", "population": "数据服务市场",
                                "unit": "亿元", "denominator": "不适用", "calculation": "不适用", "inference": "市场规模参考", "limitation": "单一机构估计",
                                "verification": "single_source", "confidence": "medium", "confidence_reason": "单一来源", "affects_conclusion": True, "materiality": "major",
                                "assumptions": "沿用行业协会口径"})
        self.led.add("claim_evidence", {"claim_id": "cl-0001", "evidence_id": "ev-0002", "relation": "supports", "applicable_scope": "全国"})
        self.assertIn("关键主张 cl-0001：只有 1 个独立来源", "\n".join(self.check()["warnings"]))

    def test_symlink_and_final_on_task(self):
        self.assertIn("只用于研究包", self.errors(self.check(final=True)))
        (self.ev / "raw/files/link.html").symlink_to(self.ev / "raw/files/M001-annual-report.html")
        self.assertIn("不允许符号链接", self.errors(self.check()))


class PackageTest(Base):
    def test_seal_publish_and_final(self):
        prep, pub = self.seal()
        pkg = pathlib.Path(pub["package"])
        self.assertEqual(pub["final"]["status"], "PASS_FINAL")
        self.assertTrue(pathlib.Path(pub["zip"]).is_file())
        self.assertFalse(rseal.staging_dir(self.task, prep["package_id"]).exists())
        self.assertEqual(subprocess.run(["shasum", "-a", "256", "-c", "--quiet", "manifest-sha256.txt"], cwd=pkg).returncode, 0)
        self.assertIn("| data_records | 3 |", (pkg / "README.md").read_text(encoding="utf-8"))
        meta, _ = snapshot.read(pkg / "raw/sources/M001-annual-report.md")
        self.assertEqual((meta["tier"], meta["grade"], meta["language"]), ("primary", "A", "unknown"))
        self.assertIn("[数据:M-R0003](data/curated/M-growth.csv)", (pkg / "report.md").read_text(encoding="utf-8"))
        e = next(x for x in Acceptance(self.task).load()["deliverables"] if x["kind"] == "research_package")
        self.assertEqual([c["result"] for c in e["upstream_checks"]], ["passed"])

    def test_publish_requires_current_review(self):
        prep = rseal.prepare(self.task, slug="xinghe-revenue")
        with self.assertRaises(rseal.SealError) as cm:
            rseal.publish(self.task, prep["package_id"])
        self.assertIn("没有针对当前暂存副本的人工复核", str(cm.exception))
        self.led.add("reviews", {"type": "research_review", "reviewer": "复核员", "at": "2026-10-23T12:00:00+08:00", "conclusion": "x",
                                 "checks": REVIEW, "digest": prep["digest"]})
        self.replace(pathlib.Path(prep["staging"]) / "report.md", "公司份额很小。", "公司份额很小，增长很快。")
        with self.assertRaises(rseal.SealError):
            rseal.publish(self.task, prep["package_id"])
        self.assertFalse(rseal.published_dir(self.task, prep["package_id"]).exists())

    def test_tampering_after_publish(self):
        _, pub = self.seal()
        pkg = pathlib.Path(pub["package"])
        before = {p: p.read_bytes() for p in pkg.rglob("*") if p.is_file()}
        again = rcheck.run(pkg, write_manifest=True)
        self.assertIn("已经封包", "\n".join(again["errors"]))
        self.assertEqual({p: p.read_bytes() for p in pkg.rglob("*") if p.is_file()}, before)
        self.replace(pkg / "README.md", "研究包", "研究包（改）")
        (pkg / "notes" / "extra.md").write_text("## E-9 新增\n- 来源: `M001` · 定位: x\n- 逐字摘录:\n  > 公司全年营业收入 3200 万元\n", encoding="utf-8")
        text = "\n".join(rcheck.run(pkg, final=True)["errors"])
        self.assertIn("README.md 的哈希不一致", text)
        self.assertIn("manifest 没有覆盖 notes/extra.md", text)
        self.assertIn("人工复核已过期", text)

    def test_package_index_and_layout_checks(self):
        prep = rseal.prepare(self.task, slug="xinghe-revenue")
        st = pathlib.Path(prep["staging"])
        self.replace(st / "sources.md", "| 全文 | 脚本采集 | raw/sources/M001", "| 部分 | 脚本采集 | raw/sources/M001")
        (st / "brief.md").write_text("旧布局", encoding="utf-8")
        text = "\n".join(rcheck.run(st)["errors"])
        self.assertIn("sources.md 中 M001 的「完整度」与快照不一致", text)
        self.assertIn("研究包里混有旧布局：brief.md", text)

    def test_legacy_package(self):
        legacy = pathlib.Path(self.tmp.name) / "legacy"
        (legacy / "raw").mkdir(parents=True)
        r = rcheck.run(legacy, write_manifest=True)
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("legacy", "\n".join(r["warnings"]))
        self.assertFalse((legacy / "manifest-sha256.txt").exists())

    def test_revision_and_slim(self):
        _, pub = self.seal()
        old = pathlib.Path(pub["package"]).name
        rcapture.capture(self.task, BASE + "/notes.txt", "uncited-notes")
        prep = rseal.prepare(self.task, revise_of=old, slim=True)
        st = pathlib.Path(prep["staging"])
        self.assertEqual(prep["package_id"], f"{old}-r2")
        self.assertEqual(json.loads((st / "package.json").read_text(encoding="utf-8"))["supersedes"], old)
        self.assertFalse(list((st / "raw/sources").glob("M003-*")))          # 精简：没被引用的来源不收
        self.assertIn("按用户要求精简", (st / "README.md").read_text(encoding="utf-8"))

    def test_review_digest_cli(self):
        prep = rseal.prepare(self.task, slug="xinghe-revenue")
        out = subprocess.run([sys.executable, str(HERE.parent / "research.py"), "check", prep["staging"], "--review-digest"],
                             capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), prep["digest"])


if __name__ == "__main__":
    unittest.main()
