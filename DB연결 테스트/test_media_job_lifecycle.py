import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException

import main
from models import MediaGenerationWithStorySchema


class MediaJobDocumentTests(unittest.TestCase):
    def test_job_records_its_owner(self):
        payload = MediaGenerationWithStorySchema(
            story_text='A child opens a glowing forest door.',
            include_video=True,
        )

        job = main.build_media_job_document(
            payload,
            story_id=None,
            step_number=None,
            owner_user_id='user-123',
        )

        self.assertEqual(job['owner_user_id'], 'user-123')
        self.assertEqual(job['status'], 'pending')

    def test_story_scene_job_has_a_unique_active_key(self):
        story_id = str(ObjectId())
        job = main.build_media_job_document(
            MediaGenerationWithStorySchema(story_text='A scene'),
            story_id=story_id,
            step_number=2,
            owner_user_id='user-123',
        )

        self.assertEqual(job['active_key'], f'user-123:{story_id}:2')

    def test_scene_serialization_keeps_retry_state(self):
        scene = main.serialize_scene(
            {
                'step_number': 2,
                'content': 'A scene',
                'image_url': '/api/media/images/image-1',
                'media_job_id': 'job-1',
                'media_status': 'partial',
                'media_error': 'video failed',
            }
        )

        self.assertEqual(scene['media_status'], 'partial')
        self.assertEqual(scene['media_error'], 'video failed')


class MediaJobLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_story_media_rejects_character_outside_saved_cast(self):
        with patch.object(
            main,
            'load_story_cast',
            new=AsyncMock(
                return_value=[{'role': 'hero', 'character_key': 'female_01'}]
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await main.ensure_story_character_profile(
                    str(ObjectId()),
                    'male_08',
                )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_duplicate_story_scene_job_reuses_the_active_job(self):
        story_id = str(ObjectId())
        existing = main.build_media_job_document(
            MediaGenerationWithStorySchema(story_text='A scene'),
            story_id=story_id,
            step_number=1,
            owner_user_id='user-dedup',
        )
        existing['_id'] = ObjectId()
        collection = SimpleNamespace(
            find_one=AsyncMock(return_value=existing),
            count_documents=AsyncMock(),
            insert_one=AsyncMock(),
        )

        with (
            patch.object(main, 'media_jobs_collection', collection),
            patch.object(main, 'persist_scene_media', new=AsyncMock(return_value=True)),
        ):
            result = await main.enqueue_media_job(
                MediaGenerationWithStorySchema(story_text='A scene'),
                story_id=story_id,
                step_number=1,
                owner_user_id='user-dedup',
            )

        self.assertEqual(result['job_id'], str(existing['_id']))
        collection.count_documents.assert_not_awaited()
        collection.insert_one.assert_not_awaited()

    async def test_duplicate_story_scene_job_rejects_different_options(self):
        story_id = str(ObjectId())
        existing = main.build_media_job_document(
            MediaGenerationWithStorySchema(
                story_text='A scene',
                include_video=False,
            ),
            story_id=story_id,
            step_number=1,
            owner_user_id='user-dedup-options',
        )
        existing['_id'] = ObjectId()
        collection = SimpleNamespace(
            find_one=AsyncMock(return_value=existing),
            count_documents=AsyncMock(),
            insert_one=AsyncMock(),
        )

        with patch.object(main, 'media_jobs_collection', collection):
            with self.assertRaises(HTTPException) as raised:
                await main.enqueue_media_job(
                    MediaGenerationWithStorySchema(
                        story_text='A scene',
                        include_video=True,
                    ),
                    story_id=story_id,
                    step_number=1,
                    owner_user_id='user-dedup-options',
                )

        self.assertEqual(raised.exception.status_code, 409)
        collection.count_documents.assert_not_awaited()
        collection.insert_one.assert_not_awaited()

    async def test_scene_update_requires_the_current_media_job(self):
        update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
        with patch.object(
            main,
            'stories_collection',
            SimpleNamespace(update_one=update_one),
        ):
            saved = await main.persist_scene_media(
                story_id=str(ObjectId()),
                step_number=3,
                image_url='/api/media/images/image-1',
                media_job_id='job-new',
                media_status='completed',
                expected_media_job_id='job-new',
            )

        self.assertTrue(saved)
        query = update_one.await_args.args[0]
        self.assertEqual(
            query['scenes']['$elemMatch'],
            {'step_number': 3, 'media_job_id': 'job-new'},
        )

    async def test_video_failure_is_saved_as_partial_when_image_succeeds(self):
        job_id = ObjectId()
        image_file_id = ObjectId()
        job = {
            '_id': job_id,
            'owner_user_id': 'user-123',
            'story_text': 'A child opens a glowing forest door.',
            'include_video': True,
            'request': {'include_video': True},
        }
        generated = {
            'image_file_id': str(image_file_id),
            'video_file_id': None,
            'image_url': f'/api/media/images/{image_file_id}',
            'video_url': None,
            'provider': 'huggingface',
            'metadata': {
                'video_status': 'failed',
                'video_error': 'video provider unavailable',
            },
            'result': {'image_file_id': str(image_file_id)},
            'scene_saved': False,
        }
        update_one = AsyncMock(
            return_value=SimpleNamespace(matched_count=1),
        )

        with (
            patch.object(
                main,
                'generate_and_store_backend_media',
                new=AsyncMock(return_value=generated),
            ),
            patch.object(main, 'heartbeat_media_job', new=AsyncMock()),
            patch.object(
                main,
                'media_jobs_collection',
                SimpleNamespace(update_one=update_one),
            ),
        ):
            await main.complete_media_job_with_backend_provider(job)

        query, update = update_one.await_args.args
        self.assertEqual(query['status'], 'running')
        self.assertEqual(update['$set']['status'], 'partial')
        self.assertEqual(
            update['$set']['error'],
            'video provider unavailable',
        )
        self.assertEqual(update['$unset'], {'active_key': ''})


if __name__ == '__main__':
    unittest.main()
