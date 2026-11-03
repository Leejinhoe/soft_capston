"""Optional, fail-closed character illustration experiment for Hugging Face Spaces.

Note on Model Architecture Separation (2026-11-01):
1. FLUX Multi-Ref Space (HF_CHARACTER_SPACE_ID):
   - Private Space testing FLUX.2-klein FP4 image-to-image with reference character.
2. SDXL LoRA Serving (HF_SDXL_LORA_SPACE_ID):
   - SDXL 1.0 LoRA weights (trained via Diffusers) are architecture-incompatible
     with FLUX Spaces and must be served via a dedicated SDXL pipeline or SDXL Space.
   - Requires trigger token format 'sks_{character_key}' in the text prompt.
"""
import asyncio
import io
import inspect
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

CHARACTER_TRIGGER_MAP = {
    "male_01": "sks_minho",
    "male_02": "sks_jun",
    "male_03": "sks_taesan",
    "male_04": "sks_doyoon",
    "male_05": "sks_bori",
    "male_06": "sks_raven",
    "male_07": "sks_ian",
    "male_08": "sks_haneul",
    "female_01": "sks_mina",
    "female_02": "sks_hana",
    "female_03": "sks_miran",
    "female_04": "sks_luna",
    "female_05": "sks_seoyeon",
    "female_06": "sks_arin",
    "female_07": "sks_nara",
    "female_08": "sks_sol",
}

CHARACTER_IDENTITY_DESCRIPTIONS = {
    "male_01": "Korean boy around 8, round face, short black hair, brown eyes",
    "male_02": "Korean teenage boy, tousled dark hair, amber eyes",
    "male_03": "middle-aged Korean man, broad mature face, long black hair tied in a topknot, visible short black beard and moustache",
    "male_04": "elderly Korean man, silver hair, short white beard, gentle wrinkles",
    "male_05": "Korean boy around 7, fluffy dark-brown hair, freckles",
    "male_06": "young Korean man, sharp pale face, long black hair, gray eyes",
    "male_07": "Korean boy around 9, neatly parted chestnut hair, brown eyes",
    "male_08": "Korean adult man, slender face, wavy dark hair, blue-gray eyes",
    "female_01": "Korean girl around 8, round friendly face, short dark-brown bob, brown eyes",
    "female_02": "Korean girl around 8, two low dark braids, brown eyes",
    "female_03": "Korean teenage girl, soft oval face, long chestnut hair, hazel eyes",
    "female_04": "young Korean woman, heart-shaped face, wavy silver-brown hair, green eyes",
    "female_05": "Korean adult woman, oval face, black hair in a low ponytail",
    "female_06": "elderly Korean woman, silver hair in a low bun, warm smile lines",
    "female_07": "young Korean woman, angular face, long black hair, violet eyes",
    "female_08": "Korean teenage girl, sun-kissed round face, wavy dark-brown hair",
}


def build_sdxl_lora_negative_prompt(character_key: str) -> str:
    negative = "text, blurry, watermark, duplicate props"
    if (character_key or "").strip().lower() == "male_03":
        negative += ", clean-shaven, teenage boy, short untied hair"
    return negative


def get_character_trigger(character_key: str) -> str:
    """Map character key (e.g. 'male_01') to named trigger token (e.g. 'sks_minho')."""
    key = (character_key or "").strip().lower()
    if key.startswith("sks_"):
        return key
    return CHARACTER_TRIGGER_MAP.get(key, f"sks_{key}")


def build_sdxl_lora_prompt(character_key: str, action: str, *, scene_description: str = "") -> str:
    """Build standardized prompt embedding character trigger and watercolor storybook style."""
    trigger = get_character_trigger(character_key)
    identity = CHARACTER_IDENTITY_DESCRIPTIONS.get((character_key or "").strip().lower(), "")
    scene = scene_description.strip()
    background = f"scene: {scene}" if scene else "solid plain white background"
    return (
        f"{trigger}, {identity}, {action}, studio quality watercolor fairytale children's "
        f"storybook illustration, soft cinematic lighting, {background}"
    )


def build_sdxl_scene_prompt(character_key: str, story_text: str, motion_plan=None) -> str:
    """Use the existing scene plan as a visual hint, without claiming it is verified."""
    plan = motion_plan if isinstance(motion_plan, dict) else {}
    action = {
        "journey": "walking through the scene",
        "jump": "jumping",
        "investigate": "looking closely and exploring the scene",
        "magic": "casting magic",
        "wave": "waving one hand",
        "sit": "sitting",
        "stand": "standing",
    }.get(plan.get("action"), "a character in a fairytale scene")
    if plan.get("action") == "journey" and plan.get("pace") == "run":
        action = "running through the scene"
    text = (story_text or "").lower()
    if (plan.get("action") == "journey" and plan.get("target") == "castle"
            and any(phrase in text for phrase in ("toward the castle", "towards the castle", "성으로", "성을 향"))):
        verb = "running" if plan.get("pace") == "run" else "walking"
        action = f"{verb} away from the viewer toward the castle, back facing viewer"
    return build_sdxl_lora_prompt(character_key, action, scene_description=(story_text or "")[:1000])



def enabled():
    return os.getenv("HF_CHARACTER_SPACE_ENABLED", "").strip().lower() == "true"


def sdxl_lora_enabled():
    return os.getenv("HF_SDXL_LORA_ENABLED", "").strip().lower() == "true"


