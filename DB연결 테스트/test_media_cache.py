import unittest

from media_cache import (
    CACHE_KEY_VERSION,
    build_media_cache_key,
    canonical_media_request,
    is_duplicate_media_request,
)


class MediaCacheKeyTests(unittest.TestCase):
    def _request(self):
        return {
            "story_text": "  A hero opens the Door  ",
            "step_number": 2,
            "character_key": "Hero_01",
            "action": "  JOURNEY ",
            "background_key": "forest_path",
            "character_asset_version": "v28",
            "scene_contract": {
                "version": 1,
                "action": "journey",
                "target": "old castle",
                "required_props": ["door", "map"],
            },
            "include_video": True,
            "video_width": 960,
        }

    def test_same_request_has_same_key_after_normalization(self):
        first = self._request()
        second = {
            "story_text": "a   HERO opens the door",
            "step_number": 2,
            "character_key": " hero_01 ",
            "action": "journey",
            "background_key": "forest_path",
            "character_asset_version": " V28 ",
            "scene_contract": {
                "target": " OLD   CASTLE ",
                "required_props": ["door", "map"],
                "action": "JOURNEY",
                "version": 1,
            },
            "include_video": True,
            "video_width": 960,
        }

        self.assertEqual(build_media_cache_key(request=first), build_media_cache_key(request=second))
        self.assertTrue(is_duplicate_media_request(first, second))

    def test_key_length_and_version_are_stable(self):
        key = build_media_cache_key(request=self._request())

        self.assertEqual(key.split(":", 1)[0], CACHE_KEY_VERSION)
        self.assertEqual(len(key), len(f"{CACHE_KEY_VERSION}:") + 64)

    def test_each_identity_choice_changes_the_key(self):
        base = self._request()
        variations = (
            ("story_text", "A different story"),
            ("step_number", 3),
            ("character_key", "hero_02"),
            ("action", "investigate"),
            ("background_key", "village"),
            ("character_asset_version", "v29"),
            ("include_video", False),
        )

        original_key = build_media_cache_key(request=base)
        for field, value in variations:
            changed = dict(base)
            changed[field] = value
            self.assertNotEqual(original_key, build_media_cache_key(request=changed), field)

    def test_contract_version_and_values_are_part_of_the_key(self):
        base = self._request()
        changed_version = dict(base)
        changed_version["scene_contract"] = dict(base["scene_contract"], version=2)
        changed_target = dict(base)
        changed_target["scene_contract"] = dict(base["scene_contract"], target="tower")

        original_key = build_media_cache_key(request=base)
        self.assertNotEqual(original_key, build_media_cache_key(request=changed_version))
        self.assertNotEqual(original_key, build_media_cache_key(request=changed_target))

    def test_asset_mapping_supplies_and_preserves_asset_version(self):
        payload = canonical_media_request(
            story="story",
            scene=1,
            character="hero",
            action="idle",
            background="plain",
            character_asset={"quality_tier": "video_motion_sheet_v3", "image_file_id": "a"},
        )

        self.assertEqual(payload["character_asset_version"], "video_motion_sheet_v3")
        self.assertEqual(payload["character_asset"]["image_file_id"], "a")


if __name__ == "__main__":
    unittest.main()
