import os
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
        self.assertIn("--codex", p.stdout)
        self.assertIn("--both", p.stdout)
        self.assertNotIn("--forge-deps", p.stdout)
        self.assertNotIn("--remove-old", p.stdout)

    def test_render_deps_without_homebrew_fails_clearly(self):
        fake_bin = pathlib.Path(self.tmp.name) / "bin"
        fake_bin.mkdir()
        uname = fake_bin / "uname"
        uname.write_text("#!/bin/sh\necho Darwin\n", encoding="utf-8")
        uname.chmod(0o755)
        env = {"PATH": f"{fake_bin}:/usr/bin:/bin", "HOME": self.tmp.name, "LC_ALL": "en_US.UTF-8"}
        p = subprocess.run(["bash", str(ROOT / "install.sh"), "--render-deps", "--target", str(self.target)],
                           capture_output=True, text=True, env=env)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("需要 Homebrew", p.stderr)

    def test_codex_uses_codex_home(self):
        codex_home = pathlib.Path(self.tmp.name) / "codex-home"
        env = dict(os.environ, CODEX_HOME=str(codex_home))
        p = subprocess.run(["bash", str(ROOT / "install.sh"), "--codex", "--link"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue((codex_home / "skills" / "router").is_symlink())
        self.assertEqual((codex_home / "skills" / "_allen-runtime").resolve(), ROOT.resolve())
        self.assertTrue((codex_home / "prompts" / "allen-company.md").is_symlink())
        self.assertTrue((codex_home / "prompts" / "allen-bp-review.md").is_symlink())

    def test_both_installs_two_platforms(self):
        fake_home = pathlib.Path(self.tmp.name) / "home"
        codex_home = pathlib.Path(self.tmp.name) / "codex-home"
        env = dict(os.environ, HOME=str(fake_home), CODEX_HOME=str(codex_home))
        p = subprocess.run(["bash", str(ROOT / "install.sh"), "--both", "--link"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue((fake_home / ".claude" / "skills" / "router").is_symlink())
        self.assertTrue((codex_home / "skills" / "router").is_symlink())
        self.assertTrue((fake_home / ".claude" / "commands" / "allen-capital.md").is_symlink())
        self.assertTrue((codex_home / "prompts" / "allen-ecosystem.md").is_symlink())

    def test_does_not_install_zerox(self):
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(list(self.target.glob("zerox-*")), [])

    def test_old_system_options_are_gone(self):
        for opt in ("--no-zerox", "--remove-old", "--forge-deps"):
            p = install(opt, "--target", str(self.target))
            self.assertEqual(p.returncode, 2, opt)
            self.assertIn(f"未知参数：{opt}", p.stderr)


if __name__ == "__main__":
    unittest.main()
