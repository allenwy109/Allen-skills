#!/usr/bin/env python3
"""尽调报告内容 → 故事线输入（设计 §5.2 "报告怎么出"第 2 步）。机械转换，不改写结论。

输入：<任务>/03d_diligence/report-content.json（先跑 diligence check-content 通过）、统一证据账。
输出（<任务>/07_storyline/）：
  00_story-brief.md   取自 project 表的目的、深度、基准日、保密
  01_materials_index.md  取自 sources
  03_storyline.md     只写结构树（按内容的章节和 11 个解释主题），按目的选故事线模式
  04_manuscript.md、04_manuscript_clean.md  母版（每个内容块前有 <!-- block:ID --> 标记、带卡片引用）和清洁版
  block_map.json      每个内容块的 ID、章节、类型、主题（拆页后复核用）
  sidecar.json        主线确认点（由内容契约决定，记为 auto_adopted）
卡片：为内容块引用的每条主张生成卡片（同一主张只建一张）。只引用了证据、还没有主张的内容块，先补登主张
（kind 按证据属性定），再生成卡片。value_tier 按主张的 materiality：critical、major → A；minor → B。
"含义"取主张的 inference；为空时取该主题解释正文的首句。

内容块 ID 的规则（<章节 ID>-<序号>）必须与 core-diligence 的 dcontent.block_ids 一致（有测试保证）。
用法：python3 tools/bridge/diligence_to_manuscript.py <任务文件夹>
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.lib import schema_check  # noqa: E402
from tools.lib.ledger import Ledger, LedgerError  # noqa: E402

ENUMS = schema_check.load("ledger.schema.json")["enums"]
KIND_BY_ATTRIBUTE = {"actual": "fact", "forecast": "forecast", "estimate": "estimate", "opinion": "third_party_view", "not_applicable": "fact"}
CARD_TYPE = {"fact": "fact", "data": "data", "estimate": "insight", "forecast": "insight", "judgment": "insight", "assumption": "insight",
             "recommendation": "recommendation", "third_party_view": "opinion"}
NEEDS_ASSUMPTIONS = {"estimate", "forecast", "judgment"}
MODE = {"company_research": ("公司研究", "风险与未知")}
TOPIC_LABEL = {"identity": "公司身份", "history_team": "沿革与团队", "offering": "产品与服务", "customers_markets": "客户与市场",
               "transaction_flow": "交易流程", "operating_model": "经营分工", "revenue_costs": "收入与成本", "differentiation": "差异化",
               "financial_performance": "财务表现", "marketing": "营销与获客", "competition": "竞争与替代"}
STATUS_LABEL = {"supported": "有依据", "partial": "部分有依据", "unknown": "未知"}
SPECIAL = ("尽调结论", "风险与红旗")


class BridgeError(Exception):
    pass


def block_ids(content):
    return [(f"{s['id']}-{i}", s, b) for s in content.get("sections") or [] for i, b in enumerate(s.get("blocks") or [], 1)]


def clean_text(master):
    """与 storyline clean 相同：只删卡片引用〔…〕。"""
    return re.sub(r"[ \t]*〔[^〔〕]*〕", "", master)


def label(enum, v):
    return ENUMS.get(enum, {}).get("labels", {}).get(v, v or "—")


def block_evidence(b):
    """内容块引用的全部证据（按出现顺序去重）。"""
    ids = []
    def take(x):
        for i in x or []:
            if i not in ids:
                ids.append(i)
    take(b.get("evidence_ids"))
    for k in ("items", "profiles", "nodes", "edges"):
        for it in b.get(k) or []:
            if isinstance(it, dict):
                take(it.get("evidence_ids"))
    for r in b.get("rows") or []:
        if isinstance(r, dict):
            for cell in r.get("cells") or []:
                take(cell.get("evidence_ids"))
    for p in b.get("points") or []:
        take(p.get("evidence_ids"))
    for text in [b.get("text")] + [x for x in (b.get("items") or []) if isinstance(x, str)]:
        take(re.findall(r"\[(ev-\d{4,})\]", text or ""))
    return ids


def _decimals(v):
    r = repr(v)
    return len(r.split(".")[1]) if "." in r and not r.endswith(".0") else 0


def block_metrics(led, b):
    """指标卡和图表里的数值机械登记为证据账指标（缺失登记为 missing，不填 0），返回指标 ID 列表。"""
    out = []
    if b.get("type") == "metrics":
        items = [(m["label"], m["value"], m["unit"]) for m in b["items"]]
    elif b.get("type") == "chart" and b.get("chart_type") not in ("range", "stacked_bar"):
        items = [(pt["label"], pt.get("value"), b["unit"]) for pt in b["points"]]
    else:
        return out
    for name, value, unit in items:
        if value is None:
            row = {"label": name, "unit": unit, "decimals": 0, "status": "missing", "status_reason": "内容里标为未披露"}
        else:
            row = {"label": name, "unit": unit, "decimals": _decimals(value), "status": "present", "value": value}
        out.append(led.add("metrics", row))
    return out


def block_statement(b):
    t = b.get("type")
    if t in ("explanation", "text", "callout"):
        return re.sub(r"\[ev-\d{4,}\]", "", b.get("text") or "").strip()
    if t == "metrics":
        return "；".join(f"{m['label']} {'未披露' if m['value'] is None else m['value']} {m['unit']}（{m['period']}）" for m in b["items"])
    if t == "people":
        return "；".join(f"{x['name']}：{x['role']}，{x['contribution']}" for x in b["profiles"])
    if t in ("process", "timeline"):
        return f"{b['title']}：" + "；".join(it["title"] for it in b["items"])
    if t == "matrix":
        return f"{b['title']}：" + "、".join(r["label"] for r in b["rows"])
    return b.get("title") or ""


def convert(task):
    task = pathlib.Path(task)
    content = json.loads((task / "03d_diligence" / "report-content.json").read_text(encoding="utf-8"))
    if content.get("version") != "1.2" or not content.get("sections"):
        raise BridgeError("report-content.json 不是 1.2 版或没有章节：先跑 diligence check-content")
    led = Ledger(task)
    p = (led.read("project") or [{}])[0]
    evidence = {e["id"]: e for e in led.read("evidence")}
    sources = {s["id"]: s for s in led.read("sources")}
    claims = {c["id"]: c for c in led.read("claims")}
    links = led.read("claim_evidence")
    cards_by_claim = {c["claim_id"]: c["id"] for c in led.read("cards") if c.get("claim_id")}
    topic_text = {b["topic"]: b["text"] for _, _, b in block_ids(content) if b.get("type") == "explanation"}
    added_claims, added_cards, cite_for = [], [], {}
    for bid, sec, b in block_ids(content):
        ev_ids = [e for e in block_evidence(b) if e in evidence]
        if not ev_ids:
            continue
        claim_ids = sorted({l["claim_id"] for l in links if l["evidence_id"] in ev_ids and l["relation"] == "supports"})
        if not claim_ids:
            first = evidence[ev_ids[0]]
            kind = KIND_BY_ATTRIBUTE.get(first.get("attribute"), "fact")
            if kind == "fact" and first.get("numeric"):
                kind = "data"
            groups = {sources.get(evidence[e]["source_id"], {}).get("origin_group") or evidence[e]["source_id"] for e in ev_ids}
            major = b.get("type") in ("explanation", "metrics", "chart")
            statement = block_statement(b) or first.get("claim_text") or first["excerpt"]
            period = f"{first['period_start']}–{first['period_end']}" if first.get("period_start") and first.get("period_end") else "截至基准日"
            weak = {sources.get(evidence[e]["source_id"], {}).get("grade") for e in ev_ids} <= {"C", "D"}
            row = {"kind": kind, "statement": statement, "scope": first.get("scope") or "not_applicable", "period": period,
                   "population": p.get("target_name") or "目标公司", "unit": first.get("unit") or "不适用：定性", "denominator": "不适用：定性或单值",
                   "calculation": "不适用：原文表述", "inference": "只陈述所引证据的内容，不作额外推论",
                   "limitation": "只有公司自己的材料，未经独立核实" if weak else "以所引原始文件的原文为准",
                   "verification": "verified" if len(groups) >= 2 else "single_source", "confidence": "medium",
                   "confidence_reason": f"转换补登：依据证据 {'、'.join(ev_ids)}", "affects_conclusion": major,
                   "materiality": "major" if major else "minor", **({"entity_id": first["entity_id"]} if first.get("entity_id") else {})}
            if kind in NEEDS_ASSUMPTIONS:
                row["assumptions"] = f"沿用所引证据（{'、'.join(ev_ids)}）的原文口径与假设"
            metric_refs = block_metrics(led, b)
            if metric_refs:
                row["metric_refs"] = metric_refs
            row = {k: v for k, v in row.items() if v != ""}
            cid = led.add("claims", row)
            for e in ev_ids:
                lid = led.add("claim_evidence", {"claim_id": cid, "evidence_id": e, "relation": "supports", "applicable_scope": "见所引证据"})
                links.append({"id": lid, "claim_id": cid, "evidence_id": e, "relation": "supports"})
            claims[cid] = {"id": cid, **row}
            claim_ids, added_claims = [cid], added_claims + [cid]
        refs = []
        for cid in claim_ids:
            c = claims[cid]
            if cid not in cards_by_claim:
                topic = b.get("topic")
                meaning = c.get("inference") or (re.split(r"(?<=[。！？])", topic_text.get(topic, ""))[0].strip() if topic else "") \
                    or "说明该事项对理解公司的作用（转换生成）"
                c_ev = [l["evidence_id"] for l in links if l["claim_id"] == cid and l["evidence_id"] in evidence] or ev_ids
                card = {"type": "risk" if "risk" in sec["id"] else CARD_TYPE.get(c["kind"], "fact"), "content": c["statement"],
                        "meaning": re.sub(r"\[ev-\d{4,}\]", "", meaning),
                        "value_tier": "A" if c.get("materiality") in ("critical", "major") else "B", "topic": TOPIC_LABEL.get(b.get("topic"), sec["title"]),
                        "claim_id": cid, "source_refs": [{"source_id": evidence[e]["source_id"], "locator": evidence[e]["locator"]} for e in c_ev]}
                cards_by_claim[cid] = led.add("cards", card)
                added_cards.append(cards_by_claim[cid])
            kid = cards_by_claim[cid]
            loc = next(({"s": evidence[l["evidence_id"]]["source_id"], "l": evidence[l["evidence_id"]]["locator"]} for l in links
                        if l["claim_id"] == cid and l["evidence_id"] in evidence), None)
            refs.append(f"{kid}｜{loc['s']} {loc['l']}" if loc else kid)
        cite_for[bid] = "〔" + "、".join(refs) + "〕"
    story = task / "07_storyline"
    story.mkdir(parents=True, exist_ok=True)
    write_files(task, story, content, p, sources, led, cite_for)
    return {"claims_added": added_claims, "cards_added": added_cards, "blocks": len(block_ids(content))}


def with_cite(text, cite):
    """卡片引用放在句末标点之前（和故事线的标注规范一致）。"""
    text = text.rstrip()
    if cite and text and text[-1] in "。！？":
        return text[:-1] + cite + text[-1]
    return text + (cite or "")


def render_block(b, cite, names=None):
    t = b["type"]
    c = cite or ""
    names = names or {}
    def strip(x):
        return re.sub(r"\[ev-\d{4,}\]", "", x or "").strip()
    if t == "explanation":
        lines = [f"### {b['title']}", "", with_cite(strip(b["text"]), c)]
        if b.get("limitations"):
            lines += ["", f"限制：{strip(b['limitations'])}"]
        return lines
    if t == "text":
        return [with_cite(strip(b["text"]), c)]
    if t == "callout":
        return [f"> **{b['title']}**：{strip(b['text'])}{c}"]
    if t == "bullets":
        return [f"- {strip(x)}" for x in b["items"]] + ([f"（来源：{c}）"] if c else [])
    if t == "table":
        return [f"**{b['title']}**", "", "| " + " | ".join(b["columns"]) + " |", "|" + "---|" * len(b["columns"])] + \
            ["| " + " | ".join(map(str, r)) + " |" for r in b["rows"]] + ["", f"{strip(b['note'])}{c}"]
    if t == "metrics":
        return [f"- {m['label']}：{'未披露' if m['value'] is None else m['value']} {m['unit']}（{m['period']}，{m['kind']}）" for m in b["items"]] + \
            ([f"（来源：{c}）"] if c else [])
    if t == "chart":
        rows = []
        for pt in b["points"]:
            if b["chart_type"] == "range":
                v = "未披露" if pt.get("low") is None else f"{pt['low']}–{pt['high']}"
            elif b["chart_type"] == "stacked_bar":
                v = "；".join(f"{x['label']} {x['value']}" for x in pt.get("parts") or [])
            else:
                v = "未披露" if pt.get("value") is None else pt["value"]
            rows.append(f"| {pt['label']} | {v} | {pt.get('kind', b['kind'])} |")
        return [f"**{b['title']}**（单位：{b['unit']}；期间：{b['period']}；主体：{names.get(b['entity_id'], b['entity_id'])}；图型：{b['chart_type']}）", "",
                "| 项目 | 数值 | 属性 |", "|---|---|---|", *rows, "", f"{strip(b['note'])}{c}"]
    if t == "timeline":
        return [f"**{b['title']}**", ""] + [f"- {it['date']}（{'已完成' if it['status'] == 'completed' else '计划'}）{it['title']}：{strip(it['text'])}"
                                            for it in b["items"]] + ([f"（来源：{c}）"] if c else [])
    if t == "process":
        seq = b.get("ordering", "sequence") == "sequence"
        return [f"**{b['title']}**（{'按顺序' if seq else '排列不表示已核实的顺序'}）", ""] + \
            [(f"{i}. " if seq else "- ") + f"{it['title']}：{strip(it['text'])}（{it.get('basis', 'evidence')}）" for i, it in enumerate(b["items"], 1)] + \
            ([f"（来源：{c}）"] if c else [])
    if t == "people":
        return [f"**{b['title']}**", ""] + [f"- {x['name']}（{x['role']}，{x['period']}）：{strip(x['background'])}；贡献：{strip(x['contribution'])}；限制：{strip(x['limitations'])}"
                                            for x in b["profiles"]] + ([f"（来源：{c}）"] if c else [])
    if t == "image":
        return [f"![{b['alt']}]({b['path']})", "", f"{strip(b['caption'])}（来源：{b['source_url'] or '本地材料'}，取得于 {b['captured_at']}；{strip(b['usage_note'])}）{c}"]
    if t == "matrix":
        return [f"**{b['title']}**", "", "| 项目 | " + " | ".join(b["columns"]) + " |", "|" + "---|" * (len(b["columns"]) + 1)] + \
            ["| " + r["label"] + " | " + " | ".join(f"{cell['text']}（{cell.get('basis', 'evidence')}）" for cell in r["cells"]) + " |" for r in b["rows"]] + \
            ["", f"{strip(b['note'])}{c}"]
    if t == "diagram":
        return [f"**{b['title']}**（{b['purpose']}；主体：{names.get(b['entity_id'], b['entity_id'])}；布局不表示层级或顺序）", ""] + \
            [f"- 节点 {n['id']}：{n['label']}（{n.get('basis', 'evidence')}）" for n in b["nodes"]] + \
            [f"- {e['source']} → {e['target']}（{e['flow']}）：{e['label']}" for e in b["edges"]] + ["", f"{strip(b['note'])}{c}"]
    return []


def write_files(task, story, content, p, sources, led, cite_for):
    purpose = p.get("purpose") or "company_research"
    mode, risk_title = MODE.get(purpose, SPECIAL)
    used = {i for _, _, b in block_ids(content) for i in block_evidence(b)}
    used_sources = {e["source_id"] for e in led.read("evidence") if e["id"] in used}
    (story / "00_story-brief.md").write_text(f"""# 简报（由 diligence_to_manuscript 生成）

