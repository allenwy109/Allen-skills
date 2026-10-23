#!/usr/bin/env python3
"""公司尽调工具（设计 §5.2）。数据写进统一证据账；工作文件在 <任务>/03d_diligence/。

子命令：
  init           建尽调：project 表、目标主体 ENT-0001（待核实）、18 个模块适用性、可选评分行、同步研报覆盖、复制模板
  sync           重算上市追溯、必读研报类别、三个"最新"指针、覆盖状态和研报门槛；为缺失类别建缺口
  status         只读：上市追溯、必读类别、门槛
  plan           生成检索计划（只是计划，不是日志）
  ratios         财务比率（--input financial-input.json），结果写 03d_diligence/calc/
  score          评分（默认关闭；公司研究禁止）
  check          结构 + 语义 + 研报检查；--mode completed 时加查约定范围完成的条件
  check-content  报告内容契约（report-content.json）；--after-split 拆页后复核；--final 加查 22 条人工清单
  audit          生成底稿 03d_diligence/audit.md（Quick 10 节，其他 20 节）和 project.json 可读导出

退出码：0 通过；1 检查发现硬错误；2 参数、输入或文件错误。
"""
import argparse
import datetime
import json
import os
import pathlib
import shutil
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def _bootstrap():
    for c in (os.environ.get("ALLEN_RUNTIME"), SKILL_DIR.parent / "_allen-runtime", SKILL_DIR.parent):
        if c and (pathlib.Path(c) / "tools" / "lib" / "runtime.py").is_file():
            sys.path.insert(0, str(pathlib.Path(c)))
            return
    raise SystemExit("找不到运行时（tools/lib），请先运行 ./install.sh")


_bootstrap()
import daudit  # noqa: E402
import dcontent  # noqa: E402
import dcore  # noqa: E402
import dplan  # noqa: E402
import dratios  # noqa: E402
import dscore  # noqa: E402
from tools.lib.ledger import Ledger, LedgerError  # noqa: E402

TEMPLATES = SKILL_DIR / "assets" / "templates"
PURPOSES = ("company_research", "investment", "acquisition", "partnership", "credit", "supplier", "competitor")


def work(task):
    return pathlib.Path(task) / "03d_diligence"


def emit(obj, as_json=True):
    print(json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=False))


def cmd_init(a):
    task = pathlib.Path(a.task)
    if a.purpose == "company_research" and a.enable_scoring:
        print("公司研究不能启用评分", file=sys.stderr)
        return 2
    as_of = a.as_of or datetime.date.today().isoformat()
    led = Ledger(task)
    if not (task / "03_evidence" / "ledger").is_dir():
        led.init()
    if led.read("entities"):
        print("证据账里已有主体：这个任务已经建过尽调，用 sync 和 check 继续", file=sys.stderr)
        return 2
    ent = led.add("entities", {"legal_name": a.target, "entity_type": "legal_entity", "identity_status": "pending", "listing_status": a.listing_status,
                               **({"registration_id": a.registration_id} if a.registration_id else {}),
                               **({"exchange": a.exchange} if a.exchange else {}), **({"security_code": a.security_code} if a.security_code else {}),
                               **({"geography": a.geography} if a.geography else {}), "identity_notes": "用户输入的待核实身份"})
    fields = {"target_name": a.target, "target_entity_id": ent, "purpose_status": "confirmed" if a.purpose else "pending",
              "diligence_depth": a.depth, "as_of_date": as_of, "information_cutoff": as_of, "timezone": a.timezone,
              "historical": as_of < datetime.date.today().isoformat(), "constraints": {"network": a.network},
              "geography": [a.geography] if a.geography else [], "identity_status": "pending", "listing_trigger": "pending",
              "control_chain_checked": False, "languages": ["zh", "en"], "module_scope": {m: {"status": "pending"} for m in dcore.MODULES},
              "report_status": "draft", "declared_complete": False, "scoring_enabled": bool(a.enable_scoring), "scoring_threshold": 0.8,
              "peer_required": False, "joint_control_triggers": False}
    if a.purpose:
        fields["purpose"] = a.purpose
    if led.read("project"):
        led.patch("project", "project", fields)
    else:
        led.add("project", {"id": "project", **fields})
    if a.enable_scoring:
        weights = dscore.default_override(a.purpose)["weights"]
        for dim, w in weights.items():
            led.add("scorecard", {"purpose": a.purpose, "dimension": dim, "weight": w, "applicability": "applicable", "confidence": "unknown",
                                  "coverage_status": "missing", "reason": "尚未评分"})
    w = work(task)
    for sub in ("modules", "calc", "materials/images"):
        (w / sub).mkdir(parents=True, exist_ok=True)
    for name in ("report-content.json", "request-list.md", "interview-outline.md", "financial-input.json"):
        if not (w / name).exists():
            shutil.copy2(TEMPLATES / name, w / name)
    r = dcore.sync_coverage(task)
    emit({"status": "initialized", "path": str(w), "target_entity_id": ent, "research_gate": r["research_gate"],
          "note": "只做了初始化：下一步锁定主体身份和控制链（entities、relations），确认模块适用性，再 sync、plan"})
    return 0


