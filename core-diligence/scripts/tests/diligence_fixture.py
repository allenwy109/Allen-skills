"""测试专用：一个虚构公司"云帆智造科技有限公司"的尽调任务（未上市、公司研究、Quick）。内容全部虚构。

make_diligence_task：证据账、模块分析、报告内容、完成复核、22 条人工清单——到 diligence check --mode completed 和
check-content --final 都能通过为止。write_split：转母版之后，作者写的故事板、逐页稿、slides.json（含 block_ids）和审计报告。
"""
import json
import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import diligence  # noqa: E402,F401  （导入时完成运行时定位）
import dcontent  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

AS_OF = "2026-10-20"


def claim(**over):
    r = {"kind": "fact", "statement": "示例", "entity_id": "ENT-0001", "scope": "consolidated", "period": "2024–2025 全年", "population": "云帆智造合并口径",
         "unit": "不适用：定性", "denominator": "不适用：单值", "calculation": "不适用：原文", "inference": "说明公司的基本情况", "limitation": "虚构数据",
         "verification": "verified", "confidence": "high", "confidence_reason": "工商登记与审计报告", "affects_conclusion": True, "materiality": "major"}
    r.update(over)
    return r


def source(title, grade, published, source_type):
    return {"origin": "user", "title": title, "published": published, "published_precision": "day", "accessed": "2026-10-18T10:00:00+08:00",
            "tier": "primary", "grade": grade, "capture_method": "user_file", "access": "full", "source_type": source_type, "time_scope": "as_of"}


def ev(src, locator, excerpt, attribute="actual"):
    return {"source_id": src, "locator": locator, "excerpt": excerpt, "attribute": attribute, "numeric": False, "entity_id": "ENT-0001", "scope": "consolidated"}


def x(topic, title, text, status, evidence, limitations=""):
    return {"type": "explanation", "topic": topic, "title": title, "text": text, "status": status, "evidence_ids": evidence, "limitations": limitations}


