import unittest
from io import BytesIO

from PIL import Image, ImageDraw

from media_compositor import compose_background_scene, compose_story_scene


def _png_bytes(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class MediaCompositorTests(unittest.TestCase):
    def test_composes_environment_scene_without_character(self):
        background = Image.new("RGB", (900, 450), "#77aadd")
        background_bytes = BytesIO()
        background.save(background_bytes, format="PNG")

        result = compose_background_scene(
            background_bytes.getvalue(),
            width=512,
            height=384,
        )

        with Image.open(BytesIO(result)) as rendered:
            self.assertEqual(rendered.size, (512, 384))
            self.assertEqual(rendered.mode, "RGB")

    def test_composes_character_on_background(self):
        background = Image.new("RGB", (800, 600), "#81b7d8")
        character = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((50, 30, 150, 390), fill="#e84c4c")

        result = compose_story_scene(
            _png_bytes(background),
            _png_bytes(character),
            width=512,
            height=384,
        )

        with Image.open(BytesIO(result)) as composed:
            self.assertEqual(composed.size, (512, 384))
            self.assertEqual(composed.format, "PNG")
            center = composed.convert("RGB").getpixel((256, 250))
            self.assertGreater(center[0], center[2])

    def test_rejects_invisible_character(self):
        background = Image.new("RGB", (512, 512), "white")
        character = Image.new("RGBA", (100, 100), (0, 0, 0, 0))

        with self.assertRaises(ValueError):
                compose_story_scene(
                    _png_bytes(background),
                    _png_bytes(character),
                )

    def test_composes_two_interacting_characters(self):
        background = Image.new("RGB", (800, 600), "#81b7d8")
        primary = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        secondary = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        ImageDraw.Draw(primary).rectangle((50, 30, 150, 390), fill="#e84c4c")
        ImageDraw.Draw(secondary).rectangle((50, 30, 150, 390), fill="#4477dd")

        result = compose_story_scene(
            _png_bytes(background),
            _png_bytes(primary),
            secondary_character_bytes=_png_bytes(secondary),
            width=512,
            height=384,
        )

        with Image.open(BytesIO(result)) as composed:
            colors = set(composed.convert("RGB").getdata())
            self.assertIn((232, 76, 76), colors)
            self.assertIn((68, 119, 221), colors)

    def test_applies_sunset_treatment_and_draws_learned_basket_prop(self):
        background = Image.new("RGB", (800, 600), "#81b7d8")
        character = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        ImageDraw.Draw(character).rectangle((50, 30, 150, 390), fill="#e84c4c")

        result = compose_story_scene(
            _png_bytes(background),
            _png_bytes(character),
            effect_tags=["sunset_glow"],
            prop_tags=["woven_basket"],
            width=512,
            height=384,
        )

        with Image.open(BytesIO(result)) as composed:
            rgb = composed.convert("RGB")
            top_pixel = rgb.getpixel((20, 20))
            basket_area = rgb.crop((300, 225, 410, 340))
            brown_pixels = sum(
                red > blue * 1.5 and red > green * 1.15
                for red, green, blue in basket_area.getdata()
            )

            self.assertGreater(top_pixel[0], 129)
            self.assertGreater(brown_pixels, 300)


if __name__ == "__main__":
    unittest.main()
