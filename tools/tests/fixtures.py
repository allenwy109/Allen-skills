"""测试共用的夹具：一家虚构公司"星河数据科技"的证据账，以及工具检查。内容全部虚构。"""
import os
import pathlib
import shutil
import subprocess

from tools.lib import office, runtime
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
                "form": form, "relationship": relationship, "reason": reason,
                "semantic_type": extra.pop("semantic_type", "point_evidence"), **extra}
    return {
        "deck": {"title": "星河数据科技经营概览", "kind": "reading", "language": "zh-CN", "audience": "投资经理", "decision": "是否继续跟进",
                 "story_mode": "company_research", "arc": "evidence-to-view", "ratio": "16x9",
                 "brief": {"question": "星河数据科技的收入增长能否支持继续跟进？", "purpose": "diagnosis", "scope": "星河数据科技合并口径",
                           "period": "2024–2026", "baseline": "2024 年收入", "constraints": "缺少客户留存和利润数据",
                           "success_criteria": "区分已核实的收入变化和待补的增长质量"},
                 "answer_claim_refs": ["cl-0001"],
                 "decision_structure": {
                     "decision_level": "有条件继续跟进",
                     "decisive_reasons": ["收入两年增长 77.8%", "绝对规模仍小", "客户留存与合同期限尚未核实"],
                     "largest_upside": "留存良好时进入利润与现金流正式尽调",
                     "largest_risk": "一次性大单造成增长质量误判",
                     "immediate_actions": ["取得客户留存数据", "核实主要合同期限"],
                     "thresholds": {"continue": "留存良好且主要合同期限得到核实", "stop": "留存不理想或主要合同无法核实"},
                 },
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
             "anchor_panel": "bars",
             "panels": [panel("bars", "primary", "main", "两年收入同量尺比较，看出增长幅度", ["cl-0001"], "svg.custom", "comparison",
                              "两期数值共用零基线，柱形比较绝对规模最直接", visual="两年收入柱形", semantic_type="point_evidence",
                              alternative="并排数字卡", tradeoff="柱形更适合比较绝对规模", capacity={"items": 2}, span=2),
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
                               "layout_reason": "左侧指标卡给出规模参考，右侧表格写建议和前提",
                               "repetition_reason": "指标背景与建议条件使用相邻证据结构，以形成同一决策阅读单元"},
             "anchor_panel": "steps",
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


STORYLINE = pathlib.Path(__file__).resolve().parents[2] / "core-storyline" / "scripts" / "storyline.py"

STORY_FILES = {
    "00_story-brief.md": """# 简报

| 项 | 内容 |
|---|---|
| 受众 | 投资经理；熟悉 SaaS 行业；最关心收入质量；有立项建议权 |
| 目的 | 判断星河数据科技是否值得继续跟进 |
| 场景 | 会前阅读；不设页数上限（假设：用户未提） |
| 语言风格 | 中文，书面，结论先行 |
| 保密 | 内部使用 |
| 外部知识 | 不引入（假设：只用公司年报） |
| 验收标准 | 能说清收入增长幅度、增长质量的缺口和下一步 |
""",
    "01_materials_index.md": """# 材料索引

| 来源 ID | 名称 | 类型 | 时间 | 作者或来源 | 可信度 | 相关度 | 体量 | 处理状态 |
|---|---|---|---|---|---|---|---|---|
| M001 | 星河数据科技 2025 年年报 | 报告 | 2026-03-28 | 公司 | 高 | 高 | 长文档（86 页） | 读完（含附录） |
""",
    "02_terms.md": """| 概念 | 材料中的叫法和口径 | 采用表述 | 说明 |
|---|---|---|---|
| 收入 | 营业收入（合并口径） | 收入 | 不含其他收益 |
""",
    "03_storyline.md": """# 故事线

故事线模式：公司研究

## 中心论点

收入两年增长近八成，但增长质量还要靠留存数据证明。

## 结构树

- 收入规模快速增长（card-0001，强）
- 下一步先补留存数据（card-0003，中）

## 压力测试

- 证据类：增长是否来自一次性大单？缺口：客户结构未披露，写入补齐路径。
- 反例类：主要客户合同期限未核实，写入风险与未知。
- 代价类：留存差则不扩大投入，止损线为不立项。
""",
    "04_manuscript.md": """# 星河数据科技经营概览

## 执行摘要

星河数据科技的收入在两年内从 1800 万元增至 3200 万元，增长 77.8%〔card-0001｜M001 p12〕。这说明规模扩张很快，但收入的绝对规模仍然偏小，单一客户的变动就可能带来明显波动，抗风险能力有限。管理层给出的 2026 年收入指引约为 4100 万元（预测）〔card-0002｜M001 p30〕，这只是公司自己的预期，不是实际经营结果，也没有给出客户数量、续约率和客单价的拆分，因此无法据此判断增长能否持续。我们建议先核实客户留存和主要合同的期限，再决定是否扩大投入〔card-0003〕。如果留存数据不理想，就不进入下一轮立项，避免为一次性的大单增长付出过高的跟进成本；如果留存良好，再补充利润和现金流的分析，进入正式尽调。

## 一、收入两年增长 77.8%，规模仍小

收入从 1800 万元增至 3200 万元〔card-0001｜M001 p12〕，增长主要发生在 2025 年。

## 二、先核实客户留存，再决定是否扩大投入

公司预计 2026 年收入约 4100 万元〔card-0002｜M001 p30〕，但没有披露客户结构。先核实留存，再决定投入〔card-0003〕。

## 结论与建议

1. 先拿到客户留存数据（优先：决定增长质量），见第二章。

## 风险、前提与待决问题

- 风险：主要客户合同期限未核实，若为短约，收入可能波动。
- 前提：年报数据真实。
- 待决：客户结构由公司财务负责人回答。

## 风险与未知

主要客户是否签了长约尚未核实。

## 补齐路径

向公司索取客户名单与合同期限【待补充：客户留存数据】。

## 方法与局限

只使用公司年报；没有利润和现金流数据。

## 附录 E 来源清单

| 编号 | 名称 |
|---|---|
| M001 | 星河数据科技 2025 年年报 |
""",
    "05_storyboard.md": """# 故事板

Deck 设定：阅读型；主 deck 4 页；备用页 0 页；合计 4 页；结尾类型：建议。

| 页码 | 章节 | 页面类型 | 行动标题 | 核心证据卡片 | 对应稿件段落 |
|---|---|---|---|---|---|
| 1 | — | 封面 | 星河数据科技经营概览 | — | — |
| 2 | 01 收入 | 数据图表 | 收入两年增长 77.8%，规模仍小 | card-0001 | 第一章 |
| 3 | 02 建议 | 建议 | 先核实客户留存，再决定是否扩大投入 | card-0002、card-0003 | 第二章 |
| 4 | — | 结尾 | 谢谢 | — | — |

横向检查：只读标题，论证完整。纵向检查：正文都支撑标题。
""",
    "06_slides.md": """# 逐页内容

## P01 ｜ — ｜ 封面
**行动标题**：星河数据科技经营概览

## P02 ｜ 01 收入 ｜ 数据图表
**行动标题**：收入两年增长 77.8%，规模仍小
**正文**：
- 收入从 1800 万元增至 3200 万元，增长 77.8%〔card-0001｜M001 p12〕
**可视化建议**：两年柱形，零基线，单位万元
**讲者备注**：先看两年柱形：收入从 1800 万元到 3200 万元，增长 77.8%〔card-0001〕。
**来源**：card-0001｜M001 p12
**追溯**：第一章；card-0001

## P03 ｜ 02 建议 ｜ 建议
**行动标题**：先核实客户留存，再决定是否扩大投入
**正文**：
- 2026 年收入指引约 4100 万元（预测）〔card-0002｜M001 p30〕
- 先核实客户留存，再决定是否扩大投入〔card-0003〕
**可视化建议**：左侧指标卡，右侧建议与前提表
**讲者备注**：指引是 4100 万元，但扩大投入前要先拿到留存数据〔card-0002〕。
**来源**：card-0002｜M001 p30；card-0003
**追溯**：第二章；card-0002、card-0003

## P04 ｜ — ｜ 结尾
**行动标题**：谢谢
""",
    "07_audit_report.md": """# 审计报告

## 1 指标摘要

A 级 1 张，已安置 1 张（card-0001）。脚本错误 0 个。

## 10 未能修正

无。
""",
}


def make_storyline_package(task):
    """完整的故事线包：报告证据账 + 07_storyline 下全部文件，并运行 cards、clean、sync。返回 Ledger。"""
    import json
    import subprocess
    import sys
    led = make_report_ledger(task)
    led.add("cards", {"type": "recommendation", "content": "先核实客户留存，再决定是否扩大投入", "meaning": "增长质量待证明",
                      "value_tier": "B", "topic": "建议", "claim_id": "cl-0004"})
    led.add("cards", {"type": "background", "content": "公司成立于 2019 年", "value_tier": "C", "topic": "背景",
                      "nature": "fact", "confidence": "high", "confidence_reason": "年报"})
    s = ensure_dir(pathlib.Path(task) / "07_storyline")
    for name, text in STORY_FILES.items():
        (s / name).write_text(text, encoding="utf-8")
    (s / "slides.json").write_text(json.dumps(report_slides(), ensure_ascii=False), encoding="utf-8")
    (s / "sidecar.json").write_text(json.dumps({"speaker_notes": [], "backup_pages": [], "confirmation_points": [
        {"stage": "storyline", "status": "auto_adopted", "note": "快速模式，自动采用推荐主线"}]}, ensure_ascii=False), encoding="utf-8")
    for cmd in ("cards", "clean", "sync"):
        p = subprocess.run([sys.executable, str(STORYLINE), cmd, str(task)], capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(f"storyline {cmd} 失败：{p.stdout}{p.stderr}")
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
    if runtime.chrome_channel() == "chromium":
        node_modules = runtime.engine_path(runtime.runtime_root(), "report-forge") / "node_modules"
        p = subprocess.run(["node", "-e", "const p=require('playwright').chromium.executablePath();require('fs').accessSync(p);"],
                           capture_output=True, text=True, env=dict(os.environ, NODE_PATH=str(node_modules)))
        if p.returncode:
            need.append("Playwright Chromium")
    elif not pathlib.Path(runtime.CHROME).is_file():
        need.append("Google Chrome")
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
