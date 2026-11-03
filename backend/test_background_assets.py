import unittest

from PIL import Image

from background_assets import (
    BACKGROUND_ASSET_DIR,
    BACKGROUND_ASSETS,
    select_background_asset,
)


class BackgroundAssetTests(unittest.TestCase):
    def test_scene_background_is_eligible_across_genres(self):
        from story_background_pack import PACK
        for key, _, _, _ in PACK:
            with self.subTest(key=key):
                selected = select_background_asset(
                    "fantasy", "The hero reached the destination.",
                    {"background_keys": [key]},
                )
                self.assertEqual(selected["key"], key)
                self.assertTrue(selected["video_path"].is_file())

    def test_unknown_or_malformed_scene_keys_keep_default(self):
        for keys in (None, "nature_pond", ["missing"], [{"key": "nature_pond"}]):
            with self.subTest(keys=keys):
                selected = select_background_asset(
                    "fantasy", "A quiet beginning", {"background_keys": keys}
                )
                self.assertEqual(selected["key"], "fantasy_castle")

    def test_arrival_timing_is_smooth_and_does_not_change_legacy(self):
        from hf_video_provider import _journey_animation_progress
        plan = {'background_key': 'fantasy_castle_gate'}
        times = [_journey_animation_progress(i / 100, plan) for i in range(101)]
        self.assertEqual(times[0], 0)
        self.assertEqual(times[-1], 1)
        self.assertEqual(times, sorted(times))
        self.assertLess(times[-1] - times[-2], .001)
        self.assertLess(times[1] - times[0], .001)
        self.assertEqual(_journey_animation_progress(.25, {'background_key': 'fantasy_castle'}), .25)

    def test_shadow_stays_on_route_while_body_bobs(self):
        from hf_video_provider import _character_motion_values, _journey_route_screen_position
        plan = {'background_key': 'fantasy_castle_gate', 'pace': 'run', '_duration_seconds': 6}
        for progress in (.13, .39, .71):
            values = _character_motion_values(action='journey', progress=progress, width=640, height=384,
                                             motion_strength=4, motion_plan=plan)
            route = _journey_route_screen_position(progress=progress, width=640, height=384, motion_plan=plan)
            self.assertAlmostEqual(values['shadow_ground_y'], route[1])
            self.assertLessEqual(values['ground_y'], values['shadow_ground_y'])

    def test_rear_pose_is_used_for_receding_not_lateral_routes(self):
        from hf_video_provider import _journey_prefers_rear
        for key in ('fantasy_castle_gate', 'adventure_stone_bridge', 'mystery_grand_library'):
            self.assertTrue(_journey_prefers_rear({'background_key': key}))
            self.assertFalse(_journey_prefers_rear({'background_key': key, 'directionality': 'reverse'}))
        for key in ('friendship_village_square', 'nature_lakeside_pavilion', 'fantasy_castle'):
            self.assertFalse(_journey_prefers_rear({'background_key': key}))

    def test_landscape_perspective_recedes_and_reverses_consistently(self):
        from hf_video_provider import _character_motion_values
        from story_background_pack import PACK
        for key, _, _, _ in PACK:
            with self.subTest(key=key):
                def values(progress, reverse=False):
                    return _character_motion_values(
                        action='journey', progress=progress, width=640, height=384,
                        motion_strength=4, motion_plan={
                            'background_key': key, 'pace': 'run',
                            'directionality': 'reverse' if reverse else 'toward_target',
                        },
                    )
                scales = [values(i / 100)['scale'] for i in range(101)]
                self.assertEqual(scales, sorted(scales, reverse=True))
                self.assertLess(scales[-1], scales[0] * .65)
                self.assertGreater(scales[-1], .08)
                for progress in (0, .25, .5, .75, 1):
                    self.assertAlmostEqual(values(progress)['scale'], values(1 - progress, True)['scale'])

    def test_facing_follows_route_and_reverse_direction(self):
        from hf_video_provider import _journey_faces_left
        plan = {'background_key': 'friendship_village_square'}
        self.assertTrue(_journey_faces_left(plan))
        self.assertFalse(_journey_faces_left({**plan, 'directionality': 'reverse'}))
        self.assertFalse(_journey_faces_left({'background_key': 'nature_lakeside_pavilion'}))
        self.assertTrue(_journey_faces_left({'background_key': 'fantasy_castle', 'directionality': 'reverse'}))

    def test_landscape_route_matches_center_cover_crop(self):
        from unittest.mock import patch
        from hf_video_provider import _journey_route_screen_position
        camera = {'stage_width': 960, 'stage_height': 480, 'crop_x': 0, 'crop_y': 0}
        # A 3:2 source scaled to width 960 is 640px tall; fit crops 80px
        # from each vertical edge. Original y=.6 must become 304, not 288.
        with patch('hf_video_provider._sample_background_route', return_value=(.5, .6)), \
             patch('hf_video_provider._background_camera_values', return_value=camera):
            position = _journey_route_screen_position(
                progress=.5, width=960, height=480,
                motion_plan={'background_key': 'fantasy_castle_gate'},
            )
        self.assertEqual(position, (480, 304))

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
                    self.assertGreaterEqual(
                        image.width / image.height, asset.get('min_aspect_ratio', 2.4)
                    )

    def test_story_pack_selection_and_routes(self):
        from story_background_pack import PACK, STORY_BACKGROUND_ROUTES
        from hf_video_provider import _sample_background_route
        for key, genres, keywords, route in PACK:
            with self.subTest(key=key):
                selected = select_background_asset(genres[0], keywords[0])
                self.assertEqual(selected['key'], key)
                self.assertEqual(selected['video_source'], 'landscape_asset')
                self.assertTrue(selected['path'].is_file())
                self.assertEqual(STORY_BACKGROUND_ROUTES[key], tuple(route))
                for step in range(101):
                    x, y = _sample_background_route(key, step / 100)
                    self.assertTrue(0 <= x <= 1 and 0 <= y <= 1)


if __name__ == "__main__":
    unittest.main()
