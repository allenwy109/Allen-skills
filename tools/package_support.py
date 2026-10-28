#!/usr/bin/env python3
"""生成 Allen 应用共用的支撑文件包，并登记统一验收。

默认只收录可交付的分析、证据账和过程结论；不会收录用户原始附件、网页原件、
引擎工作目录或内部企业储备名单。需要原始材料时必须显式传入 --include-raw。
"""
import argparse
import hashlib
import json
import pathlib
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.acceptance import Acceptance  # noqa: E402


APP_LABELS = {
    "allen-idea": "创业点子评估",
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
    "03_evidence",
    "03r_research",
    "03d_diligence",
    "04_analysis",
    "05_reviews",
    "07_storyline",
)
ALLOWED_SUFFIXES = {".md", ".txt", ".csv", ".json", ".jsonl", ".xlsx", ".pdf"}
PRIVATE_PARTS = {".backup", "staging", "internal", "_internal", "private", "forge-work", "poster-work",
                 "build", "node_modules", "__pycache__", ".cache"}
PRIVATE_NAMES = {"candidate-list", "company-reserve", "internal-company-list"}
AUDIT_FILES = (
    "07_storyline/a4-work/coverage-manifest.json",
    "07_storyline/a4-work/artifact-manifest.json",
    "07_storyline/a4-work/visual-regression.json",
    "07_storyline/a4-work/qa-evidence.json",
    "07_storyline/a4-work/qa-result.json",
    "07_storyline/a4-work/author-review.json",
    "07_storyline/a4-work/independent-review.json",
    "07_storyline/a4-work/build/pagination-manifest.json",
    "07_storyline/a4-work/build/geometry-manifest.json",
    "07_storyline/a4-work/build/media-manifest.json",
    "07_storyline/a4-work/build/visual-candidate.json",
)


class PackageError(Exception):
    pass


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_private(rel, include_raw=False):
    lowered = {p.lower() for p in rel.parts}
    if lowered & PRIVATE_PARTS:
        return True
    if "raw" in lowered and "sources" not in lowered and not include_raw:
        return True
    stem = rel.stem.lower()
    return any(token in stem for token in PRIVATE_NAMES)


def _require_safe(task, path):
    path = pathlib.Path(path)
    if path.is_symlink():
        raise PackageError(f"证据包拒绝符号链接：{path.relative_to(task)}")
    resolved = path.resolve()
    if resolved != task and task not in resolved.parents:
        raise PackageError(f"证据包路径越出任务目录：{path}")
    relative = path.relative_to(task)
    current = task
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise PackageError(f"证据包拒绝符号链接：{relative}")


def select_files(task, include_raw=False):
    selected = []
    for name in TOP_FILES:
        path = task / name
        if path.is_file():
            _require_safe(task, path)
            selected.append(path)
    for root_name in TREE_ROOTS:
        root = task / root_name
        if not root.is_dir():
            continue
        _require_safe(task, root)
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise PackageError(f"证据包拒绝符号链接：{path.relative_to(task)}")
            if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            _require_safe(task, path)
            rel = path.relative_to(task)
            if is_private(rel, include_raw):
                continue
            selected.append(path)
    if include_raw:
        raw = task / "03_evidence" / "raw"
        if raw.is_dir():
            for path in sorted(raw.rglob("*")):
                if path.is_symlink():
                    raise PackageError(f"证据包拒绝符号链接：{path.relative_to(task)}")
                if path.is_file():
                    _require_safe(task, path)
                    selected.append(path)
    for name in AUDIT_FILES:
        path = task / name
        if path.is_symlink():
            raise PackageError(f"证据包拒绝符号链接：{name}")
        if path.is_file():
            _require_safe(task, path)
            selected.append(path)
    return sorted(set(selected), key=lambda p: p.relative_to(task).as_posix())


def read_app(task, required=True):
    run = task / "app-run.json"
    if not run.is_file():
        if not required:
            return "report", "正式报告"
        raise PackageError(f"找不到 {run}，支撑包只用于 Allen 应用任务")
    doc = json.loads(run.read_text(encoding="utf-8"))
    app_id = doc.get("app_id")
    if app_id not in APP_LABELS:
        raise PackageError(f"app-run.json 中的应用无效：{app_id}")
    return app_id, APP_LABELS[app_id]


def _source_index(task):
    sources = task / "03_evidence" / "ledger" / "sources.jsonl"
    rows = ["# Source index", "", "| Source ID | Title | Snapshot |", "|---|---|---|"]
    if sources.is_file():
        for line in sources.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            source = json.loads(line)
            rows.append(f"| {source.get('id', '')} | {source.get('title', '')} | {source.get('snapshot', '')} |")
    return "\n".join(rows) + "\n"


