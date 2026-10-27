import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def valid_contract():
    option = {"name": "Example vendor", "claim_refs": ["cl-0001"]}
    return {
        "version": 1,
        "material": {"pain": True, "competition": True, "pricing": True},
        "pain": [{
            "id": "pain-1", "segment": "SMB finance teams", "trigger": "month end",
            "workaround": "spreadsheets", "consequence": "two days of rework",
            "purchase_signal": "issued an RFP", "support_claim_refs": ["cl-0001"],
            "counter_claim_refs": ["cl-0002"], "confidence": "medium",
            "validation_gap": "sample is small",
        }],
        "competition": {
            "layers": {name: [dict(option)] for name in ("direct", "indirect", "diy", "adjacent", "do_nothing")},
            "criteria": ["total cost", "deployment effort"],
            "claim_refs": ["cl-0001"],
        },
        "methods": [{
            "question": "How do buyers choose?", "method": "3C", "prerequisites": ["buyer interviews"],
            "status": "ready", "output": "segment comparison",
        }],
        "critical_claim_refs": ["cl-0001"],
        "claim_risk_assessments": [
            {"claim_ref": "cl-0001", "risk_type": "none", "narrowed": False, "limited_confidence": False},
            {"claim_ref": "cl-0002", "risk_type": "none", "narrowed": False, "limited_confidence": False},
        ],
    }


def valid_ledger(*, counterevidence=True, adversarial_search=False, issuer_only=False, statement="Observed demand exists"):
    source = {
        "id": "M001", "origin": "web", "title": "Customer research", "source_type": "company" if issuer_only else "academic",
    }
    records = {
        "sources.jsonl": [source],
        "evidence.jsonl": [
            {"id": "ev-0001", "source_id": "M001"},
            {"id": "ev-0002", "source_id": "M001"},
        ],
        "claims.jsonl": [
            {"id": "cl-0001", "statement": statement, "confidence": "medium", "limitation": "one segment"},
            {"id": "cl-0002", "statement": "Some buyers prefer spreadsheets", "confidence": "medium", "limitation": "one segment"},
        ],
        "claim_evidence.jsonl": [
            {"id": "ce-0001", "claim_id": "cl-0001", "evidence_id": "ev-0001", "relation": "supports"},
            {"id": "ce-0003", "claim_id": "cl-0002", "evidence_id": "ev-0001", "relation": "supports"},
        ],
        "search_log.jsonl": [],
    }
    if counterevidence:
        records["claim_evidence.jsonl"].append(
            {"id": "ce-0002", "claim_id": "cl-0001", "evidence_id": "ev-0002", "relation": "contradicts"}
        )
    if adversarial_search:
        records["search_log.jsonl"].append(
            {"id": "SL-0001", "query": "counterexample to observed demand", "purpose": "adversarial check cl-0001"}
        )
    return records


def run_quality_check(contract, ledger):
    temp = tempfile.TemporaryDirectory()
    task = pathlib.Path(temp.name)
    ledger_dir = task / "03_evidence" / "ledger"
    ledger_dir.mkdir(parents=True)
    (task / "03_evidence" / "decision-research.json").write_text(json.dumps(contract), encoding="utf-8")
    for filename, records in ledger.items():
        text = "".join(json.dumps(record) + "\n" for record in records)
        (ledger_dir / filename).write_text(text, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "research_quality.py"), "check", str(task)],
        cwd=ROOT, capture_output=True, text=True,
    )
    temp.cleanup()
    return result


