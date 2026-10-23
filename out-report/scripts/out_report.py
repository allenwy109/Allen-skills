#!/usr/bin/env python3
"""出正式报告（设计 §6.2 out-report）。所有会写生产记录的步骤都经 report-forge 的统一入口 report.cjs 执行。

子命令（任务目录固定为 <任务>/07_storyline/forge-work/）：
  init     转换前检查并生成蓝图（tools/bridge/to_forge.py）→ report.cjs init（editorial、narrative-focus-1）→
           写 task 字段（kind=report、complex、majorConclusion、independent）→ 写蓝图、首尾页（bookend-cover/references/back.html）→ 激活执行清单
  refresh  slides.json 或证据账改动后重新生成蓝图和首尾页（引擎会把受影响的已完成项标为需要重新核实）
  plan     提交并接收执行清单项：chart-plan、layout-plan、module-fill-plan、representatives、production、delivery
  step     ready | compile | assemble | smoke | iteration | acceptance | review-pack | aggregate | snapshot | package | archive |
           status | next | resume —— 派生 task、HTML、验收记录、聚合审查的路径从执行清单的 productionRefs 读取
  finish   打包之后：复制 HTML、PDF 到 08_deliverables/report/，由 sidecar 生成讲者备注，回查手写文字里的数字，登记验收

退出码：0 成功；1 被检查拦下或引擎步骤失败；2 参数或环境错误。
"""
import argparse
import hashlib
import html
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
PLAN_ITEMS = ("chart-plan", "layout-plan", "module-fill-plan", "representatives", "production", "delivery")
TASK_FIELDS = {"kind": "report", "complexity": "complex", "majorConclusion": True, "reviewPolicy": "independent"}


def _bootstrap():
    for c in (os.environ.get("ALLEN_RUNTIME"), SKILL_DIR.parent / "_allen-runtime", SKILL_DIR.parent):
        if c and (pathlib.Path(c) / "tools" / "lib" / "runtime.py").is_file():
            sys.path.insert(0, str(pathlib.Path(c)))
            return
    raise SystemExit("找不到运行时（tools/lib），请先运行 ./install.sh")


_bootstrap()
from tools.acceptance import Acceptance  # noqa: E402
from tools.bridge import poster_numbers, to_forge  # noqa: E402
from tools.lib import office, runtime  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402


class StepError(Exception):
    pass


def forge_dir(task):
    # 解析符号链接（如 macOS 的 /var → /private/var）：引擎用真实路径比对 task 和 HTML 的绑定
    return (pathlib.Path(task) / "07_storyline" / "forge-work").resolve()


def engine():
    return runtime.engine_dir("report-forge", skill_dir=SKILL_DIR)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def last_json(text):
    """report.cjs 的 qa 等步骤先逐行打印进度，最后才输出结果 JSON。"""
    i = text.rfind("\n{\n")
    return json.loads(text[i + 1:] if i >= 0 else text)


def node(*args, script="report.cjs", ok_codes=(0,)):
    env = dict(os.environ, PATH=os.pathsep.join([str(runtime.runtime_root(skill_dir=SKILL_DIR) / "tools" / "bin"), os.environ.get("PATH", "")]))
    env.setdefault("CHROME_CHANNEL", runtime.chrome_channel())
    p = subprocess.run(["node", str(engine() / "scripts" / script), *map(str, args)], capture_output=True, text=True, env=env)
    if p.returncode not in ok_codes:
        raise StepError(f"{script} {args[0] if args else ''} 失败：{(p.stdout + p.stderr).strip()[-2000:]}")
    try:
        return last_json(p.stdout)
    except ValueError:
        return {"output": p.stdout}


# ---------- 执行清单 ----------

def plan_doc(d):
    return json.loads((d / "execution-plan.json").read_text(encoding="utf-8"))


def plan_update(d, ops):
    doc = plan_doc(d)
    req = d / ".allen" / f"request-{doc['revision']}.json"
    req.parent.mkdir(exist_ok=True)
    req.write_text(json.dumps({"operationId": f"allen-{doc['id'][:8]}-r{doc['revision']}", "expectedRevision": doc["revision"], "ops": ops},
                              ensure_ascii=False), encoding="utf-8")
    return node("plan-update", d / "task.json", "--request", req)


def production(d, op, key):
    ref = (plan_doc(d).get("productionRefs") or {}).get(op)
    if not ref:
        raise StepError(f"还没有有效的 {op} 结果，先完成前面的步骤（out_report.py step status 查看）")
    return d / ref["files"][key]["record"]


