#!/usr/bin/env python3
"""开放问题研究的工具（设计 §5.1）。证据写进任务文件夹的统一证据账；研究包是封包时从证据账生成的副本。

子命令：
  init     建研究工作区 03r_research/（brief.md、plan.md 取自模板），在 project 表登记研究问题
  resume   断点续跑：列出各研究线下一个来源 ID、记录数和当前检查结果
  capture  采集一个网页、PDF 或本地文件（存原件、写快照、登记来源）；--browser 经本机 Chrome 只读存档
  check    检查任务文件夹或研究包（--final、--write-manifest、--review-digest 只用于研究包；--profile lite 查轻量包）
  seal     封包：--prepare 组装暂存目录并打印内容指纹；人工复核登记后 --publish 发布并生成 ZIP
  lite     L1 留档：在 work/<日期>-<主题>-lite/ 建只含 raw/ 和 answer.md 的轻量包

退出码：check 有错误为 1；capture 访问受限或超限为 2、参数或状态错误为 3；其余失败为 1。
"""
import argparse
import datetime
import json
import os
import pathlib
import re
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
import rcapture  # noqa: E402
import rcheck  # noqa: E402
import rseal  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402
from tools.lib import schema_check  # noqa: E402

TEMPLATES = SKILL_DIR / "assets" / "templates"
WORKSTREAM_CODE = re.compile(r"^[ABD-LN-TV-Z]$")


def _write_json_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _workstream_paths(task, code):
    root = pathlib.Path(task)
    return root / "03r_research" / "tasks" / f"{code}.md", root / "03r_research" / "tasks" / f"{code}.json"


def cmd_workstream_add(a):
    if not WORKSTREAM_CODE.fullmatch(a.code):
        print("研究线代号必须是单个大写字母，且不能使用 C、M、U", file=sys.stderr)
        return 1
    task_file, metadata_file = _workstream_paths(a.task, a.code)
    if task_file.exists() or metadata_file.exists():
        print(f"研究线 {a.code} 已存在", file=sys.stderr)
        return 1
    text = (TEMPLATES / "subagent-task.md").read_text(encoding="utf-8")
    text = text.replace("<代号>", a.code).replace("<主题>", a.question).replace("<角色>", a.role)
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_file.write_text(text, encoding="utf-8")
    _write_json_new(metadata_file, {
        "version": 1, "code": a.code, "role": a.role, "question": a.question,
        "task_file": str(task_file.relative_to(pathlib.Path(a.task))), "status": "awaiting_handoff",
    })
    (pathlib.Path(a.task) / "03_evidence" / "ledger" / "staging" / a.code).mkdir(parents=True, exist_ok=False)
    print(json.dumps({"code": a.code, "task_file": str(task_file), "status": "awaiting_handoff"}, ensure_ascii=False))
    return 0


def _load_workstream(task, code):
    _, metadata_file = _workstream_paths(task, code)
    if not metadata_file.is_file():
        raise ValueError(f"研究线 {code} 不存在")
    return metadata_file, json.loads(metadata_file.read_text(encoding="utf-8"))


def cmd_workstream_handoff(a):
    try:
        metadata_file, metadata = _load_workstream(a.task, a.code)
        handoff = json.loads(pathlib.Path(a.handoff).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as err:
        print(str(err), file=sys.stderr)
        return 1
    if "project_manager_disposition" in handoff:
        print("project_manager_disposition 只能由 workstream decide 写入", file=sys.stderr)
        return 1
    if handoff.get("line_id") != a.code or handoff.get("role") != metadata["role"]:
        print("handoff 的 line_id/role 与研究线不一致", file=sys.stderr)
        return 1
    candidate = dict(handoff, project_manager_disposition="accepted")
    errors = schema_check.check_document(schema_check.load("research-handoff.schema.json"), candidate)
    if errors:
        print("；".join(errors), file=sys.stderr)
        return 1
    destination = pathlib.Path(a.task) / "research-handoffs" / f"{a.code}.json"
    if destination.exists():
        print(f"研究线 {a.code} 已提交 handoff", file=sys.stderr)
        return 1
    _write_json_new(destination, handoff)
    metadata.update({"status": "awaiting_decision", "handoff": str(destination.relative_to(pathlib.Path(a.task)))})
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"code": a.code, "status": "awaiting_decision"}, ensure_ascii=False))
    return 0


