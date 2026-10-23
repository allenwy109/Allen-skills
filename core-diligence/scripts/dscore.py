"""评分（能力清单 E 节评分框架、H 节 scoring.py 的规则）。默认关闭；公司研究禁止评分；专项必须由用户确认权重和关键维度。

只计高或中置信度、证据充分的维度；覆盖率达不到门槛、关键维度缺分、有会改变决策的开放冲突或 critical 开放缺口时不发布综合分。
分数、风险、证据充分度分开呈现。
"""
DIMENSIONS = ("business", "growth", "governance", "financial", "compliance", "technology", "operations", "deal")
# 各目的的默认权重（总 100，顺序同 DIMENSIONS）与关键维度：只是建议起点，启用评分时由用户在 scoring_override 里确认
DEFAULT_WEIGHTS = {
    "investment": ((20, 20, 10, 20, 10, 10, 5, 5), ("business", "financial", "compliance")),
    "acquisition": ((15, 10, 10, 25, 10, 5, 10, 15), ("financial", "compliance", "deal")),
    "partnership": ((20, 5, 10, 15, 15, 15, 20, 0), ("business", "operations", "compliance")),
    "credit": ((10, 0, 10, 40, 20, 0, 15, 5), ("financial", "compliance")),
    "supplier": ((10, 0, 10, 20, 15, 10, 35, 0), ("operations", "financial", "compliance")),
    "competitor": ((25, 20, 5, 15, 5, 20, 10, 0), ("business", "technology")),
}
CLOSED = ("resolved", "unavailable")


def default_override(purpose):
    weights, critical = DEFAULT_WEIGHTS[purpose]
    return {"weights": dict(zip(DIMENSIONS, weights)), "critical_dimensions": list(critical)}


def score(data):
    p = data["project"]
    purpose = p.get("purpose")
    if not purpose:
        status = "purpose_pending"
        if p.get("published_score") is not None:
            return {"status": status, "errors": ["目的未定时不能发布分数"]}
        return {"status": status, "errors": []}
    if purpose == "company_research":
        errors = ["公司研究不能启用评分或发布分数"] if p.get("scoring_enabled") or p.get("published_score") is not None else []
        return {"status": "not_applicable", "errors": errors}
    if not p.get("scoring_enabled"):
        return {"status": "disabled", "errors": ["评分没有启用却写了 published_score"] if p.get("published_score") is not None else []}
    ov = p.get("scoring_override")
    if not ov:
        return {"status": "criteria_pending", "errors": [], "suggested": default_override(purpose)}
    errors = []
    weights, critical = ov.get("weights") or {}, ov.get("critical_dimensions") or []
    if not str(ov.get("reason") or "").strip():
        errors.append("scoring_override 要写理由")
    if set(weights) != set(DIMENSIONS):
        errors.append("scoring_override.weights 要写全 8 个维度")
    if not critical or len(set(critical)) != len(critical):
        errors.append("关键维度不能为空或重复")
    threshold = p.get("scoring_threshold", 0.8)
    if not 0 <= threshold <= 1:
        errors.append("scoring_threshold 要在 0–1 之间")
    rows = [r for r in data["scorecard"]]
    if any(r["purpose"] != purpose for r in rows):
        errors.append("评分行的目的与项目不一致")
    dims = [r["dimension"] for r in rows]
    if len(set(dims)) != len(dims) or set(dims) != set(weights):
        errors.append("评分行的维度要不重复，且与权重的维度完全一致")
    for d in critical:
        if not weights.get(d):
            errors.append(f"关键维度 {d} 必须有权重")
    retro = {s["id"] for s in data["sources"] if s.get("time_scope") == "retrospective"}
    ev_src = {e["id"]: e["source_id"] for e in data["evidence"]}
    for r in rows:
        if abs(r["weight"] - weights.get(r["dimension"], -1)) > 1e-9:
            errors.append(f"{r['id']}：权重要等于 scoring_override 里的 {r['dimension']}")
        if r["applicability"] == "not_applicable" and r.get("score") is not None:
            errors.append(f"{r['id']}：不适用的维度不能打分")
        if r.get("score") is not None:
            if not 1 <= r["score"] <= 5:
                errors.append(f"{r['id']}：分数要在 1–5")
            if r["coverage_status"] != "sufficient" or not r.get("evidence_ids") or not r.get("anchor") or r["confidence"] not in ("high", "medium"):
                errors.append(f"{r['id']}：打了分的维度要证据充分、有锚点、置信度为高或中")
            if any(ev_src.get(e) in retro for e in r.get("evidence_ids") or []):
                errors.append(f"{r['id']}：打分不能用事后资料")
        elif r["applicability"] == "applicable":
            if not r.get("reason"):
                errors.append(f"{r['id']}：没打分要写理由")
            if r["coverage_status"] == "sufficient":
                errors.append(f"{r['id']}：没打分不能标 sufficient")
    if errors:
        return {"status": "invalid", "errors": errors}
    applicable = [r for r in rows if r["applicability"] == "applicable"]
    if not applicable:
        return {"status": "not_applicable", "errors": []}
    total_w = sum(r["weight"] for r in applicable)
    if total_w <= 0:
        return {"status": "invalid", "errors": ["适用维度的权重和要大于 0"]}
    scored = [r for r in applicable if r.get("score") is not None]
    scored_w = sum(r["weight"] for r in scored)
    coverage = scored_w / total_w
    partial = sum(r["weight"] * r["score"] for r in scored) / scored_w if scored_w else None
    missing_critical = [d for d in critical if not any(r["dimension"] == d and r.get("score") is not None for r in rows)]
    open_conflicts = [x["id"] for x in data["conflicts"] if x["status"] == "open" and x.get("decision_changing")]
    critical_gaps = [g["id"] for g in data["gaps"] if g["status"] not in CLOSED and g["materiality"] == "critical"]
    publish = coverage + 1e-12 >= threshold and not missing_critical and not open_conflicts and not critical_gaps
    overall = partial if publish else None
    result = {"status": "complete" if publish else "insufficient_evidence", "errors": [], "coverage": coverage, "partial_score": partial,
              "overall_score": overall, "missing_critical": missing_critical, "open_decision_conflicts": open_conflicts, "critical_gaps": critical_gaps,
              "weights": {r["dimension"]: r["weight"] / total_w for r in applicable}, "configuration_reason": ov.get("reason"),
              "research_gate": p.get("research_gate"),
              "note": "分数只汇总已评分维度；风险、证据充分度和研报覆盖要分开看"}
    pub = p.get("published_score")
    if pub is not None and (overall is None or abs(pub - overall) > 1e-8):
        result["errors"].append(f"published_score={pub} 与计算出的综合分 {overall} 不一致（或不满足发布条件）")
    return result