def runs(d):
    f = d / ".allen" / "runs.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def remember(d, key, value):
    data = runs(d)
    data[key] = str(value)
    (d / ".allen").mkdir(exist_ok=True)
    (d / ".allen" / "runs.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- 蓝图与首尾页 ----------

def load_story(task):
    story = pathlib.Path(task) / "07_storyline"
    slides = json.loads((story / "slides.json").read_text(encoding="utf-8"))
    side = story / "sidecar.json"
    return slides, (json.loads(side.read_text(encoding="utf-8")) if side.is_file() else None)


def write_inputs(task, d, allow):
    """转换前检查 → 蓝图、首尾页、转换记录。返回转换结果；有问题时抛 BridgeError。"""
    slides, sidecar = load_story(task)
    result = to_forge.build(task, slides, sidecar, allow)
    (d / "deck-blueprint.json").write_text(json.dumps(result["blueprint"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    deck = slides["deck"]
    cover = deck["cover"]
    meta = {"title": deck["title"], "subtitle": cover.get("subtitle"), "date": cover["date"], "producer": cover.get("producer"),
            "version": cover.get("version"), "project": cover.get("project"), "client": cover.get("client"), "access": cover.get("access"),
            "statement": cover.get("statement"), "closingText": cover.get("closing_text")}
    spec = d / ".allen" / "bookends-input.json"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(json.dumps({"meta": {k: v for k, v in meta.items() if v}, "sources": result["references"]}, ensure_ascii=False), encoding="utf-8")
    script = (f"const B=require({json.dumps(str(engine() / 'scripts' / 'bookends.cjs'))}),fs=require('fs');"
              "const s=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));"
              # 引擎要求每页显式声明母版边界；首尾页的模板没有写，这里补 space（整页留白、不画正文边框）。
              "const fb=h=>h.replace('data-frame=\"off\">','data-frame=\"off\" data-frame-boundary=\"space\">');"
              "const out=process.argv[2];"
              "fs.writeFileSync(out+'/bookend-cover.html',fb(B.cover(s.meta)));"
              "fs.writeFileSync(out+'/bookend-references.html',B.references({sources:s.sources}));"
              "fs.writeFileSync(out+'/bookend-back.html',fb(B.backCover(s.meta)));")
    p = subprocess.run(["node", "-e", script, str(spec), str(d)], capture_output=True, text=True)
    if p.returncode:
        raise StepError(f"生成首尾页失败：{p.stderr.strip()[-800:]}")
    (d / ".allen" / "conversion.json").write_text(json.dumps({k: result[k] for k in ("notes", "trace", "a_cards")}, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    return result


def cmd_init(a):
    task, d = pathlib.Path(a.task), forge_dir(a.task)
    if d.exists():
        print(f"{d} 已存在：改动 slides.json 或证据账后用 refresh；要从头开始，先确认旧任务不再需要，再删掉这个目录", file=sys.stderr)
        return 2
    try:
        to_forge.build(task, *load_story(task), a.allow)      # 先检查，不通过就不建引擎任务
    except to_forge.BridgeError as e:
        return report_problems(e.problems)
    node("init", d, "--work-mode", "editorial", "--visual", "narrative-focus-1")
    t = json.loads((d / "task.json").read_text(encoding="utf-8"))
    t.update(TASK_FIELDS)
    (d / "task.json").write_text(json.dumps(t, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = write_inputs(task, d, a.allow)
    brief = json.loads((task / "07_storyline" / "slides.json").read_text(encoding="utf-8"))["deck"]["brief"]
    plan_update(d, [{"action": "activate", "intake": {
        "goal": brief["question"], "scope": f"{brief['scope']}；{brief['period']}", "deliverables": "自包含 HTML 与同版 PDF，另附讲者备注",
        "constraints": f"{brief['constraints']}；图表多样性、版式多样性、正文模块填充三项固定要求",
        "approach": "分析与核实已在证据账和故事线阶段完成，报告引擎按 editorial 模式组织呈现",
        "nextStep": "完成整册图表、版式与模块填充规划", "openQuestions": []}}])
    for n in result["notes"]:
        print(f"说明：{n}")
    print(f"已建报告任务：{d}")
    print("下一步：写三项规划观察，用 plan 提交 chart-plan、layout-plan、module-fill-plan；然后 step ready、step compile。")
    return 0


def cmd_refresh(a):
    d = forge_dir(a.task)
    if not (d / "task.json").is_file():
        print("还没有报告任务，先运行 init", file=sys.stderr)
        return 2
    try:
        result = write_inputs(pathlib.Path(a.task), d, a.allow)
    except to_forge.BridgeError as e:
        return report_problems(e.problems)
    for n in result["notes"]:
        print(f"说明：{n}")
    print("已重新生成蓝图和首尾页；引擎会把受影响的规划、代表页等标为需要重新核实（step status 查看）。")
    return 0


def report_problems(problems):
    print("转换前检查没有通过，退回 core-storyline 或分析层修改：", file=sys.stderr)
    for p in problems:
        print(f"- {p}", file=sys.stderr)
    return 1


# ---------- 执行清单项 ----------

def cmd_plan(a):
    d = forge_dir(a.task)
    evidence = pathlib.Path(a.evidence).resolve()
    if d not in evidence.parents:
        print(f"观察文件要放在 {d} 里（引擎按相对计划目录的路径核对）", file=sys.stderr)
        return 2
    item = next((i for i in plan_doc(d)["items"] if i["id"] == a.item), None)
    if item is None:
        print(f"执行清单里没有 {a.item}", file=sys.stderr)
        return 2
    ops = []
    if item.get("state") not in (None, "pending"):
        ops.append({"action": "reopen", "id": a.item, "reason": a.reason or "按修改后的观察重新提交"})
    ops.append({"action": "start", "id": a.item})
    plan_update(d, ops)
    attempt = next(i for i in plan_doc(d)["items"] if i["id"] == a.item)["attempt"]["id"]
    plan_update(d, [{"action": "submit", "id": a.item, "attemptId": attempt, "evidence": os.path.relpath(evidence, d)},
                    {"action": "accept", "id": a.item, "reviewer": a.reviewer, "basis": a.basis}])
    print(f"{a.item} 已提交并接收")
    return 0


# ---------- 引擎步骤 ----------

def cmd_step(a):
    d = forge_dir(a.task)
    root = d / "task.json"
    op = a.op
    if op in ("status", "next", "resume"):
        out = node(op, root, ok_codes=(0, 1))
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    if op == "ready":
        out = node(d / "deck-blueprint.json", "--task", root, "--ready", script="deck_blueprint.cjs")
        print(json.dumps({k: out.get(k) for k in ("status", "errors")}, ensure_ascii=False, indent=1))
        return 0
    if op == "compile":
        out = node("compile", root)
    elif op == "assemble":
        out = node("assemble", production(d, "compile", "task"), "--pages", d / "pages.html", "--css", d / "page.css")
    elif op in ("smoke", "iteration"):
        extra = ["--pages", a.pages] if a.pages else []
        out = node("qa", production(d, "compile", "task"), "--html", production(d, "assemble", "html"), "--tier", op, *extra)
        remember(d, op, out["result"]["auditFile"])
    elif op == "acceptance":
        out = node("qa", production(d, "compile", "task"), "--html", production(d, "assemble", "html"), "--tier", "acceptance")
    elif op == "review-pack":
        out = node("review-pack", production(d, "compile", "task"), "--audit", production(d, "qa", "audit"))
        src, dest = pathlib.Path(out["result"]["directory"]), d / "reviews"
        dest.mkdir(exist_ok=True)
        for name in ("author.json", "independent.json", "warning-decisions.json", "review-pack.json"):
            shutil.copy2(src / name, dest / name)
        print(f"审查稿已复制到 {dest}：作者填 author.json，成品审查员填 independent.json（清单见 review-pack.json）")
    elif op == "aggregate":
        reviews = a.reviews or [str(d / "reviews" / "author.json"), str(d / "reviews" / "independent.json")]
        out = node("aggregate", production(d, "compile", "task"), "--audit", production(d, "qa", "audit"), "--reviews", json.dumps(reviews))
    elif op == "snapshot":
        out = node("snapshot", production(d, "compile", "task"), "--audit", production(d, "qa", "audit"), "--review", production(d, "aggregate", "review"))
    elif op == "package":
        title = json.loads((d / "deck-blueprint.json").read_text(encoding="utf-8"))["deck"]["title"]
        out = node("package", production(d, "compile", "task"), "--audit", production(d, "qa", "audit"),
                   "--review", production(d, "aggregate", "review"), "--name", a.name or title)
    elif op == "archive":
        out = node("archive", root)
    else:
        print(f"未知步骤：{op}", file=sys.stderr)
        return 2
    print(json.dumps(out.get("result", out), ensure_ascii=False, indent=1))
    return 0


# ---------- 完成 ----------

def speaker_notes(task, out_dir):
    _, sidecar = load_story(task)
    notes = (sidecar or {}).get("speaker_notes") or []
    if not notes:
        return []
    md = out_dir.parent / "speaker-notes.md"
    lines = ["# 讲者备注", ""] + [f"## 第 {n['page']} 页\n\n{n['text']}\n" for n in sorted(notes, key=lambda n: n["page"])]
    md.write_text("\n".join(lines), encoding="utf-8")
    page = out_dir.parent / ".speaker-notes.html"
    page.write_text("<html><head><meta charset='utf-8'><title>讲者备注</title></head><body><h1>讲者备注</h1>"
                    + "".join(f"<h2>第 {n['page']} 页</h2><p>{html.escape(n['text'])}</p>" for n in sorted(notes, key=lambda n: n["page"]))
                    + "</body></html>", encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = office.convert(page, "pdf", tmp)
        shutil.copy2(pdf, out_dir.parent / "speaker-notes.pdf")
    page.unlink()
    return [md, out_dir.parent / "speaker-notes.pdf"]


def storyline_check(task):
    """故事线检查（core-storyline 的 storyline check）是报告的前置条件。"""
    script = SKILL_DIR.parent / "core-storyline" / "scripts" / "storyline.py"
    if not script.is_file():
        return {"name": "故事线检查（storyline check）", "result": "failed", "detail": f"找不到 {script}"}
    p = subprocess.run([sys.executable, str(script), "check", str(task), "--json"], capture_output=True, text=True)
    try:
        r = json.loads(p.stdout)
    except ValueError:
        return {"name": "故事线检查（storyline check）", "result": "failed", "detail": (p.stdout + p.stderr)[-300:]}
    detail = "；".join(e["message"] for e in r["errors"])[:500] or f"零错误，警告 {len(r['warnings'])} 条"
    return {"name": "故事线检查（storyline check）", "result": "passed" if r["passed"] else "failed", "detail": detail}


def diligence_checks(task):
    """尽调报告的前置检查（设计 §8.3）：尽调检查、内容契约（拆页后复核、22 条人工清单）、三种完成状态。
    research_gate 为 complete、not_applicable 且 report_status=complete 算通过；partial、limited 记为"有限完成"（最终最高有条件通过）。"""
    if not (pathlib.Path(task) / "03d_diligence" / "report-content.json").is_file():
        return []
    script = SKILL_DIR.parent / "core-diligence" / "scripts" / "diligence.py"
    if not script.is_file():
        return [{"name": "尽调检查", "result": "failed", "detail": f"找不到 {script}"}]

    def run(*args):
        p = subprocess.run([sys.executable, str(script), *args, str(task), "--json"], capture_output=True, text=True)
        try:
            return json.loads(p.stdout)
        except ValueError:
            return {"errors": [(p.stdout + p.stderr)[-300:]]}
    chk = run("check")
    cnt = run("check-content", "--after-split", "--final")
    out = [{"name": "尽调检查（diligence check）", "result": "failed" if chk.get("errors") else "passed",
            "detail": "；".join(chk.get("errors") or [])[:500] or f"{chk.get('mode')}；警告 {len(chk.get('warnings') or [])} 条"},
           {"name": "尽调内容契约（拆页后复核、22 条人工清单）", "result": "failed" if cnt.get("errors") else "passed",
            "detail": "；".join(cnt.get("errors") or [])[:500] or "11 个主题、内容块规则、拆页后同章规则和人工清单都通过"}]
    gate = chk.get("research_gate")
    status = ((Ledger(task).read("project") or [{}])[0]).get("report_status")
    if gate in ("incomplete", None) or status in ("draft", None):
        result = "failed"
    elif gate == "partial" or status == "limited":
        result = "limited"
    else:
        result = "passed"
    out.append({"name": "尽调完成状态", "result": result, "detail": f"research_gate={gate}；report_status={status}"})
    return out


def cmd_finish(a):
    task, d = pathlib.Path(a.task), forge_dir(a.task)
    try:
        html_file, pdf_file = production(d, "package", "html"), production(d, "package", "pdf")
        audit = json.loads(production(d, "qa", "audit").read_text(encoding="utf-8"))
        review = json.loads(production(d, "aggregate", "review").read_text(encoding="utf-8"))
    except StepError as e:
        print(f"{e}（finish 要在 step package 之后运行）", file=sys.stderr)
        return 2
    conv = json.loads((d / ".allen" / "conversion.json").read_text(encoding="utf-8"))
    status = node("status", d / "task.json", ok_codes=(0, 1))
    items = {i["id"]: i.get("status") for i in status["items"]}
    out_dir = task / "08_deliverables" / "report"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in (html_file, pdf_file):
        shutil.copy2(f, out_dir / f.name)
        files.append(out_dir / f.name)
    notes = speaker_notes(task, out_dir)
    trace = poster_numbers.check(task, (out_dir / html_file.name).read_text(encoding="utf-8"), conv["trace"]["allowed"], report=True)
    story_check = storyline_check(task)
    checks = [
        story_check, *diligence_checks(task),
        {"name": "转换前检查（to_forge）", "result": "passed",
         "detail": f"{conv['trace']['checked']} 个数字换成指标引用或追溯到证据账" + (f"；放行：{'、'.join(conv['trace']['allowed'])}" if conv["trace"]["allowed"] else "")},
        {"name": "A 级卡片出现在正文", "result": "failed" if conv["a_cards"]["missing"] else "passed",
         "detail": ("缺少：" + "、".join(conv["a_cards"]["missing"])) if conv["a_cards"]["missing"] else f"{conv['a_cards']['checked']} 张 A 级卡片都已出现"},
        {"name": "report-forge 正式验收（qa acceptance）", "result": "failed" if audit.get("errors") or not audit.get("acceptance") else "passed",
         "detail": "；".join(audit.get("errors") or [])[:500] or f"{len(audit['rows'])} 页；警告 {len(audit.get('warnings') or [])} 条已在审查中处置"},
        {"name": "report-forge 作者与独立审查（aggregate）", "result": "passed" if review.get("status") == "complete" else "failed",
         "detail": f"审查者：{review.get('reviewer')}"},
        {"name": "report-forge 执行清单", "result": "passed" if all(items.get(k) == "done" for k in ("acceptance", "final-review", "chart-diversity",
                                                                                                   "layout-diversity", "module-fill", "package")) else "failed",
         "detail": "；".join(f"{k}={v}" for k, v in items.items() if k not in ("delivery", "archive"))},
        {"name": "手写文字数字回查", "result": "failed" if trace["untraced"] else "passed",
         "detail": ("；".join(trace["untraced"]) if trace["untraced"] else f"{trace['checked']} 个数字都能追回证据账")[:500]},
    ]
    for c in checks:
        print(f"[{c['result']}] {c['name']}：{c['detail']}")
    slug = a.slug or "main"
    entry = Acceptance(task).record({
        "id": f"report-{slug}", "kind": "report", "title": json.loads((d / "deck-blueprint.json").read_text(encoding="utf-8"))["deck"]["title"],
        "files": [str(f.relative_to(task)) for f in files + notes], "upstream_checks": checks,
        "number_trace": {"checked": conv["trace"]["checked"] + trace["checked"], "untraced": trace["untraced"]}})
    print(f"已交付：{out_dir}")
    print(f"验收状态：{entry['status']}（成品审查员看完页面后，用 tools/acceptance.py review report-{slug} 写入结论）")
    print("实际交给用户后，写 delivery 观察（destination、deliveredAt），用 plan 提交 delivery，再 step archive。")
    return 0 if not any(c["result"] == "failed" for c in checks) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="出正式报告（report-forge）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "refresh"):
        p = sub.add_parser(name)
        p.add_argument("task")
        p.add_argument("--allow", action="append", default=[], help="显式放行的数字（会写进验收记录）")
    p = sub.add_parser("plan")
    p.add_argument("task")
    p.add_argument("item", choices=PLAN_ITEMS)
    p.add_argument("evidence", help="观察文件（放在 forge-work 目录里，格式见引擎执行清单协议）")
    p.add_argument("--reviewer", required=True, help="接收者身份（主笔）")
    p.add_argument("--basis", required=True, help="接收依据：核对了哪些文件、看到了什么")
    p.add_argument("--reason", help="重新提交时的原因")
    p = sub.add_parser("step")
    p.add_argument("task")
    p.add_argument("op")
    p.add_argument("--pages", help="iteration 只查这些页，如 2,5")
    p.add_argument("--reviews", nargs="+", help="aggregate 的审查文件；默认 forge-work/reviews 下的作者稿和独立审查稿")
    p.add_argument("--name", help="package 的文件名；默认报告标题")
    p = sub.add_parser("finish")
    p.add_argument("task")
    p.add_argument("--slug", help="验收条目 report-<slug>，默认 main")
    a = ap.parse_args(argv)
    try:
        return {"init": cmd_init, "refresh": cmd_refresh, "plan": cmd_plan, "step": cmd_step, "finish": cmd_finish}[a.cmd](a)
    except StepError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
