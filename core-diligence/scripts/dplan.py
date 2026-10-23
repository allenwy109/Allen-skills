"""检索计划（能力清单 H 节 search_plan.py，L 节优化 7）。只输出计划，所有任务都是 not_executed；计划不是日志，
真实检索的结果（成功、未找到、失败）都要登记到 search_log。

顺序：主张核验 → 缺口 → 官网（身份 1 项 + 页面 8 项）→ 关键词候选 → 研报 → 行业词 → 事件后点评。
按深度和优先级裁剪、去重：Quick 只展开目的的重点模块和第一个名称、第一种语言；Standard 展开重点模块加 01、12、15，名称最多 3 个；
Deep 展开全部适用模块。研报类别已经找到并读完最新报告的，不再生成时间窗任务。
"""
from dcore import derive

MODULE_WORDS = {
    "01": ("工商登记 股权结构 实际控制人", "国家企业信用信息公示系统、章程、交易所公告"),
    "02": ("创始人 管理团队 董事会", "官网团队页、任职公告、具名访谈"),
    "03": ("商业模式 产品价格 服务条款", "产品价格页、订购与退货条款、财报附注"),
    "04": ("市场规模 行业协会 产业链", "统计局、行业协会、券商行业报告"),
    "05": ("竞争对手 市场份额 替代", "竞品官网、公开采购记录、竞争者披露"),
    "06": ("业务阶段 客户留存 投诉", "付费与留存披露、投诉平台（只作线索）"),
    "07": ("增长 产能 扩张 瓶颈", "扩产公告、招聘（只作线索）、渠道披露"),
    "08": ("许可证 监管 政策", "主管部门、许可证查询、政策原文"),
    "09": ("客户 订单 合同 营销 渠道", "公开采购、客户侧披露、营销活动实例"),
    "10": ("产能 良率 交付 认证", "认证查询、产能披露、租约"),
    "11": ("专利 技术 数据 开源", "知识产权局、专利原文、技术文档"),
    "12": ("营业收入 毛利率 审计报告 财务报表", "年报、审计报告、监管披露"),
    "13": ("诉讼 被执行 行政处罚", "裁判文书网、执行信息公开网、主管部门"),
    "14": ("环保 安全事故 ESG 评级", "主管部门处罚、整改记录、评级机构说明"),
    "15": ("风险 失信 关联交易 审计机构变更", "监管与司法记录、审计机构公告"),
    "16": ("估值 融资 并购 交易", "公司与投资方公告、交易所公告"),
    "17": ("付款 违约 担保 授信", "债券披露、评级报告、付款记录"),
    "18": ("研报 年报 中报 深度报告", "交易所、券商研究所、合法公开平台"),
}
PURPOSE_MODULES = {"company_research": ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
                   "investment": ("05", "07", "12", "15", "16"), "acquisition": ("01", "02", "09", "10", "12", "13", "16"),
                   "partnership": ("03", "09", "10", "11", "13", "17"), "credit": ("09", "12", "13", "15", "17"),
                   "supplier": ("09", "10", "11", "12", "13", "17"), "competitor": ("03", "04", "05", "07", "09", "11")}
SITE_PAGES = ("about", "products_pricing", "founders_team", "history_news", "locations_channels", "investor_relations", "terms_identity", "visual_assets")
CATEGORY_WORDS = {"official_annual": "年度报告", "official_interim": "半年度报告 季度报告", "official_event": "重大事项公告",
                  "company_update": "公司点评 业绩点评", "company_deep": "深度报告 首次覆盖", "industry": "行业深度", "event_update": "事件点评",
                  "peer": "可比公司"}
EN = {"official_annual": "annual report", "official_interim": "interim report", "company_update": "earnings update", "company_deep": "initiation equity research",
      "industry": "sector report industry outlook", "official_event": "announcement", "event_update": "event update", "peer": "peer comparison"}
WINDOWS = (90, 180, 365, None)


