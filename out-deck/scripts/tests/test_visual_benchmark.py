import importlib.util
import json
import pathlib
import re
import tempfile
import unittest
from collections import Counter

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "build_visual_benchmark.py"
SPEC = importlib.util.spec_from_file_location("build_visual_benchmark", SCRIPT)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class VisualBenchmarkTest(unittest.TestCase):
    def test_output_must_be_a_managed_child_of_build_directory(self):
        build = SCRIPT.parents[1] / "build"
        with tempfile.TemporaryDirectory() as tmp:
            for unsafe in (pathlib.Path(tmp) / "outside", SCRIPT.parents[2], build):
                with self.assertRaisesRegex(RuntimeError, "BENCHMARK_OUTPUT_UNSAFE"):
                    benchmark.validate_output(unsafe)
        unmanaged = build / "unmanaged-existing-test"
        unmanaged.mkdir(parents=True, exist_ok=True)
        (unmanaged / "foreign.txt").write_text("do not delete")
        try:
            with self.assertRaisesRegex(RuntimeError, "BENCHMARK_OUTPUT_UNMANAGED"):
                benchmark.validate_output(unmanaged)
            self.assertTrue((unmanaged / "foreign.txt").is_file())
        finally:
            (unmanaged / "foreign.txt").unlink()
            unmanaged.rmdir()

    def test_same_locked_input_builds_blind_distinct_complete_outputs(self):
        output = SCRIPT.parents[1] / "build" / "test-visual-benchmark"
        try:
            manifest, mapping = benchmark.build(output)
            self.assertEqual(manifest["pageCount"], 5)
            self.assertEqual(set(manifest["labels"]), {"Cinder", "Willow"})
            self.assertEqual(set(manifest), {"version", "inputSha256", "blueprintSha256", "labels", "pageCount", "variants"})
            for label in manifest["labels"]:
                pages = sorted((output / label).glob("page-*.png"))
                self.assertEqual(len(pages), manifest["pageCount"])
                for name in ("deck.html", "deck.pdf", "contact-sheet.png", "qa-status.json", "cross-media.json"):
                    self.assertTrue((output / label / name).is_file())
                audit = json.loads((output / label / "qa-status.json").read_text())
                self.assertEqual(audit, {"acceptance": True, "errors": 0, "geometry": "PASS", "htmlPages": 5,
                                         "pdfPages": 5, "tier": "acceptance"})
                self.assertEqual(manifest["variants"][label]["qa"], audit)
                self.assertEqual(set(manifest["variants"][label]), {"files", "pageCount", "qa"})
                self.assertEqual(manifest["variants"][label]["pageCount"], 5)
            self.assertNotEqual((output / "Cinder/deck.html").read_bytes(), (output / "Willow/deck.html").read_bytes())
            for label in manifest["labels"]:
                media = json.loads((output / label / "cross-media.json").read_text())
                self.assertEqual(len(media["pages"]), 5)
                self.assertTrue(all(page["textSimilarity"] >= 0.93 for page in media["pages"]))
                benchmark.verify_variant_media(output / label, 5)
            stale = (output / "Cinder/page-04.png").read_bytes()
            (output / "Cinder/page-04.png").write_bytes((output / "Willow/page-04.png").read_bytes())
            with self.assertRaisesRegex(RuntimeError, "BENCHMARK_MEDIA_PNG_MISMATCH"):
                benchmark.verify_variant_media(output / "Cinder", 5)
            (output / "Cinder/page-04.png").write_bytes(stale)
            stale_pdf = (output / "Cinder/deck.pdf").read_bytes()
            (output / "Cinder/deck.pdf").write_bytes((output / "Willow/deck.pdf").read_bytes())
            with self.assertRaisesRegex(RuntimeError, "BENCHMARK_MEDIA_TEXT_MISMATCH"):
                benchmark.verify_variant_media(output / "Cinder", 5)
            (output / "Cinder/deck.pdf").write_bytes(stale_pdf)
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
            self.assertEqual(identities["releaseEvidence"]["reviewerSanitization"], {"pages": 5, "pixelIdentical": True})
            self.assertEqual(identities["releaseEvidence"]["planMutation"], {"changedPages": [2], "unchangedPages": [1, 3, 4, 5]})
            readable = {label: "\n".join(p.read_text(encoding="utf-8") for p in sorted((output / label).rglob("*"))
                                           if p.is_file() and p.suffix in {".html", ".css", ".json", ".md", ".txt"})
                        for label in manifest["labels"]}
            pattern = re.compile(r"(?i)\b(?:allen[-_][\w-]*|data-allen-[\w-]*|candidate|composer|upstream|pre-composer|reference-task|candidate-task)\b")
            fingerprints = {label: Counter(pattern.findall(text.replace("Allen 分析系统", ""))) for label, text in readable.items()}
            self.assertEqual(fingerprints["Cinder"], fingerprints["Willow"])
            self.assertFalse(any(token.lower().startswith(("allen-", "data-allen-")) for token in fingerprints["Cinder"]))
            mapping.unlink()
        finally:
            if output.exists():
                import shutil
                shutil.rmtree(output)


if __name__ == "__main__":
    unittest.main()
