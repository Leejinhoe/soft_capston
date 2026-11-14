import os
import unittest
import imageio.v2 as imageio
from io import BytesIO
import numpy as np
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("JWT_SECRET", "test-only-secret")
os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27017")

from bson import ObjectId
from fastapi.responses import Response
from PIL import Image

import branching
from story_video_assembly import assemble_scene_images


class ImageAssemblyTests(unittest.TestCase):
    def test_illustration_becomes_mp4(self):
        source = BytesIO()
        Image.new("RGB", (128, 128), "red").save(source, "PNG")
        video = assemble_scene_images([source.getvalue()])
        self.assertGreater(len(video), 100)
        self.assertEqual(video[4:8], b"ftyp")

    def test_still_scenes_hold_steady_and_only_dissolve_between_them(self):
        inputs = []
        for color in ("red", "blue"):
            source = BytesIO()
            Image.new("RGB", (128, 128), color).save(source, "PNG")
            inputs.append(source.getvalue())

        video = assemble_scene_images(inputs)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "still-journey.mp4"
            path.write_bytes(video)
            reader = imageio.get_reader(str(path))
            try:
                start = reader.get_data(0).astype(np.int16)
                held = reader.get_data(30).astype(np.int16)
                fade = reader.get_data(53).astype(np.int16)
                end = reader.get_data(70).astype(np.int16)
            finally:
                reader.close()

        self.assertLess(np.abs(start - held).mean(), 2.0)
        self.assertGreater(np.abs(held - fade).mean(), 10.0)
        self.assertLess(np.abs(fade - end).mean(), np.abs(held - end).mean())


class BackgroundJourneyTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_story_is_saved_to_r2(self):
        doc = {"_id": ObjectId(), "user_id": "owner", "status": "completed",
               "scenes": [{"image_file_id": str(ObjectId())}]}
        updated = MagicMock(matched_count=1)
        with patch.object(branching.stories_collection, "update_one", AsyncMock(return_value=updated)) as update, \
             patch.object(branching, "_my_story", AsyncMock(return_value=doc)), \
             patch.object(branching, "get_scene_image", AsyncMock(return_value=Response(b"image"))), \
             patch.object(branching, "assemble_scene_images", return_value=b"video"), \
             patch.object(branching.r2_media, "enabled", return_value=True), \
             patch.object(branching.r2_media, "put", AsyncMock()) as put:
            await branching._process_pending_journey(doc)
        self.assertEqual(put.await_count, 1)
        self.assertEqual(update.await_args_list[-1].args[1]["$set"]["assembled_video_status"], "completed")

    async def test_failed_generation_can_be_retried(self):
        doc = {"_id": ObjectId(), "user_id": "owner", "status": "completed",
               "assembled_video_status": "failed", "scenes": [{"text": "scene"}]}
        pending = {**doc, "assembled_video_status": "pending"}
        with patch.object(branching, "_my_story", AsyncMock(side_effect=[doc, pending])), \
             patch.object(branching.stories_collection, "update_one", AsyncMock()) as update:
            result = await branching.retry_journey_video(str(doc["_id"]), {"user_id": "owner"})
        self.assertEqual(result.assembled_video_status, "pending")
        self.assertEqual(update.await_args.args[1]["$set"]["assembled_video_status"], "pending")
