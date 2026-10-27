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
            self.assertEqual(set(manifest), {"version", "inputSha256", "blueprintSha256", "labels", "pageCount", "variants"})
            for label in manifest["labels"]:
                pages = sorted((output / label).glob("page-*.png"))
                self.assertEqual(len(pages), manifest["pageCount"])
                for name in ("deck.html", "deck.pdf", "contact-sheet.png", "qa-status.json"):
                    self.assertTrue((output / label / name).is_file())
                audit = json.loads((output / label / "qa-status.json").read_text())
                self.assertEqual(audit, {"acceptance": True, "errors": 0, "geometry": "PASS", "htmlPages": 5,
                                         "pdfPages": 5, "tier": "acceptance"})
                self.assertEqual(manifest["variants"][label]["qa"], audit)
                self.assertEqual(set(manifest["variants"][label]), {"files", "pageCount", "qa"})
                self.assertEqual(manifest["variants"][label]["pageCount"], 5)
            self.assertNotEqual((output / "Atlas/deck.html").read_bytes(), (output / "Juniper/deck.html").read_bytes())
            anonymous = json.loads((output / "anonymous-manifest.json").read_text())
            self.assertNotIn("mapping", anonymous)
            forbidden = ("candidate", "reference", "composer", "upstream", "pre-composer", "strategy", "provenance")
            for file in output.rglob("*"):
                if file.is_file() and ("manifest" in file.name.lower() or "instruction" in file.name.lower()):
                    lowered = file.read_text(encoding="utf-8").lower()
                    self.assertFalse(any(word in lowered for word in forbidden), f"identity leaked in {file}")
            identities = json.loads(mapping.read_text())
            self.assertEqual(set(identities["identities"].values()), {"candidate", "reference"})
            self.assertIn("releaseEvidence", identities)
            mapping.unlink()


if __name__ == "__main__":
    unittest.main()
