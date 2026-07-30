import unittest

from pydantic import ValidationError

from models import CharacterProfileUpsertSchema, MediaGenerationSchema


class CharacterModelTests(unittest.TestCase):
    def test_character_profile_accepts_pose_assets(self):
        profile = CharacterProfileUpsertSchema(
            name="Forest child",
            description="A child with short brown hair and a red cloak.",
            style_prompt="Soft watercolor storybook style.",
            assets=[
                {
                    "pose": "walking",
                    "emotion": "happy",
                    "image_file_id": "507f1f77bcf86cd799439011",
                    "tags": ["forest", "day"],
                }
            ],
        )

        self.assertEqual(profile.assets[0].pose, "walking")
        self.assertEqual(profile.assets[0].emotion, "happy")

    def test_media_request_rejects_invalid_character_key(self):
        with self.assertRaises(ValidationError):
            MediaGenerationSchema(
                story_text="A quiet forest scene",
                character_key="Invalid Key",
            )


if __name__ == "__main__":
    unittest.main()
