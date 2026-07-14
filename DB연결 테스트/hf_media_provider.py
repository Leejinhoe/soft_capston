import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

BACKEND_ENV_FILE = Path(__file__).resolve().parent / ".env"
PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

load_dotenv(PROJECT_ENV_FILE)
load_dotenv(BACKEND_ENV_FILE, override=True)

HF_TOKEN = (
    os.getenv("HF_TOKEN")
    or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    or os.getenv("HUGGINGFACE_API_TOKEN")
    or ""
).strip()
HF_IMAGE_MODEL = (
    os.getenv("HF_IMAGE_MODEL")
    or os.getenv("IMAGE_MODEL")
    or "black-forest-labs/FLUX.1-schnell"
).strip()
HF_IMAGE_API_BASE = (
    os.getenv("HF_IMAGE_API_BASE")
    or "https://router.huggingface.co/hf-inference/models"
).strip().rstrip("/")
HF_IMAGE_API_URL = (os.getenv("HF_IMAGE_API_URL") or "").strip()
HF_IMAGE_TIMEOUT_SECONDS = float(os.getenv("HF_IMAGE_TIMEOUT_SECONDS", "180"))
HF_VIDEO_MODEL = (
    os.getenv("HF_VIDEO_MODEL")
    or os.getenv("VIDEO_MODEL")
    or "Lightricks/LTX-Video-0.9.8-13B-distilled"
).strip()
HF_VIDEO_API_BASE = (
    os.getenv("HF_VIDEO_API_BASE")
    or "https://router.huggingface.co/hf-inference/models"
).strip().rstrip("/")
HF_VIDEO_API_URL = (os.getenv("HF_VIDEO_API_URL") or "").strip()
HF_VIDEO_TIMEOUT_SECONDS = float(os.getenv("HF_VIDEO_TIMEOUT_SECONDS", "600"))


class HfMediaError(RuntimeError):
    pass


def get_hf_media_config() -> Dict[str, Any]:
    return {
        "configured": bool(HF_TOKEN),
        "provider": "huggingface",
        "image_model": HF_IMAGE_MODEL,
        "image_api_base": HF_IMAGE_API_BASE,
        "image_api_url": HF_IMAGE_API_URL or None,
        "video_supported": bool(HF_TOKEN and HF_VIDEO_MODEL),
        "video_model": HF_VIDEO_MODEL,
        "video_api_base": HF_VIDEO_API_BASE,
        "video_api_url": HF_VIDEO_API_URL or None,
    }


def build_fairytale_image_prompt(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
) -> str:
    scene = " ".join(story_text.split())[:700]
    genre_text = f"{genre} fairytale" if genre else "fairytale"
    age_text = f"for {age} year old children" if age else "for children"
    return (
        "warm children's book illustration, soft cinematic lighting, "
        "gentle whimsical mood, clear main character, expressive face, "
        "storybook background, no text, no watermark, "
        f"{genre_text}, {age_text}, scene: {scene}"
    )


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


def _image_endpoint() -> str:
    if HF_IMAGE_API_URL:
        return HF_IMAGE_API_URL
    return f"{HF_IMAGE_API_BASE}/{quote(HF_IMAGE_MODEL, safe='/')}"


def _video_endpoint() -> str:
    if HF_VIDEO_API_URL:
        return HF_VIDEO_API_URL
    return f"{HF_VIDEO_API_BASE}/{quote(HF_VIDEO_MODEL, safe='/')}"


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:1000]
    if isinstance(data, dict):
        detail = data.get("error") or data.get("detail") or data.get("message")
        if detail:
            return str(detail)
    return str(data)[:1000]


async def generate_hf_fairytale_image(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    width: int = 512,
    height: int = 512,
    steps: int = 1,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    if not HF_TOKEN:
        raise HfMediaError("HF_TOKEN is missing. Add a Hugging Face token to .env.")
    if not story_text.strip():
        raise HfMediaError("story_text is empty.")

    prompt = build_fairytale_image_prompt(
        story_text=story_text,
        genre=genre,
        age=age,
    )
    parameters: Dict[str, Any] = {
        "width": int(width),
        "height": int(height),
        "num_inference_steps": int(steps),
        "guidance_scale": 0.0,
        "negative_prompt": "text, watermark, logo, blurry, distorted hands, scary, violent",
    }
    if seed is not None:
        parameters["seed"] = int(seed)

    payload = {
        "inputs": prompt,
        "parameters": parameters,
        "options": {"wait_for_model": True},
    }
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Accept": "image/png",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(
        connect=15.0,
        read=HF_IMAGE_TIMEOUT_SECONDS,
        write=30.0,
        pool=15.0,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(_image_endpoint(), headers=headers, json=payload)

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        raise HfMediaError(f"Hugging Face image generation failed: {_error_message(response)}")
    if "application/json" in content_type.lower():
        raise HfMediaError(f"Hugging Face returned JSON instead of image bytes: {_error_message(response)}")
    if not response.content:
        raise HfMediaError("Hugging Face returned an empty image response.")

    return {
        "image_bytes": response.content,
        "content_type": content_type.split(";")[0] or "image/png",
        "provider": "huggingface",
        "model": HF_IMAGE_MODEL,
        "prompt": prompt,
        "parameters": parameters,
    }


async def generate_hf_fairytale_video(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    width: int = 512,
    height: int = 384,
    num_frames: int = 17,
    steps: int = 4,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    if not HF_TOKEN:
        raise HfMediaError("HF_TOKEN is missing. Add a Hugging Face token to .env.")
    if not HF_VIDEO_MODEL:
        raise HfMediaError("HF_VIDEO_MODEL is missing.")
    if not story_text.strip():
        raise HfMediaError("story_text is empty.")

    prompt = build_fairytale_video_prompt(
        story_text=story_text,
        genre=genre,
        age=age,
    )
    parameters: Dict[str, Any] = {
        "width": int(width),
        "height": int(height),
        "num_frames": int(num_frames),
        "num_inference_steps": int(steps),
        "guidance_scale": 3.5,
        "negative_prompt": "text, watermark, logo, blurry, scary, violent, fast cuts",
    }
    if seed is not None:
        parameters["seed"] = int(seed)

    payload = {
        "inputs": prompt,
        "parameters": parameters,
        "options": {"wait_for_model": True},
    }
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Accept": "video/mp4,application/octet-stream",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(
        connect=20.0,
        read=HF_VIDEO_TIMEOUT_SECONDS,
        write=30.0,
        pool=20.0,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(_video_endpoint(), headers=headers, json=payload)

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        raise HfMediaError(f"Hugging Face video generation failed: {_error_message(response)}")
    if "application/json" in content_type.lower():
        raise HfMediaError(f"Hugging Face returned JSON instead of video bytes: {_error_message(response)}")
    if not response.content:
        raise HfMediaError("Hugging Face returned an empty video response.")

    normalized_content_type = content_type.split(";")[0].strip() or "video/mp4"
    if normalized_content_type == "application/octet-stream":
        normalized_content_type = "video/mp4"

    return {
        "video_bytes": response.content,
        "content_type": normalized_content_type,
        "provider": "huggingface",
        "model": HF_VIDEO_MODEL,
        "prompt": prompt,
        "parameters": parameters,
    }
