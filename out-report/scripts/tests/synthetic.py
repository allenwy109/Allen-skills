"""测试专用：生成合成的规划观察、代表页观察和审查稿，用来驱动 report-forge 的完整流程。

这些记录的 reviewer、basis 都写明"合成"，只验证字段和流程能走通，不是实际看图或审查的结论。
正式任务里，这些文件由作者和成品审查员按实际所见填写（见 out-report/SKILL.md），本模块不能用于正式任务。
"""
import hashlib
import json
import os
import pathlib

WHO = "合成夹具（不是实际审查）"
BODY = ("analysis", "decision", "action", "risk", "appendix")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _write(d, name, doc):
    f = d / "obs" / name
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return f


def planning(d, item, requirement):
    bp = json.loads((d / "deck-blueprint.json").read_text(encoding="utf-8"))
    obs = {"kind": "planning", "reviewer": WHO, "basis": "合成规划观察", "requirementRefs": [requirement],
           "alternatives": [{"pageId": s["id"], "considered": "合成候选", "decision": "见蓝图 selection 与 layoutReason"} for s in bp["slides"]],
           "files": [{"record": "../deck-blueprint.json", "sha256": sha(d / "deck-blueprint.json")}]}
    if item == "module-fill-plan":
        obs["modulePlans"] = [{"pageId": s["id"], "regions": [{"id": r["slot"], "content": "合成内容", "layout": "合成布局", "whitespace": "无预留"}
                                                             for r in s["visual"]["regions"]]}
                              for s in bp["slides"] if s["pageRole"] in BODY]
    return _write(d, f"{item}.json", obs)


def representatives(d, smoke_audit, pages=("p02", "p03")):
    a = json.loads(pathlib.Path(smoke_audit).read_text(encoding="utf-8"))
    rows = [r for r in a["rows"] if r.get("pageId") in pages]
    shots = [pathlib.Path(smoke_audit).parent / r["screenshot"] for r in rows]
    rel = lambda p: os.path.relpath(p, d / "obs")  # noqa: E731
    return _write(d, "representatives.json", {
        "kind": "visual", "reviewer": WHO, "basis": "合成代表页观察", "requirementRefs": ["chart-diversity", "layout-diversity", "module-fill"],
        "alternatives": [{"pageId": r["pageId"], "considered": "合成候选", "decision": "合成取舍"} for r in rows],
        "audit": {"record": rel(smoke_audit), "sha256": sha(smoke_audit)},
        "files": [{"record": rel(s), "sha256": sha(s)} for s in shots],
        "moduleObservations": [{"pageId": r["pageId"], "regionId": g["id"], "observed": "合成观察", "decision": "合成判断"}
                               for r in rows for g in r["moduleFill"]["regions"]]})


def production(d, deck_html):
    return _write(d, "production.json", {"kind": "production", "reviewer": WHO, "basis": "合成制作记录", "requirementRefs": [],
                                         "files": [{"record": os.path.relpath(deck_html, d / "obs"), "sha256": sha(deck_html)}]})


def fill_reviews(d, pages_json):
    """按 review-pack 的清单填作者稿和独立审查稿。收束句取自审计里页面的实际文字（引擎会核对）。"""
    rv = d / "reviews"
    rp = json.loads((rv / "review-pack.json").read_text(encoding="utf-8"))
    a = json.loads(pathlib.Path(rp["auditFile"]).read_text(encoding="utf-8"))
    ev = [e["id"] for e in a["evidenceManifest"]["entries"]]
    pages = [r["page"] for r in a["rows"]]
    analysis = json.loads(pathlib.Path(pages_json).read_text(encoding="utf-8"))["analysisSha256"]
    for name, indep in (("author.json", "author"), ("independent.json", "independent")):
        who = f"{WHO}·{indep}"
        r = json.loads((rv / name).read_text(encoding="utf-8"))
        r.update(status="complete", reviewer=who, analysisSha256=analysis)
        r["coverage"] = [{"reviewer": who, "independence": indep, "layers": ["page", "exhibit", "annotation", "typography", "narrative"],
                          "htmlPages": pages, "pdfPages": pages, "evidence": [{"id": i} for i in ev],
                          "panelRefs": [c["panelRef"] for c in rp["compositionChecklist"] if "panelRef" in c],
                          "relationRefs": [c["relationRef"] for c in rp["compositionChecklist"] if "relationRef" in c],
                          "narrativeReadings": [{"slideId": n["slideId"],
                                                 "observedTakeaway": next(x["focus"]["takeawayText"] for x in a["rows"] if x.get("pageId") == n["slideId"])}
                                                for n in rp["narrativeChecklist"]]}]
        r["checks"] = {k: {"status": "pass", "basis": "合成审查"} for k in ("analysis", "evidence", "visual")}
        r["warningReview"] = [{"warning": w, "status": "accepted", "note": "合成处置"} for w in a.get("warnings", [])]
        for q in r["qualityChecks"]:
            q.update(status="pass", reviewer=who, basis="合成整册审查", evidenceIds=ev)
            if q["id"] == "module-fill":
                for p in q["inventoryChecks"]:
                    p["basis"] = "合成：已核对区域清单"
                for o in q["observations"]:
                    o.update(observed="合成模块观察", decision="合成判断")
                    for g in o["diagnostics"]:
                        g.update(disposition="measurement-artifact", basis="合成处置")
            else:
                q["observations"] = [{"pageId": x.get("pageId") or f"page-{x['page']}", "observed": "合成", "considered": "合成", "decision": "合成"}
                                     for x in a["rows"]]
        (rv / name).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
