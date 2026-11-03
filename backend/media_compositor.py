from io import BytesIO
from typing import Iterable, Optional, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def _fit_background(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    scale = max(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def _load_character_layer(character_bytes: bytes) -> Image.Image:
    with Image.open(BytesIO(character_bytes)) as source_character:
        character = source_character.convert("RGBA")
    alpha_bounds = character.getchannel("A").getbbox()
    if alpha_bounds is None:
        raise ValueError("Character image does not contain visible pixels.")
    return character.crop(alpha_bounds)


def _normalized_tags(values: Optional[Iterable[str]]) -> set[str]:
    return {
        str(value).strip().lower().replace(" ", "_")
        for value in (values or [])
        if str(value).strip()
    }


def _apply_scene_effects(
    image: Image.Image,
    effect_tags: Optional[Iterable[str]],
) -> Image.Image:
    tags = _normalized_tags(effect_tags)
    treated = image.convert("RGBA")
    if "sunset_glow" in tags:
        overlay = Image.new("RGBA", treated.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for y in range(treated.height):
            ratio = y / max(treated.height - 1, 1)
            alpha = round(72 * (1.0 - ratio) + 14)
            draw.line(
                ((0, y), (treated.width, y)),
                fill=(248, 116, 79, alpha),
            )
        treated = Image.alpha_composite(treated, overlay)
    if "pale_mist" in tags:
        mist = Image.new("RGBA", treated.size, (236, 243, 244, 48))
        treated = Image.alpha_composite(treated, mist)
    if "soft_warmth" in tags:
        warmth = Image.new("RGBA", treated.size, (255, 217, 147, 26))
        treated = Image.alpha_composite(treated, warmth)
    if "murky_atmosphere" in tags:
        treated = ImageEnhance.Contrast(treated).enhance(0.82)
    return treated


def _draw_woven_basket(image: Image.Image, *, center_x: int, top: int) -> None:
    draw = ImageDraw.Draw(image)
    width = max(54, round(image.width * 0.17))
    height = max(42, round(image.height * 0.12))
    left = center_x - width // 2
    right = center_x + width // 2
    bottom = top + height
    line_width = max(2, image.width // 180)
    draw.arc(
        (left + width * 0.16, top - height * 0.55, right - width * 0.16, top + height * 0.55),
        180,
        360,
        fill=(88, 54, 28, 255),
        width=line_width + 1,
    )
    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=max(6, width // 10),
        fill=(190, 126, 55, 255),
        outline=(91, 58, 30, 255),
        width=line_width,
    )
    draw.ellipse(
        (left, top - height * 0.10, right, top + height * 0.24),
        fill=(222, 159, 78, 255),
        outline=(91, 58, 30, 255),
        width=line_width,
    )
    for offset in (0.35, 0.58, 0.79):
        y = round(top + height * offset)
        draw.line((left + 4, y, right - 4, y), fill=(122, 77, 36, 210), width=line_width)
    for offset in (0.25, 0.5, 0.75):
        x = round(left + width * offset)
        draw.line((x, top + 7, x, bottom - 5), fill=(232, 177, 94, 210), width=line_width)


def _draw_scene_props(
    image: Image.Image,
    prop_tags: Optional[Iterable[str]],
    *,
    has_secondary_character: bool,
) -> None:
    tags = _normalized_tags(prop_tags)
    if "woven_basket" in tags:
        _draw_woven_basket(
            image,
            center_x=round(image.width * (0.52 if has_secondary_character else 0.68)),
            top=round(image.height * 0.64),
        )


def _resize_character(
    character: Image.Image,
    *,
    target_height: int,
    max_width: int,
) -> Image.Image:
    scale = min(target_height / character.height, max_width / character.width)
    return character.resize(
        (
            max(1, round(character.width * scale)),
            max(1, round(character.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )


def _composite_character(
    background: Image.Image,
    character: Image.Image,
    *,
    center_x: int,
    ground_y: int,
) -> None:
    x = center_x - character.width // 2
    y = ground_y - character.height
    shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
    shadow_width = max(16, round(character.width * 0.62))
    shadow_height = max(8, round(character.height * 0.055))
    blur_radius = max(3, shadow_height // 2)
    ImageDraw.Draw(shadow).ellipse(
        (
            center_x - shadow_width // 2,
            ground_y - shadow_height // 2,
            center_x + shadow_width // 2,
            ground_y + shadow_height // 2,
        ),
        fill=(35, 35, 45, 92),
    )
    background.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur_radius)))
    background.alpha_composite(character, (x, y))


def compose_story_scene(
    background_bytes: bytes,
    character_bytes: bytes,
    *,
    secondary_character_bytes: Optional[bytes] = None,
    effect_tags: Optional[Iterable[str]] = None,
    prop_tags: Optional[Iterable[str]] = None,
    width: int = 512,
    height: int = 512,
) -> bytes:
    if width < 128 or height < 128:
        raise ValueError("Composite dimensions must be at least 128x128.")

    with Image.open(BytesIO(background_bytes)) as source_background:
        background = _fit_background(
            source_background.convert("RGBA"),
            (width, height),
        )
    background = _apply_scene_effects(background, effect_tags)
    primary = _load_character_layer(character_bytes)

    if secondary_character_bytes:
        secondary = _load_character_layer(secondary_character_bytes)
        primary = _resize_character(
            primary,
            target_height=round(height * 0.60),
            max_width=round(width * 0.45),
        )
        secondary = _resize_character(
            secondary,
            target_height=round(height * 0.54),
            max_width=round(width * 0.38),
        )
        ground_y = height - round(height * 0.035)
        _composite_character(
            background,
            secondary,
            center_x=round(width * 0.72),
            ground_y=ground_y,
        )
        _composite_character(
            background,
            primary,
            center_x=round(width * 0.34),
            ground_y=ground_y,
        )
    else:
        primary = _resize_character(
            primary,
            target_height=round(height * 0.68),
            max_width=round(width * 0.62),
        )
        _composite_character(
            background,
            primary,
            center_x=width // 2,
            ground_y=height - round(height * 0.035),
        )

    _draw_scene_props(
        background,
        prop_tags,
        has_secondary_character=bool(secondary_character_bytes),
    )

    output = BytesIO()
    background.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


def compose_background_scene(
    background_bytes: bytes,
    *,
    width: int = 512,
    height: int = 512,
    effect_tags: Optional[Iterable[str]] = None,
) -> bytes:
    if width < 128 or height < 128:
        raise ValueError("Composite dimensions must be at least 128x128.")

    with Image.open(BytesIO(background_bytes)) as source_background:
        background = _fit_background(
            source_background.convert("RGB"),
            (width, height),
        )
    background = _apply_scene_effects(background, effect_tags).convert("RGB")
    output = BytesIO()
    background.save(output, format="PNG", optimize=True)
    return output.getvalue()
