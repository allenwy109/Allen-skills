"""Consulting-delivery contract adoption and one executable L3 journey."""
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "out-report/scripts"))
from out_report import review_digest  # noqa: E402
from tools.acceptance import Acceptance  # noqa: E402
from tools.e2e.test_report_outputs import read_json, run_cli  # noqa: E402
from tools.lib.ledger import Ledger, LedgerError  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402


PROJECT = ROOT / "tools/consulting_project.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ConsultingDeliveryContractTest(unittest.TestCase):
    def test_scenes_and_apps_adopt_the_shared_contract_by_reference(self):
        router = (ROOT / "router/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## 3.1 咨询交付合同", router)
        for name in ("scene-idea", "scene-company", "scene-bp-review", "scene-topic"):
            text = (ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("router 第 3.1 节", text, name)
            self.assertIn("L1", text, name)
        for name in ("allen-idea", "allen-company", "allen-bp-review", "allen-capital", "allen-ecosystem"):
            text = (ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("router 第 3.1 节", text, name)
        storyline = (ROOT / "core-storyline/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("skill-usage-manifest.json", storyline)
        self.assertIn("accepted", storyline)

    def test_l3_fixture_merges_only_accepted_research_and_packages_a_real_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = pathlib.Path(temporary) / "consulting-delivery"
            F.make_storyline_package(task)
            subprocess.run([sys.executable, str(PROJECT), "init", str(task), "--depth", "L3"], check=True)
            write_json(task / "research-coverage.json", {
                "version": 1, "subquestions": [{
                    "id": "SQ-1", "question": "Can verified growth support follow-up?", "material_pain": False,
                    "first_party_sources": ["M001"], "user_voice": [], "behavioral": [], "transaction": [],
                    "counter_evidence": ["M001"], "geography": "China", "time_period": "2024-2026",
                    "saturated": True, "limitations": ["Retention is not disclosed"], "unresolved_gaps": [],
                }],
            })
            write_json(task / "skill-usage-manifest.json", {
                "version": 1, "skills": [{
                    "skill": "lib-consulting", "method_cards": ["profit-tree"],
                    "prerequisites": ["two comparable periods"], "status": "adopted",
                    "inputs": ["03_evidence/ledger/metrics.jsonl"], "outputs": ["04_analysis/growth.md"],
                    "project_manager_disposition": "accepted",
                }],
            })
            write_json(task / "review-closure.json", {
                "version": 1, "issues": [{
                    "id": "REV-1", "reviewer": "fact-reviewer", "severity": "major",
                    "location": "growth conclusion", "remedy": "Narrowed the conclusion to verified revenue growth",
                    "remedy_evidence": ["cl-0001"], "re_reviewer": "fact-reviewer", "status": "closed",
                }],
            })
            lines = {
                "A": ("pain-and-sentiment", "Which recurring customer pains create observable urgency?", "accepted"),
                "B": ("competitors-and-substitutes", "Which direct, indirect and status-quo substitutes constrain adoption?", "accepted"),
                "C": ("market-and-data", "How large is the adjacent market?", "rejected"),
            }
            for code, (role, question, status) in lines.items():
                write_json(task / f"03r_research/tasks/{code}.json", {
                    "kind": "research_workstream", "version": 1, "code": code,
                    "role": role, "question": question,
                    "task_file": f"03r_research/tasks/{code}.md", "status": status,
                })
                write_json(task / f"research-handoffs/{code}.json", {
                    "version": 1, "line_id": code, "role": role,
                    "summary": f"Independent finding {code}", "source_ids": [], "data_files": [],
                    "supported_claims": [f"{code}-cl-0001"], "counter_evidence": ["none found"],
                    "limitations": ["synthetic fixture"], "unresolved_questions": ["none"],
                    "next_search_recommendation": "stop at saturation",
                    "project_manager_disposition": status,
                })
                staged = task / f"03_evidence/ledger/staging/{code}/claims.jsonl"
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_text(json.dumps({
                    "id": f"{code}-cl-0001", "kind": "fact", "statement": f"LINE-{code}-FINDING",
                    "scope": "consolidated", "period": "2024-2026", "population": "fixture",
                    "unit": "不适用：定性", "denominator": "不适用：定性", "calculation": "不适用：定性",
                    "inference": "fixture", "limitation": "synthetic fixture", "verification": "verified",
                    "confidence": "high", "confidence_reason": "fixture contract",
                    "affects_conclusion": False, "materiality": "minor",
                }, ensure_ascii=False) + "\n", encoding="utf-8")

            staged_a = task / "03_evidence/ledger/staging/A/claims.jsonl"
            reviewed_a = staged_a.read_bytes()
            with staged_a.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({
                    "id": "A-cl-9999", "kind": "fact", "statement": "SMUGGLED-UNREVIEWED-FINDING",
                    "scope": "consolidated", "period": "2024-2026", "population": "fixture",
                    "unit": "不适用：定性", "denominator": "不适用：定性", "calculation": "不适用：定性",
                    "inference": "fixture", "limitation": "synthetic fixture", "verification": "verified",
                    "confidence": "high", "confidence_reason": "fixture contract",
                    "affects_conclusion": False, "materiality": "minor",
                }, ensure_ascii=False) + "\n")
            staged_with_smuggling = staged_a.read_bytes()
            ledger_before = [item["statement"] for item in Ledger(task).read("claims")]
            with self.assertRaisesRegex(LedgerError, "A-cl-9999"):
                Ledger(task).merge("A")
            self.assertEqual(staged_with_smuggling, staged_a.read_bytes())
            self.assertEqual(ledger_before, [item["statement"] for item in Ledger(task).read("claims")])
            staged_a.write_bytes(reviewed_a)
            Ledger(task).merge("A")
            Ledger(task).merge("B")
            statements = [item["statement"] for item in Ledger(task).read("claims")]
            self.assertIn("LINE-A-FINDING", statements)
            self.assertIn("LINE-B-FINDING", statements)
            self.assertNotIn("LINE-C-FINDING", statements)
            with self.assertRaisesRegex(LedgerError, "accepted"):
                Ledger(task).merge("C")
            self.assertTrue((task / "03_evidence/ledger/staging/C").is_dir())
            self.assertNotIn("LINE-C-FINDING", [item["statement"] for item in Ledger(task).read("claims")])
            validated = subprocess.run(
                [sys.executable, str(PROJECT), "validate", str(task)], capture_output=True, text=True,
            )
            self.assertEqual(0, validated.returncode, validated.stdout + validated.stderr)

            initialized = run_cli("init", task)
            self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)
            render_document_path = task / "07_storyline/a4-work/render-document.json"
            render_document = read_json(render_document_path)
            exhibit_block = next(block for component in render_document["components"]
                                 for block in component["payload"].get("blocks", [])
                                 if "cl-0001" in block.get("claim_refs", []) and block.get("metric_refs"))
            exhibit_block["content"]["semantic_type"] = "decision-tree"
            exhibit_block["content"]["exhibit"] = {
                "kind": "decision-tree", "family": "decision-tree", "form": "svg.custom",
                "nodes": [{"id": "growth", "label": "收入增长已核实"}, {"id": "verify", "label": "核实客户留存"}],
                "edges": [{"from": "growth", "to": "verify", "label": "继续跟进"}],
            }
            action_block = next(block for component in render_document["components"]
                                for block in component["payload"].get("blocks", [])
                                if "cl-0004" in block.get("claim_refs", []))
            action_block["content"]["semantic_type"] = "30-60-90-roadmap"
            action_block["content"]["exhibit"] = {
                "kind": "30-60-90-roadmap", "family": "timeline", "form": "html.table",
                "stages": [{"label": "30 天", "output": "取得留存数据"},
                           {"label": "60 天", "output": "核实合同期限"},
                           {"label": "90 天", "output": "作出继续或停止决策"}],
            }
            write_json(render_document_path, render_document)
            rendered = run_cli("render", task)
            self.assertEqual(1, rendered.returncode, rendered.stdout + rendered.stderr)
            self.assertIn("REPORT_VISUAL_REGRESSION", rendered.stdout, rendered.stdout + rendered.stderr)
            work = task / "07_storyline/a4-work"
            regression = read_json(work / "visual-regression.json")
            artifacts = read_json(work / "artifact-manifest.json")
            pages = [page["id"] for page in read_json(work / "build/pagination-manifest.json")["pages"]]
            author_name = "Fixture author"
            write_json(work / "author.json", {
                "type": "author", "reviewer": author_name, "reviewedAt": "2026-10-28T10:00:00+10:30",
                "decision": "accepted", "reason": "Inspected every rendered page for hierarchy, evidence and pagination.",
                "baselineDigest": regression["baselineDigest"], "candidateDigest": regression["candidateDigest"],
                "differenceDigest": regression["differenceDigest"], "artifactDigest": artifacts["artifactDigest"],
                "paginationDigest": artifacts["paginationDigest"],
            })
            author_reviewed = run_cli("review", task, "author", work / "author.json")
            self.assertEqual(0, author_reviewed.returncode, author_reviewed.stdout + author_reviewed.stderr)
            issue = {
                "id": "RV-0001", "level": "major", "text": "Growth wording initially exceeded the evidence.",
                "reviewer": "Fixture visual reviewer", "resolved": True,
                "remedy": "Narrowed the statement to the two verified revenue periods.",
                "remedy_evidence": ["cl-0001"],
                "re_review": {"reviewer": "Fixture visual reviewer", "at": "2026-10-28T10:10:00+10:30",
                              "evidence": ["cl-0001"], "digest": ""},
            }
            issue["re_review"]["digest"] = review_digest(issue["re_review"])
            decision = {
                "reviewer": "Fixture decision maker", "role": "decision-maker-reviewer",
                "at": "2026-10-28T10:11:00+10:30",
                "answers": {key: "The final PDF provides a specific and actionable executive answer."
                            for key in ("answer_visibility", "executive_summary", "argument_sufficiency", "actions", "ownership", "continue_stop_thresholds")},
            }
            decision["review_digest"] = review_digest(decision)
            independent = {
                "type": "independent", "reviewer": "Fixture visual reviewer", "role": "visual-design-reviewer",
                "at": "2026-10-28T10:12:00+10:30", "conclusion": "The final media preserve the evidence-to-decision hierarchy.",
                "issues": [issue], "artifactDigest": artifacts["artifactDigest"],
                "paginationDigest": artifacts["paginationDigest"], "page_ids": pages,
                "media": ["html", "pdf"], "scales": ["100%", "contact-sheet"],
                "chapter_contact_sheets": [{"chapter": "whole-book", "page_ids": pages,
                    "observation": "The complete contact sheet has a consistent hierarchy and readable density."}],
                "headline_chain": {"status": "reviewed", "observation": "Headlines progress from evidence through judgment to action."},
                "worst_page": {"page_id": pages[-1], "finding": "The densest page remains legible and preserves the intended comparison."},
                "decision_review": decision,
                "observations": [{"page_id": page, "media": ["html", "pdf"], "scale": ["100%", "contact-sheet"],
                    "observation": f"{page} was inspected for hierarchy, evidence and exhibit integrity in both media.",
                    "reason": "No clipping, semantic omission or misleading visual emphasis remains."} for page in pages],
            }
            independent["review_digest"] = review_digest(independent)
            write_json(work / "independent.json", independent)
            reviewed = run_cli("review", task, "independent", work / "independent.json")
            self.assertEqual(0, reviewed.returncode, reviewed.stdout + reviewed.stderr)
            packaged = run_cli("package", task)
            self.assertEqual(0, packaged.returncode, packaged.stdout + packaged.stderr)

            report = next((task / "08_deliverables/client-report").glob("*.html"))
            html = report.read_text(encoding="utf-8")
            client_body = html.split("<body>", 1)[1]
            forbidden = {
                "raw URL": r"https?://", "references appendix": r"references-appendix|source-table|References and appendix",
                "source grade": r"source[-_ ]grade|grade\s*[=:]", "capture metadata": r"capture_method|captured_at|accessed_at",
                "internal research label": r"research-handoffs|skill-usage-manifest|review-closure|03r_research",
            }
            for label, pattern in forbidden.items():
                self.assertIsNone(re.search(pattern, client_body, re.IGNORECASE), label)
            self.assertIn('class="citation-marker" href="#source-M001">[1]</a>', client_body)
            self.assertEqual(1, client_body.count('class="compact-source-anchor" id="source-M001"'))
            exhibit = re.search(r'<[^>]+data-exhibit-kind="decision-tree"[^>]*>.*?</[^>]+>', html, re.DOTALL)
            self.assertIsNotNone(exhibit, "canonical decision-tree exhibit missing")
            exhibit_page = html[html.rfind('<section class="page"', 0, exhibit.start()):html.find('</section>', exhibit.end())]
            for binding in ('data-claim-id="cl-0001"', 'data-metric-id="m-0001"', 'data-source-id="M001"'):
                self.assertIn(binding, exhibit_page)
            self.assertTrue((task / "08_deliverables/evidence-package.zip").is_file())
            entry = next(item for item in Acceptance(task).load()["deliverables"] if item["id"] == "report-main")
            self.assertEqual("passed", entry["status"])
            self.assertEqual("visual-design-reviewer", entry["reviewer"]["role"])
            self.assertEqual("decision-maker-reviewer", entry["reviewer"]["decision_review"]["role"])


if __name__ == "__main__":
    unittest.main()
