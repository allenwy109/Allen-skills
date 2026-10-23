"""尽调的推导与检查（设计 §5.2；能力清单 B、D、H 节 common.py 的规则，L 节优化 2、4、5、7）。只用标准库。

数据全部来自统一证据账（project、entities、relations、sources、evidence、claims、claim_evidence、research_reports、
coverage、conflicts、gaps、risks、search_log）。字段和条件必填由 ledger.schema.json 和 `ledger check` 负责；
这里做跨表的推导（上市追溯、必读类别、最新指针、覆盖状态、研报门槛）和尽调专属的语义检查。
"""
import datetime

from tools.lib.ledger import Ledger

BASE_CATEGORIES = ("official_annual", "official_interim", "company_update", "company_deep", "industry")
EVENT_CATEGORIES = ("official_event", "event_update")
CONTROL = ("control", "brand_of", "branch_of")
CLOSED_GAP = ("resolved", "unavailable")
MODULES = tuple(f"{i:02d}" for i in range(1, 19))


def today():
    return datetime.date.today().isoformat()


def load(task):
    led = Ledger(task)
    data = {t: led.read(t) for t in led.schema["tables"]}
    data["project"] = (data["project"] or [{}])[0]
    return led, data


def _by_id(rows):
    return {r["id"]: r for r in rows}


def _in_force(rel, as_of):
    """生效区间左闭右开 [effective_from, effective_to)。"""
    return rel["effective_from"] <= as_of and (not rel.get("effective_to") or as_of < rel["effective_to"])


def listed_entities(data):
    """从目标沿生效、已核实、非拟议的控制类边向上追溯，返回 (上市主体 ID 列表, 状态, 警告)。
    状态：triggered / not_triggered / pending（身份未锁定、上市状态未知、有未核实的生效边、控制链未核对）。"""
    p, warnings = data["project"], []
    ents = _by_id(data["entities"])
    target = p.get("target_entity_id")
    as_of = p.get("as_of_date") or today()
    if not target or target not in ents:
        return [], "pending", ["project.target_entity_id 没有指向主体表里的主体"]
    kinds = CONTROL + (("joint_control",) if p.get("joint_control_triggers") else ())
    reach, frontier, pending = {target}, [target], []
    while frontier:
        child = frontier.pop()
        for rel in data["relations"]:
            if rel["child_id"] != child or not _in_force(rel, as_of):
                continue
            if rel["relation_type"] == "joint_control" and "joint_control" not in kinds:
                if ents.get(rel["parent_id"], {}).get("listing_status") == "listed":
                    warnings.append(f"{rel['parent_id']} 通过共同控制关联目标且已上市：默认不触发研报追溯，"
                                    "需要时把 project.joint_control_triggers 设为 true")
                continue
            if rel["relation_type"] not in kinds:
                continue
            if rel["state"] == "proposed":
                continue                                       # 拟收购、拟控制不算已控制
            if rel["verification"] != "verified":
                pending.append(rel["id"])
                continue
            if rel["parent_id"] not in reach:
                reach.add(rel["parent_id"])
                frontier.append(rel["parent_id"])
    listed = []
    for eid in sorted(reach):
        e = ents.get(eid, {})
        start, end = e.get("listing_start"), e.get("listing_end")
        if e.get("listing_status") == "listed" and (not start or start <= as_of) and (not end or as_of < end):
            listed.append(eid)
        elif e.get("listing_status") == "delisted" and start and end and start <= as_of < end:
            listed.append(eid)                                 # 历史时点仍在上市期内
    reasons = []
    if ents[target].get("identity_status") != "resolved":
        reasons.append("目标主体身份没有锁定")
    if any(ents.get(eid, {}).get("listing_status") == "unknown" for eid in reach):
        reasons.append("有主体的上市状态未知")
    if pending:
        reasons.append("有未核实的生效控制边：" + "、".join(pending))
    if not p.get("control_chain_checked") or not p.get("control_evidence_ids"):
        reasons.append("控制链没有核对（control_chain_checked、control_evidence_ids）")
    if reasons:
        return listed, "pending", warnings + reasons
    return listed, ("triggered" if listed else "not_triggered"), warnings


