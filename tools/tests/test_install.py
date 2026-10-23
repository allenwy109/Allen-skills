import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def install(*args):
    return subprocess.run(["bash", str(ROOT / "install.sh"), *args], capture_output=True, text=True)


class InstallRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = pathlib.Path(self.tmp.name) / "skills"

    def tearDown(self):
        self.tmp.cleanup()

    def test_copy_mode_installs_runtime_with_marker(self):
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rt = self.target / "_allen-runtime"
        self.assertTrue((self.target / "router" / "SKILL.md").is_file())
        self.assertTrue((rt / "vendor" / "vendor.lock").is_file())
        self.assertTrue((rt / "tools" / "lib" / "runtime.py").is_file())
        self.assertTrue((rt / ".installed-by-allen-skills").is_file())
        self.assertFalse(rt.is_symlink())
        check = subprocess.run(["python3", str(rt / "tools" / "vendor_sync.py"), "check"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_reinstall_is_idempotent(self):
        self.assertEqual(install("--target", str(self.target)).returncode, 0)
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("_allen-runtime", p.stdout)

    def test_link_mode_links_repo_root(self):
        p = install("--link", "--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rt = self.target / "_allen-runtime"
        self.assertTrue(rt.is_symlink())
        self.assertEqual(rt.resolve(), ROOT.resolve())

    def test_foreign_runtime_dir_is_not_overwritten(self):
        foreign = self.target / "_allen-runtime"
        foreign.mkdir(parents=True)
        (foreign / "mine.txt").write_text("keep", encoding="utf-8")
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue((foreign / "mine.txt").is_file())
        self.assertIn("_allen-runtime（目标已存在且不是本脚本安装的", p.stdout)

    def test_help_lists_render_deps(self):
        p = subprocess.run(["bash", str(ROOT / "install.sh"), "--help"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn("--render-deps", p.stdout)
        self.assertIn("--forge-deps", p.stdout)

    def test_render_deps_without_homebrew_fails_clearly(self):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.tmp.name, "LC_ALL": "en_US.UTF-8"}
        p = subprocess.run(["bash", str(ROOT / "install.sh"), "--render-deps", "--target", str(self.target)],
                           capture_output=True, text=True, env=env)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("需要 Homebrew", p.stderr)

    def test_does_not_install_zerox(self):
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(list(self.target.glob("zerox-*")), [])
        self.assertNotEqual(install("--no-zerox", "--target", str(self.target)).returncode, 0)

    def test_remove_old_deletes_only_zerox_skills_we_installed(self):
        ours = self.target / "zerox-storyline"
        ours.mkdir(parents=True)
        (ours / ".installed-by-allen-skills").write_text("source=x", encoding="utf-8")
        theirs = self.target / "zerox-mine"
        theirs.mkdir()
        old = self.target / "consulting-analysis"
        old.mkdir()
        p = install("--target", str(self.target))
        self.assertIn("zerox-storyline 是以前装的 zerox skill", p.stdout)
        self.assertTrue(ours.is_dir())
        p = install("--remove-old", "--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("已删除旧的 zerox skill：zerox-storyline", p.stdout)
        self.assertFalse(ours.exists())
        self.assertFalse(old.exists())
        self.assertTrue(theirs.is_dir())


if __name__ == "__main__":
    unittest.main()
