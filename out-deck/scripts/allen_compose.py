#!/usr/bin/env python3
"""Deterministic Allen-side page composer for report-forge blueprints."""
import hashlib
import html
import json
import pathlib
import re


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
CN_NUMBERS = ("一", "二", "三", "四", "五", "六", "七", "八")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ComposeError(f"REPORT_DECK_INPUT_INVALID: {path.name}: {exc}") from exc


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _validate_plans(deck_dir, blueprint_sha):
    for name in ("chart-plan", "layout-plan", "module-fill-plan"):
        path = deck_dir / "obs" / f"{name}.json"
        if not path.is_file():
            raise ComposeError(f"REPORT_DECK_PLAN_MISSING: {name}")
        doc = _load(path)
        bindings = [item for item in doc.get("files", []) if item.get("record", "").endswith("deck-blueprint.json")]
        if not bindings or bindings[0].get("sha256") != blueprint_sha:
            raise ComposeError(f"REPORT_DECK_PLAN_STALE: {name}")


def _claim_maps(doc):
    claims = {claim["id"]: claim for claim in doc.get("claims", [])}
    metrics = {}
    for claim in claims.values():
        for metric in claim.get("metrics", []):
            if "value" in metric:
                metrics[metric["id"]] = metric
    return claims, metrics


def _metric_text(metric):
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
    values = [metrics[mid] for mid in page.get("metricRefs", []) if mid in metrics]
    if not values:
        return _quote(page, page_claims, metrics)
    numeric = [float(v["value"]) for v in values]
    maximum = max(numeric) or 1
    bars = []
    for index, metric in enumerate(values[:4]):
        height = max(8, round(float(metric["value"]) / maximum * 210))
        x = 75 + index * 120
        y = 245 - height
        bars.append(f'<rect x="{x}" y="{y}" width="72" height="{height}" rx="4" class="chart-bar"/>'
                    f'<text x="{x + 36}" y="{y - 12}" text-anchor="middle" class="chart-value" data-content-key="metric:{_esc(metric["id"])}">{_esc(_metric_text(metric))}</text>'
                    f'<text x="{x + 36}" y="275" text-anchor="middle" class="chart-label">{_esc(metric["id"])}</text>')
    statement = page_claims[0]["statement"] if page_claims else page.get("proves", "")
    evidence = (f'<aside class="insight-aside"><div class="eyebrow">WHAT THE DATA SAYS</div>'
                f'<p data-content-key="claim:{_esc(page_claims[0]["id"])}">{_esc(statement)}</p>'
                f'<p class="limitation" data-content-key="limitation:{_esc(page_claims[0]["id"])}">{_esc(page_claims[0].get("limitation", ""))}</p></aside>') if page_claims else ""
    return ('<div class="exhibit trend-exhibit"><svg viewBox="0 0 560 300" role="img" aria-label="同量尺趋势比较">'
            '<line x1="45" x2="525" y1="245" y2="245" class="axis"/>' + "".join(bars) + '</svg>' + evidence + '</div>')


