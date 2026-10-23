#!/usr/bin/env python3
"""生成四个 Allen 应用共用的支撑文件包，并登记统一验收。

默认只收录可交付的分析、证据账和过程结论；不会收录用户原始附件、网页原件、
引擎工作目录或内部企业储备名单。需要原始材料时必须显式传入 --include-raw。
"""
import argparse
import hashlib
import json
import pathlib
import sys
import zipfile
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.acceptance import Acceptance  # noqa: E402


APP_LABELS = {
    "allen-company": "了解企业",
    "allen-capital": "资本市场对接与表现",
    "allen-ecosystem": "上下游机会",
    "allen-bp-review": "评审 BP",
}

TOP_FILES = (
    "00_brief.md",
    "01_issue-tree.md",
    "02_method-plan.md",
    "05_review-log.md",
    "06_synthesis.md",
)
TREE_ROOTS = (
    "03_evidence/ledger",
    "03r_research",
    "03d_diligence",
    "04_analysis",
    "07_storyline",
)
ALLOWED_SUFFIXES = {".md", ".txt", ".csv", ".json", ".jsonl", ".xlsx"}
PRIVATE_PARTS = {"raw", ".backup", "staging", "internal", "_internal", "private", "forge-work", "poster-work"}
PRIVATE_NAMES = {"candidate-list", "company-reserve", "internal-company-list"}


class PackageError(Exception):
    pass


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_private(rel):
    lowered = {p.lower() for p in rel.parts}
    if lowered & PRIVATE_PARTS:
        return True
    stem = rel.stem.lower()
    return any(token in stem for token in PRIVATE_NAMES)


def select_files(task, include_raw=False):
    selected = []
    for name in TOP_FILES:
        path = task / name
        if path.is_file():
            selected.append(path)
    for root_name in TREE_ROOTS:
        root = task / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            rel = path.relative_to(task)
            if not include_raw and is_private(rel):
                continue
            selected.append(path)
    if include_raw:
        raw = task / "03_evidence" / "raw"
        if raw.is_dir():
            selected.extend(p for p in sorted(raw.rglob("*")) if p.is_file())
    return sorted(set(selected), key=lambda p: p.relative_to(task).as_posix())


def read_app(task):
    run = task / "app-run.json"
    if not run.is_file():
        raise PackageError(f"找不到 {run}，支撑包只用于 Allen 应用任务")
    doc = json.loads(run.read_text(encoding="utf-8"))
    app_id = doc.get("app_id")
    if app_id not in APP_LABELS:
        raise PackageError(f"app-run.json 中的应用无效：{app_id}")
    return app_id, APP_LABELS[app_id]


def build(task_dir, include_raw=False):
    task = pathlib.Path(task_dir).resolve()
    app_id, app_label = read_app(task)
    files = select_files(task, include_raw)
    if not files:
        raise PackageError("没有可打包的支撑文件")

    deliverables = task / "08_deliverables"
    deliverables.mkdir(parents=True, exist_ok=True)
    output = deliverables / "supporting-package.zip"
    tmp = output.with_suffix(".zip.tmp")
    manifest = {
        "version": 1,
        "task": task.name,
        "app_id": app_id,
        "app": app_label,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "includes_raw_materials": include_raw,
        "files": [
            {
                "path": path.relative_to(task).as_posix(),
                "size": path.stat().st_size,
                "sha256": digest(path),
            }
            for path in files
        ],
    }
    readme = (
        f"# {app_label}：支撑文件包\n\n"
        "本包用于复核主报告，包含任务定义、证据账、分析过程和审查记录。\n\n"
        "- 主报告的 PDF 与 HTML 单独交付，不在本包内重复收录。\n"
        f"- 用户原始材料：{'已按显式选项收录' if include_raw else '默认未收录'}。\n"
        "- 内部企业储备名单、候选清单和渲染引擎过程文件不收录。\n"
        "- manifest.json 给出每个文件的 SHA-256，便于核对完整性。\n"
    )
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("supporting-package/README.md", readme)
        archive.writestr(
            "supporting-package/manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
        )
        for path in files:
            rel = path.relative_to(task).as_posix()
            archive.write(path, f"supporting-package/{rel}")
    tmp.replace(output)

    entry = Acceptance(task).record(
        {
            "id": "support-" + app_id.removeprefix("allen-"),
            "kind": "support_package",
            "title": f"{app_label}支撑文件包",
            "files": ["08_deliverables/supporting-package.zip"],
            "upstream_checks": [
                {"name": "support manifest", "result": "passed", "detail": f"已登记 {len(files)} 个支撑文件"},
                {"name": "raw material policy", "result": "passed", "detail": "原始材料按显式选项处理"},
            ],
            "number_trace": {"checked": 0, "untraced": []},
        }
    )
    return {"output": str(output), "files": len(files), "acceptance_id": entry["id"], "status": entry["status"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成 Allen 应用的支撑文件包")
    parser.add_argument("task")
    parser.add_argument("--include-raw", action="store_true", help="把用户原件和网页原件加入支撑包")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.task, args.include_raw), ensure_ascii=False, indent=1))
        return 0
    except (PackageError, OSError, ValueError, zipfile.BadZipFile) as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
