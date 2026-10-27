#!/usr/bin/env python3
"""Read-only A4 PDF geometry and visual artifact comparison helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


POINTS_PER_MM = 72 / 25.4
MEDIABOX = re.compile(rb"/MediaBox\s*\[\s*([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s*\]")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_media_boxes_mm(path: Path) -> list[list[float]]:
    boxes = []
    for match in MEDIABOX.finditer(path.read_bytes()):
        x0, y0, x1, y1 = (float(value) for value in match.groups())
        boxes.append([round((x1 - x0) / POINTS_PER_MM, 3), round((y1 - y0) / POINTS_PER_MM, 3)])
    return boxes


def compare_files(baseline: Path, candidate: Path) -> dict:
    baseline_digest = sha256(baseline)
    candidate_digest = sha256(candidate)
    return {
        "schemaVersion": "1.0",
        "status": "identical" if baseline_digest == candidate_digest else "different",
        "baseline": str(baseline),
        "candidate": str(candidate),
        "baselineDigest": baseline_digest,
        "candidateDigest": candidate_digest,
        "differences": [] if baseline_digest == candidate_digest else [{"kind": "sha256", "baseline": baseline_digest, "candidate": candidate_digest}],
        "baselineUpdated": False,
    }


def compare_manifests(baseline: dict, candidate: dict, pagination_page_ids: list[str] | None = None) -> dict:
    """Compare immutable per-page raster hashes; approval is handled separately."""
    baseline_pages = baseline.get("artifacts", {}).get("pagePngSha256", {})
    candidate_pages = candidate.get("artifacts", {}).get("pagePngSha256", {})
    expected = pagination_page_ids if pagination_page_ids is not None else list(candidate_pages) if isinstance(candidate_pages, dict) else []
    errors = []
    for label, pages in (("baseline", baseline_pages), ("candidate", candidate_pages)):
        if not isinstance(pages, dict) or not pages or any(not isinstance(key, str) or not key or not isinstance(value, str) or not SHA256.fullmatch(value) for key, value in pages.items()):
            errors.append(f"{label} pagePngSha256 must be a non-empty page-to-SHA256 map")
        elif label == "candidate" and list(pages) != expected:
            errors.append(f"{label} page set/order differs from pagination")
    if not expected:
        errors.append("pagination page IDs must be non-empty")
    if errors:
        return {"schemaVersion": "1.0", "status": "invalid", "errors": errors, "differences": [], "baselineUpdated": False}
    differences = []
    for page in sorted(set(baseline_pages) | set(candidate_pages)):
        before = baseline_pages.get(page)
        after = candidate_pages.get(page)
        if before != after:
            differences.append({"page": page, "kind": "added" if before is None else "removed" if after is None else "changed", "baseline": before, "candidate": after})
    baseline_digest = hashlib.sha256(json.dumps(baseline_pages, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    candidate_digest = hashlib.sha256(json.dumps(candidate_pages, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    difference_digest = hashlib.sha256(json.dumps(differences, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schemaVersion": "1.0",
        "status": "identical" if not differences else "different",
        "baselineDigest": baseline_digest,
        "candidateDigest": candidate_digest,
        "baselinePages": [{"id": page, "digest": baseline_pages[page]} for page in baseline_pages],
        "candidatePages": [{"id": page, "digest": candidate_pages[page]} for page in candidate_pages],
        "differences": differences,
        "differenceDigest": difference_digest,
        "baselineUpdated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare_files(args.baseline, args.candidate)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
