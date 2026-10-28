#!/usr/bin/env python3
"""交付物验收记录（设计 §8.3）。只有 08_deliverables/acceptance.json 能判定"已完成"。

用法（任务文件夹下的路径都写相对任务文件夹的路径）：
  python3 tools/acceptance.py <任务文件夹> record <条目.json>     登记或更新一个交付物（自动计算文件哈希和状态）
  python3 tools/acceptance.py <任务文件夹> review <交付物ID> <审查.json>   写入成品审查员的结论
  python3 tools/acceptance.py <任务文件夹> fixture true|false    标记是否为测试夹具（只有夹具允许 skipped）
  python3 tools/acceptance.py <任务文件夹> check [--json]        重新计算全部状态（含文件是否被改动）
check：有任何交付物为 failed 时以 1 退出；conditional 以 0 退出，但必须把条件告诉用户。

状态规则（全文只有这一套）：
  failed       任一前置检查失败；非夹具出现 skipped；有追溯不到的数字；有未解决的阻塞问题；
               还没有成品审查；验收后文件被改动
  conditional  不是 failed，但有：未解决的重要问题、未处置的警告、有限完成（limited）、
               降级为 Markdown 交付、只有作者自审（未经独立审查）
  passed       其余情况
"""
import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.lib import schema_check  # noqa: E402

SCHEMA = schema_check.load("acceptance.schema.json")


