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
    movements = (
        (("달리", "달려", "뛰어가", "뛰어갔"), "runs forward with clear alternating steps"),
        (("열었", "열어", "연다", "열고", "열며"), "gently opens the object in front of them"),
        (("건너", "건넌", "걸었", "걸어", "걸음을 옮", "나아갔", "나아가"), "walks forward with clear alternating steps"),
        (("손을 흔", "손 흔", "인사"), "waves one hand gently"),
        (("살펴", "들여다", "바라보", "관찰"), "looks around slowly"),
        (("앉았", "앉아", "앉는", "앉는다"), "slowly sits down"),
    )
    movement = next((description for words, description in movements
                     if any(word in cleaned for word in words)),
                    "makes a small natural movement")
    return (
        "Animate the supplied storybook illustration. The same character " + movement +
        ". Preserve the character's face, clothes, body proportions, and the existing "
        "background. Stable camera, coherent anatomy, smooth continuous movement."
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
