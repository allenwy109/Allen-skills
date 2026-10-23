#!/usr/bin/env python3
"""Allen 四个应用入口的运行状态机。

用法：
  app_runtime.py init <任务目录> --app allen-company --request "..." [--file PATH] [--url URL] [--depth L2]
  app_runtime.py next <任务目录>
  app_runtime.py advance <任务目录> [--stage STAGE]
  app_runtime.py wait <任务目录> --reason "..."
  app_runtime.py block <任务目录> --reason "..."
  app_runtime.py resume <任务目录>
  app_runtime.py finish <任务目录>

它不替模型写分析，只负责锁定应用、给出下一阶段、检查产物并阻止提前结束。
"""
import argparse
import datetime as dt
import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.acceptance import Acceptance  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

RUN_FILE = "app-run.json"

APPS = {
    "allen-company": {"title": "了解企业", "scene": "scene-company", "report": "企业全景评估报告"},
    "allen-capital": {"title": "资本市场对接与表现", "scene": "scene-company", "report": "资本对接与参与判断报告"},
    "allen-ecosystem": {"title": "上下游机会", "scene": "scene-company", "report": "产业协同与上下游机会报告"},
    "allen-bp-review": {"title": "评审 BP", "scene": "scene-bp-review", "report": "BP 评审与修改建议报告"},
}

STAGES = {
    "intake": {"skill": "core-intake", "required": ["00_brief.md", "03_evidence/ledger/project.jsonl"]},
    "framing": {"skill": "core-framing", "required": ["01_issue-tree.md"]},
    "evidence": {"skill": "core-evidence", "required": ["03_evidence/ledger/sources.jsonl", "03_evidence/ledger/claims.jsonl"]},
    "method": {"skill": "core-method-select", "required": ["02_method-plan.md"]},
    "analysis": {"skill": None, "required": ["04_analysis/*.md"]},
    "review": {"skill": "core-review", "required": ["05_review-log.md"]},
    "synthesis": {"skill": "core-synthesis", "required": ["06_synthesis.md"]},
    "storyline": {"skill": "core-storyline", "required": ["07_storyline/slides.json"]},
    "report": {"skill": "out-report", "required": ["08_deliverables/report/*.pdf", "08_deliverables/report/*.html"]},
    "support": {"skill": "tools/package_support.py", "required": ["08_deliverables/supporting-package.zip"]},
    "acceptance": {"skill": "tools/acceptance.py", "required": ["08_deliverables/acceptance.json"]},
}

COMPANY_ORDER = ["intake", "framing", "evidence", "method", "analysis", "review", "synthesis", "storyline", "report", "support", "acceptance"]
BP_ORDER = ["intake", "evidence", "framing", "method", "analysis", "review", "synthesis", "storyline", "report", "support", "acceptance"]


class AppError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def run_path(task):
    return pathlib.Path(task) / RUN_FILE


def load(task):
    p = run_path(task)
    if not p.is_file():
        raise AppError(f"找不到 {p}，先运行 init")
    return json.loads(p.read_text(encoding="utf-8"))


def save(task, doc):
    doc["updated_at"] = now()
    p = run_path(task)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def patterns_for(task, run, stage):
    patterns = list(STAGES[stage]["required"])
    if stage == "intake":
        if run["inputs"]["files"]:
            patterns.append("03_evidence/ledger/sources.jsonl")
    return patterns


def matches(task, pattern):
    task = pathlib.Path(task)
    found = [pathlib.Path(p) for p in glob.glob(str(task / pattern), recursive=True)]
    return [p for p in found if p.is_file() and (p.stat().st_size > 0 or p.suffix == ".jsonl")]


def validate_stage(task, run, stage):
    missing = [p for p in patterns_for(task, run, stage) if not matches(task, p)]
    if stage == "acceptance" and not missing:
        doc = Acceptance(task).check()
        kinds = {d["kind"]: d for d in doc.get("deliverables", [])}
        for kind in ("report", "support_package"):
            item = kinds.get(kind)
            if not item:
                missing.append(f"acceptance:kind={kind}")
            elif item.get("status") == "failed":
                missing.append(f"acceptance:{item['id']}=failed")
    return missing


def stage_payload(task, run):
    if run["cursor"] >= len(run["stages"]):
        return {"status": run["status"], "next": None}
    stage = run["stages"][run["cursor"]]
    spec = STAGES[stage]
    skill = spec["skill"]
    if stage == "analysis":
        skill = APPS[run["app_id"]]["scene"]
    skill_file = None
    if skill and not skill.startswith("tools/"):
        skill_file = str(ROOT / skill / "SKILL.md")
    elif skill:
        skill_file = str(ROOT / skill)
    return {
        "status": run["status"],
        "app_id": run["app_id"],
        "stage": stage,
        "skill": skill,
        "skill_file": skill_file,
        "required_outputs": patterns_for(task, run, stage),
        "completed_stages": run["completed_stages"],
    }