class AcceptanceError(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compute_status(entry, fixture, task=None):
    """返回 (状态, 失败原因, 条件)。task 不为空时还会核对文件哈希。"""
    failures, conditions = [], []
    dispositions = {d["source"] for d in entry.get("dispositions") or []}
    for c in entry.get("upstream_checks") or []:
        r, label = c["result"], f"{c['name']}" + (f"：{c['detail']}" if c.get("detail") else "")
        if r == "failed":
            failures.append(f"前置检查失败：{label}")
        elif r == "skipped" and not fixture:
            failures.append(f"正式任务不允许跳过检查：{label}")
        elif r == "warnings" and c["name"] not in dispositions:
            conditions.append(f"有未处置的警告：{label}")
        elif r == "limited":
            conditions.append(f"有限完成：{label}")
    untraced = (entry.get("number_trace") or {}).get("untraced") or []
    if untraced:
        failures.append(f"有 {len(untraced)} 个数字追溯不到证据账：{'、'.join(untraced[:5])}")
    reviewer = entry.get("reviewer")
    if not reviewer:
        failures.append("尚未经过成品审查")
    else:
        for i in reviewer.get("issues") or []:
            if i["resolved"]:
                if entry.get("kind") == "report" and i["level"] in ("blocking", "major"):
                    re_review = i.get("re_review") or {}
                    if (not str(i.get("remedy") or "").strip() or not i.get("remedy_evidence")
                            or not str(re_review.get("reviewer") or "").strip()
                            or not str(re_review.get("at") or "").strip()
                            or not _digest(re_review.get("digest"))):
                        failures.append(f"已解决的{i['level']}问题 {i['id']} 缺少补救证据和一次复审")
                continue
            if i["level"] == "blocking":
                failures.append(f"未解决的阻塞问题 {i['id']}：{i['text']}")
            elif i["level"] == "major":
                target = failures if entry.get("kind") == "report" else conditions
                target.append(f"未解决的重要问题 {i['id']}：{i['text']}")
        if reviewer["type"] == "self":
            conditions.append("未经独立审查（只有作者按清单自审）")
        elif entry.get("kind") == "report":
            failures.extend(_report_review_failures(reviewer))
    if entry.get("downgraded"):
        conditions.append("未出正式成品，降级为 Markdown 交付")
    if task is not None:
        for f in entry.get("files") or []:
            p = pathlib.Path(task) / f["path"]
            if not p.is_file():
                failures.append(f"文件不存在：{f['path']}")
            elif sha256(p) != f["sha256"]:
                failures.append(f"验收后文件被改动：{f['path']}")
    status = "failed" if failures else ("conditional" if conditions else "passed")
    return status, failures, conditions


EXECUTIVE_QUESTIONS = {
    "answer_visibility", "executive_summary", "argument_sufficiency",
    "actions", "ownership", "continue_stop_thresholds",
}


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _report_review_failures(reviewer):
    failures = []
    author = str(reviewer.get("author") or "").strip()
    visual = str(reviewer.get("reviewer") or "").strip()
    if reviewer.get("role") != "visual-design-reviewer" or not _digest(reviewer.get("review_digest")):
        failures.append("视觉审查缺少独立角色身份或审查摘要")
    worst = reviewer.get("worst_page") or {}
    if not str(worst.get("page_id") or "").strip() or not str(worst.get("finding") or "").strip():
        failures.append("视觉审查缺少最差页评估")
    decision = reviewer.get("decision_review") or {}
    decision_name = str(decision.get("reviewer") or "").strip()
    answers = decision.get("answers") or {}
    if (decision.get("role") != "decision-maker-reviewer" or not _digest(decision.get("review_digest"))
            or set(answers) != EXECUTIVE_QUESTIONS
            or any(not str(answers[key]).strip() for key in EXECUTIVE_QUESTIONS)):
        failures.append("决策者审查未回答六个高管问题或缺少独立角色身份和审查摘要")
    if author and author in {visual, decision_name}:
        failures.append("独立审查者与作者不能相同")
    if visual and visual == decision_name:
        failures.append("视觉与决策审查者必须独立")
    return failures


class Acceptance:
    def __init__(self, task):
        self.task = pathlib.Path(task)
        self.path = self.task / "08_deliverables" / "acceptance.json"

    def load(self):
        if not self.path.is_file():
            return {"task": self.task.name, "fixture": False, "updated_at": now(), "deliverables": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, doc):
        doc["updated_at"] = now()
        errors = schema_check.check_document(SCHEMA, doc)
        if errors:
            raise AcceptanceError("；".join(errors))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def _finish(self, entry, fixture):
        entry["status"], entry["failures"], entry["conditions"] = compute_status(entry, fixture, self.task)
        return entry

    def record(self, entry):
        doc = self.load()
        entry = dict(entry)
        files = []
        for f in entry.get("files") or []:
            path = f["path"] if isinstance(f, dict) else f
            p = self.task / path
            if not p.is_file():
                raise AcceptanceError(f"交付物文件不存在：{path}")
            files.append({"path": path, "sha256": sha256(p)})
        entry["files"] = files
        old = next((d for d in doc["deliverables"] if d["id"] == entry.get("id")), None)
        if old and old.get("reviewer") and not entry.get("reviewer"):
            if [f["sha256"] for f in old["files"]] == [f["sha256"] for f in files]:
                entry["reviewer"] = old["reviewer"]   # 文件没变，沿用已有审查；文件变了就要重新审查
        entry.setdefault("upstream_checks", [])
        entry.setdefault("number_trace", {"checked": 0, "untraced": []})
        self._finish(entry, doc["fixture"])
        doc["deliverables"] = [d for d in doc["deliverables"] if d["id"] != entry.get("id")] + [entry]
        self.save(doc)
        return entry

    def review(self, did, reviewer):
        doc = self.load()
        entry = next((d for d in doc["deliverables"] if d["id"] == did), None)
        if not entry:
            raise AcceptanceError(f"没有交付物 {did}")
        entry["reviewer"] = reviewer
        self._finish(entry, doc["fixture"])
        self.save(doc)
        return entry

    def set_fixture(self, value):
        doc = self.load()
        doc["fixture"] = value
        for e in doc["deliverables"]:
            self._finish(e, value)
        self.save(doc)

    def check(self):
        doc = self.load()
        for e in doc["deliverables"]:
            self._finish(e, doc["fixture"])
        if doc["deliverables"]:
            self.save(doc)
        return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description="交付物验收记录")
    ap.add_argument("task")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("entry")
    v = sub.add_parser("review")
    v.add_argument("deliverable")
    v.add_argument("review")
    f = sub.add_parser("fixture")
    f.add_argument("value", choices=["true", "false"])
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    acc = Acceptance(a.task)
    labels = SCHEMA["enums"]["status"]["labels"]
    try:
        if a.cmd == "record":
            e = acc.record(json.loads(pathlib.Path(a.entry).read_text(encoding="utf-8")))
            print(f"{e['id']}：{labels[e['status']]}")
        elif a.cmd == "review":
            e = acc.review(a.deliverable, json.loads(pathlib.Path(a.review).read_text(encoding="utf-8")))
            print(f"{e['id']}：{labels[e['status']]}")
        elif a.cmd == "fixture":
            acc.set_fixture(a.value == "true")
        elif a.cmd == "check":
            doc = acc.check()
            if a.json:
                print(json.dumps(doc, ensure_ascii=False, indent=1))
            else:
                for e in doc["deliverables"]:
                    print(f"[{labels[e['status']]}] {e['id']}（{e['title']}）")
                    for x in e["failures"]:
                        print(f"    不通过原因：{x}")
                    for x in e["conditions"]:
                        print(f"    条件：{x}")
            return 1 if any(e["status"] == "failed" for e in doc["deliverables"]) else 0
    except (AcceptanceError, ValueError, OSError) as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
