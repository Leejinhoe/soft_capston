"""Opt-in live Cloudflare and isolated Mongo integration test."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

LIVE = os.getenv("MEDIA_LIVE_TEST") == "1"
if LIVE and not os.getenv("DB_NAME", "").startswith("fairytale_media_test_"):
    raise RuntimeError("Live media tests require a dedicated fairytale_media_test_ database.")

os.environ.setdefault("JWT_SECRET", "isolated-test-only")
os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27017")

import imageio.v2 as imageio
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

import branching
from database import client as mongo_client
from security import get_current_user
from story_engine import SceneResult


class FakeStoryEngine:
    async def opening(self, setup):
        return SceneResult("미나는 숲에서 성을 발견했다.", ["성으로 걸어간다", "기다린다", "길을 살핀다"])

    async def next_scene(self, setup, scenes, choice):
        return SceneResult("미나는 성을 향해 걸어간다.", ["문을 연다", "주위를 살핀다", "돌아간다"])

    async def ending(self, setup, scenes, choice):
        return SceneResult("미나는 즐겁게 집으로 돌아갔다.", [], "미나의 모험")


def synthetic_clip():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "clip.mp4"
        with imageio.get_writer(str(path), fps=12, codec="libx264", macro_block_size=2,
                                ffmpeg_log_level="error") as writer:
            for index in range(24):
                frame = np.zeros((96, 160, 3), dtype=np.uint8)
                frame[:, index * 3:index * 3 + 20, 1] = 200
                writer.append_data(frame)
        return path.read_bytes()


@unittest.skipUnless(LIVE, "Set MEDIA_LIVE_TEST=1 and use an isolated database")
class LiveMediaTests(unittest.TestCase):
    def test_choice_real_image_mock_video_and_journey(self):
        self.addCleanup(mongo_client.close)
        app = FastAPI()
        app.include_router(branching.router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "isolated-media-test"}
        branching.configure(None, engine=FakeStoryEngine())
        with patch.object(branching, "recommend_vocab", AsyncMock(return_value=[])), \
             patch.object(branching.hf_space_video, "enabled", return_value=True), \
             patch.object(branching.hf_space_video, "generate_scene_video",
                          AsyncMock(return_value={"video_bytes": synthetic_clip(), "provider": "test-fixture"})):
            with TestClient(app) as client:
                started = client.post("/api/stories/branching/start", json={
                    "prompt": "숲속 모험", "genre": "판타지", "age": "7", "character_key": "female_01"})
                self.assertEqual(started.status_code, 200, started.text)
                story_id = started.json()["story_id"]
                chosen = client.post(f"/api/stories/{story_id}/choose", json={"scene_number": 1, "choice_index": 0})
                self.assertEqual(chosen.status_code, 200, chosen.text)
                self.assertEqual(chosen.json()["character_key"], "female_01")
                image = client.post(f"/api/stories/{story_id}/scenes/2/image")
                self.assertEqual(image.status_code, 200, image.text)
                self.assertTrue(image.json()["scenes"][1]["image_url"])
                loaded = client.get(f"/api/stories/{story_id}/scenes/2/image")
                self.assertEqual(loaded.status_code, 200, loaded.text[:100])
                self.assertTrue(loaded.content.startswith(b"\x89PNG"))
                video = client.post(f"/api/stories/{story_id}/scenes/2/video")
                self.assertEqual(video.status_code, 200, video.text)
                self.assertTrue(video.json()["scenes"][1]["video_url"])
                ending = client.post(f"/api/stories/{story_id}/finish", json={"scene_number": 2})
                self.assertEqual(ending.status_code, 200, ending.text)
                self.assertTrue(ending.json()["scenes"][1]["image_url"])
                journey = client.post(f"/api/stories/{story_id}/journey-video")
                self.assertEqual(journey.status_code, 200, journey.text)
                self.assertTrue(journey.json()["assembled_video_url"])
                downloaded = client.get(f"/api/stories/{story_id}/journey-video")
                self.assertEqual(downloaded.status_code, 200)
                self.assertEqual(downloaded.content[4:8], b"ftyp")
                print("Isolated live test passed; story", story_id, "database", os.environ["DB_NAME"])


if __name__ == "__main__":
    unittest.main()
