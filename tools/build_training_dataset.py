"""Build a captioned fairytale image dataset from the bundled assets.

The output is suitable for a Hugging Face ImageFolder-style dataset:
<output>/images/*.jpg and <output>/metadata.jsonl.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "DB연결 테스트"))

from motion_policy import SOLO_TRAINING_POSES  # noqa: E402


CHARACTER_DIR = ROOT / "assets" / "characters"
BACKGROUND_DIR = ROOT / "assets" / "backgrounds"
CHARACTER_KEYS = tuple(
    [f"male_{index:02d}" for index in range(1, 9)]
    + [f"female_{index:02d}" for index in range(1, 9)]
)
POSES = SOLO_TRAINING_POSES
POSE_CAPTIONS = {
    "default": "standing calmly with a neutral storybook pose",
    "happy": "smiling happily with an expressive joyful pose",
    "sad": "looking sad with a gentle emotional pose",
    "angry": "standing bravely with a determined angry expression",
    "walking": "walking toward the next story destination",
    "magic": "casting a gentle magical spell with glowing energy",
}
GENRES = ("fantasy", "adventure", "nature", "friendship", "mystery")
SCENES = {
    "fantasy": "an enchanted forest path leading toward a glowing castle",
    "adventure": "a wide adventure trail leading toward ancient ruins",
    "nature": "a peaceful woodland scene with a pond and soft light",
    "friendship": "a warm village square prepared for a small festival",
    "mystery": "an old library filled with maps, clocks, and clues",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "training_datasets" / "fairytale_multi_v2",
    )
    parser.add_argument(
        "--extra-root",
        type=Path,
        default=None,
        help="Optional folder containing <character_key>/*.png and matching .txt captions.",
    )
    parser.add_argument(
        "--characters",
        nargs="*",
        default=list(CHARACTER_KEYS),
        choices=CHARACTER_KEYS,
    )
    parser.add_argument("--max-backgrounds", type=int, default=3)
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove only the selected output dataset before rebuilding it.",
    )
    return parser.parse_args()


def _genre_for(character_key: str) -> str:
    index = int(character_key[-2:]) - 1
    gender_offset = 0 if character_key.startswith("male_") else 2
    return GENRES[(index + gender_offset) % len(GENRES)]


def _backgrounds_for(genre: str, limit: int) -> list[Path]:
    paths = sorted(
        path
        for path in BACKGROUND_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        and path.name.lower().startswith(f"{genre}_")
    )
    wide = [path for path in paths if "_wide_" in path.stem]
    ordered = wide + [path for path in paths if path not in wide]
    return ordered[: max(1, limit)]


def _crop_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    bounds = rgba.getchannel("A").getbbox()
    if bounds is None:
        return rgba
    return rgba.crop(bounds)


def _composite(
    character_path: Path,
    background_path: Path,
    output_path: Path,
    *,
    resolution: int,
    randomizer: random.Random,
) -> None:
    background = Image.open(background_path).convert("RGB")
    canvas = ImageOps.fit(
        background,
        (resolution, resolution),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    character = _crop_alpha(Image.open(character_path))
    target_height = int(resolution * randomizer.uniform(0.62, 0.82))
    target_width = max(1, round(character.width * target_height / character.height))
    character = character.resize(
        (target_width, target_height),
        Image.Resampling.LANCZOS,
    )
    max_x = max(0, resolution - target_width - 12)
    x = randomizer.randint(12, max_x + 12) if max_x else 0
    y = resolution - target_height - randomizer.randint(8, 24)

    shadow = Image.new("RGBA", character.size, (22, 18, 35, 105))
    shadow.putalpha(character.getchannel("A").point(lambda value: int(value * 0.38)))
    blurred_shadow = Image.new("RGBA", (resolution, resolution), (0, 0, 0, 0))
    blurred_shadow.alpha_composite(shadow, (x + 7, y + 9))
    blurred_shadow = blurred_shadow.filter(ImageFilter.GaussianBlur(8))

    rgba_canvas = canvas.convert("RGBA")
    rgba_canvas = Image.alpha_composite(rgba_canvas, blurred_shadow)
    rgba_canvas.alpha_composite(character, (x, y))
    rgba_canvas.convert("RGB").save(output_path, quality=95, optimize=True)


def _extra_sources(extra_root: Path | None, character_key: str) -> list[tuple[Path, str]]:
    if extra_root is None:
        return []
    folder = extra_root / character_key
    if not folder.is_dir():
        return []
    items = []
    for image_path in sorted(folder.iterdir()):
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        caption_path = image_path.with_suffix(".txt")
        caption = (
            caption_path.read_text(encoding="utf-8").strip()
            if caption_path.is_file()
            else "performing a clear natural fairytale action"
        )
        items.append((image_path, caption))
    return items


def build_dataset(args: argparse.Namespace) -> dict[str, int]:
    output = args.output.resolve()
    if args.clean and output.exists():
        for path in sorted(output.glob("**/*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    image_dir = output / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    records = []
    skipped = []
    randomizer = random.Random(args.seed)
    for character_key in args.characters:
        genre = _genre_for(character_key)
        backgrounds = _backgrounds_for(genre, args.max_backgrounds)
        if not backgrounds:
            skipped.append(f"{character_key}: no {genre} background")
            continue

        sources = []
        for pose in POSES:
            source_path = CHARACTER_DIR / f"{character_key}_{pose}.png"
            if source_path.is_file():
                sources.append((source_path, POSE_CAPTIONS[pose]))
            else:
                skipped.append(str(source_path))
        sources.extend(_extra_sources(args.extra_root, character_key))

        for source_index, (source_path, action) in enumerate(sources):
            for background_index, background_path in enumerate(backgrounds):
                filename = (
                    f"{character_key}__source_{source_index:02d}"
                    f"__background_{background_index:02d}.jpg"
                )
                output_path = image_dir / filename
                _composite(
                    source_path,
                    background_path,
                    output_path,
                    resolution=args.resolution,
                    randomizer=randomizer,
                )
                token = f"ft_{character_key}"
                caption = (
                    f"{token} character, {character_key}, {action}, "
                    f"in {SCENES[genre]}, children's storybook illustration, "
                    "consistent character identity, polished watercolor and gouache, no text"
                )
                records.append({"file_name": f"images/{filename}", "text": caption})

    with (output / "metadata.jsonl").open("w", encoding="utf-8") as metadata_file:
        for record in records:
            metadata_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {
        "characters": len(args.characters),
        "images": len(records),
        "solo_training_poses": list(POSES),
        "resolution": args.resolution,
        "max_backgrounds_per_character": args.max_backgrounds,
        "skipped": len(skipped),
    }
    (output / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if skipped:
        print("Skipped:")
        print("\n".join(skipped[:20]))
    print(f"Dataset: {output}")
    return summary


if __name__ == "__main__":
    build_dataset(_parse_args())
