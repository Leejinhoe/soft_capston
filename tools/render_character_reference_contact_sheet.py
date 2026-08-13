import argparse
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def fetch_image(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return Image.open(io.BytesIO(response.read())).convert("RGB")


def reference_asset(profile):
    assets = profile.get("assets") or []
    return next(
        (
            asset
            for asset in assets
            if asset.get("quality_tier") == "premium_reference"
        ),
        next((asset for asset in assets if asset.get("pose") == "default"), None),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Render the active story character reference images as a contact sheet."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--output",
        default="output/video_previews/story_character_references.png",
    )
    args = parser.parse_args()

    payload = fetch_json(f"{args.base_url}/api/media/characters")
    profiles = payload if isinstance(payload, list) else payload.get("value", [])
    rows = []
    for profile in sorted(profiles, key=lambda item: item.get("character_key", "")):
        asset = reference_asset(profile)
        if not asset or not asset.get("image_url"):
            continue
        image = fetch_image(f"{args.base_url}{asset['image_url']}")
        rows.append((profile, asset, image))

    if not rows:
        raise RuntimeError("No character reference images are available.")

    columns = 4
    cell_width = 300
    cell_height = 350
    label_height = 42
    rows_count = (len(rows) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows_count * cell_height),
        "#f4f5f7",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for index, (profile, asset, image) in enumerate(rows):
        column = index % columns
        row = index // columns
        left = column * cell_width
        top = row * cell_height
        fitted = image.copy()
        fitted.thumbnail((cell_width - 20, cell_height - label_height - 20))
        x = left + (cell_width - fitted.width) // 2
        y = top + 10 + (cell_height - label_height - 20 - fitted.height) // 2
        sheet.paste(fitted, (x, y))
        draw.rectangle(
            (left, top, left + cell_width - 1, top + cell_height - 1),
            outline="#c9ced6",
            width=2,
        )
        label = (
            f"{profile.get('character_key')} | "
            f"{asset.get('quality_tier', 'reference')}"
        )
        draw.text(
            (left + 10, top + cell_height - label_height + 8),
            label,
            fill="#20242b",
            font=font,
        )

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)
    print(output)


if __name__ == "__main__":
    main()