def cmd_sync(a):
    r = dcore.sync_coverage(a.task)
    _export(a.task)
    emit(r)
    return 1 if r["errors"] else 0


def cmd_status(a):
    _, data = dcore.load(a.task)
    d = dcore.derive(data)
    emit({"listing_trigger": d["listing"], "listed_entities": d["listed"], "research_gate": d["gate"], "warnings": d["warnings"], "errors": d["errors"],
          "requirements": [{"entity": e, "category": c, "state": d["rows"][(e, c)]["state"], "latest_read": d["rows"][(e, c)]["pointers"]["read"]}
                           for e, c, _, _ in d["requirements"]]})
    return 0


def cmd_plan(a):
    _, data = dcore.load(a.task)
    plan = dplan.build(data)
    if a.output:
        pathlib.Path(a.output).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已写出 {a.output}（{len(plan['tasks'])} 个任务）")
    else:
        emit(plan)
    return 0


def cmd_ratios(a):
    try:
        doc = json.loads(pathlib.Path(a.input).read_text(encoding="utf-8"))
        if doc.get("synthetic") is None:
            raise dratios.InputError("要写 synthetic（是否为合成数据）")
        result = dratios.calculate(doc)
    except (OSError, ValueError, dratios.InputError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    _, data = dcore.load(a.task)
    ev_ids = {e["id"] for e in data["evidence"]}
    src_ids = {s["id"] for s in data["sources"]}
    missing = sorted({e for ids in doc["input_evidence"].values() for e in ids} - ev_ids) + sorted(set(doc["source_ids"]) - src_ids)
    if missing:
        print(json.dumps({"error": f"输入引用了证据账里没有的证据或来源：{missing}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    out = pathlib.Path(a.output) if a.output else work(a.task) / "calc" / f"ratios-{doc['entity_id']}-{doc['period_end']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"input": a.input, **result}, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    print(f"已写出 {out}；告警 {len(result['alerts'])} 条（只是核查线索）")
    return 0


def cmd_score(a):
    _, data = dcore.load(a.task)
    r = dscore.score(data)
    emit(r)
    return 1 if r.get("errors") else 0


def placeholders(task):
    p = work(task) / "report-content.json"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    return [m for m in ("{{", "尚未填写】", "未提供模块分析") if m in text]


def check(task, mode="draft"):
    led, data = dcore.load(task)
    errors, warnings = [], []
    for i in led.check():
        (errors if i["level"] == "error" else warnings).append(f"证据账 {i['table']}:{i['id']}：{i['message']}")
    d = dcore.derive(data)
    errors += d["errors"] + dcore.semantic_errors(data) + dcore.research_errors(data, d)
    warnings += d["warnings"]
    s = dscore.score(data)
    errors += s.get("errors") or []
    p = data["project"]
    ents = {e["id"]: e for e in data["entities"]}
    if p.get("identity_status") and p["identity_status"] != ents.get(p.get("target_entity_id"), {}).get("identity_status"):
        errors.append("project.identity_status 与主体表里目标主体的身份状态不一致")
    groups = {}
    for src in data["sources"]:
        if src.get("origin_group"):
            groups.setdefault(src["origin_group"], []).append(src["id"])
    warnings += [f"同源组 {g}：{'、'.join(ids)} 只算一个独立来源" for g, ids in groups.items() if len(ids) > 1]
    if d["gate"] in ("partial", "incomplete"):
        warnings.append(f"研报门槛是 {d['gate']}：首页要说明限制，列出报告、机构、日期、障碍和补齐路径")
    for act in p.get("completed_actions") or []:
        if act["status"] == "completed" and not act.get("evidence_ids") and not act.get("output_locator"):
            errors.append(f"动作「{act['action']}」标为完成，却没有证据或产出位置")
    completed = mode == "completed" or p.get("report_status") == "complete" or p.get("declared_complete")
    if completed:
        errors += dcore.completion_errors(data, d)
        if ents.get(p.get("target_entity_id"), {}).get("identity_status") != "resolved":
            errors.append("完成态要求目标主体身份已锁定")
        pending = [m for m, v in (p.get("module_scope") or {}).items() if v.get("status") == "pending"]
        if pending:
            errors.append(f"完成态不能有 pending 的模块：{'、'.join(pending)}")
        if not p.get("last_refresh_at"):
            errors.append("完成态要有 last_refresh_at（交付前复查一次最新研报）")
        errors += [f"report-content.json 残留占位：{m}" for m in placeholders(task)]
        mdir = work(task) / "modules"
        for m, v in (p.get("module_scope") or {}).items():
            if v.get("status") == "applicable":
                files = sorted(mdir.glob(f"{m}-*.md")) if mdir.is_dir() else []
                if len(files) != 1 or not files[0].read_text(encoding="utf-8").strip():
                    errors.append(f"适用模块 {m} 要有且只有一个非空的分析文件 modules/{m}-*.md")
    return {"status": "invalid" if errors else "structure_passed", "mode": "completed" if completed else mode, "errors": errors, "warnings": warnings,
            "research_gate": d["gate"], "listing_trigger": d["listing"], "score": s}


def cmd_check(a):
    r = check(a.task, a.mode)
    emit(r) if a.json else _print(r)
    return 1 if r["errors"] else 0


def content_check(task, after_split=False, final=False):
    _, data = dcore.load(task)
    p = work(task) / "report-content.json"
    try:
        content = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"status": "invalid", "errors": [f"读不了 {p}：{e}"], "warnings": []}
    r = dcontent.validate(content, data, task)
    hints = dcontent.visual_hints(content)
    errors = list(r["errors"])
    if after_split:
        try:
            block_map = json.loads((pathlib.Path(task) / "07_storyline" / "block_map.json").read_text(encoding="utf-8"))
            slides = json.loads((pathlib.Path(task) / "07_storyline" / "slides.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return {"status": "invalid", "errors": [f"拆页后复核要有 07_storyline/block_map.json 和 slides.json：{e}"], "warnings": r["warnings"]}
        errors = list(dict.fromkeys(errors + dcontent.after_split(content, block_map, slides, data, task)))
    if final:
        errors += dcontent.manual_errors(data)
    return {"status": "invalid" if errors else "passed", "errors": errors, "warnings": r["warnings"], "visual_review": hints,
            "reader_coverage": r.get("reader_coverage"), "chart_count": r.get("chart_count"), "used_evidence": r.get("used_evidence"),
            "reading_review": {"status": "requires_independent_reading", "questions": dcontent.TOPIC_QUESTIONS}}


def cmd_check_content(a):
    r = content_check(a.task, a.after_split, a.final)
    emit(r) if a.json else _print(r)
    return 1 if r["errors"] else 0


def _export(task):
    _, data = dcore.load(task)
    w = work(task)
    w.mkdir(parents=True, exist_ok=True)
    (w / "project.json").write_text(json.dumps(data["project"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_audit(a):
    _, data = dcore.load(a.task)
    d = dcore.derive(data)
    p = work(a.task) / "report-content.json"
    content = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    hints = dcontent.visual_hints(content) if content else []
    text, errors = daudit.build(a.task, data, d, content, hints, dscore.score(data))
    (work(a.task) / "audit.md").write_text(text, encoding="utf-8")
    _export(a.task)
    for e in errors:
        print(f"- {e}", file=sys.stderr)
    print(f"已生成 {work(a.task) / 'audit.md'}")
    return 1 if errors else 0


def _print(r):
    print(f"状态：{r['status']}")
    for e in r["errors"]:
        print(f"[错误] {e}")
    for w in r["warnings"]:
        print(f"[警告] {w}")
    for h in r.get("visual_review") or []:
        print(f"[编排提示] {h['section']}：{h['message']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="公司尽调")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("task")
    p.add_argument("--target", required=True)
    p.add_argument("--purpose", choices=PURPOSES)
    p.add_argument("--depth", choices=("Quick", "Standard", "Deep"), default="Standard")
    p.add_argument("--as-of")
    p.add_argument("--timezone", default="Asia/Shanghai")
    p.add_argument("--geography")
    p.add_argument("--registration-id")
    p.add_argument("--listing-status", default="unknown", choices=("listed", "unlisted", "otc", "bond_only", "proposed", "delisted", "unknown"))
    p.add_argument("--exchange")
    p.add_argument("--security-code")
    p.add_argument("--network", default="unknown", choices=("unknown", "online", "offline"))
    p.add_argument("--enable-scoring", action="store_true")
    for name in ("sync", "status", "score", "audit"):
        sub.add_parser(name).add_argument("task")
    p = sub.add_parser("plan")
    p.add_argument("task")
    p.add_argument("-o", "--output")
    p = sub.add_parser("ratios")
    p.add_argument("task")
    p.add_argument("--input", required=True)
    p.add_argument("-o", "--output")
    p = sub.add_parser("check")
    p.add_argument("task")
    p.add_argument("--mode", choices=("draft", "completed"), default="draft")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("check-content")
    p.add_argument("task")
    p.add_argument("--after-split", action="store_true")
    p.add_argument("--final", action="store_true")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        return {"init": cmd_init, "sync": cmd_sync, "status": cmd_status, "plan": cmd_plan, "ratios": cmd_ratios, "score": cmd_score,
                "check": cmd_check, "check-content": cmd_check_content, "audit": cmd_audit}[a.cmd.replace("_", "-")](a)
    except LedgerError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
