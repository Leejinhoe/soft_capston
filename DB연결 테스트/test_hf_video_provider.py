import asyncio
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat

from hf_video_provider import (
    BACKGROUND_JOURNEY_ROUTES,
    _blend_bottom_aligned,
    _background_camera_values,
    _background_stage_spec,
    _character_motion_values,
    _draw_action_effects,
    _fit_background,
    _journey_route_screen_position,
    _lock_grounded_action_legs,
    _motion_timeline,
    _optical_flow_interpolate,
    _prepare_background_stage,
    _prepare_motion_sheet,
    _prepare_run_cycle_sheet,
    _render_frame,
    _render_layered_frame,
    _select_motion_pose,
    _select_action_sheet_pose,
    _select_dedicated_action_cycle_pose,
    _select_jump_cycle_pose,
    _select_posture_cycle_pose,
    _select_run_cycle_pose,
    build_video_motion_plan,
    build_fairytale_video_prompt,
    generate_hf_fairytale_video,
    _normalize_frame_count,
    _paste_character_layer,
)


class HfVideoProviderTests(unittest.TestCase):
    @staticmethod
    def _motion_sheet():
        sheet = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sheet)
        colors = (
            "#777777",
            "#ff2020",
            "#2060ff",
            "#ff9d20",
            "#b020ff",
            "#202020",
            "#20bb70",
            "#ffe020",
        )
        for index, color in enumerate(colors):
            column = index % 4
            row = index // 4
            left = column * 100
            top = row * 100
            draw.rectangle((left + 20, top + 10, left + 80, top + 90), fill=color)
        return sheet

    def test_motion_sheet_is_split_into_eight_visible_cells(self):
        cells = _prepare_motion_sheet(self._motion_sheet(), Image)

        self.assertEqual(len(cells), 8)
        self.assertTrue(all(cell.getchannel("A").getbbox() for cell in cells))
        self.assertEqual(len({cell.size for cell in cells}), 1)
        self.assertTrue(
            all(cell.getchannel("A").getbbox()[3] == cell.height for cell in cells)
        )

    def test_idle_action_adds_no_unmotivated_particles(self):
        frame = Image.new("RGBA", (320, 180), (0, 0, 0, 0))

        _draw_action_effects(
            frame=frame,
            Image=Image,
            ImageDraw=ImageDraw,
            ImageFilter=ImageFilter,
            action="idle",
            progress=0.5,
            center_x=160,
            ground_y=165,
            character_width=80,
            character_height=140,
        )

        self.assertIsNone(frame.getchannel("A").getbbox())

    def test_v28_quality_review_can_suppress_decorative_effect_layers(self):
        frame = Image.new("RGBA", (320, 180), (0, 0, 0, 0))

        _draw_action_effects(
            frame=frame,
            Image=Image,
            ImageDraw=ImageDraw,
            ImageFilter=ImageFilter,
            action="battle",
            progress=0.52,
            center_x=160,
            ground_y=165,
            character_width=80,
            character_height=140,
            suppress_effects=True,
        )

        self.assertIsNone(frame.getchannel("A").getbbox())

    def test_v28_cycle_reports_selection_duration_and_fallback_metadata(self):
        background = Image.new("RGBA", (320, 180), "#8ec7ee")
        character = Image.new("RGBA", (80, 140), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((20, 8, 60, 132), fill="#d95050")
        cycle = self._motion_sheet()

        def png_bytes(image):
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        result = asyncio.run(
            generate_hf_fairytale_video(
                image_bytes=png_bytes(background),
                story_text="The hero steps forward and swings a sword.",
                width=256,
                height=256,
                num_frames=12,
                frame_rate=6,
                motion_context={
                    "background_key": "fantasy_castle",
                    "background_bytes": png_bytes(background),
                    "character_key": "male_01",
                    "character_bytes": png_bytes(character),
                    "character_battle_cycle_sheet_bytes": png_bytes(cycle),
                    "motion_asset_version": "v28",
                    "suppress_action_effects": True,
                    "action_semantics": {
                        "motion_mode": "stationary",
                        "animation_action": "battle",
                        "participant_count": 1,
                        "requires_partner": False,
                    },
                },
            )
        )

        parameters = result["parameters"]
        self.assertEqual(parameters["animation_mode"], "identity_locked_action_cycle_v28_stable_alpha")
        self.assertEqual(parameters["motion_asset_tier"], "dedicated_action_cycle")
        self.assertEqual(parameters["motion_asset_version"], "v28")
        self.assertEqual(parameters["dedicated_action_cycle_version"], "v28")
        self.assertEqual(parameters["num_frames"], 12)
        self.assertEqual(parameters["frame_rate"], 6)
        self.assertEqual(parameters["duration_seconds"], 2.0)
        self.assertFalse(parameters["motion_fallback_used"])
        self.assertTrue(parameters["action_effects_suppressed"])
        self.assertEqual(
            parameters["compositor_mode"],
            "cinematic_action_compositor_v29_stable_alpha",
        )
        self.assertIn(b"ftyp", result["video_bytes"][:64])

    def test_missing_v28_cycle_marks_reference_fallback_in_metadata(self):
        background = Image.new("RGBA", (320, 180), "#8ec7ee")
        character = Image.new("RGBA", (80, 140), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((20, 8, 60, 132), fill="#d95050")

        def png_bytes(image):
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        result = asyncio.run(
            generate_hf_fairytale_video(
                image_bytes=png_bytes(background),
                story_text="The hero jumps over a branch.",
                width=256,
                height=256,
                num_frames=6,
                frame_rate=6,
                motion_context={
                    "background_bytes": png_bytes(background),
                    "character_bytes": png_bytes(character),
                    "motion_asset_version": "v28",
                    "action_semantics": {
                        "motion_mode": "stationary",
                        "animation_action": "jump",
                        "participant_count": 1,
                        "requires_partner": False,
                    },
                },
            )
        )

        self.assertTrue(result["parameters"]["motion_fallback_used"])
        self.assertEqual(
            result["parameters"]["motion_fallback_reason"],
            "semantic_action_asset_missing",
        )
        self.assertEqual(
            result["parameters"]["animation_mode"],
            "reference_transform_v29_semantic_fallback",
        )

    def test_legacy_action_version_is_explicitly_marked(self):
        background = Image.new("RGBA", (320, 180), "#8ec7ee")
        character = Image.new("RGBA", (80, 140), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((20, 8, 60, 132), fill="#d95050")

        def png_bytes(image):
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        result = asyncio.run(
            generate_hf_fairytale_video(
                image_bytes=png_bytes(background),
                story_text="The hero steps forward and swings a sword.",
                width=256,
                height=256,
                num_frames=6,
                frame_rate=6,
                motion_context={
                    "background_bytes": png_bytes(background),
                    "character_bytes": png_bytes(character),
                    "character_battle_cycle_sheet_bytes": png_bytes(self._motion_sheet()),
                    "motion_asset_version": "v23",
                    "action_semantics": {
                        "motion_mode": "stationary",
                        "animation_action": "battle",
                        "participant_count": 1,
                        "requires_partner": False,
                    },
                },
            )
        )

        self.assertTrue(result["parameters"]["motion_fallback_used"])
        self.assertEqual(
            result["parameters"]["motion_fallback_reason"],
            "legacy_action_asset_version",
        )

    def test_run_cycle_sheet_is_split_into_eight_normalized_cells(self):
        sheet = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sheet)
        for index in range(8):
            column = index % 4
            row = index // 4
            left = column * 100
            top = row * 100
            visible_bottom = top + 90 - (index % 4) * 6
            draw.rectangle(
                (left + 20, top + 10, left + 80, visible_bottom),
                fill=(index * 12, 80, 180, 255),
            )

        cells = _prepare_run_cycle_sheet(sheet, Image)

        self.assertEqual(len(cells), 8)
        self.assertTrue(all(cell.getchannel("A").getbbox() for cell in cells))
        self.assertEqual(len({cell.size for cell in cells}), 1)
        visible_heights = {
            cell.getchannel("A").getbbox()[3] - cell.getchannel("A").getbbox()[1]
            for cell in cells
        }
        self.assertGreater(len(visible_heights), 1)

    def test_run_cycle_uses_discrete_identity_locked_frames(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]

        first = _select_run_cycle_pose(
            cells,
            progress=0.02,
            pace="run",
            duration_seconds=8.0,
        )
        second = _select_run_cycle_pose(
            cells,
            progress=0.035,
            pace="run",
            duration_seconds=8.0,
        )

        self.assertIs(first, cells[1])
        self.assertIs(second, cells[2])

    def test_jump_cycle_plays_once_and_returns_to_idle(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]

        selected = [
            _select_jump_cycle_pose(cells, progress=progress).getpixel((0, 0))[0]
            for progress in (0.0, 0.38, 0.42, 0.46, 0.50, 0.53, 1.0)
        ]

        self.assertEqual(selected[0], 7)
        self.assertIn(3, selected)
        self.assertIn(5, selected)
        self.assertEqual(selected[-1], 7)

    def test_jump_cycle_smooths_adjacent_key_poses_on_the_shared_canvas(self):
        cells = [Image.new("RGBA", (20, 24), (40, 80, 160, 255)) for _ in range(8)]
        cells[7] = Image.new("RGBA", (20, 24), (220, 40, 40, 255))
        cells[0] = Image.new("RGBA", (20, 24), (40, 80, 220, 255))

        interpolated = _select_jump_cycle_pose(
            cells,
            progress=0.385,
            Image=Image,
            interpolation_cache={},
        )

        self.assertEqual(interpolated.size, (20, 24))
        self.assertNotEqual(interpolated.tobytes(), cells[7].tobytes())
        self.assertNotEqual(interpolated.tobytes(), cells[0].tobytes())

    def test_action_sheet_uses_distinct_semantic_pose_sequences(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]

        expected_active_cells = {
            "wave": {1},
            "investigate": {2},
            "interaction": {3},
            "rescue": {3},
            "magic": {4, 5},
            "battle": {6, 7},
        }
        for action, expected in expected_active_cells.items():
            selected = {
                _select_action_sheet_pose(
                    cells,
                    action=action,
                    progress=index / 20,
                ).getpixel((0, 0))[0]
                for index in range(21)
            }
            self.assertTrue(expected.issubset(selected))
            self.assertTrue(selected.issubset({0, *expected}))

    def test_action_sheet_smooths_pose_changes_without_moving_the_feet(self):
        cells = [Image.new("RGBA", (18, 24), (40, 80, 160, 255)) for _ in range(8)]
        cells[1] = Image.new("RGBA", (18, 24), (220, 40, 40, 255))

        interpolated = _select_action_sheet_pose(
            cells,
            action="wave",
            progress=0.22,
            Image=Image,
            interpolation_cache={},
        )

        self.assertNotEqual(interpolated.getpixel((9, 2)), cells[0].getpixel((9, 2)))
        self.assertNotEqual(interpolated.getpixel((9, 2)), cells[1].getpixel((9, 2)))
        self.assertIn(
            interpolated.getpixel((9, 23)),
            {cells[0].getpixel((9, 23)), cells[1].getpixel((9, 23))},
        )

    def test_generic_investigate_uses_the_lower_reaching_pose(self):
        timeline = _motion_timeline("investigate", "walk", "primary")
        active_poses = {pose for time, pose in timeline if 0.2 < time < 0.9}

        self.assertIn(6, active_poses)
        self.assertNotIn(7, active_poses)

    def test_dedicated_action_cycle_visits_all_frames_in_order(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]
        selected = [
            _select_dedicated_action_cycle_pose(
                cells,
                action="magic",
                progress=0.18 + (0.56 * index / 28),
            ).getpixel((0, 0))[0]
            for index in range(29)
        ]

        self.assertEqual(selected[0], 0)
        self.assertEqual(selected[-1], 7)
        self.assertEqual(set(selected), set(range(8)))
        self.assertEqual(selected, sorted(selected))

    def test_dedicated_action_cycle_uses_more_of_the_video(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]

        self.assertIs(
            _select_dedicated_action_cycle_pose(
                cells, action="battle", progress=0.12
            ),
            cells[0],
        )
        self.assertIsNot(
            _select_dedicated_action_cycle_pose(
                cells, action="battle", progress=0.30
            ),
            cells[0],
        )
        self.assertIs(
            _select_dedicated_action_cycle_pose(
                cells, action="battle", progress=0.80
            ),
            cells[-1],
        )

    def test_sit_and_stand_dedicated_cycles_reach_the_authored_end_pose(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]

        for action in ("sit", "stand"):
            with self.subTest(action=action):
                start = _select_dedicated_action_cycle_pose(
                    cells, action=action, progress=0.05
                )
                middle = _select_dedicated_action_cycle_pose(
                    cells, action=action, progress=0.45
                )
                end = _select_dedicated_action_cycle_pose(
                    cells, action=action, progress=0.90
                )
                self.assertIs(start, cells[0])
                self.assertNotIn(middle.getpixel((0, 0))[0], {0, 7})
                self.assertIs(end, cells[7])

    def test_posture_cycle_keeps_the_readable_seated_pose(self):
        sit_cells = [
            Image.new("RGBA", (10, 10), (10 + index, 0, 0, 255))
            for index in range(8)
        ]
        stand_cells = [
            Image.new("RGBA", (10, 10), (30 + index, 0, 0, 255))
            for index in range(8)
        ]

        seated = _select_posture_cycle_pose(
            sit_cells, stand_cells, action="sit", progress=0.90
        )
        stand_start = _select_posture_cycle_pose(
            sit_cells, stand_cells, action="stand", progress=0.05
        )
        upright = _select_posture_cycle_pose(
            sit_cells, stand_cells, action="stand", progress=0.90
        )
        rising = _select_posture_cycle_pose(
            sit_cells, stand_cells, action="stand", progress=0.45
        )

        self.assertIs(seated, sit_cells[4])
        self.assertIs(stand_start, sit_cells[4])
        self.assertIn(rising, sit_cells[1:4])
        self.assertIs(upright, stand_cells[7])

    def test_frame_count_is_capped_at_fifteen_seconds(self):
        self.assertEqual(_normalize_frame_count(9999, 24), 360)

    def test_frame_count_honors_shorter_requested_duration(self):
        self.assertEqual(_normalize_frame_count(180, 30), 180)
        self.assertEqual(_normalize_frame_count(60, 30), 60)

    def test_run_cycle_uses_both_alternating_leg_halves_in_order(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]

        selected = [
            _select_run_cycle_pose(
                cells,
                progress=(index + 0.25) / 16.0,
                pace="run",
                duration_seconds=2.0,
            )
            for index in range(8)
        ]

        self.assertEqual(selected, cells)

    def test_walk_cycle_uses_reduced_contact_pose_sequence(self):
        cells = [Image.new("RGBA", (10, 10), (index, 0, 0, 255)) for index in range(8)]
        selected = {
            _select_run_cycle_pose(
                cells,
                progress=index / 32.0,
                pace="walk",
                duration_seconds=2.0,
            ).getpixel((0, 0))[0]
            for index in range(33)
        }

        self.assertEqual(selected, {0, 1, 4, 5})

    def test_run_cycle_interpolates_between_adjacent_key_poses(self):
        import cv2
        import numpy as np

        cells = [Image.new("RGBA", (24, 24), (40, 80, 160, 255)) for _ in range(8)]
        cells[0] = Image.new("RGBA", (24, 24), (220, 40, 40, 255))
        cells[1] = Image.new("RGBA", (24, 24), (40, 80, 220, 255))

        interpolated = _select_run_cycle_pose(
            cells,
            progress=0.06,
            pace="run",
            duration_seconds=1.0,
            Image=Image,
            cv2=cv2,
            np=np,
            interpolation_cache={},
        )

        self.assertNotEqual(interpolated.tobytes(), cells[0].tobytes())
        self.assertNotEqual(interpolated.tobytes(), cells[1].tobytes())

    def test_run_cycle_uses_linear_time_between_key_poses(self):
        cells = [Image.new("RGBA", (8, 8), (40, 80, 160, 255)) for _ in range(8)]
        cells[0] = Image.new("RGBA", (8, 8), (220, 40, 40, 255))
        cells[1] = Image.new("RGBA", (8, 8), (40, 80, 220, 255))

        interpolated = _select_run_cycle_pose(
            cells,
            progress=1.0 / 64.0,
            pace="run",
            duration_seconds=2.0,
            Image=Image,
        )

        self.assertEqual(interpolated.getpixel((4, 4)), (175, 50, 85, 255))

    def test_run_cycle_keeps_nearest_leg_pose_during_interpolation(self):
        cells = [Image.new("RGBA", (16, 16), (40, 80, 160, 255)) for _ in range(8)]
        cells[0] = Image.new("RGBA", (16, 16), (220, 40, 40, 255))
        cells[1] = Image.new("RGBA", (16, 16), (40, 80, 220, 255))

        interpolated = _select_run_cycle_pose(
            cells,
            progress=1.0 / 48.0,
            pace="run",
            duration_seconds=2.0,
            Image=Image,
        )

        self.assertNotEqual(interpolated.getpixel((8, 2)), cells[0].getpixel((8, 2)))
        self.assertEqual(interpolated.getpixel((8, 15)), cells[0].getpixel((8, 15)))

    def test_run_cycle_interpolation_preserves_the_normalized_canvas(self):
        cells = []
        for index in range(8):
            cell = Image.new("RGBA", (40, 48), (0, 0, 0, 0))
            draw = ImageDraw.Draw(cell)
            width = 14 + index
            height = 30 + (index % 3) * 4
            draw.rectangle(
                ((40 - width) // 2, 48 - height, (40 + width) // 2, 47),
                fill=(40 + index * 15, 80, 180, 255),
            )
            cells.append(cell)

        selected_sizes = {
            _select_run_cycle_pose(
                cells,
                progress=index / 23,
                pace="run",
                duration_seconds=1.0,
                Image=Image,
                interpolation_cache={},
            ).size
            for index in range(24)
        }

        self.assertEqual(selected_sizes, {(40, 48)})

    def test_grounded_action_interpolation_keeps_nearest_lower_body(self):
        interpolated = Image.new("RGBA", (18, 24), (40, 80, 220, 255))
        discrete = Image.new("RGBA", (18, 24), (220, 40, 40, 255))

        grounded = _lock_grounded_action_legs(
            interpolated,
            discrete,
            Image,
        )

        self.assertEqual(grounded.size, (18, 24))
        self.assertEqual(grounded.getpixel((9, 2)), interpolated.getpixel((9, 2)))
        self.assertEqual(grounded.getpixel((9, 23)), discrete.getpixel((9, 23)))

    def test_target_camera_keeps_fractional_pan_coordinates(self):
        plan = build_video_motion_plan(
            story_text="The child runs toward the castle.",
            character_pose="walking",
            background_key="fantasy_castle",
        )

        camera = _background_camera_values(768, 384, 0.123, plan)

        self.assertIsInstance(camera["crop_x"], float)
        self.assertNotEqual(camera["crop_x"], round(camera["crop_x"]))

    def test_character_motion_focus_reduces_camera_follow(self):
        character_plan = {
            "action": "magic",
            "target": "castle",
            "background_key": "fantasy_castle",
            "motion_focus": "character",
        }
        camera_plan = {**character_plan, "motion_focus": "camera"}

        character_span = (
            _background_camera_values(768, 384, 0.82, character_plan)["crop_x"]
            - _background_camera_values(768, 384, 0.18, character_plan)["crop_x"]
        )
        camera_span = (
            _background_camera_values(768, 384, 0.82, camera_plan)["crop_x"]
            - _background_camera_values(768, 384, 0.18, camera_plan)["crop_x"]
        )

        self.assertGreater(camera_span, 0.0)
        self.assertLess(character_span, camera_span * 0.6)

    def test_stationary_posture_actions_keep_the_background_locked(self):
        for action in ("sit", "stand", "wave", "investigate"):
            plan = {
                "action": action,
                "target": "castle",
                "background_key": "fantasy_castle",
                "motion_focus": "character",
            }
            start = _background_camera_values(768, 384, 0.10, plan)
            end = _background_camera_values(768, 384, 384 / 480, plan)

            with self.subTest(action=action):
                self.assertEqual(start["crop_x"], end["crop_x"])
                self.assertEqual(start["crop_y"], end["crop_y"])

    def test_character_first_action_has_visible_root_motion(self):
        plan = {"motion_focus": "character"}
        battle_start = _character_motion_values(
            action="battle",
            progress=0.24,
            width=768,
            height=384,
            motion_strength=2,
            motion_plan=plan,
        )
        battle_strike = _character_motion_values(
            action="battle",
            progress=0.52,
            width=768,
            height=384,
            motion_strength=2,
            motion_plan=plan,
        )

        self.assertGreater(
            abs(battle_strike["center_x"] - battle_start["center_x"]),
            768 * 0.08,
        )
        self.assertNotEqual(battle_start["rotation"], battle_strike["rotation"])

    def test_motion_plan_marks_partner_actions_as_non_solo(self):
        solo = build_video_motion_plan(
            story_text="The hero jumps over a branch.",
            action_tags=["jumping"],
            action_semantics={
                "animation_action": "jump",
                "motion_mode": "stationary",
                "participant_count": 1,
            },
        )
        pair = build_video_motion_plan(
            story_text="The hero hands a map to a friend.",
            action_tags=["interacting"],
            action_semantics={
                "animation_action": "interaction",
                "motion_mode": "stationary",
                "participant_count": 2,
                "requires_partner": True,
                "requires_object": True,
            },
        )

        self.assertTrue(solo["solo_action"])
        self.assertFalse(pair["solo_action"])

    def test_walk_and_run_keep_the_same_api_action_but_expose_distinct_kinds(self):
        walk = build_video_motion_plan(
            story_text="The hero walks toward the castle.",
            action_tags=["walking"],
            background_key="fantasy_castle",
        )
        run = build_video_motion_plan(
            story_text="The hero runs toward the castle.",
            action_tags=["running"],
            background_key="fantasy_castle",
        )

        self.assertEqual(walk["action"], "journey")
        self.assertEqual(run["action"], "journey")
        self.assertEqual(walk["locomotion_kind"], "walk")
        self.assertEqual(run["locomotion_kind"], "run")
        self.assertEqual(walk["alignment"]["foot_contact"], "alternating_grounded")
        self.assertEqual(run["alignment"]["body_facing"], "toward_target")

    def test_stationary_sit_and_stand_are_not_mapped_to_journey(self):
        sit = build_video_motion_plan(
            story_text="The hero sits beneath the tree.",
            action_tags=["sitting"],
        )
        stand = build_video_motion_plan(
            story_text="The hero stands and looks ahead.",
            action_tags=["standing"],
        )

        self.assertEqual(sit["action"], "sit")
        self.assertEqual(stand["action"], "stand")
        self.assertEqual(sit["motion_mode"], "stationary")
        self.assertEqual(stand["motion_mode"], "stationary")
        self.assertTrue(all(key in sit["phase_timings"] for key in ("prepare", "act", "recover")))

    def test_sit_and_stand_have_distinct_phase_timelines(self):
        sit_poses = [pose for _, pose in _motion_timeline("sit", "walk", "primary")]
        stand_poses = [pose for _, pose in _motion_timeline("stand", "walk", "primary")]

        self.assertNotEqual(sit_poses, stand_poses)
        self.assertEqual(sit_poses[0], 0)
        self.assertEqual(sit_poses[-1], 6)
        self.assertEqual(stand_poses[0], 6)
        self.assertEqual(stand_poses[-1], 0)

    def test_rotated_character_uses_visible_feet_as_the_ground_anchor(self):
        frame = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        character = Image.new("RGBA", (24, 32), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((5, 4, 18, 29), fill=(220, 80, 40, 255))

        _paste_character_layer(
            frame=frame,
            character_image=character,
            Image=Image,
            ImageDraw=ImageDraw,
            ImageFilter=ImageFilter,
            center_x=50,
            ground_y=80,
            scale=0.32,
            rotation=12.0,
        )

        character_mask = Image.new("L", frame.size, 0)
        character_mask.putdata(
            [
                255 if red > 150 and green < 150 and blue < 120 else 0
                for red, green, blue, _ in frame.getdata()
            ]
        )
        bounds = character_mask.getbbox()
        self.assertIsNotNone(bounds)
        self.assertGreaterEqual(bounds[3], 78)
        self.assertLessEqual(bounds[3], 80)

    def test_character_layer_uses_stable_canvas_center_across_asymmetric_poses(self):
        class RecordingFrame:
            size = (100, 100)
            height = 100

            def __init__(self):
                self.placements = []

            def alpha_composite(self, _image, dest=None):
                if dest is not None:
                    self.placements.append(dest)

        positions = []
        for left in (2, 28):
            frame = RecordingFrame()
            character = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
            ImageDraw.Draw(character).rectangle(
                (left, 4, left + 9, 39),
                fill=(220, 80, 40, 255),
            )
            _paste_character_layer(
                frame=frame,
                character_image=character,
                Image=Image,
                ImageDraw=ImageDraw,
                ImageFilter=ImageFilter,
                center_x=50,
                ground_y=80,
                scale=0.40,
                rotation=0.0,
            )
            positions.append(frame.placements[-1][0])

        self.assertEqual(positions, [30, 30])

    def test_motion_prompt_carries_phase_and_alignment_contract(self):
        plan = build_video_motion_plan(
            story_text="The hero runs toward the castle.",
            action_tags=["running"],
            background_key="fantasy_castle",
        )
        prompt = build_fairytale_video_prompt(
            story_text="The hero runs toward the castle.",
            motion_plan=plan,
        )

        self.assertIn("prepare, act, and recover", prompt)
        self.assertIn("toward_target", prompt)
        self.assertIn("alternating_grounded", prompt)

    def test_journey_alternates_opposite_walking_poses(self):
        cells = _prepare_motion_sheet(self._motion_sheet(), Image)
        plan = build_video_motion_plan(
            story_text="The child walks toward the castle.",
            character_pose="walking",
            background_key="fantasy_castle",
        )

        first = _select_motion_pose(
            cells,
            motion_plan=plan,
            progress=0.20,
            Image=Image,
        )
        second = _select_motion_pose(
            cells,
            motion_plan=plan,
            progress=0.30,
            Image=Image,
        )

        self.assertNotEqual(first.tobytes(), second.tobytes())
        self.assertNotEqual(
            first.convert("RGB").getpixel((first.width // 2, first.height // 2)),
            second.convert("RGB").getpixel((second.width // 2, second.height // 2)),
        )

    def test_journey_timeline_repeats_both_foot_positions_and_returns_idle(self):
        timeline = _motion_timeline("journey", "walk", "primary")
        poses = [pose for _, pose in timeline]

        self.assertEqual(poses[0], 0)
        self.assertEqual(poses[-1], 0)
        self.assertGreaterEqual(poses.count(1), 5)
        self.assertGreaterEqual(poses.count(2), 5)

    def test_jump_sentence_builds_airborne_action(self):
        plan = build_video_motion_plan(
            story_text="The hero jumps over a fallen tree.",
            action_tags=["jumping"],
            background_key="fantasy_castle",
        )

        self.assertEqual(plan["action"], "jump")
        self.assertEqual(plan["motion_mode"], "stationary")
        self.assertEqual(plan["effects"], ["landing_dust"])

    def test_jump_motion_has_clear_airborne_and_landing_phases(self):
        plan = {"action": "jump"}
        start = _character_motion_values(
            action="jump", progress=0.0, width=768, height=384,
            motion_strength=2, motion_plan=plan,
        )
        airborne = _character_motion_values(
            action="jump", progress=0.46, width=768, height=384,
            motion_strength=2, motion_plan=plan,
        )
        landed = _character_motion_values(
            action="jump", progress=1.0, width=768, height=384,
            motion_strength=2, motion_plan=plan,
        )

        self.assertLess(airborne["ground_y"], start["ground_y"] - 80)
        self.assertLess(airborne["ground_contact"], 0.05)
        self.assertAlmostEqual(landed["ground_contact"], 1.0)

    def test_waving_is_distinct_from_conversation(self):
        plan = build_video_motion_plan(
            story_text="The child waves goodbye to a friend.",
            action_tags=["waving"],
        )
        poses = [pose for _, pose in _motion_timeline("wave", "walk", "primary")]

        self.assertEqual(plan["action"], "wave")
        self.assertEqual(plan["effects"], ["hand_motion_stroke"])
        self.assertGreaterEqual(poses.count(7), 4)

    def test_learned_motion_modifiers_change_video_plan(self):
        slow_plan = build_video_motion_plan(
            story_text="아이는 성을 향해 슬며시 걸었다.",
            action_tags=["walking"],
            motion_modifier_tags=["slow_subtle"],
        )
        fast_plan = build_video_motion_plan(
            story_text="아이는 성을 향해 날쌔게 움직였다.",
            action_tags=["walking"],
            motion_modifier_tags=["fast_agile"],
        )

        self.assertEqual(slow_plan["pace"], "walk")
        self.assertEqual(slow_plan["motion_style"], "slow subtle")
        self.assertEqual(fast_plan["pace"], "run")
        self.assertEqual(fast_plan["motion_style"], "fast agile")

    def test_korean_walk_conjugation_selects_journey_motion(self):
        plan = build_video_motion_plan(
            story_text="아이는 과수원 길을 슬며시 걸으며 웃었어요.",
            motion_modifier_tags=["slow_subtle"],
        )

        self.assertEqual(plan["action"], "journey")
        self.assertEqual(plan["pace"], "walk")

    def test_trembling_modifier_adds_visible_character_jitter(self):
        base = _character_motion_values(
            action="idle",
            progress=0.37,
            width=768,
            height=384,
            motion_strength=2,
            motion_plan={},
        )
        trembling = _character_motion_values(
            action="idle",
            progress=0.37,
            width=768,
            height=384,
            motion_strength=2,
            motion_plan={"source_motion_modifier_tags": ["trembling"]},
        )

        self.assertNotEqual(base["center_x"], trembling["center_x"])
        self.assertNotEqual(base["rotation"], trembling["rotation"])

    def test_investigation_and_interaction_do_not_use_magic_pose(self):
        expected_active_pose = {
            "investigate": 6,
            "interaction": 7,
        }
        for action, active_pose in expected_active_pose.items():
            with self.subTest(action=action):
                poses = [
                    pose
                    for _, pose in _motion_timeline(
                        action,
                        "walk",
                        "primary",
                    )
                ]

                self.assertNotIn(3, poses)
                self.assertNotIn(4, poses)
                self.assertIn(active_pose, poses)

    def test_target_facing_run_cycles_all_rear_view_cells(self):
        timeline = _motion_timeline(
            "journey",
            "run",
            "primary",
            target_facing=True,
        )
        poses = [pose for _, pose in timeline]

        self.assertEqual(set(poses), set(range(8)))
        self.assertEqual(len(poses), 20)

    def test_battle_timeline_has_anticipation_strike_and_follow_through(self):
        poses = [
            pose
            for _, pose in _motion_timeline("battle", "walk", "primary")
        ]

        self.assertEqual(set(poses), {0, 5})
        self.assertGreaterEqual(poses.count(5), 4)
        self.assertEqual(poses[-1], 0)

    def test_stationary_actions_do_not_borrow_unrelated_pose_cells(self):
        expected = {
            "magic": {0, 4},
            "battle": {0, 5},
            "rescue": {0, 6},
            "investigate": {0, 6},
            "interaction": {0, 7},
            "wave": {0, 7},
        }
        for action, allowed in expected.items():
            with self.subTest(action=action):
                poses = {
                    pose
                    for _, pose in _motion_timeline(action, "walk", "primary")
                }
                self.assertEqual(poses, allowed)

    def test_aim_timeline_holds_pose_without_running_cells(self):
        timeline = _motion_timeline(
            "battle",
            "walk",
            "primary",
            interaction_kind="aim",
        )
        poses = [pose for _, pose in timeline]

        self.assertEqual(poses, [0, 5, 5, 0])
        self.assertNotIn(1, poses)
        self.assertNotIn(2, poses)
        self.assertNotIn(3, poses)

    def test_optical_flow_keeps_more_opaque_pixels_than_crossfade(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("OpenCV is not installed")

        first = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        second = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        ImageDraw.Draw(first).rectangle((8, 18, 38, 72), fill="#e13e3eff")
        ImageDraw.Draw(second).rectangle((20, 18, 50, 72), fill="#e13e3eff")
        crossfade = _blend_bottom_aligned(first, second, 0.5, Image)
        interpolated = _optical_flow_interpolate(
            first,
            second,
            0.5,
            Image=Image,
            cv2=cv2,
            np=np,
            cache={},
            cache_key="moving-rectangle",
        )

        crossfade_opaque = sum(
            alpha >= 220 for alpha in crossfade.getchannel("A").getdata()
        )
        interpolated_opaque = sum(
            alpha >= 220 for alpha in interpolated.getchannel("A").getdata()
        )
        self.assertGreater(interpolated_opaque, crossfade_opaque)

    def test_optical_flow_preserves_chroma_on_transparent_edges(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("OpenCV is not installed")

        first = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        second = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(first).rectangle((10, 12, 40, 58), fill=(255, 0, 0, 160))
        ImageDraw.Draw(second).rectangle((14, 12, 44, 58), fill=(255, 0, 0, 160))
        interpolated = _optical_flow_interpolate(
            first,
            second,
            0.5,
            Image=Image,
            cv2=cv2,
            np=np,
            cache={},
            cache_key="premultiplied-red-rectangle",
        )

        partial = [
            pixel
            for pixel in interpolated.getdata()
            if 8 <= pixel[3] <= 240
        ]
        self.assertTrue(partial)
        self.assertTrue(all(red >= 245 for red, _, _, _ in partial))
        self.assertTrue(all(green <= 3 and blue <= 3 for _, green, blue, _ in partial))

    def test_dissimilar_silhouettes_use_a_clean_pose_cut(self):
        import cv2
        import numpy as np

        first = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        second = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        ImageDraw.Draw(first).rectangle((3, 15, 20, 74), fill="#e13e3eff")
        ImageDraw.Draw(second).rectangle((58, 15, 75, 74), fill="#2870dfff")
        interpolated = _optical_flow_interpolate(
            first,
            second,
            0.6,
            Image=Image,
            cv2=cv2,
            np=np,
            cache={},
            cache_key="dissimilar-poses",
        )

        self.assertEqual(interpolated.tobytes(), second.tobytes())

    def test_single_warp_transition_does_not_crossfade_two_character_poses(self):
        import cv2
        import numpy as np

        first = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        second = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        ImageDraw.Draw(first).rectangle((10, 12, 45, 74), fill="#e13e3eff")
        ImageDraw.Draw(second).rectangle((18, 12, 53, 74), fill="#2870dfff")

        early = _optical_flow_interpolate(
            first,
            second,
            0.35,
            Image=Image,
            cv2=cv2,
            np=np,
            cache={},
            cache_key="single-warp-early",
            prefer_single_warp=True,
        )
        late = _optical_flow_interpolate(
            first,
            second,
            0.65,
            Image=Image,
            cv2=cv2,
            np=np,
            cache={},
            cache_key="single-warp-late",
            prefer_single_warp=True,
        )

        early_colors = [pixel for pixel in early.getdata() if pixel[3] >= 64]
        late_colors = [pixel for pixel in late.getdata() if pixel[3] >= 64]
        self.assertTrue(all(red > blue for red, _, blue, _ in early_colors))
        self.assertTrue(all(blue > red for red, _, blue, _ in late_colors))

    def test_walking_to_castle_builds_a_journey_plan(self):
        plan = build_video_motion_plan(
            story_text="The child walks toward the castle.",
            character_pose="walking",
            action_tags=["walking"],
            background_key="fantasy_castle",
        )

        self.assertEqual(plan["action"], "journey")
        self.assertEqual(plan["target"], "castle")
        self.assertEqual(plan["effects"], ["grounded_steps"])

    def test_korean_conjugated_running_sentence_builds_a_fast_journey(self):
        plan = build_video_motion_plan(
            story_text="민호가 숲길을 달려 빛나는 성문을 향해 나아갔다.",
            background_key="fantasy_castle",
        )

        self.assertEqual(plan["action"], "journey")
        self.assertEqual(plan["target"], "castle")
        self.assertEqual(plan["pace"], "run")

    def test_learned_running_tag_sets_journey_and_run_pace(self):
        plan = build_video_motion_plan(
            story_text="용사는 괴물을 뒤쫓았어요.",
            action_tags=["running"],
            background_key="nature_pond",
        )

        self.assertEqual(plan["action"], "journey")
        self.assertEqual(plan["pace"], "run")

    def test_learned_interaction_tag_uses_interaction_motion(self):
        plan = build_video_motion_plan(
            story_text="아이는 친구에게 열쇠를 건네받았어요.",
            action_tags=["interacting"],
            background_key="mystery_library",
        )

        self.assertEqual(plan["action"], "interaction")
        self.assertEqual(plan["effects"], ["object_transfer"])

    def test_handoff_semantics_force_stationary_two_person_interaction(self):
        plan = build_video_motion_plan(
            story_text="하나는 친구에게 열쇠를 건네받은 뒤 문으로 걸어갔어요.",
            action_tags=["interacting", "walking"],
            action_semantics={
                "motion_mode": "stationary",
                "participant_count": 2,
                "requires_partner": True,
                "animation_action": "interaction",
                "interaction_kind": "handoff_receive",
                "subject_role": "receiver",
                "partner_role": "giver",
                "source_word": "건네받다",
            },
            background_key="mystery_library",
        )

        self.assertEqual(plan["action"], "interaction")
        self.assertEqual(plan["motion_mode"], "stationary")
        self.assertEqual(plan["participant_count"], 2)
        self.assertTrue(plan["requires_partner"])
        self.assertEqual(plan["interaction_kind"], "handoff_receive")
        self.assertEqual(plan["semantic_source_word"], "건네받다")

    def test_motion_plan_keeps_target_and_prop_requirements_separate(self):
        plan = build_video_motion_plan(
            story_text="궁수가 과녁을 겨누었다.",
            action_tags=["fighting"],
            action_semantics={
                "motion_mode": "stationary",
                "participant_count": 1,
                "requires_partner": False,
                "animation_action": "battle",
                "interaction_kind": "aim",
                "requires_object": True,
                "object_role": "weapon",
                "requires_target": True,
                "target_type": "person_or_object",
                "body_focus": "arms_and_gaze",
                "temporal_pattern": "held_pose",
            },
        )

        self.assertEqual(plan["action"], "battle")
        self.assertFalse(plan["requires_partner"])
        self.assertTrue(plan["requires_object"])
        self.assertEqual(plan["object_role"], "weapon")
        self.assertTrue(plan["requires_target"])
        self.assertEqual(plan["body_focus"], "arms_and_gaze")

    def test_semantic_pace_controls_unmapped_locomotion_verb(self):
        plan = build_video_motion_plan(
            story_text="아이는 마당을 부산하게 설치었다.",
            action_semantics={
                "motion_mode": "locomotion",
                "participant_count": 1,
                "requires_partner": False,
                "animation_action": "journey",
                "interaction_kind": "move_erratically",
                "path_pattern": "erratic",
                "pace": "run",
            },
        )

        self.assertEqual(plan["action"], "journey")
        self.assertEqual(plan["pace"], "run")
        self.assertEqual(plan["path_pattern"], "erratic")

    def test_weather_clearing_visibly_removes_fog(self):
        source = Image.new("RGB", (640, 384), "#315d42")
        ImageDraw.Draw(source).rectangle((320, 0, 639, 383), fill="#e2ad43")
        plan = build_video_motion_plan(
            story_text="안개가 걷혔다.",
            action_semantics={
                "motion_mode": "environmental",
                "participant_count": 0,
                "animation_action": "idle",
                "interaction_kind": "weather_clearing",
            },
        )

        start = _render_frame(
            source_image=source,
            Image=Image,
            ImageEnhance=ImageEnhance,
            ImageOps=ImageOps,
            width=512,
            height=384,
            progress=0.0,
            motion_strength=2,
            motion_plan=plan,
        )
        end = _render_frame(
            source_image=source,
            Image=Image,
            ImageEnhance=ImageEnhance,
            ImageOps=ImageOps,
            width=512,
            height=384,
            progress=1.0,
            motion_strength=2,
            motion_plan=plan,
        )

        self.assertGreater(
            sum(ImageStat.Stat(end).stddev),
            sum(ImageStat.Stat(start).stddev),
        )

    def test_learned_emotion_verb_uses_readable_expression_motion(self):
        plan = build_video_motion_plan(
            story_text="아이는 안도의 눈물을 흘리며 흐느꼈어요.",
            action_tags=["emoting"],
            background_key="friendship_square",
        )

        self.assertEqual(plan["action"], "conversation")

    def test_target_journey_uses_a_wide_tracking_background_stage(self):
        plan = build_video_motion_plan(
            story_text="The child runs toward the castle.",
            background_key="fantasy_castle",
        )
        stage = _background_stage_spec(768, 384, plan)

        self.assertGreaterEqual(stage["width_scale"], 1.45)
        self.assertGreater(stage["pan_end"] - stage["pan_start"], 0.50)

    def test_each_panorama_assigns_its_own_journey_destination(self):
        expected_targets = {
            "fantasy_castle": "castle",
            "adventure_ruins": "ruins",
            "nature_pond": "forest",
            "friendship_square": "village",
            "mystery_library": "clue",
            "fantasy_crystal_cave": "portal",
            "adventure_harbor": "ship",
            "nature_snowfield": "refuge",
            "friendship_festival": "pavilion",
            "mystery_clocktower": "clock_door",
        }
        for background_key, target in expected_targets.items():
            with self.subTest(background_key=background_key):
                plan = build_video_motion_plan(
                    story_text="The child runs forward.",
                    background_key=background_key,
                )
                self.assertEqual(plan["action"], "journey")
                self.assertEqual(plan["target"], target)
                self.assertEqual(plan["background_key"], background_key)

    def test_each_panorama_route_moves_forward_and_deeper(self):
        for background_key in BACKGROUND_JOURNEY_ROUTES:
            with self.subTest(background_key=background_key):
                plan = build_video_motion_plan(
                    story_text="The child runs forward.",
                    background_key=background_key,
                )
                positions = [
                    _journey_route_screen_position(
                        progress=progress,
                        width=768,
                        height=384,
                        motion_plan=plan,
                    )
                    for progress in (0.0, 0.25, 0.5, 0.75, 1.0)
                ]
                self.assertTrue(all(position is not None for position in positions))
                x_values = [position[0] for position in positions]
                y_values = [position[1] for position in positions]
                self.assertEqual(x_values, sorted(x_values))
                self.assertEqual(y_values, sorted(y_values, reverse=True))
                self.assertGreater(x_values[-1] - x_values[0], 80)
                self.assertGreater(y_values[0] - y_values[-1], 100)

    def test_castle_route_stays_on_the_visible_road(self):
        plan = build_video_motion_plan(
            story_text="The child runs toward the castle.",
            background_key="fantasy_castle",
        )
        positions = [
            _journey_route_screen_position(
                progress=progress,
                width=768,
                height=384,
                motion_plan=plan,
            )
            for progress in (0.0, 0.25, 0.5, 0.75, 1.0)
        ]

        self.assertGreater(positions[0][0], 768 * 0.70)
        self.assertGreater(positions[0][1], 384 * 0.90)
        self.assertGreater(positions[-1][0], positions[0][0])
        self.assertLess(positions[-1][1], 384 * 0.55)

    def test_target_journey_crosses_most_of_the_wide_route(self):
        start = _character_motion_values(
            action="journey",
            progress=0.0,
            width=768,
            height=384,
            motion_strength=2,
        )
        end = _character_motion_values(
            action="journey",
            progress=1.0,
            width=768,
            height=384,
            motion_strength=2,
        )

        self.assertAlmostEqual(start["center_x"], 768 * 0.16)
        self.assertAlmostEqual(end["center_x"], 768 * 0.63)
        self.assertGreater(end["center_x"] - start["center_x"], 768 * 0.45)

    def test_target_journey_pans_across_a_wide_background(self):
        background = Image.new("RGBA", (1600, 500), (0, 0, 0, 255))
        draw = ImageDraw.Draw(background)
        for x in range(background.width):
            amount = x / (background.width - 1)
            color = (round(255 * (1.0 - amount)), 80, round(255 * amount), 255)
            draw.line((x, 0, x, background.height), fill=color)
        plan = build_video_motion_plan(
            story_text="The child runs toward the castle.",
            background_key="fantasy_castle",
        )

        start = _fit_background(
            background,
            Image,
            ImageOps,
            768,
            384,
            0.0,
            plan,
        )
        end = _fit_background(
            background,
            Image,
            ImageOps,
            768,
            384,
            1.0,
            plan,
        )

        start_blue = ImageStat.Stat(start.convert("RGB")).mean[2]
        end_blue = ImageStat.Stat(end.convert("RGB")).mean[2]
        self.assertEqual(start.size, (768, 384))
        self.assertEqual(end.size, (768, 384))
        self.assertGreater(end_blue, start_blue + 20)

    def test_prepared_background_stage_matches_uncached_render(self):
        background = Image.new("RGBA", (500, 240), (40, 80, 120, 255))
        plan = build_video_motion_plan(
            story_text="The child runs toward the castle.",
            action_tags=["running"],
            background_key="fantasy_castle",
        )
        prepared = _prepare_background_stage(
            background,
            Image,
            ImageOps,
            320,
            160,
            plan,
        )
        uncached = _fit_background(
            background,
            Image,
            ImageOps,
            320,
            160,
            0.42,
            plan,
        )
        cached = _fit_background(
            background,
            Image,
            ImageOps,
            320,
            160,
            0.42,
            plan,
            prepared_background=prepared,
        )

        self.assertEqual(cached.tobytes(), uncached.tobytes())

    def test_magic_pose_takes_priority_over_generic_scene_words(self):
        plan = build_video_motion_plan(
            story_text="The hero walks through the forest.",
            character_pose="magic",
            action_tags=["walking"],
            effect_tags=["glowing_light"],
        )

        self.assertEqual(plan["action"], "magic")
        self.assertEqual(plan["effects"], ["hand_rune"])

    def test_layered_journey_changes_character_position_between_frames(self):
        background = Image.new("RGBA", (640, 480), "#8ec7ee")
        character = Image.new("RGBA", (180, 360), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((45, 25, 135, 340), fill="#d95050")
        plan = build_video_motion_plan(
            story_text="A hero walks toward the castle.",
            character_pose="walking",
            background_key="fantasy_castle",
        )
        _, _, ImageModule, ImageDrawModule, ImageEnhance, ImageFilter, ImageOps = (
            __import__("hf_video_provider")._load_video_dependencies()
        )
        start = _render_layered_frame(
            background_image=background,
            character_image=character,
            Image=ImageModule,
            ImageDraw=ImageDrawModule,
            ImageEnhance=ImageEnhance,
            ImageFilter=ImageFilter,
            ImageOps=ImageOps,
            width=512,
            height=384,
            progress=0.0,
            motion_strength=2,
            motion_plan=plan,
        )
        end = _render_layered_frame(
            background_image=background,
            character_image=character,
            Image=ImageModule,
            ImageDraw=ImageDrawModule,
            ImageEnhance=ImageEnhance,
            ImageFilter=ImageFilter,
            ImageOps=ImageOps,
            width=512,
            height=384,
            progress=1.0,
            motion_strength=2,
            motion_plan=plan,
        )

        self.assertNotEqual(start.tobytes(), end.tobytes())
        output = BytesIO()
        end.save(output, format="PNG")
        self.assertGreater(len(output.getvalue()), 100)

    def test_target_journey_uses_rear_view_sheet_instead_of_front_sheet(self):
        background = Image.new("RGBA", (640, 480), "#8ec7ee")
        character = Image.new("RGBA", (180, 360), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((45, 25, 135, 340), fill="#d95050")
        rear_sheet = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
        rear_draw = ImageDraw.Draw(rear_sheet)
        for index in range(8):
            column = index % 4
            row = index // 4
            rear_draw.rectangle(
                (column * 100 + 20, row * 100 + 10, column * 100 + 80, row * 100 + 90),
                fill="#20bb70",
            )
        rear_cells = _prepare_motion_sheet(rear_sheet, Image)
        plan = build_video_motion_plan(
            story_text="민호가 성을 향해 달려갔다.",
            background_key="fantasy_castle",
        )
        _, _, ImageModule, ImageDrawModule, ImageEnhance, ImageFilter, ImageOps = (
            __import__("hf_video_provider")._load_video_dependencies()
        )

        frame = _render_layered_frame(
            background_image=background,
            character_image=character,
            character_target_journey_motion_cells=rear_cells,
            Image=ImageModule,
            ImageDraw=ImageDrawModule,
            ImageEnhance=ImageEnhance,
            ImageFilter=ImageFilter,
            ImageOps=ImageOps,
            width=512,
            height=384,
            progress=0.5,
            motion_strength=3,
            motion_plan=plan,
        )

        green_pixels = sum(
            1
            for red, green, blue in frame.getdata()
            if green > 120 and green > red + 25 and green > blue + 20
        )
        self.assertGreater(green_pixels, 100)

    def test_missing_jump_cycle_uses_reference_instead_of_walking_cell(self):
        background = Image.new("RGBA", (320, 180), "#8ec7ee")
        reference = Image.new("RGBA", (60, 100), (0, 0, 0, 0))
        ImageDraw.Draw(reference).rectangle((15, 5, 45, 96), fill="#d95050")
        generic_cells = [
            Image.new("RGBA", (60, 100), "#20bb70")
            for _ in range(8)
        ]
        plan = build_video_motion_plan(
            story_text="The hero jumps over a branch.",
            action_tags=["jumping"],
            action_semantics={"animation_action": "jump"},
        )

        frame = _render_layered_frame(
            background_image=background,
            character_image=reference,
            character_motion_cells=generic_cells,
            Image=Image,
            ImageDraw=ImageDraw,
            ImageEnhance=ImageEnhance,
            ImageFilter=ImageFilter,
            ImageOps=ImageOps,
            width=320,
            height=180,
            progress=0.5,
            motion_strength=3,
            motion_plan=plan,
        )

        red_pixels = sum(
            1
            for red, green, blue in frame.getdata()
            if red > 140 and red > green + 30 and red > blue + 20
        )
        green_pixels = sum(
            1
            for red, green, blue in frame.getdata()
            if green > 140 and green > red + 30 and green > blue + 20
        )
        self.assertGreater(red_pixels, 100)
        self.assertEqual(green_pixels, 0)

    def test_all_sixteen_profiles_use_identity_safe_reference_fallbacks(self):
        asset_dir = Path(__file__).resolve().parents[1] / "assets" / "characters"
        background = Image.new("RGBA", (160, 96), "#8ec7ee")
        generic_cells = [
            Image.new("RGBA", (60, 100), (0, 255, 0, 255))
            for _ in range(8)
        ]
        character_keys = [
            f"{gender}_{index:02d}"
            for gender in ("female", "male")
            for index in range(1, 9)
        ]

        for character_key in character_keys:
            reference_path = asset_dir / f"{character_key}_reference_v2.png"
            self.assertTrue(reference_path.is_file(), reference_path)
            reference = Image.open(reference_path).convert("RGBA")
            for action in ("jump", "investigate", "interaction", "sit", "stand"):
                with self.subTest(character=character_key, action=action):
                    plan = build_video_motion_plan(
                        story_text=f"The hero performs {action}.",
                        action_semantics={"animation_action": action},
                    )
                    frame = _render_layered_frame(
                        background_image=background,
                        character_image=reference,
                        character_motion_cells=generic_cells,
                        Image=Image,
                        ImageDraw=ImageDraw,
                        ImageEnhance=ImageEnhance,
                        ImageFilter=ImageFilter,
                        ImageOps=ImageOps,
                        width=160,
                        height=96,
                        progress=0.5,
                        motion_strength=3,
                        motion_plan=plan,
                    )
                    neon_green = sum(
                        1
                        for red, green, blue in frame.getdata()
                        if green > 240 and red < 20 and blue < 20
                    )
                    self.assertEqual(neon_green, 0)

    def test_battle_frame_includes_secondary_character(self):
        background = Image.new("RGBA", (640, 480), "#8ec7ee")
        primary = Image.new("RGBA", (180, 360), (0, 0, 0, 0))
        secondary = Image.new("RGBA", (180, 360), (0, 0, 0, 0))
        ImageDraw.Draw(primary).rectangle((45, 25, 135, 340), fill="#d95050")
        ImageDraw.Draw(secondary).rectangle((45, 25, 135, 340), fill="#3471cb")
        plan = build_video_motion_plan(
            story_text="The hero battles the dragon.",
            character_pose="angry",
            action_tags=["fighting"],
        )
        _, _, ImageModule, ImageDrawModule, ImageEnhance, ImageFilter, ImageOps = (
            __import__("hf_video_provider")._load_video_dependencies()
        )

        frame = _render_layered_frame(
            background_image=background,
            character_image=primary,
            secondary_character_image=secondary,
            Image=ImageModule,
            ImageDraw=ImageDrawModule,
            ImageEnhance=ImageEnhance,
            ImageFilter=ImageFilter,
            ImageOps=ImageOps,
            width=512,
            height=384,
            progress=0.5,
            motion_strength=3,
            motion_plan=plan,
        )

        blue_pixels = sum(
            1
            for red, green, blue in frame.getdata()
            if blue > 140 and blue > red + 30 and blue > green + 20
        )
        self.assertGreater(blue_pixels, 100)

    def test_handoff_frame_includes_partner_and_transferred_key(self):
        background = Image.new("RGBA", (640, 480), "#606878")
        primary = Image.new("RGBA", (180, 360), (0, 0, 0, 0))
        secondary = Image.new("RGBA", (180, 360), (0, 0, 0, 0))
        ImageDraw.Draw(primary).rectangle((45, 25, 135, 340), fill="#d95050")
        ImageDraw.Draw(secondary).rectangle((45, 25, 135, 340), fill="#3471cb")
        plan = build_video_motion_plan(
            story_text="아이는 친구에게 열쇠를 건네받았어요.",
            action_tags=["interacting"],
            action_semantics={
                "motion_mode": "stationary",
                "participant_count": 2,
                "requires_partner": True,
                "animation_action": "interaction",
                "interaction_kind": "handoff_receive",
            },
        )
        _, _, ImageModule, ImageDrawModule, ImageEnhance, ImageFilter, ImageOps = (
            __import__("hf_video_provider")._load_video_dependencies()
        )

        frame = _render_layered_frame(
            background_image=background,
            character_image=primary,
            secondary_character_image=secondary,
            Image=ImageModule,
            ImageDraw=ImageDrawModule,
            ImageEnhance=ImageEnhance,
            ImageFilter=ImageFilter,
            ImageOps=ImageOps,
            width=512,
            height=384,
            progress=0.55,
            motion_strength=2,
            motion_plan=plan,
        )

        blue_pixels = sum(
            1
            for red, green, blue in frame.getdata()
            if blue > 140 and blue > red + 30 and blue > green + 20
        )
        gold_pixels = sum(
            1
            for red, green, blue in frame.getdata()
            if red > 210 and green > 170 and blue < 170
        )
        self.assertGreater(blue_pixels, 100)
        self.assertGreater(gold_pixels, 10)


if __name__ == "__main__":
    unittest.main()