| 项 | 内容 |
|---|---|
| 受众 | {p.get('focus') or '需要了解这家公司的决策者（假设：用户未另行说明）'} |
| 目的 | {label('purpose', purpose)}{('；' + p['focus']) if p.get('focus') else ''} |
| 场景 | 会前阅读；不设页数上限（假设：用户未提） |
| 语言风格 | {'中文' if content.get('language') == 'zh-CN' else 'English'}，书面，结论先行 |
| 保密 | {p.get('confidentiality') or '内部使用（假设）'} |
| 外部知识 | 只用证据账里登记的资料 |
| 验收标准 | 读者只读正文就能回答 11 个主题问题，并看到推进条件和限制；基准日 {p.get('as_of_date') or '—'} |
""", encoding="utf-8")
    rows = ["# 材料索引（由 diligence_to_manuscript 生成）", "", "| 来源 ID | 名称 | 类型 | 时间 | 作者或来源 | 可信度 | 相关度 | 体量 | 处理状态 |", "|---|---|---|---|---|---|---|---|---|"]
    status = {"full": "读完", "partial": "读至部分（见快照的访问说明）", "summary": "仅摘要", "snippet_only": "仅搜索摘要", "metadata_only": "仅元数据（无法读取）",
              "blocked": "访问受阻", "unreadable": "无法读取"}
    for s in sources.values():
        rows.append(f"| {s['id']} | {s['title']} | {label('source_type', s.get('source_type'))} | {s.get('published') or '未知'} | "
                    f"{s.get('author_org') or s.get('publisher') or '—'} | {s.get('grade') or '—'} | {'高' if s['id'] in used_sources else '中'} | — | "
                    f"{status.get(s.get('access'), s.get('access'))} |")
    (story / "01_materials_index.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    cards = {c["claim_id"]: c["id"] for c in led.read("cards") if c.get("claim_id")}
    tree, stress = [], []
    for s in content["sections"]:
        tree.append(f"- {s['title']}")
        for i, b in enumerate(s["blocks"], 1):
            if b.get("type") == "explanation":
                ids = re.findall(r"card-\d{4,}", cite_for.get(f"{s['id']}-{i}", ""))
                tree.append(f"  - {TOPIC_LABEL[b['topic']]}：{b['title']}（{STATUS_LABEL[b['status']]}{'；' + '、'.join(ids) if ids else ''}）")
    for c in led.read("claims"):
        if c.get("counterevidence") or c.get("unresolved"):
            stress.append(f"- {c['id']}：反证 {c.get('counterevidence') or '—'}；未决 {c.get('unresolved') or '—'}")
    for r in led.read("risks"):
        stress.append(f"- 风险 {r['id']}：{r['description']}（替代解释：{r['alternative_explanations']}）")
    (story / "03_storyline.md").write_text("\n".join([
        "# 故事线（由 diligence_to_manuscript 生成，只写结构树，不改写结论）", "", f"故事线模式：{mode}", "",
        "## 中心论点", "", re.split(r"(?<=[。！？])", content["summary"])[0], "", "## 结构树", "", *tree, "",
        "## 压力测试", "", *(stress or ["- 证据、反例、代价三类质疑见各主题的限制和风险章"]), ""]), encoding="utf-8")
    lines = [f"# {content['title']}", "", f"> {content['subtitle']}", "", "## 执行摘要", "", content["summary"], ""]
    titles = [s["title"] for s in content["sections"]]
    names = {"industry": "行业", **{e["id"]: e["legal_name"] for e in led.read("entities")}}
    for s in content["sections"]:
        lines += [f"## {s['title']}", ""]
        if s.get("summary"):
            lines += [s["summary"], ""]
        for i, b in enumerate(s["blocks"], 1):
            bid = f"{s['id']}-{i}"
            lines += [f"<!-- block:{bid} -->"] + render_block(b, cite_for.get(bid), names) + [""]
    gaps = [g for g in led.read("gaps") if g["status"] not in ("resolved", "unavailable")]
    risks = led.read("risks")
    if not any(risk_title in t for t in titles):
        lines += [f"## {risk_title}", ""] + ([f"- {r['description']}（{label('risk_status', r['status'])}，{label('risk_severity', r['severity'])}）：影响 {r['impact']}；缓释 {r['mitigation']}"
                                              for r in risks] + [f"- 未知：{g['description']}" for g in gaps] or ["- 无已登记的重大风险"]) + [""]
    if not any("补齐路径" in t for t in titles):
        lines += ["## 补齐路径", ""] + ([f"- {g['description']}：{g['acquisition_path']}（{g['priority']}，负责：{g['owner_role']}）" for g in gaps]
                                        or ["- 无开放缺口"]) + [""]
    if not any("方法与局限" in t for t in titles):
        lines += ["## 方法与局限", "", content["scope_note"], ""]
    master = "\n".join(lines)
    (story / "04_manuscript.md").write_text(master, encoding="utf-8")
    (story / "04_manuscript_clean.md").write_text(clean_text(master), encoding="utf-8")
    (story / "block_map.json").write_text(json.dumps([{"block_id": bid, "section_id": s["id"], "section_title": s["title"], "type": b["type"],
                                                       **({"topic": b["topic"]} if b.get("topic") else {})} for bid, s, b in block_ids(content)],
                                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    side_path = story / "sidecar.json"
    side = json.loads(side_path.read_text(encoding="utf-8")) if side_path.is_file() else {"speaker_notes": [], "backup_pages": [], "confirmation_points": []}
    if not any(c["stage"] == "storyline" for c in side["confirmation_points"]):
        side["confirmation_points"].append({"stage": "storyline", "status": "auto_adopted", "note": "尽调报告的主线由报告内容契约决定（转换生成）"})
    side_path.write_text(json.dumps(side, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for base in (ROOT, ROOT.parent):
        script = base / "core-storyline" / "scripts" / "storyline.py"
        if script.is_file():
            subprocess.run([sys.executable, str(script), "cards", str(task)], capture_output=True, text=True)
            break


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    if len(a) != 1:
        print("用法：diligence_to_manuscript.py <任务文件夹>", file=sys.stderr)
        return 2
    try:
        r = convert(a[0])
    except (BridgeError, LedgerError, OSError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False))
    print("下一步：core-storyline 按「仅拆页」从阶段 5 开始（故事板、06_slides.md、slides.json 写 block_ids），然后 diligence check-content --after-split。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