def build(data):
    p = data["project"]
    depth = p.get("diligence_depth") or "Standard"
    d = derive(data)
    tasks, seen = [], set()

    def add(task):
        key = (task["type"], task.get("query") or task.get("goal"))
        if key in seen:
            return
        seen.add(key)
        task.update(id=f"T{len(tasks) + 1:03d}", status="not_executed")
        tasks.append(task)

    gaps = {g["id"]: g for g in data["gaps"] if g["status"] not in ("resolved", "unavailable")}
    review = p.get("completion_review") or {}
    keys = set(review.get("key_claim_ids") or [])
    claims = [c for c in data["claims"] if c["id"] in keys or c.get("materiality") in ("critical", "major")]
    claims.sort(key=lambda c: (c["id"] not in keys, c.get("materiality") != "critical"))
    linked = set()
    for c in claims:
        related = [g for g in gaps.values() if c["id"] in (g.get("affected_claims") or [])]
        linked |= {g["id"] for g in related}
        prio = min(["P0" if c.get("materiality") == "critical" else "P1"] + [g["priority"] for g in related])
        add({"type": "claim_verification", "priority": prio, "claim_id": c["id"], "goal": f"核验：{c['statement']}",
             "assumptions": c.get("assumptions"), "counterevidence": c.get("counterevidence"), "unresolved": c.get("unresolved"),
             "gaps": [{"id": g["id"], "need": g["description"], "path": g["acquisition_path"]} for g in related]})
    for g in sorted((g for g in gaps.values() if g["id"] not in linked), key=lambda g: g["priority"]):
        add({"type": "gap_resolution", "priority": g["priority"], "gap_id": g["id"], "goal": g["description"], "path": g["acquisition_path"]})
    add({"type": "official_site_identity", "priority": "P0", "goal": "确认官网归属（用户入口、登记披露链接、App 发行方、可靠的双向关联；不凭同名或搜索排名，不猜路径）",
         "record_fields": ["url", "依据", "访问日"]})
    for page in SITE_PAGES:
        add({"type": "official_site_page", "priority": "P1", "page": page, "depends_on": "official_site_identity",
             "goal": f"读官网 {page} 页", "record_fields": ["实际 URL", "标题", "真实性及依据", "发布日", "适用期", "访问日", "可访问程度", "定位"],
             "done_when": "页面已读并存档，或确认不存在、无法读取并登记原因"})
    ents = {e["id"]: e for e in data["entities"]}
    names = []
    for eid in [p.get("target_entity_id")] + d["listed"]:
        e = ents.get(eid)
        if e:
            names += [(eid, n) for n in [e["legal_name"], *(e.get("aliases") or []), e.get("security_code")] if n]
    scope = p.get("module_scope") or {}
    applicable = [m for m in MODULE_WORDS if (scope.get(m) or {}).get("status") != "not_applicable"]
    focus = PURPOSE_MODULES.get(p.get("purpose") or "company_research", PURPOSE_MODULES["company_research"])
    if depth == "Quick":
        modules = [m for m in applicable if m in focus]
        names = names[:1]
        langs = (p.get("languages") or ["zh"])[:1]
    elif depth == "Standard":
        modules = [m for m in applicable if m in set(focus) | {"01", "12", "15"}]
        names = names[:3]
        langs = p.get("languages") or ["zh", "en"]
    else:
        modules, langs = applicable, p.get("languages") or ["zh", "en"]
    for eid, name in names:
        for m in modules:
            words, hint = MODULE_WORDS[m]
            for lang in langs:
                q = f"{name} {words}" if lang == "zh" else f"{name} {words} (in English)"
                add({"type": "keyword_candidate", "priority": "P1" if m in focus else "P2", "entity_id": eid, "module": m, "language": lang,
                     "query": q, "source_hint": hint})
    covs = {(c["research_entity_id"], c["category"]): c for c in data["coverage"]}
    for eid, cat, _, _ in d["requirements"]:
        row = d["rows"].get((eid, cat), {})
        if row and row["pointers"]["read"] and covs.get((eid, cat), {}).get("search_status") == "found":
            continue                                           # 已找到并读完最新报告，不再重复生成
        listed = ents.get(eid, {}).get("legal_name", eid)
        target = ents.get(p.get("target_entity_id"), {}).get("legal_name", "")
        for w in WINDOWS[:1] if depth == "Quick" else WINDOWS:
            add({"type": "research_report", "priority": "P0", "entity_id": eid, "category": cat, "window_days": w,
                 "query": f"{listed} {target} {CATEGORY_WORDS[cat]} {EN[cat]} filetype:pdf".strip(),
                 "goal": f"找 {cat} 在 {('近 %d 天' % w) if w else '不限时间'} 内的最新报告"})
    for kw in p.get("industry_keywords") or []:
        add({"type": "industry", "priority": "P1", "query": f"{kw} 行业深度 市场规模 供需", "goal": "细分行业的口径与供需"})
    for ev in p.get("events") or []:
        add({"type": "post_event", "priority": "P0", "entity_id": ev["entity_id"], "query": f"{ents.get(ev['entity_id'], {}).get('legal_name', '')} {ev['description']} 点评",
             "goal": f"事件 {ev['date']}「{ev['description']}」之后的研究和官方更正"})
    return {"type": "plan_only", "depth": depth, "listed_entities": d["listed"], "listing_trigger": d["listing"], "tasks": tasks,
            "stop_rule": "关键问题已有足够证据、重要冲突已处理、剩余缺口逐项评估过影响、继续检索的边际收益低；预算用尽可以停止工作，但不等于完成，强制研报检索仍必须执行",
            "warning": "这是计划，不是日志；每次真实检索都要登记 search_log（成功、未找到、失败都要记）"}
