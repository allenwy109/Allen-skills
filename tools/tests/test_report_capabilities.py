import json
import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from tools import report_capabilities


ROOT = pathlib.Path(__file__).resolve().parents[2]
REQUIRED_IDS = {
    "layouts-38", "masters-6", "themes-3", "ratios-2", "form-catalog",
    "form-capacity", "chart-diversity", "layout-diversity", "module-fill",
    "representative-pages", "contact-sheet-worst-page", "html-pdf-page-review",
    "official-showcase", "showcase-build-scripts", "screenshot-manifest",
    "author-review", "independent-review", "review-reuse", "execution-plan",
    "resume-recovery", "narrative", "composition", "evidence-binding",
    "packaging", "upstream-contract-tests", "real-browser-tests",
}


class ReportCapabilitiesTests(unittest.TestCase):
    def write_matrix(self, root, capabilities, status="in-progress", phase="development"):
        path = root / "references" / "upstream-capability-matrix.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "phase": phase, "status": status, "capabilities": capabilities,
        }), encoding="utf-8")

    def capability(self, capability_id, status="parity"):
        return {
            "id": capability_id,
            "category": "contract",
            "upstream_ref": "evidence.txt",
            "local_ref": "evidence.txt",
            "test": "evidence.txt",
            "visual_evidence": "evidence.txt",
            "status": status,
        }

    def test_inspect_reads_upstream_assets(self):
        result = report_capabilities.inspect(ROOT)

        self.assertEqual(result["layout_count"], 38)
        self.assertEqual(result["master_count"], 6)
        self.assertEqual(set(result["themes"]), {"mckinsey", "bcg", "accenture"})
        self.assertEqual(set(result["ratios"]), {"16x9", "4x3"})
        self.assertTrue(result["showcase_files"])

    def test_check_accepts_repository_matrix(self):
        self.assertEqual(report_capabilities.check(ROOT), [])

    def test_check_rejects_empty_and_incomplete_capability_sets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self.write_matrix(root, [])
            empty_errors = report_capabilities.check(root)
            capabilities = [self.capability(item) for item in sorted(REQUIRED_IDS - {"packaging"})]
            (root / "evidence.txt").write_text("present", encoding="utf-8")
            self.write_matrix(root, capabilities)
            incomplete_errors = report_capabilities.check(root)

        self.assertTrue(any("missing capability ids:" in error for error in empty_errors))
        self.assertIn("matrix: missing capability ids: packaging", incomplete_errors)

    def test_check_rejects_extra_and_duplicate_capability_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "evidence.txt").write_text("present", encoding="utf-8")
            capabilities = [self.capability(item) for item in sorted(REQUIRED_IDS)]
            capabilities.extend([self.capability("layouts-38"), self.capability("unexpected")])
            self.write_matrix(root, capabilities)

            errors = report_capabilities.check(root)

        self.assertIn("layouts-38: duplicate id", errors)
        self.assertIn("matrix: extra capability ids: unexpected", errors)

    def test_check_rejects_missing_unknown_and_bad_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            matrix = {
                "phase": "development",
                "status": "in-progress",
                "capabilities": [
                    {
                        "id": "missing-capability",
                        "category": "layout",
                        "upstream_ref": "missing-upstream",
                        "local_ref": "missing-local",
                        "test": "missing-test",
                        "visual_evidence": "missing-visual",
                        "status": "missing",
                    },
                    {
                        "id": "unknown-capability",
                        "category": "theme",
                        "upstream_ref": "missing-upstream-2",
                        "local_ref": "missing-local-2",
                        "test": "missing-test-2",
                        "visual_evidence": "missing-visual-2",
                        "status": "unknown",
                    },
                ],
            }
            path = root / "references" / "upstream-capability-matrix.json"
            path.parent.mkdir()
            path.write_text(json.dumps(matrix), encoding="utf-8")

            errors = report_capabilities.check(root)

        self.assertTrue(any("missing-capability: status missing" in error for error in errors))
        self.assertTrue(any("unknown-capability: unknown status unknown" in error for error in errors))
        for field in ("upstream_ref", "local_ref", "test", "visual_evidence"):
            self.assertTrue(any(f"missing-capability: {field} does not exist" in error for error in errors))

    def test_default_and_strict_status_rules(self):
        cases = {
            "parity": (True, True),
            "superseded": (True, True),
            "untested": (True, False),
            "present-not-used": (True, False),
            "missing": (False, False),
        }
        for status, (default_allowed, strict_allowed) in cases.items():
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                evidence = root / "evidence.txt"
                evidence.write_text("present", encoding="utf-8")
                capabilities = [self.capability(item) for item in sorted(REQUIRED_IDS)]
                next(item for item in capabilities if item["id"] == "packaging")["status"] = status
                self.write_matrix(root, capabilities)

                default_errors = report_capabilities.check(root)
                strict_errors = report_capabilities.check(root, strict=True)

                self.assertEqual(not default_errors, default_allowed)
                self.assertEqual(not strict_errors, strict_allowed)

    def test_complete_status_and_release_phase_automatically_use_strict_rules(self):
        gates = (("development", "complete"), ("phase-4-release", "in-progress"))
        for phase, status in gates:
            with self.subTest(phase=phase, status=status), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                (root / "evidence.txt").write_text("present", encoding="utf-8")
                capabilities = [self.capability(item) for item in sorted(REQUIRED_IDS)]
                capabilities[0]["status"] = "untested"
                self.write_matrix(root, capabilities, status=status, phase=phase)

                errors = report_capabilities.check(root)

                self.assertTrue(any("status untested is not release-ready" in error for error in errors))

    def test_inspect_uses_public_js_exports_independent_of_formatting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            assets = root / "vendor" / "report-forge" / "assets"
            (assets / "layout-atlas").mkdir(parents=True)
            (assets / "layout-atlas" / "catalog.json").write_text(
                json.dumps({"layouts": [1], "masters": [1]}), encoding="utf-8"
            )
            (assets / "deck-themes.js").write_text(
                "module.exports = { ids : [ 'one', 'two' ] };\n", encoding="utf-8"
            )
            (assets / "deck-grid.js").write_text(
                "module.exports={ RATIOS : { 'wide' : {}, 'square' : {} } };\n", encoding="utf-8"
            )
            showcase = root / "vendor" / "report-forge" / "docs" / "showcase"
            showcase.mkdir(parents=True)
            (showcase / "example.png").write_bytes(b"png")

            result = report_capabilities.inspect(root)

        self.assertEqual(result["themes"], ["one", "two"])
        self.assertEqual(result["ratios"], ["square", "wide"])

    def test_inspect_and_cli_report_stable_errors_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            assets = root / "vendor" / "report-forge" / "assets"
            (assets / "layout-atlas").mkdir(parents=True)
            (assets / "layout-atlas" / "catalog.json").write_text(
                json.dumps({"layouts": [], "masters": []}), encoding="utf-8"
            )
            (assets / "deck-themes.js").write_text("invalid javascript", encoding="utf-8")
            (assets / "deck-grid.js").write_text("module.exports={RATIOS:{}}", encoding="utf-8")

            with self.assertRaisesRegex(report_capabilities.CapabilityError, "cannot inspect JavaScript"):
                report_capabilities.inspect(root)

        output = io.StringIO()
        with mock.patch.object(
            report_capabilities, "inspect", side_effect=report_capabilities.CapabilityError("broken assets")
        ), redirect_stdout(output):
            code = report_capabilities.main(["inspect"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload, {"error": "broken assets", "ok": False})
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
