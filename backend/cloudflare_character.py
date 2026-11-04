"""Opt-in reference image editing through Workers AI."""
import asyncio
import base64
import binascii
import io
import os
import re
from pathlib import Path

import httpx
from PIL import Image

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
MAX_BYTES = 10_000_000
STORYBOOK_STYLE = (
    "Consistent hand-painted children's picture-book illustration, "
    "soft watercolor washes on textured paper, delicate ink outlines, "
    "gentle natural lighting and a balanced, cohesive color palette. "
    "Render both the character and the environment in the same watercolor style; "
    "avoid photorealism, 3D rendering, glossy plastic surfaces, text and watermarks."
)


def enabled():
    return os.getenv("CLOUDFLARE_CHARACTER_ENABLED", "").strip().lower() == "true"


def prepare_reference(data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Invalid reference image size")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 4_000_000:
            raise ValueError("Reference image is too large")
        source.load()
        rgba = source.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        white.alpha_composite(rgba)
        rgb = white.convert("RGB")
        rgb.thumbnail((512, 512))
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        return buf.getvalue()


def _english_visual_hint(scene: str) -> str:
    if not re.search(r"[\uac00-\ud7a3]", scene):
        return ""
    if any(k in scene for k in ("달려", "달리", "뛰어서", "뛰어가")):
        return " Visual action: the character is running forward, with alternating legs and arms."
    if any(k in scene for k in ("걸어", "나아", "건너", "향해")):
        return " Visual action: the character is walking forward with a dynamic, expressive pose."
    return " Visual action: expressive fairytale storybook scene with clear character pose."


def directional_reference(character_key, scene_contract):
    """Return a second identity reference only for unambiguous scene directions."""
    key = str(character_key or '').strip().lower()
    if not re.fullmatch(r'(male|female)_0[1-8]', key) or not isinstance(scene_contract, dict):
        return None
    action = scene_contract.get('action')
    direction = scene_contract.get('background_direction')
    if direction in ('left_to_right', 'right_to_left'):
        view = 'side'
    elif action == 'journey' and direction in ('toward_target', 'toward_route'):
        view = 'back'
    else:
        return None
    path = Path(__file__).resolve().parent.parent / 'assets' / 'characters' / 'reference_views' / f'{key}_{view}.png'
    if not path.is_file():
        return None
    return view, path.read_bytes()


def infer_reference_direction(scene):
    text = (scene or "").casefold()
    movement = any(word in text for word in ("걸어", "걸었", "걷", "달려", "달리", "건너", "향해", "나아가", "walk", "run"))
    if not movement:
        return None
    if any(word in text for word in ("왼쪽", "오른쪽", "left", "right")):
        return {"action": "journey", "background_direction": "left_to_right"}
    if any(word in text for word in ("향해", "toward", "towards")):
        return {"action": "journey", "background_direction": "toward_target"}
    return None


def build_scene_prompt(scene, direction_view=None):
    prompt = (
        "Use the same illustrated character from the first reference, preserving "
        "recognizable facial features, hair and age. Illustrate this story scene: "
        + scene + _english_visual_hint(scene) + " " + STORYBOOK_STYLE
    )
    if direction_view in ('side', 'back'):
        prompt += (
            " The first image defines the character's identity. The second image shows "
            f"the same character from the {direction_view} view; follow that viewing direction."
        )
    return prompt


async def generate_scene(reference, story_text, direction_reference=None, direction_view=None):
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_AI_TOKEN", "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", account) or not token:
        raise ValueError("Cloudflare Workers AI is not configured")
    scene = (story_text or "").strip()[:1000]
    if not scene:
        raise ValueError("Scene description is required")
    use_direction = bool(direction_reference and direction_view in ('side', 'back'))
    prompt = build_scene_prompt(scene, direction_view if use_direction else None)
    ref_bytes = prepare_reference(reference)
    files = {"input_image_0": ("reference.png", ref_bytes, "image/png")}
    if use_direction:
        files['input_image_1'] = ('direction.png', prepare_reference(direction_reference), 'image/png')
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=45, follow_redirects=False) as client:
        for attempt in range(2):
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    files=files,
                    data={"prompt": prompt},
                )
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                status_code = getattr(exc.response, "status_code", 0)
                if attempt == 0 and status_code in {408, 429, 500, 502, 503, 504}:
                    await asyncio.sleep(1.0)
                    continue
                raise
            except httpx.TransportError:
                if attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                raise
        payload = response.json()
    encoded = (payload.get("result") or {}).get("image")
    if not payload.get("success") or not isinstance(encoded, str) or len(encoded) > MAX_BYTES * 2:
        raise ValueError("Cloudflare returned an invalid image")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Cloudflare returned invalid image data") from exc
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Cloudflare returned an invalid image size")
    with Image.open(io.BytesIO(data)) as image:
        if min(image.size) < 128 or image.width * image.height > 4_000_000:
            raise ValueError("Cloudflare returned invalid dimensions")
        image.load()
        out = io.BytesIO()
        image.convert("RGB").save(out, format="PNG")
        return out.getvalue()