def requirements(data, listed):
    """每个上市主体：5 个基础类别；有绑定到该主体（或目标）的事件时加 2 个事件类别；peer_required 时加 peer。
    official_interim 可以按豁免（理由 + 证据）剔除。返回 [(主体, 类别, 理由, 事件日期)] 和错误。"""
    p, errors, out = data["project"], [], []
    target = p.get("target_entity_id")
    exempt = {}
    for x in p.get("category_exemptions") or []:
        if x["category"] != "official_interim":
            errors.append(f"豁免只允许 official_interim（中期报告），{x['entity_id']} 的 {x['category']} 不能豁免")
        elif not x.get("reason") or not x.get("evidence_ids"):
            errors.append(f"{x['entity_id']} 的中期报告豁免要写理由并附证据")
        else:
            exempt[(x["entity_id"], x["category"])] = x
    for eid in listed:
        events = sorted({e["date"] for e in p.get("events") or [] if e["entity_id"] in (eid, target)})
        cats = list(BASE_CATEGORIES) + (list(EVENT_CATEGORIES) if events else []) + (["peer"] if p.get("peer_required") else [])
        for c in cats:
            if (eid, c) in exempt:
                continue
            reason = {"official_event": "存在重大事件", "event_update": "存在重大事件", "peer": "需要可比研究"}.get(c, "上市主体必读")
            out.append((eid, c, reason, events if c in EVENT_CATEGORIES else []))
    return out, errors


def candidates(data, entity, category):
    """同目标、同覆盖主体、含该类别、未排除、报告日不晚于基准日、来源为 as_of 的报告；去掉被替代版本后按日期倒序。"""
    p = data["project"]
    as_of = p.get("as_of_date") or today()
    sources = _by_id(data["sources"])
    rows = [r for r in data["research_reports"]
            if r["target_id"] == p.get("target_entity_id") and r["coverage_entity_id"] == entity and category in r["categories"]
            and r["relevance"] != "excluded" and r["report_date"] <= as_of
            and (sources.get(r["source_id"], {}).get("time_scope") or "as_of") == "as_of"]
    superseded = {r["supersedes_id"] for r in rows if r.get("supersedes_id")}
    return sorted([r for r in rows if r["id"] not in superseded], key=lambda r: r["report_date"], reverse=True)


def pointers(cands):
    """三个"最新"指针：同一最新日期的多份报告全部列出（优化 7）。"""
    def latest(rows):
        if not rows:
            return []
        top = rows[0]["report_date"]
        return sorted(r["id"] for r in rows if r["report_date"] == top)
    return {"discovered": latest(cands), "fulltext": latest([r for r in cands if r["access_status"] == "full"]),
            "read": latest([r for r in cands if r["reading_status"] == "analyzed" and r["access_status"] == "full"])}


def coverage_state(cov, cands, data, event_dates=()):
    gaps = _by_id(data["gaps"])
    top = [r for r in cands if cands and r["report_date"] == cands[0]["report_date"]]
    read = [r for r in cands if r["access_status"] == "full" and r["reading_status"] == "analyzed"]
    events_ok = all(any(r["report_date"] >= d for r in read) for d in event_dates)
    gap_ok = not cov.get("gap_id") or gaps.get(cov["gap_id"], {}).get("status") in CLOSED_GAP
    complete = (bool(top) and all(r["access_status"] == "full" and r["reading_status"] == "analyzed" and r["relevance"] == "direct" for r in top)
                and events_ok and cov.get("search_status") == "found" and bool(cov.get("search_ids")) and bool(cov.get("latestness_checked_at"))
                and cov.get("event_coverage") in ("covered", "not_applicable") and gap_ok)
    if complete:
        return "complete"
    return "partial" if read else "incomplete"


def research_gate(data, reqs, status_by_key, listing):
    """研报门槛：基于实际的检索和阅读记录判断，不依赖联网标志（优化 5）。"""
    if not reqs:
        return "incomplete" if listing == "pending" else "not_applicable"
    states = [status_by_key.get((e, c), "incomplete") for e, c, _, _ in reqs]
    if all(s == "complete" for s in states) and listing != "pending":
        return "complete"
    if any(s in ("complete", "partial") for s in states):
        return "partial"
    return "incomplete"


