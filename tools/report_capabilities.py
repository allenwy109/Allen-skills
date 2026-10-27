#!/usr/bin/env python3
"""Inspect and validate the vendored report-forge capability inventory."""

import argparse
import json
import pathlib
import re
import sys


MATRIX = pathlib.Path("references/upstream-capability-matrix.json")
REFERENCE_FIELDS = ("upstream_ref", "local_ref", "test", "visual_evidence")
STATUSES = {"parity", "missing", "untested", "present-not-used", "superseded"}
RELEASE_READY = {"parity", "superseded"}


def _object_keys(path, start, end):
    text = path.read_text(encoding="utf-8")
    body = text.split(start, 1)[1].split(end, 1)[0]
    return re.findall(r'^  ["\']([^"\']+)["\']:\s*\{', body, re.MULTILINE)


def inspect(root):
    root = pathlib.Path(root)
    forge = root / "vendor" / "report-forge"
    catalog = json.loads(
        (forge / "assets" / "layout-atlas" / "catalog.json").read_text(encoding="utf-8")
    )
    themes = _object_keys(
        forge / "assets" / "deck-themes.js", "const presets={", "\n};\nfunction get"
    )
    ratios = _object_keys(
        forge / "assets" / "deck-grid.js", "const RATIOS = {", "\n};\n\n/* 行高"
    )
    showcase = forge / "docs" / "showcase"
    return {
        "layout_count": len(catalog["layouts"]),
        "master_count": len(catalog["masters"]),
        "themes": themes,
        "ratios": ratios,
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

    errors = []
    for field in ("phase", "status"):
        if not isinstance(matrix.get(field), str) or not matrix[field].strip():
            errors.append(f"matrix: {field} must be a non-empty string")
    capabilities = matrix.get("capabilities")
    if not isinstance(capabilities, list):
        return errors + ["matrix: capabilities must be an array"]

    seen = set()
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(f"capability[{index}]: must be an object")
            continue
        capability_id = capability.get("id")
        label = capability_id if isinstance(capability_id, str) and capability_id else f"capability[{index}]"
        if label in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(label)
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
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inspect", "check"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    root = pathlib.Path(__file__).resolve().parent.parent
    if args.command == "inspect":
        result = inspect(root)
        code = 0
    else:
        errors = check(root, strict=args.strict)
        result = {"errors": errors, "ok": not errors, "strict": args.strict}
        code = 1 if errors else 0
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
