import asyncio
import io
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from hf_media_common import HfMediaError

LOCAL_VIDEO_PROVIDER = (os.getenv("VIDEO_PROVIDER") or "local-animation").strip()
LOCAL_VIDEO_MODEL = (
    os.getenv("LOCAL_VIDEO_MODEL")
    or os.getenv("VIDEO_MODEL")
    or "storybook-ken-burns-v1"
).strip()
LOCAL_VIDEO_FRAME_RATE = int(os.getenv("LOCAL_VIDEO_FRAME_RATE", "12"))
LOCAL_VIDEO_DURATION_SECONDS = float(os.getenv("LOCAL_VIDEO_DURATION_SECONDS", "4.0"))


def get_hf_video_config() -> Dict[str, Any]:
    return {
        "configured": True,
        "video_supported": True,
        "video_provider": LOCAL_VIDEO_PROVIDER,
        "video_model": LOCAL_VIDEO_MODEL,
        "video_task": "image-to-video-local-animation",
        "video_requires_gpu": False,
        "video_requires_external_api": False,
        "video_default_frame_rate": LOCAL_VIDEO_FRAME_RATE,
        "video_default_duration_seconds": LOCAL_VIDEO_DURATION_SECONDS,
    }


def build_fairytale_video_prompt(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
) -> str:
    scene = " ".join(story_text.split())[:500]
    genre_text = f"{genre} fairytale" if genre else "fairytale"
    age_text = f"for {age} year old children" if age else "for children"
    return (
        "storybook still image animation, gentle camera movement, "
        "warm magical mood, no generated text, "
        f"{genre_text}, {age_text}, scene: {scene}"
    )


def _load_video_dependencies():
    try:
        import imageio.v2 as imageio
        import numpy as np
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:
        raise HfMediaError(
            "Local video generation needs pillow, numpy, imageio, and imageio-ffmpeg. "
            "Run `pip install -r requirements.txt` in the backend folder."
        ) from exc
    return imageio, np, Image, ImageEnhance, ImageOps


def _even_dimension(value: int, minimum: int = 256) -> int:
    normalized = max(minimum, int(value))
    return normalized if normalized % 2 == 0 else normalized - 1


def _normalize_frame_count(num_frames: int, frame_rate: int) -> int:
    requested = max(1, int(num_frames))
    default_frames = max(1, int(round(LOCAL_VIDEO_DURATION_SECONDS * frame_rate)))
    return max(requested, default_frames)


def _ease_in_out(progress: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * progress)


def _render_frame(
    *,
    source_image,
    Image,
    ImageEnhance,
    ImageOps,
    width: int,
    height: int,
    progress: float,
    motion_strength: int,
):
    eased = _ease_in_out(progress)
    zoom_start = 1.04
    zoom_end = 1.08 + min(max(motion_strength, 1), 8) * 0.01
    zoom = zoom_start + (zoom_end - zoom_start) * eased
    scaled_width = int(math.ceil(width * zoom))
    scaled_height = int(math.ceil(height * zoom))

    fitted = ImageOps.fit(
        source_image,
        (scaled_width, scaled_height),
        method=getattr(Image, "Resampling", Image).LANCZOS,
        centering=(0.5, 0.5),
    )
    max_x = max(0, scaled_width - width)
    max_y = max(0, scaled_height - height)
    x_offset = int(max_x * eased)
    y_offset = int(max_y * (1.0 - eased) * 0.5)
    frame = fitted.crop((x_offset, y_offset, x_offset + width, y_offset + height))

    fade = min(1.0, progress * 6.0, (1.0 - progress) * 6.0)
    brightness = 0.94 + 0.06 * fade
    contrast = 1.02
    frame = ImageEnhance.Brightness(frame).enhance(brightness)
    frame = ImageEnhance.Contrast(frame).enhance(contrast)
    return frame


def _generate_local_video_bytes(
    *,
    image_bytes: bytes,
    width: int,
    height: int,
    num_frames: int,
    frame_rate: int,
    motion_strength: int,
) -> bytes:
    imageio, np, Image, ImageEnhance, ImageOps = _load_video_dependencies()
    width = _even_dimension(width)
    height = _even_dimension(height)
    frame_rate = min(max(int(frame_rate), 6), 30)
    total_frames = _normalize_frame_count(num_frames, frame_rate)

    try:
        source_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise HfMediaError("Generated image bytes could not be opened for video rendering.") from exc

    with tempfile.TemporaryDirectory(prefix="fairytale_video_") as temp_dir:
        output_path = Path(temp_dir) / "scene.mp4"
        writer = imageio.get_writer(
            str(output_path),
            fps=frame_rate,
            codec="libx264",
            quality=8,
            macro_block_size=16,
            ffmpeg_log_level="error",
            output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        )
        try:
            for index in range(total_frames):
                progress = index / max(total_frames - 1, 1)
                frame = _render_frame(
                    source_image=source_image,
                    Image=Image,
                    ImageEnhance=ImageEnhance,
                    ImageOps=ImageOps,
                    width=width,
                    height=height,
                    progress=progress,
                    motion_strength=motion_strength,
                )
                writer.append_data(np.asarray(frame, dtype=np.uint8))
        finally:
            writer.close()

        video_bytes = output_path.read_bytes()
        if not video_bytes:
            raise HfMediaError("Local video renderer returned an empty MP4 file.")
        return video_bytes


async def generate_hf_fairytale_video(
    *,
    image_bytes: bytes,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    width: int = 512,
    height: int = 384,
    num_frames: int = 48,
    steps: int = 2,
    seed: Optional[int] = None,
    frame_rate: Optional[int] = None,
) -> Dict[str, Any]:
    if not image_bytes:
        raise HfMediaError("image_bytes is empty.")

    prompt = build_fairytale_video_prompt(
        story_text=story_text,
        genre=genre,
        age=age,
    )
    normalized_frame_rate = frame_rate or LOCAL_VIDEO_FRAME_RATE
    normalized_frames = _normalize_frame_count(num_frames, normalized_frame_rate)

    video_bytes = await asyncio.to_thread(
        _generate_local_video_bytes,
        image_bytes=image_bytes,
        width=width,
        height=height,
        num_frames=normalized_frames,
        frame_rate=normalized_frame_rate,
        motion_strength=steps,
    )

    return {
        "video_bytes": video_bytes,
        "content_type": "video/mp4",
        "provider": LOCAL_VIDEO_PROVIDER,
        "model": LOCAL_VIDEO_MODEL,
        "prompt": prompt,
        "parameters": {
            "width": _even_dimension(width),
            "height": _even_dimension(height),
            "num_frames": normalized_frames,
            "frame_rate": min(max(int(normalized_frame_rate), 6), 30),
            "motion_strength": int(steps),
            "seed": seed,
        },
    }