def derive(data):
    """一次算出全部推导结果，供 sync 和检查共用。"""
    listed, listing, warnings = listed_entities(data)
    reqs, errors = requirements(data, listed)
    covs = {(c["research_entity_id"], c["category"]): c for c in data["coverage"] if c["target_id"] == data["project"].get("target_entity_id")}
    rows = {}
    for eid, cat, reason, events in reqs:
        cands = candidates(data, eid, cat)
        cov = covs.get((eid, cat), {})
        rows[(eid, cat)] = {"pointers": pointers(cands), "state": coverage_state(cov, cands, data, events), "cands": cands, "events": events}
    gate = research_gate(data, reqs, {k: v["state"] for k, v in rows.items()}, listing)
    return {"listed": listed, "listing": listing, "warnings": warnings, "errors": errors, "requirements": reqs, "rows": rows, "gate": gate}


def sync_coverage(task):
    """为缺失的必读类别建缺口和覆盖行；重算三个指针（含研报表的反向数组）和每行状态；更新 listing_trigger 和 research_gate。
    不检索、不关闭缺口。"""
    led, data = load(task)
    d = derive(data)
    target = data["project"].get("target_entity_id")
    covs = {(c["research_entity_id"], c["category"]): c for c in data["coverage"] if c["target_id"] == target}
    created = []
    for eid, cat, reason, events in d["requirements"]:
        if (eid, cat) in covs:
            continue
        gap_id = led.add("gaps", {"description": f"{eid} 的必读研报类别 {cat} 还没有检索", "module": "18", "entity_id": eid,
                               "reason": "not_executed", "materiality": "major", "priority": "P0", "route": "research",
                               "blocking_scope": "branch", "acquisition_path": "按 references/listed-research.md 检索并阅读", "owner_role": "研究负责人",
                               "status": "open"})
        cov_id = led.add("coverage", {"target_id": target, "research_entity_id": eid, "category": cat, "required": True, "reason": reason,
                                   "search_status": "not_executed", "event_dates": events,
                                   "event_coverage": "pending" if events else "not_applicable", "gate_status": "incomplete", "gap_id": gap_id})
        created.append(cov_id)
    # 重新读取后重算指针与状态
    led, data = load(task)
    d = derive(data)
    back = {r["id"]: {"discovered": set(), "fulltext": set(), "read": set()} for r in data["research_reports"]}
    for c in data["coverage"]:
        key = (c["research_entity_id"], c["category"])
        row = d["rows"].get(key)
        if row is None:
            continue
        ptr = row["pointers"]
        led.patch("coverage", c["id"], {"latest_discovered_ids": ptr["discovered"] or None, "latest_fulltext_ids": ptr["fulltext"] or None,
                                        "latest_read_ids": ptr["read"] or None, "gate_status": row["state"]})
        for kind in ("discovered", "fulltext", "read"):
            for rid in ptr[kind]:
                back[rid][kind].add(c["id"])
    for rid, kinds in back.items():
        led.patch("research_reports", rid, {f"latest_{k}_for": sorted(v) or None for k, v in kinds.items()})
    led.patch("project", "project", {"listing_trigger": d["listing"], "research_gate": d["gate"]})
    return {"created": created, "listing_trigger": d["listing"], "research_gate": d["gate"], "warnings": d["warnings"], "errors": d["errors"]}


# ---------- 检查 ----------

