import unittest

from background_assets import select_background_asset


class BackgroundAssetTests(unittest.TestCase):
    def test_selects_genre_default(self):
        selected = select_background_asset("fantasy", "A quiet beginning")

        self.assertIsNotNone(selected)
        self.assertEqual(selected["key"], "fantasy_castle")
        self.assertTrue(selected["path"].is_file())

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


if __name__ == "__main__":
    unittest.main()
