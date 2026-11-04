import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import imageio.v2 as imageio
import numpy as np

from story_video_assembly import assemble_scene_videos
import main
from fastapi import HTTPException
from bson import ObjectId


class StoryVideoAssemblyTests(unittest.TestCase):
    def test_rejects_empty_scenes(self):
        with self.assertRaises(ValueError):
            assemble_scene_videos([])

    def test_combines_two_clips(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.mp4"
            with imageio.get_writer(str(path), fps=12, codec="libx264", macro_block_size=2) as writer:
                for _ in range(12):
                    writer.append_data(np.full((64, 64, 3), 140, dtype=np.uint8))
            result = assemble_scene_videos([path.read_bytes(), path.read_bytes()])
            self.assertEqual(result[4:8], b"ftyp")
            out = Path(folder) / "output.mp4"
            out.write_bytes(result)
            with imageio.get_reader(str(out)) as reader:
                self.assertEqual(reader.count_frames(), 24)
                self.assertEqual(reader.get_data(0).shape[:2], (360, 640))


class StoryImageFallbackTests(unittest.TestCase):
    def test_mixes_image_scene_and_video_scene(self):
        import io
        from PIL import Image
        from story_video_assembly import assemble_scene_media, IMAGE_SCENE_FRAMES
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), (200, 120, 60)).save(buf, "PNG")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.mp4"
            with imageio.get_writer(str(path), fps=12, codec="libx264", macro_block_size=2) as writer:
                for _ in range(12):
                    writer.append_data(np.full((64, 64, 3), 140, dtype=np.uint8))
            result = assemble_scene_media([("image", buf.getvalue()), ("video", path.read_bytes())])
            out = Path(folder) / "output.mp4"
            out.write_bytes(result)
            with imageio.get_reader(str(out)) as reader:
                self.assertEqual(reader.count_frames(), IMAGE_SCENE_FRAMES + 12)

    def test_eight_scenes_capped_within_twenty_seconds(self):
        import io
        from PIL import Image
        from story_video_assembly import assemble_scene_media, HIGH_QUALITY_FPS, MAX_TOTAL_SECONDS
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), (180, 110, 90)).save(buf, "PNG")
        img_bytes = buf.getvalue()
        result = assemble_scene_media([("image", img_bytes) for _ in range(8)], fps=HIGH_QUALITY_FPS)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "output8.mp4"
            out.write_bytes(result)
            with imageio.get_reader(str(out)) as reader:
                frames = reader.count_frames()
                duration = frames / HIGH_QUALITY_FPS
                self.assertGreaterEqual(duration, 16.0)
                self.assertLessEqual(duration, MAX_TOTAL_SECONDS)

    def test_supports_action_animation_scene(self):
        from story_video_assembly import assemble_scene_media, IMAGE_SCENE_FRAMES
        result = assemble_scene_media([
            (
                "action",
                {
                    "character_key": "female_01",
                    "story_text": "미나가 주문을 외우며 오솔길을 따라 걸어갔어요.",
                    "genre": "판타지",
                    "action": "run",
                },
            )
        ])
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "action.mp4"
            out.write_bytes(result)
            with imageio.get_reader(str(out)) as reader:
                self.assertEqual(reader.count_frames(), IMAGE_SCENE_FRAMES)
                self.assertEqual(reader.get_data(0).shape[:2], (360, 640))


class StoryAssemblyEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_incomplete_story(self):
        with patch.object(main, 'require_story_owner', AsyncMock(return_value={'completed': False})):
            with self.assertRaises(HTTPException) as error:
                await main.assemble_story_video('story', object())
        self.assertEqual(error.exception.status_code, 409)

    async def test_reports_scene_without_image_or_video(self):
        story = {'completed': True, 'scenes': [{'step_number': 2, 'image_url': '/api/media/images/example'}]}
        with patch.object(main, 'require_story_owner', AsyncMock(return_value=story)):
            with self.assertRaises(HTTPException) as error:
                await main.assemble_story_video('story', object())
        self.assertEqual(error.exception.detail['missing_scenes'], [2])

    async def test_reuses_unchanged_owned_assembly(self):
        story_id, owner, scene_id, output_id = map(str, (ObjectId(), ObjectId(), ObjectId(), ObjectId()))
        url = f'/api/media/videos/{output_id}'
        story = {'completed': True, 'scenes': [{'step_number': 1, 'video_url': f'/api/media/videos/{scene_id}'}],
                 'assembled_video_url': url, 'assembled_video_sources': [scene_id]}
        bucket = MagicMock()
        bucket.find.return_value.to_list = AsyncMock(return_value=[{'metadata': {'story_id': story_id, 'owner_user_id': owner}}])
        with patch.object(main, 'require_story_owner', AsyncMock(return_value=story)), \
             patch.object(main, 'authenticated_user_id', return_value=owner), \
             patch.object(main, 'media_files_bucket', bucket), \
             patch.object(main, 'download_gridfs_file', AsyncMock()) as download:
            result = await main.assemble_story_video(story_id, object())
        self.assertEqual(result['video_url'], url)
        self.assertTrue(result['reused'])
        download.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
