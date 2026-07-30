"""Generate deterministic transparent storybook character assets with Pillow."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "assets" / "characters"
CANVAS_SIZE = 512
SCALE = 4
POSES = ("default", "happy", "sad", "angry", "walking", "talking", "magic", "rescue")


@dataclass(frozen=True)
class CharacterStyle:
    key: str
    skin: str
    hair: str
    outfit: str
    accent: str
    eyes: str
    hair_style: str


SKINS = ("#f6c8a9", "#e8b28f", "#d7956e", "#b97150")
HAIRS = ("#39251f", "#171a21", "#70452d", "#d8a64d", "#8b3f35", "#40304f")
OUTFITS_MALE = ("#2f78b7", "#3d8a64", "#9b4d4d", "#7655a8", "#cf7a32", "#397d88", "#62744a", "#305da8")
OUTFITS_FEMALE = ("#d45b83", "#5d75bd", "#4a9676", "#9a5da8", "#d0793e", "#397f95", "#b24f62", "#647f3e")
ACCENTS = ("#f2c94c", "#ef8354", "#78c6a3", "#d7aefb", "#f4a261", "#80b9de", "#e9c46a", "#f28482")
HAIR_STYLES_MALE = ("short", "swept", "curly", "spiky", "parted", "wavy", "crop", "long")
HAIR_STYLES_FEMALE = ("bob", "long", "ponytail", "braids", "curly", "bun", "wavy", "short")


def build_styles() -> tuple[CharacterStyle, ...]:
    styles = []
    for index in range(8):
        styles.append(
            CharacterStyle(
                key=f"male_{index + 1:02d}",
                skin=SKINS[index % len(SKINS)],
                hair=HAIRS[index % len(HAIRS)],
                outfit=OUTFITS_MALE[index],
                accent=ACCENTS[index],
                eyes=("#3c2c27", "#23465f", "#315b43")[index % 3],
                hair_style=HAIR_STYLES_MALE[index],
            )
        )
    for index in range(8):
        styles.append(
            CharacterStyle(
                key=f"female_{index + 1:02d}",
                skin=SKINS[(index + 1) % len(SKINS)],
                hair=HAIRS[(index + 2) % len(HAIRS)],
                outfit=OUTFITS_FEMALE[index],
                accent=ACCENTS[(index + 3) % len(ACCENTS)],
                eyes=("#3c2c27", "#23465f", "#315b43")[index % 3],
                hair_style=HAIR_STYLES_FEMALE[index],
            )
        )
    return tuple(styles)


STYLES = build_styles()


def _scaled_points(points: Iterable[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(round(x * SCALE), round(y * SCALE)) for x, y in points]


def _xy(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    return tuple(round(value * SCALE) for value in box)


def _line(draw: ImageDraw.ImageDraw, points, fill, width=4):
    draw.line(_scaled_points(points), fill=fill, width=round(width * SCALE), joint="curve")


def _ellipse(draw: ImageDraw.ImageDraw, box, fill, outline=None, width=1):
    draw.ellipse(_xy(box), fill=fill, outline=outline, width=round(width * SCALE))


def _polygon(draw: ImageDraw.ImageDraw, points, fill, outline=None):
    draw.polygon(_scaled_points(points), fill=fill, outline=outline)


def _rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(
        _xy(box),
        radius=round(radius * SCALE),
        fill=fill,
        outline=outline,
        width=round(width * SCALE),
    )


def _arc(draw: ImageDraw.ImageDraw, box, start, end, fill, width=3):
    draw.arc(_xy(box), start=start, end=end, fill=fill, width=round(width * SCALE))


def _pose_geometry(pose: str):
    if pose == "walking":
        return ((173, 260), (345, 243), (226, 413), (301, 432))
    if pose == "magic":
        return ((157, 218), (361, 179), (234, 425), (291, 425))
    if pose == "rescue":
        return ((149, 213), (367, 213), (230, 425), (296, 425))
    if pose == "talking":
        return ((174, 262), (356, 221), (238, 425), (294, 425))
    if pose == "happy":
        return ((170, 224), (344, 224), (237, 425), (294, 425))
    if pose == "sad":
        return ((181, 284), (333, 284), (239, 425), (292, 425))
    if pose == "angry":
        return ((170, 273), (345, 273), (231, 425), (300, 425))
    return ((179, 278), (335, 278), (239, 425), (292, 425))


def _draw_hair_back(draw: ImageDraw.ImageDraw, style: CharacterStyle):
    if style.hair_style in {"long", "wavy", "ponytail", "braids"}:
        _rounded(draw, (181, 76, 334, 249), 60, style.hair)
    if style.hair_style == "ponytail":
        _ellipse(draw, (315, 108, 375, 220), style.hair)
    if style.hair_style == "braids":
        for x in (188, 318):
            for y in range(170, 257, 24):
                _ellipse(draw, (x - 10, y, x + 10, y + 27), style.hair)
    if style.hair_style == "bun":
        _ellipse(draw, (226, 49, 292, 111), style.hair)


def _draw_hair_front(draw: ImageDraw.ImageDraw, style: CharacterStyle):
    color = style.hair
    if style.hair_style in {"curly"}:
        for x, y in ((190, 105), (213, 85), (241, 79), (269, 79), (297, 87), (321, 109)):
            _ellipse(draw, (x - 24, y - 18, x + 24, y + 27), color)
    elif style.hair_style == "spiky":
        _polygon(draw, ((180, 129), (192, 74), (215, 101), (239, 61), (256, 98), (291, 65), (296, 105), (334, 90), (326, 146)), color)
    elif style.hair_style in {"swept", "parted"}:
        _polygon(draw, ((179, 142), (189, 92), (258, 71), (329, 98), (326, 140), (268, 103), (246, 143), (229, 106)), color)
    elif style.hair_style in {"bob", "short", "crop"}:
        _rounded(draw, (178, 77, 336, 151), 43, color)
        _polygon(draw, ((179, 126), (206, 96), (231, 128), (258, 91), (284, 125), (332, 103), (334, 153)), color)
    else:
        _rounded(draw, (180, 76, 334, 145), 42, color)
        _polygon(draw, ((181, 130), (211, 97), (236, 133), (266, 92), (293, 129), (331, 101), (333, 151)), color)


def _draw_face(draw: ImageDraw.ImageDraw, style: CharacterStyle, pose: str):
    outline = "#593c32"
    _ellipse(draw, (187, 91, 328, 234), style.skin, outline, 2)
    _ellipse(draw, (178, 144, 199, 180), style.skin, outline, 2)
    _ellipse(draw, (316, 144, 337, 180), style.skin, outline, 2)
    _draw_hair_front(draw, style)

    eye_y = 157
    if pose == "happy":
        _arc(draw, (216, eye_y - 4, 241, eye_y + 15), 190, 350, style.eyes, 4)
        _arc(draw, (275, eye_y - 4, 300, eye_y + 15), 190, 350, style.eyes, 4)
    elif pose == "sad":
        _arc(draw, (216, eye_y, 241, eye_y + 16), 195, 345, style.eyes, 4)
        _arc(draw, (275, eye_y, 300, eye_y + 16), 195, 345, style.eyes, 4)
    else:
        _ellipse(draw, (221, 151, 236, 169), style.eyes)
        _ellipse(draw, (280, 151, 295, 169), style.eyes)
        _ellipse(draw, (225, 153, 230, 159), "#ffffff")
        _ellipse(draw, (284, 153, 289, 159), "#ffffff")

    if pose == "angry":
        _line(draw, ((215, 143), (239, 149)), outline, 3)
        _line(draw, ((277, 149), (301, 143)), outline, 3)
        _arc(draw, (240, 186, 277, 211), 195, 345, outline, 4)
    elif pose == "sad":
        _line(draw, ((215, 145), (239, 140)), outline, 3)
        _line(draw, ((277, 140), (301, 145)), outline, 3)
        _arc(draw, (240, 187, 277, 212), 195, 345, outline, 4)
        _ellipse(draw, (299, 169, 306, 183), "#72b9df")
    elif pose in {"happy", "rescue"}:
        _arc(draw, (238, 178, 279, 211), 10, 170, outline, 4)
    elif pose == "talking":
        _ellipse(draw, (247, 183, 270, 205), "#8b4747", outline, 2)
    else:
        _arc(draw, (244, 182, 273, 204), 15, 165, outline, 3)

    _ellipse(draw, (205, 178, 220, 186), "#e9938c")
    _ellipse(draw, (296, 178, 311, 186), "#e9938c")


def _draw_body(draw: ImageDraw.ImageDraw, style: CharacterStyle, pose: str):
    outline = "#49362f"
    left_hand, right_hand, left_foot, right_foot = _pose_geometry(pose)
    _rounded(draw, (242, 218, 274, 247), 8, style.skin, outline, 2)

    _line(draw, ((215, 258), left_hand), outline, 31)
    _line(draw, ((215, 258), left_hand), style.outfit, 24)
    _line(draw, ((300, 258), right_hand), outline, 31)
    _line(draw, ((300, 258), right_hand), style.outfit, 24)
    _ellipse(draw, (left_hand[0] - 13, left_hand[1] - 13, left_hand[0] + 13, left_hand[1] + 13), style.skin, outline, 2)
    _ellipse(draw, (right_hand[0] - 13, right_hand[1] - 13, right_hand[0] + 13, right_hand[1] + 13), style.skin, outline, 2)

    _rounded(draw, (198, 235, 317, 370), 38, style.outfit, outline, 3)
    _polygon(draw, ((199, 335), (183, 390), (332, 390), (316, 335)), style.outfit, outline)
    _rounded(draw, (207, 282, 308, 302), 8, style.accent, outline, 2)
    _ellipse(draw, (247, 281, 268, 303), "#f4d35e", outline, 2)
    _polygon(draw, ((235, 240), (257, 267), (280, 240)), style.accent, outline)

    _line(draw, ((238, 370), left_foot), outline, 32)
    _line(draw, ((238, 370), left_foot), "#494f68", 24)
    _line(draw, ((287, 370), right_foot), outline, 32)
    _line(draw, ((287, 370), right_foot), "#494f68", 24)
    _ellipse(draw, (left_foot[0] - 25, left_foot[1] - 9, left_foot[0] + 19, left_foot[1] + 17), "#45352f", outline, 2)
    _ellipse(draw, (right_foot[0] - 19, right_foot[1] - 9, right_foot[0] + 25, right_foot[1] + 17), "#45352f", outline, 2)


def _draw_pose_effects(draw: ImageDraw.ImageDraw, style: CharacterStyle, pose: str):
    if pose == "magic":
        hand_x, hand_y = _pose_geometry(pose)[1]
        _line(draw, ((hand_x, hand_y), (397, 119)), "#6d4932", 7)
        for radius, color in ((42, "#7dd3fc"), (29, "#c4b5fd"), (14, "#fff7ae")):
            _arc(draw, (397 - radius, 119 - radius, 397 + radius, 119 + radius), 0, 330, color, 5)
        for angle in range(0, 360, 60):
            x = 397 + math.cos(math.radians(angle)) * 55
            y = 119 + math.sin(math.radians(angle)) * 55
            _ellipse(draw, (x - 5, y - 5, x + 5, y + 5), "#fff7ae")
    elif pose == "rescue":
        _polygon(draw, ((258, 249), (279, 271), (258, 302), (237, 271)), "#f4d35e", "#7b5b24")
        _ellipse(draw, (242, 254, 274, 286), "#f4d35e", "#7b5b24", 2)
        _rounded(draw, (252, 280, 264, 321), 4, "#f4d35e", "#7b5b24", 2)
    elif pose == "talking":
        _rounded(draw, (337, 151, 425, 205), 17, "#ffffff", "#6d7c8d", 3)
        _polygon(draw, ((348, 201), (338, 222), (365, 204)), "#ffffff", "#6d7c8d")
        for x in (354, 377, 400):
            _ellipse(draw, (x, 174, x + 8, 182), style.accent)
    elif pose == "happy":
        for x, y in ((150, 159), (370, 151), (351, 305)):
            _line(draw, ((x - 8, y), (x + 8, y)), style.accent, 4)
            _line(draw, ((x, y - 8), (x, y + 8)), style.accent, 4)
    elif pose == "angry":
        _line(draw, ((343, 119), (361, 106), (357, 129), (377, 123)), "#d84a4a", 5)
    elif pose == "sad":
        _ellipse(draw, (153, 321, 163, 338), "#72b9df")


def render_character(style: CharacterStyle, pose: str) -> Image.Image:
    if pose not in POSES:
        raise ValueError(f"Unknown pose: {pose}")
    image = Image.new("RGBA", (CANVAS_SIZE * SCALE, CANVAS_SIZE * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _ellipse(draw, (185, 430, 334, 455), (64, 50, 45, 45))
    _draw_hair_back(draw, style)
    _draw_body(draw, style, pose)
    _draw_face(draw, style, pose)
    _draw_pose_effects(draw, style, pose)
    return image.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)


def generate_all(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for style in STYLES:
        for pose in POSES:
            path = output_dir / f"{style.key}_{pose}.png"
            render_character(style, pose).save(path, "PNG", optimize=True)
            generated.append(path)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    generated = generate_all(args.output_dir)
    print(f"Generated {len(generated)} character assets in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
