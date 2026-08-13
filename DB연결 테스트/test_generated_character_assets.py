import hashlib
import importlib.util
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path

from PIL import Image, ImageColor


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "tools" / "generate_character_assets.py"
ASSET_DIR = ROOT / "assets" / "characters"
MOTION_SHEET_DIR = ASSET_DIR / "motion_sheets"
POSES = ("default", "happy", "sad", "angry", "walking", "talking", "magic", "rescue")
KEYS = tuple(
    [f"male_{index:02d}" for index in range(1, 9)]
    + [f"female_{index:02d}" for index in range(1, 9)]
)
PREMIUM_REFERENCES = {
    f"{key}_reference_v2.png"
    for key in KEYS
}

spec = importlib.util.spec_from_file_location("generate_character_assets", GENERATOR_PATH)
generator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


class GeneratedCharacterAssetTests(unittest.TestCase):
    def test_motion_sheet_matrix_has_eight_visible_transparent_cells(self):
        expected = {f"{key}_motion_sheet_v3.png" for key in KEYS}
        target_expected = {
            f"{key}_target_journey_sheet_v4.png" for key in KEYS
        }
        legacy_run_cycle_assets = {
            "male_01_run_cycle_v6.png",
            "male_01_run_cycle_v9.png",
            "male_01_run_cycle_v11.png",
        }
        run_cycle_expected = {
            f"{key}_run_cycle_v12.png" for key in KEYS
        }
        run_cycle_v16_expected = {
            f"{key}_run_cycle_v16.png" for key in KEYS
        }
        jump_cycle_expected = {"male_01_jump_cycle_v19.png"}
        action_sheet_expected = {"male_01_action_sheet_v21.png"}
        action_cycle_expected = {
            "male_01_battle_cycle_v22.png",
            "male_01_magic_cycle_v22.png",
            "male_01_interaction_cycle_v22.png",
        }
        custom_action_cycle_expected = {
            "male_01_sit_cycle_v1.png",
            "male_01_stand_cycle_v1.png",
            "male_01_crawl_cycle_v1.png",
            "male_01_climb_cycle_v1.png",
        }
        actual = {path.name for path in MOTION_SHEET_DIR.glob("*.png")}
        self.assertEqual(
            actual,
            expected
            | target_expected
            | legacy_run_cycle_assets
            | run_cycle_expected
            | run_cycle_v16_expected
            | jump_cycle_expected
            | action_sheet_expected
            | action_cycle_expected
            | custom_action_cycle_expected,
        )

        for filename in expected:
            path = MOTION_SHEET_DIR / filename
            with self.subTest(path=filename), Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertGreaterEqual(image.width, 1600)
                self.assertGreaterEqual(image.height, 800)
                for row in range(2):
                    top = round(row * image.height / 2)
                    bottom = round((row + 1) * image.height / 2)
                    for column in range(4):
                        left = round(column * image.width / 4)
                        right = round((column + 1) * image.width / 4)
                        alpha = image.getchannel("A").crop(
                            (left, top, right, bottom)
                        )
                        self.assertIsNotNone(alpha.getbbox())
                        self.assertGreater(
                            alpha.histogram()[0],
                            alpha.width * alpha.height // 3,
                        )

        for filename in target_expected:
            path = MOTION_SHEET_DIR / filename
            with self.subTest(path=filename), Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertGreaterEqual(image.width, 1400)
                self.assertGreaterEqual(image.height, 850)
                alpha = image.getchannel("A")
                self.assertEqual(
                    [
                        alpha.getpixel((0, 0)),
                        alpha.getpixel((image.width - 1, 0)),
                        alpha.getpixel((0, image.height - 1)),
                        alpha.getpixel((image.width - 1, image.height - 1)),
                    ],
                    [0, 0, 0, 0],
                )
                for row in range(2):
                    top = round(row * image.height / 2)
                    bottom = round((row + 1) * image.height / 2)
                    for column in range(4):
                        left = round(column * image.width / 4)
                        right = round((column + 1) * image.width / 4)
                        cell_alpha = alpha.crop((left, top, right, bottom))
                        self.assertIsNotNone(cell_alpha.getbbox())
                        self.assertGreater(
                            cell_alpha.histogram()[0],
                            cell_alpha.width * cell_alpha.height // 3,
                        )

        for filename in run_cycle_expected | run_cycle_v16_expected:
            path = MOTION_SHEET_DIR / filename
            with self.subTest(path=filename), Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (1536, 1024))
                for row in range(2):
                    top = round(row * image.height / 2)
                    bottom = round((row + 1) * image.height / 2)
                    for column in range(4):
                        left = round(column * image.width / 4)
                        right = round((column + 1) * image.width / 4)
                        alpha = image.getchannel("A").crop(
                            (left, top, right, bottom)
                        )
                        bounds = alpha.getbbox()
                        self.assertIsNotNone(bounds)
                        self.assertAlmostEqual(
                            (bounds[0] + bounds[2]) / 2,
                            alpha.width / 2,
                            delta=2,
                        )
                        self.assertAlmostEqual(bounds[3], 480, delta=2)
                        self.assertGreater(
                            alpha.histogram()[0],
                            alpha.width * alpha.height // 3,
                        )

        for filename in jump_cycle_expected:
            path = MOTION_SHEET_DIR / filename
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (1536, 1024))
                self.assertEqual(
                    [
                        image.getchannel("A").getpixel((0, 0)),
                        image.getchannel("A").getpixel((image.width - 1, 0)),
                        image.getchannel("A").getpixel((0, image.height - 1)),
                        image.getchannel("A").getpixel((image.width - 1, image.height - 1)),
                    ],
                    [0, 0, 0, 0],
                )

        for filename in action_sheet_expected | action_cycle_expected:
            path = MOTION_SHEET_DIR / filename
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (1536, 1024))
                alpha = image.getchannel("A")
                self.assertEqual(
                    [
                        alpha.getpixel((0, 0)),
                        alpha.getpixel((image.width - 1, 0)),
                        alpha.getpixel((0, image.height - 1)),
                        alpha.getpixel((image.width - 1, image.height - 1)),
                    ],
                    [0, 0, 0, 0],
                )
                for row in range(2):
                    for column in range(4):
                        cell = alpha.crop(
                            (
                                column * image.width // 4,
                                row * image.height // 2,
                                (column + 1) * image.width // 4,
                                (row + 1) * image.height // 2,
                            )
                        )
                        self.assertIsNotNone(cell.getbbox())

        for filename in custom_action_cycle_expected:
            path = MOTION_SHEET_DIR / filename
            with self.subTest(path=filename), Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size[0] % 4, 0)
                self.assertEqual(image.size[1] % 2, 0)
                alpha = image.getchannel("A")
                self.assertEqual(alpha.getextrema()[0], 0)
                for row in range(2):
                    for column in range(4):
                        cell = alpha.crop(
                            (
                                column * image.width // 4,
                                row * image.height // 2,
                                (column + 1) * image.width // 4,
                                (row + 1) * image.height // 2,
                            )
                        )
                        self.assertIsNotNone(cell.getbbox())

    def test_complete_asset_matrix_exists(self):
        expected = {f"{key}_{pose}.png" for key in KEYS for pose in POSES}
        actual = {
            path.name
            for path in ASSET_DIR.glob("*.png")
            if path.name.startswith(("male_", "female_"))
        }
        self.assertEqual(actual, expected | PREMIUM_REFERENCES)

    def test_premium_references_are_large_transparent_and_visible(self):
        for filename in PREMIUM_REFERENCES:
            path = ASSET_DIR / filename
            with self.subTest(path=filename), Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertGreaterEqual(image.width, 1024)
                self.assertGreaterEqual(image.height, 1024)
                alpha = image.getchannel("A")
                minimum, maximum = alpha.getextrema()
                self.assertEqual(minimum, 0)
                self.assertEqual(maximum, 255)
                self.assertIsNotNone(alpha.getbbox())
                self.assertGreater(
                    alpha.histogram()[0],
                    image.width * image.height // 3,
                )

    def test_premium_references_have_no_large_detached_body_parts(self):
        for filename in PREMIUM_REFERENCES:
            path = ASSET_DIR / filename
            with self.subTest(path=filename), Image.open(path) as image:
                alpha = image.getchannel("A")
                alpha.thumbnail((128, 192), Image.Resampling.LANCZOS)
                mask = [value >= 96 for value in alpha.getdata()]
                width, height = alpha.size
                visited = bytearray(len(mask))
                component_sizes = []

                for start, visible in enumerate(mask):
                    if not visible or visited[start]:
                        continue
                    visited[start] = 1
                    queue = deque([start])
                    size = 0
                    while queue:
                        index = queue.popleft()
                        size += 1
                        x = index % width
                        y = index // width
                        for neighbor in (
                            index - 1 if x else -1,
                            index + 1 if x + 1 < width else -1,
                            index - width if y else -1,
                            index + width if y + 1 < height else -1,
                        ):
                            if (
                                neighbor >= 0
                                and mask[neighbor]
                                and not visited[neighbor]
                            ):
                                visited[neighbor] = 1
                                queue.append(neighbor)
                    component_sizes.append(size)

                component_sizes.sort(reverse=True)
                self.assertTrue(component_sizes)
                detached_pixels = sum(component_sizes[1:])
                self.assertLess(
                    detached_pixels,
                    component_sizes[0] * 0.06,
                    f"{filename} contains a large detached visible component.",
                )

    def test_assets_are_rgba_transparent_and_visible(self):
        for key in KEYS:
            for pose in POSES:
                path = ASSET_DIR / f"{key}_{pose}.png"
                with self.subTest(path=path.name), Image.open(path) as image:
                    self.assertEqual(image.mode, "RGBA")
                    self.assertEqual(image.size, (512, 512))
                    alpha = image.getchannel("A")
                    minimum, maximum = alpha.getextrema()
                    self.assertEqual(minimum, 0)
                    self.assertEqual(maximum, 255)
                    visible_bounds = alpha.getbbox()
                    self.assertIsNotNone(visible_bounds)
                    self.assertGreater(visible_bounds[2] - visible_bounds[0], 180)
                    self.assertGreater(visible_bounds[3] - visible_bounds[1], 300)
                    transparent_pixels = alpha.histogram()[0]
                    self.assertGreater(transparent_pixels, image.width * image.height // 3)

    def test_generation_is_deterministic(self):
        source_hash = hashlib.sha256(
            (ASSET_DIR / "male_01_magic.png").read_bytes()
        ).hexdigest()
        with tempfile.TemporaryDirectory() as temporary_dir:
            generated = generator.generate_all(Path(temporary_dir))
            self.assertEqual(len(generated), 128)
            regenerated_hash = hashlib.sha256(
                (Path(temporary_dir) / "male_01_magic.png").read_bytes()
            ).hexdigest()
        self.assertEqual(source_hash, regenerated_hash)

    def test_same_character_keeps_identity_colors_across_poses(self):
        for style in generator.STYLES:
            expected_colors = {
                ImageColor.getrgb(style.skin),
                ImageColor.getrgb(style.hair),
                ImageColor.getrgb(style.outfit),
            }
            for pose in POSES:
                image = Image.open(ASSET_DIR / f"{style.key}_{pose}.png").convert("RGBA")
                opaque_colors = {
                    pixel[:3]
                    for pixel in image.getdata()
                    if pixel[3] == 255
                }
                with self.subTest(key=style.key, pose=pose):
                    self.assertTrue(expected_colors.issubset(opaque_colors))


if __name__ == "__main__":
    unittest.main()
