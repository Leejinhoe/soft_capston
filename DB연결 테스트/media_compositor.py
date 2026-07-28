from io import BytesIO
from typing import Tuple

from PIL import Image, ImageFilter


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


def compose_story_scene(
    background_bytes: bytes,
    character_bytes: bytes,
    *,
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
    with Image.open(BytesIO(character_bytes)) as source_character:
        character = source_character.convert("RGBA")

    alpha_bounds = character.getchannel("A").getbbox()
    if alpha_bounds is None:
        raise ValueError("Character image does not contain visible pixels.")
    character = character.crop(alpha_bounds)

    target_height = round(height * 0.68)
    scale = min(target_height / character.height, width * 0.62 / character.width)
    character = character.resize(
        (
            max(1, round(character.width * scale)),
            max(1, round(character.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )

    x = (width - character.width) // 2
    y = max(0, height - character.height - round(height * 0.035))

    shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
    shadow_width = max(16, round(character.width * 0.62))
    shadow_height = max(8, round(height * 0.035))
    shadow_blob = Image.new(
        "RGBA",
        (shadow_width, shadow_height),
        (35, 35, 45, 92),
    ).filter(ImageFilter.GaussianBlur(max(3, shadow_height // 2)))
    shadow_x = (width - shadow_width) // 2
    shadow_y = min(height - shadow_height, y + character.height - shadow_height // 2)
    shadow.alpha_composite(shadow_blob, (shadow_x, shadow_y))

    background.alpha_composite(shadow)
    background.alpha_composite(character, (x, y))

    output = BytesIO()
    background.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
