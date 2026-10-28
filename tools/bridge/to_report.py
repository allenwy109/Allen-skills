#!/usr/bin/env python3
"""Deterministically convert slides.json and its ledger to a medium-neutral report model."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib import schema_check  # noqa: E402
from tools.lib.ledger import Ledger, LedgerError  # noqa: E402


CONTENT_ROLES = {"analysis", "decision", "action", "risk"}
FORM_KIND = {
    "svg.custom": "chart",
    "html.text": "text",
    "html.kpi": "metric",
    "html.table": "table",
}
LAYOUT_CATALOG = json.loads((ROOT / "out-report" / "assets" / "a4-layout-catalog.json").read_text(encoding="utf-8"))
EXHIBIT_LAYOUTS = {item["kind"]: item for item in LAYOUT_CATALOG["exhibits"]}


def _route_exhibit_kind(panel):
    semantic = panel.get("semantic_type")
    if semantic == "point_evidence":
        return None
    matches = [item for item in LAYOUT_CATALOG["exhibits"] if semantic in item["semantic_types"]]
    if len(matches) == 1:
        return matches[0]["kind"]
    relationship = panel.get("relationship")
    capacity = panel.get("capacity") or {}
    candidates = [item for item in LAYOUT_CATALOG["exhibits"] if relationship in item["relationships"]]
    fitting = [item for item in candidates if capacity.get(item["capacity"]["field"], 0) <= item["capacity"]["hard"]]
    return fitting[0]["kind"] if len(fitting) == 1 else None


def _native_exhibit(panel, semantic_content):
    kind = _route_exhibit_kind(panel)
    if kind not in EXHIBIT_LAYOUTS:
        return None
    layout = EXHIBIT_LAYOUTS[kind]
    form = panel.get("form")
    if not form:
        raise ReportError("REPORT_EXHIBIT_MISSING", f"panel {panel.get('id')} 的 {kind} 缺少 form")
    supplied = panel.get("exhibit")
    if supplied:
        if supplied.get("kind", kind) != kind:
            raise ReportError("REPORT_EXHIBIT_MISMATCH", f"panel {panel.get('id')} 的 exhibit kind 不一致")
        declared_form = supplied.get("form", form)
        if declared_form != form or declared_form not in layout["forms"]:
            raise ReportError("REPORT_EXHIBIT_MISMATCH", f"panel {panel.get('id')} 的 {kind} 不能使用 {declared_form}")
        exhibit = {**supplied, "kind": kind, "form": declared_form}
    elif kind == "pain-comparison" and semantic_content.get("pain_groups"):
        groups = semantic_content["pain_groups"]
        exhibit = {"kind": kind, "family": "matrix", "form": form, "columns": ["当前替代", "后果", "购买信号"],
                   "rows": [{"label": row["segment"], "values": [row["workaround"], row["consequence"], row["purchase_signal"]]} for row in groups]}
    elif kind == "competitor-matrix" and semantic_content.get("comparison"):
        comparison = semantic_content["comparison"]
        exhibit = {"kind": kind, "family": "matrix", "form": form, "columns": comparison["criteria"],
                   "rows": [{"label": row["name"], "values": [row["values"].get(column, "未提供") for column in comparison["criteria"]]} for row in comparison["alternatives"]]}
    else:
        raise ReportError("REPORT_EXHIBIT_MISSING", f"panel {panel.get('id')} 的 {kind} 缺少结构化 exhibit")
    if exhibit.get("family") != layout["family"]:
        raise ReportError("REPORT_EXHIBIT_MISMATCH", f"panel {panel.get('id')} 的 family 与 catalog 不一致")
    missing = [field for field in layout["required_fields"] if not exhibit.get(field)]
    if missing:
        raise ReportError("REPORT_EXHIBIT_MISSING", f"panel {panel.get('id')} 缺少 {','.join(missing)}")
    count = len(exhibit[layout["capacity"]["field"]])
    if kind == "competitor-matrix" and any(len(row.get("values", [])) != len(exhibit["columns"]) for row in exhibit["rows"]):
        raise ReportError("REPORT_EXHIBIT_MISMATCH", f"panel {panel.get('id')} 的 competitor matrix 行宽与 columns 不一致")
    if count > layout["capacity"]["hard"]:
        raise ReportError("REPORT_EXHIBIT_MISMATCH", f"panel {panel.get('id')} 超过 hard capacity")
    forbidden = [field for field in layout["forbidden_content"] if exhibit.get(field)]
    if forbidden:
        raise ReportError("REPORT_EXHIBIT_MISMATCH", f"panel {panel.get('id')} 含 forbidden content：{','.join(forbidden)}")
    exhibit["selected_layout"] = kind
    exhibit["layout_reason"] = f"{panel.get('relationship')} · {count}/{layout['capacity']['hard']} {layout['capacity']['unit']}"
    exhibit["capacity_state"] = "soft-exceeded" if count > layout["capacity"]["soft"] else "within-soft"
    return exhibit


class ReportError(Exception):
    def __init__(self, code, problems):
        self.code = code
        self.problems = problems if isinstance(problems, list) else [problems]
        super().__init__(f"{code}: " + "；".join(self.problems))


def _unique(values, label, problems):
    seen = set()
    for value in values:
        if value in seen:
            problems.append(f"重复 {label}：{value}")
        seen.add(value)
    return seen


def _index(records, table, problems):
    """Index only after duplicate IDs have been reported; never silently overwrite."""
    seen = set()
    duplicate = False
    for record in records:
        rid = record.get("id")
        if rid in seen:
            problems.append(f"{table} 重复 id：{rid}")
            duplicate = True
        seen.add(rid)
    if duplicate:
        return {}
    return {record["id"]: record for record in records}


def _refs_for_claims(claim_ids, links, evidence):
    evidence_ids = {link["evidence_id"] for link in links if link["claim_id"] in claim_ids}
    return {evidence[eid]["source_id"] for eid in evidence_ids if eid in evidence}


def _source_bindings(claim_ids, links, evidence, explicit=()):
    locators = {source_id: set() for source_id in explicit}
    for link in links:
        if link["claim_id"] not in claim_ids:
            continue
        item = evidence[link["evidence_id"]]
        locators.setdefault(item["source_id"], set()).add(item["locator"])
    return [{"source_id": source_id, "locators": sorted(values)}
            for source_id, values in sorted(locators.items())]


def _claim_details(claim_ids, claims, links, evidence):
    details = []
    for claim_id in sorted(claim_ids):
        claim = claims[claim_id]
        related = [link for link in links if link["claim_id"] == claim_id]
        grouped = {}
        for link in related:
            item = evidence[link["evidence_id"]]
            grouped.setdefault(link["relation"], []).append({
                "source_id": item["source_id"], "locator": item["locator"],
                "excerpt": item.get("excerpt") or item.get("claim_text") or item.get("interpretation", ""),
            })
        scopes = sorted({link.get("applicable_scope", "") for link in related if link.get("applicable_scope")})
        scope = claim.get("population") or claim.get("scope") or ("；".join(scopes) if scopes else "未限定")
        details.append({
            "id": claim_id, "statement": claim["statement"], "identity": claim["kind"],
            "confidence": claim["confidence"], "scope": scope, "limitation": claim["limitation"],
            "support_label": "indirect_lead" if claim["kind"] == "recommendation" or claim.get("verification") == "unverified" else "support",
            "support": grouped.get("supports", []), "counter": grouped.get("contradicts", []),
        })
    return details


def _decision_research(task):
    path = pathlib.Path(task) / "03_evidence" / "decision-research.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _semantic_content(panel, panel_claims, claims, decision):
    semantic = panel.get("semantic_type")
    result = {}
    if semantic == "pain-demand":
        rows = []
        for pain in decision.get("pain", []):
            refs = set(pain.get("support_claim_refs", [])) | set(pain.get("counter_claim_refs", []))
            if not refs.intersection(panel_claims):
                continue
            counter = "；".join(claims[ref]["statement"] for ref in pain.get("counter_claim_refs", []) if ref in claims)
            rows.append({
                "segment": pain["segment"], "trigger": pain["trigger"], "workaround": pain["workaround"],
                "consequence": pain["consequence"], "purchase_signal": pain["purchase_signal"],
                "evidence_strength": pain["confidence"], "counter": counter or "未取得结构化反证",
                "validation_gap": pain["validation_gap"],
            })
        if rows:
            result["pain_groups"] = rows
    if semantic == "competition" and decision.get("competition"):
        competition = decision["competition"]
        criteria = competition.get("criteria", [])
        alternatives = []
        for layer, entries in competition.get("layers", {}).items():
            for entry in entries:
                alternatives.append({
                    "name": entry["name"], "layer": layer,
                    "values": {criterion: entry.get("values", {}).get(criterion, "待同口径核实") for criterion in criteria},
                })
        result["comparison"] = {"criteria": criteria, "alternatives": alternatives}
    return result


def _citation_registry(sections, source_ids):
    ordered = []
    seen = set()
    for section in sections:
        for block in section["blocks"]:
            for source_id in block["source_ids"]:
                if source_id not in seen:
                    seen.add(source_id)
                    ordered.append(source_id)
    ordered.extend(sorted(set(source_ids) - seen))
    return [{"source_id": source_id, "number": number, "appendix_anchor": f"source-{source_id}"}
            for number, source_id in enumerate(ordered, 1)]


def validate_report(report):
    """Validate report structure plus uniqueness and internal reference integrity."""
    problems = schema_check.check_document(schema_check.load("report.schema.json"), report, "report.json")
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)
    registry = report["registry"]
    known = {key: set(values) for key, values in registry.items()}
    for key, values in registry.items():
        _unique(values, f"registry.{key}", problems)
    blocks = [block for section in report["sections"] for block in section["blocks"]]
    _unique([block["id"] for block in blocks], "block id", problems)
    relations = [relation for section in report["sections"] for relation in section["relations"]]
    _unique([relation["id"] for relation in relations], "relation id", problems)
    checks = (("claim_refs", "claim_ids", "claim"), ("metric_refs", "metric_ids", "metric"),
              ("source_ids", "source_ids", "source"), ("panel_refs", "panel_ids", "panel"),
              ("relation_refs", "relation_ids", "relation"))
    for block in blocks:
        exhibit = block.get("content", {}).get("exhibit")
        if exhibit:
            semantic = block["content"].get("semantic_type")
            layout = next((item for item in LAYOUT_CATALOG["exhibits"] if semantic in item["semantic_types"]), None)
            if not layout or exhibit.get("selected_layout") != layout["kind"] or exhibit.get("capacity_state") not in {"within-soft", "soft-exceeded"}:
                raise ReportError("REPORT_EXHIBIT_MISMATCH", f"block {block['id']} 的 selected_layout/capacity_state 与 catalog 不一致")
        for field, registry_field, label in checks:
            _unique(block[field], f"block {block['id']} {field}", problems)
            for ref in sorted(set(block[field]) - known[registry_field]):
                problems.append(f"block {block['id']} 引用了未知 {label}：{ref}")
        binding_ids = [binding["source_id"] for binding in block["source_bindings"]]
        _unique(binding_ids, f"block {block['id']} source binding", problems)
        for binding in block["source_bindings"]:
            _unique(binding["locators"], f"block {block['id']} source binding locator", problems)
        if set(binding_ids) != set(block["source_ids"]):
            problems.append(f"block {block['id']} 的 source_bindings 与 source_ids 不一致")
    _unique(report["executive_summary"]["answer_claim_refs"], "executive_summary.answer_claim_refs", problems)
    _unique(report["executive_summary"]["a_card_refs"], "executive_summary.a_card_refs", problems)
    for ref in sorted(set(report["executive_summary"]["answer_claim_refs"]) - known["claim_ids"]):
        problems.append(f"executive_summary 引用了未知 claim：{ref}")
    for ref in sorted(set(report["executive_summary"]["a_card_refs"]) - known["card_ids"]):
        problems.append(f"executive_summary 引用了未知 card：{ref}")
    for relation in relations:
        _unique(relation["panel_refs"], f"relation {relation['id']} panel_refs", problems)
        for ref in sorted(set(relation["panel_refs"]) - known["panel_ids"]):
            problems.append(f"relation {relation['id']} 引用了未知 panel：{ref}")
    reference_ids = [reference["id"] for reference in report["references"]]
    _unique(reference_ids, "references source id", problems)
    if "citation_registry" in report:
        citation_ids = [item["source_id"] for item in report["citation_registry"]]
        citation_numbers = [item["number"] for item in report["citation_registry"]]
        citation_anchors = [item["appendix_anchor"] for item in report["citation_registry"]]
        _unique(citation_ids, "citation_registry source id", problems)
        _unique(citation_numbers, "citation_registry number", problems)
        _unique(citation_anchors, "citation_registry appendix anchor", problems)
        if set(citation_ids) != set(reference_ids):
            problems.append("citation_registry 与 references 来源不一致")
        if citation_numbers != list(range(1, len(citation_numbers) + 1)):
            problems.append("citation_registry number 必须从 1 连续递增")
        for item in report["citation_registry"]:
            if item["appendix_anchor"] != f"source-{item['source_id']}":
                problems.append(f"citation_registry appendix anchor 与 source 不一致：{item['source_id']}")
    actual = {
        "claim_ids": ({ref for block in blocks for ref in block["claim_refs"]}
                      | set(report["executive_summary"]["answer_claim_refs"])),
        "metric_ids": {ref for block in blocks for ref in block["metric_refs"]},
        "source_ids": set(reference_ids),
        "panel_ids": {ref for block in blocks for ref in block["panel_refs"]},
        "relation_ids": {relation["id"] for relation in relations},
        "card_ids": set(report["executive_summary"]["a_card_refs"]),
    }
    for field, values in actual.items():
        if known[field] != values:
            problems.append(f"registry.{field} 与报告实际内容不一致")
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)
    return []


def build(task, slides, sidecar=None, bibliography_policy=None):
    """Return ``(report, coverage)`` or raise ReportError with a stable code."""
    if bibliography_policy not in (None, "evidence_package", "full"):
        raise ReportError("REPORT_COVERAGE_MISMATCH", "bibliography_policy 只能是 evidence_package 或显式 full")
    problems = schema_check.check_document(schema_check.load("slides.schema.json"), slides, "slides.json")
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)

    ledger = Ledger(task)
    problems = []
    relevant = {"claims", "metrics", "sources", "cards", "evidence", "claim_evidence"}
    try:
        ledger_issues = ledger.check()
    except (LedgerError, KeyError, TypeError, ValueError) as error:
        raise ReportError("REPORT_COVERAGE_MISMATCH", f"证据账无法校验：{error}") from error
    for issue in ledger_issues:
        if issue["level"] != "error" or issue["table"] not in relevant:
            continue
        message = issue["message"]
        if message == "id 重复":
            message = f"{issue['table']} 重复 id：{issue['id']}"
        problems.append(message)
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)
    claim_records = ledger.read("claims")
    metric_records = ledger.read("metrics")
    source_records = ledger.read("sources")
    cards = ledger.read("cards")
    claims = _index(claim_records, "claims", problems)
    metrics = _index(metric_records, "metrics", problems)
    sources = _index(source_records, "sources", problems)
    _index(cards, "cards", problems)
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)
    evidence_records = ledger.read("evidence")
    link_records = ledger.read("claim_evidence")
    evidence = _index(evidence_records, "evidence", problems)
    _index(link_records, "claim_evidence", problems)
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)
    links = link_records
    decision = _decision_research(task)
    content = sorted((slide for slide in slides["slides"] if slide["page_role"] in CONTENT_ROLES),
                     key=lambda slide: slide["page"])

    claim_refs = [ref for slide in content for ref in slide.get("claim_refs", [])]
    metric_refs = [ref for slide in content for ref in slide.get("metric_refs", [])]
    panel_ids = [panel["id"] for slide in content for panel in slide.get("panels", [])]
    relation_ids = [relation["id"] for slide in content for relation in slide.get("relations", [])]
    problems = []
    _unique(panel_ids, "panel id", problems)
    _unique(relation_ids, "relation id", problems)
    for ref in sorted(set(claim_refs) - set(claims)):
        problems.append(f"未知 claim：{ref}")
    for ref in sorted(set(metric_refs) - set(metrics)):
        problems.append(f"未知 metric：{ref}")
    answer_claim_refs = slides["deck"].get("answer_claim_refs", [])
    for ref in sorted(set(answer_claim_refs) - set(claims)):
        problems.append(f"deck.answer_claim_refs 引用了未知 claim：{ref}")

    for slide in content:
        panels = slide.get("panels", [])
        local_panels = {panel["id"] for panel in panels}
        anchor = slide.get("anchor_panel")
        if anchor and anchor not in local_panels:
            problems.append(f"第 {slide['page']} 页 anchor_panel 引用了未知 panel：{anchor}")
        related = set()
        for relation in slide.get("relations", []):
            if len(set(relation["panel_refs"])) < 2:
                problems.append(f"relation {relation['id']} 至少两个不同 panel 才能构成 relation")
            for ref in relation["panel_refs"]:
                if ref not in local_panels:
                    problems.append(f"relation {relation['id']} 引用了未知 panel：{ref}")
                else:
                    related.add(ref)
        if len(panels) > 1:
            for ref in sorted(local_panels - related):
                problems.append(f"第 {slide['page']} 页存在孤儿 panel：{ref}")
        for panel in panels:
            unknown = sorted(set(panel["claim_refs"]) - set(claims))
            for ref in unknown:
                problems.append(f"panel {panel['id']} 引用了未知 claim：{ref}")
            if panel["form"] not in FORM_KIND:
                raise ReportError("REPORT_UNSUPPORTED_BLOCK", f"不支持的 block form：{panel['form']}")

    a_cards = sorted(card["id"] for card in cards if card.get("value_tier") == "A")
    a_claims = set()
    for card in cards:
        if card.get("value_tier") != "A":
            continue
        if not card.get("claim_id"):
            problems.append(f"A 级卡片 {card['id']} 缺少 claim_id")
        else:
            a_claims.add(card["claim_id"])
    missing_a = sorted(ref for ref in a_claims if ref not in set(claim_refs))
    if missing_a:
        problems.append("A 级卡片的 claim 未进入正文：" + "、".join(missing_a))
    source_ids = _refs_for_claims(set(claim_refs), links, evidence)
    for card in cards:
        if card.get("value_tier") == "A":
            source_ids.update(ref["source_id"] for ref in card.get("source_refs", []))
    for slide in content:
        for panel in slide.get("panels", []):
            source_ids.update(panel.get("source_ids", []))
    for ref in sorted(source_ids - set(sources)):
        problems.append(f"未知 source：{ref}")
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)

    sections = []
    output_claims, output_metrics, output_sources = set(), set(), set(source_ids)
    output_panels, output_relations = set(), set()
    for index, slide in enumerate(content, 1):
        slide_claims = set(slide.get("claim_refs", []))
        slide_metrics = set(slide.get("metric_refs", []))
        relations = sorted(slide.get("relations", []), key=lambda item: item["id"])
        blocks = []
        for panel in sorted(slide.get("panels", []), key=lambda item: item["id"]):
            panel_claims = sorted(set(panel["claim_refs"]))
            panel_metrics = sorted(mid for cid in panel_claims for mid in claims[cid].get("metric_refs", []) if mid in slide_metrics)
            panel_sources = _refs_for_claims(set(panel_claims), links, evidence) | set(panel.get("source_ids", []))
            source_bindings = _source_bindings(set(panel_claims), links, evidence, panel.get("source_ids", []))
            rel_refs = sorted(r["id"] for r in relations if panel["id"] in r["panel_refs"])
            semantic_content = _semantic_content(panel, set(panel_claims), claims, decision)
            native_exhibit = _native_exhibit(panel, semantic_content)
            if not native_exhibit and panel.get("semantic_type") != "point_evidence":
                raise ReportError("REPORT_EXHIBIT_MISSING", f"panel {panel.get('id')} 的 {panel.get('semantic_type') or '<missing>'} 无法唯一路由；请显式声明 exhibit kind")
            blocks.append({
                "id": f"p{slide['page']:02d}-{panel['id']}",
                "kind": FORM_KIND[panel["form"]],
                "claim_refs": panel_claims,
                "metric_refs": sorted(set(panel_metrics)),
                "source_ids": sorted(panel_sources),
                "source_bindings": source_bindings,
                "panel_refs": [panel["id"]],
                "relation_refs": rel_refs,
                "identity": sorted({claims[cid]["kind"] for cid in panel_claims}),
                "content": {k: v for k, v in {
                    "title": slide["action_title"], "subtitle": slide.get("subtitle"),
                    "purpose": panel["purpose"], "form": panel["form"],
                    "relationship": panel["relationship"], "reason": panel["reason"],
                    "anchor": panel["id"] == slide.get("anchor_panel"),
                    "role": panel["role"], "alternative": panel.get("alternative"),
                    "tradeoff": panel.get("tradeoff"), "capacity": panel.get("capacity"),
                    "semantic_type": (native_exhibit or {}).get("kind") or "point_evidence", "visual": panel.get("visual"),
                    "slot": panel["slot"], "span": panel["span"],
                    "claims": _claim_details(panel_claims, claims, links, evidence),
                    "exhibit": native_exhibit,
                    **semantic_content,
                }.items() if v is not None},
            })
            output_claims.update(panel_claims)
            output_metrics.update(panel_metrics)
            output_sources.update(panel_sources)
            output_panels.add(panel["id"])
        output_relations.update(r["id"] for r in relations)
        sections.append({"id": f"section-{index:02d}", "title": slide.get("section") or slide["action_title"],
                         "blocks": blocks, "relations": relations})

    expected = {
        "claims": sorted(set(claim_refs)), "a_cards": a_cards, "panels": sorted(panel_ids),
        "relations": sorted(relation_ids), "metrics": sorted(set(metric_refs)), "sources": sorted(source_ids),
        "answer_claims": sorted(set(answer_claim_refs)),
    }
    actual = {
        "claims": sorted(output_claims), "a_cards": a_cards, "panels": sorted(output_panels),
        "relations": sorted(output_relations), "metrics": sorted(output_metrics), "sources": sorted(output_sources),
        "answer_claims": sorted(set(answer_claim_refs)),
    }
    if expected != actual:
        differences = [f"{key}: input={expected[key]} output={actual[key]}" for key in expected if expected[key] != actual[key]]
        raise ReportError("REPORT_COVERAGE_MISMATCH", differences)

    deck = slides["deck"]
    cover = deck.get("cover", {})
    reference_locators = {source_id: set() for source_id in source_ids}
    for binding in _source_bindings(set(claim_refs), links, evidence):
        reference_locators[binding["source_id"]].update(binding["locators"])
    for card in cards:
        if card.get("value_tier") == "A":
            for ref in card.get("source_refs", []):
                if ref.get("locator"):
                    reference_locators[ref["source_id"]].add(ref["locator"])
    report = {
        "version": "1.0.0",
        "metadata": {k: v for k, v in {"title": deck["title"], "language": deck["language"],
                                        "audience": deck.get("audience"), "decision": deck.get("decision"),
                                        "date": cover.get("date"),
                                        "bibliography_policy": bibliography_policy or "evidence_package",
                                        "client_citations": "compact"}.items() if v is not None},
        "executive_summary": {"question": deck.get("brief", {}).get("question", deck["title"]),
                              "answer_claim_refs": sorted(set(answer_claim_refs)), "a_card_refs": list(a_cards)},
        "registry": {"claim_ids": sorted(set(expected["claims"]) | set(expected["answer_claims"])),
                     "metric_ids": list(expected["metrics"]),
                     "source_ids": list(expected["sources"]), "card_ids": list(expected["a_cards"]),
                     "panel_ids": list(expected["panels"]), "relation_ids": list(expected["relations"])},
        "citation_registry": _citation_registry(sections, source_ids),
        "sections": sections,
        "references": [{k: v for k, v in {"id": sid, "title": sources[sid]["title"], "url": sources[sid].get("final_url") or sources[sid].get("url"),
                                                "origin": sources[sid]["origin"], "author": sources[sid].get("author_org"),
                                                "publisher": sources[sid].get("publisher"), "published": sources[sid].get("published"),
                                                "accessed": sources[sid].get("accessed"), "grade": sources[sid].get("grade"),
                                                "conflict_of_interest": sources[sid].get("conflict_of_interest"),
                                                "locators": sorted(reference_locators[sid])}.items() if v is not None} for sid in sorted(source_ids)],
        "appendix": [],
    }
    validate_report(report)
    return report, {"version": "1.0.0", "input": expected, "output": actual}
