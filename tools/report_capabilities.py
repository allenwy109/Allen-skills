#!/usr/bin/env python3
"""Inspect and validate the vendored report-forge capability inventory."""

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys


MATRIX = pathlib.Path("references/upstream-capability-matrix.json")
BASELINE = pathlib.Path("references/upstream-visual-baseline.json")
BASELINE_SCHEMA = pathlib.Path("references/visual-baseline.schema.json")
SHOWCASE = pathlib.Path("vendor/report-forge/docs/showcase")
UPSTREAM_REPO = "https://github.com/ZeroxZhang/zerox-skills.git"
UPSTREAM_COMMIT = "ee1f980c8dd7c53408e1a05a084229e6ec03c660"
REFERENCE_FIELDS = ("upstream_ref", "local_ref", "test", "visual_evidence")
STATUSES = {"parity", "missing", "untested", "present-not-used", "superseded"}
RELEASE_READY = {"parity", "superseded"}
REQUIRED_CAPABILITY_IDS = {
    "layouts-38", "masters-6", "themes-3", "ratios-2", "form-catalog",
    "form-capacity", "chart-diversity", "layout-diversity", "module-fill",
    "representative-pages", "contact-sheet-worst-page", "html-pdf-page-review",
    "official-showcase", "showcase-build-scripts", "screenshot-manifest",
    "author-review", "independent-review", "review-reuse", "execution-plan",
    "resume-recovery", "narrative", "composition", "evidence-binding",
    "packaging", "upstream-contract-tests", "real-browser-tests",
}


class CapabilityError(Exception):
    """A stable, user-facing capability inspection failure."""


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_baseline(root):
    root = pathlib.Path(root).resolve()
    showcase = root / SHOWCASE
    if not showcase.is_dir():
        raise CapabilityError(f"{SHOWCASE}: showcase directory does not exist")
    artifacts = []
    for path in sorted(item for item in showcase.rglob("*") if item.is_file()):
        artifacts.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": _digest(path),
            "size": path.stat().st_size,
        })
    if not artifacts:
        raise CapabilityError(f"{SHOWCASE}: showcase contains no files")
    return {
        "version": 1,
        "upstream_repo": UPSTREAM_REPO,
        "upstream_commit": UPSTREAM_COMMIT,
        "license": "Apache-2.0",
        "status": "captured",
        "approval": "unapproved",
        "artifacts": artifacts,
    }


def write_baseline(root, baseline):
    path = pathlib.Path(root).resolve() / BASELINE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _schema_errors(schema):
    required = {"version", "upstream_repo", "upstream_commit", "license", "status",
                "approval", "artifacts"}
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return ["baseline schema: root must define an object"]
    if set(schema.get("required", [])) != required:
        return ["baseline schema: required fields do not match contract"]
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not required.issubset(properties):
        return ["baseline schema: properties do not match contract"]
    items = properties.get("artifacts", {}).get("items", {})
    if set(items.get("required", [])) != {"path", "sha256", "size"}:
        return ["baseline schema: artifact fields do not match contract"]
    expected_constants = {
        "version": 1,
        "upstream_repo": UPSTREAM_REPO,
        "upstream_commit": UPSTREAM_COMMIT,
        "license": "Apache-2.0",
    }
    for field, value in expected_constants.items():
        if properties[field].get("const") != value:
            return [f"baseline schema: {field} const does not match contract"]
    if schema.get("additionalProperties") is not False or items.get("additionalProperties") is not False:
        return ["baseline schema: additional properties must be rejected"]
    return []


