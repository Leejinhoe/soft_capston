import unittest
import hashlib
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from scene_library import approved_image, read_catalog, select_assets
from scene_library import load_scene_references


class SceneLibraryTests(unittest.TestCase):
    def test_catalog_contains_eight_backgrounds_twelve_props(self):
        assets = read_catalog()
        self.assertEqual(sum(a["kind"] == "background" for a in assets), 8)
        self.assertEqual(sum(a["kind"] == "prop" for a in assets), 12)

    def test_drafts_never_reach_generation(self):
        assets = [{**a, "status": "draft"} for a in read_catalog()]
        self.assertEqual(select_assets("숲에서 보물상자를 연다", assets), [])
        with self.assertRaises(ValueError):
            approved_image(assets[0])

    def test_selects_at_most_one_of_each_kind(self):
        assets = [{**a, "status": "approved"} for a in read_catalog()]
        result = select_assets("숲에서 보물상자를 열쇠로 연다", assets)
        self.assertEqual([a["asset_id"] for a in result], ["forest", "chest"])

    def test_no_unrelated_default_or_english_substring(self):
        assets = [{**a, "status": "approved"} for a in read_catalog()]
        self.assertEqual(select_assets("monkey smiles", assets), [])
        self.assertEqual(select_assets("웃는다", assets), [])

    def test_preview_cannot_be_published_as_production(self):
        item = {**read_catalog()[0], "status": "approved", "file": "previews/backgrounds-v1.png"}
        with self.assertRaises(ValueError):
            approved_image(item)


class SceneLibraryLookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_failure_falls_back_without_blocking_generation(self):
        database = MagicMock()
        database.__getitem__.return_value.find.side_effect = RuntimeError("offline")
        self.assertEqual(await load_scene_references(database, MagicMock(), "숲"), [])

    async def test_reads_and_verifies_gridfs_reference(self):
        data = b"test-reference"
        doc = {**read_catalog()[0], "file_id": str(ObjectId()),
               "sha256": hashlib.sha256(data).hexdigest()}
        database = MagicMock()
        cursor = database.__getitem__.return_value.find.return_value.sort.return_value.limit.return_value
        cursor.to_list = AsyncMock(return_value=[doc])
        stream = MagicMock(length=len(data), read=AsyncMock(return_value=data))
        bucket = MagicMock(open_download_stream=AsyncMock(return_value=stream))
        refs = await load_scene_references(database, bucket, "숲")
        self.assertEqual(refs[0]["data"], data)
        doc["sha256"] = "corrupt"
        self.assertEqual(await load_scene_references(database, bucket, "숲"), [])


if __name__ == "__main__":
    unittest.main()
