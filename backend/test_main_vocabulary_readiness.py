import unittest

from main import (
    build_enabled_visual_vocabulary_filter,
    build_usable_visual_action_filter,
    build_usable_visual_vocabulary_filter,
)


class VocabularyReadinessFilterTests(unittest.TestCase):
    def test_base_filter_only_accepts_enabled_image_usable_words(self):
        self.assertEqual(
            build_usable_visual_vocabulary_filter(),
            {
                "enabled": True,
                "usable_for_image": True,
            },
        )

    def test_base_filter_preserves_semantic_conditions(self):
        self.assertEqual(
            build_usable_visual_vocabulary_filter(
                **{"action_semantics.requires_partner": True}
            ),
            {
                "enabled": True,
                "usable_for_image": True,
                "action_semantics.requires_partner": True,
            },
        )

    def test_enabled_filter_can_count_non_visual_terms(self):
        self.assertEqual(
            build_enabled_visual_vocabulary_filter(primary_role="non_visual"),
            {
                "enabled": True,
                "primary_role": "non_visual",
            },
        )

    def test_action_filter_applies_same_usable_gate_to_all_action_categories(self):
        self.assertEqual(
            build_usable_visual_action_filter(solo_action=True),
            {
                "enabled": True,
                "usable_for_image": True,
                "pos_group": "verb",
                "primary_role": "action",
                "solo_action": True,
            },
        )

        for semantic_field in (
            "action_semantics.requires_partner",
            "action_semantics.requires_object",
            "action_semantics.requires_target",
        ):
            with self.subTest(semantic_field=semantic_field):
                query = build_usable_visual_action_filter(
                    **{semantic_field: True}
                )
                self.assertTrue(query["enabled"])
                self.assertTrue(query["usable_for_image"])
                self.assertEqual(query["pos_group"], "verb")
                self.assertEqual(query["primary_role"], "action")
                self.assertTrue(query[semantic_field])


if __name__ == "__main__":
    unittest.main()
