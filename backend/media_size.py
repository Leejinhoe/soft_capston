"""CPU-only size reduction; preserve acceptable originals and never trim clips."""
import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps
import imageio_ffmpeg

IMAGE_LIMIT = 10_000_000
VIDEO_LIMIT = 30_000_000
INPUT_LIMIT = 150_000_000


def fit_image(data, limit=IMAGE_LIMIT):
    if len(data) <= limit:
        return data
    if len(data) > INPUT_LIMIT:
        raise ValueError("Image input exceeds processing limit")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError("Image dimensions exceed processing limit")
        image = ImageOps.exif_transpose(source).convert("RGBA" if "A" in source.getbands() else "RGB")
        for edge in (4096, 3072, 2048, 1536, 1024):
            image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            if output.tell() <= limit:
                return output.getvalue()
    raise ValueError("Image cannot fit storage limit")


def fit_video(data, limit=VIDEO_LIMIT):
    if len(data) <= limit:
        return data
    if len(data) > INPUT_LIMIT:
        raise ValueError("Video input exceeds processing limit")
    with tempfile.TemporaryDirectory(prefix="media_size_") as directory:
        source = Path(directory) / "source.mp4"
        target = Path(directory) / "compressed.mp4"
        source.write_bytes(data)
        for edge, crf in ((1920, 23), (1280, 26), (960, 29)):
            scale = f"scale=w='min({edge},iw)':h='min({edge},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
            subprocess.run([
                imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-y", "-v", "error",
                "-threads", "2", "-i", str(source), "-map", "0:v:0", "-map", "0:a?",
                "-vf", scale, "-c:v", "libx264", "-threads", "2", "-preset", "fast",
                "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart", str(target),
            ], check=True, capture_output=True, timeout=120)
            if 0 < target.stat().st_size <= limit:
                return target.read_bytes()
    raise ValueError("Video cannot fit storage limit without excessive quality loss")
