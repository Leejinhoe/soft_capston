import unittest

from story_cast import (
    build_story_cast,
    extract_character_name,
    normalize_story_characters,
    select_story_cast_member,
)


def _profile(key, genres):
    return {
        "character_key": key,
        "name": key,
        "description": f"fixed face for {key}",
        "style_prompt": "storybook",
        "genres": genres,
        "active": True,
        "assets": [
            {
                "pose": "default",
                "emotion": "neutral",
                "image_file_id": f"{key}-file",
                "tags": genres,
            }
        ],
    }


class StoryCastTests(unittest.TestCase):
    def test_extracts_quoted_name(self):
        self.assertEqual(
            extract_character_name("brave child 'Yonggam'"),
            "Yonggam",
        )

    def test_builds_stable_role_cast(self):
        characters = {
            "hero": "brave child 'Yonggam'",
            "companion": "forest fairy 'Luna'",
        }
        profiles = [
            _profile("fantasy_mina", ["fantasy"]),
            _profile("adventure_jun", ["adventure"]),
        ]

        first = build_story_cast(characters, profiles, genre="fantasy")
        second = build_story_cast(characters, list(reversed(profiles)), genre="fantasy")

        self.assertEqual(first, second)
        self.assertEqual([item["role"] for item in first], ["hero", "companion"])
        self.assertNotEqual(first[0]["character_key"], first[1]["character_key"])
        self.assertEqual(first[0]["face_asset"]["pose"], "default")

    def test_selects_mentioned_character_and_defaults_to_hero(self):
        cast = [
            {"role": "hero", "name": "Yonggam", "character_key": "hero-face"},
            {"role": "companion", "name": "Luna", "character_key": "fairy-face"},
        ]
        self.assertEqual(
            select_story_cast_member(cast, "Luna opened the forest door.")[
                "character_key"
            ],
            "fairy-face",
        )
        self.assertEqual(
            select_story_cast_member(cast, "The journey continued.")[
                "character_key"
            ],
            "hero-face",
        )

    def test_ignores_empty_character_values(self):
        self.assertEqual(
            normalize_story_characters({"hero": "  ", "guide": "Old guide"}),
            {"guide": "Old guide"},
        )

    def test_keeps_key_item_out_of_face_cast(self):
        cast = build_story_cast(
            {
                "hero": "brave child 'Yonggam'",
                "key_item": "magic key 'Hope Key'",
            },
            [_profile("fantasy_mina", ["fantasy"])],
            genre="fantasy",
        )
        self.assertEqual([item["role"] for item in cast], ["hero"])


if __name__ == "__main__":
    unittest.main()