CONTENT = {
    "version": "1.2", "title": "云帆智造：电子制造视觉质检设备商，收入两年增长过半", "subtitle": "公司研究 · 基准日 2026-10-20 · 虚构样稿", "language": "zh-CN",
    "summary": ("云帆智造是一家 2019 年在上海注册成立的视觉质检设备公司，面向长三角电子代工厂销售质检设备并收取软件订阅费。"
                "审计报告显示，2024 年营业收入 3600 万元，2025 年营业收入 5600 万元，2025 年毛利率 42.0%。"
                "公司的获客主要依靠行业展会和代理商，竞争对手包括国内视觉检测企业和进口设备，但价格和性能的优势目前只有公司自己的说法。"
                "客户续约率和客户集中度没有披露，这是判断增长能否持续的关键缺口；补齐路径是向公司索取客户名单与续约记录。"
                "本报告只做公司研究，不作投资判断。"),
    "scope_note": "约定范围：Quick 公司研究，覆盖身份、团队、产品、商业模式、财务、营销和竞争；资料来自用户提供的工商登记、公司介绍材料和 2025 年审计报告，没有访谈和现场核查。",
    "sections": [
        {"id": "company-profile", "title": "公司是谁：2019 年成立的视觉质检设备商", "blocks": [
            x("identity", "研究对象是哪家公司", "研究对象是云帆智造科技有限公司这一法人，品牌与法人一致，没有发现集团或子公司结构。", "supported", ["ev-0001"]),
            {"type": "timeline", "purpose": "company_history", "title": "公司时间线", "items": [
                {"title": "在上海注册成立", "text": "公司完成工商注册", "evidence_ids": ["ev-0001"], "date": "2019-03-12", "status": "completed"},
                {"title": "推出第一代视觉质检设备", "text": "首款产品面向电子制造", "evidence_ids": ["ev-0002"], "date": "2021", "status": "completed"}]},
            x("history_team", "从哪里来", "创始人此前在工业相机企业负责研发，创业后先做设备，再加上软件订阅。", "partial", ["ev-0002", "ev-0003"],
              "团队其他成员的履历只有公司自述")]},
        {"id": "founders-team", "title": "谁在经营：创始人主导研发与销售", "blocks": [
            {"type": "people", "title": "核心人物", "profiles": [
                {"name": "李明", "role": "创始人兼首席执行官", "period": "公司成立至今", "background": "曾在工业相机企业负责研发",
                 "contribution": "主导第一代设备的研发", "limitations": "贡献的依据只有公司介绍材料", "evidence_ids": ["ev-0003"]}]}]},
        {"id": "products-customers", "title": "卖什么、卖给谁：质检设备加软件订阅", "blocks": [
            x("offering", "卖什么", "主要产品是面向电子制造的视觉质检设备，以及配套的检测软件订阅。", "supported", ["ev-0004"]),
            x("customers_markets", "卖给谁", "公司称客户主要是长三角的电子代工厂，没有取得客户名单。", "partial", ["ev-0005"], "只有公司自述，没有客户名单")]},
        {"id": "business-model", "title": "业务怎样运转：一次性卖设备，按年收软件费", "blocks": [
            x("transaction_flow", "一笔业务怎么走", "客户选型后采购设备，公司工程师上门安装调试，之后客户按年订阅检测软件。", "supported", ["ev-0006"]),
            {"type": "process", "purpose": "business_model", "ordering": "conceptual", "title": "业务模式", "items": [
                {"title": "需求与选型", "text": "电子代工厂提出质检需求", "basis": "evidence", "evidence_ids": ["ev-0006"]},
                {"title": "安装调试", "text": "公司工程师上门完成", "basis": "company_claim", "evidence_ids": ["ev-0006"]},
                {"title": "软件订阅", "text": "客户按年续订检测软件", "basis": "company_claim", "evidence_ids": ["ev-0006"]}]},
            x("operating_model", "谁做什么", "设备由公司组装，安装和维护由公司工程师完成，没有发现外包履约。", "supported", ["ev-0006"]),
            x("revenue_costs", "怎样赚钱", "收入来自设备销售和软件订阅两部分，成本结构没有披露。", "partial", ["ev-0006"], "成本结构和两部分收入的拆分未披露")]},
        {"id": "financial-performance", "title": "经营结果：收入两年增长过半", "blocks": [
            x("financial_performance", "营收与毛利", "2024 年营业收入 3600 万元，2025 年营业收入 5600 万元；2025 年毛利率 42.0%。", "supported", ["ev-0007", "ev-0008"]),
            {"type": "chart", "chart_type": "column", "title": "两年营业收入", "unit": "万元", "period": "2024–2025", "entity_id": "ENT-0001", "kind": "actual",
             "evidence_ids": ["ev-0007"], "note": "合并口径，来自审计报告", "points": [{"label": "2024", "value": 3600}, {"label": "2025", "value": 5600}]}]},
        {"id": "marketing-competition", "title": "怎样获客、和谁竞争", "blocks": [
            x("marketing", "营销与获客", "公司称主要通过行业展会和代理商获客，没有获客成本和转化数据。", "partial", ["ev-0009"], "没有获客成本和转化数据"),
            x("competition", "竞争与替代", "公司称主要竞争对手是国内视觉检测企业和进口设备。", "partial", ["ev-0010"], "竞品名单和份额只有公司说法"),
            {"type": "matrix", "purpose": "competition", "title": "与进口设备对照", "columns": ["云帆智造", "进口设备"], "note": "全部是公司口径，待核实",
             "rows": [{"label": "价格", "cells": [{"text": "较低（公司口径）", "basis": "company_claim", "evidence_ids": ["ev-0010"]},
                                                 {"text": "较高（公司口径）", "basis": "company_claim", "evidence_ids": ["ev-0010"]}]}]},
            x("differentiation", "为什么选它", "公司称价格低于进口设备，这一点没有独立来源印证。", "partial", ["ev-0010"], "差异化只有公司说法")]},
        {"id": "material-risks", "title": "主要风险与未知", "blocks": [
            {"type": "text", "text": "客户续约率和客户集中度没有披露，收入能否持续取决于老客户是否续订软件。"}]}]}

MODULE_TEXT = "## 结论\n\n按 Quick 深度完成本模块的基础判断，详见主报告对应章节；没有展开的检查项记为未开展。\n"


