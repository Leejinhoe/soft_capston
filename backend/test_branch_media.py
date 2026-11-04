import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("JWT_SECRET", "test-only-secret")
os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27017")

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import branching


class MediaHttpTests(unittest.TestCase):
    def test_video_and_image_reject_missing_token(self):
        app = FastAPI()
        app.include_router(branching.router)
        with TestClient(app) as client:
            for kind in ("image", "video"):
                response = client.get(f"/api/stories/{ObjectId()}/scenes/1/{kind}")
                self.assertEqual(response.status_code, 401)


class SceneImageTests(unittest.IsolatedAsyncioTestCase):
    def test_scene_prompts_share_style_without_inventing_direction(self):
        forest = branching.cloudflare_character.build_scene_prompt('숲에서 지도를 살핀다')
        castle = branching.cloudflare_character.build_scene_prompt('성을 향해 걸어간다', 'back')
        style = branching.cloudflare_character.STORYBOOK_STYLE
        self.assertIn(style, forest)
        self.assertIn(style, castle)
        self.assertIn('숲에서 지도를 살핀다', forest)
        self.assertNotIn('second image', forest.lower())
        self.assertIn('back view', castle)

    async def test_image_uses_previous_choice_and_direction_reference(self):
        doc = {"_id": ObjectId(), "user_id": "owner", "character_key": "female_01",
               "scenes": [{"text": "시작", "chosen": "성을 향해 걸어간다"}, {"text": "미나가 나아갔다"}]}
        bucket = MagicMock(upload_from_stream=AsyncMock(return_value=ObjectId()), delete=AsyncMock())
        collection = MagicMock(update_one=AsyncMock(return_value=MagicMock(matched_count=1)))
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)), \
             patch.object(branching, "stories_collection", collection), \
             patch.object(branching, "AsyncIOMotorGridFSBucket", return_value=bucket), \
             patch.object(branching.cloudflare_character, "enabled", return_value=True), \
             patch.object(branching.cloudflare_character, "generate_scene", AsyncMock(return_value=b"png")) as generate:
            await branching.create_scene_image(str(doc["_id"]), 2, {"user_id": "owner"})
        self.assertIn("성을 향해 걸어간다", generate.await_args.args[1])
        self.assertEqual(generate.await_args.kwargs["direction_view"], "back")

    def test_direction_reference_only_for_explicit_movement(self):
        toward = branching.cloudflare_character.infer_reference_direction('성을 향해 걸어간다')
        view, data = branching.cloudflare_character.directional_reference('female_01', toward)
        self.assertEqual(view, 'back')
        self.assertTrue(data)
        self.assertIsNone(branching.cloudflare_character.infer_reference_direction('성 앞에서 기다린다'))

    async def test_journey_uses_existing_scene_clips(self):
        video_id = ObjectId()
        doc = {"_id": ObjectId(), "user_id": "owner", "status": "completed",
               "scenes": [{"text": "one", "video_file_id": str(video_id)}, {"text": "two"}]}
        output_id = ObjectId()
        bucket = MagicMock(upload_from_stream=AsyncMock(return_value=output_id), delete=AsyncMock())
        collection = MagicMock(update_one=AsyncMock(return_value=MagicMock(matched_count=1)))
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)), \
             patch.object(branching, "get_scene_video", AsyncMock(return_value=MagicMock(body=b"clip"))) as load, \
             patch.object(branching, "stories_collection", collection), \
             patch.object(branching, "AsyncIOMotorGridFSBucket", return_value=bucket), \
             patch.object(branching, "assemble_scene_videos", return_value=b"result") as assemble:
            await branching.create_journey_video(str(doc["_id"]), {"user_id": "owner"})
        load.assert_awaited_once()
        assemble.assert_called_once_with([b"clip"])
        self.assertIn(str(output_id), collection.update_one.await_args.args[1]["$set"]["assembled_video_url"])

    async def test_journey_requires_at_least_one_clip(self):
        doc = {"status": "completed", "scenes": [{"text": "one"}]}
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)):
            with self.assertRaises(HTTPException) as caught:
                await branching.create_journey_video("story", {"user_id": "owner"})
        self.assertEqual(caught.exception.status_code, 409)

    async def test_video_uses_choice_that_led_to_scene_and_saved_image(self):
        doc = {"_id": ObjectId(), "user_id": "owner", "character_key": "female_01",
               "scenes": [{"text": "시작", "chosen": "문을 연다"},
                          {"text": "다음", "image_url": "/api/media/images/abc"}]}
        file_id = ObjectId()
        bucket = MagicMock(upload_from_stream=AsyncMock(return_value=file_id), delete=AsyncMock())
        collection = MagicMock(update_one=AsyncMock(return_value=MagicMock(matched_count=1)))
        image = MagicMock(body=b"image")
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)), \
             patch.object(branching, "get_scene_image", AsyncMock(return_value=image)), \
             patch.object(branching, "stories_collection", collection), \
             patch.object(branching, "AsyncIOMotorGridFSBucket", return_value=bucket), \
             patch.object(branching.hf_space_video, "enabled", return_value=True), \
             patch.object(branching.hf_space_video, "generate_scene_video",
                          AsyncMock(return_value={"video_bytes": b"video", "provider": "test"})) as generate:
            await branching.create_scene_video(str(doc["_id"]), 2, {"user_id": "owner"})
        generate.assert_awaited_once_with(b"image", "문을 연다")
        self.assertEqual(collection.update_one.await_args.args[1]["$set"]["scenes.1.video_file_id"], str(file_id))

    async def test_video_uses_file_referenced_by_owned_scene(self):
        video_id = ObjectId()
        doc = {"scenes": [{"video_url": f"/api/media/videos/{video_id}"}]}
        stream = MagicMock(length=4, read=AsyncMock(return_value=b"mp4!"))
        bucket = MagicMock(open_download_stream=AsyncMock(return_value=stream))
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)) as owned, \
             patch.object(branching, "AsyncIOMotorGridFSBucket", return_value=bucket):
            result = await branching.get_scene_video("story", 1, {"user_id": "owner"})
        owned.assert_awaited_once_with("story", "owner")
        bucket.open_download_stream.assert_awaited_once_with(video_id)
        self.assertEqual(result.body, b"mp4!")

    def test_selected_character_name_is_restored_in_story_prompt(self):
        setup = branching._setup({"topic": "마법의 숲", "genre": "판타지", "age": "7", "character_key": "female_01"})
        self.assertEqual(setup.character_name, "미나")
        from story_engine import opening_prompt
        self.assertIn("선택된 주인공 이름: 미나", opening_prompt(setup))

    async def test_invalid_character_does_not_generate_or_upload(self):
        doc = {"_id": ObjectId(), "user_id": "owner", "character_key": "../secret",
               "scenes": [{"text": "장면"}]}
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)), \
             patch.object(branching.cloudflare_character, "generate_scene", AsyncMock()) as generate:
            with self.assertRaises(HTTPException) as caught:
                await branching.create_scene_image(str(doc["_id"]), 1, {"user_id": "owner"})
        self.assertEqual(caught.exception.status_code, 400)
        generate.assert_not_awaited()

    async def test_creates_image_for_selected_character_and_scene(self):
        doc = {"_id": ObjectId(), "user_id": "owner", "character_key": "female_01",
               "scenes": [{"text": "숲을 걷는다"}]}
        file_id = ObjectId()
        bucket = MagicMock(upload_from_stream=AsyncMock(return_value=file_id), delete=AsyncMock())
        collection = MagicMock(update_one=AsyncMock(return_value=MagicMock(matched_count=1)))
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)), \
             patch.object(branching, "stories_collection", collection), \
             patch.object(branching, "AsyncIOMotorGridFSBucket", return_value=bucket), \
             patch.object(branching.cloudflare_character, "enabled", return_value=True), \
             patch.object(branching.cloudflare_character, "generate_scene", AsyncMock(return_value=b"png")) as generate:
            await branching.create_scene_image(str(doc["_id"]), 1, {"user_id": "owner"})
        self.assertEqual(generate.await_args.args[1], "숲을 걷는다")
        update = collection.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["scenes.0.image_file_id"], str(file_id))
        bucket.delete.assert_not_awaited()

    async def test_discards_only_new_file_on_concurrent_save(self):
        doc = {"_id": ObjectId(), "user_id": "owner", "character_key": "male_01",
               "scenes": [{"text": "장면"}]}
        file_id = ObjectId()
        bucket = MagicMock(upload_from_stream=AsyncMock(return_value=file_id), delete=AsyncMock())
        collection = MagicMock(update_one=AsyncMock(return_value=MagicMock(matched_count=0)))
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)), \
             patch.object(branching, "stories_collection", collection), \
             patch.object(branching, "AsyncIOMotorGridFSBucket", return_value=bucket), \
             patch.object(branching.cloudflare_character, "enabled", return_value=True), \
             patch.object(branching.cloudflare_character, "generate_scene", AsyncMock(return_value=b"png")):
            await branching.create_scene_image(str(doc["_id"]), 1, {"user_id": "owner"})
        bucket.delete.assert_awaited_once_with(file_id)

    async def test_concurrent_scene_updates_cause_retry_not_media_loss(self):
        original = [{"text": "start", "choices": ["go"], "chosen": None, "chosen_index": None}]
        doc = {"_id": ObjectId(), "user_id": "owner", "scenes": original}
        selected = [{**original[0], "chosen": "go", "chosen_index": 0}]
        collection = MagicMock(update_one=AsyncMock(return_value=MagicMock(matched_count=0)))
        with patch.object(branching, "stories_collection", collection):
            with self.assertRaises(HTTPException) as caught:
                await branching._save_step(doc, selected, {"text": "next"}, {}, {"choice": "go"})
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(collection.update_one.await_args.args[0]["scenes"], original)

    async def test_loads_only_image_referenced_by_owned_story(self):
        image_id = ObjectId()
        doc = {"scenes": [{"image_url": f"/api/media/images/{image_id}"}]}
        stream = MagicMock(length=3, read=AsyncMock(return_value=b"png"))
        bucket = MagicMock(open_download_stream=AsyncMock(return_value=stream))
        with patch.object(branching, "_my_story", AsyncMock(return_value=doc)) as owned, \
             patch.object(branching, "AsyncIOMotorGridFSBucket", return_value=bucket):
            result = await branching.get_scene_image("story", 1, {"user_id": "owner"})
        owned.assert_awaited_once_with("story", "owner")
        bucket.open_download_stream.assert_awaited_once_with(image_id)
        self.assertEqual(result.body, b"png")
        self.assertEqual(result.headers["cache-control"], "private, no-store")

    async def test_missing_scene_is_not_read(self):
        with patch.object(branching, "_my_story", AsyncMock(return_value={"scenes": []})):
            with self.assertRaises(HTTPException) as caught:
                await branching.get_scene_image("story", 1, {"user_id": "owner"})
        self.assertEqual(caught.exception.status_code, 404)

    async def test_unowned_story_is_rejected(self):
        with patch.object(branching, "_my_story", AsyncMock(side_effect=HTTPException(404))):
            with patch.object(branching, "AsyncIOMotorGridFSBucket") as bucket:
                with self.assertRaises(HTTPException):
                    await branching.get_scene_image("story", 1, {"user_id": "other"})
                bucket.assert_not_called()


if __name__ == "__main__":
    unittest.main()
