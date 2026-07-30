import asyncio
import io
import os
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx
from huggingface_hub import AsyncInferenceClient

from hf_media_common import HF_TOKEN, HfMediaError

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
HF_IMAGE_PROVIDERS: Tuple[str, ...] = tuple(
    provider.strip()
    for provider in (
        os.getenv("HF_IMAGE_PROVIDERS")
        or os.getenv("HF_IMAGE_PROVIDER")
        or "fal-ai,nscale,replicate"
    ).split(",")
    if provider.strip()
)
HF_IMAGE_TIMEOUT_SECONDS = float(os.getenv("HF_IMAGE_TIMEOUT_SECONDS", "180"))
HF_IMAGE_RETRY_DELAY_SECONDS = float(os.getenv("HF_IMAGE_RETRY_DELAY_SECONDS", "1.5"))
TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def get_hf_image_config() -> Dict[str, Any]:
    return {
        "configured": bool(HF_TOKEN),
        "image_model": HF_IMAGE_MODEL,
        "image_api_base": HF_IMAGE_API_BASE,
        "image_api_url": HF_IMAGE_API_URL or None,
        "image_provider": HF_IMAGE_PROVIDERS[0] if HF_IMAGE_PROVIDERS else None,
        "image_providers": list(HF_IMAGE_PROVIDERS),
        "image_retry_delay_seconds": HF_IMAGE_RETRY_DELAY_SECONDS,
    }


def build_fairytale_image_prompt(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    character_description: Optional[str] = None,
    character_style_prompt: Optional[str] = None,
    character_action_hint: Optional[str] = None,
) -> str:
    scene = " ".join(story_text.split())[:700]
    genre_text = f"{genre} fairytale" if genre else "fairytale"
    age_text = f"for {age} year old children" if age else "for children"
    character_text = ""
    if character_description:
        character_text = f", recurring main character: {' '.join(character_description.split())[:500]}"
    style_text = ""
    if character_style_prompt:
        style_text = f", fixed visual style: {' '.join(character_style_prompt.split())[:300]}"
    action_text = ""
    if character_action_hint:
        action_text = f", character action: {' '.join(character_action_hint.split())[:160]}"
    return (
        "warm children's book illustration, soft cinematic lighting, "
        "gentle whimsical mood, clear main character, expressive face, "
        "storybook background, no text, no watermark, "
        f"{genre_text}, {age_text}{character_text}{style_text}{action_text}, scene: {scene}"
    )


def _image_endpoint() -> str:
    if HF_IMAGE_API_URL:
        return HF_IMAGE_API_URL
    return f"{HF_IMAGE_API_BASE}/{quote(HF_IMAGE_MODEL, safe='/')}"


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


def _provider_error_status(exc: Exception) -> Optional[int]:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _provider_error_summary(provider: str, exc: Exception) -> str:
    status = _provider_error_status(exc)
    if status is not None:
        return f"{provider}: HTTP {status}"
    label = exc.__class__.__name__
    detail = " ".join(str(exc).split())[:240]
    return f"{provider}: {label}{f' ({detail})' if detail else ''}"


def _is_retryable_provider_error(exc: Exception) -> bool:
    status = _provider_error_status(exc)
    if status is not None:
        return status in TRANSIENT_STATUS_CODES
    return isinstance(exc, (TimeoutError, httpx.TimeoutException, httpx.TransportError))


async def generate_hf_fairytale_image(
    *,
    story_text: str,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    character_description: Optional[str] = None,
    character_style_prompt: Optional[str] = None,
    character_action_hint: Optional[str] = None,
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
        character_description=character_description,
        character_style_prompt=character_style_prompt,
        character_action_hint=character_action_hint,
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

    if HF_IMAGE_API_URL:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(_image_endpoint(), headers=headers, json=payload)

        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400:
            raise HfMediaError(f"Hugging Face image generation failed: {_error_message(response)}")
        if "application/json" in content_type.lower():
            raise HfMediaError(f"Hugging Face returned JSON instead of image bytes: {_error_message(response)}")
        if not response.content:
            raise HfMediaError("Hugging Face returned an empty image response.")
        image_bytes = response.content
        selected_provider = "custom-endpoint"
        attempted_providers = [selected_provider]
    else:
        if not HF_IMAGE_PROVIDERS:
            raise HfMediaError("No Hugging Face image providers are configured.")

        errors = []
        attempted_providers = []
        for index, provider in enumerate(HF_IMAGE_PROVIDERS):
            attempted_providers.append(provider)
            try:
                async with AsyncInferenceClient(
                    provider=provider,
                    token=HF_TOKEN,
                    timeout=HF_IMAGE_TIMEOUT_SECONDS,
                ) as client:
                    image = await client.text_to_image(
                        prompt,
                        model=HF_IMAGE_MODEL,
                        negative_prompt=parameters["negative_prompt"],
                        width=parameters["width"],
                        height=parameters["height"],
                        num_inference_steps=parameters["num_inference_steps"],
                        guidance_scale=parameters["guidance_scale"],
                        seed=parameters.get("seed"),
                    )
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()
                content_type = "image/png"
                selected_provider = provider
                break
            except Exception as exc:
                errors.append(_provider_error_summary(provider, exc))
                has_fallback = index + 1 < len(HF_IMAGE_PROVIDERS)
                if not _is_retryable_provider_error(exc) or not has_fallback:
                    raise HfMediaError(
                        "Hugging Face image generation failed after provider attempts: "
                        + "; ".join(errors)
                    ) from exc
                if HF_IMAGE_RETRY_DELAY_SECONDS > 0:
                    await asyncio.sleep(HF_IMAGE_RETRY_DELAY_SECONDS)

    return {
        "image_bytes": image_bytes,
        "content_type": content_type.split(";")[0] or "image/png",
        "provider": "huggingface",
        "inference_provider": selected_provider,
        "attempted_providers": attempted_providers,
        "model": HF_IMAGE_MODEL,
        "prompt": prompt,
        "parameters": parameters,
    }
