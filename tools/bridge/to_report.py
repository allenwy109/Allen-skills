#!/usr/bin/env python3
"""Deterministically convert slides.json and its ledger to a medium-neutral report model."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib import schema_check  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402


CONTENT_ROLES = {"analysis", "decision", "action", "risk"}
FORM_KIND = {
    "svg.custom": "chart",
    "html.text": "text",
    "html.kpi": "metric",
    "html.table": "table",
}


class ReportError(Exception):
    def __init__(self, code, problems):
        self.code = code
        self.problems = problems if isinstance(problems, list) else [problems]
        super().__init__("；".join(self.problems))


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


def build(task, slides, sidecar=None):
    """Return ``(report, coverage)`` or raise ReportError with a stable code."""
    problems = schema_check.check_document(schema_check.load("slides.schema.json"), slides, "slides.json")
    if problems:
        raise ReportError("REPORT_COVERAGE_MISMATCH", problems)

    ledger = Ledger(task)
    problems = []
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
    evidence = {item["id"]: item for item in ledger.read("evidence")}
    links = ledger.read("claim_evidence")
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
            rel_refs = sorted(r["id"] for r in relations if panel["id"] in r["panel_refs"])
            blocks.append({
                "id": f"p{slide['page']:02d}-{panel['id']}",
                "kind": FORM_KIND[panel["form"]],
                "claim_refs": panel_claims,
                "metric_refs": sorted(set(panel_metrics)),
                "source_ids": sorted(panel_sources),
                "panel_refs": [panel["id"]],
                "relation_refs": rel_refs,
                "identity": sorted({claims[cid]["kind"] for cid in panel_claims}),
                "content": {k: v for k, v in {
                    "title": slide["action_title"], "subtitle": slide.get("subtitle"),
                    "purpose": panel["purpose"], "form": panel["form"],
                    "relationship": panel["relationship"], "reason": panel["reason"],
                    "anchor": panel["id"] == slide.get("anchor_panel"),
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
    report = {
        "version": "1.0.0",
        "metadata": {k: v for k, v in {"title": deck["title"], "language": deck["language"],
                                        "audience": deck.get("audience"), "decision": deck.get("decision"),
                                        "date": cover.get("date")}.items() if v is not None},
        "executive_summary": {"question": deck.get("brief", {}).get("question", deck["title"]),
                              "answer_claim_refs": sorted(set(answer_claim_refs)), "a_card_refs": a_cards},
        "sections": sections,
        "references": [{k: v for k, v in {"id": sid, "title": sources[sid]["title"], "url": sources[sid].get("final_url") or sources[sid].get("url"),
                                                "origin": sources[sid]["origin"]}.items() if v is not None} for sid in sorted(source_ids)],
        "appendix": [],
    }
    schema_errors = schema_check.check_document(schema_check.load("report.schema.json"), report, "report.json")
    if schema_errors:
        raise ReportError("REPORT_COVERAGE_MISMATCH", schema_errors)
    return report, {"version": "1.0.0", "input": expected, "output": actual}