def semantic_errors(data):
    """尽调专属的语义检查（证据账的通用检查之外）。"""
    p, out = data["project"], []
    as_of = p.get("as_of_date")
    sources, ents = _by_id(data["sources"]), _by_id(data["entities"])
    evidence = _by_id(data["evidence"])
    links = {}
    for l in data["claim_evidence"]:
        links.setdefault(l["claim_id"], []).append(l)
    for s in data["sources"]:
        acc = (s.get("accessed") or "")[:10]
        for k in ("published", "revised_date"):
            if s.get(k) and acc and len(s[k]) == 10 and acc < s[k]:
                out.append(f"来源 {s['id']}：访问日 {acc} 早于{k} {s[k]}")
        if as_of and s.get("time_scope", "as_of") == "as_of" and s.get("published") and len(s["published"]) >= 10 and s["published"] > as_of:
            out.append(f"来源 {s['id']}：发布于基准日 {as_of} 之后，却标为 as_of（截止日隔离）")
    for e in data["evidence"]:
        if as_of and e.get("attribute") == "actual" and e.get("period_end") and e["period_end"] > as_of:
            out.append(f"证据 {e['id']}：实际数据的期间结束晚于基准日")
    for c in data["claims"]:
        sup = [l for l in links.get(c["id"], []) if l["relation"] == "supports"]
        if c["verification"] == "verified" and not sup:
            out.append(f"主张 {c['id']}：已核实却没有支持证据")
        if c["verification"] in ("verified", "refuted") and c.get("entity_id") and ents.get(c["entity_id"], {}).get("identity_status") != "resolved":
            out.append(f"主张 {c['id']}：主体 {c['entity_id']} 身份没有锁定，不能形成已核实或已推翻的结论")
        if c["verification"] == "refuted" and (c.get("confidence") not in ("high", "medium") or c.get("unresolved")):
            out.append(f"主张 {c['id']}：被推翻要有高或中置信度，且 unresolved 为空（修正后的结论另建新主张）")
    for r in data["research_reports"]:
        src = sources.get(r["source_id"], {})
        if src and src.get("access") != r["access_status"]:
            out.append(f"研报 {r['id']}：获取状态 {r['access_status']} 与来源 {r['source_id']} 的 {src.get('access')} 不一致")
        if src and r["report_date"] not in {src.get("published"), src.get("revised_date")} - {None}:
            out.append(f"研报 {r['id']}：报告日要等于来源的发布日或修订日（不能用平台收录日、上传日）")
        if r["reading_status"] == "analyzed" and r["access_status"] != "full":
            out.append(f"研报 {r['id']}：只有全文才能标 analyzed")
        if set(r["category_relevance"]) != set(r["categories"]) or not all(str(v).strip() for v in r["category_relevance"].values()):
            out.append(f"研报 {r['id']}：category_relevance 的键要和 categories 一致，且逐类写明相关性")
        if r.get("data_cutoff") and r["data_cutoff"] > r["report_date"]:
            out.append(f"研报 {r['id']}：数据截止日晚于报告日")
        old = _by_id(data["research_reports"]).get(r.get("supersedes_id")) if r.get("supersedes_id") else None
        if r.get("supersedes_id") and (not old or old["publisher"] != r["publisher"] or old["coverage_entity_id"] != r["coverage_entity_id"]
                                       or old["report_date"] > r["report_date"]):
            out.append(f"研报 {r['id']}：替代关系不成立（要同机构、同覆盖主体、日期不早于被替代的报告）")
    return out


def research_errors(data, d):
    out = []
    p = data["project"]
    target = p.get("target_entity_id")
    logs = _by_id(data["search_log"])
    seen = {}
    for c in data["coverage"]:
        if c["target_id"] != target:
            continue
        key = (c["research_entity_id"], c["category"])
        if key in seen:
            out.append(f"覆盖行重复：{key[0]} {key[1]}")
        seen[key] = c
        if c["search_status"] != "not_executed" and not c.get("search_ids"):
            out.append(f"覆盖 {c['id']}：检索状态是 {c['search_status']}，却没有检索记录 ID")
        for sid in c.get("search_ids") or []:
            if logs.get(sid, {}).get("status") == "not_executed":
                out.append(f"覆盖 {c['id']}：引用的检索记录 {sid} 没有实际执行")
    for eid, cat, _, _ in d["requirements"]:
        c = seen.get((eid, cat))
        if c is None:
            out.append(f"必读类别缺覆盖行：{eid} {cat}（运行 diligence sync）")
            continue
        if not c["required"]:
            out.append(f"覆盖 {c['id']}：{cat} 是必读类别，不能标为可选")
        row = d["rows"][(eid, cat)]
        ptr = row["pointers"]
        for kind, field in (("discovered", "latest_discovered_ids"), ("fulltext", "latest_fulltext_ids"), ("read", "latest_read_ids")):
            if sorted(c.get(field) or []) != ptr[kind]:
                out.append(f"覆盖 {c['id']}：{field} 应为 {ptr[kind] or '空'}（运行 diligence sync）")
        if c["gate_status"] != row["state"]:
            out.append(f"覆盖 {c['id']}：gate_status 应为 {row['state']}")
        if row["cands"] and c.get("latestness_checked_at") and c["latestness_checked_at"][:10] < row["cands"][0]["report_date"]:
            out.append(f"覆盖 {c['id']}：最新性复查时间早于已发现的最新报告")
        if row["state"] != "complete" and (not c.get("gap_id") or _by_id(data["gaps"]).get(c["gap_id"], {}).get("status") in CLOSED_GAP):
            out.append(f"覆盖 {c['id']}：没有完成的必读类别要挂一个开放缺口")
    if p.get("research_gate") and p["research_gate"] != d["gate"]:
        out.append(f"project.research_gate 写的是 {p['research_gate']}，推导结果是 {d['gate']}")
    if p.get("listing_trigger") and p["listing_trigger"] != d["listing"]:
        out.append(f"project.listing_trigger 写的是 {p['listing_trigger']}，推导结果是 {d['listing']}")
    if p.get("declared_complete") and d["gate"] not in ("complete", "not_applicable"):
        out.append("declared_complete=true，但研报门槛不是 complete 或 not_applicable")
    return out