def check_baseline(root):
    root = pathlib.Path(root).resolve()
    try:
        schema = json.loads((root / BASELINE_SCHEMA).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{BASELINE_SCHEMA}: cannot read schema: {error}"]
    errors = _schema_errors(schema)
    if errors:
        return errors
    try:
        baseline = json.loads((root / BASELINE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{BASELINE}: cannot read baseline: {error}"]
    if not isinstance(baseline, dict):
        return ["baseline: must be an object"]
    expected = generate_baseline(root)
    extra_fields = sorted(set(baseline) - set(expected))
    if extra_fields:
        errors.append("baseline: unknown fields: " + ", ".join(extra_fields))
    for field in ("version", "upstream_repo", "upstream_commit", "license", "status", "approval"):
        if baseline.get(field) != expected[field]:
            errors.append(f"baseline: {field} must be {expected[field]!r}")
    artifacts = baseline.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return errors + ["baseline: artifacts must be a non-empty array"]
    seen = set()
    actual = {}
    showcase = (root / SHOWCASE).resolve()
    for index, artifact in enumerate(artifacts):
        label = f"baseline artifact[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{label}: must be an object")
            continue
        extra_fields = sorted(set(artifact) - {"path", "sha256", "size"})
        if extra_fields:
            errors.append(f"{label}: unknown fields: " + ", ".join(extra_fields))
        path_text = artifact.get("path")
        if not isinstance(path_text, str) or not path_text:
            errors.append(f"{label}: path must be a non-empty string")
            continue
        if path_text in seen:
            errors.append(f"{label}: duplicate path: {path_text}")
        seen.add(path_text)
        path = (root / path_text).resolve()
        try:
            path.relative_to(showcase)
        except ValueError:
            errors.append(f"{label}: path escapes showcase: {path_text}")
            continue
        if not path.exists():
            errors.append(f"{label}: file does not exist: {path_text}")
            continue
        if not path.is_file():
            errors.append(f"{label}: path is not a file: {path_text}")
            continue
        actual[path_text] = artifact
        if artifact.get("sha256") != _digest(path):
            errors.append(f"{label}: sha256 mismatch: {path_text}")
        if artifact.get("size") != path.stat().st_size:
            errors.append(f"{label}: size mismatch: {path_text}")
    expected_by_path = {item["path"]: item for item in expected["artifacts"]}
    missing = sorted(set(expected_by_path) - set(actual))
    extra = sorted(set(actual) - set(expected_by_path))
    if missing:
        errors.append("baseline: missing artifacts: " + ", ".join(missing))
    if extra:
        errors.append("baseline: extra artifacts: " + ", ".join(extra))
    return errors


def _javascript_capabilities(forge):
    script = (
        "const themes=require(process.argv[1]),grid=require(process.argv[2]);"
        "process.stdout.write(JSON.stringify({themes:themes.ids,ratios:Object.keys(grid.RATIOS).sort()}));"
    )
    try:
        result = subprocess.run(
            ["node", "-e", script, str(forge / "assets" / "deck-themes.js"),
             str(forge / "assets" / "deck-grid.js")],
            check=True, capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        if not isinstance(data.get("themes"), list) or not isinstance(data.get("ratios"), list):
            raise ValueError("invalid exports")
        return data
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as error:
        raise CapabilityError("cannot inspect JavaScript exports") from error


def inspect(root):
    root = pathlib.Path(root).resolve()
    forge = root / "vendor" / "report-forge"
    try:
        catalog = json.loads(
            (forge / "assets" / "layout-atlas" / "catalog.json").read_text(encoding="utf-8")
        )
        layouts = catalog["layouts"]
        masters = catalog["masters"]
        if not isinstance(layouts, list) or not isinstance(masters, list):
            raise ValueError("invalid catalog")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        raise CapabilityError("cannot inspect layout catalog") from error
    javascript = _javascript_capabilities(forge)
    showcase = forge / "docs" / "showcase"
    return {
        "layout_count": len(layouts),
        "master_count": len(masters),
        "themes": javascript["themes"],
        "ratios": javascript["ratios"],
        "showcase_files": sorted(
            str(path.relative_to(root)) for path in showcase.rglob("*") if path.is_file()
        ),
    }


def check(root, strict=False):
    root = pathlib.Path(root).resolve()
    path = root / MATRIX
    try:
        matrix = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{MATRIX}: cannot read matrix: {error}"]
    if not isinstance(matrix, dict):
        return ["matrix: must be an object"]

    errors = []
    for field in ("phase", "status"):
        if not isinstance(matrix.get(field), str) or not matrix[field].strip():
            errors.append(f"matrix: {field} must be a non-empty string")
    capabilities = matrix.get("capabilities")
    if not isinstance(capabilities, list):
        return errors + ["matrix: capabilities must be an array"]

    seen = set()
    ids = []
    strict = strict or _requires_strict(matrix)
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(f"capability[{index}]: must be an object")
            continue
        capability_id = capability.get("id")
        label = capability_id if isinstance(capability_id, str) and capability_id else f"capability[{index}]"
        if label in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(label)
        if isinstance(capability_id, str) and capability_id:
            ids.append(capability_id)
        for field in ("id", "category", *REFERENCE_FIELDS, "status"):
            if not isinstance(capability.get(field), str) or not capability[field].strip():
                errors.append(f"{label}: {field} must be a non-empty string")

        status = capability.get("status")
        if status not in STATUSES:
            errors.append(f"{label}: unknown status {status}")
        elif status == "missing":
            errors.append(f"{label}: status missing")
        elif strict and status not in RELEASE_READY:
            errors.append(f"{label}: status {status} is not release-ready")

        for field in REFERENCE_FIELDS:
            reference = capability.get(field)
            if not isinstance(reference, str) or not reference.strip():
                continue
            target = (root / reference).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                errors.append(f"{label}: {field} escapes repository: {reference}")
            else:
                if not target.exists():
                    errors.append(f"{label}: {field} does not exist: {reference}")
                elif not target.is_file():
                    errors.append(f"{label}: {field} is not a file: {reference}")
    actual = set(ids)
    missing = sorted(REQUIRED_CAPABILITY_IDS - actual)
    extra = sorted(actual - REQUIRED_CAPABILITY_IDS)
    if missing:
        errors.append("matrix: missing capability ids: " + ", ".join(missing))
    if extra:
        errors.append("matrix: extra capability ids: " + ", ".join(extra))
    return errors


def _requires_strict(matrix):
    return (
        matrix.get("status") in {"complete", "release"}
        or str(matrix.get("phase", "")).startswith(("phase-4", "release"))
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inspect", "check", "baseline-generate", "baseline-check"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    root = pathlib.Path(__file__).resolve().parent.parent
    try:
        if args.command == "inspect":
            result = inspect(root)
            code = 0
        elif args.command == "baseline-generate":
            baseline = generate_baseline(root)
            write_baseline(root, baseline)
            result = baseline
            code = 0
        elif args.command == "baseline-check":
            errors = check_baseline(root)
            result = {"errors": errors, "ok": not errors}
            code = 1 if errors else 0
        else:
            errors = check(root, strict=args.strict)
            try:
                matrix = json.loads((root / MATRIX).read_text(encoding="utf-8"))
                effective_strict = args.strict or (
                    isinstance(matrix, dict) and _requires_strict(matrix)
                )
            except (OSError, json.JSONDecodeError):
                effective_strict = args.strict
            result = {"errors": errors, "ok": not errors, "strict": effective_strict}
            code = 1 if errors else 0
    except CapabilityError as error:
        result = {"error": str(error), "ok": False}
        code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
