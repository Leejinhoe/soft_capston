import argparse
from pathlib import Path

import imageio.v2 as imageio
from PIL import Image, ImageDraw


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render sampled video frames as a contact sheet.")
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--frame-width", type=int, default=320)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    reader = imageio.get_reader(str(args.video))
    try:
        metadata = reader.get_meta_data()
        fps = float(metadata.get("fps") or 30.0)
        first_frame = Image.fromarray(reader.get_data(0)).convert("RGB")
        frame_height = round(args.frame_width * first_frame.height / first_frame.width)
        label_height = 24
        rows = (args.count + args.columns - 1) // args.columns
        sheet = Image.new(
            "RGB",
            (args.frame_width * args.columns, (frame_height + label_height) * rows),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        for index in range(args.count):
            second = args.start + index * args.interval
            frame_index = max(0, round(second * fps))
            frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
            frame.thumbnail(
                (args.frame_width, frame_height),
                Image.Resampling.LANCZOS,
            )
            x = (index % args.columns) * args.frame_width
            y = (index // args.columns) * (frame_height + label_height)
            sheet.paste(frame, (x, y + label_height))
            draw.text((x + 8, y + 5), f"{second:.2f}s / frame {frame_index}", fill="black")
    finally:
        reader.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
