import copy
import json
import pathlib
import unittest

from tools import report_release


ROOT = pathlib.Path(__file__).resolve().parents[2]


class ReportReleaseTests(unittest.TestCase):
    def load(self):
        return json.loads((ROOT / "references/report-output-release.json").read_text(encoding="utf-8"))

    def test_repository_release_is_valid(self):
        self.assertEqual(report_release.check(ROOT), [])

    def test_approved_release_rejects_machine_specific_commands(self):
        release = self.load()
        release["verification"]["commands"][0]["command"] = "/Users/example/bin/check"
        errors = report_release.validate_release_data(release)
        self.assertTrue(any("machine-specific absolute path" in error for error in errors))

    def test_deck_gate_rejects_loss_or_fewer_than_two_wins(self):
        release = self.load()
        candidate = release["deck"]["candidateScores"]
        reference = release["deck"]["referenceScores"]
        candidate.update(reference)
        errors = report_release.validate_release_data(release)
        self.assertTrue(any("at least two dimensions" in error for error in errors))

        release = self.load()
        release["deck"]["candidateScores"]["finish"] = 3
        errors = report_release.validate_release_data(release)
        self.assertTrue(any("at least 4" in error for error in errors))

    def test_evidence_hash_drift_is_rejected(self):
        release = self.load()
        release["evidence"]["deckScorecard"]["sha256"] = "0" * 64
        errors = report_release.check_evidence(ROOT, release)
        self.assertTrue(any("sha256 mismatch" in error for error in errors))

    def test_reveal_and_scorecard_are_separate_and_bound(self):
        release = self.load()
        scorecard = ROOT / release["evidence"]["deckScorecard"]["path"]
        reveal = ROOT / release["evidence"]["deckReveal"]["path"]
        self.assertNotEqual(scorecard, reveal)
        raw = scorecard.read_text(encoding="utf-8").lower()
        self.assertNotIn('"candidate"', raw)
        self.assertNotIn('"reference"', raw)
        revealed = json.loads(reveal.read_text(encoding="utf-8"))
        self.assertEqual(revealed["identities"], {"Cinder": "candidate", "Willow": "reference"})


if __name__ == "__main__":
    unittest.main()
