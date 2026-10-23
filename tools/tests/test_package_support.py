import json
import pathlib
import tempfile
import unittest
import zipfile

from tools import package_support as P


class PackageSupportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name) / "task"
        self.task.mkdir()
        (self.task / "app-run.json").write_text(
            json.dumps({"app_id": "allen-company"}), encoding="utf-8"
        )
        (self.task / "00_brief.md").write_text("brief", encoding="utf-8")
        (self.task / "04_analysis").mkdir()
        (self.task / "04_analysis" / "market.md").write_text("market", encoding="utf-8")
        (self.task / "04_analysis" / "internal").mkdir()
        (self.task / "04_analysis" / "internal" / "candidate-list.csv").write_text("secret", encoding="utf-8")
        (self.task / "03_evidence" / "raw" / "user").mkdir(parents=True)
        (self.task / "03_evidence" / "raw" / "user" / "bp.pdf").write_bytes(b"pdf")

    def tearDown(self):
        self.tmp.cleanup()

    def names(self):
        with zipfile.ZipFile(self.task / "08_deliverables" / "supporting-package.zip") as archive:
            return set(archive.namelist()), json.loads(archive.read("supporting-package/manifest.json"))

    def test_default_package_excludes_raw_and_internal_files(self):
        result = P.build(self.task)
        self.assertEqual(result["acceptance_id"], "support-company")
        self.assertEqual(result["status"], "failed")  # 独立成品审查前不能交付
        names, manifest = self.names()
        self.assertIn("supporting-package/00_brief.md", names)
        self.assertIn("supporting-package/04_analysis/market.md", names)
        self.assertNotIn("supporting-package/04_analysis/internal/candidate-list.csv", names)
        self.assertNotIn("supporting-package/03_evidence/raw/user/bp.pdf", names)
        self.assertFalse(manifest["includes_raw_materials"])

    def test_include_raw_is_explicit(self):
        P.build(self.task, include_raw=True)
        names, manifest = self.names()
        self.assertIn("supporting-package/03_evidence/raw/user/bp.pdf", names)
        self.assertTrue(manifest["includes_raw_materials"])

    def test_requires_valid_app_run(self):
        (self.task / "app-run.json").unlink()
        with self.assertRaises(P.PackageError):
            P.build(self.task)


if __name__ == "__main__":
    unittest.main()