def cmd_workstream_decide(a):
    try:
        metadata_file, metadata = _load_workstream(a.task, a.code)
        handoff_path = pathlib.Path(a.task) / "research-handoffs" / f"{a.code}.json"
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as err:
        print(str(err), file=sys.stderr)
        return 1
    handoff["project_manager_disposition"] = a.status
    errors = schema_check.check_document(schema_check.load("research-handoff.schema.json"), handoff)
    if errors:
        print("；".join(errors), file=sys.stderr)
        return 1
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata.update({"status": a.status, "decision_reason": a.reason})
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"code": a.code, "status": a.status, "reason": a.reason}, ensure_ascii=False))
    return 0


def cmd_init(a):
    task = pathlib.Path(a.task)
    led = Ledger(task)
    if not (task / "03_evidence" / "ledger").is_dir():
        led.init()
    rs = task / "03r_research"
    rs.mkdir(parents=True, exist_ok=True)
    for name in ("brief.md", "plan.md"):
        if not (rs / name).exists():
            shutil.copy2(TEMPLATES / name, rs / name)
    proj = led.read("project")
    fields = {"question": a.question, "information_cutoff": datetime.date.today().isoformat()}
    if proj:
        led.patch("project", "project", {k: v for k, v in fields.items() if not proj[0].get(k)})
    else:
        led.add("project", {"id": "project", **fields})
    print(f"已建研究工作区：{rs}（先写 brief.md，定好子问题、数据需求和 data_status、search_status）")
    return 0


def cmd_resume(a):
    task = pathlib.Path(a.task)
    led = Ledger(task)
    sources = led.read("sources")
    lines = sorted({s["id"][0] for s in sources} | {"M"})
    out = {"next_source_ids": {ln: led.next_id("sources", ln) for ln in lines},
           "counts": {t: len(led.read(t)) for t in ("sources", "evidence", "search_log", "claims")}}
    r = rcheck.run(task)
    out["check"] = {"status": r["status"], "errors": len(r["errors"]), "warnings": len(r["warnings"]), "first_errors": r["errors"][:5]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_capture(a):
    try:
        r = rcapture.capture(a.task, a.source, a.slug, line=a.line, sid=a.id, title=a.title, author=a.author, published=a.published,
                             lang=a.lang, tier=a.tier, grade=a.grade, coi=a.coi,
                             subquestions=[x for x in (a.subquestions or "").split(",") if x], supersedes=a.supersedes,
                             archive_url=a.archive_url, rights_note=a.rights_note, access_note=a.access_note, access=a.access,
                             max_bytes=a.max_bytes, max_chars=a.max_extract_chars, browser=a.browser, cdp=a.cdp,
                             respect_robots=a.respect_robots, lite=a.lite)
    except rcapture.CaptureError as e:
        print(json.dumps({"ok": False, "reason": e.reason, **e.extra}, ensure_ascii=False))
        return e.code
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 2


def cmd_check(a):
    if a.review_digest:
        if rcheck.symlinks(a.target):
            print("不允许符号链接", file=sys.stderr)
            return 1
        print(rcheck.digest(a.target))
        return 0
    r = rcheck.run(a.target, final=a.final, write_manifest=a.write_manifest, profile=a.profile)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"状态：{r['status']}")
        print(f"错误 {len(r['errors'])} 个")
        for e in r["errors"]:
            print(f"- {e}")
        print(f"警告 {len(r['warnings'])} 个")
        for w in r["warnings"]:
            print(f"- {w}")
        print(json.dumps(r["stats"], ensure_ascii=False))
        if r["status"] == "PASS_AUTOMATED":
            print("仅自动检查通过，仍须人工复核。")
    return 1 if r["errors"] else 0


