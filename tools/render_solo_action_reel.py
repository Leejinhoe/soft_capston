"""Build a labeled solo-action reel from the generated preview clips."""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "output" / "action_previews"
SOLO_CLIPS = (
    ("RUN", "male_01_run_v25.mp4"),
    ("JUMP", "male_01_jump_v25.mp4"),
    ("LOOK AROUND", "male_01_investigate_v25.mp4"),
    ("CAST MAGIC", "male_01_magic_v25.mp4"),
    ("WAVE", "male_01_wave_v25.mp4"),
)
OUTPUT = VIDEO_DIR / "male_01_solo_action_reel_v25.mp4"
FPS = 12
FRAMES_PER_CLIP = FPS * 3


def _labeled_frame(frame, label: str):
    image = Image.fromarray(frame).convert("RGB")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, image.width, 30), fill=(20, 28, 42, 210))
    draw.text((12, 8), f"SOLO ACTION  |  {label}", fill=(255, 255, 255, 255))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def main() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(OUTPUT),
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=2,
        ffmpeg_log_level="error",
        output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for label, filename in SOLO_CLIPS:
            path = VIDEO_DIR / filename
            if not path.is_file():
                raise FileNotFoundError(f"Missing preview clip: {path}")
            reader = imageio.get_reader(str(path))
            try:
                for frame_index, frame in enumerate(reader):
                    if frame_index >= FRAMES_PER_CLIP:
                        break
                    labeled = _labeled_frame(frame, label)
                    writer.append_data(np.asarray(labeled, dtype=np.uint8))
            finally:
                reader.close()
    finally:
        writer.close()
    print(OUTPUT.resolve())
    return OUTPUT


if __name__ == "__main__":
    main()