def init_task(args):
    if args.app not in APPS:
        raise AppError("未知应用：" + args.app)
    task = pathlib.Path(args.task).resolve()
    if run_path(task).exists():
        raise AppError(f"任务已存在：{run_path(task)}")
    task.mkdir(parents=True, exist_ok=True)
    for d in ("03_evidence", "04_analysis", "07_storyline", "08_deliverables"):
        (task / d).mkdir(exist_ok=True)
    request = pathlib.Path(args.request_file).read_text(encoding="utf-8") if args.request_file else args.request
    request = request or ""
    info = APPS[args.app]
    brief = (f"# 任务单\n\n- 日期：{dt.date.today().isoformat()}\n- 应用：{info['title']}（{args.app}）\n"
             f"- 场景：{info['scene']}\n- 投入深度：{args.depth}\n- 交付物：主报告（PDF + HTML）+ 支撑文件包（ZIP）\n"
             f"- 用户文件：{'、'.join(args.file) if args.file else '无'}\n- 用户网址：{'、'.join(args.url) if args.url else '无'}\n\n"
             "## 用户要求（原文）\n\n" + request + "\n")
    (task / "00_brief.md").write_text(brief, encoding="utf-8")
    Ledger(task).init()
    order = BP_ORDER if args.app == "allen-bp-review" else COMPANY_ORDER
    run = {
        "version": 1,
        "run_id": task.name,
        "app_id": args.app,
        "title": info["title"],
        "scene": info["scene"],
        "depth": args.depth,
        "status": "running",
        "cursor": 0,
        "stages": order,
        "completed_stages": [],
        "inputs": {"files": list(args.file), "urls": list(args.url)},
        "wait_reason": None,
        "block_reason": None,
        "created_at": now(),
    }
    save(task, run)
    return stage_payload(task, run)


def advance(task, requested=None):
    run = load(task)
    if run["status"] != "running":
        raise AppError(f"当前状态 {run['status']} 不能推进")
    payload = stage_payload(task, run)
    stage = payload["stage"]
    if stage is None:
        raise AppError("没有待推进阶段，请运行 finish")
    if requested and requested != stage:
        raise AppError(f"当前阶段是 {stage}，不能推进 {requested}")
    missing = validate_stage(task, run, stage)
    if missing:
        return {**payload, "validation": "failed", "missing": missing}
    run["completed_stages"].append(stage)
    run["cursor"] += 1
    save(task, run)
    return {"advanced": stage, **stage_payload(task, run)}


def set_state(task, status, reason):
    run = load(task)
    run["status"] = status
    if status == "waiting_user":
        run["wait_reason"] = reason
    else:
        run["block_reason"] = reason
    save(task, run)
    return stage_payload(task, run) | {"reason": reason}


def resume(task):
    run = load(task)
    if run["status"] in ("waiting_user", "blocked"):
        run["status"] = "running"
        save(task, run)
    return stage_payload(task, run)


def finish(task):
    run = load(task)
    if run["cursor"] != len(run["stages"]):
        p = stage_payload(task, run)
        raise AppError(f"任务尚未完成，当前阶段：{p['stage']}")
    doc = Acceptance(task).check()
    failed = [d["id"] for d in doc.get("deliverables", []) if d["status"] == "failed"]
    if failed:
        raise AppError("仍有验收失败的交付物：" + "、".join(failed))
    run["status"] = "completed"
    run["completed_at"] = now()
    run["conditions"] = [c for d in doc.get("deliverables", []) for c in d.get("conditions", [])]
    save(task, run)
    return {"status": "completed", "app_id": run["app_id"], "conditions": run["conditions"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Allen 应用入口运行状态机")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("task")
    p.add_argument("--app", choices=sorted(APPS), required=True)
    p.add_argument("--request", default="")
    p.add_argument("--request-file")
    p.add_argument("--file", action="append", default=[])
    p.add_argument("--url", action="append", default=[])
    p.add_argument("--depth", choices=("L1", "L2", "L3"), default="L2")
    for name in ("next", "resume", "finish"):
        q = sub.add_parser(name)
        q.add_argument("task")
    p = sub.add_parser("advance")
    p.add_argument("task")
    p.add_argument("--stage")
    for name in ("wait", "block"):
        q = sub.add_parser(name)
        q.add_argument("task")
        q.add_argument("--reason", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "init":
            out = init_task(a)
        elif a.cmd == "next":
            out = stage_payload(a.task, load(a.task))
        elif a.cmd == "advance":
            out = advance(a.task, a.stage)
        elif a.cmd == "wait":
            out = set_state(a.task, "waiting_user", a.reason)
        elif a.cmd == "block":
            out = set_state(a.task, "blocked", a.reason)
        elif a.cmd == "resume":
            out = resume(a.task)
        else:
            out = finish(a.task)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1 if out.get("validation") == "failed" else 0
    except (AppError, OSError, ValueError) as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

