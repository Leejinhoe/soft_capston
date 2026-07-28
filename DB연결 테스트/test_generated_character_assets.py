import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageColor


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "tools" / "generate_character_assets.py"
ASSET_DIR = ROOT / "assets" / "characters"
POSES = ("default", "happy", "sad", "angry", "walking", "talking", "magic", "rescue")
KEYS = tuple(
    [f"male_{index:02d}" for index in range(1, 9)]
    + [f"female_{index:02d}" for index in range(1, 9)]
)

spec = importlib.util.spec_from_file_location("generate_character_assets", GENERATOR_PATH)
generator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


class GeneratedCharacterAssetTests(unittest.TestCase):
    def test_complete_asset_matrix_exists(self):
        expected = {f"{key}_{pose}.png" for key in KEYS for pose in POSES}
        actual = {
            path.name
            for path in ASSET_DIR.glob("*.png")
            if path.name.startswith(("male_", "female_"))
        }
        self.assertEqual(actual, expected)

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
