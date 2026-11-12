import tempfile
import unittest
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from story_video_assembly import assemble_scene_videos


class JourneyEncodingTests(unittest.TestCase):
    def test_encodes_existing_clips_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            clips = []
            for index, color in enumerate(((220, 30, 30), (30, 30, 220))):
                path = folder / f"clip{index}.mp4"
                with imageio.get_writer(str(path), fps=12, codec="libx264", macro_block_size=2,
                                        ffmpeg_log_level="error") as writer:
                    for _ in range(12):
                        frame = np.zeros((96, 160, 3), dtype=np.uint8)
                        frame[:] = color
                        writer.append_data(frame)
                clips.append(path.read_bytes())
            output = folder / "journey.mp4"
            output.write_bytes(assemble_scene_videos(clips))
            with imageio.get_reader(str(output)) as reader:
                first = reader.get_data(0).mean(axis=(0, 1))
                last = reader.get_data(23).mean(axis=(0, 1))
                self.assertGreater(first[0], first[2])
                self.assertGreater(last[2], last[0])
                self.assertAlmostEqual(reader.get_meta_data()["fps"], 12)


if __name__ == "__main__":
    unittest.main()
