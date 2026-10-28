#!/usr/bin/env python3
"""Initialize, validate, and summarize consulting project quality artifacts."""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib import schema_check


ARTIFACTS = {
    "research-coverage.json": {"version": 1, "subquestions": []},
    "skill-usage-manifest.json": {"version": 1, "skills": []},
    "review-closure.json": {"version": 1, "issues": []},
}
SCHEMAS = {
    "research-coverage.json": "research-coverage.schema.json",
    "skill-usage-manifest.json": "skill-usage.schema.json",
    "review-closure.json": "review-closure.schema.json",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path, value):
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError:
        pass


def init_project(task, depth):
    task.mkdir(parents=True, exist_ok=True)
    write_new(task / "consulting-project.json", {"version": 1, "depth": depth})
    for name, value in ARTIFACTS.items():
        write_new(task / name, value)
    (task / "research-handoffs").mkdir(exist_ok=True)


def load_document(path, code, errors):
    if not path.is_file():
        errors.append((code, f"missing {path.name}"))
        return None
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append((code, f"cannot read {path.name}: {exc}"))
        return None


def validate_project(task):
    errors = []
    config = load_document(task / "consulting-project.json", "PROJECT_CONFIG", errors)
    docs = {}
    for name, schema_name in SCHEMAS.items():
        doc = load_document(task / name, "ARTIFACT_MISSING", errors)
        docs[name] = doc
        if doc is not None:
            for detail in schema_check.check_document(schema_check.load(schema_name), doc):
                errors.append(("SCHEMA_INVALID", f"{name}: {detail}"))

    handoffs = []
    handoffs_by_line = {}
    handoff_dir = task / "research-handoffs"
    for path in sorted(handoff_dir.glob("*.json")) if handoff_dir.is_dir() else []:
        handoff = load_document(path, "HANDOFF_INVALID", errors)
        if handoff is None:
            continue
        handoffs.append(handoff)
        if handoff.get("line_id"):
            handoffs_by_line[handoff["line_id"]] = handoff
        schema_errors = schema_check.check_document(schema_check.load("research-handoff.schema.json"), handoff)
        for detail in schema_errors:
            code = "HANDOFF_DISPOSITION" if "project_manager_disposition" in detail else "SCHEMA_INVALID"
            errors.append((code, f"{path.name}: {detail}"))

    workstreams = {}
    workstream_dir = task / "03r_research" / "tasks"
    for path in sorted(workstream_dir.glob("*.json")) if workstream_dir.is_dir() else []:
        try:
            candidate = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            if re.fullmatch(r"[A-Z]", path.stem):
                errors.append(("WORKSTREAM_INVALID", f"cannot read {path.name}: {exc}"))
            continue
        if candidate.get("kind") != "research_workstream" and not re.fullmatch(r"[A-Z]", path.stem):
            continue
        workstream = candidate
        code = workstream.get("code", path.stem)
        workstreams[code] = workstream
        if workstream is None:
            continue
        status = workstream.get("status")
        if status not in ("accepted", "rejected"):
            errors.append(("WORKSTREAM_OPEN", f"{code} is {status or 'missing status'}"))
        else:
            handoff = handoffs_by_line.get(code)
            if handoff is None:
                errors.append(("WORKSTREAM_HANDOFF_MISSING", f"{code} has terminal metadata without handoff"))
            elif handoff.get("role") != workstream.get("role") or handoff.get("project_manager_disposition") != status:
                errors.append(("WORKSTREAM_MISMATCH", f"{code} metadata and handoff role/disposition differ"))
    for line_id in handoffs_by_line:
        if line_id not in workstreams:
            errors.append(("WORKSTREAM_METADATA_MISSING", f"{line_id} has handoff without metadata"))

    depth = config.get("depth") if isinstance(config, dict) else None
    if depth not in ("L1", "L2", "L3"):
        errors.append(("PROJECT_DEPTH_INVALID", "depth must be L1, L2, or L3"))
    accepted = {code for code, item in workstreams.items()
                if item.get("status") == "accepted" and code in handoffs_by_line
                and handoffs_by_line[code].get("project_manager_disposition") == "accepted"
                and handoffs_by_line[code].get("role") == item.get("role")}
    if depth == "L3" and len(accepted) < 2:
        errors.append(("RESEARCH_LINES_MIN", "L3 requires at least two independent research lines"))

    coverage = docs.get("research-coverage.json")
    if isinstance(coverage, dict):
        for question in coverage.get("subquestions", []):
            if question.get("material_pain"):
                classes = sum(bool(question.get(name)) for name in ("user_voice", "behavioral", "transaction"))
                if classes < 2:
                    errors.append(("PAIN_SIGNAL_CLASSES", f"{question.get('id', '?')} has {classes} signal classes; 2 required"))

    usage = docs.get("skill-usage-manifest.json")
    if isinstance(usage, dict):
        for skill in usage.get("skills", []):
            if skill.get("status") in ("adopted", "downgraded") and not skill.get("outputs"):
                errors.append(("SKILL_OUTPUT_REQUIRED", f"{skill.get('skill', '?')} has no output"))

    reviews = docs.get("review-closure.json")
    if isinstance(reviews, dict):
        for issue in reviews.get("issues", []):
            if issue.get("severity") in ("blocking", "major") and issue.get("status") != "closed":
                errors.append(("REVIEW_OPEN_MAJOR", f"{issue.get('id', '?')} is {issue.get('status', 'open')}"))
            if issue.get("severity") in ("blocking", "major") and issue.get("status") == "closed":
                evidence = issue.get("remedy_evidence")
                valid_evidence = (isinstance(evidence, list) and evidence and
                                  all(isinstance(item, str) and item.strip() for item in evidence))
                if (not isinstance(issue.get("remedy"), str) or not issue["remedy"].strip() or
                        not valid_evidence or not isinstance(issue.get("re_reviewer"), str) or
                        not issue["re_reviewer"].strip()):
                    errors.append(("REVIEW_CLOSURE_INCOMPLETE", f"{issue.get('id', '?')} lacks remedy or re-review evidence"))
    return errors


def summarize(task):
    handoffs = list((task / "research-handoffs").glob("*.json")) if (task / "research-handoffs").is_dir() else []
    coverage = read_json(task / "research-coverage.json")
    usage = read_json(task / "skill-usage-manifest.json")
    reviews = read_json(task / "review-closure.json")
    gaps = [gap for item in coverage.get("subquestions", []) for gap in item.get("unresolved_gaps", [])]
    skills = usage.get("skills", [])
    names = [item.get("skill", "?") for item in skills]
    adopted = [item.get("skill", "?") for item in skills if item.get("status") == "adopted"]
    open_reviews = sum(item.get("status") != "closed" for item in reviews.get("issues", []))
    print(f"Research lines: {len(handoffs)}")
    print("Coverage gaps: " + (", ".join(gaps) if gaps else "none"))
    print("Used skills: " + (", ".join(names) if names else "none"))
    print("Adopted skills: " + (", ".join(adopted) if adopted else "none"))
    print(f"Open reviews: {open_reviews}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("task", type=pathlib.Path)
    init.add_argument("--depth", choices=("L1", "L2", "L3"), required=True)
    for name in ("validate", "summary"):
        command = sub.add_parser(name)
        command.add_argument("task", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.command == "init":
        init_project(args.task, args.depth)
        return 0
    if args.command == "validate":
        errors = validate_project(args.task)
        for code, detail in errors:
            print(f"{code}: {detail}")
        if not errors:
            print("OK")
        return 1 if errors else 0
    try:
        summarize(args.task)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"SUMMARY_INVALID: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
