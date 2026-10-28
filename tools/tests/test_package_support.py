import json
import pathlib
import tempfile
import unittest
import zipfile
import subprocess
import sys
import shutil

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
        (self.task / "03_evidence" / "raw" / "sources").mkdir(parents=True)
        (self.task / "03_evidence" / "raw" / "sources" / "M001.md").write_text("snapshot M001", encoding="utf-8")
        (self.task / "03_evidence" / "ledger").mkdir()
        (self.task / "03_evidence" / "ledger" / "sources.jsonl").write_text('{"id":"M001"}\n', encoding="utf-8")
        (self.task / "03_evidence" / "data" / "calculations").mkdir(parents=True)
        (self.task / "03_evidence" / "data" / "calculations" / "model.csv").write_text("claim_id,value\ncl-1,1\n", encoding="utf-8")
        (self.task / "03r_research" / "work" / "search-logs").mkdir(parents=True)
        (self.task / "03r_research" / "work" / "search-logs" / "M.md").write_text("query", encoding="utf-8")
        (self.task / "05_reviews").mkdir()
        (self.task / "05_reviews" / "independent.json").write_text("{}", encoding="utf-8")
        (self.task / "07_storyline" / "a4-work" / "build").mkdir(parents=True)
        (self.task / "07_storyline" / "a4-work" / "coverage-manifest.json").write_text("{}", encoding="utf-8")
        (self.task / "07_storyline" / "a4-work" / "build" / "cache.bin").write_bytes(b"cache")
        (self.task / ".backup").mkdir()
        (self.task / ".backup" / "secret.txt").write_text("secret", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def names(self):
        with zipfile.ZipFile(self.task / "08_deliverables" / "evidence-package.zip") as archive:
            return set(archive.namelist()), json.loads(archive.read("evidence-package/package-manifest.json"))

    def test_default_package_excludes_raw_and_internal_files(self):
        result = P.build(self.task)
        self.assertEqual(result["acceptance_id"], "evidence-company")
        self.assertEqual(result["status"], "failed")  # 独立成品审查前不能交付
        names, manifest = self.names()
        self.assertIn("evidence-package/00_brief.md", names)
        self.assertIn("evidence-package/04_analysis/market.md", names)
        self.assertIn("evidence-package/source-index.md", names)
        self.assertIn("evidence-package/03_evidence/raw/sources/M001.md", names)
        self.assertIn("evidence-package/03_evidence/ledger/sources.jsonl", names)
        self.assertIn("evidence-package/03_evidence/data/calculations/model.csv", names)
        self.assertIn("evidence-package/03r_research/work/search-logs/M.md", names)
        self.assertIn("evidence-package/05_reviews/independent.json", names)
        self.assertIn("evidence-package/07_storyline/a4-work/coverage-manifest.json", names)
        self.assertIn("evidence-package/checksums-sha256.txt", names)
        self.assertNotIn("evidence-package/04_analysis/internal/candidate-list.csv", names)
        self.assertNotIn("evidence-package/03_evidence/raw/user/bp.pdf", names)
        self.assertFalse(any(".backup" in name or "cache.bin" in name or "/build/" in name for name in names))
        self.assertFalse(manifest["includes_raw_materials"])

        with tempfile.TemporaryDirectory() as extracted:
            with zipfile.ZipFile(self.task / "08_deliverables/evidence-package.zip") as archive:
                archive.extractall(extracted)
            package = pathlib.Path(extracted) / "evidence-package"
            subprocess.run([sys.executable, str(pathlib.Path(P.__file__)), "--verify", package], check=True)

    def test_include_raw_is_explicit(self):
        P.build(self.task, include_raw=True)
        names, manifest = self.names()
        self.assertIn("evidence-package/03_evidence/raw/user/bp.pdf", names)
        self.assertTrue(manifest["includes_raw_materials"])

    def test_requires_valid_app_run(self):
        (self.task / "app-run.json").unlink()
        with self.assertRaises(P.PackageError):
            P.build(self.task)

    def test_generic_report_package_fails_without_source_ledger(self):
        shutil.rmtree(self.task / "03_evidence/ledger")
        with self.assertRaisesRegex(P.PackageError, "sources.jsonl"):
            P.build(self.task, require_app=False)

    def test_verify_rejects_missing_tampered_extra_and_manifest_mismatch(self):
        P.build(self.task)
        source = self.task / "08_deliverables/evidence-package"
        for mutation in ("deleted", "tampered", "extra", "manifest-size", "empty-checksums"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                package = pathlib.Path(temporary) / "package"
                shutil.copytree(source, package)
                target = package / "00_brief.md"
                if mutation == "deleted":
                    target.unlink()
                elif mutation == "tampered":
                    target.write_text("changed", encoding="utf-8")
                elif mutation == "extra":
                    (package / "unlisted.txt").write_text("extra", encoding="utf-8")
                elif mutation == "manifest-size":
                    manifest = json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))
                    next(item for item in manifest["files"] if item["path"] == "00_brief.md")["size"] += 1
                    (package / "package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                else:
                    (package / "checksums-sha256.txt").write_text("", encoding="utf-8")
                with self.assertRaises(P.PackageError):
                    P.verify(package)


if __name__ == "__main__":
    unittest.main()