def verify(package_dir):
    package = pathlib.Path(package_dir).resolve()
    checksum = package / "checksums-sha256.txt"
    if not checksum.is_file():
        raise PackageError("缺少 checksums-sha256.txt")
    lines = checksum.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise PackageError("checksums-sha256.txt 为空")
    recorded = {}
    for line in lines:
        try:
            expected, rel = line.split("  ", 1)
        except ValueError as error:
            raise PackageError("checksums-sha256.txt 格式无效") from error
        if rel in recorded:
            raise PackageError(f"重复校验路径：{rel}")
        recorded[rel] = expected
        path = (package / rel).resolve()
        if package not in path.parents:
            raise PackageError(f"校验路径越界：{rel}")
        if not path.is_file() or digest(path) != expected:
            raise PackageError(f"校验失败：{rel}")
    actual = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()}
    expected_actual = set(recorded) | {"checksums-sha256.txt"}
    if actual != expected_actual:
        raise PackageError("包内文件与 checksums-sha256.txt 不一致")
    manifest = json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise PackageError("package-manifest.json 没有文件记录")
    manifest_paths = [item.get("path") for item in entries]
    if len(manifest_paths) != len(set(manifest_paths)) or any(not path for path in manifest_paths):
        raise PackageError("package-manifest.json 路径重复或为空")
    generated = {"README.md", "source-index.md", "package-manifest.json"}
    if set(manifest_paths) != set(recorded) - generated:
        raise PackageError("package-manifest.json 与校验清单不一致")
    for item in entries:
        path = package / item["path"]
        if item.get("size") != path.stat().st_size or item.get("sha256") != digest(path):
            raise PackageError(f"package-manifest.json 文件记录不一致：{item['path']}")
    return {"package": str(package), "verified": True}


def build(task_dir, include_raw=False, require_app=True, output_root=None, record_acceptance=True):
    task = pathlib.Path(task_dir).resolve()
    app_id, app_label = read_app(task, require_app)
    if not (task / "03_evidence" / "ledger" / "sources.jsonl").is_file():
        raise PackageError("证据包缺少 03_evidence/ledger/sources.jsonl")
    files = select_files(task, include_raw)
    if not files:
        raise PackageError("没有可打包的支撑文件")

    deliverables = pathlib.Path(output_root).resolve() if output_root else task / "08_deliverables"
    deliverables.mkdir(parents=True, exist_ok=True)
    output = deliverables / "evidence-package.zip"
    destination = deliverables / "evidence-package"
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
        "- package-manifest.json 登记源文件，checksums-sha256.txt 用于核对包内完整性。\n"
    )
    with tempfile.TemporaryDirectory(dir=deliverables) as temporary:
        package = pathlib.Path(temporary) / "evidence-package"
        package.mkdir()
        (package / "README.md").write_text(readme, encoding="utf-8")
        (package / "source-index.md").write_text(_source_index(task), encoding="utf-8")
        (package / "package-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for path in files:
            rel = path.relative_to(task).as_posix()
            target = package / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        checksummed = sorted(path for path in package.rglob("*") if path.is_file())
        (package / "checksums-sha256.txt").write_text(
            "".join(f"{digest(path)}  {path.relative_to(package).as_posix()}\n" for path in checksummed), encoding="utf-8")
        verify(package)
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(package, destination)
    tmp = output.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                archive.write(path, f"evidence-package/{path.relative_to(destination).as_posix()}")
    tmp.replace(output)

    record = {
        "id": "evidence-" + app_id.removeprefix("allen-"),
        "kind": "support_package",
        "title": f"{app_label}证据包",
        "files": ["08_deliverables/evidence-package.zip"],
        "upstream_checks": [
            {"name": "support manifest", "result": "passed", "detail": f"已登记 {len(files)} 个支撑文件"},
            {"name": "raw material policy", "result": "passed", "detail": "原始材料按显式选项处理"},
        ],
        "number_trace": {"checked": 0, "untraced": []},
    }
    entry = Acceptance(task).record(record) if record_acceptance else {"id": record["id"], "status": "staged"}
    return {"output": str(output), "directory": str(destination), "files": len(files),
            "acceptance_id": entry["id"], "status": entry["status"], "acceptance_record": record}


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成 Allen 应用的证据包")
    parser.add_argument("task", nargs="?")
    parser.add_argument("--verify")
    parser.add_argument("--include-raw", action="store_true", help="把用户原件和网页原件加入支撑包")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            print(json.dumps(verify(args.verify), ensure_ascii=False, indent=1))
            return 0
        if not args.task:
            parser.error("task is required unless --verify is used")
        print(json.dumps(build(args.task, args.include_raw), ensure_ascii=False, indent=1))
        return 0
    except (PackageError, OSError, ValueError, zipfile.BadZipFile) as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