def completion_errors(data, d):
    """约定范围完成的条件（report_status=complete 或 declared_complete 时检查）。"""
    p, out = data["project"], []
    claims = _by_id(data["claims"])
    links = {}
    for l in data["claim_evidence"]:
        links.setdefault(l["claim_id"], []).append(l)
    review = p.get("completion_review")
    if not review:
        return ["范围完成要有 completion_review"]
    if not p.get("purpose"):
        out.append("范围完成要先确认目的（purpose）")
    if d["listing"] == "pending":
        out.append("主体或控制链还没锁定（listing_trigger=pending），不能判定范围完成")
    keys = review.get("key_claim_ids") or []
    if not keys:
        out.append("completion_review.key_claim_ids 不能为空")
    for cid in keys:
        c = claims.get(cid)
        if not c:
            out.append(f"关键主张 {cid} 不存在")
            continue
        if c["verification"] != "verified" or c.get("confidence") not in ("high", "medium"):
            out.append(f"关键主张 {cid}：要已核实且置信度为高或中")
        if not any(l["relation"] == "supports" for l in links.get(cid, [])):
            out.append(f"关键主张 {cid}：没有支持证据")
    for c in data["claims"]:
        if c.get("materiality") == "critical" and c["id"] not in keys and c["verification"] != "refuted":
            out.append(f"critical 主张 {c['id']} 要列入关键主张，或作为有效的已推翻主张保留")
    for x in data["conflicts"]:
        if x["status"] == "open" and x.get("decision_changing"):
            out.append(f"冲突 {x['id']} 还开着且会改变决策")
    open_gaps = {g["id"]: g for g in data["gaps"] if g["status"] not in CLOSED_GAP}
    assessed = {a["gap_id"]: a for a in review.get("gap_assessments") or []}
    for gid, a in assessed.items():
        if gid not in open_gaps:
            out.append(f"completion_review 评估的缺口 {gid} 不是当前开放的缺口")
        elif a["disposition"] == "blocks_completion" or open_gaps[gid]["materiality"] == "critical":
            out.append(f"缺口 {gid} 阻断完成（blocks_completion 或 critical）")
    for gid in sorted(set(open_gaps) - set(assessed)):
        out.append(f"开放缺口 {gid} 没有在 completion_review 里评估影响")
    for (eid, cat), row in d["rows"].items():
        cov = next((c for c in data["coverage"] if c["research_entity_id"] == eid and c["category"] == cat), None)
        if cov and (cov["search_status"] == "not_executed" or not cov.get("latestness_checked_at")):
            out.append(f"必读类别 {eid} {cat} 没有实际检索或没有复查最新性")
    if p.get("declared_complete"):
        if open_gaps:
            out.append("declared_complete=true 时不能有开放缺口")
        if any(a["status"] != "completed" for a in p.get("completed_actions") or []):
            out.append("declared_complete=true 时所有动作都要完成")
    return out
