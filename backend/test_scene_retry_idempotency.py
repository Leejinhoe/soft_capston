import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException

import main
from models import SceneSchema


class SceneRetryTests(unittest.IsolatedAsyncioTestCase):
    def test_scene_response_keeps_video_request_kind(self):
        serialized = main.serialize_scene({
            'step_number': 1, 'content': 'scene', 'media_requested_video': True,
        })
        self.assertTrue(serialized['media_requested_video'])

    async def test_repeat_is_not_pushed_again(self):
        story_id = str(ObjectId())
        scene = SceneSchema(step_number=2, story_text='next', choice_made='choice')
        collection = SimpleNamespace(
            update_one=AsyncMock(return_value=SimpleNamespace(modified_count=0)),
            find_one=AsyncMock(return_value={'scenes': [
                {'step_number': 2, 'content': 'next', 'user_choice': 'choice'}
            ]}),
        )
        with patch.object(main, 'stories_collection', collection), patch.object(
            main, 'require_story_owner', new=AsyncMock()
        ):
            result = await main.push_scene(story_id, scene, None)
        self.assertEqual(result['message'], 'Scene already saved.')
        query = collection.update_one.call_args.args[0]
        self.assertEqual(query['scenes']['$not']['$elemMatch']['step_number'], 2)

    async def test_repeat_backfills_missing_image_url(self):
        story_id = str(ObjectId())
        scene = SceneSchema(
            step_number=2,
            story_text='next',
            choice_made='choice',
            image_url='/api/media/images/0123456789abcdef01234567',
        )
        collection = SimpleNamespace(
            update_one=AsyncMock(return_value=SimpleNamespace(modified_count=0)),
            find_one=AsyncMock(return_value={'scenes': [
                {'step_number': 2, 'content': 'next', 'user_choice': 'choice', 'image_url': None}
            ]}),
        )
        with patch.object(main, 'stories_collection', collection), patch.object(
            main, 'require_story_owner', new=AsyncMock()
        ):
            result = await main.push_scene(story_id, scene, None)
        self.assertEqual(result['message'], 'Scene already saved.')
        self.assertEqual(collection.update_one.await_count, 2)
        backfill_update = collection.update_one.await_args_list[1].args[1]
        self.assertEqual(
            backfill_update['$set']['scenes.$.image_url'],
            '/api/media/images/0123456789abcdef01234567',
        )

    async def test_conflicting_step_is_rejected(self):
        story_id = str(ObjectId())
        scene = SceneSchema(step_number=2, story_text='new', choice_made='choice')
        collection = SimpleNamespace(
            update_one=AsyncMock(return_value=SimpleNamespace(modified_count=0)),
            find_one=AsyncMock(return_value={'scenes': [
                {'step_number': 2, 'content': 'different', 'user_choice': 'choice'}
            ]}),
        )
        with patch.object(main, 'stories_collection', collection), patch.object(
            main, 'require_story_owner', new=AsyncMock()
        ):
            with self.assertRaises(HTTPException) as error:
                await main.push_scene(story_id, scene, None)
        self.assertEqual(error.exception.status_code, 409)


if __name__ == '__main__':
    unittest.main()
