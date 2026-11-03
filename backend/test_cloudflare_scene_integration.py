import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import main


class StopBeforeUpload(BaseException):
    pass


class CloudflareSceneIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_scene(self, generator):
        upload = AsyncMock(side_effect=StopBeforeUpload)
        with ExitStack() as stack:
            for name, value in {
                "load_story_cast": [],
                "load_visual_context": {},
                "load_active_character_profile": {"character_key": "female_01", "name": "Mina"},
                "generate_composite_scene": {
                    "image_bytes": b"original", "character_bytes": b"reference", "content_type": "image/png",
                    "provider": "local-composite", "model": "compositor",
                },
            }.items():
                stack.enter_context(patch.object(main, name, AsyncMock(return_value=value)))
            stack.enter_context(patch.object(main, "select_background_asset", return_value={"key": "forest"}))
            stack.enter_context(patch.object(main, "select_character_asset", side_effect=lambda profile, *a, **kw: {"pose": "default"} if profile else None))
            stack.enter_context(patch.object(main, "space_character_enabled", return_value=False))
            stack.enter_context(patch.object(main, "sdxl_lora_enabled", return_value=False))
            stack.enter_context(patch.object(main, "cloudflare_character_enabled", return_value=True))
            stack.enter_context(patch.object(main, "generate_cloudflare_scene", generator))
            stack.enter_context(patch.object(main, "inspect_generated_media", return_value={"passed": True}))
            stack.enter_context(patch.object(main, "upload_generated_media_file", upload))
            with self.assertRaises(StopBeforeUpload):
                await main.generate_and_store_backend_media(
                    story_text="Mina opens a chest.", character_key="female_01", include_video=False,
                )
        return upload.await_args.kwargs

    async def test_generated_scene_is_uploaded_as_unverified(self):
        generate = AsyncMock(return_value=b"cloudflare-scene")
        saved = await self.run_scene(generate)
        generate.assert_awaited_once_with(b"reference", "Mina opens a chest.")
        self.assertEqual(saved["content"], b"cloudflare-scene")
        self.assertEqual(saved["provider"], "cloudflare_workers_ai")
        self.assertEqual(saved["extra_metadata"]["identity_verification"], "not_verified")
        self.assertIsNone(saved["extra_metadata"]["asset_fingerprint"])

    async def test_failure_saves_original_composite(self):
        saved = await self.run_scene(AsyncMock(side_effect=TimeoutError()))
        self.assertEqual(saved["content"], b"original")
        self.assertEqual(saved["provider"], "local-composite")
