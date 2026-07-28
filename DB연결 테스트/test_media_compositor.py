import unittest
from io import BytesIO

from PIL import Image, ImageDraw

from media_compositor import compose_story_scene


def _png_bytes(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class MediaCompositorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
