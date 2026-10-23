import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace

from tools import record_probe


class RecordProbeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rt = pathlib.Path(self.tmp.name)
        (self.rt / "vendor" / "report-forge").mkdir(parents=True)
        (self.rt / "vendor" / "vendor.lock").write_text(json.dumps({"commit": "abc123"}), encoding="utf-8")
        self.response = self.rt / "response.json"
        self.response.write_text("{}", encoding="utf-8")
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, code):
        def run(args, cwd=None, capture_output=None, text=None):
            self.calls.append((args, cwd))
            return SimpleNamespace(returncode=code, stdout="verify output", stderr="")
        return run

    def test_success_writes_verified_record(self):
        code = record_probe.run(self.rt, self.response, runner=self.runner(0), now="2026-10-22T10:00:00+00:00")
        self.assertEqual(code, 0)
        data = json.loads((self.rt / ".probe.json").read_text(encoding="utf-8"))
        self.assertEqual(data["verified"], True)
        self.assertEqual(data["commit"], "abc123")
        self.assertEqual(data["at"], "2026-10-22T10:00:00+00:00")
        args, cwd = self.calls[0]
        self.assertEqual(args[:2], ["node", "scripts/probe_capabilities.cjs"])
        self.assertEqual(args[2:], [str(self.rt / ".probe-task"), "--verify", str(self.response)])
        self.assertEqual(cwd, self.rt / "vendor" / "report-forge")

    def test_failure_writes_unverified_record(self):
        code = record_probe.run(self.rt, self.response, runner=self.runner(1))
        self.assertEqual(code, 1)
        data = json.loads((self.rt / ".probe.json").read_text(encoding="utf-8"))
        self.assertEqual(data["verified"], False)

    def test_missing_response_file(self):
        code = record_probe.run(self.rt, self.rt / "nope.json", runner=self.runner(0))
        self.assertEqual(code, 2)
        self.assertFalse((self.rt / ".probe.json").exists())

    def test_node_not_found(self):
        def run(*args, **kwargs):
            raise FileNotFoundError("node")
        code = record_probe.run(self.rt, self.response, runner=run)
        self.assertEqual(code, 2)
        self.assertFalse((self.rt / ".probe.json").exists())


if __name__ == "__main__":
    unittest.main()
