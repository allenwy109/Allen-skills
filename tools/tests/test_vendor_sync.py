import json
import pathlib
import subprocess
import tempfile
import unittest

from tools import vendor_sync


class VendorConfigTest(unittest.TestCase):
    def test_report_forge_showcase_is_included(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        config = json.loads((root / "vendor" / "vendor.config.json").read_text(encoding="utf-8"))
        self.assertNotIn("docs/showcase/", config["engines"]["report-forge"]["exclude"])


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def make_upstream(root):
    """建一个本地上游仓库：两个引擎目录，含要排除的文件。返回 (仓库路径, commit)。"""
    repo = root / "upstream"
    (repo / "eng-a" / "docs" / "showcase").mkdir(parents=True)
    (repo / "eng-a" / "SKILL.md").write_text("---\nname: eng-a\n---\n", encoding="utf-8")
    (repo / "eng-a" / "a.txt").write_text("alpha\n", encoding="utf-8")
    (repo / "eng-a" / "docs" / "guide.md").write_text("guide\n", encoding="utf-8")
    (repo / "eng-a" / "docs" / "showcase" / "big.bin").write_bytes(b"x" * 10)
    (repo / "eng-b").mkdir()
    (repo / "eng-b" / "b.txt").write_text("beta\n", encoding="utf-8")
    (repo / "eng-b" / "sample.pdf").write_bytes(b"%PDF")
    git(repo, "init", "-q")
    git(repo, "config", "uploadpack.allowReachableSHA1InWant", "true")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return repo, commit


def make_config(repo, commit):
    return {
        "repo": repo.as_uri(),
        "commit": commit,
        "generated": ["node_modules/", "__pycache__/"],
        "engines": {
            "a": {"upstream": "eng-a", "exclude": ["docs/showcase/"]},
            "b": {"upstream": "eng-b", "exclude": ["sample.*"]},
        },
    }


class MatchesTest(unittest.TestCase):
    def test_directory_pattern_without_slash_matches_any_component(self):
        self.assertTrue(vendor_sync.matches("x/__pycache__/m.pyc", ["__pycache__/"]))
        self.assertTrue(vendor_sync.matches("node_modules/p/index.js", ["node_modules/"]))

    def test_directory_pattern_with_slash_matches_prefix_only(self):
        self.assertTrue(vendor_sync.matches("docs/showcase/a.png", ["docs/showcase/"]))
        self.assertFalse(vendor_sync.matches("other/docs/showcase/a.png", ["docs/showcase/"]))

    def test_glob_pattern(self):
        self.assertTrue(vendor_sync.matches("sample.pdf", ["sample.*"]))
        self.assertFalse(vendor_sync.matches("b.txt", ["sample.*"]))


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.repo, self.commit = make_upstream(root)
        self.cfg = make_config(self.repo, self.commit)
        self.vendor = root / "vendor"
        (self.vendor / "patches").mkdir(parents=True)
        self.cache = root / "cache"

    def tearDown(self):
        self.tmp.cleanup()

    def test_sync_copies_renames_excludes_and_locks(self):
        lock = vendor_sync.sync(self.cfg, self.vendor, self.cache)
        a = self.vendor / "a"
        self.assertTrue((a / "UPSTREAM-SKILL.md").is_file())
        self.assertFalse((a / "SKILL.md").exists())
        self.assertTrue((a / "docs" / "guide.md").is_file())
        self.assertFalse((a / "docs" / "showcase").exists())
        self.assertFalse((self.vendor / "b" / "sample.pdf").exists())
        self.assertEqual(lock["commit"], self.commit)
        self.assertEqual(set(lock["engines"]["a"]["files"]), {"UPSTREAM-SKILL.md", "a.txt", "docs/guide.md"})
        self.assertEqual(lock["engines"]["a"]["files"]["a.txt"], vendor_sync.sha256(a / "a.txt"))
        on_disk = json.loads((self.vendor / "vendor.lock").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, lock)

    def test_check_passes_after_sync(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        self.assertEqual(vendor_sync.check(self.vendor), [])

    def test_check_reports_modified_missing_extra_and_skill_md(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        (self.vendor / "a" / "a.txt").write_text("changed\n", encoding="utf-8")
        (self.vendor / "b" / "b.txt").unlink()
        (self.vendor / "b" / "extra.txt").write_text("x", encoding="utf-8")
        (self.vendor / "a" / "SKILL.md").write_text("x", encoding="utf-8")
        errors = "\n".join(vendor_sync.check(self.vendor))
        self.assertIn("文件被改动：a/a.txt", errors)
        self.assertIn("缺少文件：b/b.txt", errors)
        self.assertIn("未登记的文件：b/extra.txt", errors)
        self.assertIn("a/SKILL.md 不应存在", errors)

    def test_check_ignores_generated_files(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        nm = self.vendor / "a" / "node_modules" / "p"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("x", encoding="utf-8")
        self.assertEqual(vendor_sync.check(self.vendor), [])

    def test_patches_are_applied_and_recorded(self):
        patch = (
            "--- a/a/a.txt\n"
            "+++ b/a/a.txt\n"
            "@@ -1 +1 @@\n"
            "-alpha\n"
            "+alpha patched\n"
        )
        (self.vendor / "patches" / "0001-test.patch").write_text(patch, encoding="utf-8")
        lock = vendor_sync.sync(self.cfg, self.vendor, self.cache)
        self.assertEqual((self.vendor / "a" / "a.txt").read_text(encoding="utf-8"), "alpha patched\n")
        self.assertEqual([p["name"] for p in lock["patches"]], ["0001-test.patch"])
        self.assertEqual(vendor_sync.check(self.vendor), [])

    def test_check_without_lock(self):
        errors = vendor_sync.check(self.vendor)
        self.assertEqual(len(errors), 1)
        self.assertIn("缺少", errors[0])

    def test_missing_upstream_dir_is_an_error(self):
        self.cfg["engines"]["c"] = {"upstream": "eng-missing", "exclude": []}
        with self.assertRaises(SystemExit):
            vendor_sync.sync(self.cfg, self.vendor, self.cache)

    def test_conflicting_patch_is_an_error(self):
        patch = "--- a/a/a.txt\n+++ b/a/a.txt\n@@ -1 +1 @@\n-not the content\n+x\n"
        (self.vendor / "patches" / "0001-bad.patch").write_text(patch, encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError):
            vendor_sync.sync(self.cfg, self.vendor, self.cache)

    def test_check_detects_patch_changes_after_sync(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        (self.vendor / "patches" / "0002-new.patch").write_text("x", encoding="utf-8")
        self.assertIn("补丁与 vendor.lock 不一致", "\n".join(vendor_sync.check(self.vendor)))

    def test_check_detects_unknown_engine_dir(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        (self.vendor / "stray").mkdir()
        self.assertIn("未登记的引擎目录：stray", "\n".join(vendor_sync.check(self.vendor)))


if __name__ == "__main__":
    unittest.main()
