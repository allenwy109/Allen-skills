import json
import pathlib
import tempfile
import unittest

from tools import report_capabilities


ROOT = pathlib.Path(__file__).resolve().parents[2]


class ReportCapabilitiesTests(unittest.TestCase):
    def test_inspect_reads_upstream_assets(self):
        result = report_capabilities.inspect(ROOT)

        self.assertEqual(result["layout_count"], 38)
        self.assertEqual(result["master_count"], 6)
        self.assertEqual(set(result["themes"]), {"mckinsey", "bcg", "accenture"})
        self.assertEqual(set(result["ratios"]), {"16x9", "4x3"})
        self.assertTrue(result["showcase_files"])

    def test_check_accepts_repository_matrix(self):
        self.assertEqual(report_capabilities.check(ROOT), [])

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

    def test_default_check_allows_development_statuses_but_strict_rejects_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("present", encoding="utf-8")
            matrix = {
                "phase": "development",
                "status": "in-progress",
                "capabilities": [
                    {
                        "id": "planned-capability",
                        "category": "contract",
                        "upstream_ref": "evidence.txt",
                        "local_ref": "evidence.txt",
                        "test": "evidence.txt",
                        "visual_evidence": "evidence.txt",
                        "status": "untested",
                    }
                ],
            }
            path = root / "references" / "upstream-capability-matrix.json"
            path.parent.mkdir()
            path.write_text(json.dumps(matrix), encoding="utf-8")

            self.assertEqual(report_capabilities.check(root), [])
            strict_errors = report_capabilities.check(root, strict=True)

        self.assertEqual(strict_errors, ["planned-capability: status untested is not release-ready"])


if __name__ == "__main__":
    unittest.main()
