import asyncio
import os
from typing import Any, Dict, Optional

from huggingface_hub import InferenceClient

from hf_media_common import HF_TOKEN, HfMediaError

HF_VIDEO_PROVIDER = (os.getenv("HF_VIDEO_PROVIDER") or "fal-ai").strip()
HF_VIDEO_MODEL = (
    os.getenv("HF_VIDEO_MODEL")
    or os.getenv("VIDEO_MODEL")
    or "Lightricks/LTX-Video-0.9.8-13B-distilled"
).strip()
HF_VIDEO_TIMEOUT_SECONDS = float(os.getenv("HF_VIDEO_TIMEOUT_SECONDS", "600"))


def get_hf_video_config() -> Dict[str, Any]:
    return {
        "configured": bool(HF_TOKEN and HF_VIDEO_MODEL),
        "video_supported": bool(HF_TOKEN and HF_VIDEO_MODEL),
        "video_provider": HF_VIDEO_PROVIDER,
        "video_model": HF_VIDEO_MODEL,
        "video_task": "image-to-video",
        "video_timeout_seconds": HF_VIDEO_TIMEOUT_SECONDS,
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
        "short gentle storybook animation, warm magical lighting, "
        "slow camera movement, clear main character, consistent character design, "
        "soft cinematic motion, no text, no watermark, "
        f"{genre_text}, {age_text}, scene: {scene}"
    )


def _video_error_message(exc: Exception) -> str:
    message = str(exc)
    if "402" in message or "Payment Required" in message or "depleted your monthly included credits" in message:
        return (
            "Hugging Face video generation requires available Inference Provider credits. "
            f"Original error: {message[:900]}"
        )
    return message[:1000]


async def generate_hf_fairytale_video(
    *,
    image_bytes: bytes,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    width: int = 512,
    height: int = 384,
    num_frames: int = 9,
    steps: int = 2,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    if not HF_TOKEN:
        raise HfMediaError("HF_TOKEN is missing. Add a Hugging Face token to .env.")
    if not HF_VIDEO_MODEL:
        raise HfMediaError("HF_VIDEO_MODEL is missing.")
    if not image_bytes:
        raise HfMediaError("image_bytes is empty.")

    prompt = build_fairytale_video_prompt(
        story_text=story_text,
        genre=genre,
        age=age,
    )
    normalized_steps = max(2, int(steps))
    normalized_frames = max(9, int(num_frames))
    target_size = {"width": int(width), "height": int(height)}

    def _run_generation() -> bytes:
        client = InferenceClient(provider=HF_VIDEO_PROVIDER, api_key=HF_TOKEN)
        return client.image_to_video(
            image_bytes,
            model=HF_VIDEO_MODEL,
            prompt=prompt,
            negative_prompt="text, watermark, logo, blurry, scary, violent, fast cuts",
            num_frames=normalized_frames,
            num_inference_steps=normalized_steps,
            guidance_scale=1.0,
            seed=seed,
            target_size=target_size,
        )

    try:
        video_bytes = await asyncio.wait_for(
            asyncio.to_thread(_run_generation),
            timeout=HF_VIDEO_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise HfMediaError(_video_error_message(exc)) from exc

    if not video_bytes:
        raise HfMediaError("Hugging Face returned an empty video response.")

    return {
        "video_bytes": video_bytes,
        "content_type": "video/mp4",
        "provider": f"huggingface:{HF_VIDEO_PROVIDER}",
        "model": HF_VIDEO_MODEL,
        "prompt": prompt,
        "parameters": {
            "width": int(width),
            "height": int(height),
            "num_frames": normalized_frames,
            "num_inference_steps": normalized_steps,
            "guidance_scale": 1.0,
            "target_size": target_size,
        },
    }
