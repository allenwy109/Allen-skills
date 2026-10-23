#!/usr/bin/env python3
"""把 slides.json、sidecar.json 和证据账转成 report-forge 的蓝图（设计 §6.2 out-report；映射见 MAPPING.md）。

报告引擎的内容真源是蓝图（schemaVersion 3）：顶层 sources、claims（指标挂在主张下）、analysis，
以及逐页的 claimRefs、metricRefs、visual、density 和组合证据（exhibit.semantics.composition）。
本脚本只做机械搬运和转换前检查，不改写结论：
- 主张身份：fact、data、third_party_view → fact；estimate、judgment → estimate；其余同名。
- 核实状态：支持证据的来源全部是用户材料 → provided；否则 → source_checked；
  没有来源的建议、假设 → not_applicable；没有来源的事实类主张拦下。
- 不能以事实呈现的主张（设计 §6.2）：关键的未核实主张 → 假设，句尾加"（待确认）"（引擎会在句首加"假设："，
  所以不用设计里写的前缀，避免"假设：待确认："两层叠加）；被推翻的 → 假设，写成
  "曾认为……，已被推翻"，限制写反证；非关键的未核实主张、冲突未处理的主张拦下。
- 文字里的数字（主张的陈述、分母、计算、推论、限制，页面的标题和 proves）必须换成指标引用 {{metric:id}}，
  由引擎统一显示；找不到对应指标的数字拦下（4 位年份和编号除外，或用 allow 显式放行）。
  副标题和 adds 引擎不解析指标引用，所以不能写数字；讲者备注里的数字也要能追回证据账。
- 引擎 ready 校验没有覆盖、要到 compile 才报的项，这里提前拦下：自定义布局的 slot 名称、
  panel 的主张不属于本页、主展品不唯一。

用法：python3 tools/bridge/to_forge.py <任务文件夹> -o <deck-blueprint.json> [--allow 3]
输入：<任务>/07_storyline/slides.json、sidecar.json（可选）、03_evidence/ledger/。
退出码：0 成功；1 有不能转换的问题（逐条列出）；2 文件错误。
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.bridge.poster_numbers import ID_PATTERN, NUMBER  # noqa: E402
from tools.lib import metrics as M  # noqa: E402
from tools.lib import schema_check  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

FORGE_KIND = {"fact": "fact", "data": "fact", "third_party_view": "fact", "estimate": "estimate", "judgment": "estimate",
              "forecast": "forecast", "assumption": "assumption", "recommendation": "recommendation"}
FACTUAL = {"fact", "estimate", "forecast"}
CONTENT_ROLES = {"analysis", "decision", "action", "risk", "appendix"}
SLOTS = {"main", "left", "right", "top", "bottom", "aside", "full"}
CLAIM_TEXT = ("statement", "denominator", "calculation", "inference", "limitation")
YEAR = re.compile(r"(19|20|21)\d\d")


class BridgeError(Exception):
    def __init__(self, problems):
        super().__init__("；".join(problems))
        self.problems = problems


def _numbers(text):
    """返回 [(起点, 终点, 数字原文)]；编号和 4 位年份不算。"""
    clean = ID_PATTERN.sub(lambda m: " " * len(m.group(0)), text)
    out = []
    for m in NUMBER.finditer(clean):
        num = m.group(0).replace(",", "")
        if num.lstrip("-") and not YEAR.fullmatch(num):
            out.append((m.start(), m.end(), m.group(0)))
    return out


class _Pool:
    """进入蓝图的指标：显示值 → 指标 ID，用来把文字里的数字换成指标引用。"""

    def __init__(self, metrics, ids):
        self.metrics, self.by_display = metrics, {}
        for mid in ids:
            m = metrics[mid]
            shown = M.display(M.evaluate(metrics, mid), m["decimals"])
            self.by_display.setdefault(shown, []).append(mid)

    def tokenize(self, text, prefer, where, allow, problems, counter):
        """把 text 里的数字换成 {{metric:id}}；数字后紧跟的单位一并替换。"""
        if not text:
            return text
        out, last = [], 0
        for start, end, raw in _numbers(text):
            counter[0] += 1
            num = raw.replace(",", "")
            if num in allow:
                continue
            hits = self.by_display.get(num, [])
            choice = [h for h in hits if h in prefer] or hits
            if not choice:
                problems.append(f"{where}：数字 {raw} 不是任何进入报告的指标的显示值（改写成指标引用、补登指标，或用 --allow 放行）")
                continue
            if len(set(choice)) > 1:
                problems.append(f"{where}：数字 {raw} 同时等于 {'、'.join(sorted(set(choice)))} 的显示值，无法确定是哪一个")
                continue
            mid = choice[0]
            unit = self.metrics[mid]["unit"]
            tail = text[end:]
            stripped = tail.lstrip(" ")
            if unit and stripped.startswith(unit):
                end += len(tail) - len(stripped) + len(unit)
            out.append(text[last:start] + "{{metric:" + mid + "}}")
            last = end
        out.append(text[last:])
        return "".join(out)


def _scan_only(text, values, where, allow, problems, counter):
    """不能写指标引用的地方（副标题、adds、讲者备注）：数字必须等于某个指标的显示值。"""
    for _, _, raw in _numbers(text or ""):
        counter[0] += 1
        num = raw.replace(",", "")
        if num not in allow and num not in values:
            problems.append(f"{where}：数字 {raw} 追溯不到证据账")


def _source_entry(src, locators):
    url = src.get("final_url") or src.get("url") or ""
    if url.startswith(("http://", "https://")):
        where = url
    else:   # 本地文件地址对读者没有意义，只写类别
        where = "用户提供材料" if src.get("origin") == "user" else "本地存档材料"
    if locators:
        where += " · " + "、".join(locators)
    return {"label": src["title"], "locator": where}


def build(task, slides_doc, sidecar=None, allow=()):
    """返回 {"blueprint", "references", "notes", "trace"}；有问题时抛 BridgeError。"""
    problems = schema_check.check_document(schema_check.load("slides.schema.json"), slides_doc, "slides.json")
    if problems:
        raise BridgeError(problems)
    led = Ledger(task)
    metrics = {m["id"]: m for m in led.read("metrics")}
    claims = {c["id"]: c for c in led.read("claims")}
    by_metric = M.claims_by_metric(list(claims.values()))
    conflicts = led.read("conflicts")
    resolved = M.resolved_conflict_claims(conflicts)
    sources = {s["id"]: s for s in led.read("sources")}
    evidence = {e["id"]: e for e in led.read("evidence")}
    links = led.read("claim_evidence")
    allow = {a.replace(",", "") for a in allow}
    notes, counter = [], [0]
    deck, slides = slides_doc["deck"], slides_doc["slides"]

    for key in ("brief", "answer_claim_refs", "cover"):
        if not deck.get(key):
            problems.append(f"deck.{key} 缺失：报告引擎需要研究问题、核心答案主张和封面信息")
    if deck.get("cover") and not deck["cover"].get("date"):
        problems.append("deck.cover.date 缺失：封面和封底必须有报告日期")
    if deck.get("arc") == "other" and not deck.get("arc_reason"):
        problems.append("deck.arc 为 other 时要写 arc_reason")

    # 1. 用到哪些主张
    used = []
    for s in slides:
        if s["page_role"] in CONTENT_ROLES:
            problems.extend(_body_problems(s, f"第 {s['page']} 页"))
        refs = list(s.get("claim_refs") or [])
        for p in s.get("panels") or []:
            for cid in p["claim_refs"]:
                if cid not in refs:
                    problems.append(f"第 {s['page']} 页 panel {p['id']}：主张 {cid} 不在本页 claim_refs 里")
        used += refs
    used += deck.get("answer_claim_refs") or []
    used = list(dict.fromkeys(used))

    # 2. 主张：身份、核实状态、不能以事实呈现的改写
    forge_claims, metric_owner = [], {}
    for cid in used:
        c = claims.get(cid)
        if not c:
            problems.append(f"主张 {cid} 不在证据账里")
            continue
        src_ids = sorted({evidence[l["evidence_id"]]["source_id"] for l in links
                          if l["claim_id"] == cid and l["relation"] == "supports" and l["evidence_id"] in evidence})
        kind, verification, statement = FORGE_KIND[c["kind"]], None, c["statement"]
        limitation = c.get("limitation") or ""
        extra = []
        if M.presentable(c, resolved):
            if src_ids:
                verification = "provided" if all(sources[s]["origin"] == "user" for s in src_ids) else "source_checked"
            elif kind in FACTUAL:
                problems.append(f"主张 {cid}（{c['kind']}）没有支持证据的来源，不能以事实呈现")
                continue
            else:
                verification = "not_applicable"
            if c["verification"] == "single_source":
                extra.append("单一来源")
            if c["verification"] == "conflicting":
                reasons = [x.get("accepted_reason") for x in conflicts if cid in (x.get("claim_ids") or []) and x.get("status") == "resolved"]
                extra.append("来源有冲突，采信理由：" + "；".join(r for r in reasons if r))
        elif c["verification"] == "unverified" and c.get("affects_conclusion"):
            kind, verification, statement = "assumption", "not_applicable", statement.rstrip("。") + "（待确认）"
            notes.append(f"{cid} 未核实但影响结论，改写为待确认的假设")
            src_ids = []
        elif c["verification"] == "refuted":
            kind, verification = "assumption", "not_applicable"
            statement = "曾认为" + statement.rstrip("。") + "，已被推翻"
            contra = sorted({evidence[l["evidence_id"]]["source_id"] for l in links
                             if l["claim_id"] == cid and l["relation"] == "contradicts" and l["evidence_id"] in evidence})
            limitation = "反证：" + ("；".join(f"{sources[s]['title']}（{s}）" for s in contra if s in sources) or c.get("counterevidence") or "见证据账")
            notes.append(f"{cid} 已被推翻，改写为被推翻的说法")
            src_ids = []
        else:
            why = "冲突没有写采信理由" if c["verification"] == "conflicting" else "未核实且不影响结论，不进入成品"
            problems.append(f"主张 {cid}（{c['verification']}）不能进入报告：{why}")
            continue
        for mid in c.get("metric_refs") or []:
            m = metrics.get(mid)
            if not m:
                problems.append(f"主张 {cid} 引用的指标 {mid} 不存在")
            elif m.get("status") in ("missing", "not_applicable"):
                notes.append(f"{cid} 引用的指标 {mid} 状态为 {m['status']}，不进入报告")
            else:
                metric_owner.setdefault(mid, cid)
                if m.get("status") == "approximate":
                    extra.append(f"{m.get('label') or '相关数值'}为近似值" + (f"（{m['status_reason']}）" if m.get("status_reason") else ""))
        if extra:
            limitation = "；".join([limitation, *extra]) if limitation else "；".join(extra)
        forge_claims.append({"id": cid, "kind": kind, "statement": statement, "verification": verification, "sourceKeys": src_ids,
                             **{k: c.get(k) or "不适用" for k in ("period", "population", "unit", "denominator", "calculation", "inference")},
                             "limitation": limitation or "无"})

    # 公式的输入指标挂在公式指标所属的主张下
    pending = list(metric_owner)
    while pending:
        mid = pending.pop()
        for arg in (metrics[mid].get("formula") or {}).get("args") or []:
            if arg not in metric_owner:
                if arg not in metrics or metrics[arg].get("status") in ("missing", "not_applicable"):
                    problems.append(f"指标 {mid} 的公式输入 {arg} 不存在或没有值")
                    continue
                metric_owner[arg] = metric_owner[mid]
                pending.append(arg)
    if problems:
        raise BridgeError(problems)
    try:
        pool = _Pool(metrics, list(metric_owner))
    except M.MetricError as e:
        raise BridgeError([str(e)]) from e
    values = set(pool.by_display)
    for fc in forge_claims:
        owned = [mid for mid, owner in metric_owner.items() if owner == fc["id"]]
        prefer = set(claims[fc["id"]].get("metric_refs") or [])
        for k in CLAIM_TEXT:
            fc[k] = pool.tokenize(fc[k], prefer, f"主张 {fc['id']}.{k}", allow, problems, counter)
        if owned:
            fc["metrics"] = [{"id": mid, "unit": metrics[mid]["unit"], "decimals": metrics[mid]["decimals"],
                              **({"value": metrics[mid]["value"]} if metrics[mid].get("value") is not None
                                 else {"formula": {"op": metrics[mid]["formula"]["op"], "args": list(metrics[mid]["formula"]["args"])}})}
                             for mid in owned]

    # 3. 来源
    used_sources = sorted({s for fc in forge_claims for s in fc["sourceKeys"]})
    forge_sources, references = {}, []
    for sid in used_sources:
        src = sources[sid]
        locs = sorted({e["locator"] for e in evidence.values() if e["source_id"] == sid and e.get("locator")
                       and any(l["evidence_id"] == e["id"] and l["claim_id"] in used for l in links)})
        forge_sources[sid] = _source_entry(src, locs)
        url = src.get("final_url") or src.get("url") or ""
        web = url.startswith(("http://", "https://"))   # 引擎的参考资料只接受网页链接；用户文件只写类别
        references.append({k: v for k, v in {"id": sid, "title": src["title"], "author": src.get("author_org") or src.get("publisher"),
                                              "date": src.get("published"), "url": url if web else None,
                                              "kind": "用户提供材料" if src.get("origin") == "user" else None,
                                              "locator": "、".join(locs)}.items() if v})

    # 4. 页面
    notes_by_page = {n["page"]: n["text"] for n in (sidecar or {}).get("speaker_notes") or []}
    forge_slides = []
    for s in slides:
        where = f"第 {s['page']} 页"
        refs = s.get("claim_refs") or []
        prefer = {mid for cid in refs for mid in (claims.get(cid, {}).get("metric_refs") or [])} | set(s.get("metric_refs") or [])
        fs = {"id": f"p{s['page']:02d}", "sequence": s["page"], "pageRole": s["page_role"], "storyBeat": s["story_beat"],
              "title": pool.tokenize(s["action_title"], prefer, f"{where}标题", allow, problems, counter),
              "subtitle": s.get("subtitle") or "", "cornerLabel": s.get("section") or "", "speakerIntent": notes_by_page.get(s["page"], "")}
        _scan_only(fs["subtitle"], values, f"{where}副标题", allow, problems, counter)
        if s["page_role"] in CONTENT_ROLES:
            _scan_only(s["adds"], values, f"{where} adds", allow, problems, counter)
            for mid in s.get("metric_refs") or []:
                if mid not in metric_owner:
                    problems.append(f"{where} metric_refs 里的 {mid} 不在报告的指标里（缺失，或没有被本报告的主张引用）")
            vi = s.get("visual_intent") or {}
            panels = s["panels"]
            fs.update({
                "proves": pool.tokenize(s["proves"], prefer, f"{where} proves", allow, problems, counter),
                "adds": s["adds"], "claimRefs": list(refs), "metricRefs": list(s.get("metric_refs") or []),
                "visual": {k: v for k, v in {"layout": vi.get("layout") or "custom", "readingPath": vi.get("reading_path"),
                                             "layoutReason": vi.get("layout_reason"), "repetitionReason": vi.get("repetition_reason"),
                                             "regions": [{k2: v2 for k2, v2 in {"slot": p.get("slot"), "role": p["role"], "span": p.get("span", 1),
                                                                                  "panelRef": p["id"]}.items() if v2 is not None} for p in panels]}.items() if v},
                "density": {k: v for k, v in {"profile": s["density"]["profile"],
                                              "evidenceUnits": [{"role": u["role"], "purpose": u["purpose"]} for u in s["density"]["evidence_units"]],
                                              "spaceIntent": s["density"]["space_intent"], "sparseReason": s["density"].get("sparse_reason")}.items() if v},
                "exhibit": {"contract": "semantic-exhibit-v1", "semantics": {"composition": {
                    "version": 1, "anchorPanel": s.get("anchor_panel") or panels[0]["id"], "readingOrder": [p["id"] for p in panels],
                    "panels": {p["id"]: _panel(p) for p in panels},
                    "relations": [{"id": r["id"], "kind": r["kind"], "panelRefs": list(r["panel_refs"]), "reason": r["reason"]} for r in s.get("relations") or []]}}}})
        forge_slides.append(fs)
    for n in (sidecar or {}).get("speaker_notes") or []:
        _scan_only(n["text"], values, f"讲者备注第 {n['page']} 页", allow, problems, counter)
    if problems:
        raise BridgeError(problems)

    brief = deck["brief"]
    blueprint = {
        "schemaVersion": 3, "analysisAlgorithm": "semantic-v2",
        "deck": {k: v for k, v in {"title": deck["title"], "audience": deck.get("audience") or "未注明", "decision": deck.get("decision"),
                                   "mode": "reading", "ratio": deck.get("ratio") or "16x9", "arc": deck["arc"],
                                   "arcReason": deck.get("arc_reason") if deck["arc"] == "other" else None}.items() if v},
        "sources": forge_sources, "claims": forge_claims, "artifacts": [],
        "analysis": {
            "brief": {"question": brief["question"], "purpose": brief["purpose"], "scope": brief["scope"], "period": brief["period"],
                      "baseline": brief["baseline"], "constraints": brief["constraints"], "successCriteria": brief["success_criteria"]},
            "issues": [{"id": "core", "question": brief["question"], "priority": "high", "disposition": "answered", "workItemRefs": ["storyline"]}],
            "gaps": [], "options": [],
            "workItems": [{"id": "storyline", "issueRefs": ["core"], "method": "editorial",
                           "rationale": "分析和核实已在证据账与故事线阶段完成，报告引擎只组织呈现", "status": "complete",
                           "inputClaimRefs": [], "artifactRefs": [], "outputClaimRefs": [fc["id"] for fc in forge_claims],
                           "counterEvidence": "各主张的限制、反证和未解决事项见证据账；缺口在风险页或附录列出"}],
            "synthesis": {"answerClaimRefs": list(deck["answer_claim_refs"]), "openIssueRefs": [], "basis": deck.get("decision") or brief["question"]}},
        "slides": forge_slides}
    on_pages = {cid for s in slides if s["page_role"] in CONTENT_ROLES for cid in s.get("claim_refs") or []}
    a_cards = [c for c in led.read("cards") if c.get("value_tier") == "A"]
    missing = [f"{c['id']}（{c['content']}）" for c in a_cards if not c.get("claim_id") or c["claim_id"] not in on_pages]
    return {"blueprint": blueprint, "references": references, "notes": notes,
            "trace": {"checked": counter[0], "untraced": [], "allowed": sorted(allow)},
            "a_cards": {"checked": len(a_cards), "missing": missing}}


def _panel(p):
    sel = {"relationship": p["relationship"], "reason": p["reason"]}
    if p.get("alternative"):
        sel.update(alternative=p["alternative"], tradeoff=p.get("tradeoff") or "")
    out = {"purpose": p["purpose"], "claimRefs": list(p["claim_refs"]), "form": p["form"], "selection": sel}
    for ours, theirs in (("capacity", "capacity"), ("semantic_type", "semanticType"), ("visual", "visual"), ("source_ids", "sourceKeys")):
        if p.get(ours):
            out[theirs] = p[ours]
    return out


def _body_problems(s, where):
    out = []
    for key in ("proves", "adds", "density", "panels", "claim_refs"):
        if not s.get(key):
            out.append(f"{where}（正文）缺少 {key}")
    if out:
        return out
    panels = s["panels"]
    ids = [p["id"] for p in panels]
    if len(set(ids)) != len(ids):
        out.append(f"{where} panel id 重复")
    if sum(p["role"] == "primary" for p in panels) != 1:
        out.append(f"{where} 必须恰好有一个 role=primary 的 panel")
    if ((s.get("visual_intent") or {}).get("layout") or "custom") == "custom":
        for p in panels:
            if p.get("slot") not in SLOTS:
                out.append(f"{where} panel {p['id']} 的 slot 须为 {'/'.join(sorted(SLOTS))}（自定义布局）")
    for p in panels:
        if len(p["reason"].strip()) < 12:
            out.append(f"{where} panel {p['id']} 的选型理由至少 12 个字：具体说明这个形式怎样呈现本页的证据关系")
        if len(p["purpose"].strip()) < 8:
            out.append(f"{where} panel {p['id']} 的用途至少 8 个字：这件展品让读者看出什么")
    if len(s["adds"].strip()) < 12:
        out.append(f"{where} adds 至少 12 个字：读者读完本页比上一页多知道什么")
    if len(s["density"]["space_intent"].strip()) < 12:
        out.append(f"{where} density.space_intent 至少 12 个字")
    for u in s["density"]["evidence_units"]:
        if len(u["purpose"].strip()) < 8:
            out.append(f"{where} 证据单元的用途至少 8 个字：{u['purpose']}")
    for r in s.get("relations") or []:
        if len(r["reason"].strip()) < 12:
            out.append(f"{where} relation {r['id']} 的理由至少 12 个字：这些展品为何必须一起看")
    if len(panels) > 1 and not s.get("relations"):
        out.append(f"{where} 有多个 panel，须用 relations 说明它们如何共同支持本页结论")
    for r in s.get("relations") or []:
        for ref in r["panel_refs"]:
            if ref not in ids:
                out.append(f"{where} relation {r['id']} 引用了不存在的 panel {ref}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="slides.json + 证据账 → report-forge 蓝图")
    ap.add_argument("task")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--allow", action="append", default=[], help="显式放行的数字（要写进验收记录）")
    a = ap.parse_args(argv)
    story = pathlib.Path(a.task) / "07_storyline"
    try:
        slides_doc = json.loads((story / "slides.json").read_text(encoding="utf-8"))
        side = story / "sidecar.json"
        sidecar = json.loads(side.read_text(encoding="utf-8")) if side.is_file() else None
    except (OSError, ValueError) as e:
        print(f"读取失败：{e}", file=sys.stderr)
        return 2
    try:
        result = build(a.task, slides_doc, sidecar, a.allow)
    except BridgeError as e:
        for p in e.problems:
            print(f"- {p}", file=sys.stderr)
        return 1
    pathlib.Path(a.output).write_text(json.dumps(result["blueprint"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for n in result["notes"]:
        print(f"说明：{n}")
    print(f"已写出 {a.output}（{result['trace']['checked']} 个数字都已换成指标引用或追溯到证据账）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
