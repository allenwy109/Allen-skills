"""A4 out-report workflow tests using a synthetic storyline and evidence ledger."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tools.acceptance import Acceptance  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402


def runtime_root():
    if (ROOT / "vendor/report-forge/node_modules/playwright").is_dir():
        return ROOT
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT,
                            check=True, capture_output=True, text=True).stdout.strip()
    return (ROOT / common).resolve().parent


def run(*args):
    env = dict(os.environ)
    env.setdefault("ALLEN_RUNTIME", str(runtime_root()))
    return subprocess.run([sys.executable, str(SCRIPTS / "out_report.py"), *map(str, args)],
                          capture_output=True, text=True, env=env)


def make_task(root, change=None):
    task = pathlib.Path(root) / "task"
    F.make_storyline_package(task)
    if change:
        source = task / "07_storyline/slides.json"
        doc = json.loads(source.read_text(encoding="utf-8"))
        change(doc)
        source.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return task


def missing():
    return [name for name in ("node", "pdfinfo", "pdftoppm", "pdftotext") if not shutil.which(name)] + F.missing_tools()


class A4OutReportPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.need = missing()
        if cls.need:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        cls.task = make_task(cls.tmp.name).resolve()
        cls.story = cls.task / "07_storyline"
        cls.work = cls.story / "a4-work"

    @classmethod
    def tearDownClass(cls):
        if not cls.need:
            cls.tmp.cleanup()

    def setUp(self):
        if self.need:
            message = "missing: " + ", ".join(self.need)
            if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
                self.fail(message)
            self.skipTest(message)

    def command(self, *args, expected=0):
        result = run(*args)
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        return result

    def test_a4_workflow_is_default_and_packages_audited_outputs(self):
        self.command("init", self.task)
        self.assertTrue((self.story / "report.json").is_file())
        self.assertTrue((self.work / "coverage-manifest.json").is_file())
        self.assertFalse((self.story / "forge-work/pages.html").exists())

        preview = self.command("render", self.task, expected=1)
        self.assertIn("REPORT_VISUAL_REGRESSION", preview.stdout)
        self.assertTrue((self.work / "build/report.html").is_file())
        pdf = self.work / "build/report.pdf"
        self.assertTrue(pdf.is_file())
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        self.assertRegex(info, r"Page size:\s+594\.96 x 841\.92 pts \(A4\)")
        self.assertFalse((self.story / "forge-work/pages.html").exists())

        regression = json.loads((self.work / "visual-regression.json").read_text(encoding="utf-8"))
        author = self.work / "author-review.json"
        author.write_text(json.dumps({
            "type": "author", "reviewer": "Synthetic author", "reviewedAt": "2026-10-27T12:00:00+10:30",
            "decision": "accepted", "reason": "Synthetic fixture visually reviewed",
            "baselineDigest": regression["baselineDigest"], "candidateDigest": regression["candidateDigest"],
            "differenceDigest": regression["differenceDigest"],
        }), encoding="utf-8")
        self.command("review", self.task, "author", author)

        independent = self.work / "independent-review.json"
        independent.write_text(json.dumps({
            "type": "independent", "reviewer": "Synthetic independent reviewer",
            "at": "2026-10-27T12:05:00+10:30", "conclusion": "Synthetic fixture accepted", "issues": [],
        }), encoding="utf-8")
        self.command("review", self.task, "independent", independent)
        self.command("package", self.task)

        out = self.task / "08_deliverables/report"
        for name in ("report.html", "report.pdf", "coverage-manifest.json", "pagination-manifest.json",
                     "geometry-manifest.json", "visual-regression.json", "qa-result.json"):
            self.assertTrue((out / name).is_file(), name)
        entry = next(item for item in Acceptance(self.task).load()["deliverables"] if item["id"] == "report-main")
        names = [check["name"] for check in entry["upstream_checks"]]
        self.assertEqual(names, ["storyline", "coverage", "pagination", "geometry", "visual-regression", "author-review", "independent-review"])
        self.assertEqual([check["result"] for check in entry["upstream_checks"]], ["passed"] * 7)

    def test_package_fails_closed_before_both_reviews(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary)
            self.assertEqual(0, run("init", task).returncode)
            self.assertEqual(1, run("render", task).returncode)
            result = run("package", task)
            self.assertEqual(1, result.returncode)
            self.assertIn("author-review", result.stderr)
            self.assertIn("independent-review", result.stderr)


class A4OutReportContractTest(unittest.TestCase):
    def test_skill_routes_reports_to_a4_not_forge_author_pages(self):
        text = (ROOT / "out-report/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("A4", text)
        self.assertNotIn("forge-work/pages.html", text)
        self.assertNotIn("作者写 `forge-work/pages.html`", text)

    def test_invalid_storyline_does_not_create_a4_work(self):
        def change(doc):
            doc["slides"][1]["panels"][0]["form"] = "unsupported.form"
        with tempfile.TemporaryDirectory() as temporary:
            task = make_task(temporary, change)
            result = run("init", task)
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertIn("REPORT_UNSUPPORTED_BLOCK", result.stderr)
            self.assertFalse((task / "07_storyline/a4-work").exists())


if __name__ == "__main__":
    unittest.main()
