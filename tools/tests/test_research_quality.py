import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCENE_PATHS = [
    ROOT / name / "SKILL.md"
    for name in ("scene-idea", "scene-company", "scene-topic", "scene-bp-review")
]
METHOD_TEMPLATE = ROOT / "core-method-select" / "assets" / "method-plan-template.md"
SHARED_GUIDE = ROOT / "core-evidence" / "references" / "decision-research-contracts.md"
REVIEW_PROMPTS = ROOT / "core-review" / "references" / "reviewer-prompts.md"
REVIEW_STANDARD = ROOT / "core-review" / "references" / "output-standard.md"
PRESSURE_CASES = ROOT / "tests" / "research-quality-cases.md"


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
            {"claim_ref": "cl-0001", "risk_type": "none", "narrowed": False, "limited_confidence": False,
             "issuer_source_ids": []},
            {"claim_ref": "cl-0002", "risk_type": "none", "narrowed": False, "limited_confidence": False,
             "issuer_source_ids": []},
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
    def test_research_scenes_route_material_questions_through_shared_contract(self):
        for path in SCENE_PATHS:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("decision-research.json", text)
                self.assertIn("research_quality.py", text)
                self.assertRegex(text, r"L2/L3|L2、L3|L2 和 L3")
                sequence = "core-review → research_quality check → core-synthesis"
                self.assertIn(sequence, text)
                self.assertLess(text.index("core-review", text.index(sequence)), text.index("research_quality check", text.index(sequence)))
                self.assertLess(text.index("research_quality check", text.index(sequence)), text.index("core-synthesis", text.index(sequence)))

    def test_method_plan_requires_prerequisite_status_output_and_downgrade(self):
        text = METHOD_TEMPLATE.read_text(encoding="utf-8")
        for field in ("前提状态", "实际产出", "降级理由"):
            self.assertIn(field, text)

    def test_shared_guide_covers_decision_research_judgments(self):
        text = SHARED_GUIDE.read_text(encoding="utf-8")
        self.assertIn("细分客户 → 触发情境 → 当前权宜办法 → 可观察后果 → 购买或切换信号 → 证据边界", text)
        for key in ("direct（直接）", "indirect（间接）", "diy（自建）", "adjacent（相邻）", "do_nothing（不行动）"):
            self.assertRegex(text, rf"(?m)^- {re.escape(key)}：")
        for method in ("3C", "五力 / 替代品", "STP", "定价三角", "客户旅程", "KSF / 能力差距"):
            self.assertRegex(text, rf"(?m)^\| {re.escape(method)} \|")
        self.assertIn("不强制全用", text)
        self.assertIn("issuer_source_ids", text)

    def test_review_rechecks_gate_and_challenges_known_failure_modes(self):
        prompts = REVIEW_PROMPTS.read_text(encoding="utf-8")
        standard = REVIEW_STANDARD.read_text(encoding="utf-8")
        self.assertIn("审查开始先独立运行 `python3 <运行时>/tools/research_quality.py check <任务文件夹>`", prompts)
        self.assertRegex(prompts, r"独立挑战发布方偏差：.*发行方、卖方或被评企业")
        self.assertRegex(prompts, r"检查是否漏了直接、间接、自建、相邻、不行动中的任何替代层")
        self.assertRegex(prompts, r"找出没有证据支持的强度措辞")
        self.assertRegex(prompts, r"是否只列方法名，却没有可检查的实际产出")
        self.assertIn("决策研究门禁失败", standard)

    def test_pressure_suite_contains_five_required_cases(self):
        text = PRESSURE_CASES.read_text(encoding="utf-8")
        cases = re.findall(r"(?ms)^## Case \d+：.*?(?=^## Case |\Z)", text)
        self.assertEqual(len(cases), 5)
        for expected_depth, case in zip(("L2", "L2", "L2", "L3", "L1"), cases):
            self.assertRegex(case, r"(?m)^- Depth: L[123]$")
            self.assertIn(f"- Depth: {expected_depth}", case)
            self.assertRegex(case, r"(?m)^- Input: \S.+$")
            required = re.search(r"(?ms)^- Required outcomes:\n((?:  - .+\n?)+)", case)
            forbidden = re.search(r"(?ms)^- Forbidden outcomes:\n((?:  - .+\n?)+)", case)
            self.assertIsNotNone(required)
            self.assertIsNotNone(forbidden)
            self.assertGreaterEqual(required.group(1).count("  - "), 2)
            self.assertGreaterEqual(forbidden.group(1).count("  - "), 1)
            self.assertRegex(required.group(1), r"QUALITY_|issuer_source_ids|purchase_signal|research_quality\.py|decision-research\.json")
            self.assertRegex(forbidden.group(1), r"(?m)^  - 不得")

    def test_complete_contract_passes(self):
        result = run_quality_check(valid_contract(), valid_ledger())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_material_pain_requires_purchase_signal(self):
        contract = valid_contract()
        contract["pain"][0].pop("purchase_signal")
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_PAIN_PURCHASE_SIGNAL", result.stderr)

    def test_material_pain_requires_at_least_one_pain_record(self):
        contract = valid_contract()
        contract["pain"] = []
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_PAIN_REQUIRED", result.stderr)

    def test_non_material_pain_accepts_empty_pain_records(self):
        contract = valid_contract()
        contract["material"]["pain"] = False
        contract["pain"] = []
        result = run_quality_check(contract, valid_ledger())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_material_competition_requires_all_substitute_layers(self):
        contract = valid_contract()
        contract["competition"]["layers"].pop("do_nothing")
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_COMPETITION_LAYER", result.stderr)

    def test_non_material_competition_accepts_empty_layers_and_criteria(self):
        contract = valid_contract()
        contract["material"]["competition"] = False
        contract["competition"] = {"layers": {}, "criteria": [], "claim_refs": []}
        result = run_quality_check(contract, valid_ledger())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_material_competition_requires_criteria(self):
        contract = valid_contract()
        contract["competition"]["criteria"] = []
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_COMPETITION_CRITERIA", result.stderr)

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

    def test_adversarial_search_claim_binding_uses_exact_id(self):
        ledger = valid_ledger(counterevidence=False, adversarial_search=True)
        ledger["search_log.jsonl"][0]["purpose"] = "adversarial check cl-00010"
        result = run_quality_check(valid_contract(), ledger)
        self.assertIn("QUALITY_CRITICAL_CLAIM", result.stderr)

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
        contract["claim_risk_assessments"][0]["issuer_source_ids"] = ["M001"]
        ledger = valid_ledger(issuer_only=True, statement="Buyers show strong commercial intent")
        result = run_quality_check(contract, ledger)
        self.assertIn("QUALITY_ISSUER_ONLY", result.stderr)

    def test_issuer_only_high_risk_claim_outside_critical_refs_is_rejected(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][1]["risk_type"] = "prevalence"
        contract["claim_risk_assessments"][1]["issuer_source_ids"] = ["M001"]
        result = run_quality_check(contract, valid_ledger(issuer_only=True))
        self.assertIn("QUALITY_ISSUER_ONLY", result.stderr)

    def test_ordinary_wording_does_not_bypass_structured_high_risk_check(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][0]["risk_type"] = "causality"
        contract["claim_risk_assessments"][0]["issuer_source_ids"] = ["M001"]
        result = run_quality_check(contract, valid_ledger(issuer_only=True, statement="Result improved after rollout"))
        self.assertIn("QUALITY_ISSUER_ONLY", result.stderr)

    def test_issuer_only_narrowed_low_confidence_claim_is_allowed(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][0].update(
            risk_type="competitive_intensity", narrowed=True, limited_confidence=True,
            issuer_source_ids=["M001"],
        )
        ledger = valid_ledger(issuer_only=True)
        ledger["claims.jsonl"][0]["confidence"] = "low"
        result = run_quality_check(contract, ledger)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_independent_buyer_company_source_is_not_treated_as_issuer(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][0]["risk_type"] = "willingness_to_pay"
        result = run_quality_check(contract, valid_ledger(issuer_only=True))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_issuer_source_is_rejected(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][0]["issuer_source_ids"] = ["M999"]
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_ISSUER_SOURCE", result.stderr)

    def test_issuer_source_must_support_assessed_claim(self):
        contract = valid_contract()
        contract["claim_risk_assessments"][1]["issuer_source_ids"] = ["M001"]
        ledger = valid_ledger()
        ledger["claim_evidence.jsonl"] = [
            link for link in ledger["claim_evidence.jsonl"]
            if not (link["claim_id"] == "cl-0002" and link["relation"] == "supports")
        ]
        result = run_quality_check(contract, ledger)
        self.assertIn("QUALITY_ISSUER_SOURCE", result.stderr)

    def test_every_referenced_claim_needs_risk_assessment(self):
        contract = valid_contract()
        contract["claim_risk_assessments"] = contract["claim_risk_assessments"][:1]
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_RISK_ASSESSMENT", result.stderr)

    def test_risk_assessment_claim_reference_must_resolve(self):
        contract = valid_contract()
        contract["claim_risk_assessments"].append(
            {"claim_ref": "cl-9999", "risk_type": "none", "narrowed": False, "limited_confidence": False,
             "issuer_source_ids": []}
        )
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_CLAIM_REF", result.stderr)

    def test_duplicate_risk_assessment_is_rejected(self):
        contract = valid_contract()
        contract["claim_risk_assessments"].append(dict(contract["claim_risk_assessments"][0]))
        result = run_quality_check(contract, valid_ledger())
        self.assertIn("QUALITY_RISK_ASSESSMENT", result.stderr)

    def test_non_object_jsonl_records_are_stable_ledger_errors(self):
        for filename in ("claims.jsonl", "claim_evidence.jsonl", "evidence.jsonl", "sources.jsonl", "search_log.jsonl"):
            with self.subTest(filename=filename):
                ledger = valid_ledger()
                ledger[filename] = [["not", "an", "object"]]
                result = run_quality_check(valid_contract(), ledger)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"QUALITY_LEDGER: {filename}:1", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
