#!/usr/bin/env python3
"""Validate a task's decision-research contract against its evidence ledger."""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib import schema_check


LAYERS = ("direct", "indirect", "diy", "adjacent", "do_nothing")
ADVERSARIAL = re.compile(r"adversarial|counter(?:example|evidence)?|disconfirm|反向|反证|反例|证伪", re.IGNORECASE)


def read_jsonl(path):
    if not path.is_file():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as err:
            raise ValueError(f"{path.name}:{number}: {err.msg}") from err
        if not isinstance(record, dict):
            raise ValueError(f"{path.name}:{number}: record must be an object")
        records.append(record)
    return records


def issue(code, message):
    return f"{code}: {message}"


def claim_refs(contract):
    refs = list(contract.get("critical_claim_refs", []))
    for pain in contract.get("pain", []):
        refs += pain.get("support_claim_refs", []) + pain.get("counter_claim_refs", [])
    competition = contract.get("competition", {})
    refs += competition.get("claim_refs", [])
    for options in competition.get("layers", {}).values():
        for option in options if isinstance(options, list) else []:
            refs += option.get("claim_refs", [])
    return refs


def valid_evidence_link(link, evidences, sources):
    evidence = evidences.get(link.get("evidence_id"))
    return bool(evidence and evidence.get("source_id") in sources)


def contains_claim_id(text, claim_id):
    return re.search(rf"(?<![A-Za-z0-9_-]){re.escape(claim_id)}(?![A-Za-z0-9_-])", text) is not None


