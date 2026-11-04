"""One reference -> cloud image -> private video provider test; no database changes."""
import asyncio
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")

from cloudflare_character import generate_scene
from hf_space_video import generate_scene_video


async def main():
    out = ROOT / "artifacts/cloudflare_video_integration"
    out.mkdir(parents=True, exist_ok=True)
    reference = (ROOT / "assets/characters/female_01_reference_v2.png").read_bytes()
    started = time.monotonic()
    scene = await generate_scene(reference, "A girl kneels by an open treasure chest in an enchanted forest.")
    (out / "scene.png").write_bytes(scene)
    print("Image saved, seconds:", round(time.monotonic() - started, 2), flush=True)
    started = time.monotonic()
    result = await generate_scene_video(scene, "A storybook girl kneels beside the open treasure chest and looks inside. The camera stays still.", 42)
    (out / "scene.mp4").write_bytes(result["video_bytes"])
    print("Video saved, seconds:", round(time.monotonic() - started, 2), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
