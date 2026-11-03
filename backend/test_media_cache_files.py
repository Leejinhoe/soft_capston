import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from bson import ObjectId
import main


class CacheFilesTests(unittest.IsolatedAsyncioTestCase):
    async def test_deleted_video_invalidates_completed_result(self):
        cursor = SimpleNamespace(to_list=AsyncMock(side_effect=[[object()], []]))
        bucket = SimpleNamespace(find=Mock(return_value=cursor))
        with patch.object(main, 'media_files_bucket', bucket):
            valid = await main.cached_media_files_exist(
                {'image_file_id': ObjectId(), 'video_file_id': ObjectId()}, True)
        self.assertFalse(valid)

    async def test_image_only_does_not_require_video(self):
        cursor = SimpleNamespace(to_list=AsyncMock(return_value=[object()]))
        bucket = SimpleNamespace(find=Mock(return_value=cursor))
        with patch.object(main, 'media_files_bucket', bucket):
            self.assertTrue(await main.cached_media_files_exist({'image_file_id': ObjectId()}, False))
        bucket.find.assert_called_once()

    async def test_invalid_file_id_is_cache_miss(self):
        self.assertFalse(await main.cached_media_files_exist({'image_file_id': 'bad'}, False))
