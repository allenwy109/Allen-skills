#!/usr/bin/env python3
"""Build, review, and package deterministic A4 reports from storyline contracts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import datetime
import tempfile
import zipfile

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
A4_DIR = SKILL_DIR / "scripts" / "a4"


def _bootstrap():
    local_root = SKILL_DIR.parent
    if (local_root / "tools/lib/runtime.py").is_file():
        sys.path.insert(0, str(local_root))
        sys.path.insert(0, str(A4_DIR))
        return
    for candidate in (os.environ.get("ALLEN_RUNTIME"), SKILL_DIR.parent / "_allen-runtime", SKILL_DIR.parent):
        if candidate and (pathlib.Path(candidate) / "tools/lib/runtime.py").is_file():
            sys.path.insert(0, str(pathlib.Path(candidate)))
            sys.path.insert(0, str(A4_DIR))
            return
    raise SystemExit("找不到运行时（tools/lib），请先运行 ./install.sh")


_bootstrap()
from tools.acceptance import Acceptance  # noqa: E402
from tools import package_support  # noqa: E402
from tools.bridge import to_forge, to_report  # noqa: E402
from tools.lib import runtime  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402
from visual_regression import compare_manifests  # noqa: E402


class StepError(Exception):
    pass


def story_dir(task):
    return pathlib.Path(task).resolve() / "07_storyline"


def work_dir(task):
    return story_dir(task) / "a4-work"


def client_report_dir(task, for_write=True):
    """Use the new delivery path, while allowing legacy reports to be read in place."""
    deliverables = pathlib.Path(task).resolve() / "08_deliverables"
    current = deliverables / "client-report"
    legacy = deliverables / "report"
    return current if for_write or current.exists() or not legacy.exists() else legacy


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def structured_digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def load_story(task):
    story = story_dir(task)
    slides = read_json(story / "slides.json")
    sidecar = read_json(story / "sidecar.json") if (story / "sidecar.json").is_file() else None
    return slides, sidecar


def run(command, *, input_text=None):
    env = dict(os.environ)
    env.setdefault("ALLEN_RUNTIME", str(runtime.runtime_root(skill_dir=SKILL_DIR)))
    result = subprocess.run([str(item) for item in command], input=input_text, capture_output=True, text=True, env=env)
    if result.returncode:
        raise StepError((result.stderr or result.stdout).strip()[-3000:])
    return result


def report_problem(error):
    code = getattr(error, "code", "REPORT_CONVERSION_FAILED")
    details = getattr(error, "problems", [str(error)])
    print(f"{code}: " + "；".join(details), file=sys.stderr)
    return 1


def _component_for_block(block, section, index, report, metrics):
    block = json.loads(json.dumps(block, ensure_ascii=False))
    displays = []
    for metric_id in block["metric_refs"]:
        metric = metrics.get(metric_id, {})
        if metric.get("status") != "present" or "value" not in metric:
            continue
        value = metric["value"]
        decimals = metric.get("decimals")
        if isinstance(value, (int, float)) and isinstance(decimals, int):
            value = f"{value:.{decimals}f}"
        displays.append(f"{value} {metric.get('unit', '')}".strip())
    if displays:
        block["content"]["visual"] = "、".join(displays)
    base = {"id": f"{section['id']}-item-{index:02d}", "title": block["content"]["title"], "blocks": [block]}
    source_groups = [{"source_id": binding["source_id"], "locators": binding["locators"]}
                     for binding in block["source_bindings"]]
    semantic_type = block["content"].get("semantic_type")
    if semantic_type == "pain-demand" and block["content"].get("pain_groups"):
        return {"kind": "pain-demand", "payload": {**base, "layout_id": "full-evidence",
                                                          "pain_groups": block["content"]["pain_groups"]}}
    if semantic_type == "competition" and block["content"].get("comparison"):
        comparison = block["content"]["comparison"]
        return {"kind": "comparison", "payload": {**base, "layout_id": "comparison-columns",
                                                         "criteria": comparison["criteria"],
                                                         "alternatives": comparison["alternatives"]}}
    if block["kind"] == "chart":
        return {"kind": "data-chart", "payload": {**base, "layout_id": "full-evidence", "unit": block["content"].get("subtitle") or "见来源口径",
                                                        "period": report["metadata"].get("date") or "报告期", "items": [block["id"]]}}
    if block["kind"] == "metric":
        return {"kind": "executive-summary", "payload": {**base, "layout_id": "overview-detail", "answers": [block["content"]["purpose"]],
                                                               "summary_items": [{"text": block["id"], "qualification": block["content"].get("subtitle") or "以来源口径为准"}]}}
    return {"kind": "claim-evidence", "payload": {**base, "layout_id": "full-evidence", "claim": block["content"]["purpose"],
                                                          "evidence_groups": source_groups}}


def render_document(report, task):
    metrics = {item["id"]: item for item in Ledger(task).read("metrics")}
    claims = {item["id"]: item for item in Ledger(task).read("claims")}
    answer_claims = [claims[claim_id] for claim_id in report["executive_summary"]["answer_claim_refs"] if claim_id in claims]
    summary_items = [{
        "text": claim["statement"], "identity": claim["kind"], "confidence": claim["confidence"],
        "qualification": claim.get("limitation") or claim.get("scope") or "以正文证据与限制为准",
    } for claim in answer_claims[:4]]
    if len(summary_items) == 1:
        claim = answer_claims[0]
        summary_items.append({
            "text": f"适用范围：{claim.get('population') or claim.get('scope') or '未限定'}",
            "identity": "qualification", "confidence": claim["confidence"],
            "qualification": claim.get("limitation") or "需要结合正文边界判断",
        })
    answer = answer_claims[0]["statement"] if answer_claims else report["executive_summary"].get("question", "")
    components = [
        {"kind": "cover", "payload": {"id": "cover", "title": report["metadata"]["title"], "layout_id": "overview-detail",
                                         "title_groups": [{"title": report["metadata"]["title"]}], "blocks": []}},
        {"kind": "toc", "payload": {"id": "toc", "title": "目录", "layout_id": "full-evidence", "blocks": [],
                                       "entries": [{"title": section["title"], "destination": f"chapter-{index:02d}"}
                                                   for index, section in enumerate(report["sections"], 1)]}},
        {"kind": "executive-summary", "payload": {"id": "executive-summary", "title": "执行摘要", "layout_id": "overview-detail", "blocks": [],
                                                     "answers": [answer] if answer else [],
                                                     "summary_items": summary_items}},
    ]
    for section_index, section in enumerate(report["sections"], 1):
        chapter_id = f"chapter-{section_index:02d}"
        components.append({"kind": "section-title", "payload": {"id": chapter_id, "title": section["title"], "layout_id": "overview-detail",
                                                                    "chapter_claims": [section["title"]], "blocks": []}})
        components.extend(_component_for_block(block, section, index, report, metrics) for index, block in enumerate(section["blocks"], 1))
    references = report["references"]
    if report["metadata"].get("bibliography_policy") != "full":
        references = [{"id": reference["id"], "title": reference["id"],
                       "locators": reference.get("locators") or ["Evidence package"]}
                      for reference in references]
    components.append({"kind": "references-appendix", "payload": {"id": "references", "title": "来源索引", "layout_id": "continued-table",
                                                                         "blocks": [], "references": references}})
    document = {"title": report["metadata"]["title"], "components": components}
    if "citation_registry" in report:
        document["citation_registry"] = report["citation_registry"]
    return document


def cmd_init(args):
    task = pathlib.Path(args.task).resolve()
    story = story_dir(task)
    work = work_dir(task)
    if work.exists() or (story / "report.json").exists():
        print("A4 报告任务已存在；故事线变化后用 refresh", file=sys.stderr)
        return 2
    slides, sidecar = load_story(task)
    try:
        legacy = to_forge.build(task, slides, sidecar, args.allow)
        report, coverage = to_report.build(task, slides, sidecar, bibliography_policy=args.bibliography_policy)
    except (to_forge.BridgeError, to_report.ReportError) as error:
        return report_problem(error)
    work.mkdir(parents=True)
    write_json(story / "report.json", report)
    write_json(work / "coverage-manifest.json", coverage)
    write_json(work / "render-document.json", render_document(report, task))
    write_json(work / "conversion.json", {"notes": legacy["notes"], "trace": legacy["trace"], "a_cards": legacy["a_cards"]})
    print(f"已建立 A4 报告任务：{work}")
    print("下一步：out_report render <任务>；首次视觉差异会失败关闭，需作者实际查看逐页 PNG 后提交 review。")
    return 0


def cmd_refresh(args):
    work = work_dir(args.task)
    if not work.is_dir():
        print("尚未建立 A4 报告任务", file=sys.stderr)
        return 2
    shutil.rmtree(work)
    report = story_dir(args.task) / "report.json"
    if report.exists():
        report.unlink()
    return cmd_init(args)


def _visual_regression(work, pagination):
    baseline = read_json(SKILL_DIR / "golden/approved-page-baseline.json")
    candidate = read_json(work / "build/visual-candidate.json")
    page_ids = [page["id"] for page in pagination["pages"]]
    regression = compare_manifests(baseline, candidate, page_ids)
    author = work / "author-review.json"
    if author.is_file():
        regression["disposition"] = read_json(author)
    write_json(work / "visual-regression.json", regression)
    return regression


def _qa(work):
    build = work / "build"
    pagination = read_json(build / "pagination-manifest.json")
    evidence = {
        "pagination": pagination,
        "geometry": read_json(build / "geometry-manifest.json"),
        "coverage": read_json(work / "coverage-manifest.json"),
        "media": read_json(build / "media-manifest.json"),
        "regression": _visual_regression(work, pagination),
    }
    evidence_file = work / "qa-evidence.json"
    write_json(evidence_file, evidence)
    qa_file = work / "qa-result.json"
    result = run(["node", A4_DIR / "qa.cjs", evidence_file, qa_file])
    return json.loads(result.stdout)


def artifact_paths(work):
    build = work / "build"
    paths = [work.parent / "report.json", work / "render-document.json", work / "coverage-manifest.json",
             build / "report.html", build / "report.pdf", build / "pagination-manifest.json",
             build / "geometry-manifest.json", build / "media-manifest.json", build / "visual-candidate.json"]
    paths.extend(sorted(build.glob("page-*.png")))
    return paths


def capture_artifacts(work):
    build = work / "build"
    pagination = build / "pagination-manifest.json"
    paths = artifact_paths(work)
    if not paths or any(not path.is_file() for path in paths):
        raise StepError("REPORT_ARTIFACT_MISSING: rendered HTML, PDF, candidate and page PNGs are required")
    hashes = {os.path.relpath(path, work): file_sha256(path) for path in paths}
    manifest = {"schemaVersion": "1.0", "pageCount": len(list(build.glob("page-*.png"))),
                "paginationDigest": file_sha256(pagination), "artifacts": hashes}
    manifest["artifactDigest"] = structured_digest({"paginationDigest": manifest["paginationDigest"], "artifacts": hashes})
    write_json(work / "artifact-manifest.json", manifest)
    return manifest


def verify_artifacts(work):
    manifest_file = work / "artifact-manifest.json"
    if not manifest_file.is_file():
        raise StepError("REPORT_ARTIFACT_MISSING: artifact-manifest.json")
    expected = read_json(manifest_file)
    current_paths = artifact_paths(work)
    current = {os.path.relpath(path, work): file_sha256(path) for path in current_paths if path.is_file()}
    pagination = work / "build/pagination-manifest.json"
    pagination_digest = file_sha256(pagination) if pagination.is_file() else ""
    digest = structured_digest({"paginationDigest": pagination_digest, "artifacts": current})
    if current != expected.get("artifacts") or pagination_digest != expected.get("paginationDigest") or digest != expected.get("artifactDigest"):
        raise StepError("REPORT_ARTIFACT_MISMATCH: reviewed HTML, PDF, PNG, candidate or pagination artifact changed")
    return expected


def replace_delivery(destination, sources):
    """Build a complete managed directory, then swap it into place without stale files."""
    destination = pathlib.Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = pathlib.Path(tempfile.mkdtemp(prefix=f".{destination.name}-staging-", dir=destination.parent))
    backup = None
    try:
        for name, source in sources.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if destination.exists():
            backup = pathlib.Path(tempfile.mkdtemp(prefix=f".{destination.name}-previous-", dir=destination.parent))
            backup.rmdir()
            destination.replace(backup)
        staging.replace(destination)
        if backup is not None:
            shutil.rmtree(backup)
    except Exception:
        if not destination.exists() and backup is not None and backup.exists():
            backup.replace(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)


def cmd_render(args):
    work = work_dir(args.task)
    if not (work / "render-document.json").is_file():
        print("尚未建立 A4 报告任务，先运行 init", file=sys.stderr)
        return 2
    build = work / "build"
    build.mkdir(exist_ok=True)
    try:
        run(["node", A4_DIR / "render.cjs", work / "render-document.json", build])
        run(["node", A4_DIR / "export.cjs", build / "report.html", build])
        capture_artifacts(work)
        result = _qa(work)
    except StepError as error:
        print(str(error), file=sys.stderr)
        return 1
    for item in result["blocking"]:
        print(f"[{item['code']}] {item['location']}：{item['detail']}")
    for item in result["warnings"]:
        print(f"[{item['code']}] {item['location']}：{item['detail']}")
    print(f"A4 预览：{build / 'report.pdf'}；QA={result['status']}")
    return 0 if result["status"] != "failed" else 1


def useful_observation(value):
    text = str(value or "").strip()
    generic = {"pass", "passed", "ok", "normal", "正常", "通过", "无问题", "没问题"}
    return len(text) >= 20 and text.lower() not in generic


def _validate_author(review, regression, artifacts):
    try:
        reviewed_at = datetime.datetime.fromisoformat(str(review.get("reviewedAt", "")).replace("Z", "+00:00"))
    except ValueError:
        reviewed_at = None
    required = (
        review.get("type") == "author" and isinstance(review.get("reviewer"), str) and review["reviewer"].strip()
        and reviewed_at is not None and reviewed_at.tzinfo is not None
        and review.get("decision") == "accepted" and useful_observation(review.get("reason"))
        and review.get("artifactDigest") == artifacts["artifactDigest"]
        and review.get("paginationDigest") == artifacts["paginationDigest"]
        and review.get("baselineDigest") == regression.get("baselineDigest")
        and review.get("candidateDigest") == regression.get("candidateDigest")
        and review.get("differenceDigest") == regression.get("differenceDigest")
    )
    if not required:
        raise StepError("REPORT_REVIEW_INVALID: author review must have a timezone-aware timestamp, accepted disposition with a specific reason, and bind the current artifact, pagination, baseline, candidate, and difference digests")


def _validate_independent(review, work, artifacts):
    pagination = read_json(work / "build/pagination-manifest.json")
    page_ids = [page["id"] for page in pagination["pages"]]
    try:
        reviewed_at = datetime.datetime.fromisoformat(str(review.get("at", "")).replace("Z", "+00:00"))
    except ValueError:
        reviewed_at = None
    observations = review.get("observations")
    sheets = review.get("chapter_contact_sheets")
    headline = review.get("headline_chain") or {}
    observed_ids = [item.get("page_id") for item in observations] if isinstance(observations, list) else []
    sheet_ids = [page for sheet in sheets for page in sheet.get("page_ids", [])] if isinstance(sheets, list) else []
    required = (
        review.get("type") == "independent" and isinstance(review.get("reviewer"), str) and review["reviewer"].strip()
        and reviewed_at is not None and reviewed_at.tzinfo is not None and useful_observation(review.get("conclusion"))
        and review.get("artifactDigest") == artifacts["artifactDigest"]
        and review.get("paginationDigest") == artifacts["paginationDigest"]
        and review.get("page_ids") == page_ids and set(review.get("media") or []) == {"html", "pdf"}
        and "100%" in (review.get("scales") or []) and bool({"contact-sheet", "thumbnail"} & set(review.get("scales") or []))
        and isinstance(sheets, list) and sheets and len(sheet_ids) == len(page_ids) and set(sheet_ids) == set(page_ids)
        and all(useful_observation(sheet.get("observation")) for sheet in sheets)
        and headline.get("status") == "reviewed" and useful_observation(headline.get("observation"))
        and isinstance(observations, list) and observed_ids == page_ids
        and all(set(item.get("media") or []) == {"html", "pdf"} and "100%" in (item.get("scale") or [])
                and bool({"contact-sheet", "thumbnail"} & set(item.get("scale") or []))
                and useful_observation(item.get("observation")) and useful_observation(item.get("reason")) for item in observations)
        and isinstance(review.get("issues"), list) and not any(not issue.get("resolved", False) for issue in review["issues"])
    )
    if not required:
        raise StepError("REPORT_REVIEW_INVALID: independent review must bind artifacts and pagination, cover every page in HTML/PDF at 100% and contact-sheet/thumbnail scales, review chapter sheets and headline chain, and record specific observations/reasons with no unresolved issues")


def cmd_review(args):
    work = work_dir(args.task)
    source = pathlib.Path(args.review).resolve()
    review = read_json(source)
    try:
        artifacts = verify_artifacts(work)
    except StepError as error:
        print(str(error), file=sys.stderr)
        return 1
    if args.kind == "author":
        regression = read_json(work / "visual-regression.json")
        try:
            _validate_author(review, regression, artifacts)
        except StepError as error:
            print(str(error), file=sys.stderr)
            return 1
        write_json(work / "author-review.json", review)
        try:
            qa = _qa(work)
        except StepError as error:
            print(str(error), file=sys.stderr)
            return 1
        if qa["status"] == "failed":
            print("REPORT_REVIEW_INVALID: author disposition did not clear visual QA", file=sys.stderr)
            return 1
    else:
        try:
            _validate_independent(review, work, artifacts)
        except StepError as error:
            print(str(error), file=sys.stderr)
            return 1
        write_json(work / "independent-review.json", review)
    print(f"已登记 {args.kind} review")
    return 0


def storyline_check(task):
    script = SKILL_DIR.parent / "core-storyline/scripts/storyline.py"
    result = subprocess.run([sys.executable, str(script), "check", str(task), "--json"], capture_output=True, text=True)
    try:
        value = json.loads(result.stdout)
        return {"name": "storyline", "result": "passed" if value["passed"] else "failed",
                "detail": f"errors={len(value['errors'])}; warnings={len(value['warnings'])}"}
    except (ValueError, KeyError):
        return {"name": "storyline", "result": "failed", "detail": (result.stdout + result.stderr)[-500:]}


def diligence_checks(task):
    task = pathlib.Path(task)
    if not (task / "03d_diligence/report-content.json").is_file():
        return []
    script = SKILL_DIR.parent / "core-diligence/scripts/diligence.py"

    def check(*arguments):
        result = subprocess.run([sys.executable, str(script), *arguments, str(task), "--json"], capture_output=True, text=True)
        try:
            return json.loads(result.stdout)
        except ValueError:
            return {"errors": [(result.stdout + result.stderr)[-500:]]}

    base = check("check")
    content = check("check-content", "--after-split", "--final")
    gate = base.get("research_gate")
    projects = Ledger(task).read("project")
    report_status = projects[0].get("report_status") if projects else None
    status = "failed" if gate in (None, "incomplete") or report_status in (None, "draft") else "limited" if gate == "partial" or report_status == "limited" else "passed"
    return [
        {"name": "尽调检查（diligence check）", "result": "failed" if base.get("errors") else "passed",
         "detail": "；".join(base.get("errors") or [])[:500] or f"research_gate={gate}"},
        {"name": "尽调内容契约（拆页后复核、22 条人工清单）", "result": "failed" if content.get("errors") else "passed",
         "detail": "；".join(content.get("errors") or [])[:500] or "final content contract passed"},
        {"name": "尽调完成状态", "result": status, "detail": f"research_gate={gate}; report_status={report_status}"},
    ]


def cmd_package(args):
    task = pathlib.Path(args.task).resolve()
    work = work_dir(task)
    missing = [name for name in ("author-review.json", "independent-review.json") if not (work / name).is_file()]
    if missing:
        print("REPORT_REVIEW_REQUIRED: " + "、".join(name.removesuffix(".json") for name in missing), file=sys.stderr)
        return 1
    try:
        artifacts = verify_artifacts(work)
        _validate_author(read_json(work / "author-review.json"), read_json(work / "visual-regression.json"), artifacts)
        _validate_independent(read_json(work / "independent-review.json"), work, artifacts)
        qa = _qa(work)
    except StepError as error:
        print(str(error), file=sys.stderr)
        return 1
    if qa["status"] == "failed":
        print("REPORT_QA_FAILED: " + "、".join(item["code"] for item in qa["blocking"]), file=sys.stderr)
        return 1
    build = work / "build"
    out = client_report_dir(task)
    sources = {"report.html": build / "report.html", "report.pdf": build / "report.pdf"}
    replace_delivery(out, sources)
    try:
        evidence = package_support.build(task, require_app=False)
    except (package_support.PackageError, OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"EVIDENCE_PACKAGE_FAILED: {error}", file=sys.stderr)
        return 1
    checks = [
        storyline_check(task), *diligence_checks(task),
        {"name": "coverage", "result": "passed", "detail": "input/output sets equal; duplicates rejected"},
        {"name": "pagination", "result": "passed", "detail": f"{read_json(build / 'pagination-manifest.json')['pageCount']} A4 pages"},
        {"name": "geometry", "result": "passed", "detail": "A4, no overflow, clipping, overlap, or undersized type"},
        {"name": "visual-regression", "result": "passed", "detail": qa["status"]},
        {"name": "author-review", "result": "passed", "detail": read_json(work / "author-review.json")["reviewer"]},
        {"name": "independent-review", "result": "passed", "detail": read_json(work / "independent-review.json")["reviewer"]},
    ]
    independent = read_json(work / "independent-review.json")
    acceptance_reviewer = {key: independent[key] for key in ("type", "reviewer", "at", "conclusion", "issues")}
    entry = Acceptance(task).record({
        "id": f"report-{args.slug}", "kind": "report", "title": read_json(story_dir(task) / "report.json")["metadata"]["title"],
        "files": [str((out / name).relative_to(task)) for name in sources], "upstream_checks": checks, "reviewer": acceptance_reviewer,
    })
    print(f"已打包 A4 报告：{out}")
    print(f"已打包证据包：{evidence['output']}")
    print(f"统一验收状态：{entry['status']}")
    return 0 if entry["status"] == "passed" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="确定性 A4 正式报告")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "refresh"):
        item = sub.add_parser(name)
        item.add_argument("task")
        item.add_argument("--allow", action="append", default=[])
        item.add_argument("--bibliography-policy", choices=("evidence_package", "full"), default="evidence_package")
    item = sub.add_parser("render"); item.add_argument("task")
    item = sub.add_parser("review"); item.add_argument("task"); item.add_argument("kind", choices=("author", "independent")); item.add_argument("review")
    item = sub.add_parser("package"); item.add_argument("task"); item.add_argument("--slug", default="main")
    args = parser.parse_args(argv)
    return {"init": cmd_init, "refresh": cmd_refresh, "render": cmd_render, "review": cmd_review, "package": cmd_package}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