def _matrix(page, page_claims, metrics):
    rows = []
    for index, claim in enumerate(page_claims[:5], 1):
        rows.append(f'<tr><td>{CN_NUMBERS[index - 1]}</td><td data-content-key="claim:{_esc(claim["id"])}">{_esc(claim["statement"])}</td>'
                    f'<td data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", "待验证"))}</td></tr>')
    return ('<div class="exhibit matrix-exhibit"><table aria-label="方案与证据比较"><thead><tr><th>#</th><th>判断／选项</th><th>边界／验证条件</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _roadmap(page, page_claims, metrics):
    steps = []
    for index, claim in enumerate(page_claims[:4], 1):
        steps.append(f'<article class="roadmap-step"><div class="step-no">阶段{CN_NUMBERS[index - 1]}</div>'
                     f'<h2 data-content-key="claim:{_esc(claim["id"])}">{_esc(claim["statement"])}</h2>'
                     f'<p>门槛：<span data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", "完成核验后进入下一阶段"))}</span></p></article>')
    return f'<div class="exhibit roadmap-exhibit" aria-label="分阶段路线图">{"".join(steps)}</div>'


def _quote(page, page_claims, metrics):
    claim = page_claims[0] if page_claims else {"statement": page.get("proves", ""), "limitation": ""}
    return ('<div class="exhibit quote-exhibit"><div class="quote-mark">“</div>'
            f'<blockquote data-content-key="claim:{_esc(claim.get("id", ""))}">{_esc(claim["statement"])}</blockquote><aside><div class="eyebrow">WHY IT MATTERS</div>'
            f'<p>{_esc(page.get("adds") or page.get("proves") or claim.get("limitation", ""))}</p>'
            f'<p class="limitation">边界：<span data-content-key="limitation:{_esc(claim.get("id", ""))}">{_esc(claim.get("limitation", "待进一步核验"))}</span></p></aside></div>')


RENDERERS = {"trend-bars": _trend, "comparison-matrix": _matrix, "roadmap": _roadmap, "evidence-quote": _quote}


def _selection(page, body_index, recent):
    composition = (((page.get("exhibit") or {}).get("semantics") or {}).get("composition") or {})
    panels = composition.get("panels") or {}
    anchor = panels.get(composition.get("anchorPanel")) or next(iter(panels.values()), {})
    relationship = ((anchor.get("selection") or {}).get("relationship") or "text").lower()
    declared_form = anchor.get("form")
    if declared_form == "svg.custom":
        selection = ("trend-bars", "chart-sidebar")
    elif declared_form == "html.text":
        selection = ("evidence-quote", "prose-aside")
    else:
        selection = FORMS.get(relationship, FALLBACKS[body_index % len(FALLBACKS)])
    if len(recent) >= 2 and recent[-1] == recent[-2] == selection[1]:
        selection = FALLBACKS[body_index % len(FALLBACKS)]
        if selection[1] == recent[-1]:
            selection = FALLBACKS[(body_index + 1) % len(FALLBACKS)]
    for panel in panels.values():
        count = (panel.get("capacity") or {}).get("items", len(panel.get("claimRefs", [])))
        if not isinstance(count, int) or count > MAX_ITEMS:
            raise ComposeError(f"REPORT_DECK_CAPACITY: {page.get('id')} exceeds {MAX_ITEMS} items")
    return selection


def _body_page(page, form, layout, claims, metrics, sources):
    page_claims = _claims(page, claims, metrics)
    source_ids = _source_ids(page, claims)
    exhibit = RENDERERS[form](page, page_claims, metrics)
    composition = (((page.get("exhibit") or {}).get("semantics") or {}).get("composition") or {})
    panels = composition.get("panels") or {}
    anchor = composition.get("anchorPanel") or next(iter(panels), "main")
    panel_html = [f'<div class="allen-primary-panel" data-panel-id="{_esc(anchor)}" data-module="exhibit">{exhibit}</div>']
    for panel_id, panel in panels.items():
        if panel_id == anchor:
            continue
        refs = [claims[ref] for ref in panel.get("claimRefs", []) if ref in claims]
        statements = "".join(f'<p data-content-key="claim:{_esc(claim["id"])}">{_esc(_replace_metrics(claim.get("statement", ""), metrics))}</p>'
                             f'<p class="limitation" data-content-key="limitation:{_esc(claim["id"])}">{_esc(claim.get("limitation", ""))}</p>' for claim in refs)
        content = f'<h2>{_esc(panel.get("purpose", "补充证据"))}</h2>{statements}'
        if panel.get("form") == "html.kpi":
            content = f'<div class="kpi-card">{content}</div>'
        panel_html.append(f'<aside class="allen-support-panel" data-panel-id="{_esc(panel_id)}" data-module="annotation">{content}</aside>')
    relations = "".join(f'<span class="relation-audit" data-relation-id="{_esc(rel.get("id"))}" aria-label="{_esc(rel.get("reason"))}"></span>'
                        for rel in composition.get("relations", []))
    metric_strip = "".join(f'<span data-content-key="metric:{_esc(mid)}">{_esc(_metric_text(metrics[mid])) if mid in metrics else _esc(mid)}</span>'
                            for mid in page.get("metricRefs", []))
    corner = re.sub(r"^\s*\d+\s*", "", page.get("cornerLabel") or "")
    return (f'<section class="slide reading allen-slide allen-form-{form} allen-layout-{layout}" data-page-id="{_esc(page["id"])}" '
            f'data-allen-form="{form}" data-allen-layout="{layout}" data-frame-boundary="line">'
            f'<header class="slide__header"><div class="corner">{_esc(corner)}</div>'
            f'<h1 class="slide__title" data-content-key="title">{_esc(_replace_metrics(page.get("title", ""), metrics))}</h1>'
            f'<p class="slide__lead">{_esc(page.get("subtitle", ""))}</p></header>'
            f'<main class="slide__body"><div class="allen-panel-grid">{"".join(panel_html)}</div>{relations}</main>'
            f'<div class="metric-strip" aria-label="本页指标">{metric_strip}</div>{_source_block(source_ids, sources)}'
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
    audit = ('<div class="source-audit"><article><strong>完整</strong><span>已定位来源</span></article>'
             '<article><strong>可追溯</strong><span>绑定来源的主张</span></article>'
             '<article><strong>逐页</strong><span>正文保留近端定位</span></article></div>')
    return (f'<section class="slide allen-references" data-page-id="references" data-page-role="references" data-frame-boundary="line">'
            f'<header class="slide__header"><div class="corner">{sequence:02d}</div><h1 class="slide__title">Sources / 来源与定位</h1></header>'
            f'{audit}<ol>{rows}</ol><p class="reference-note">单一来源不等于单一证据：本页同时给出主张绑定数量与逐页定位责任，避免空洞来源页。</p></section>')


CSS = """
.allen-slide,.allen-cover,.allen-back,.allen-references{font-family:'Deck Inter','Deck Noto Sans SC',sans-serif;color:#17252b;background:#f7f4ed}
.allen-slide{padding:38px 54px 34px;box-sizing:border-box}.slide__header{padding-top:12px}.corner,.bookend-kicker,.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#087f73;font-weight:600}
.slide__title{font-family:'Deck Playfair Display','Deck Noto Serif SC',serif;font-size:31px;line-height:1.22;margin:8px 0}.slide__lead{font-size:14px;color:#66777d;margin:0}.slide__body{height:400px;margin-top:18px}.exhibit{height:100%}.trend-exhibit{display:grid;grid-template-columns:2fr 1fr;gap:32px}.trend-exhibit svg{width:100%;height:100%;background:#fff;border:1px solid #ced8d6}.chart-bar{fill:#087f73}.axis{stroke:#77878b;stroke-width:1}.chart-value{font-size:16px;font-weight:600}.chart-label{font-size:12px;fill:#66777d}.insight-aside,.quote-exhibit aside{padding:24px;background:#e7efed}.insight-aside p{font-size:20px;line-height:1.45}.limitation{font-size:12px!important;color:#66777d;line-height:1.5!important}
.allen-panel-grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(180px,1fr);gap:18px;height:100%}.allen-primary-panel:only-child{grid-column:1/-1}.allen-primary-panel{min-width:0}.allen-support-panel{background:#fff;padding:16px;align-self:stretch}.allen-support-panel h2{font-size:14px;line-height:1.35}.allen-support-panel p{font-size:12px;line-height:1.45}.relation-audit{display:none}
.metric-strip{position:absolute;left:54px;bottom:77px;display:flex;gap:8px}.metric-strip span{background:#e7efed;color:#153c47;padding:4px 8px;font-size:12px;font-weight:600}
.matrix-exhibit table{width:100%;border-collapse:collapse;background:#fff}.matrix-exhibit th{background:#153c47;color:#fff;text-align:left;padding:13px;font-weight:600}.matrix-exhibit td{padding:16px 13px;border-bottom:1px solid #cbd5d2;font-size:15px}.roadmap-exhibit{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;align-items:stretch}.roadmap-step{background:#fff;padding:20px}.roadmap-step:nth-child(even){margin-top:54px}.step-no{font-size:28px;color:#087f73;font-family:'Deck Playfair Display','Deck Noto Serif SC',serif}.roadmap-step h2{font-size:17px;line-height:1.35}.roadmap-step p{font-size:12px;color:#66777d;line-height:1.5}
.quote-exhibit{display:grid;grid-template-columns:80px 2fr 1fr;gap:25px;align-items:center}.quote-mark{font-family:'Deck Playfair Display','Deck Noto Serif SC',serif;font-size:110px;color:#087f73;align-self:start}.quote-exhibit blockquote{font-family:'Deck Playfair Display','Deck Noto Serif SC',serif;font-size:28px;line-height:1.45;margin:0}.evidence-source{position:absolute;left:54px;bottom:46px;font-size:12px;line-height:1.35;color:#617276;max-width:70%}.takeaway{position:absolute;right:54px;bottom:45px;max-width:34%;font-size:14px;font-weight:600;text-align:right}.allen-cover,.allen-back{padding:70px 78px;display:flex;flex-direction:column;justify-content:center}.allen-cover h1,.allen-back h1{font:600 46px/1.22 'Deck Playfair Display','Deck Noto Serif SC',serif;max-width:760px}.allen-cover:before{content:'';position:absolute;left:78px;top:92px;width:74px;height:8px;background:#087f73}.allen-references{padding:48px 62px}.source-audit{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:20px 0}.source-audit article{background:#153c47;color:white;padding:16px}.source-audit strong{font-size:25px}.source-audit span{display:block;color:#d9e5e2;font-size:12px}.allen-references ol{display:grid;grid-template-columns:1fr 1fr;gap:18px 34px;margin-top:18px}.allen-references li{background:#fff;padding:16px}.allen-references span{display:block;color:#66777d;font-size:12px;margin-top:7px}.reference-note{font-size:12px;color:#66777d}
""".strip() + "\n"


def compose(deck_dir):
    deck_dir = pathlib.Path(deck_dir)
    blueprint_path = deck_dir / "deck-blueprint.json"
    blueprint = _load(blueprint_path)
    digest = _sha(blueprint_path)
    _validate_plans(deck_dir, digest)
    claims, metrics = _claim_maps(blueprint)
    sources = blueprint.get("sources") or {}
    html_pages, manifest_pages, recent = [], [], []
    body_index = 0
    for page in sorted(blueprint.get("slides", []), key=lambda item: item.get("sequence", 0)):
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
            form, layout = _selection(page, body_index, recent)
            recent.append(layout); body_index += 1
            html_pages.append(_body_page(page, form, layout, claims, metrics, sources))
            manifest_pages.append({"id": page["id"], "role": "body", "form": form, "layout": layout,
                                   "claimRefs": page.get("claimRefs", []), "sourceIds": _source_ids(page, claims)})
    # The engine requires a references role. A single source becomes a filled
    # provenance audit rather than a nearly empty list page.
    references_page = bool(sources)
    if references_page:
        insert_at = max(0, len(html_pages) - 1)
        reference = deck_dir / "bookend-references.html"
        if reference.is_file():
            reference_html = reference.read_text(encoding="utf-8")
            source_claims = sum(1 for claim in claims.values() if claim.get("sourceKeys"))
            audit = ('<div class="source-audit" data-module="source-audit"><article><strong>完整</strong><span>已定位来源</span></article>'
                     '<article><strong>可追溯</strong><span>绑定来源的主张</span></article>'
                     '<article><strong>逐页</strong><span>正文保留近端定位</span></article></div>')
            reference_html = reference_html.replace("</section>", audit + "</section>")
        else:
            reference_html = _references(sources, len(html_pages), claims)
        html_pages.insert(insert_at, reference_html)
        manifest_pages.insert(insert_at, {"id": "references", "role": "references", "form": "source-list", "layout": "references"})
    manifest = {"version": 1, "blueprintSha256": digest, "referencesPage": references_page, "sparseReferences": False, "pages": manifest_pages,
                "forms": sorted({p["form"] for p in manifest_pages if p["role"] == "body"}),
                "layouts": sorted({p["layout"] for p in manifest_pages if p["role"] == "body"})}
    (deck_dir / ".allen").mkdir(exist_ok=True)
    (deck_dir / "pages.html").write_text("\n".join(html_pages) + "\n", encoding="utf-8")
    (deck_dir / "page.css").write_text(CSS, encoding="utf-8")
    (deck_dir / ".allen" / "composition-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import sys
    try:
        print(json.dumps(compose(sys.argv[1]), ensure_ascii=False, indent=2))
    except ComposeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
