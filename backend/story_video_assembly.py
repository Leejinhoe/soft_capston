"""Combine already generated scene clips without invoking a GPU provider."""
import math
import tempfile
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageOps

WIDTH, HEIGHT, FPS = 640, 360, 12
MAX_SCENES = 20
MAX_FRAMES_PER_SCENE = FPS * 5
FADE_FRAMES = 6


def _fit(frame):
    image = ImageOps.contain(Image.fromarray(frame).convert("RGB"), (WIDTH, HEIGHT))
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    canvas.paste(image, ((WIDTH - image.width) // 2, (HEIGHT - image.height) // 2))
    return np.asarray(canvas, dtype=np.uint8)


def assemble_scene_videos(clips):
    if not clips or len(clips) > MAX_SCENES:
        raise ValueError("A story must have between 1 and 20 scene videos")
    with tempfile.TemporaryDirectory(prefix="story_video_") as folder:
        output = Path(folder) / "story.mp4"
        previous = None
        with imageio.get_writer(str(output), fps=FPS, codec="libx264", macro_block_size=2,
                                ffmpeg_log_level="error", output_params=["-preset", "veryfast", "-pix_fmt", "yuv420p"]) as writer:
            for scene_index, clip in enumerate(clips):
                if not clip or len(clip) > 30_000_000:
                    raise ValueError("Invalid scene video size")
                path = Path(folder) / f"scene_{scene_index}.mp4"
                path.write_bytes(clip)
                with imageio.get_reader(str(path)) as reader:
                    source_fps = float(reader.get_meta_data().get("fps") or FPS)
                    if not math.isfinite(source_fps) or source_fps <= 0:
                        raise ValueError("Invalid scene video frame rate")
                    last_index = -1
                    last_frame = None
                    for index in range(MAX_FRAMES_PER_SCENE):
                        source_index = int(index * source_fps / FPS)
                        if source_index != last_index:
                            try:
                                last_frame = _fit(reader.get_data(source_index))
                            except IndexError:
                                break
                            last_index = source_index
                        frame = last_frame
                        if previous is not None and index < FADE_FRAMES:
                            alpha = (index + 1) / (FADE_FRAMES + 1)
                            frame = (previous.astype(np.float32) * (1 - alpha) + frame.astype(np.float32) * alpha).astype(np.uint8)
                        writer.append_data(frame)
                    if last_frame is None:
                        raise ValueError("Scene video contains no frames")
                    previous = last_frame.copy()
        return output.read_bytes()