def cmd_seal(a):
    try:
        if a.publish:
            r = rseal.publish(a.task, a.publish)
            print(json.dumps({k: v for k, v in r.items() if k != "final"}, ensure_ascii=False, indent=1))
            print("已发布。最终状态以 research check <包目录> --final 为准。")
        else:
            r = rseal.prepare(a.task, slug=a.slug, slim=a.slim, revise_of=a.revise_of)
            print(json.dumps(r, ensure_ascii=False, indent=1))
            print(f"下一步：复核人在 {r['staging']} 上实际复核，在证据账 reviews 表登记 type=research_review、digest={r['digest']}，"
                  f"然后运行 research.py seal {a.task} --publish {r['package_id']}")
    except rseal.SealError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_lite(a):
    root = pathlib.Path(a.root) / "work" / f"{datetime.date.today().isoformat()}-{a.slug}-lite"
    (root / "raw" / "sources").mkdir(parents=True, exist_ok=True)
    if not (root / "answer.md").exists():
        (root / "answer.md").write_text(f"# {a.question}\n\n（简短回答，每个事实后写来源 ID，如 M001）\n", encoding="utf-8")
    print(f"已建轻量包：{root}（用 capture --lite {root} 存来源，写完 answer.md 后 check --profile lite）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="开放问题研究")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("task")
    p.add_argument("--question", required=True)
    sub.add_parser("resume").add_argument("task")
    p = sub.add_parser("capture")
    p.add_argument("task", help="任务文件夹；--lite 时是轻量包目录")
    p.add_argument("source", help="http/https 网址或本地文件")
    p.add_argument("--slug", required=True)
    p.add_argument("--id")
    p.add_argument("--line", default="M")
    p.add_argument("--title")
    p.add_argument("--author")
    p.add_argument("--published")
    p.add_argument("--lang")
    p.add_argument("--tier", default="secondary", choices=rcheck.ENUM["tier"])
    p.add_argument("--grade", default="B", choices=rcheck.ENUM["grade"])
    p.add_argument("--coi")
    p.add_argument("--subquestions")
    p.add_argument("--supersedes")
    p.add_argument("--archive-url")
    p.add_argument("--rights-note")
    p.add_argument("--access-note")
    p.add_argument("--access", choices=rcheck.ENUM["access"], help="手动覆盖完整度（正文仍按上限截断）")
    p.add_argument("--max-bytes", type=int, default=50 * 1024 * 1024)
    p.add_argument("--max-extract-chars", type=int, default=400000)
    p.add_argument("--browser", action="store_true", help="经本机已开的 Chrome 只读打开并存档（不登录）")
    p.add_argument("--cdp", default="http://127.0.0.1:9222")
    p.add_argument("--respect-robots", action="store_true")
    p.add_argument("--lite", action="store_true")
    p = sub.add_parser("check")
    p.add_argument("target")
    p.add_argument("--json", action="store_true")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--final", action="store_true")
    g.add_argument("--write-manifest", action="store_true")
    g.add_argument("--review-digest", action="store_true")
    p.add_argument("--profile", choices=("full", "lite"), default="full")
    p = sub.add_parser("seal")
    p.add_argument("task")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--prepare", action="store_true")
    g.add_argument("--publish", metavar="包ID")
    p.add_argument("--slug")
    p.add_argument("--slim", action="store_true", help="用户明确要求精简时：只收被引用的来源")
    p.add_argument("--revise-of", metavar="旧包ID")
    p = sub.add_parser("lite")
    p.add_argument("root", help="放轻量包的目录（会建在 <root>/work/ 下）")
    p.add_argument("--slug", required=True)
    p.add_argument("--question", required=True)
    p = sub.add_parser("workstream")
    work = p.add_subparsers(dest="workstream_cmd", required=True)
    q = work.add_parser("add")
    q.add_argument("task")
    q.add_argument("code")
    q.add_argument("--role", required=True)
    q.add_argument("--question", required=True)
    q = work.add_parser("handoff")
    q.add_argument("task")
    q.add_argument("code")
    q.add_argument("handoff")
    q = work.add_parser("decide")
    q.add_argument("task")
    q.add_argument("code")
    q.add_argument("--status", choices=("accepted", "needs_revision", "rejected"), required=True)
    q.add_argument("--reason", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "check" and not pathlib.Path(a.target).is_dir():
        ap.error(f"{a.target} 不存在")
    if a.cmd == "workstream":
        return {"add": cmd_workstream_add, "handoff": cmd_workstream_handoff, "decide": cmd_workstream_decide}[a.workstream_cmd](a)
    return {"init": cmd_init, "resume": cmd_resume, "capture": cmd_capture, "check": cmd_check, "seal": cmd_seal, "lite": cmd_lite}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