def action_for_scene(text):
    text = (text or "").lower()
    if ("망원경" in text or "telescope" in text) and any(
        term in text for term in ("보", "살펴", "바라", "관찰", "들여다", "look", "gaze", "peer")
    ):
        return "The character looks through a handheld brass telescope."
    return None


def extract_character(data):
    if not data or len(data) > 10_000_000:
        raise ValueError("Invalid generated image size")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 4_000_000:
            raise ValueError("Generated image dimensions exceed limit")
        rgb = np.asarray(source.convert("RGB"))
    h, w = rgb.shape[:2]
    white = np.all(rgb >= 245, axis=2).astype(np.uint8)
    if not all(white[y, x] for y, x in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1))):
        raise ValueError("Generated background is not plain white")
    n, labels = cv2.connectedComponents(white, connectivity=8)
    border_labels = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
    background = np.isin(labels, border_labels[border_labels != 0])
    foreground = (~background).astype(np.uint8)
    count, parts, stats, _ = cv2.connectedComponentsWithStats(foreground, connectivity=8)
    if count < 2:
        raise ValueError("Generated image has no character")
    areas = stats[1:, cv2.CC_STAT_AREA]
    biggest = int(np.argmax(areas)) + 1
    large_parts = sum(int(area) for area in areas if area > h * w * 0.004)
    if not large_parts or stats[biggest, cv2.CC_STAT_AREA] / large_parts < 0.9:
        raise ValueError("Generated image contains detached scene objects")
    mask = (parts == biggest).astype(np.uint8) * 255
    x, y, bw, bh, area = stats[biggest]
    if area < h * w * 0.04 or area > h * w * 0.75 or x <= 0 or y <= 0 or x + bw >= w or y + bh >= h:
        raise ValueError("Generated character is incomplete or badly framed")
    rgba = Image.fromarray(rgb).convert("RGBA")
    rgba.putalpha(Image.fromarray(mask))
    output = io.BytesIO()
    rgba.save(output, format="PNG")
    return output.getvalue()


def validate_scene_image(data):
    """Check file integrity without removing a generated scene's background."""
    if not data or len(data) > 10_000_000:
        raise ValueError("Invalid generated image size")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 4_000_000 or min(source.size) < 128:
            raise ValueError("Invalid generated scene dimensions")
        source.load()
        output = io.BytesIO()
        source.convert("RGB").save(output, format="PNG")
    return output.getvalue()


def _create_space_client(client_class, space, token, folder):
    parameters = inspect.signature(client_class).parameters
    token_name = "token" if "token" in parameters else "hf_token"
    return client_class(space, **{token_name: token}, verbose=False, download_files=folder)


def _call_space(reference, action, seed):
    from gradio_client import Client, handle_file

    token = os.getenv("HF_TOKEN", "").strip()
    space = os.getenv("HF_CHARACTER_SPACE_ID", "").strip()
    if not token or not space:
        raise ValueError("Space and token must be configured")
    with tempfile.TemporaryDirectory(prefix="fairytale_space_") as folder:
        reference_path = Path(folder) / "reference.png"
        reference_path.write_bytes(reference)
        client = _create_space_client(Client, space, token, folder)
        job = client.submit(reference=handle_file(str(reference_path)), action=action, seed=seed, api_name="/generate")
        try:
            result = job.result(timeout=45)
        except TimeoutError:
            job.cancel()
            raise
        result_path = Path(result).resolve()
        if not result_path.is_relative_to(Path(folder).resolve()):
            raise ValueError("Space returned an unexpected output path")
        return result_path.read_bytes()


def _call_sdxl_lora_space(prompt, negative_prompt, seed):
    """Call dedicated SDXL LoRA serving endpoint/Space."""
    from gradio_client import Client

    token = os.getenv("HF_TOKEN", "").strip()
    space = os.getenv("HF_SDXL_LORA_SPACE_ID", "").strip()
    if not token or not space:
        raise ValueError("SDXL LoRA Space and token must be configured")
    with tempfile.TemporaryDirectory(prefix="fairytale_sdxl_lora_") as folder:
        client = _create_space_client(Client, space, token, folder)
        job = client.submit(
            prompt=prompt,
            negative_prompt=negative_prompt or "text, blurry, watermark, duplicate props",
            seed=seed,
            api_name="/generate",
        )
        try:
            result = job.result(timeout=180)
        except TimeoutError:
            job.cancel()
            raise
        result_path = Path(result).resolve()
        if not result_path.is_relative_to(Path(folder).resolve()):
            raise ValueError("SDXL Space returned an unexpected output path")
        return result_path.read_bytes()


async def generate_character(reference, action, seed=42):
    """Multi-ref Space generation (e.g. FLUX.2-klein)."""
    data = await asyncio.to_thread(_call_space, reference, action, seed)
    return await asyncio.to_thread(extract_character, data)


async def generate_character_sdxl_lora(prompt, negative_prompt=None, seed=42, *, output_mode="cutout"):
    """Generate a cutout or validate a complete scene; neither verifies identity."""
    if output_mode not in {"cutout", "scene"}:
        raise ValueError("Unsupported output mode")
    data = await asyncio.to_thread(_call_sdxl_lora_space, prompt, negative_prompt, seed)
    processor = extract_character if output_mode == "cutout" else validate_scene_image
    return await asyncio.to_thread(processor, data)
