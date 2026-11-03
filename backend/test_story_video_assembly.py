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


class StoryAssemblyEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_incomplete_story(self):
        with patch.object(main, 'require_story_owner', AsyncMock(return_value={'completed': False})):
            with self.assertRaises(HTTPException) as error:
                await main.assemble_story_video('story', object())
        self.assertEqual(error.exception.status_code, 409)

    async def test_reports_missing_scene_instead_of_making_still_video(self):
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