def make_diligence_task(task):
    task = pathlib.Path(task)
    diligence.main(["init", str(task), "--target", "云帆智造科技有限公司", "--purpose", "company_research", "--depth", "Quick",
                    "--as-of", AS_OF, "--listing-status", "unlisted", "--network", "online"])
    led = Ledger(task)
    led.add("sources", source("营业执照与工商登记", "S", "2026-01-10", "official"), line="U")
    led.add("sources", source("公司介绍材料", "C", "2026-06-01", "company"), line="U")
    led.add("sources", source("2025 年审计报告", "S", "2026-04-15", "official"), line="U")
    rows = [ev("U001", "第 1 页", "统一社会信用代码 91310000MA1FL0000X，成立日期 2019-03-12"),
            ev("U002", "第 3 页", "2021 年推出第一代视觉质检设备"),
            ev("U002", "第 5 页", "创始人李明曾在工业相机企业负责研发"),
            ev("U002", "第 6 页", "主要产品是面向电子制造的视觉质检设备和软件订阅"),
            ev("U002", "第 8 页", "客户主要是长三角的电子代工厂"),
            ev("U002", "第 9 页", "设备一次性销售，软件按年订阅，安装和维护由公司工程师完成"),
            ev("U003", "第 12 页", "2024 年营业收入 3600 万元，2025 年营业收入 5600 万元"),
            ev("U003", "第 13 页", "2025 年毛利率 42.0%"),
            ev("U002", "第 11 页", "主要通过行业展会和代理商获客"),
            ev("U002", "第 12 页", "主要竞争对手包括国内视觉检测企业和进口设备")]
    for r in rows:
        led.add("evidence", r)
    led.patch("entities", "ENT-0001", {"identity_status": "resolved", "registration_id": "91310000MA1FL0000X", "evidence_ids": ["ev-0001"], "geography": "上海"})
    for value, dec, unit in ((3600, 0, "万元"), (5600, 0, "万元"), (42.0, 1, "%")):
        led.add("metrics", {"unit": unit, "decimals": dec, "status": "present", "value": value})
    led.add("claims", claim(statement="云帆智造于 2019 年在上海注册成立"))
    led.add("claims", claim(kind="data", statement="2024 年营业收入 3600 万元，2025 年营业收入 5600 万元", unit="万元", metric_refs=["m-0001", "m-0002"],
                            verification="verified", inference="收入规模两年增长过半", calculation="审计报告原值"))
    led.add("claims", claim(kind="data", statement="2025 年毛利率 42.0%", unit="%", metric_refs=["m-0003"], verification="verified",
                            inference="毛利水平说明定价有一定空间", calculation="审计报告原值"))
    for cid, eid in (("cl-0001", "ev-0001"), ("cl-0002", "ev-0007"), ("cl-0003", "ev-0008")):
        led.add("claim_evidence", {"claim_id": cid, "evidence_id": eid, "relation": "supports", "applicable_scope": "合并口径"})
    led.add("claim_evidence", {"claim_id": "cl-0001", "evidence_id": "ev-0002", "relation": "context", "applicable_scope": "公司沿革"})
    led.add("gaps", {"description": "客户续约率和客户集中度未披露", "module": "09", "entity_id": "ENT-0001", "reason": "not_disclosed", "materiality": "major",
                     "priority": "P1", "route": "user", "blocking_scope": "none", "acquisition_path": "向公司索取客户名单与续约记录", "owner_role": "研究负责人",
                     "status": "open"})
    led.add("risks", {"description": "收入依赖少数电子代工客户（线索）", "entity_id": "ENT-0001", "status": "lead", "severity": "major", "impact": "老客户不续订会拖累收入",
                      "likelihood": "未知", "time_horizon": "12 个月", "alternative_explanations": "客户其实分散，只是公司没有披露",
                      "mitigation": "取得客户名单与续约记录", "residual_risk": "取得名单前无法判断", "closure_condition": "客户集中度和续约率核实后关闭",
                      "owner_role": "研究负责人"})
    scope = {m: {"status": "applicable"} for m in [f"{i:02d}" for i in range(1, 13)] + ["15"]}
    scope.update({"13": {"status": "not_applicable", "reason": "Quick 公司研究，未发现涉诉线索，扫描后不展开"},
                  "14": {"status": "not_applicable", "reason": "Quick 公司研究，ESG 议题与本次理解无关"},
                  "16": {"status": "not_applicable", "reason": "不做估值或交易分析"},
                  "17": {"status": "not_applicable", "reason": "不涉及授信或供应商准入"},
                  "18": {"status": "not_applicable", "reason": "未上市，也没有上市主体控制（见控制链核对）"}})
    led.patch("project", "project", {"identity_status": "resolved", "control_chain_checked": True, "control_evidence_ids": ["ev-0001"], "module_scope": scope,
                                     "last_refresh_at": "2026-10-20T18:00:00+08:00", "confidentiality": "内部使用", "report_status": "complete",
                                     "completion_review": {"scope": CONTENT["scope_note"], "key_claim_ids": ["cl-0001", "cl-0002"],
                                                           "gap_assessments": [{"gap_id": "G-0001", "impact": "无法判断收入增长能否持续，结论限于已核实的收入规模",
                                                                                "disposition": "limits_conclusion"}],
                                                           "reviewed_at": "2026-10-20T18:30:00+08:00"}})
    mods = task / "03d_diligence" / "modules"
    for m, v in scope.items():
        if v["status"] == "applicable":
            (mods / f"{m}-module.md").write_text(f"# 模块 {m}\n\n{MODULE_TEXT}", encoding="utf-8")
    (task / "03d_diligence" / "report-content.json").write_text(json.dumps(CONTENT, ensure_ascii=False, indent=1), encoding="utf-8")
    led.add("reviews", {"type": "diligence_manual", "reviewer": "作者（测试）", "at": "2026-10-20T19:00:00+08:00", "conclusion": "22 条人工清单逐条完成",
                        "checks": {k: {"passed": True, "evidence": "测试夹具：逐条核对"} for k in dcontent.MANUAL_ITEMS}})
    diligence.main(["sync", str(task)])
    return led


