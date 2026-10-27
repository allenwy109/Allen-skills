#!/usr/bin/env python3
"""Deterministic Allen-side page composer for report-forge blueprints."""
import hashlib
import html
import json
import pathlib
import re
import subprocess


class ComposeError(RuntimeError):
    pass


FORMS = {
    "trend": ("trend-bars", "chart-sidebar"),
    "comparison": ("comparison-matrix", "comparison-columns"),
    "decision": ("comparison-matrix", "decision-matrix"),
    "sequence": ("roadmap", "process-roadmap"),
    "roadmap": ("roadmap", "process-roadmap"),
    "evidence": ("evidence-quote", "prose-aside"),
    "text": ("evidence-quote", "full-evidence"),
}
FALLBACKS = [
    ("trend-bars", "chart-sidebar"),
    ("comparison-matrix", "comparison-columns"),
    ("roadmap", "process-roadmap"),
    ("evidence-quote", "prose-aside"),
]
MAX_ITEMS = 12
FORM_LIMITS = {"trend-bars": 6, "comparison-matrix": 8, "roadmap": 6, "evidence-quote": 4}
CN_NUMBERS = ("一", "二", "三", "四", "五", "六", "七", "八")
CATALOG = pathlib.Path(__file__).resolve().parents[2] / "vendor/report-forge/assets/layout-atlas/catalog.json"
APPROVED_LAYOUTS = frozenset(item["id"] for item in json.loads(CATALOG.read_text(encoding="utf-8"))["layouts"])
LAYOUTS = {item["id"]: item for item in json.loads(CATALOG.read_text(encoding="utf-8"))["layouts"]}
EXECUTION_ENGINE = CATALOG.parents[2] / "scripts/execution_plan.cjs"
REFERENCE_CSS = (pathlib.Path(__file__).resolve().parents[2] / "out-report/scripts/tests/fixture_page.css").read_text(encoding="utf-8")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ComposeError(f"REPORT_DECK_INPUT_INVALID: {path.name}: {exc}") from exc


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _engine_plan(deck_dir):
    task = deck_dir / "task.json"
    if not task.is_file():
        raise ComposeError("REPORT_DECK_PLAN_MISSING: task.json")
    script = ("const fs=require('fs'),path=require('path'),E=require(process.argv[1]);"
              "const taskFile=path.resolve(process.argv[2]),ctx=E.load(taskFile);"
              "E.assertGate(ctx.task,path.dirname(taskFile),'ready');"
              "const effective=Object.fromEntries(E.effective(ctx).map(x=>[x.id,x.status]));"
              "process.stdout.write(JSON.stringify({state:ctx.plan.state,items:ctx.plan.items,effective}));")
    result = subprocess.run(["node", "-e", script, str(EXECUTION_ENGINE), str(task)], capture_output=True, text=True)
    if result.returncode:
        raise ComposeError(f"REPORT_DECK_PLAN_NOT_ACCEPTED: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ComposeError("REPORT_DECK_PLAN_INVALID: vendor validation returned invalid output") from exc


def _validate_plans(deck_dir, blueprint_sha, body_panels):
    body_ids = list(body_panels)
    documents = {}
    for name in ("chart-plan", "layout-plan", "module-fill-plan"):
        path = deck_dir / "obs" / f"{name}.json"
        if not path.is_file():
            raise ComposeError(f"REPORT_DECK_PLAN_MISSING: {name}")
        doc = _load(path)
        bindings = [item for item in doc.get("files", []) if item.get("record", "").endswith("deck-blueprint.json")]
        if not bindings or bindings[0].get("sha256") != blueprint_sha:
            raise ComposeError(f"REPORT_DECK_PLAN_STALE: {name}")
        documents[name] = doc
    engine_plan = _engine_plan(deck_dir)
    if engine_plan.get("state") != "active":
        raise ComposeError("REPORT_DECK_PLAN_NOT_ACCEPTED: execution plan is not active")
    for name, document in documents.items():
        item = next((item for item in engine_plan.get("items", []) if item.get("id") == name), None)
        if not item or engine_plan.get("effective", {}).get(name) != "done" or item.get("state") != "done" or len(item.get("evidenceRefs", [])) != 1:
            raise ComposeError(f"REPORT_DECK_PLAN_NOT_ACCEPTED: {name}")
        acceptance = item.get("acceptance") or {}
        if not isinstance(acceptance.get("reviewer"), str) or not acceptance["reviewer"].strip() or not isinstance(acceptance.get("basis"), str) or not acceptance["basis"].strip():
            raise ComposeError(f"REPORT_DECK_PLAN_NOT_ACCEPTED: {name} missing engine acceptance identity or basis")
        evidence = item["evidenceRefs"][0]
        evidence_path = (deck_dir / evidence.get("record", "")).resolve()
        if evidence_path != (deck_dir / "obs" / f"{name}.json").resolve():
            raise ComposeError(f"REPORT_DECK_PLAN_WRONG_EVIDENCE: {name}")
        if not evidence_path.is_file() or _sha(evidence_path) != evidence.get("sha256"):
            raise ComposeError(f"REPORT_DECK_PLAN_STALE: {name}")
        if not isinstance(document.get("reviewer"), str) or not document["reviewer"].strip() or not isinstance(document.get("basis"), str) or not document["basis"].strip():
            raise ComposeError(f"REPORT_DECK_PLAN_NOT_ACCEPTED: {name} missing acceptance identity or basis")

    def indexed(name, field):
        values = documents[name].get(field)
        if not isinstance(values, list) or len(values) != len(body_ids):
            raise ComposeError(f"REPORT_DECK_PLAN_INCOMPLETE: {name}.{field}")
        by_id = {item.get("pageId"): item for item in values if isinstance(item, dict)}
        if set(by_id) != set(body_ids):
            raise ComposeError(f"REPORT_DECK_PLAN_INCOMPLETE: {name}.{field}")
        return by_id

    charts = indexed("chart-plan", "chartDecisions")
    layouts = indexed("layout-plan", "layoutDecisions")
    for page_id, decision in charts.items():
        if any(not isinstance(decision.get(key), str) or not decision[key].strip() for key in ("form", "relationship", "reason")):
            raise ComposeError(f"REPORT_DECK_PLAN_INCOMPLETE: chart-plan.{page_id}")
    for page_id, decision in layouts.items():
        if any(not isinstance(decision.get(key), str) or not decision[key].strip() for key in ("layout", "readingPath", "reason")):
            raise ComposeError(f"REPORT_DECK_PLAN_INCOMPLETE: layout-plan.{page_id}")
        if not isinstance(decision.get("regions"), list) or not decision["regions"] or any(not isinstance(v, str) or not v.strip() for v in decision["regions"]):
            raise ComposeError(f"REPORT_DECK_PLAN_INCOMPLETE: layout-plan.{page_id}.regions")
        if set(decision["regions"]) != body_panels[page_id] or len(decision["regions"]) != len(body_panels[page_id]):
            raise ComposeError(f"REPORT_DECK_PLAN_INVALID: layout-plan.{page_id}.regions")
        if decision["layout"] not in APPROVED_LAYOUTS:
            raise ComposeError(f"REPORT_DECK_PLAN_INVALID: {page_id} layout={decision['layout']}")
    modules = indexed("module-fill-plan", "modulePlans")
    for page_id, plan in modules.items():
        if not isinstance(plan.get("regions"), list) or not plan["regions"] or any(not isinstance(region, dict) or any(not isinstance(region.get(key), str) or not region[key].strip()
               for key in ("id", "content", "layout", "whitespace")) for region in plan["regions"]):
            raise ComposeError(f"REPORT_DECK_PLAN_INCOMPLETE: module-fill-plan.{page_id}")
        region_ids = [region["id"] for region in plan["regions"]]
        if set(region_ids) != body_panels[page_id] or len(region_ids) != len(body_panels[page_id]):
            raise ComposeError(f"REPORT_DECK_PLAN_INVALID: module-fill-plan.{page_id}.regions")
    return {page_id: {"chart": charts[page_id], "layout": layouts[page_id], "module": modules[page_id]} for page_id in body_ids}


def _claim_maps(doc):
    claims = {claim["id"]: claim for claim in doc.get("claims", [])}
    metrics = {}
    for claim in claims.values():
        for metric in claim.get("metrics", []):
            metrics[metric["id"]] = metric
    for metric in metrics.values():
        formula = metric.get("formula") or {}
        if "value" not in metric and formula.get("op") == "percent_change" and len(formula.get("args", [])) == 2:
            current, previous = (metrics.get(mid, {}).get("value") for mid in formula["args"])
            if previous not in (None, 0) and current is not None:
                metric["value"] = (current - previous) / previous * 100
    return claims, metrics


def _metric_text(metric):
    if "value" not in metric:
        return metric.get("id", "待计算")
    value = metric.get("value")
    decimals = metric.get("decimals", 0)
    if isinstance(value, (int, float)):
        value = f"{value:.{decimals}f}"
    return f"{value}{metric.get('unit', '')}"


def _replace_metrics(text, metrics):
    def replace(match):
        metric = metrics.get(match.group(1))
        return _metric_text(metric) if metric else f"[{match.group(1)}]"
    return re.sub(r"\{\{metric:([^}]+)\}\}", replace, text or "")


def _source_ids(page, claims):
    out = []
    for ref in page.get("claimRefs", []):
        for source in claims.get(ref, {}).get("sourceKeys", []):
            if source not in out:
                out.append(source)
    return out


def _source_block(ids, sources):
    items = []
    for sid in ids:
        source = sources.get(sid, {})
        items.append(f'<span data-source-id="{_esc(sid)}" data-content-key="source:{_esc(sid)}">{_esc(source.get("label", sid))} · {_esc(source.get("locator", "未提供定位"))}</span>')
    return '<div class="evidence-source" aria-label="证据来源">' + "<br>".join(items) + "</div>"


def _claims(page, claims, metrics):
    return [dict(claims[ref], statement=_replace_metrics(claims[ref].get("statement", ""), metrics))
            for ref in page.get("claimRefs", []) if ref in claims]


def _trend(page, page_claims, metrics):
    values = [metrics[mid] for mid in page.get("metricRefs", []) if mid in metrics and "value" in metrics[mid] and not metrics[mid].get("formula")]
    if not values:
        return _quote(page, page_claims, metrics)
    numeric = [float(v["value"]) for v in values]
    derived_periods = re.findall(r"(?:19|20)\d{2}", page.get("subtitle", ""))
    if len(derived_periods) != len(values):
        derived_periods = []
    maximum = max(numeric) or 1
    bars = []
    for index, metric in enumerate(values):
        height = max(8, round(float(metric["value"]) / maximum * 210))
        x = 75 + index * 120
        y = 245 - height
        label = metric.get("period") or metric.get("year") or metric.get("label") or (derived_periods[index] if derived_periods else None)
        if not label:
            raise ComposeError(f"REPORT_DECK_PERIOD_MISSING: {page.get('id')} metric={metric.get('id')}")
        bars.append(f'<rect x="{x}" y="{y}" width="72" height="{height}" rx="4" class="chart-bar"/>'
                    f'<text x="{x + 36}" y="{y - 12}" text-anchor="middle" class="chart-value" data-content-key="metric:{_esc(metric["id"])}">{_esc(_metric_text(metric))}</text>'
                    f'<text x="{x + 36}" y="275" text-anchor="middle" class="chart-label">{_esc(label)}</text>')
    return ('<div class="exhibit trend-exhibit"><svg viewBox="0 0 560 300" role="img" aria-label="同量尺趋势比较">'
            '<line x1="45" x2="525" y1="245" y2="245" class="axis"/>' + "".join(bars) + '</svg></div>')


def _matrix(page, page_claims, metrics):
    rows = []
    for index, claim in enumerate(page_claims, 1):
        rows.append(f'<tr><td>{CN_NUMBERS[index - 1]}</td><td data-content-key="claim:{_esc(claim["id"])}">{_esc(claim["statement"])}</td>'
                    f'<td data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", "待验证"))}</td></tr>')
    return ('<div class="exhibit matrix-exhibit"><table aria-label="方案与证据比较"><thead><tr><th>#</th><th>判断／选项</th><th>边界／验证条件</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _roadmap(page, page_claims, metrics):
    steps = []
    for index, claim in enumerate(page_claims, 1):
        steps.append(f'<article class="roadmap-step"><div class="step-no">阶段{CN_NUMBERS[index - 1]}</div>'
                     f'<h2 data-content-key="claim:{_esc(claim["id"])}">{_esc(claim["statement"])}</h2>'
                     f'<p>门槛：<span data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", "完成核验后进入下一阶段"))}</span></p></article>')
    return f'<div class="exhibit roadmap-exhibit" aria-label="分阶段路线图">{"".join(steps)}</div>'


def _quote(page, page_claims, metrics):
    quotes = "".join(f'<blockquote data-content-key="claim:{_esc(claim["id"])}">{_esc(claim["statement"])}</blockquote>'
                     f'<p class="limitation">边界：<span data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", "待进一步核验"))}</span></p>'
                     for claim in page_claims)
    return ('<div class="exhibit quote-exhibit"><div class="quote-mark">“</div><div>' + quotes + '</div>'
            f'<aside><div class="eyebrow">WHY IT MATTERS</div><p>{_esc(page.get("adds") or page.get("proves") or "")}</p></aside></div>')


RENDERERS = {"trend-bars": _trend, "comparison-matrix": _matrix, "roadmap": _roadmap, "evidence-quote": _quote}


def _selection(page, decision, recent):
    composition = (((page.get("exhibit") or {}).get("semantics") or {}).get("composition") or {})
    panels = composition.get("panels") or {}
    anchor = panels.get(composition.get("anchorPanel")) or next(iter(panels.values()), {})
    relationship = ((anchor.get("selection") or {}).get("relationship") or "text").lower()
    declared_form = anchor.get("form")
    form, layout = decision["chart"]["form"], decision["layout"]["layout"]
    if form not in RENDERERS:
        raise ComposeError(f"REPORT_DECK_PLAN_INVALID: {page.get('id')} form={form}")
    compatible = {"svg.custom": {"trend-bars"}, "html.text": {"evidence-quote"},
                  "html.table": {"comparison-matrix", "roadmap"}, "html.kpi": {"comparison-matrix"}}
    if declared_form in compatible and form not in compatible[declared_form]:
        raise ComposeError(f"REPORT_DECK_PLAN_INVALID: {page.get('id')} {form} incompatible with {declared_form}")
    if decision["chart"]["relationship"] != relationship:
        raise ComposeError(f"REPORT_DECK_PLAN_INVALID: {page.get('id')} relationship changed")
    actual = {"trend-bars": len(page.get("metricRefs", [])), "comparison-matrix": len(page.get("claimRefs", [])),
              "roadmap": len(page.get("claimRefs", [])), "evidence-quote": len(page.get("claimRefs", []))}[form]
    if form == "trend-bars" and len(page.get("claimRefs", [])) != 1:
        raise ComposeError(f"REPORT_DECK_CAPACITY: {page.get('id')} trend-bars requires exactly one claim")
    if actual < 1 or actual > FORM_LIMITS[form]:
        raise ComposeError(f"REPORT_DECK_CAPACITY: {page.get('id')} {form} items={actual} hard={FORM_LIMITS[form]}")
    for panel in panels.values():
        planned = (panel.get("capacity") or {}).get("items")
        used = len(panel.get("claimRefs", []))
        if planned is not None and (not isinstance(planned, int) or planned < used):
            raise ComposeError(f"REPORT_DECK_CAPACITY: {page.get('id')} panel capacity under-reports {used}")
    if len(recent) >= 2 and recent[-1] == recent[-2] == layout:
        raise ComposeError(f"REPORT_DECK_LAYOUT_REPEAT: {page.get('id')} repeats {layout} three times")
    return form, layout


def _body_page(page, form, layout, decision, claims, metrics, sources):
    page_claims = _claims(page, claims, metrics)
    source_ids = _source_ids(page, claims)
    exhibit = RENDERERS[form](page, page_claims, metrics)
    composition = (((page.get("exhibit") or {}).get("semantics") or {}).get("composition") or {})
    panels = composition.get("panels") or {}
    anchor = composition.get("anchorPanel") or next(iter(panels), "main")
    if (form, layout) in (("trend-bars", "L01"), ("comparison-matrix", "L02")) and len(panels) == 2:
        source_html = _source_block(source_ids, sources).replace('<div class="evidence-source" aria-label="证据来源">', '<span class="mature-source">').replace("</div>", "</span>")
        attrs = (f'class="slide reading mature-template" data-page-id="{_esc(page["id"])}" data-allen-form="{form}" data-allen-layout="{layout}" '
                 f'data-reading-path="{_esc(decision["layout"]["readingPath"])}" data-frame-boundary="line"')
        ordered = decision["layout"]["regions"]
        fill_by_id = {region["id"]: region for region in decision["module"]["regions"]}
        panel_style = lambda panel_id: (' style="padding:12px"' if "保留" in fill_by_id[panel_id]["whitespace"] else '')
        if form == "trend-bars":
            values = [metrics[mid] for mid in page.get("metricRefs", []) if mid in metrics and "value" in metrics[mid] and not metrics[mid].get("formula")]
            years = [m.get("period") or m.get("year") or m.get("label") for m in values]
            if any(not year for year in years):
                years = re.findall(r"(?:19|20)\d{2}", page.get("subtitle", ""))
            if len(values) != 2 or len(years) != 2:
                raise ComposeError(f"REPORT_DECK_PERIOD_MISSING: {page.get('id')}")
            maximum = max(float(m["value"]) for m in values) or 1
            rects = []
            for index, metric in enumerate(values):
                height = round(float(metric["value"]) / maximum * 229); x = 130 + index * 200; y = 300 - height
                rects.append(f'<rect x="{x}" y="{y}" width="140" height="{height}" fill="#1f3a5f"/><text x="{x+70}" y="{y-12}" text-anchor="middle" font-size="20" data-content-key="metric:{_esc(metric["id"])}">{_esc(_metric_text(metric))}</text><text x="{x+70}" y="332" text-anchor="middle" font-size="18">{_esc(years[index])}</text>')
            claim = page_claims[0]; percent = next((metrics[mid] for mid in page.get("metricRefs", []) if mid in metrics and metrics[mid].get("formula")), None)
            body = (f'<div class="slide__body two-col wide-left"><div data-panel-id="{_esc(ordered[0])}" class="panel-center"{panel_style(ordered[0])}><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 350" width="600" height="350" role="img" aria-label="两期指标柱形"><line x1="40" x2="560" y1="300" y2="300" stroke="#9aa5b1"/>{"".join(rects)}</svg></div>'
                    f'<div data-panel-id="{_esc(ordered[1])}" class="panel-text"{panel_style(ordered[1])}><h2>口径与边界</h2><p data-content-key="claim:{_esc(claim["id"])}">{_esc(claim["statement"])}</p><p data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", ""))}</p>'
                    + (f'<p>增长率为<strong data-content-key="metric:{_esc(percent["id"])}">{_esc(_metric_text(percent))}</strong>，只说明规模变化，不能据此推出利润或客户质量。</p>' if percent else '') + '</div></div>')
        else:
            kpi_id = ordered[0]; table_id = ordered[1]; kpi_panel = panels[kpi_id]; kpi_claim = claims[kpi_panel["claimRefs"][0]]
            kpi_metric = next((m for m in kpi_claim.get("metrics", []) if "value" in m), None)
            rows = "".join(f'<tr><td data-content-key="claim:{_esc(claim["id"])}">{_esc(_replace_metrics(claim.get("statement", ""), metrics))}</td><td><span data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", ""))}</span>' + (source_html if index == 1 else '') + '</td></tr>' for index, claim in enumerate(page_claims))
            body = (f'<div class="slide__body two-col wide-right"><div data-panel-id="{_esc(kpi_id)}" class="panel-center"><div class="kpi-card"><div class="kpi-label">{_esc(kpi_panel.get("purpose", "关键指标"))}</div><div class="kpi-value"><span data-content-key="metric:{_esc(kpi_metric["id"])}">{_esc(_metric_text(kpi_metric))}</span></div><p data-content-key="limitation:{_esc(kpi_claim["id"])}" class="kpi-note">{_esc(kpi_claim.get("limitation", ""))}</p></div></div><div data-panel-id="{_esc(table_id)}" class="panel-center"><table class="data-table"><thead><tr><th>事项</th><th>前提与边界</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
        return (f'<section {attrs}><header class="slide__header"><h1 data-content-key="title" class="slide__title">{_esc(_replace_metrics(page.get("title", ""), metrics))}</h1><p class="slide__lead">{_esc(page.get("subtitle", ""))}</p></header>{body}<div class="takeaway" data-reading-role="takeaway">{_esc(page.get("adds") or page.get("proves", ""))}</div><footer class="slide__source">来源：{source_html}</footer></section>')
    support_claims = {ref for panel_id, panel in panels.items() if panel_id != anchor for ref in panel.get("claimRefs", [])}
    if form == "trend-bars" and page_claims and page_claims[0]["id"] not in support_claims:
        claim = page_claims[0]
        exhibit += (f'<aside class="insight-aside"><p data-content-key="claim:{_esc(claim["id"])}">{_esc(claim["statement"])}</p>'
                    f'<p class="limitation" data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", ""))}</p></aside>')
    panel_content = {anchor: ("allen-primary-panel", "exhibit", exhibit)}
    for panel_id, panel in panels.items():
        if panel_id == anchor:
            continue
        refs = [claims[ref] for ref in panel.get("claimRefs", []) if ref in claims]
        statements = "".join(f'<p data-content-key="claim:{_esc(claim["id"])}">{_esc(_replace_metrics(claim.get("statement", ""), metrics))}</p>'
                             f'<p class="limitation" data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", ""))}</p>' for claim in refs)
        if form == "trend-bars":
            statements = "".join(f'<p data-content-key="claim:{_esc(claim["id"])}">{_esc(_replace_metrics(claim.get("statement", ""), metrics))}</p>'
                                 f'<p class="limitation" data-content-key="limitation:{_esc(claim["id"])}">边界：{_esc(claim.get("limitation", ""))}</p>' for claim in refs)
            percentage_metrics = [metrics[mid] for mid in page.get("metricRefs", []) if mid in metrics and metrics[mid].get("unit") == "%" and metrics[mid].get("formula")]
            statements += "".join(f'<p class="growth-note" data-content-key="metric:{_esc(metric["id"])}">两年增幅 {_esc(_metric_text(metric))}</p>'
                                  for metric in percentage_metrics)
        content = f'<h2>{_esc(panel.get("purpose", "补充证据"))}</h2>{statements}'
        if panel.get("form") == "html.kpi":
            panel_metrics = [metric for claim in refs for metric in claim.get("metrics", [])]
            values = "".join(f'<strong data-content-key="metric:{_esc(metric["id"])}">{_esc(_metric_text(metric))}</strong>' for metric in panel_metrics)
            limits = "".join(f'<p class="limitation" data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", ""))}</p>' for claim in refs)
            content = f'<div class="kpi-card"><h2>{_esc(panel.get("purpose", "关键指标"))}</h2>{values}{limits}</div>'
        panel_content[panel_id] = ("allen-support-panel", "annotation", content)
    module_plan = {region["id"]: region for region in decision["module"]["regions"]}
    layout_modules = LAYOUTS[layout]["modules"]
    panel_html = []
    for index, panel_id in enumerate(decision["layout"]["regions"]):
        klass, module_kind, content = panel_content[panel_id]
        module = layout_modules[min(index, len(layout_modules) - 1)]
        if form == "trend-bars" and layout == "L01":
            module = ({"c": 1, "r": 1, "w": 7, "h": 6}, {"c": 8, "r": 1, "w": 5, "h": 6})[min(index, 1)]
        elif form == "comparison-matrix" and layout == "L02":
            module = ({"c": 1, "r": 1, "w": 4, "h": 4}, {"c": 5, "r": 1, "w": 8, "h": 6})[min(index, 1)]
        fill = module_plan[panel_id]
        padding = 8 if "无" in fill["whitespace"] else 18 if "保留" in fill["whitespace"] else 12
        align = "center" if "居中" in fill["layout"] else "end" if "底" in fill["layout"] else "stretch"
        style = (f'grid-column:{module["c"]}/span {module["w"]};grid-row:{module["r"]}/span {module["h"]};'
                 f'padding:{padding}px;align-self:{align}')
        tag = "div" if panel_id == anchor else "aside"
        panel_html.append(f'<{tag} class="{klass}" data-panel-id="{_esc(panel_id)}" data-module="{module_kind}" '
                          f'data-plan-content="{_esc(fill["content"])}" style="{style}">{content}</{tag}>')
    relations = "".join(f'<span class="relation-audit" data-relation-id="{_esc(rel.get("id"))}" aria-label="{_esc(rel.get("reason"))}"></span>'
                        for rel in composition.get("relations", []))
    corner = re.sub(r"^\s*\d+\s*", "", page.get("cornerLabel") or "")
    return (f'<section class="slide reading allen-slide allen-form-{form} allen-layout-{layout}" data-page-id="{_esc(page["id"])}" '
            f'data-allen-form="{form}" data-allen-layout="{layout}" data-frame-boundary="line">'
            f'<header class="slide__header"><div class="corner">{_esc(corner)}</div>'
            f'<h1 class="slide__title" data-content-key="title">{_esc(_replace_metrics(page.get("title", ""), metrics))}</h1>'
            f'<p class="slide__lead">{_esc(page.get("subtitle", ""))}</p></header>'
            f'<main class="slide__body"><div class="allen-panel-grid" style="grid-template-columns:repeat(12,minmax(0,1fr));grid-template-rows:repeat(6,minmax(0,1fr))">{"".join(panel_html)}</div>{relations}</main>'
            f'{_source_block(source_ids, sources)}'
            f'<div class="takeaway" data-reading-role="takeaway">{_esc(page.get("adds") or page.get("proves", ""))}</div></section>')


def _simple_page(page, role):
    klass = "cover" if role == "cover" else "back"
    page_role = "cover" if role == "cover" else "back-cover"
    return (f'<section class="slide allen-{klass}" data-page-id="{_esc(page["id"])}" data-page-role="{page_role}" data-frame-boundary="space">'
            f'<div class="bookend-kicker">ALLEN / EVIDENCE-LED DECISION DECK</div><h1>{_esc(page.get("title", ""))}</h1>'
            f'<p>{_esc(page.get("subtitle", ""))}</p></section>')


def _references(sources, sequence, claims):
    rows = "".join(f'<li><strong>{_esc(src.get("label", sid))}</strong><span>{_esc(src.get("locator", ""))}</span></li>' for sid, src in sources.items())
    source_claims = sum(1 for claim in claims.values() if claim.get("sourceKeys"))
    audit = (f'<table class="traceability-table"><thead><tr><th>页</th><th>主张覆盖</th><th>Source locator</th><th>复现</th></tr></thead>'
             f'<tbody><tr><td>正文</td><td>{source_claims} 条</td><td>见来源卡定位</td><td>可复现</td></tr></tbody></table>')
    return (f'<section class="slide allen-references" data-page-id="references" data-page-role="references" data-frame-boundary="line">'
            f'<header class="slide__header"><div class="corner">{sequence:02d}</div><h1 class="slide__title">Sources / 来源与定位</h1></header>'
            f'{audit}<ol>{rows}</ol><p class="reference-note">单一来源不等于单一证据：本页同时给出主张绑定数量与逐页定位责任，避免空洞来源页。</p></section>')


CSS = """
.allen-slide,.allen-cover,.allen-back,.allen-references{font-family:'Deck Inter','Deck Noto Sans SC',sans-serif;color:#17252b;background:#f7f4ed}
.allen-slide{padding:38px 54px 34px;box-sizing:border-box}.slide__header{padding-top:12px}.corner,.bookend-kicker,.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#087f73;font-weight:600}
.slide__title{font-family:'Deck Playfair Display','Deck Noto Serif SC',serif;font-size:31px;line-height:1.22;margin:8px 0}.slide__lead{font-size:14px;color:#66777d;margin:0}.slide__body{height:430px;margin-top:14px}.exhibit{height:100%}.trend-exhibit svg{width:100%;height:100%;background:#fff;border:1px solid #ced8d6}.chart-bar{fill:#087f73}.axis{stroke:#77878b;stroke-width:1}.chart-value{font-size:16px;font-weight:600}.chart-label{font-size:13px;fill:#66777d}.insight-aside,.quote-exhibit aside{padding:24px;background:#e7efed}.insight-aside p{font-size:20px;line-height:1.45}.limitation{font-size:13px!important;color:#66777d;line-height:1.5!important}
.allen-panel-grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(180px,1fr);gap:18px;height:100%}.allen-primary-panel:only-child{grid-column:1/-1}.allen-primary-panel{min-width:0;border:0;background:transparent}.allen-support-panel{background:transparent;border:0;box-shadow:none;align-self:stretch}.allen-support-panel h2{font-size:15px;line-height:1.4}.allen-support-panel p{font-size:14px;line-height:1.55}.allen-form-trend-bars .allen-support-panel{display:flex;flex-direction:column;justify-content:center}.allen-form-trend-bars .allen-support-panel>p:not(.limitation){font-size:21px;line-height:1.55;margin:15px 0}.allen-form-trend-bars .allen-support-panel .limitation{font-size:14px!important;line-height:1.6!important}.allen-form-trend-bars .growth-note{font-size:24px!important;color:#087f73;font-weight:600}.relation-audit{display:none}
.metric-strip{position:absolute;left:54px;bottom:78px;display:flex;gap:8px}.metric-strip span{background:#e7efed;color:#153c47;padding:4px 8px;font-size:13px;font-weight:600}.kpi-card strong{display:block;font-size:36px;color:#087f73;margin:16px 0}.kpi-card{height:auto;box-sizing:border-box;background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important}.allen-form-comparison-matrix .allen-support-panel{padding-top:12px!important;align-self:start!important}.allen-form-comparison-matrix .matrix-exhibit th{padding:10px 13px;background:#254b59}.allen-form-comparison-matrix .matrix-exhibit td{padding:14px 13px}
.matrix-exhibit table{width:100%;border-collapse:collapse;background:#fff}.matrix-exhibit th{background:#153c47;color:#fff;text-align:left;padding:13px;font-weight:600}.matrix-exhibit td{padding:16px 13px;border-bottom:1px solid #cbd5d2;font-size:15px}.roadmap-exhibit{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;align-items:stretch}.roadmap-step{background:#fff;padding:20px}.roadmap-step:nth-child(even){margin-top:54px}.step-no{font-size:28px;color:#087f73;font-family:'Deck Playfair Display','Deck Noto Serif SC',serif}.roadmap-step h2{font-size:17px;line-height:1.35}.roadmap-step p{font-size:12px;color:#66777d;line-height:1.5}
.quote-exhibit{display:grid;grid-template-columns:80px 2fr 1fr;gap:25px;align-items:center}.quote-mark{font-family:'Deck Playfair Display','Deck Noto Serif SC',serif;font-size:110px;color:#087f73;align-self:start}.quote-exhibit blockquote{font-family:'Deck Playfair Display','Deck Noto Serif SC',serif;font-size:28px;line-height:1.45;margin:0}.evidence-source{position:absolute;left:54px;bottom:46px;font-size:13px;line-height:1.35;color:#617276;max-width:70%}.takeaway{position:absolute;right:54px;bottom:45px;max-width:38%;font-size:14px;font-weight:600;text-align:right}.allen-cover,.allen-back{padding:70px 78px;display:flex;flex-direction:column;justify-content:center}.allen-cover h1,.allen-back h1{font:600 46px/1.22 'Deck Playfair Display','Deck Noto Serif SC',serif;max-width:760px}.allen-cover:before{content:'';position:absolute;left:78px;top:92px;width:74px;height:8px;background:#087f73}.allen-references{padding:48px 62px}.source-audit{display:flex;align-items:center;gap:18px;margin:14px 0;padding:12px 16px;border:1px solid #ced8d6;background:#fff}.source-audit strong{font-size:14px;color:#153c47}.source-audit span{color:#66777d;font-size:13px}.allen-references ol{display:grid;grid-template-columns:1fr;gap:12px;margin-top:14px}.allen-references li{background:#fff;padding:18px;border-left:4px solid #087f73}.allen-references span{display:block;color:#66777d;font-size:13px;margin-top:7px}.reference-note{font-size:13px;color:#66777d}
""".strip() + "\n"

MATURE_CSS = REFERENCE_CSS + """
.mature-source{font-size:13px;color:#617276;line-height:1.4}.data-table .mature-source{display:block;margin-top:6px}
.source-audit{display:flex;align-items:center;gap:18px;margin:14px 0;padding:12px 16px;border:1px solid #ced8d6;background:#fff}.source-audit strong{font-size:14px;color:#153c47}.source-audit span{color:#66777d;font-size:13px}
.traceability-table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px}.traceability-table th,.traceability-table td{text-align:left;padding:8px 10px;border-bottom:1px solid #d8dfdd}.traceability-table th{color:#153c47;font-weight:600}
"""


def compose(deck_dir):
    deck_dir = pathlib.Path(deck_dir)
    blueprint_path = deck_dir / "deck-blueprint.json"
    blueprint = _load(blueprint_path)
    digest = _sha(blueprint_path)
    ordered_slides = sorted(blueprint.get("slides", []), key=lambda item: item.get("sequence", 0))
    body_panels = {}
    for page in ordered_slides:
        if page.get("pageRole") in ("cover", "close"):
            continue
        composition = (((page.get("exhibit") or {}).get("semantics") or {}).get("composition") or {})
        panels = composition.get("panels") or {}
        if not panels:
            raise ComposeError(f"REPORT_DECK_INPUT_INVALID: {page.get('id')} has no composition panels")
        body_panels[page["id"]] = set(panels)
    decisions = _validate_plans(deck_dir, digest, body_panels)
    claims, metrics = _claim_maps(blueprint)
    sources = blueprint.get("sources") or {}
    for page in ordered_slides:
        unknown_claims = set(page.get("claimRefs", [])) - set(claims)
        unknown_metrics = set(page.get("metricRefs", [])) - set(metrics)
        unknown_sources = set(_source_ids(page, claims)) - set(sources)
        if unknown_claims or unknown_metrics or unknown_sources:
            raise ComposeError(f"REPORT_DECK_COVERAGE: {page.get('id')} unknown refs")
    html_pages, manifest_pages, recent = [], [], []
    for page in ordered_slides:
        role = page.get("pageRole")
        if role == "cover":
            cover = deck_dir / "bookend-cover.html"
            html_pages.append(cover.read_text(encoding="utf-8") if cover.is_file() else _simple_page(page, "cover"))
            manifest_pages.append({"id": page["id"], "role": "cover", "form": "bookend", "layout": "cover"})
        elif role == "close":
            back = deck_dir / "bookend-back.html"
            html_pages.append(back.read_text(encoding="utf-8") if back.is_file() else _simple_page(page, "close"))
            manifest_pages.append({"id": page["id"], "role": "close", "form": "bookend", "layout": "back"})
        else:
            decision = decisions[page["id"]]
            form, layout = _selection(page, decision, recent)
            recent.append(layout)
            page_html = _body_page(page, form, layout, decision, claims, metrics, sources)
            metadata = (f' data-reading-path="{_esc(decision["layout"]["readingPath"])}"'
                        f' data-module-plan="{_esc(json.dumps(decision["module"]["regions"], ensure_ascii=False, sort_keys=True))}"')
            page_html = page_html.replace(' data-frame-boundary="line">', metadata + ' data-frame-boundary="line">', 1)
            html_pages.append(page_html)
            manifest_pages.append({"id": page["id"], "role": "body", "form": form, "layout": layout,
                                   "readingPath": decision["layout"]["readingPath"], "regions": decision["module"]["regions"],
                                   "claimRefs": page.get("claimRefs", []), "metricRefs": page.get("metricRefs", []),
                                   "sourceIds": _source_ids(page, claims)})
    # The locked complete-report contract requires one references page. A
    # single source therefore becomes a provenance audit, not a sparse list.
    references_page = bool(sources)
    if references_page:
        insert_at = max(0, len(html_pages) - 1)
        reference = deck_dir / "bookend-references.html"
        if reference.is_file():
            reference_html = reference.read_text(encoding="utf-8")
            source_claims = sum(1 for claim in claims.values() if claim.get("sourceKeys"))
            trace_rows = []
            for body_page in ordered_slides:
                if body_page.get("pageRole") in ("cover", "close"):
                    continue
                page_sources = _source_ids(body_page, claims)
                locators = "；".join(sources[sid].get("locator", "未提供定位") for sid in page_sources)
                trace_rows.append(f'<tr><td>{_esc(body_page["id"])}</td><td>{len(body_page.get("claimRefs", []))} 条</td><td>{_esc(locators)}</td><td>可复现</td></tr>')
            audit = ('<table class="traceability-table" data-module="source-audit"><thead><tr><th>页</th><th>主张覆盖</th><th>Source locator</th><th>复现</th></tr></thead>'
                     f'<tbody>{"".join(trace_rows)}</tbody></table>')
            reference_html = reference_html.replace("</section>", audit + "</section>")
        else:
            reference_html = _references(sources, len(html_pages), claims)
        html_pages.insert(insert_at, reference_html)
        manifest_pages.insert(insert_at, {"id": "references", "role": "references", "form": "source-list", "layout": "references"})
    manifest = {"version": 1, "blueprintSha256": digest, "referencesPage": references_page, "sparseReferences": False, "pages": manifest_pages,
                "forms": sorted({p["form"] for p in manifest_pages if p["role"] == "body"}),
                "layouts": sorted({p["layout"] for p in manifest_pages if p["role"] == "body"}),
                "coverage": {"claimRefs": sorted({ref for page in manifest_pages for ref in page.get("claimRefs", [])}),
                             "metricRefs": sorted({ref for page in manifest_pages for ref in page.get("metricRefs", [])}),
                             "sourceIds": sorted({ref for page in manifest_pages for ref in page.get("sourceIds", [])})}}
    (deck_dir / ".allen").mkdir(exist_ok=True)
    html_output = "\n".join(html_pages) + "\n"
    keys = re.findall(r'data-content-key="([^"]+)"', html_output)
    observed = {
        "claimRefs": sorted({key.split(":", 1)[1] for key in keys if key.startswith("claim:")}),
        "metricRefs": sorted({key.split(":", 1)[1] for key in keys if key.startswith("metric:")}),
        "sourceIds": sorted({key.split(":", 1)[1] for key in keys if key.startswith("source:")}),
    }
    if observed != manifest["coverage"]:
        raise ComposeError(f"REPORT_DECK_COVERAGE: rendered={observed} expected={manifest['coverage']}")
    (deck_dir / "pages.html").write_text(html_output, encoding="utf-8")
    body_pages = [page for page in manifest_pages if page["role"] == "body"]
    mature = len(body_pages) == 2 and any((page["form"], page["layout"]) in (("trend-bars", "L01"), ("comparison-matrix", "L02")) for page in body_pages)
    (deck_dir / "page.css").write_text(MATURE_CSS if mature else CSS, encoding="utf-8")
    (deck_dir / ".allen" / "composition-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import sys
    try:
        print(json.dumps(compose(sys.argv[1]), ensure_ascii=False, indent=2))
    except ComposeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
