import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId

import main
from models import StoryCharacterChatSchema, StoryCharacterDiscoverySchema


class NoticesAndCharacterChatTests(unittest.IsolatedAsyncioTestCase):
    def test_notice_serialization_keeps_delivery_state(self):
        notice_id = ObjectId()
        serialized = main.serialize_notice(
            {
                "_id": notice_id,
                "title": "업데이트 안내",
                "content": "새 기능이 추가되었습니다.",
                "is_pinned": True,
                "email_requested": True,
                "email_delivery_status": "completed_with_failures",
                "email_recipient_count": 3,
                "email_sent_count": 2,
                "email_failed_count": 1,
                "email_delivery_error": "one recipient failed",
            },
            include_delivery_error=True,
        )

        self.assertEqual(serialized["id"], str(notice_id))
        self.assertTrue(serialized["is_pinned"])
        self.assertEqual(serialized["email_sent_count"], 2)
        self.assertEqual(serialized["email_delivery_error"], "one recipient failed")

    def test_legacy_character_block_excludes_non_character_items(self):
        payload = "[등장인물] {'hero': \"꼬마 용사 '용감이'\", 'key_item': \"희망의 열쇠\"}"

        characters = main._parse_legacy_story_characters(payload)

        self.assertEqual(len(characters), 1)
        self.assertEqual(characters[0]["name"], "용감이")
        self.assertEqual(characters[0]["role"], "hero")

    async def test_story_character_discovery_prefers_persisted_cast(self):
        persisted_cast = [
            {
                "role": "hero",
                "name": "용감이",
                "fixed_description": "용감하고 다정한 아이",
            }
        ]
        payload = StoryCharacterDiscoverySchema(
            story_id="story-1",
            story_text="[등장인물] {'hero': \"다른 이름\"}",
        )

        with patch.object(
            main,
            "load_story_cast",
            new=AsyncMock(return_value=persisted_cast),
        ):
            characters = await main.resolve_chat_characters(payload)

        self.assertEqual(characters[0]["name"], "용감이")
        self.assertEqual(characters[0]["role"], "hero")

    async def test_character_chat_returns_suggestions_and_persists_history(self):
        messages_collection = SimpleNamespace(insert_many=AsyncMock())
        payload = StoryCharacterChatSchema(
            story_id="story-1",
            character={
                "name": "용감이",
                "personality": "용감하고 다정한 마음",
            },
            messages=[{"role": "user", "content": "무서웠어"}],
            user_message="왜 끝까지 갔어?",
        )

        with patch.object(main, "messages_collection", messages_collection):
            result = await main.chat_with_story_character(
                payload,
                SimpleNamespace(headers={}),
            )

        self.assertIn("reply", result)
        self.assertEqual(len(result["suggested_replies"]), 3)
        messages_collection.insert_many.assert_awaited_once()
        saved_messages = messages_collection.insert_many.await_args.args[0]
        self.assertEqual(saved_messages[-1]["role"], "character")

    def test_malformed_stored_email_does_not_abort_notice_delivery_list(self):
        self.assertEqual(main.safe_normalize_email("valid@example.com"), "valid@example.com")
        self.assertIsNone(main.safe_normalize_email("not-an-email"))


if __name__ == "__main__":
    unittest.main()