class ResearchQualityTest(unittest.TestCase):
    def test_complete_contract_passes(self):
        result = run_quality_check(valid_contract(), valid_ledger())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_material_pain_requires_purchase_signal(self):
        contract = valid_contract()
        contract["pain"][0].pop("purchase_signal")
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_PAIN_PURCHASE_SIGNAL", result.stderr)

    def test_material_competition_requires_all_substitute_layers(self):
        contract = valid_contract()
        contract["competition"]["layers"].pop("do_nothing")
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_COMPETITION_LAYER", result.stderr)

    def test_critical_claim_requires_adversarial_treatment(self):
        result = run_quality_check(valid_contract(), valid_ledger(counterevidence=False, adversarial_search=False))
        self.assertIn("QUALITY_CRITICAL_CLAIM", result.stderr)

    def test_critical_claim_without_support_is_rejected(self):
        ledger = valid_ledger()
        ledger["claim_evidence.jsonl"] = [x for x in ledger["claim_evidence.jsonl"] if x["claim_id"] != "cl-0001"]
        result = run_quality_check(valid_contract(), ledger)
        self.assertIn("QUALITY_CRITICAL_CLAIM", result.stderr)

    def test_critical_support_requires_resolvable_source(self):
        ledger = valid_ledger()
        ledger["sources.jsonl"] = []
        result = run_quality_check(valid_contract(), ledger)
        self.assertIn("QUALITY_CRITICAL_CLAIM", result.stderr)

    def test_adversarial_search_can_replace_counterevidence(self):
        contract = valid_contract()
        contract["pain"][0]["counter_claim_refs"] = []
        contract["pain"][0]["adversarial_search_ref"] = "SL-0001"
        result = run_quality_check(contract, valid_ledger(counterevidence=False, adversarial_search=True))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_material_pain_requires_counter_claim_or_adversarial_search(self):
        contract = valid_contract()
        contract["pain"][0]["counter_claim_refs"] = []
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_PAIN_COUNTEREVIDENCE", result.stderr)
        self.assertNotEqual(result.returncode, 0)

    def test_unknown_claim_reference_is_rejected(self):
        contract = valid_contract()
        contract["pain"][0]["support_claim_refs"] = ["cl-9999"]
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_CLAIM_REF", result.stderr)

    def test_downgraded_method_requires_reason(self):
        contract = valid_contract()
        contract["methods"][0]["status"] = "hypothesis"
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_METHOD_DOWNGRADE", result.stderr)

    def test_issuer_only_high_risk_claim_is_rejected(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][0]["risk_type"] = "willingness_to_pay"
        ledger = valid_ledger(issuer_only=True, statement="Buyers show strong commercial intent")
        result = run_quality_check(contract, ledger)
        self.assertIn("QUALITY_ISSUER_ONLY", result.stderr)

    def test_issuer_only_high_risk_claim_outside_critical_refs_is_rejected(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][1]["risk_type"] = "prevalence"
        result = run_quality_check(contract, valid_ledger(issuer_only=True))
        self.assertIn("QUALITY_ISSUER_ONLY", result.stderr)

    def test_ordinary_wording_does_not_bypass_structured_high_risk_check(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][0]["risk_type"] = "causality"
        result = run_quality_check(contract, valid_ledger(issuer_only=True, statement="Result improved after rollout"))
        self.assertIn("QUALITY_ISSUER_ONLY", result.stderr)

    def test_issuer_only_narrowed_low_confidence_claim_is_allowed(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][0].update(
            risk_type="competitive_intensity", narrowed=True, limited_confidence=True
        )
        ledger = valid_ledger(issuer_only=True)
        ledger["claims.jsonl"][0]["confidence"] = "low"
        result = run_quality_check(contract, ledger)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_referenced_claim_needs_risk_assessment(self):
        contract = valid_contract()
        contract["claim_risk_assessments"] = contract["claim_risk_assessments"][:1]
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_RISK_ASSESSMENT", result.stderr)

    def test_risk_assessment_claim_reference_must_resolve(self):
        contract = valid_contract()
        contract["claim_risk_assessments"].append(
            {"claim_ref": "cl-9999", "risk_type": "none", "narrowed": False, "limited_confidence": False}
        )
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_CLAIM_REF", result.stderr)

    def test_duplicate_risk_assessment_is_rejected(self):
        contract = valid_contract()
        contract["claim_risk_assessments"].append(dict(contract["claim_risk_assessments"][0]))
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_RISK_ASSESSMENT", result.stderr)


if __name__ == "__main__":
    unittest.main()
