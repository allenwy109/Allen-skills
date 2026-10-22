import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def copy_repo(dst):
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "node_modules", ".font-venv", "__pycache__", ".probe-task"))


class ValidateTest(unittest.TestCase):
    def run_validate(self, root):
        return subprocess.run(["python3", str(root / "tools" / "validate.py")], capture_output=True, text=True)

    def test_repo_passes(self):
        p = self.run_validate(ROOT)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_tampered_vendor_file_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            with open(copy / "vendor" / "onepager" / "LICENSE.txt", "a", encoding="utf-8") as f:
                f.write("tamper\n")
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("vendor：文件被改动：onepager/LICENSE.txt", p.stdout)

    def test_missing_lock_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            (copy / "vendor" / "vendor.lock").unlink()
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("vendor：缺少", p.stdout)


if __name__ == "__main__":
    unittest.main()
