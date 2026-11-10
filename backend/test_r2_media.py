import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

os.environ.setdefault("JWT_SECRET", "test-only-secret")
os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27017")

import branching
import r2_media


class R2StorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_and_download_use_private_fixed_key(self):
        story_id, media_id = str(ObjectId()), str(ObjectId())
        body = MagicMock(read=MagicMock(return_value=b"png"))
        client = MagicMock(get_object=MagicMock(return_value={
            "Body": body, "ContentLength": 3,
            "Metadata": {"sha256": "d9881b4ba886d1a439c9a6ec7e587d174f36b8a50a8ecde2b47e6290ed08ecf"}}))
        # Use an exact hash from the test bytes, not a hardcoded fixture.
        import hashlib
        client.get_object.return_value["Metadata"]["sha256"] = hashlib.sha256(b"png").hexdigest()
        with patch.object(r2_media, "_client", return_value=client), \
             patch.object(r2_media, "_bucket", return_value="private-test"):
            key = await r2_media.put(story_id, "image", media_id, b"png")
            self.assertEqual(key, f"stories/{story_id}/image/{media_id}")
            self.assertEqual(await r2_media.get(story_id, "image", media_id, 10), b"png")
        self.assertEqual(client.put_object.call_args.kwargs["ContentType"], "image/png")

    async def test_owned_story_reads_r2_without_gridfs(self):
        story_id, media_id = str(ObjectId()), str(ObjectId())
        doc = {"_id": ObjectId(story_id), "user_id": "owner",
               "scenes": [{"image_file_id": media_id, "image_storage": "r2"}]}
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)) as owned, \
             patch.object(branching.r2_media, "get", AsyncMock(return_value=b"png")) as get, \
             patch.object(branching, "AsyncIOMotorGridFSBucket") as gridfs:
            response = await branching.get_scene_image(story_id, 1, {"user_id": "owner"})
        owned.assert_awaited_once_with(story_id, "owner")
        get.assert_awaited_once_with(story_id, "image", media_id, 10_000_000)
        gridfs.assert_not_called()
        self.assertEqual(response.body, b"png")

    async def test_oversized_r2_object_is_rejected_before_read(self):
        client = MagicMock(get_object=MagicMock(return_value={
            "Body": MagicMock(), "ContentLength": 11, "Metadata": {}}))
        with patch.object(r2_media, "_client", return_value=client), \
             patch.object(r2_media, "_bucket", return_value="private-test"):
            with self.assertRaises(ValueError):
                await r2_media.get(str(ObjectId()), "image", str(ObjectId()), 10)
        client.get_object.return_value["Body"].read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
