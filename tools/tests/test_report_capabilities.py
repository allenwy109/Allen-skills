import json
import io
import hashlib
import pathlib
import shutil
import subprocess
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
    def make_baseline_root(self):
        temporary = tempfile.TemporaryDirectory()
        root = pathlib.Path(temporary.name)
        showcase = root / "vendor" / "report-forge" / "docs" / "showcase"
        showcase.mkdir(parents=True)
        (showcase / "a.txt").write_bytes(b"alpha\n")
        (showcase / "nested").mkdir()
        (showcase / "nested" / "b.bin").write_bytes(b"\x00\x01")
        references = root / "references"
        references.mkdir()
        schema = ROOT / "references" / "visual-baseline.schema.json"
        if schema.exists():
            shutil.copy2(schema, references / schema.name)
        else:
            (references / schema.name).write_text(json.dumps({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "Upstream visual baseline",
                "type": "object",
                "required": ["version", "upstream_repo", "upstream_commit", "license",
                             "status", "approval", "artifacts"],
            }), encoding="utf-8")
        return temporary, root

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

    def test_check_rejects_directories_for_every_reference_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for name in ("upstream", "local", "tests", "visual"):
                (root / name).mkdir()
            capabilities = []
            for capability_id in sorted(REQUIRED_IDS):
                capability = self.capability(capability_id)
                capability.update({
                    "upstream_ref": "upstream",
                    "local_ref": "local",
                    "test": "tests",
                    "visual_evidence": "visual",
                })
                capabilities.append(capability)
            self.write_matrix(root, capabilities)

            errors = report_capabilities.check(root)

        for field in ("upstream_ref", "local_ref", "test", "visual_evidence"):
            self.assertTrue(any(f"{field} is not a file" in error for error in errors))

    def test_non_object_matrix_returns_stable_error_and_real_cli_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            matrix = root / "references" / "upstream-capability-matrix.json"
            matrix.parent.mkdir()
            matrix.write_text("[]\n", encoding="utf-8")

            self.assertEqual(report_capabilities.check(root), ["matrix: must be an object"])

            tools = root / "tools"
            tools.mkdir()
            (tools / "__init__.py").write_text("", encoding="utf-8")
            shutil.copy2(ROOT / "tools" / "report_capabilities.py", tools / "report_capabilities.py")
            result = subprocess.run(
                ["python3", str(tools / "report_capabilities.py"), "check"],
                capture_output=True, text=True,
            )
            shutil.copy2(ROOT / "tools" / "validate.py", tools / "validate.py")
            validation = subprocess.run(
                ["python3", str(tools / "validate.py")], capture_output=True, text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {
            "errors": ["matrix: must be an object"], "ok": False, "strict": False,
        })
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(validation.returncode, 1)
        self.assertIn("错误：report capabilities：matrix: must be an object", validation.stdout)
        self.assertNotIn("Traceback", validation.stderr)

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

    def test_generate_baseline_records_provenance_and_all_showcase_files(self):
        temporary, root = self.make_baseline_root()
        with temporary:
            baseline = report_capabilities.generate_baseline(root)
            self.assertEqual(baseline["upstream_commit"], "ee1f980c8dd7c53408e1a05a084229e6ec03c660")
            self.assertEqual(baseline["license"], "Apache-2.0")
            self.assertEqual(baseline["status"], "captured")
            self.assertEqual(baseline["approval"], "unapproved")
            self.assertTrue(baseline["artifacts"])
            self.assertEqual(
                {item["path"] for item in baseline["artifacts"]},
                {
                    "vendor/report-forge/docs/showcase/a.txt",
                    "vendor/report-forge/docs/showcase/nested/b.bin",
                },
            )
            for item in baseline["artifacts"]:
                artifact = root / item["path"]
                self.assertEqual(item["size"], artifact.stat().st_size)
                self.assertEqual(item["sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())

    def test_repository_baseline_schema_defines_required_contract(self):
        schema = json.loads((ROOT / "references" / "visual-baseline.schema.json").read_text())
        self.assertEqual(schema["type"], "object")
        self.assertEqual(set(schema["required"]), {
            "version", "upstream_repo", "upstream_commit", "license",
            "status", "approval", "artifacts",
        })
        self.assertEqual(set(schema["properties"]["artifacts"]["items"]["required"]), {
            "path", "sha256", "size",
        })

    def test_check_baseline_accepts_generated_manifest_and_rejects_tampering(self):
        temporary, root = self.make_baseline_root()
        with temporary:
            baseline = report_capabilities.generate_baseline(root)
            report_capabilities.write_baseline(root, baseline)
            self.assertEqual(report_capabilities.check_baseline(root), [])

            cases = {
                "bad hash": lambda data: data["artifacts"][0].update(sha256="0" * 64),
                "missing item": lambda data: data["artifacts"].pop(),
                "duplicate path": lambda data: data["artifacts"].append(dict(data["artifacts"][0])),
                "path escape": lambda data: data["artifacts"][0].update(path="../outside"),
                "directory": lambda data: data["artifacts"][0].update(path="vendor/report-forge/docs/showcase/nested"),
                "missing file": lambda data: data["artifacts"][0].update(path="vendor/report-forge/docs/showcase/nope"),
                "extra baseline field": lambda data: data.update(unexpected=True),
                "extra artifact field": lambda data: data["artifacts"][0].update(unexpected=True),
            }
            for label, mutate in cases.items():
                with self.subTest(label=label):
                    changed = json.loads(json.dumps(baseline))
                    mutate(changed)
                    report_capabilities.write_baseline(root, changed)
                    self.assertTrue(report_capabilities.check_baseline(root))

    def test_check_baseline_rejects_schema_errors(self):
        temporary, root = self.make_baseline_root()
        with temporary:
            baseline = report_capabilities.generate_baseline(root)
            baseline["version"] = 2
            report_capabilities.write_baseline(root, baseline)
            self.assertTrue(any("version" in error for error in report_capabilities.check_baseline(root)))

            (root / "references" / "visual-baseline.schema.json").write_text("{}\n", encoding="utf-8")
            self.assertTrue(any("schema" in error for error in report_capabilities.check_baseline(root)))

    def test_baseline_cli_is_stable_json_without_traceback(self):
        output = io.StringIO()
        with mock.patch.object(
            report_capabilities, "check_baseline", return_value=["baseline: broken"]
        ), redirect_stdout(output):
            code = report_capabilities.main(["baseline-check"])

        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue()), {"errors": ["baseline: broken"], "ok": False})
        self.assertNotIn("Traceback", output.getvalue())

    def test_baseline_check_cli_rejects_malformed_schema_without_traceback(self):
        canonical = json.loads(
            (ROOT / "references" / "visual-baseline.schema.json").read_text(encoding="utf-8")
        )
        approved_only = json.loads(json.dumps(canonical))
        approved_only["properties"]["approval"]["enum"] = ["approved"]
        empty_status = json.loads(json.dumps(canonical))
        empty_status["properties"]["status"]["enum"] = []
        missing_hash_pattern = json.loads(json.dumps(canonical))
        del missing_hash_pattern["properties"]["artifacts"]["items"]["properties"]["sha256"]["pattern"]
        missing_item_properties = json.loads(json.dumps(canonical))
        del missing_item_properties["properties"]["artifacts"]["items"]["properties"]
        malformed_schemas = {
            "numeric required": {
                "type": "object",
                "required": 7,
                "properties": {},
            },
            "null artifact items": {
                "type": "object",
                "required": ["version", "upstream_repo", "upstream_commit", "license",
                             "status", "approval", "artifacts"],
                "properties": {
                    "version": {}, "upstream_repo": {}, "upstream_commit": {},
                    "license": {}, "status": {}, "approval": {},
                    "artifacts": {"items": None},
                },
            },
            "approved only": approved_only,
            "empty status": empty_status,
            "missing hash pattern": missing_hash_pattern,
            "missing item properties": missing_item_properties,
        }
        for label, schema in malformed_schemas.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                tools = root / "tools"
                references = root / "references"
                tools.mkdir()
                references.mkdir()
                shutil.copy2(ROOT / "tools" / "report_capabilities.py",
                             tools / "report_capabilities.py")
                (references / "visual-baseline.schema.json").write_text(
                    json.dumps(schema), encoding="utf-8"
                )

                result = subprocess.run(
                    ["python3", str(tools / "report_capabilities.py"), "baseline-check"],
                    capture_output=True, text=True,
                )

                self.assertEqual(result.returncode, 1)
                payload = json.loads(result.stdout)
                self.assertFalse(payload["ok"])
                self.assertTrue(any("schema" in error for error in payload["errors"]))
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
