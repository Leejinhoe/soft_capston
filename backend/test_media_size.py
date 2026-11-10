import io
import tempfile
import unittest
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image

from media_size import fit_image, fit_video


class MediaSizeTests(unittest.TestCase):
    def test_small_originals_are_unchanged(self):
        self.assertEqual(fit_image(b"original"), b"original")
        self.assertEqual(fit_video(b"original"), b"original")

    def test_image_remains_png_and_preserves_alpha(self):
        output = io.BytesIO()
        Image.new("RGBA", (1200, 800), (100, 50, 30, 128)).save(output, "PNG", compress_level=0)
        reduced = fit_image(output.getvalue(), limit=100_000)
        self.assertLessEqual(len(reduced), 100_000)
        with Image.open(io.BytesIO(reduced)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.getpixel((0, 0))[3], 128)

    def test_video_reencoding_preserves_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.mp4"
            with imageio.get_writer(str(path), fps=12, codec="libx264", quality=10) as writer:
                for i in range(24):
                    frame = np.full((96, 160, 3), 90, dtype=np.uint8)
                    frame[:, i:i + 10] = 240
                    writer.append_data(frame)
            # Padding simulates an oversized container without changing frames.
            data = path.read_bytes() + b"\0" * 100_000
            reduced = fit_video(data, limit=50_000)
            self.assertLessEqual(len(reduced), 50_000)
            path.write_bytes(reduced)
            with imageio.get_reader(str(path)) as reader:
                self.assertEqual(reader.count_frames(), 24)
                self.assertAlmostEqual(reader.get_meta_data()["duration"], 2.0, places=1)


if __name__ == "__main__":
    unittest.main()
