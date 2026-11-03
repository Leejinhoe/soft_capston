import unittest

from scene_contract import (
    apply_scene_contract,
    normalize_scene_contract,
    resolve_scene_contract,
    validate_scene_contract,
)


class SceneContractTests(unittest.TestCase):
    def test_participant_identity_and_roles_are_preserved_and_validated(self):
        contract = normalize_scene_contract(
            {
                "action": "conversation",
                "character_key": "hero_01",
                "participants": [
                    {"character_key": "hero_01", "role": "speaker"},
                    {"character_key": "guide_02", "role": "listener"},
                ],
                "target": "guide_02",
            },
            character_key="hero_01",
        )
        self.assertTrue(contract["valid"])
        self.assertEqual(contract["character_keys"], ["hero_01", "guide_02"])
        self.assertEqual(contract["participant_roles"]["guide_02"], "listener")

    def test_selected_character_cannot_be_reassigned_by_participant_name(self):
        contract = normalize_scene_contract(
            {"participants": [{"character_key": "hero_01", "role": "speaker"}]},
            character_key="villain_09",
        )
        self.assertFalse(contract["valid"])
        self.assertIn("selected_character_not_participant", contract["validation_errors"])

    def test_journey_requires_direction_and_partner_actions_need_two_keys(self):
        self.assertEqual(
            validate_scene_contract(
                {
                    "action": "journey",
                    "background_direction": "toward_target",
                    "participants": [],
                    "participant_count": 0,
                }
            ),
            [],
        )
        contract = normalize_scene_contract(
            {"action": "conversation", "participant_count": 1, "character_key": "hero_01"}
        )
        self.assertIn("action_requires_partner", contract["validation_errors"])
    def test_explicit_action_wins_over_ambiguous_story_keywords(self):
        contract = normalize_scene_contract(
            {
                "action": "investigate",
                "scene_goal": "성문에 새겨진 문양을 살핀다",
                "background_direction": "toward target",
                "required_props": ["old_key"],
                "participant_count": 1,
                "requires_object": True,
            },
            character_key="female_04",
        )
        context = apply_scene_contract(
            {
                "action_tags": ["journey"],
                "action_semantics": {"animation_action": "journey"},
                "prop_tags": ["castle"],
            },
            contract,
        )

        self.assertTrue(contract["valid"])
        self.assertEqual(context["action_semantics"]["animation_action"], "investigate")
        self.assertEqual(context["action_semantics"]["directionality"], "toward_target")
        self.assertEqual(context["action_semantics"]["participant_count"], 1)
        self.assertTrue(context["action_semantics"]["requires_object"])
        self.assertEqual(context["prop_tags"], ["old_key"])

    def test_unknown_explicit_action_is_rejected_without_silent_fallback(self):
        contract = normalize_scene_contract({"action": "teleport"})

        self.assertFalse(contract["valid"])
        self.assertEqual(contract["action"], None)
        self.assertEqual(contract["validation_errors"], ["unsupported_action:teleport"])

    def test_derived_contract_records_final_motion_plan(self):
        contract = resolve_scene_contract(
            story_text="The selected hero walks toward the castle.",
            visual_context={
                "action_semantics": {"directionality": "toward_target"},
                "prop_tags": ["castle"],
            },
            motion_plan={
                "action": "journey",
                "target": "castle",
                "directionality": "toward_target",
                "alignment": {"body_facing": "toward_target"},
            },
            character_key="male_01",
        )

        self.assertTrue(contract["valid"])
        self.assertEqual(contract["action"], "journey")
        self.assertEqual(contract["target"], "castle")
        self.assertEqual(contract["character_key"], "male_01")
        self.assertIn("castle", contract["required_props"])


if __name__ == "__main__":
    unittest.main()
