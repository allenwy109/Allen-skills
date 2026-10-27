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

    def test_deck_verdict_is_recomputed_not_trusted(self):
        release = self.load()
        scorecard = json.loads((ROOT / release["evidence"]["deckScorecard"]["path"]).read_text(encoding="utf-8"))
        reveal = json.loads((ROOT / release["evidence"]["deckReveal"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(report_release.validate_deck_verdict(release, scorecard, reveal), [])

        mutations = []
        wrong_label = copy.deepcopy(scorecard)
        wrong_label["verdict"]["passingLabel"] = "Willow"
        mutations.append(wrong_label)
        false_tie = copy.deepcopy(scorecard)
        false_tie["verdict"]["tiedDimensions"].append("evidence_geometry")
        mutations.append(false_tie)
        fake_threshold = copy.deepcopy(scorecard)
        fake_threshold["verdict"]["threshold"] = 3
        mutations.append(fake_threshold)
        fake_blocker = copy.deepcopy(scorecard)
        fake_blocker["verdict"]["blockers"] = ["fabricated"]
        mutations.append(fake_blocker)

        for mutation in mutations:
            with self.subTest(mutation=mutation["verdict"]):
                errors = report_release.validate_deck_verdict(release, mutation, reveal)
                self.assertTrue(errors)

        release_mutations = []
        wrong_release_label = copy.deepcopy(release)
        wrong_release_label["deck"]["passingLabel"] = "Willow"
        release_mutations.append(wrong_release_label)
        false_release_tie = copy.deepcopy(release)
        false_release_tie["deck"]["tiedDimensions"].append("evidence_geometry")
        release_mutations.append(false_release_tie)
        fake_release_threshold = copy.deepcopy(release)
        fake_release_threshold["deck"]["scoreThreshold"] = 3
        release_mutations.append(fake_release_threshold)
        fake_release_blocker = copy.deepcopy(release)
        fake_release_blocker["deck"]["blockers"] = ["fabricated"]
        release_mutations.append(fake_release_blocker)
        for mutation in release_mutations:
            with self.subTest(release=mutation["deck"]):
                errors = report_release.validate_deck_verdict(mutation, scorecard, reveal)
                self.assertTrue(errors)

    def test_ci_checkout_fetches_full_history_for_commit_validation(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        self.assertRegex(
            workflow,
            r"uses: actions/checkout@v4\n\s+with:\n\s+fetch-depth: 0",
        )
        self.assertIn("  pull_request:\n", workflow)
        self.assertIn("  push:\n    branches: [main]\n", workflow)


if __name__ == "__main__":
    unittest.main()
