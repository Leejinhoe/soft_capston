"""Opt-in image-to-video client for a private Hugging Face Space."""
import asyncio
import inspect
import os
import re
import tempfile
from pathlib import Path

from hf_media_common import HfMediaError

MAX_IMAGE_BYTES = 10_000_000
MAX_VIDEO_BYTES = 30_000_000


def enabled():
    return os.getenv("HF_VIDEO_SPACE_ENABLED", "").strip().lower() == "true"


def _normalize_video_action_prompt(action: str) -> str:
    cleaned = (action or "").strip()[:500]
    if not cleaned or not re.search(r"[\uac00-\ud7a3]", cleaned):
        return cleaned
    if "무지갯빛 다리" in cleaned or any(k in cleaned for k in ("나아갔", "걸음을 옮", "걸었", "건너")):
        return (
            "Animated watercolor storybook illustration, the young fairytale character walks "
            "forward with clear stepping motion and swinging arms along a magical path, "
            "floating glowing particles, smooth camera pan."
        )
    if "보물 상자" in cleaned or "나침반" in cleaned or "지도가" in cleaned:
        return (
            "Animated watercolor storybook illustration, the young fairytale character leans "
            "forward excitedly and opens a glowing treasure chest, holding up a shining map "
            "with expressive hand and body movement."
        )
    if "별빛의 정원" in cleaned or "보물을 발견" in cleaned:
        return (
            "Animated watercolor storybook illustration, the young fairytale character smiles "
            "brightly, waves both hands happily and celebrates in a sparkling starlight garden."
        )
    if "수정 연못" in cleaned or "문자" in cleaned:
        return (
            "Animated watercolor storybook illustration, the young fairytale character gestures "
            "gently while examining glowing ancient runes beside a shimmering crystal pond with "
            "rippling water reflections."
        )
    return (
        "Animated watercolor storybook illustration, the young fairytale character moves "
        "naturally with expressive body and hand gestures in a magical fairytale scene."
    )


def _generate(image_bytes, action, seed):
    from gradio_client import Client, handle_file

    space = os.getenv("HF_VIDEO_SPACE_ID", "").strip()
    token = os.getenv("HF_TOKEN", "").strip()
    if not space or not token:
        raise HfMediaError("Video Space and token must be configured")
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise HfMediaError("Invalid scene image size")
    action = _normalize_video_action_prompt(action)
    if not action:
        raise HfMediaError("Video action is required")
    with tempfile.TemporaryDirectory(prefix="fairytale_video_space_") as folder:
        image_path = Path(folder) / "scene.png"
        image_path.write_bytes(image_bytes)
        token_name = "token" if "token" in inspect.signature(Client).parameters else "hf_token"
        client = Client(space, **{token_name: token}, verbose=False, download_files=folder)
        job = client.submit(handle_file(str(image_path)), action, int(42 if seed is None else seed), api_name="/generate")
        try:
            result = job.result(timeout=180)
        except TimeoutError:
            job.cancel()
            raise HfMediaError("Video Space timed out") from None
        if isinstance(result, dict):
            result = result.get("video")
        if not isinstance(result, str):
            raise HfMediaError("Video Space returned an invalid result")
        path = Path(result).resolve()
        if not path.is_relative_to(Path(folder).resolve()) or not path.is_file():
            raise HfMediaError("Video Space returned an unexpected output path")
        if path.stat().st_size > MAX_VIDEO_BYTES:
            raise HfMediaError("Video Space output is too large")
        data = path.read_bytes()
        if len(data) < 12 or data[4:8] != b"ftyp":
            raise HfMediaError("Video Space output is not an MP4 file")
        return data


async def generate_scene_video(image_bytes, action, seed=None):
    data = await asyncio.to_thread(_generate, image_bytes, action, seed)
    return {
        "video_bytes": data,
        "content_type": "video/mp4",
        "provider": "huggingface-space-i2v",
        "model": "Lightricks/LTX-Video",
        "prompt": _normalize_video_action_prompt(action),
        "parameters": {"width": 384, "height": 384, "num_frames": 25,
                       "frame_rate": 12, "duration_seconds": 25 / 12,
                       "identity_verification": "not_verified"},
    }
