"""尽调底稿 audit.md（能力清单 H 节 build_audit_report.py；Quick 10 节，Standard/Deep 20 节）。从证据账生成，不手改。
主报告给读者看判断；底稿给核验者追溯：台账、模块、覆盖、评分、主张核验、桥接、冲突、缺口、日志、请求、访谈。
"""
import json
import pathlib
import re

from tools.lib import schema_check

ENUMS = schema_check.load("ledger.schema.json")["enums"]
QUICK = ("元信息", "执行摘要", "研究完成范围", "主体与控制链", "研报覆盖", "关键主张与证据", "风险与冲突", "信息缺口与补齐路径", "下一步", "证据附录")
FULL = ("元信息", "执行摘要", "研究完成范围", "主体与关系", "研报覆盖与目录", "评分摘要", "关键主张核验", "主张与证据关联", "桥接与口径", "冲突",
        "风险", "信息缺口与补齐路径", "模块分析", "财务计算底稿", "图表与编排复核", "只读正文复述记录", "人工清单记录", "下一步：资料请求清单",
        "下一步：访谈提纲", "证据附录与检索日志")


def L(enum, v):
    return ENUMS.get(enum, {}).get("labels", {}).get(v, v if v not in (None, "") else "—")


def demote(text, levels):
    """嵌入的文件标题统一降级，保持底稿自己的章节结构。"""
    return re.sub(r"(?m)^(#{1,6}) ", lambda m: "#" * min(6, len(m.group(1)) + levels) + " ", text)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c if c not in (None, "", []) else "—").replace("|", "／").replace("\n", " ") for c in r) + " |" for r in rows]
    return out if rows else out + ["| " + " | ".join(["无"] + [""] * (len(headers) - 1)) + " |"]


def modules(task, scope):
    """读 modules/NN-*.md；同一编号多于一个文件报错；不适用写理由；缺文件写【缺口】。返回 (文本行, 错误)。"""
    mdir = pathlib.Path(task) / "03d_diligence" / "modules"
    out, errors = [], []
    for i in range(1, 19):
        m = f"{i:02d}"
        files = sorted(mdir.glob(f"{m}-*.md")) if mdir.is_dir() else []
        st = (scope.get(m) or {}).get("status", "pending")
        out.append(f"### 模块 {m}（{L('module_status', st)}）")
        if len(files) > 1:
            errors.append(f"模块 {m} 有多个文件：{'、'.join(f.name for f in files)}")
        if st == "not_applicable":
            out.append(f"不适用：{(scope.get(m) or {}).get('reason') or '【缺口：不适用要写理由】'}")
        elif files:
            out.append(demote(files[0].read_text(encoding="utf-8").strip(), 3))
        else:
            out.append(f"【缺口：模块 {m} 还没有分析文件】")
        out.append("")
    return out, errors


