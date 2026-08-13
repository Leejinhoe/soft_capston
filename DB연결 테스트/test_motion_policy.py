import unittest

from motion_policy import SOLO_ANIMATION_ACTIONS, is_solo_action_semantics


class MotionPolicyTests(unittest.TestCase):
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
