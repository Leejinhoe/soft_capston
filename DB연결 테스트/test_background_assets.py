import unittest

from PIL import Image

from background_assets import (
    BACKGROUND_ASSET_DIR,
    BACKGROUND_ASSETS,
    select_background_asset,
)


class BackgroundAssetTests(unittest.TestCase):
    def test_selects_genre_default(self):
        selected = select_background_asset("fantasy", "A quiet beginning")

        self.assertIsNotNone(selected)
        self.assertEqual(selected["key"], "fantasy_castle")
        self.assertTrue(selected["path"].is_file())
        self.assertTrue(selected["video_path"].is_file())
        self.assertEqual(selected["video_source"], "panorama_asset")
        self.assertEqual(selected["video_path"].name, "fantasy_castle_wide_v2.png")

    def test_supports_korean_genre(self):
        selected = select_background_asset("추리", "도서관에서 단서를 찾았다")

        self.assertIsNotNone(selected)
        self.assertEqual(selected["key"], "mystery_library")

    def test_visual_context_can_override_unknown_genre(self):
        selected = select_background_asset(
            None,
            "주인공이 낯선 장소에 도착했다",
            visual_context={"background_keys": ["nature_pond"]},
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["key"], "nature_pond")

    def test_korean_genre_alias_keeps_the_existing_default(self):
        selected = select_background_asset("판타지", "조용한 이야기의 시작")

        self.assertIsNotNone(selected)
        self.assertEqual(selected["key"], "fantasy_castle")

    def test_new_backgrounds_are_selected_by_scene_keywords(self):
        cases = (
            ("fantasy", "수정 동굴의 차원문을 향해 달렸다", "fantasy_crystal_cave"),
            ("adventure", "항구의 배와 등대를 향해 달렸다", "adventure_harbor"),
            ("nature", "설원의 눈길을 지나 오두막으로 향했다", "nature_snowfield"),
            ("friendship", "축제 무대와 정자를 향해 달렸다", "friendship_festival"),
            ("mystery", "시계탑의 비밀문을 찾아 달렸다", "mystery_clocktower"),
        )
        for genre, story_text, expected_key in cases:
            with self.subTest(expected_key=expected_key):
                selected = select_background_asset(genre, story_text)

                self.assertIsNotNone(selected)
                self.assertEqual(selected["key"], expected_key)
                self.assertEqual(selected["video_source"], "panorama_asset")

    def test_every_background_has_a_real_panorama_for_video(self):
        for asset in BACKGROUND_ASSETS:
            with self.subTest(key=asset["key"]):
                video_path = BACKGROUND_ASSET_DIR / asset["video_filename"]
                self.assertTrue(video_path.is_file())
                with Image.open(video_path) as image:
                    self.assertGreaterEqual(image.width / image.height, 2.4)


if __name__ == "__main__":
    unittest.main()
