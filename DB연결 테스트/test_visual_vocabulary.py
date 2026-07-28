import unittest

from visual_vocabulary import classify_fit_vocabulary, match_visual_vocabulary


class VisualVocabularyTests(unittest.TestCase):
    def test_classifies_environment_effect(self):
        result = classify_fit_vocabulary(
            {
                "word": "회오리",
                "meaning": "바람이 한곳에서 빙빙 도는 현상",
                "pos_group": "명사",
            }
        )

        self.assertEqual(result["primary_role"], "environment_effect")
        self.assertTrue(result["usable_for_image"])
        self.assertIn("whirlwind", result["effect_tags"])
        self.assertTrue(result["evidence"])

    def test_classifies_visual_action_and_builds_stem(self):
        result = classify_fit_vocabulary(
            {
                "word": "다가다",
                "meaning": "대상이 있는 쪽으로 몸을 움직이다",
                "pos_group": "동사",
            }
        )

        self.assertEqual(result["primary_role"], "action")
        self.assertIn("다가", result["match_terms"])
        self.assertIn("walking", result["action_tags"])

    def test_keeps_abstract_noun_non_visual(self):
        result = classify_fit_vocabulary(
            {
                "word": "이유",
                "meaning": "어떤 생각이나 행동을 하게 된 까닭",
                "pos_group": "명사",
            }
        )

        self.assertEqual(result["primary_role"], "non_visual")
        self.assertFalse(result["usable_for_image"])

    def test_matches_inflected_story_word(self):
        document = classify_fit_vocabulary(
            {
                "word": "다가다",
                "meaning": "대상이 있는 쪽으로 몸을 움직이다",
                "pos_group": "동사",
            }
        )
        document.update({"fit_score": 91, "enabled": True})

        context = match_visual_vocabulary(
            "주인공은 빛나는 문으로 천천히 다가갔어요.",
            [document],
        )

        self.assertEqual(context["matched_words"], ["다가다"])
        self.assertIn("walking", context["action_tags"])

    def test_matches_irregular_korean_verb(self):
        document = classify_fit_vocabulary(
            {
                "word": "걷다",
                "meaning": "다리를 움직여 앞으로 가다",
                "pos_group": "동사",
            }
        )
        document.update({"fit_score": 90, "enabled": True})

        context = match_visual_vocabulary(
            "아이는 달빛이 비치는 숲길을 천천히 걸었어요.",
            [document],
        )

        self.assertEqual(context["matched_words"], ["걷다"])
        self.assertIn("walking", context["action_tags"])


if __name__ == "__main__":
    unittest.main()
