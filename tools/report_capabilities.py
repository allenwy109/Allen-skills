#!/usr/bin/env python3
"""Inspect and validate the vendored report-forge capability inventory."""

import argparse
import json
import pathlib
import subprocess
import sys


MATRIX = pathlib.Path("references/upstream-capability-matrix.json")
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
    parser.add_argument("command", choices=("inspect", "check"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    root = pathlib.Path(__file__).resolve().parent.parent
    try:
        if args.command == "inspect":
            result = inspect(root)
            code = 0
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