SLIDES_MD = """# 逐页内容

## P01 ｜ — ｜ 封面
**行动标题**：云帆智造公司研究

## P02 ｜ 01 公司身份 ｜ 时间线
**行动标题**：2019 年在上海成立的视觉质检设备商
**正文**：
- 云帆智造于 2019 年在上海注册成立{c1}
**可视化建议**：时间线
**讲者备注**：先看公司是谁、从哪里来{c1}。
**来源**：{s1}
**追溯**：公司是谁；{k1}

## P03 ｜ 02 团队与产品 ｜ 观点+证据
**行动标题**：创始人主导，卖设备加软件订阅
**正文**：
- 创始人李明主导第一代设备研发{c4}
- 产品是视觉质检设备和软件订阅{c5}
- 客户是长三角电子代工厂（公司自述）{c6}
**可视化建议**：人物卡与产品要点
**讲者备注**：团队和产品的依据多为公司材料{c5}。
**来源**：{s4}；{s5}；{s6}
**追溯**：团队与产品；{k4}、{k5}、{k6}

## P04 ｜ 03 商业模式与财务 ｜ 数据图表
**行动标题**：一次性卖设备、按年收软件费，收入两年增长过半
**正文**：
- 设备一次性销售，软件按年订阅{c7}
- 2024 年营业收入 3600 万元，2025 年营业收入 5600 万元{c2}
- 2025 年毛利率 42.0%{c3}
**可视化建议**：两年收入柱形
**讲者备注**：收入增长来自设备和订阅，但两部分的拆分没有披露{c2}。
**来源**：{s7}；{s2}；{s3}
**追溯**：商业模式与财务；{k7}、{k2}、{k3}

## P05 ｜ 04 营销与竞争 ｜ 对比
**行动标题**：靠展会和代理商获客，优势只有公司说法
**正文**：
- 主要通过行业展会和代理商获客{c8}
- 竞争对手是国内视觉检测企业和进口设备{c9}
**可视化建议**：对照矩阵
**讲者备注**：营销和竞争的说法都待核实{c9}。
**来源**：{s8}；{s9}
**追溯**：营销与竞争；{k8}、{k9}

## P06 ｜ 05 风险与补齐 ｜ 下一步
**行动标题**：先拿到客户名单和续约记录
**正文**：
- 客户续约率和集中度没有披露{c6}
**可视化建议**：缺口与补齐路径
**讲者备注**：补齐路径是向公司索取客户名单{c6}。
**来源**：{s6}
**追溯**：主要风险与未知；{k6}

## P07 ｜ — ｜ 结尾
**行动标题**：谢谢
"""

STORYBOARD = """# 故事板

Deck 设定：阅读型；主 deck 7 页；备用页 0 页；结尾类型：下一步。

| 页码 | 章节 | 页面类型 | 行动标题 |
|---|---|---|---|
| 1 | — | 封面 | 云帆智造公司研究 |
| 2–6 | 01–05 | 正文 | 见逐页 |
| 7 | — | 结尾 | 谢谢 |

横向检查：只读标题，论证完整。纵向检查：正文都支撑标题。
"""


