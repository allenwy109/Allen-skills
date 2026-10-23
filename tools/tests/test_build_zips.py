"""build-zips.py：只打包能在 claude.ai 上单独使用的 skill。"""
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


class BuildZipsTest(unittest.TestCase):
    def test_excludes_out_skills_runtime_and_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(ROOT / "tools" / "build-zips.py"), tmp], capture_output=True, text=True, check=True)
            names = sorted(p.stem for p in pathlib.Path(tmp).glob("*.zip"))
            self.assertIn("router", names)
            self.assertIn("core-storyline", names)
            self.assertFalse([n for n in names if n.startswith(("out-", "_", "zerox-"))], names)
            with zipfile.ZipFile(pathlib.Path(tmp) / "core-storyline.zip") as z:
                self.assertFalse([n for n in z.namelist() if "__pycache__" in n], "不应打包缓存文件")


if __name__ == "__main__":
    unittest.main()
