import json
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools" / "vocabulary_ensemble"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from merge_ensemble import load_reports, merge_reports  # noqa: E402


class VocabularyEnsembleTests(unittest.TestCase):
    def test_real_reports_use_the_same_twelve_words(self):
        merged = merge_reports(
            load_reports(TOOLS_DIR / "runs")
        )
        self.assertEqual(merged["annotator_count"], 5)
        self.assertEqual(merged["word_count"], 12)
        self.assertTrue(all(item["ensemble"]["annotator_count"] == 5 for item in merged["words"]))

    def test_majority_and_evidence_are_merged(self):
        reports = []
        for index in range(5):
            reports.append(
                (
                    f"agent_{index}",
                    [
                        {
                            "word": "walk",
                            "canonical_action": "journey",
                            "motion_mode": "locomotion",
                            "participant_count": 0,
                            "requires_partner": False,
                            "requires_object": False,
                            "requires_target": False,
                            "solo_action": True,
                            "synonyms": [f"walk-{index}"],
                            "positive_cues": [f"cue-{index}"],
                            "negative_cues": [f"avoid-{index}"],
                            "phases": [
                                {"name": "prepare", "cues": ["ready"]},
                                {"name": "act", "cues": ["step"]},
                                {"name": "recover", "cues": ["stop"]},
                            ],
                            "scene_requirements": ["ground"],
                            "prompt_variants": [f"prompt-{index}"],
                            "confidence": 0.8,
                            "ambiguity_notes": "none",
                        }
                    ],
                )
            )
        merged = merge_reports(reports)["words"][0]
        self.assertEqual(merged["participant_count"], 1)
        self.assertTrue(merged["solo_action"])
        self.assertEqual(len(merged["prompt_variants"]), 5)
        self.assertEqual(merged["ensemble"]["agreement"], 1.0)
        self.assertIn("walk-4", merged["synonyms"])


if __name__ == "__main__":
    unittest.main()
