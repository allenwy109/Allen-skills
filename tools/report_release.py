#!/usr/bin/env python3
"""Validate the tracked report-output release record and compact evidence bundle."""

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools import report_capabilities


RELEASE = pathlib.Path("references/report-output-release.json")
SCHEMA = pathlib.Path("references/report-output-release.schema.json")
DIMENSIONS = {
    "visual_focus", "evidence_geometry", "density", "typography",
    "chart_clarity", "book_rhythm", "source_integration", "finish",
}
ROOT_FIELDS = {
    "schemaVersion", "schema", "status", "releasedAt", "implementationHead",
    "provenance", "capabilities", "evidence", "a4", "deck", "scenarios",
    "verification", "review",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
ABSOLUTE_MACHINE_PATH = re.compile(r"(?:^|[\s=])(?:/Users/|/home/|[A-Za-z]:\\)")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _score_errors(label, scores):
    if not isinstance(scores, dict) or set(scores) != DIMENSIONS:
        return [f"{label}: scores must contain exactly eight release dimensions"]
    errors = []
    for dimension, value in scores.items():
        if type(value) is not int or not 1 <= value <= 5:
            errors.append(f"{label}: {dimension} score must be an integer from 1 to 5")
        elif value < 4:
            errors.append(f"{label}: {dimension} score must be at least 4")
    return errors


def validate_release_data(release):
    if not isinstance(release, dict):
        return ["release: must be an object"]
    errors = []
    missing = sorted(ROOT_FIELDS - set(release))
    extra = sorted(set(release) - ROOT_FIELDS)
    if missing:
        errors.append("release: missing fields: " + ", ".join(missing))
    if extra:
        errors.append("release: unknown fields: " + ", ".join(extra))
    if release.get("schemaVersion") != "1.0":
        errors.append("release: schemaVersion must be 1.0")
    if release.get("schema") != SCHEMA.as_posix():
        errors.append(f"release: schema must be {SCHEMA.as_posix()}")
    status = release.get("status")
    if status not in {"pending-verification", "approved"}:
        errors.append("release: invalid status")
    if status == "approved" and not _nonempty(release.get("releasedAt")):
        errors.append("release: approved status requires releasedAt")
    if not COMMIT.fullmatch(str(release.get("implementationHead", ""))):
        errors.append("release: implementationHead must be a commit id")

    a4 = release.get("a4")
    deck = release.get("deck")
    if not isinstance(a4, dict):
        errors.append("a4: must be an object")
    else:
        errors.extend(_score_errors("a4", a4.get("scores")))
        if a4.get("status") != "approved" or a4.get("approvedBy") != "user":
            errors.append("a4: current digest must be explicitly approved by user")
        if not SHA256.fullmatch(str(a4.get("candidateDigest", ""))):
            errors.append("a4: candidateDigest must be sha256")
    if not isinstance(deck, dict):
        errors.append("deck: must be an object")
    else:
        candidate = deck.get("candidateScores")
        reference = deck.get("referenceScores")
        errors.extend(_score_errors("deck candidate", candidate))
        if not isinstance(reference, dict) or set(reference) != DIMENSIONS:
            errors.append("deck reference: scores must contain exactly eight release dimensions")
        elif isinstance(candidate, dict) and set(candidate) == DIMENSIONS:
            losses = sorted(k for k in DIMENSIONS if candidate[k] < reference[k])
            wins = sorted(k for k in DIMENSIONS if candidate[k] > reference[k])
            if losses:
                errors.append("deck candidate: dimensions lower than reference: " + ", ".join(losses))
            if len(wins) < 2:
                errors.append("deck candidate: must beat reference in at least two dimensions")
            if sorted(deck.get("winningDimensions", [])) != wins:
                errors.append("deck candidate: winningDimensions do not match scores")
        reviewer = deck.get("reviewer")
        expected_reviewer = {
            "mode": "fresh-read-only-anonymous",
            "identityAvailableDuringScoring": False,
            "sourceCodeAvailableDuringScoring": False,
            "priorPacketsAvailableDuringScoring": False,
        }
        if reviewer != expected_reviewer:
            errors.append("deck: reviewer independence contract is incomplete")

    verification = release.get("verification")
    if not isinstance(verification, dict):
        errors.append("verification: must be an object")
    else:
        commands = verification.get("commands")
        if not isinstance(commands, list) or not commands:
            errors.append("verification: commands must be a non-empty array")
        else:
            for index, item in enumerate(commands):
                command = item.get("command") if isinstance(item, dict) else None
                if not _nonempty(command):
                    errors.append(f"verification command[{index}]: command must be non-empty")
                elif ABSOLUTE_MACHINE_PATH.search(command):
                    errors.append(f"verification command[{index}]: machine-specific absolute path")
                if not isinstance(item, dict) or item.get("result") != "passed":
                    errors.append(f"verification command[{index}]: result must be passed")
        if status == "approved" and verification.get("allPassed") is not True:
            errors.append("verification: approved release requires allPassed=true")
    return errors


def _is_tracked(root, relative):
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--error-unmatch", relative.as_posix()],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def check_evidence(root, release):
    root = pathlib.Path(root).resolve()
    errors = []
    evidence = release.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != {
        "deckScorecard", "deckReveal", "deckArtifacts", "a4Evidence", "scenarioTests"
    }:
        return ["evidence: must contain the five compact evidence records"]
    loaded = {}
    for key, record in evidence.items():
        if not isinstance(record, dict):
            errors.append(f"evidence {key}: must be an object")
            continue
        relative = pathlib.Path(str(record.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != ("references", "release-evidence"):
            errors.append(f"evidence {key}: path must stay in references/release-evidence")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"evidence {key}: file does not exist: {relative}")
            continue
        if not _is_tracked(root, relative):
            errors.append(f"evidence {key}: file is not tracked: {relative}")
        expected = record.get("sha256")
        if not SHA256.fullmatch(str(expected or "")):
            errors.append(f"evidence {key}: sha256 is invalid")
        elif digest(path) != expected:
            errors.append(f"evidence {key}: sha256 mismatch")
        try:
            loaded[key] = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"evidence {key}: invalid JSON: {error}")
    if errors:
        return errors

    scorecard = loaded["deckScorecard"]
    reveal = loaded["deckReveal"]
    artifacts = loaded["deckArtifacts"]
    a4_evidence = loaded["a4Evidence"]
    scenario = loaded["scenarioTests"]
    if reveal.get("bindings", {}).get("deckScorecardSha256") != evidence["deckScorecard"]["sha256"]:
        errors.append("deck reveal: scorecard hash binding mismatch")
    if reveal.get("bindings", {}).get("deckArtifactsSha256") != evidence["deckArtifacts"]["sha256"]:
        errors.append("deck reveal: artifacts hash binding mismatch")
    identities = reveal.get("identities")
    if identities != {"Cinder": "candidate", "Willow": "reference"} or reveal.get("revealedAfterScoring") is not True:
        errors.append("deck reveal: identities or post-review reveal state mismatch")
    labels = scorecard.get("labels", {})
    if set(labels) != set(identities or {}):
        errors.append("deck scorecard: labels do not match reveal")
    else:
        candidate_label = next((k for k, v in identities.items() if v == "candidate"), None)
        reference_label = next((k for k, v in identities.items() if v == "reference"), None)
        if labels[candidate_label].get("scores") != release["deck"].get("candidateScores"):
            errors.append("deck scorecard: candidate scores do not match release")
        if labels[reference_label].get("scores") != release["deck"].get("referenceScores"):
            errors.append("deck scorecard: reference scores do not match release")
    artifact_manifest = artifacts.get("anonymousManifest", {})
    for field, release_field in (("sha256", "anonymousManifestSha256"),
                                 ("inputSha256", "inputSha256"),
                                 ("blueprintSha256", "blueprintSha256")):
        if artifact_manifest.get(field) != release["deck"].get(release_field):
            errors.append(f"deck artifacts: {field} does not match release")
    candidate_artifact = artifacts.get("variants", {}).get("Cinder", {})
    if candidate_artifact.get("deckPdfSha256") != release["deck"].get("candidatePdfSha256"):
        errors.append("deck artifacts: candidate PDF hash mismatch")
    if candidate_artifact.get("crossMediaSha256") != release["deck"].get("candidateCrossMediaSha256"):
        errors.append("deck artifacts: candidate cross-media hash mismatch")

    a4 = release.get("a4", {})
    for field in ("status", "candidateDigest", "approvedBy", "approvedAt", "approvalReason", "scores"):
        if a4_evidence.get(field) != a4.get(field):
            errors.append(f"a4 evidence: {field} does not match release")
    if a4.get("reviewManifest") != evidence["a4Evidence"]["path"]:
        errors.append("a4 evidence: release reviewManifest must point to tracked compact evidence")
    if a4.get("reviewManifestSha256") != evidence["a4Evidence"]["sha256"]:
        errors.append("a4 evidence: release reviewManifest hash mismatch")
    if release.get("deck", {}).get("reviewPacket") != evidence["deckArtifacts"]["path"]:
        errors.append("deck evidence: release reviewPacket must point to tracked compact evidence")
    baseline_record = a4_evidence.get("baselineManifest", {})
    baseline_path = pathlib.Path(str(baseline_record.get("path", "")))
    if not baseline_path.is_absolute() and (root / baseline_path).is_file():
        baseline = load_json(root / baseline_path)
        if digest(root / baseline_path) != baseline_record.get("sha256"):
            errors.append("a4 evidence: baseline manifest hash mismatch")
        for field in ("status", "candidateDigest", "approvedBy", "approvedAt"):
            if baseline.get(field) != a4_evidence.get(field):
                errors.append(f"a4 evidence: baseline {field} mismatch")
    else:
        errors.append("a4 evidence: baseline manifest missing")

    scenario_record = scenario.get("scenarioManifest", {})
    scenario_path = pathlib.Path(str(scenario_record.get("path", "")))
    if not scenario_path.is_absolute() and (root / scenario_path).is_file():
        if digest(root / scenario_path) != scenario_record.get("sha256"):
            errors.append("scenario evidence: manifest hash mismatch")
        if scenario_record.get("sha256") != release.get("scenarios", {}).get("manifestSha256"):
            errors.append("scenario evidence: release manifest hash mismatch")
    else:
        errors.append("scenario evidence: manifest missing")
    return errors


def _commit_errors(root, release):
    errors = []
    commits = {"implementationHead": release.get("implementationHead")}
    provenance = release.get("provenance", {})
    for field in ("composerReferenceCommit", "finalBenchmarkIntegrityCommit", "a4ApprovalCommit"):
        commits[field] = provenance.get(field)
    for label, commit in commits.items():
        if not COMMIT.fullmatch(str(commit or "")):
            errors.append(f"commit {label}: invalid id")
            continue
        exists = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=root,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if exists.returncode:
            errors.append(f"commit {label}: does not exist")
            continue
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ancestor.returncode:
            errors.append(f"commit {label}: is not an ancestor of HEAD")
    return errors


def _tracked_path_errors(root, release):
    errors = []
    paths = [release.get("schema"), release.get("review"),
             release.get("capabilities", {}).get("matrix"),
             release.get("deck", {}).get("rebuildConfig")]
    for value in paths:
        if not _nonempty(value):
            errors.append("release tracked path: missing value")
            continue
        relative = pathlib.Path(value)
        if relative.is_absolute() or ".." in relative.parts or not (root / relative).is_file():
            errors.append(f"release tracked path: invalid or missing: {value}")
        elif not _is_tracked(root, relative):
            errors.append(f"release tracked path: not tracked: {value}")
    config = release.get("deck", {}).get("rebuildConfig")
    if _nonempty(config) and (root / config).is_file():
        if digest(root / config) != release["deck"].get("rebuildConfigSha256"):
            errors.append("deck: rebuild config hash mismatch")
    try:
        matrix = load_json(root / release["capabilities"]["matrix"])
    except (OSError, json.JSONDecodeError, KeyError) as error:
        errors.append(f"capability matrix: cannot read release evidence: {error}")
    else:
        matrix_evidence = matrix.get("release_evidence")
        if not isinstance(matrix_evidence, dict) or not matrix_evidence:
            errors.append("capability matrix: release_evidence must be a non-empty object")
        else:
            for label, value in matrix_evidence.items():
                if label.endswith("digest"):
                    if not SHA256.fullmatch(str(value)):
                        errors.append(f"capability matrix: invalid digest {label}")
                    continue
                relative = pathlib.Path(str(value))
                if relative.is_absolute() or ".." in relative.parts or not (root / relative).is_file():
                    errors.append(f"capability matrix: invalid release evidence path {label}: {value}")
                elif not _is_tracked(root, relative):
                    errors.append(f"capability matrix: untracked release evidence path {label}: {value}")
    return errors


def _schema_errors(root):
    try:
        schema = load_json(root / SCHEMA)
    except (OSError, json.JSONDecodeError) as error:
        return [f"release schema: cannot read: {error}"]
    errors = []
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        errors.append("release schema: root must be a closed object")
    if set(schema.get("required", [])) != ROOT_FIELDS:
        errors.append("release schema: required fields do not match canonical release fields")
    if set(schema.get("properties", {})) != ROOT_FIELDS:
        errors.append("release schema: properties do not match canonical release fields")
    return errors


def check(root):
    root = pathlib.Path(root).resolve()
    try:
        release = load_json(root / RELEASE)
    except (OSError, json.JSONDecodeError) as error:
        return [f"{RELEASE}: cannot read: {error}"]
    errors = validate_release_data(release)
    errors.extend(_schema_errors(root))
    errors.extend(check_evidence(root, release))
    errors.extend(report_capabilities.check(root, strict=True))
    errors.extend(_commit_errors(root, release))
    errors.extend(_tracked_path_errors(root, release))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check",))
    args = parser.parse_args(argv)
    del args
    root = pathlib.Path(__file__).resolve().parent.parent
    errors = check(root)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
