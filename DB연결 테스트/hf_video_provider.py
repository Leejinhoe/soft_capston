import asyncio
import io
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from hf_media_common import HfMediaError
from media_compositor import build_character_shadow, prepare_story_scene_layers

LOCAL_VIDEO_PROVIDER = (os.getenv("VIDEO_PROVIDER") or "local-animation").strip()
LOCAL_VIDEO_MODEL = (
    os.getenv("LOCAL_VIDEO_MODEL")
    or os.getenv("VIDEO_MODEL")
    or "storybook-layered-motion-v2"
).strip()
LOCAL_VIDEO_FRAME_RATE = int(os.getenv("LOCAL_VIDEO_FRAME_RATE", "12"))
LOCAL_VIDEO_DURATION_SECONDS = float(os.getenv("LOCAL_VIDEO_DURATION_SECONDS", "4.0"))


def get_hf_video_config() -> Dict[str, Any]:
    return {
        "configured": True,
        "video_supported": True,
        "video_provider": LOCAL_VIDEO_PROVIDER,
        "video_model": LOCAL_VIDEO_MODEL,
        "video_task": "layered-character-animation",
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


def select_motion_preset(story_text: str) -> str:
    normalized = " ".join(story_text.lower().split())
    keyword_groups = (
        ("run", ("run", "running", "race", "sprint", "달리", "뛰어가", "도망")),
        ("jump", ("jump", "leap", "hop", "점프", "뛰어오", "껑충")),
        ("fly", ("fly", "flies", "flying", "float", "soar", "날아", "비행", "떠오")),
        ("walk", ("walk", "walking", "stroll", "걷", "산책", "다가가")),
        ("wave", ("wave", "waving", "greet", "인사", "손을 흔", "손 흔")),
        ("talk", ("talk", "speak", "whisper", "sing", "말하", "이야기", "노래")),
    )
    for preset, keywords in keyword_groups:
        if any(keyword in normalized for keyword in keywords):
            return preset
    return "idle"


def _character_motion(
    *,
    preset: str,
    progress: float,
    width: int,
    height: int,
    motion_strength: int,
) -> Dict[str, float]:
    strength = min(max(int(motion_strength), 1), 8) / 8.0
    phase = math.tau * progress
    sway = math.sin(phase)
    pulse = math.sin(phase * 2.0)
    values = {
        "x": sway * width * 0.006 * strength,
        "y": -abs(pulse) * height * 0.003 * strength,
        "angle": sway * 0.8 * strength,
        "scale_x": 1.0 + pulse * 0.004 * strength,
        "scale_y": 1.0 + pulse * 0.01 * strength,
        "shadow_scale": 1.0,
        "shadow_opacity": 92.0,
    }
    if preset == "walk":
        values.update(
            x=sway * width * 0.018 * strength,
            y=-abs(pulse) * height * 0.012 * strength,
            angle=sway * 1.8 * strength,
        )
    elif preset == "run":
        values.update(
            x=sway * width * 0.03 * strength,
            y=-abs(pulse) * height * 0.025 * strength,
            angle=sway * 3.2 * strength,
            scale_x=1.0 + pulse * 0.012 * strength,
        )
    elif preset == "jump":
        lift = abs(math.sin(math.pi * progress)) * height * 0.14 * strength
        values.update(
            x=sway * width * 0.014 * strength,
            y=-lift,
            angle=sway * 2.0 * strength,
            scale_y=1.0 + math.sin(math.pi * progress) * 0.025 * strength,
            shadow_scale=max(0.5, 1.0 - lift / max(height * 0.25, 1)),
            shadow_opacity=max(35.0, 92.0 - lift * 0.45),
        )
    elif preset == "fly":
        lift = (0.45 + 0.35 * math.sin(phase)) * height * 0.11 * strength
        values.update(
            x=sway * width * 0.025 * strength,
            y=-lift,
            angle=sway * 2.6 * strength,
            shadow_scale=0.55,
            shadow_opacity=42.0,
        )
    elif preset == "wave":
        values.update(
            x=sway * width * 0.009 * strength,
            y=-abs(pulse) * height * 0.006 * strength,
            angle=sway * 2.4 * strength,
            scale_x=1.0 + pulse * 0.009 * strength,
        )
    elif preset == "talk":
        values.update(
            y=-abs(pulse) * height * 0.005 * strength,
            angle=sway * 1.2 * strength,
            scale_y=1.0 + pulse * 0.014 * strength,
        )
    return values


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


def _render_layered_frame(
    *,
    background,
    character,
    position: Tuple[int, int],
    Image,
    ImageEnhance,
    ImageOps,
    width: int,
    height: int,
    progress: float,
    motion_strength: int,
    motion_preset: str,
):
    camera_frame = _render_frame(
        source_image=background.convert("RGB"),
        Image=Image,
        ImageEnhance=ImageEnhance,
        ImageOps=ImageOps,
        width=width,
        height=height,
        progress=progress,
        motion_strength=max(1, motion_strength // 2),
    ).convert("RGBA")
    motion = _character_motion(
        preset=motion_preset,
        progress=progress,
        width=width,
        height=height,
        motion_strength=motion_strength,
    )
    scaled_width = max(1, round(character.width * motion["scale_x"]))
    scaled_height = max(1, round(character.height * motion["scale_y"]))
    animated = character.resize(
        (scaled_width, scaled_height),
        getattr(Image, "Resampling", Image).LANCZOS,
    )
    animated = animated.rotate(
        motion["angle"],
        resample=getattr(Image, "Resampling", Image).BICUBIC,
        expand=True,
    )

    base_x, base_y = position
    base_center_x = base_x + character.width // 2
    base_feet_y = base_y + character.height
    character_x = round(base_center_x - animated.width / 2 + motion["x"])
    character_y = round(base_feet_y - animated.height + motion["y"])
    shadow_y = base_feet_y - animated.height
    shadow = build_character_shadow(
        camera_frame.size,
        animated.size,
        (character_x, shadow_y),
        opacity=round(motion["shadow_opacity"]),
        scale=motion["shadow_scale"],
    )
    camera_frame.alpha_composite(shadow)
    camera_frame.alpha_composite(animated, (character_x, character_y))
    return camera_frame.convert("RGB")


def _generate_local_video_bytes(
    *,
    image_bytes: bytes,
    width: int,
    height: int,
    num_frames: int,
    frame_rate: int,
    motion_strength: int,
    story_text: str,
    background_bytes: Optional[bytes] = None,
    character_layer_bytes: Optional[bytes] = None,
) -> Tuple[bytes, str]:
    imageio, np, Image, ImageEnhance, ImageOps = _load_video_dependencies()
    width = _even_dimension(width)
    height = _even_dimension(height)
    frame_rate = min(max(int(frame_rate), 6), 30)
    total_frames = _normalize_frame_count(num_frames, frame_rate)

    layered_scene = None
    if background_bytes and character_layer_bytes:
        try:
            layered_scene = prepare_story_scene_layers(
                background_bytes,
                character_layer_bytes,
                width=width,
                height=height,
            )
        except Exception:
            layered_scene = None

    if layered_scene is None:
        try:
            source_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise HfMediaError(
                "Generated image bytes could not be opened for video rendering."
            ) from exc
    motion_preset = select_motion_preset(story_text)

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
                if layered_scene is not None:
                    background, character, position = layered_scene
                    frame = _render_layered_frame(
                        background=background,
                        character=character,
                        position=position,
                        Image=Image,
                        ImageEnhance=ImageEnhance,
                        ImageOps=ImageOps,
                        width=width,
                        height=height,
                        progress=progress,
                        motion_strength=motion_strength,
                        motion_preset=motion_preset,
                    )
                else:
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
        animation_mode = "layered_character_motion" if layered_scene is not None else "ken_burns"
        return video_bytes, animation_mode


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
    background_bytes: Optional[bytes] = None,
    character_layer_bytes: Optional[bytes] = None,
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

    video_bytes, animation_mode = await asyncio.to_thread(
        _generate_local_video_bytes,
        image_bytes=image_bytes,
        width=width,
        height=height,
        num_frames=normalized_frames,
        frame_rate=normalized_frame_rate,
        motion_strength=steps,
        story_text=story_text,
        background_bytes=background_bytes,
        character_layer_bytes=character_layer_bytes,
    )
    motion_preset = select_motion_preset(story_text)

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
            "motion_preset": motion_preset,
            "animation_mode": animation_mode,
            "character_motion": animation_mode == "layered_character_motion",
            "seed": seed,
        },
    }