def check(task):
    task = pathlib.Path(task)
    evidence = task / "03_evidence"
    contract_path = evidence / "decision-research.json"
    errors = []
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        return [issue("QUALITY_CONTRACT", str(err))]

    schema = schema_check.load("decision-research.schema.json")
    schema_errors = schema_check.check_document(schema, contract)
    for message in schema_errors:
        errors.append(issue("QUALITY_SCHEMA", message))

    if not isinstance(contract, dict):
        return errors
    material = contract.get("material") if isinstance(contract.get("material"), dict) else {}
    pains = contract.get("pain") if isinstance(contract.get("pain"), list) else []
    if material.get("pain"):
        if not pains:
            errors.append(issue("QUALITY_PAIN_REQUIRED", "material pain needs at least one pain record"))
        for pain in pains:
            if not isinstance(pain, dict):
                continue
            if not str(pain.get("purchase_signal", "")).strip():
                errors.append(issue("QUALITY_PAIN_PURCHASE_SIGNAL", f"{pain.get('id', '?')} lacks purchase_signal"))
            if not pain.get("counter_claim_refs") and not str(pain.get("adversarial_search_ref", "")).strip():
                errors.append(issue("QUALITY_PAIN_COUNTEREVIDENCE", f"{pain.get('id', '?')} needs counterevidence or adversarial search"))

    competition = contract.get("competition") if isinstance(contract.get("competition"), dict) else {}
    layers = competition.get("layers") if isinstance(competition.get("layers"), dict) else {}
    if material.get("competition"):
        if not competition.get("criteria"):
            errors.append(issue("QUALITY_COMPETITION_CRITERIA", "material competition needs comparison criteria"))
        for layer in LAYERS:
            options = layers.get(layer)
            if not isinstance(options, list) or not options:
                errors.append(issue("QUALITY_COMPETITION_LAYER", f"missing competition layer: {layer}"))
                continue
            for option in options:
                if not isinstance(option, dict):
                    continue
                named = bool(str(option.get("name", "")).strip())
                explicit_na = option.get("not_applicable") is True and bool(str(option.get("rationale", "")).strip())
                if not named and not explicit_na:
                    errors.append(issue("QUALITY_COMPETITION_LAYER", f"{layer} needs a named option or evidenced not_applicable record"))

    methods = contract.get("methods") if isinstance(contract.get("methods"), list) else []
    for method in methods:
        if isinstance(method, dict) and method.get("status") != "ready" and not str(method.get("downgrade_reason", "")).strip():
            errors.append(issue("QUALITY_METHOD_DOWNGRADE", f"{method.get('method', '?')} lacks downgrade_reason"))

    if schema_errors:
        return errors

    ledger = evidence / "ledger"
    try:
        claims = {x.get("id"): x for x in read_jsonl(ledger / "claims.jsonl")}
        links = read_jsonl(ledger / "claim_evidence.jsonl")
        evidences = {x.get("id"): x for x in read_jsonl(ledger / "evidence.jsonl")}
        sources = {x.get("id"): x for x in read_jsonl(ledger / "sources.jsonl")}
        searches = read_jsonl(ledger / "search_log.jsonl")
    except ValueError as err:
        return errors + [issue("QUALITY_LEDGER", str(err))]

    referenced = set(claim_refs(contract))
    assessments = contract.get("claim_risk_assessments", [])
    assessment_refs = [x["claim_ref"] for x in assessments]
    for ref in sorted(referenced | set(assessment_refs)):
        if ref not in claims:
            errors.append(issue("QUALITY_CLAIM_REF", f"unknown claim reference: {ref}"))

    searches_by_id = {x.get("id"): x for x in searches}
    for pain in pains:
        if not isinstance(pain, dict) or not pain.get("adversarial_search_ref"):
            continue
        search = searches_by_id.get(pain["adversarial_search_ref"])
        if not search or not ADVERSARIAL.search(f"{search.get('query', '')} {search.get('purpose', '')}"):
            errors.append(issue("QUALITY_PAIN_COUNTEREVIDENCE", f"{pain.get('id', '?')} has no valid adversarial search"))

    assessment_by_claim = {x["claim_ref"]: x for x in assessments}
    for ref in sorted({x for x in assessment_refs if assessment_refs.count(x) > 1}):
        errors.append(issue("QUALITY_RISK_ASSESSMENT", f"{ref} has duplicate risk assessments"))
    for ref in sorted(referenced - assessment_by_claim.keys()):
        errors.append(issue("QUALITY_RISK_ASSESSMENT", f"{ref} lacks explicit risk assessment"))

    for ref in contract.get("critical_claim_refs", []):
        if ref not in claims:
            continue
        related = [x for x in links if x.get("claim_id") == ref]
        supported = any(x.get("relation") == "supports" and valid_evidence_link(x, evidences, sources) for x in related)
        contradicted = any(x.get("relation") == "contradicts" and valid_evidence_link(x, evidences, sources) for x in related)
        searched = any(
            contains_claim_id(f"{x.get('query', '')} {x.get('purpose', '')}", ref) and
            ADVERSARIAL.search(f"{x.get('query', '')} {x.get('purpose', '')}")
            for x in searches
        )
        if not supported or not (contradicted or searched):
            errors.append(issue("QUALITY_CRITICAL_CLAIM", f"{ref} needs support and adversarial treatment"))

    for ref in sorted(referenced & assessment_by_claim.keys() & claims.keys()):
        assessment = assessment_by_claim[ref]
        support_links = [
            x for x in links
            if x.get("claim_id") == ref and x.get("relation") == "supports" and valid_evidence_link(x, evidences, sources)
        ]
        support_source_ids = {evidences[x["evidence_id"]]["source_id"] for x in support_links}
        issuer_source_ids = set(assessment.get("issuer_source_ids", []))
        for source_id in sorted(issuer_source_ids):
            if source_id not in sources:
                errors.append(issue("QUALITY_ISSUER_SOURCE", f"{ref} names unknown issuer source: {source_id}"))
            elif source_id not in support_source_ids:
                errors.append(issue("QUALITY_ISSUER_SOURCE", f"{source_id} does not support assessed claim {ref}"))
        if assessment["risk_type"] == "none":
            continue
        issuer_only = bool(support_source_ids) and support_source_ids <= issuer_source_ids
        exception = assessment["narrowed"] and assessment["limited_confidence"] and claims[ref].get("confidence") == "low"
        if issuer_only and not exception:
            errors.append(issue("QUALITY_ISSUER_ONLY", f"{ref} is a high-risk claim supported only by issuer sources"))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("check")
    command.add_argument("task")
    args = parser.parse_args(argv)
    errors = check(args.task)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("research quality check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
