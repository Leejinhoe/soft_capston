import unittest

from motion_policy import SOLO_ANIMATION_ACTIONS, is_solo_action_semantics, validate_motion_semantics


class MotionPolicyTests(unittest.TestCase):
    def test_partner_action_requires_distinct_declared_participants(self):
        semantics = {
            "animation_action": "conversation",
            "participant_count": 2,
            "participants": [
                {"character_key": "hero_01", "role": "speaker"},
                {"character_key": "guide_02", "role": "listener"},
            ],
        }
        self.assertEqual(validate_motion_semantics(semantics), [])
        self.assertIn(
            "action_requires_partner",
            validate_motion_semantics({"animation_action": "conversation", "participant_count": 1}),
        )

    def test_solo_journey_requires_direction(self):
        self.assertFalse(
            is_solo_action_semantics(
                {"animation_action": "journey", "participant_count": 1}
            )
        )
        self.assertTrue(
            is_solo_action_semantics(
                {
                    "animation_action": "journey",
                    "participant_count": 1,
                    "directionality": "toward_target",
                }
            )
        )
    def test_new_stationary_actions_are_allowed_for_one_character(self):
        for action in ("sit", "stand"):
            with self.subTest(action=action):
                self.assertIn(action, SOLO_ANIMATION_ACTIONS)
                self.assertTrue(
                    is_solo_action_semantics(
                        {
                            "animation_action": action,
                            "motion_mode": "stationary",
                            "participant_count": 1,
                        }
                    )
                )

    def test_partner_or_object_requirement_blocks_solo_training(self):
        self.assertFalse(
            is_solo_action_semantics(
                {
                    "animation_action": "stand",
                    "motion_mode": "stationary",
                    "participant_count": 1,
                    "requires_partner": True,
                }
            )
        )
        self.assertFalse(
            is_solo_action_semantics(
                {
                    "animation_action": "sit",
                    "motion_mode": "stationary",
                    "participant_count": 1,
                    "requires_object": True,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
