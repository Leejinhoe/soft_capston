import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
import main
from models import MediaGenerationWithStorySchema


class VideoReuseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.story_id = str(ObjectId())
        self.image_id = str(ObjectId())
        self.video_id = str(ObjectId())
        self.payload = MediaGenerationWithStorySchema(
            story_text='The hero walks to the castle.', character_key='male_01', include_video=True,
            scene_contract={'action': 'journey', 'character_key': 'male_01', 'participant_count': 1},
        )
        self.source = main.build_media_job_document(self.payload, story_id=self.story_id,
                                                    step_number=1, owner_user_id='owner')
        self.source.update({
            '_id': ObjectId(), 'status': 'completed', 'cache_key': 'key:revision',
            'video_reuse_worker_revision': 'revision',
            'video_reuse_environment': main.video_reuse_environment(),
            'video_reuse_worker_environment': main.video_reuse_environment(),
            'image_file_id': ObjectId(), 'video_file_id': ObjectId(self.video_id),
            'video_url': f'/api/media/videos/{self.video_id}', 'provider': 'local-composite',
            'result_metadata': {'video_status': 'completed', 'secondary_character_key': None},
            'result': {},
        })

    def test_exact_cache_key_includes_story_and_scene(self):
        first = main.build_media_job_cache_key(self.payload, story_id=self.story_id, step_number=1)
        different_story = main.build_media_job_cache_key(self.payload, story_id=str(ObjectId()), step_number=1)
        different_step = main.build_media_job_cache_key(self.payload, story_id=self.story_id, step_number=2)
        self.assertNotEqual(first, different_story)
        self.assertNotEqual(first, different_step)

    async def run_reuse(self, candidates, payload=None):
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=candidates)
        collection = SimpleNamespace(find=MagicMock(return_value=cursor),
                                     insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id=ObjectId())),
                                     update_one=AsyncMock())
        current = {'file_id': self.image_id, 'url': f'/api/media/images/{self.image_id}'}
        with (patch.object(main, 'media_jobs_collection', collection),
              patch.object(main, 'existing_scene_image', AsyncMock(return_value=current)),
              patch.object(main, 'cached_media_files_exist', AsyncMock(return_value=True)),
              patch.object(main, 'persist_scene_media', AsyncMock(return_value=True)) as persist):
            result = await main.reuse_matching_story_video(
                payload or self.payload, story_id=self.story_id, step_number=2,
                owner_user_id='owner', revision='revision', cache_key='new-key:revision')
        return result, collection, persist

    async def test_matching_video_keeps_target_image_and_new_job(self):
        result, collection, persist = await self.run_reuse([self.source])
        self.assertEqual(result['status'], 'completed')
        self.assertNotEqual(result['job_id'], str(self.source['_id']))
        self.assertEqual(result['result']['video_file_id'], self.video_id)
        self.assertEqual(result['result']['image_file_id'], self.image_id)
        self.assertTrue(result['result']['metadata']['video_reused'])
        self.assertEqual(persist.await_args.kwargs['expected_media_job_id'], result['job_id'])
        query = collection.find.call_args.args[0]
        self.assertEqual(query['owner_user_id'], 'owner')
        self.assertEqual(query['story_id'], ObjectId(self.story_id))

    async def test_old_worker_or_changed_text_is_never_reused(self):
        old = {**self.source, 'video_reuse_worker_revision': None}
        changed = {**self.source, 'story_text': 'Different scene', 'request': {**self.source['request'], 'story_text': 'Different scene'}}
        for candidate in (old, changed):
            result, collection, _ = await self.run_reuse([candidate])
            self.assertIsNone(result)
            collection.insert_one.assert_not_awaited()

    async def test_missing_video_file_is_not_reused(self):
        with patch.object(main, 'cached_media_files_exist', AsyncMock(return_value=False)):
            cursor = MagicMock()
            cursor.sort.return_value = cursor
            cursor.limit.return_value = cursor
            cursor.to_list = AsyncMock(return_value=[self.source])
            collection = SimpleNamespace(find=MagicMock(return_value=cursor), insert_one=AsyncMock())
            current = {'file_id': self.image_id, 'url': f'/api/media/images/{self.image_id}'}
            with (patch.object(main, 'media_jobs_collection', collection),
                  patch.object(main, 'existing_scene_image', AsyncMock(return_value=current))):
                result = await main.reuse_matching_story_video(
                    self.payload, story_id=self.story_id, step_number=2,
                    owner_user_id='owner', revision='revision', cache_key='key:revision')
        self.assertIsNone(result)
        collection.insert_one.assert_not_awaited()

    async def test_partner_scene_is_not_reused(self):
        payload = self.payload.model_copy(update={'scene_contract': self.payload.scene_contract.model_copy(update={'participant_count': 2})})
        result, collection, _ = await self.run_reuse([self.source], payload)
        self.assertIsNone(result)
        collection.find.assert_not_called()


if __name__ == '__main__':
    unittest.main()
