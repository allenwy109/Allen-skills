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
    led.add("claims", claim(kind="forecast", statement="2026 年收入约 4100 万元", period="2026 全年", assumptions="沿用管理层指引", metric_refs=["m-0007"],
                            verification="single_source", confidence="medium"))
    led.add("claim_evidence", {"claim_id": "cl-0001", "evidence_id": "ev-0001", "relation": "supports", "applicable_scope": "合并口径"})
    return led


def make_report_ledger(task):
    """在 make_ledger 的基础上补报告要用的内容：
    cl-0004 建议（有证据支持）；cl-0005 未核实但影响结论（报告里应改写为"（待确认）"的假设）；
    card-0001 A 级卡片关联 cl-0001；card-0002 B 级卡片关联 cl-0003；ev-0002 支持 cl-0003。"""
    led = make_ledger(task)
    led.add("evidence", {"source_id": "M001", "locator": "p30", "excerpt": "管理层预计 2026 年收入约 4100 万元", "attribute": "forecast", "numeric": False})
    led.add("claims", claim(kind="recommendation", statement="先核实客户留存，再决定是否扩大投入", unit="不适用：定性",
                            calculation="不适用：定性", inference="收入增长需要留存数据才能判断质量", limitation="建议基于两年数据"))
    led.add("claims", claim(kind="fact", statement="主要客户已签三年合同", verification="unverified", confidence="low",
                            confidence_reason="只有管理层口述", unit="不适用：定性", calculation="不适用：定性", inference="影响收入的可持续性"))
    led.add("claim_evidence", {"claim_id": "cl-0003", "evidence_id": "ev-0002", "relation": "supports", "applicable_scope": "合并口径"})
    led.add("claim_evidence", {"claim_id": "cl-0004", "evidence_id": "ev-0001", "relation": "supports", "applicable_scope": "合并口径"})
    led.add("cards", {"type": "data", "content": "收入两年增长近八成", "meaning": "规模增长快，但基数小", "value_tier": "A", "topic": "收入", "claim_id": "cl-0001",
                      "source_refs": [{"source_id": "M001", "locator": "p12"}]})
    led.add("cards", {"type": "data", "content": "2026 年收入指引", "meaning": "管理层预期继续增长", "value_tier": "B", "topic": "收入", "claim_id": "cl-0003",
                      "source_refs": [{"source_id": "M001", "locator": "p30"}]})
    return led


def report_slides():
    """报告夹具的 slides.json：封面、两页正文（分析页、行动页）、封底。"""
    def panel(pid, role, slot, purpose, claims, form, relationship, reason, **extra):
        return {"id": pid, "role": role, "slot": slot, "span": extra.pop("span", 1), "purpose": purpose, "claim_refs": claims,
                "form": form, "relationship": relationship, "reason": reason, **extra}
    return {
        "deck": {"title": "星河数据科技经营概览", "kind": "reading", "language": "zh-CN", "audience": "投资经理", "decision": "是否继续跟进",
                 "story_mode": "company_research", "arc": "evidence-to-view", "ratio": "16x9",
                 "brief": {"question": "星河数据科技的收入增长能否支持继续跟进？", "purpose": "diagnosis", "scope": "星河数据科技合并口径",
                           "period": "2024–2026", "baseline": "2024 年收入", "constraints": "缺少客户留存和利润数据",
                           "success_criteria": "区分已核实的收入变化和待补的增长质量"},
                 "answer_claim_refs": ["cl-0001"],
                 "cover": {"subtitle": "虚构样稿，仅用于工具验证", "producer": "Allen 分析系统", "date": "2026-10-23", "version": "v1",
                           "project": "星河数据科技", "closing_text": "谢谢"}},
        "slides": [
            {"page": 1, "type": "cover", "action_title": "星河数据科技经营概览", "page_role": "cover", "story_beat": "context"},
            {"page": 2, "type": "data_chart", "action_title": "收入两年增长 77.8%，规模仍小", "section": "01 收入",
             "page_role": "analysis", "story_beat": "diagnosis", "subtitle": "单位：万元｜2024–2025 全年｜合并口径",
             "proves": "收入从 1800 万元增至 3200 万元", "adds": "读者知道收入增长的幅度和绝对规模",
             "claim_refs": ["cl-0001"], "metric_refs": ["m-0001", "m-0002", "m-0003"],
             "density": {"profile": "balanced", "space_intent": "主图充分展开，右侧写口径和边界",
                         "evidence_units": [{"role": "primary", "purpose": "两年收入同量尺比较"}, {"role": "support", "purpose": "说明收入口径和推论边界"}]},
             "visual_intent": {"relationship": "comparison", "form": "svg.custom", "layout": "custom", "reading_path": "标题 → 两年柱形 → 口径与边界",
                               "layout_reason": "主图占左侧三分之二，右侧写口径和边界"},
             "panels": [panel("bars", "primary", "main", "两年收入同量尺比较，看出增长幅度", ["cl-0001"], "svg.custom", "comparison",
                              "两期数值共用零基线，柱形比较绝对规模最直接", visual="两年收入柱形", semantic_type="comparison", span=2),
                        panel("note", "support", "aside", "说明收入口径和不能推出的结论", ["cl-0001"], "html.text", "text",
                              "口径和边界是文字判断，用短段落最清楚")],
             "relations": [{"id": "bars-note", "kind": "boundary", "panel_refs": ["bars", "note"], "reason": "右侧文字限定左图能支持的结论范围"}]},
            {"page": 3, "type": "recommendation", "action_title": "先核实客户留存，再决定是否扩大投入", "section": "02 建议",
             "page_role": "action", "story_beat": "action", "subtitle": "建议｜依据：收入变化与管理层指引",
             "proves": "增长质量需要留存数据，才能支持扩大投入", "adds": "读者知道下一步先补什么数据、再做什么决定",
             "claim_refs": ["cl-0003", "cl-0004", "cl-0005"], "metric_refs": ["m-0007"],
             "density": {"profile": "balanced", "space_intent": "左侧单个指标，右侧条件表",
                         "evidence_units": [{"role": "context", "purpose": "2026 年指引作为规模参考"}, {"role": "primary", "purpose": "建议与对应的前提条件"}]},
             "visual_intent": {"relationship": "decision", "form": "html.table", "layout": "custom", "reading_path": "标题 → 指引 → 建议与待确认事项",
                               "layout_reason": "左侧指标卡给出规模参考，右侧表格写建议和前提"},
             "panels": [panel("kpi", "context", "left", "给出 2026 年收入指引的规模参考", ["cl-0003"], "html.kpi", "kpi",
                              "单个预测值用指标卡突出，并标明预测身份", capacity={"items": 1}),
                        panel("steps", "primary", "right", "建议和待确认事项逐项对应", ["cl-0004", "cl-0005"], "html.table", "decision",
                              "建议与前提需要逐行对应，表格比段落清楚", span=2)],
             "relations": [{"id": "kpi-steps", "kind": "complement", "panel_refs": ["kpi", "steps"], "reason": "指引说明规模，表格说明扩大投入前先补的证据"}]},
            {"page": 4, "type": "close", "action_title": "谢谢", "page_role": "close", "story_beat": "close"}]}


def report_sidecar():
    return {"speaker_notes": [{"page": 2, "text": "先看两年柱形：收入从 1800 万元到 3200 万元，增长 77.8%。"},
                              {"page": 3, "text": "指引是 4100 万元，但扩大投入前要先拿到留存数据。"}],
            "backup_pages": [], "confirmation_points": []}


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