def build(task, data, derived, content=None, hints=None, score=None):
    p = data["project"]
    full = (p.get("diligence_depth") or "Standard") != "Quick"
    names = FULL if full else QUICK
    claims = {c["id"]: c for c in data["claims"]}
    review = p.get("completion_review") or {}
    d = pathlib.Path(task) / "03d_diligence"
    parts, errors = {}, []
    parts["元信息"] = table(["项", "内容"], [["目标", p.get("target_name")], ["目标主体", p.get("target_entity_id")], ["目的", L("purpose", p.get("purpose"))],
                                          ["深度", p.get("diligence_depth")], ["基准日", p.get("as_of_date")], ["历史时点研究", "是" if p.get("historical") else "否"],
                                          ["网络与访问", json.dumps(p.get("constraints") or {}, ensure_ascii=False)], ["保密", p.get("confidentiality")],
                                          ["最近复查", p.get("last_refresh_at")]])
    parts["执行摘要"] = [(content or {}).get("summary") or "【缺口：执行摘要尚未填写】"]
    scope_rows = [[m, L("module_status", (v or {}).get("status")), (v or {}).get("reason")] for m, v in sorted((p.get("module_scope") or {}).items())]
    gap_rows = [[a["gap_id"], a["impact"], L("gap_disposition", a["disposition"])] for a in review.get("gap_assessments") or []]
    parts["研究完成范围"] = ([f"- 研报门槛：{L('gate', derived['gate'])}；报告状态：{L('report_status', p.get('report_status'))}；"
                         f"声明完成：{'是' if p.get('declared_complete') else '否'}"]
                        + ([f"- 网络不可用：本次是离线材料分析，只给补查计划"] if (p.get("constraints") or {}).get("network") == "offline" else [])
                        + [f"- 完成复核范围：{review.get('scope') or '—'}（{review.get('reviewed_at') or '未复核'}）", ""]
                        + table(["缺口", "影响", "处置"], gap_rows) + [""] + table(["模块", "适用性", "理由"], scope_rows))
    ent_rows = [[e["id"], e["legal_name"], L("entity_type", e["entity_type"]), L("identity_status", e["identity_status"]), L("listing", e["listing_status"]),
                 e.get("exchange"), e.get("security_code")] for e in data["entities"]]
    rel_rows = [[r["id"], r["parent_id"], r["child_id"], L("relation_type", r["relation_type"]), r.get("ownership_percent"),
                 f"[{r['effective_from']}, {r.get('effective_to') or '∞'})", L("relation_state", r["state"]), L("relation_verification", r["verification"])]
                for r in data["relations"]]
    ent_part = table(["ID", "法定名称", "类型", "身份", "上市", "交易所", "代码"], ent_rows) + [""] + \
        table(["ID", "上级", "下级", "关系", "比例", "生效区间", "状态", "核验"], rel_rows) + \
        ["", f"上市追溯：{L('listing_trigger', derived['listing'])}；上市主体：{'、'.join(derived['listed']) or '无'}"] + [f"- {w}" for w in derived["warnings"]]
    parts["主体与控制链"] = parts["主体与关系"] = ent_part
    cov_rows = [[c["id"], c["research_entity_id"], c["category"], L("search_status", c["search_status"]), "、".join(c.get("latest_read_ids") or []),
                 L("gate", c["gate_status"]), c.get("gap_id")] for c in data["coverage"]]
    rr_rows = [[r["id"], r["publisher"], r["title"], r["report_date"], L("access", r["access_status"]), L("reading", r["reading_status"]), L("relevance", r["relevance"])]
               for r in data["research_reports"]]
    cov_part = table(["覆盖", "主体", "类别", "检索", "最新已读", "状态", "缺口"], cov_rows)
    if derived["gate"] not in ("complete", "not_applicable"):
        cov_part.append("\n最新相关研报尚未取得或读完：只能说截至基准日在列明渠道中发现的最新报告，缺口和补齐路径见下文。")
    parts["研报覆盖"] = cov_part
    parts["研报覆盖与目录"] = cov_part + [""] + table(["研报", "机构", "标题", "报告日", "获取", "阅读", "相关性"], rr_rows)
    parts["评分摘要"] = ([f"状态：{(score or {}).get('status', '未计算')}"] + ([f"覆盖率 {score['coverage']:.0%}，综合分 {score['overall_score']}"]
                                                                         if score and score.get("coverage") is not None else [])
                      + [""] + table(["维度", "权重", "适用", "分数", "证据充分度", "理由"],
                                     [[r["dimension"], r["weight"], L("applicability", r["applicability"]), r.get("score"), L("coverage_status", r["coverage_status"]), r.get("reason")]
                                      for r in data["scorecard"]]))
    key_rows = [[cid, claims.get(cid, {}).get("statement"), L("verification", claims.get(cid, {}).get("verification")), L("confidence", claims.get(cid, {}).get("confidence"))]
                for cid in review.get("key_claim_ids") or []]
    claim_rows = [[c["id"], L("claim_kind", c["kind"]), c["statement"], L("verification", c["verification"]), L("confidence", c.get("confidence")), L("materiality", c.get("materiality"))]
                  for c in data["claims"]]
    parts["关键主张核验"] = table(["主张", "陈述", "核实", "置信度"], key_rows)
    parts["关键主张与证据"] = parts["关键主张核验"] + [""] + table(["主张", "身份", "陈述", "核实", "置信度", "重大性"], claim_rows)
    parts["主张与证据关联"] = table(["主张", "身份", "陈述", "核实", "置信度", "重大性"], claim_rows) + [""] + \
        table(["关联", "主张", "证据", "关系", "适用范围"], [[l["id"], l["claim_id"], l["evidence_id"], L("ce_relation", l["relation"]), l.get("applicable_scope")]
                                                      for l in data["claim_evidence"]])
    parts["桥接与口径"] = table(["关联", "主张", "证据", "桥接说明"], [[l["id"], l["claim_id"], l["evidence_id"], l.get("bridge")] for l in data["claim_evidence"] if l.get("bridge")])
    conflict_rows = [[x["id"], "、".join(x["claim_ids"]), x["left_value_scope"], x["right_value_scope"], L("conflict_status", x["status"]), x.get("accepted_reason"),
                      "是" if x.get("decision_changing") else "否"] for x in data["conflicts"]]
    risk_rows = [[r["id"], r["description"], L("risk_status", r["status"]), L("risk_severity", r["severity"]), r["impact"], r["mitigation"], r["closure_condition"]]
                 for r in data["risks"]]
    parts["冲突"] = table(["冲突", "主张", "一方", "另一方", "状态", "采信理由", "改变决策"], conflict_rows)
    parts["风险"] = table(["风险", "描述", "性质", "严重度", "影响", "缓释", "关闭条件"], risk_rows)
    parts["风险与冲突"] = parts["风险"] + [""] + parts["冲突"]
    parts["信息缺口与补齐路径"] = table(["缺口", "需要什么", "原因", "重大性", "优先级", "获取路径", "负责", "状态"],
                                   [[g["id"], g["description"], L("gap_reason", g["reason"]), L("materiality", g["materiality"]), g["priority"], g["acquisition_path"],
                                     g["owner_role"], L("gap_status", g["status"])] for g in data["gaps"]])
    mod_lines, mod_errors = modules(task, p.get("module_scope") or {})
    parts["模块分析"] = mod_lines
    errors += mod_errors
    calc = d / "calc"
    parts["财务计算底稿"] = ([f"- [{f.name}](calc/{f.name})" for f in sorted(calc.glob("*.json"))] if calc.is_dir() else []) or ["无（没有运行财务计算）"]
    parts["图表与编排复核"] = table(["章节", "提示", "处置"], [[h["section"], h["message"], "见 reviews 表 visual_review_disposition"] for h in hints or []])
    rv = data.get("reviews") or []
    parts["只读正文复述记录"] = table(["审查", "审查员", "时间", "结论"], [[r["id"], r["reviewer"], r["at"], r["conclusion"]] for r in rv if r["type"] == "reading_recap"])
    manual = next((r for r in reversed(rv) if r["type"] == "diligence_manual"), None)
    from dcontent import MANUAL_ITEMS
    parts["人工清单记录"] = table(["编号", "内容", "通过", "依据"], [[k, t, ("是" if (manual or {}).get("checks", {}).get(k, {}).get("passed") else "否") if manual else "未记录",
                                                          (manual or {}).get("checks", {}).get(k, {}).get("evidence")] for k, t in MANUAL_ITEMS.items()])
    req = demote((d / "request-list.md").read_text(encoding="utf-8"), 3) if (d / "request-list.md").is_file() else "【缺口：资料请求清单尚未填写】"
    itv = demote((d / "interview-outline.md").read_text(encoding="utf-8"), 3) if (d / "interview-outline.md").is_file() else "【缺口：访谈提纲尚未填写】"
    parts["下一步：资料请求清单"], parts["下一步：访谈提纲"] = [req], [itv]
    parts["下一步"] = ["#### 资料请求清单", req, "", "#### 访谈提纲", itv]
    src = {s["id"]: s for s in data["sources"]}
    ev_rows = [[e["id"], e["source_id"], src.get(e["source_id"], {}).get("title"), e["locator"], L("attribute", e.get("attribute")), (e.get("excerpt") or "")[:60]]
               for e in data["evidence"]]
    log_rows = [[q["id"], q["searched_at"], q["tool"], q["query"], L("search_status", q["status"])] for q in data["search_log"]]
    appendix = table(["证据", "来源", "标题", "定位", "属性", "摘录"], ev_rows) + [""] + \
        table(["来源", "标题", "发布", "访问", "等级", "获取"], [[s["id"], s["title"], s.get("published"), s["accessed"], s.get("grade"), L("access", s.get("access"))] for s in data["sources"]])
    parts["证据附录"] = appendix
    parts["证据附录与检索日志"] = appendix + [""] + table(["检索", "时间", "渠道", "查询", "结果"], log_rows) + \
        ["", "### 方法与局限", (content or {}).get("scope_note") or "【缺口：方法与局限尚未填写】"]
    lines = [f"# 尽调底稿：{p.get('target_name') or ''}", "", "> 由 diligence.py audit 从证据账生成，不要手改。", ""]
    for i, name in enumerate(names, 1):
        lines += [f"## {i} {name}", ""] + parts[name] + [""]
    return "\n".join(lines), errors