def write_split(task):
    """转母版之后，作者写的拆页产出（卡片编号从证据账读取）。"""
    task = pathlib.Path(task)
    led = Ledger(task)
    card = {c["claim_id"]: c for c in led.read("cards")}
    ev = {e["id"]: e for e in led.read("evidence")}
    links = led.read("claim_evidence")
    fill = {}
    for n in range(1, 10):
        cid = f"cl-{n:04d}"
        c = card[cid]
        e = next(ev[l["evidence_id"]] for l in links if l["claim_id"] == cid and l["relation"] == "supports")
        fill[f"c{n}"] = f"〔{c['id']}｜{e['source_id']} {e['locator']}〕"
        fill[f"s{n}"] = f"{c['id']}｜{e['source_id']} {e['locator']}"
        fill[f"k{n}"] = c["id"]
    s = task / "07_storyline"
    (s / "06_slides.md").write_text(SLIDES_MD.format(**fill), encoding="utf-8")
    (s / "05_storyboard.md").write_text(STORYBOARD, encoding="utf-8")
    (s / "07_audit_report.md").write_text("# 审计报告\n\n## 1 指标摘要\n\n" + "、".join(fill[f"k{n}"] for n in range(1, 10)) + " 都已安置。\n", encoding="utf-8")
    (s / "02_terms.md").write_text("| 概念 | 材料中的叫法和口径 | 采用表述 | 说明 |\n|---|---|---|---|\n| 收入 | 营业收入（合并口径） | 营业收入 | 审计口径 |\n", encoding="utf-8")
    import subprocess
    subprocess.run([sys.executable, str(SCRIPTS.parents[1] / "core-storyline" / "scripts" / "storyline.py"), "cards", str(task)], capture_output=True, text=True)

    def page(n, title, section, role, beat, ptype, claims, metrics, panels, proves, adds, blocks, relation):
        return {"page": n, "type": ptype, "action_title": title, "section": section, "page_role": role, "story_beat": beat,
                "subtitle": "合并口径｜基准日见封面", "proves": proves, "adds": adds, "claim_refs": claims, "metric_refs": metrics,
                "density": {"profile": "balanced", "space_intent": "主展品占主要区域，辅助文字写清口径和限制",
                            "evidence_units": [{"role": p["role"], "purpose": p["purpose"]} for p in panels]},
                "visual_intent": {"relationship": panels[0]["relationship"], "form": panels[0]["form"], "layout": "custom",
                                  "reading_path": "标题 → 主展品 → 辅助说明", "layout_reason": "主展品在左，辅助说明在右",
                                  "repetition_approved": True,
                                  "repetition_reason": "虚构尽调夹具按主题逐页保留主证据加边界说明的共同结构，以验证跨主题阅读复述的一致性"},
                "panels": panels, "relations": [{"id": f"pair-{n}", "kind": relation, "panel_refs": [panels[0]["id"], panels[1]["id"]],
                                                 "reason": "辅助说明限定主展品能支持的结论范围"}], "block_ids": blocks}

    def panel(pid, role, slot, purpose, claims, form, rel, reason, **kw):
        kw.setdefault("semantic_type", "point_evidence")
        return {"id": pid, "role": role, "slot": slot, "span": 2 if role == "primary" else 1, "purpose": purpose, "claim_refs": claims,
                "form": form, "relationship": rel, "reason": reason, **kw}
    doc = {"deck": {"title": "云帆智造公司研究", "kind": "reading", "language": "zh-CN", "audience": "需要了解这家公司的决策者", "decision": "是否继续深入研究",
                    "story_mode": "company_research", "arc": "evidence-to-view", "ratio": "16x9",
                    "brief": {"question": "云帆智造是一家什么公司、经营得怎样？", "purpose": "research", "scope": "云帆智造合并口径", "period": "2019–2026",
                              "baseline": "2024 年收入", "constraints": "没有访谈和现场核查", "success_criteria": "读者能回答 11 个主题问题并看到补齐路径"},
                    "answer_claim_refs": ["cl-0002"],
                    "decision_structure": {
                        "decision_level": "有条件继续深入研究",
                        "decisive_reasons": ["收入增长已有披露", "产品与收费模式可以描述", "客户续约和集中度仍待核实"],
                        "largest_upside": "设备销售叠加软件订阅可能形成持续收入",
                        "largest_risk": "客户与续约数据缺失，增长质量无法判断",
                        "immediate_actions": ["取得客户名单、续约记录和收入集中度"],
                        "thresholds": {"continue": "客户与续约记录支持收入可持续性", "stop": "关键客户或续约证据无法取得"}},
                    "cover": {"subtitle": "公司研究 · 虚构样稿", "producer": "Allen 分析系统", "date": "2026-10-20", "version": "v1", "project": "云帆智造", "closing_text": "谢谢"}},
           "slides": [
               {"page": 1, "type": "cover", "action_title": "云帆智造公司研究", "page_role": "cover", "story_beat": "context"},
               page(2, "2019 年在上海成立的视觉质检设备商", "01 公司身份", "analysis", "context", "timeline", ["cl-0001"], [],
                    [panel("timeline", "primary", "main", "公司成立和第一代产品的时间顺序", ["cl-0001"], "svg.custom", "process", "时间线按日期排开成立和首款产品，最能表达先后顺序",
                           visual="公司时间线"),
                     panel("identity", "support", "aside", "说明研究对象就是这家法人", ["cl-0001"], "html.text", "text", "主体边界是文字判断，用短段落说明法人与品牌的关系")],
                    "公司 2019 年注册成立，品牌与法人一致", "读者知道研究对象是谁、从哪里来",
                    ["company-profile-1", "company-profile-2", "company-profile-3"], "boundary"),
               page(3, "创始人主导，卖设备加软件订阅", "02 团队与产品", "analysis", "context", "point_evidence", ["cl-0004", "cl-0005", "cl-0006"], [],
                    [panel("offer", "primary", "main", "产品和客户的要点逐条对应", ["cl-0005", "cl-0006"], "html.table", "exact", "产品和客户要点逐行对照，表格比段落更容易核对"),
                     panel("people", "support", "aside", "创始人的角色、经历与可归属的贡献", ["cl-0004"], "html.text", "text", "人物的角色、经历和贡献用短段落写清依据")],
                    "公司由创始人主导，产品是设备加订阅", "读者知道谁在经营、卖什么、卖给谁",
                    ["founders-team-1", "products-customers-1", "products-customers-2"], "complement"),
               page(4, "一次性卖设备、按年收软件费，收入两年增长过半", "03 商业模式与财务", "analysis", "diagnosis", "data_chart",
                    ["cl-0007", "cl-0002", "cl-0003"], ["m-0001", "m-0002", "m-0003"],
                    [panel("bars", "primary", "main", "两年营业收入同量尺比较", ["cl-0002"], "svg.custom", "comparison", "两期收入共用零基线，柱形最直接比较绝对规模",
                           visual="两年收入柱形"),
                     panel("model", "support", "aside", "收费方式、毛利水平和未披露的拆分", ["cl-0007", "cl-0003"], "html.text", "text", "收费机制和毛利口径是文字判断，用短段落说明边界")],
                    "收入从 3600 万元增至 5600 万元", "读者知道公司怎样赚钱、规模多大",
                    ["business-model-1", "business-model-2", "business-model-3", "business-model-4", "financial-performance-1", "financial-performance-2"], "boundary"),
               page(5, "靠展会和代理商获客，优势只有公司说法", "04 营销与竞争", "analysis", "insight", "comparison", ["cl-0008", "cl-0009"], [],
                    [panel("matrix", "primary", "main", "与进口设备逐项对照，全部是公司口径", ["cl-0009"], "html.table", "comparison", "与进口设备逐项对照，共同表头便于看出公司口径"),
                     panel("market", "support", "aside", "获客渠道、方式和缺少的数据", ["cl-0008"], "html.text", "text", "获客渠道和数据缺口用短段落说明，没有数字可画")],
                    "营销和竞争优势目前只有公司说法", "读者知道怎样获客、和谁竞争、哪些待核实",
                    ["marketing-competition-1", "marketing-competition-2", "marketing-competition-3", "marketing-competition-4"], "complement"),
               page(6, "先拿到客户名单和续约记录", "05 风险与补齐", "risk", "action", "next_steps", ["cl-0006"], [],
                    [panel("gaps", "primary", "main", "关键缺口和补齐路径", ["cl-0006"], "html.table", "decision", "每个缺口对应一条补齐路径，表格逐行对照最清楚"),
                     panel("why", "support", "aside", "缺口为什么影响判断", ["cl-0006"], "html.text", "text", "缺口为什么影响判断是文字推理，用短段落说明")],
                    "客户续约和集中度是判断持续性的关键缺口", "读者知道下一步先补什么资料", ["material-risks-1"], "complement"),
               {"page": 7, "type": "close", "action_title": "谢谢", "page_role": "close", "story_beat": "close"}]}
    (s / "slides.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
