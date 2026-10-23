import pathlib
import tempfile
import unittest
from unittest import mock

from tools.lib import runtime


def make_runtime(root):
    (root / "vendor" / "report-forge").mkdir(parents=True)
    (root / "vendor" / "vendor.lock").write_text("{}", encoding="utf-8")
    return root


class RuntimeRootTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_env_override_wins(self):
        rt = make_runtime(self.base / "rt")
        self.assertEqual(runtime.runtime_root(env={"ALLEN_RUNTIME": str(rt)}), rt.resolve())

    def test_invalid_env_override_is_an_error(self):
        with self.assertRaises(runtime.RuntimeNotFound):
            runtime.runtime_root(env={"ALLEN_RUNTIME": str(self.base / "nope")})

    def test_installed_runtime_next_to_skill(self):
        make_runtime(self.base / "skills" / "_allen-runtime")
        skill = self.base / "skills" / "out-report"
        skill.mkdir(parents=True)
        self.assertEqual(runtime.runtime_root(skill_dir=skill, env={}), (self.base / "skills" / "_allen-runtime").resolve())

    def test_falls_back_to_repo_root(self):
        repo = make_runtime(self.base / "repo")
        with mock.patch.object(runtime, "REPO_ROOT", repo):
            self.assertEqual(runtime.runtime_root(env={}), repo.resolve())

    def test_nothing_found(self):
        with mock.patch.object(runtime, "REPO_ROOT", self.base / "empty"):
            with self.assertRaises(runtime.RuntimeNotFound):
                runtime.runtime_root(env={})


class EngineAndVenvTest(unittest.TestCase):
    def test_platform_executables_are_strings(self):
        self.assertTrue(runtime.CHROME)
        self.assertTrue(runtime.SOFFICE_APP)

    def test_chrome_channel_distinguishes_chromium(self):
        self.assertEqual(runtime.chrome_channel("/usr/bin/chromium"), "chromium")
        self.assertEqual(runtime.chrome_channel("/opt/google/chrome/chrome"), "chrome")

    def test_engine_dir(self):
        with tempfile.TemporaryDirectory() as t:
            rt = make_runtime(pathlib.Path(t))
            d = runtime.engine_dir("report-forge", env={"ALLEN_RUNTIME": str(rt)})
            self.assertEqual(d, (rt / "vendor" / "report-forge").resolve())

    def test_unknown_engine(self):
        with self.assertRaises(ValueError):
            runtime.engine_dir("zerox-deep-research", env={})
        with self.assertRaises(ValueError):
            runtime.engine_path("/rt", "zerox-deep-research")

    def test_engine_path(self):
        self.assertEqual(runtime.engine_path("/rt", "onepager"), pathlib.Path("/rt/vendor/onepager"))

    def test_missing_engine_dir(self):
        with tempfile.TemporaryDirectory() as t:
            rt = make_runtime(pathlib.Path(t))
            with self.assertRaises(runtime.RuntimeNotFound):
                runtime.engine_dir("onepager", env={"ALLEN_RUNTIME": str(rt)})

    def test_venv_python_default_and_override(self):
        self.assertEqual(runtime.venv_python(env={"ALLEN_VENV": "/x/venv"}), pathlib.Path("/x/venv/bin/python"))
        default = runtime.venv_python(env={"HOME": "/home/u"})
        self.assertEqual(default, pathlib.Path("/home/u/.cache/allen-skills/venv/bin/python"))


if __name__ == "__main__":
    unittest.main()
