import importlib.util
import json
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "build_visual_benchmark.py"
SPEC = importlib.util.spec_from_file_location("build_visual_benchmark", SCRIPT)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class VisualBenchmarkTest(unittest.TestCase):
    def test_same_locked_input_builds_blind_distinct_complete_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "packet"
            manifest, mapping = benchmark.build(output)
            self.assertEqual(manifest["pageCount"], 5)
            self.assertEqual(set(manifest["labels"]), {"Atlas", "Juniper"})
            for label in manifest["labels"]:
                pages = sorted((output / label).glob("page-*.png"))
                self.assertEqual(len(pages), manifest["pageCount"])
                for name in ("deck.html", "deck.pdf", "contact-sheet.png"):
                    self.assertTrue((output / label / name).is_file())
            self.assertNotEqual((output / "Atlas/deck.html").read_bytes(), (output / "Juniper/deck.html").read_bytes())
            anonymous = json.loads((output / "anonymous-manifest.json").read_text())
            self.assertNotIn("mapping", anonymous)
            self.assertNotIn("candidate", {key.lower() for key in anonymous if key != "compositionContract"})
            identities = json.loads(mapping.read_text())
            self.assertEqual(set(identities.values()), {"candidate", "reference"})
            mapping.unlink()


if __name__ == "__main__":
    unittest.main()
