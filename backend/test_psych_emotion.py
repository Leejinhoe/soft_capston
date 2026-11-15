import os
import unittest
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "unit-test-only-not-a-real-secret")

from psych import ChoiceInsight, _choice_insight
from psych_engine import ChoiceStep


class ChoiceEmotionTests(unittest.TestCase):
    def setUp(self):
        self.step = ChoiceStep(
            scene=2,
            scene_text="숲에서 길을 찾는다.",
            options=["친구를 부른다", "혼자 걷는다"],
            choice="친구를 부른다",
        )

    def test_keeps_only_reviewed_display_labels(self):
        result = {
            "emotion_scoring_enabled": True,
            "presentation_status": "emotion_candidates",
            "display_emotions": [
                {"label": "기쁨", "label_display": "기쁨"},
                {"label": "기쁨", "label_display": "기쁨"},
            ],
        }
        with patch("psych.emotion_runtime.analyze", return_value=result):
            insight = _choice_insight(self.step, "함께할 방법을 찾아요.")

        self.assertEqual(insight["emotion_labels"], ["기쁨"])
        self.assertEqual(insight["emotion_status"], "detected")
        self.assertEqual(ChoiceInsight(**insight).emotion_labels, ["기쁨"])

    def test_no_candidate_is_not_presented_as_an_emotion(self):
        with patch("psych.emotion_runtime.analyze", return_value={
            "emotion_scoring_enabled": True,
            "presentation_status": "no_emotion_candidate",
            "display_emotions": [],
        }):
            insight = _choice_insight(self.step, "기본 해석")

        self.assertEqual(insight["emotion_labels"], [])
        self.assertEqual(insight["emotion_status"], "no_candidate")

    def test_model_failure_does_not_break_psychology_insight(self):
        with patch("psych.emotion_runtime.analyze", side_effect=RuntimeError("not installed")):
            insight = _choice_insight(self.step, "기본 해석")

        self.assertEqual(insight["insight"], "기본 해석")
        self.assertEqual(insight["emotion_labels"], [])
        self.assertEqual(insight["emotion_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
