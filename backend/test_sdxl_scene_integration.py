import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from bson import ObjectId

import main
from models import MediaGenerationWithStorySchema


class StopBeforeUpload(BaseException):
    pass


class SdxlSceneIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_video_space_uses_saved_scene_image_and_skips_asset_requirement(self):
        story_id, image_id = str(ObjectId()), str(ObjectId())
        remote = AsyncMock(return_value={'video_bytes': b'video', 'content_type': 'video/mp4',
                                         'provider': 'huggingface-space-i2v', 'model': 'ltx', 'parameters': {}})
        upload = AsyncMock(side_effect=StopBeforeUpload)
        with ExitStack() as stack:
            for name, value in {
                'load_story_cast': [{'character_key': 'male_01', 'role': 'hero'}],
                'load_visual_context': {},
                'load_active_character_profile': {'character_key': 'male_01', 'name': 'Hero'},
                'generate_composite_scene': {'image_bytes': b'different-composite', 'content_type': 'image/png',
                                             'provider': 'local-composite', 'model': 'compositor'},
                'existing_scene_image': {'file_id': image_id, 'url': f'/api/media/images/{image_id}'},
                'download_gridfs_file': b'saved-scene',
            }.items():
                stack.enter_context(patch.object(main, name, AsyncMock(return_value=value)))
            stack.enter_context(patch.object(main, 'video_space_enabled', return_value=True))
            stack.enter_context(patch.object(main, 'generate_space_video', remote))
            stack.enter_context(patch.object(main, 'select_background_asset', return_value={'key': 'castle'}))
            stack.enter_context(patch.object(main, 'select_character_asset',
                                side_effect=lambda profile, *a, **kw: {'pose': 'default'} if profile else None))
            stack.enter_context(patch.object(main, 'space_character_enabled', return_value=False))
            stack.enter_context(patch.object(main, 'sdxl_lora_enabled', return_value=False))
            stack.enter_context(patch.object(main, 'inspect_generated_media', return_value={'passed': True}))
            asset_check = stack.enter_context(patch.object(main, 'missing_motion_asset_request'))
            stack.enter_context(patch.object(main, 'upload_generated_media_file', upload))
            with self.assertRaises(StopBeforeUpload):
                await main.generate_and_store_backend_media(
                    story_text='The hero walks toward the castle.', story_id=story_id,
                    step_number=1, character_key='male_01', include_video=True,
                )
        self.assertEqual(remote.await_args.args[0], b'saved-scene')
        asset_check.assert_not_called()
        self.assertEqual(upload.await_args.kwargs['media_kind'], 'video')

    async def test_cached_video_uses_current_scene_image(self):
        story_id, old_image, current_image, video_id = (str(ObjectId()) for _ in range(4))
        cached = {
            '_id': ObjectId(), 'status': 'completed', 'image_file_id': ObjectId(old_image),
            'image_url': f'/api/media/images/{old_image}', 'video_file_id': ObjectId(video_id),
            'video_url': f'/api/media/videos/{video_id}', 'include_video': True,
            'video_reuse_worker_revision': 'revision',
            'video_reuse_worker_environment': main.video_reuse_environment(),
        }
        collection = SimpleNamespace(find_one=AsyncMock(side_effect=[None, cached]))
        current_url = f'/api/media/images/{current_image}'
        payload = MediaGenerationWithStorySchema(story_text='A scene', include_video=True)
        with (
            patch.object(main, 'media_jobs_collection', collection),
            patch.object(main, 'render_revision', return_value='revision'),
            patch.object(main, 'cloudflare_character_enabled', return_value=False),
            patch.object(main, 'cached_media_files_exist', AsyncMock(return_value=True)),
            patch.object(main, 'existing_scene_image', AsyncMock(return_value={'file_id': current_image, 'url': current_url})),
            patch.object(main, 'persist_scene_media', AsyncMock(return_value=True)) as persist,
        ):
            result = await main.enqueue_media_job(payload, story_id=story_id, step_number=1, owner_user_id='test-owner')
        self.assertEqual(result['result']['image_url'], current_url)
        self.assertEqual(persist.await_args.kwargs['image_url'], current_url)

    async def test_video_generation_does_not_replace_existing_scene_image(self):
        story_id, image_id = str(ObjectId()), str(ObjectId())
        image_url = f'/api/media/images/{image_id}'
        upload = AsyncMock(side_effect=StopBeforeUpload)
        with ExitStack() as stack:
            for name, value in {
                'load_story_cast': [{'character_key': 'male_01', 'role': 'hero'}],
                'load_visual_context': {},
                'load_active_character_profile': {'character_key': 'male_01', 'name': 'Hero'},
                'generate_composite_scene': {'image_bytes': b'composite', 'content_type': 'image/png',
                                             'provider': 'local-composite', 'model': 'compositor'},
                'existing_scene_image': {'file_id': image_id, 'url': image_url},
                'generate_hf_fairytale_video': {'video_bytes': b'video', 'content_type': 'video/mp4',
                                                'provider': 'local', 'model': 'test', 'parameters': {}},
            }.items():
                stack.enter_context(patch.object(main, name, AsyncMock(return_value=value)))
            stack.enter_context(patch.object(main, 'select_background_asset', return_value={'key': 'castle'}))
            stack.enter_context(patch.object(main, 'select_character_asset',
                                side_effect=lambda profile, *a, **kw: {'pose': 'default'} if profile else None))
            stack.enter_context(patch.object(main, 'space_character_enabled', return_value=False))
            stack.enter_context(patch.object(main, 'sdxl_lora_enabled', return_value=True))
            stack.enter_context(patch.object(main, 'video_space_enabled', return_value=False))
            stack.enter_context(patch.object(main, 'inspect_generated_media', return_value={'passed': True}))
            stack.enter_context(patch.object(main, 'missing_motion_asset_request', return_value=None))
            stack.enter_context(patch.object(main, 'upload_generated_media_file', upload))
            with self.assertRaises(StopBeforeUpload):
                await main.generate_and_store_backend_media(
                    story_text='The hero walks toward the castle.', story_id=story_id,
                    step_number=1, character_key='male_01', include_video=True,
                )
        upload.assert_awaited_once()
        self.assertEqual(upload.await_args.kwargs['media_kind'], 'video')

    async def test_existing_story_image_is_found_by_step_and_url(self):
        story_id, image_id = str(ObjectId()), str(ObjectId())
        collection = SimpleNamespace(find_one=AsyncMock(return_value={'scenes': [
            {'step_number': 1, 'image_url': f'/api/media/images/{image_id}'},
            {'step_number': 2, 'image_url': '/other'},
        ]}))
        with patch.object(main, 'stories_collection', collection):
            existing = await main.existing_scene_image(story_id, 1)
            self.assertEqual(existing, {'file_id': image_id, 'url': f'/api/media/images/{image_id}'})
            self.assertIsNone(await main.existing_scene_image(story_id, 3))

    async def run_scene(self, generator, *, allowed=True):
        upload = AsyncMock(side_effect=StopBeforeUpload)
        with ExitStack() as stack:
            for name, value in {
                'load_story_cast': [],
                'load_visual_context': {},
                'load_active_character_profile': {'character_key': 'male_01', 'name': 'Hero'},
                'generate_composite_scene': {
                    'image_bytes': b'original', 'content_type': 'image/png',
                    'provider': 'local-composite', 'model': 'compositor',
                    'background_key': 'castle', 'background_source': 'bundled_asset',
                },
            }.items():
                stack.enter_context(patch.object(main, name, AsyncMock(return_value=value)))
            stack.enter_context(patch.object(main, 'select_background_asset', return_value={'key': 'castle'}))
            stack.enter_context(patch.object(
                main, 'select_character_asset',
                side_effect=lambda profile, *args, **kwargs: {'pose': 'default'} if profile else None,
            ))
            stack.enter_context(patch.object(main, 'space_character_enabled', return_value=False))
            stack.enter_context(patch.object(main, 'sdxl_lora_enabled', return_value=True))
            stack.enter_context(patch.object(main, 'generate_character_sdxl_lora', generator))
            stack.enter_context(patch.object(main, 'inspect_generated_media', return_value={'passed': True}))
            stack.enter_context(patch.object(main, 'upload_generated_media_file', upload))
            stack.enter_context(patch.dict('os.environ', {'HF_SDXL_LORA_ALLOW_UNVERIFIED': str(allowed).lower()}))
            with self.assertRaises(StopBeforeUpload):
                await main.generate_and_store_backend_media(
                    story_text='The hero walks to the castle.', character_key='male_01',
                    include_video=False,
                )
        return upload.await_args.kwargs

    async def test_success_stores_sdxl_output_as_unverified(self):
        generator = AsyncMock(return_value=b'new-scene')
        saved = await self.run_scene(generator)
        generator.assert_awaited_once()
        self.assertEqual(saved['content'], b'new-scene')
        self.assertEqual(saved['provider'], 'huggingface_space')
        self.assertEqual(saved['extra_metadata']['identity_verification'], 'not_verified')
        self.assertIsNone(saved['extra_metadata']['asset_fingerprint'])

    async def test_provider_error_preserves_composite(self):
        generator = AsyncMock(side_effect=TimeoutError())
        saved = await self.run_scene(generator)
        generator.assert_awaited_once()
        self.assertEqual(saved['content'], b'original')
        self.assertEqual(saved['provider'], 'local-composite')

    async def test_unverified_output_needs_explicit_opt_in(self):
        generator = AsyncMock(return_value=b'new-scene')
        saved = await self.run_scene(generator, allowed=False)
        generator.assert_not_awaited()
        self.assertEqual(saved['content'], b'original')
