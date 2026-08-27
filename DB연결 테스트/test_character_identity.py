import unittest

from character_identity import (
    asset_fingerprint,
    asset_version,
    build_character_identity_context,
    character_identity_matches,
    identity_context_from_profile,
    with_character_identity,
)


class CharacterIdentityTests(unittest.TestCase):
    def test_context_uses_key_and_face_asset_without_display_name(self):
        context = build_character_identity_context(
            character_key="female_01",
            face_asset="face-v2",
            asset_version="v2",
        )

        self.assertEqual(context["character_key"], "female_01")
        self.assertEqual(context["face_asset"], "face-v2")
        self.assertEqual(context["image_file_id"], "face-v2")
        self.assertEqual(context["asset_version"], "v2")
        self.assertNotIn("name", context)

    def test_image_file_id_is_accepted_as_face_anchor(self):
        context = build_character_identity_context(
            character_key="male_01", image_file_id="gridfs-image"
        )
        self.assertEqual(context["face_asset"], "gridfs-image")
        self.assertEqual(context["image_file_id"], "gridfs-image")

    def test_fingerprint_is_stable_and_ignores_delivery_url(self):
        asset = {"character_key": "female_01", "image_file_id": "face", "pose": "default"}
        same_asset = {**asset, "image_url": "/api/media/images/other"}
        self.assertEqual(asset_fingerprint(asset), asset_fingerprint(same_asset))
        self.assertEqual(asset_version(asset), asset_fingerprint(asset))

    def test_explicit_version_tracks_replacement(self):
        self.assertEqual(asset_version({"asset_version": "v3"}), "v3")
        self.assertNotEqual(
            asset_fingerprint({"character_key": "a", "image_file_id": "one"}),
            asset_fingerprint({"character_key": "a", "image_file_id": "two"}),
        )

    def test_profile_anchor_prefers_premium_reference(self):
        context = identity_context_from_profile(
            {
                "character_key": "female_01",
                "name": "display name must not be used",
                "assets": [
                    {"pose": "default", "image_file_id": "fast"},
                    {"quality_tier": "premium_reference", "image_file_id": "reference", "asset_version": "v2"},
                ],
            }
        )
        self.assertEqual(context["image_file_id"], "reference")
        self.assertEqual(context["asset_version"], "v2")

    def test_asset_can_carry_context_and_match_later_scene_asset(self):
        anchor = build_character_identity_context("female_01", "face", asset_version="v2")
        enriched = with_character_identity({"pose": "walking", "image_file_id": "walking"}, anchor)
        self.assertEqual(enriched["identity_context"], anchor)
        self.assertTrue(character_identity_matches(anchor, enriched["identity_context"]))
        self.assertFalse(character_identity_matches(anchor, {"character_key": "male_01", "image_file_id": "face", "asset_version": "v2"}))


if __name__ == "__main__":
    unittest.main()
