"""测试共用的夹具：一家虚构公司"星河数据科技"的证据账，以及工具检查。内容全部虚构。"""
import os
import pathlib
import shutil

from tools.lib import office
from tools.lib.ledger import Ledger


def claim(**over):
    r = {"kind": "data", "statement": "示例主张", "scope": "consolidated", "period": "2024–2025 全年", "population": "星河数据科技",
         "unit": "万元", "denominator": "不适用：单值", "calculation": "不适用：原文数字", "inference": "只说明规模",
         "limitation": "虚构数据", "verification": "verified", "confidence": "high", "confidence_reason": "虚构的一手来源",
         "affects_conclusion": True, "materiality": "major"}
    r.update(over)
    return r


def make_ledger(task):
    """建一个可以出图的证据账，返回 Ledger。
    指标：m-0001 2024 收入 1800；m-0002 2025 收入 3200；m-0003 增长率（公式）；m-0004 缺失；
         m-0005 只被未核实主张引用；m-0006 没有主张引用；m-0007 2026 收入预测 4100。"""
    led = Ledger(task)
    led.init()
    led.add("sources", {"origin": "web", "title": "星河数据科技 2025 年年报", "url": "https://example.com/report", "published": "2026-03-28",
                        "published_precision": "day", "accessed": "2026-10-22T10:00:00+08:00", "tier": "primary", "grade": "S",
                        "capture_method": "script", "access": "full"}, line="M")
    led.add("evidence", {"source_id": "M001", "locator": "p12", "excerpt": "营业收入 3200 万元，上年 1800 万元", "attribute": "actual", "numeric": False})
    for value in (1800, 3200):
        led.add("metrics", {"unit": "万元", "decimals": 0, "status": "present", "value": value})
    led.add("metrics", {"unit": "%", "decimals": 1, "status": "present", "formula": {"op": "percent_change", "args": ["m-0002", "m-0001"]}})
    led.add("metrics", {"unit": "万元", "decimals": 0, "status": "missing", "status_reason": "未披露"})
    led.add("metrics", {"unit": "万元", "decimals": 0, "status": "present", "value": 999})
    led.add("metrics", {"unit": "万元", "decimals": 0, "status": "present", "value": 1})
    led.add("metrics", {"unit": "万元", "decimals": 0, "status": "approximate", "status_reason": "管理层指引", "value": 4100})
    led.add("claims", claim(statement="收入从 1800 万元增至 3200 万元", metric_refs=["m-0001", "m-0002", "m-0003", "m-0004"]))
    led.add("claims", claim(statement="某渠道收入 999 万元", verification="unverified", confidence="low", confidence_reason="只有模型记忆",
                            metric_refs=["m-0005"]))
    led.add("claims", claim(kind="forecast", statement="2026 年收入约 4100 万元", assumptions="沿用管理层指引", metric_refs=["m-0007"],
                            verification="single_source", confidence="medium"))
    led.add("claim_evidence", {"claim_id": "cl-0001", "evidence_id": "ev-0001", "relation": "supports", "applicable_scope": "合并口径"})
    return led


def revenue_chart(**over):
    chart = {"id": "revenue", "type": "column", "title": "星河数据科技收入两年增长近八成", "subtitle": "", "unit": "万元",
             "source_ids": ["M001"],
             "data": {"categories": ["2024", "2025"], "series": [{"name": "收入", "values": [{"metric": "m-0001"}, {"metric": "m-0002"}]}]}}
    chart.update(over)
    return chart


def missing_tools(*tools):
    need = [t for t in tools if not shutil.which(t)]
    try:
        office.soffice_path()
    except office.OfficeError:
        need.append("soffice")
    return need


def require_tools(test_case, *tools):
    """缺工具时：默认跳过；设置 ALLEN_REQUIRE_TOOLS=1 时直接失败（完整自检不允许空过）。"""
    need = missing_tools(*tools)
    if need:
        msg = f"缺少工具：{', '.join(need)}"
        if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
            test_case.fail(msg)
        test_case.skipTest(msg)


def ensure_dir(p):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)
    return pathlib.Path(p)
