import copy
import json
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException

import main
from story_cast import (
    build_story_cast,
    normalize_story_characters,
    select_story_cast_member,
)


CHARACTERS_JSON = """
{
  "hero": "꼬마 용사 '용감이'",
  "target": "용에게 납치된 '순수한 공주 미란'",
  "antagonist": "냉혹하지만 과거에는 친구였던 '용의 왕 다크론'",
  "companion": "지혜로운 숲의 요정 '루나'",
  "guide": "오래된 지도를 가진 '노인 나무꾼'",
  "key_item": "미란을 지키는 마법의 열쇠 '희망의 열쇠'"
}
"""


def _profile(character_key, name, genres, image_file_id):
    return {
        "character_key": character_key,
        "name": name,
        "description": f"fixed face profile for {name}",
        "style_prompt": "consistent children's storybook character",
        "genres": genres,
        "active": True,
        "assets": [
            {
                "pose": "default",
                "emotion": "neutral",
                "image_file_id": image_file_id,
                "image_url": f"/api/media/images/{image_file_id}",
                "tags": genres,
            }
        ],
    }


PROFILES = [
    _profile("face_hero_01", "Hero Face", ["fantasy"], "hero-face-file"),
    _profile("face_target_01", "Target Face", ["romance"], "target-face-file"),
    _profile("face_villain_01", "Villain Face", ["mystery"], "villain-face-file"),
    _profile("face_companion_01", "Companion Face", ["nature"], "companion-face-file"),
    _profile("face_guide_01", "Guide Face", ["adventure"], "guide-face-file"),
]


class FakeStoriesCollection:
    """Minimal isolated story store that models the MongoDB persistence boundary."""

    def __init__(self):
        self._documents = {}

    def save_locked_cast(self, story_id, characters, story_cast):
        self._documents[story_id] = copy.deepcopy(
            {
                "_id": story_id,
                "characters": characters,
                "story_cast": story_cast,
                "character_identity_locked": True,
            }
        )

    def load_cast_member(self, story_id, story_text):
        story = self._documents.get(story_id)
        return select_story_cast_member(
            (story or {}).get("story_cast"),
            story_text,
        )

    def find_story(self, story_id):
        return copy.deepcopy(self._documents.get(story_id))


class FakeAsyncCursor:
    def __init__(self, documents):
        self._documents = documents

    async def to_list(self, length):
        return copy.deepcopy(self._documents[:length])


class FakeCharacterProfilesCollection:
    def __init__(self, profiles):
        self._profiles = profiles
        self.find_queries = []

    def find(self, query):
        self.find_queries.append(copy.deepcopy(query))
        return FakeAsyncCursor(self._profiles)


class FakeMainStoriesCollection:
    """Async fake for the exact Motor calls made by main story-cast functions."""

    def __init__(self, story):
        self.story = copy.deepcopy(story)
        self.find_queries = []
        self.update_calls = []

    async def find_one(self, query, projection=None):
        self.find_queries.append(
            (copy.deepcopy(query), copy.deepcopy(projection))
        )
        if query.get("_id") != self.story.get("_id"):
            return None
        if projection == {"story_cast": 1}:
            return {"story_cast": copy.deepcopy(self.story.get("story_cast"))}
        return copy.deepcopy(self.story)

    async def update_one(self, query, update):
        self.update_calls.append(
            (copy.deepcopy(query), copy.deepcopy(update))
        )
        if query.get("_id") == self.story.get("_id"):
            self.story.update(copy.deepcopy(update.get("$set", {})))
        return object()


class StoryCharacterIdentityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stories = FakeStoriesCollection()
        self.story_id = "isolated-story-001"

        parsed_characters = json.loads(CHARACTERS_JSON)
        characters = normalize_story_characters(parsed_characters)
        story_cast = build_story_cast(
            characters,
            PROFILES,
            genre="fantasy",
        )
        self.stories.save_locked_cast(self.story_id, characters, story_cast)

    def test_character_identity_remains_locked_across_story_scenes(self):
        saved_story = self.stories.find_story(self.story_id)
        cast_by_role = {
            member["role"]: member for member in saved_story["story_cast"]
        }

        first_hero_scene = self.stories.load_cast_member(
            self.story_id,
            "용감이는 빛나는 숲의 문 앞에서 검을 들었다.",
        )
        second_hero_scene = self.stories.load_cast_member(
            self.story_id,
            "긴 여행 끝에 용감이가 다크론의 성에 도착했다.",
        )
        companion_scene = self.stories.load_cast_member(
            self.story_id,
            "루나는 반짝이는 날개로 어두운 숲길을 밝혔다.",
        )
        target_scene = self.stories.load_cast_member(
            self.story_id,
            "순수한 공주 미란은 높은 탑에서 희망의 노래를 불렀다.",
        )

        self.assertTrue(saved_story["character_identity_locked"])
        self.assertEqual(
            first_hero_scene["character_key"],
            cast_by_role["hero"]["character_key"],
        )
        self.assertEqual(
            second_hero_scene["character_key"],
            first_hero_scene["character_key"],
        )
        self.assertEqual(
            second_hero_scene["face_asset"],
            first_hero_scene["face_asset"],
        )
        self.assertEqual(
            companion_scene["character_key"],
            cast_by_role["companion"]["character_key"],
        )
        self.assertEqual(
            target_scene["character_key"],
            cast_by_role["target"]["character_key"],
        )
        self.assertNotEqual(
            companion_scene["character_key"],
            first_hero_scene["character_key"],
        )
        self.assertNotEqual(
            target_scene["character_key"],
            first_hero_scene["character_key"],
        )

    def test_all_character_names_select_their_persisted_role_profile(self):
        saved_story = self.stories.find_story(self.story_id)
        scenes_by_role = {
            "hero": "용감이가 먼저 앞으로 나섰다.",
            "target": "순수한 공주 미란이 탑의 창문을 열었다.",
            "antagonist": "용의 왕 다크론은 왕좌에서 천천히 일어났다.",
            "companion": "루나가 숲의 지혜를 들려주었다.",
            "guide": "노인 나무꾼은 오래된 지도를 펼쳤다.",
        }

        for member in saved_story["story_cast"]:
            with self.subTest(role=member["role"]):
                selected = self.stories.load_cast_member(
                    self.story_id,
                    scenes_by_role[member["role"]],
                )
                self.assertEqual(selected["role"], member["role"])
                self.assertEqual(
                    selected["character_key"],
                    member["character_key"],
                )
                self.assertEqual(
                    selected["face_asset"],
                    member["face_asset"],
                )

    def test_key_item_is_saved_as_story_data_but_never_becomes_a_face(self):
        saved_story = self.stories.find_story(self.story_id)

        self.assertIn("key_item", saved_story["characters"])
        self.assertEqual(
            saved_story["characters"]["key_item"],
            "미란을 지키는 마법의 열쇠 '희망의 열쇠'",
        )
        self.assertNotIn(
            "key_item",
            {member["role"] for member in saved_story["story_cast"]},
        )
        self.assertNotIn(
            "희망의 열쇠",
            {member["name"] for member in saved_story["story_cast"]},
        )

    def test_rebuilding_from_same_saved_json_is_deterministic(self):
        saved_story = self.stories.find_story(self.story_id)
        rebuilt_cast = build_story_cast(
            saved_story["characters"],
            list(reversed(PROFILES)),
            genre="fantasy",
        )

        self.assertEqual(rebuilt_cast, saved_story["story_cast"])


class MainStoryCharacterIdentityAsyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.story_object_id = ObjectId()
        self.story_id = str(self.story_object_id)
        self.owner_id = str(ObjectId())
        self.characters = {
            "hero": "Brave child 'Arin'",
            "antagonist": "Dragon king 'Darkron'",
            "companion": "Forest fairy 'Luna'",
            "key_item": "Magic key 'Hope Key'",
        }
        self.story = {
            "_id": self.story_object_id,
            "user_id": self.owner_id,
            "genre": "fantasy",
            "story_cast": [],
        }
        self.stories = FakeMainStoriesCollection(self.story)
        self.profiles = FakeCharacterProfilesCollection(PROFILES)

    def _request(self, user_id=None):
        return SimpleNamespace(
            state=SimpleNamespace(
                auth={"uid": user_id or self.owner_id}
            )
        )

    async def test_legacy_story_without_cast_is_migrated_on_first_use(self):
        with (
            patch.object(main, "stories_collection", self.stories),
            patch.object(
                main,
                "character_profiles_collection",
                self.profiles,
            ),
        ):
            migrated_cast = await main.load_story_cast(self.story_id)

        self.assertEqual(len(migrated_cast), 1)
        self.assertEqual(migrated_cast[0]["role"], "hero")
        self.assertTrue(migrated_cast[0]["character_key"])
        saved_fields = self.stories.update_calls[0][1]["$set"]
        self.assertEqual(saved_fields["characters"], {"hero": "Legacy story hero"})
        self.assertTrue(saved_fields["character_identity_locked"])
        self.assertEqual(saved_fields["schema_version"], 2)

    async def test_main_save_and_load_lock_real_function_flow(self):
        payload = main.StoryCharactersSchema(
            characters=self.characters,
            user_id=self.owner_id,
        )

        with (
            patch.object(main, "stories_collection", self.stories),
            patch.object(
                main,
                "character_profiles_collection",
                self.profiles,
            ),
        ):
            response = await main.save_story_characters(
                self.story_id,
                payload,
                self._request(),
            )
            first_scene_member = await main.load_story_cast_member(
                self.story_id,
                "Arin entered the castle.",
            )
            later_scene_member = await main.load_story_cast_member(
                self.story_id,
                "Arin faced the final gate.",
            )
            antagonist_member = await main.load_story_cast_member(
                self.story_id,
                "Darkron raised his hand.",
            )

        self.assertTrue(response["character_identity_locked"])
        self.assertEqual(response["story_id"], self.story_id)
        self.assertNotIn(
            "key_item",
            {member["role"] for member in response["story_cast"]},
        )
        self.assertEqual(
            self.profiles.find_queries,
            [{"active": True, "assets.0": {"$exists": True}}],
        )
        self.assertEqual(len(self.stories.update_calls), 1)

        update_filter, update_document = self.stories.update_calls[0]
        self.assertEqual(update_filter, {"_id": self.story_object_id})
        self.assertEqual(set(update_document), {"$set"})
        saved_fields = update_document["$set"]
        self.assertEqual(
            set(saved_fields),
            {
                "characters",
                "character_overrides",
                "story_cast",
                "character_identity_locked",
                "updated_at",
            },
        )
        self.assertTrue(saved_fields["character_identity_locked"])
        self.assertEqual(saved_fields["characters"], response["characters"])
        self.assertEqual(saved_fields["character_overrides"], {})
        self.assertEqual(saved_fields["story_cast"], response["story_cast"])
        self.assertIsInstance(saved_fields["updated_at"], datetime)
        self.assertTrue(self.stories.story["character_identity_locked"])

        self.assertEqual(
            first_scene_member["character_key"],
            later_scene_member["character_key"],
        )
        self.assertEqual(
            first_scene_member["face_asset"],
            later_scene_member["face_asset"],
        )
        self.assertNotEqual(
            antagonist_member["character_key"],
            first_scene_member["character_key"],
        )

    async def test_main_save_honors_selected_hero_profile(self):
        payload = main.StoryCharactersSchema(
            characters=self.characters,
            character_overrides={"hero": "face_target_01"},
            user_id=self.owner_id,
        )

        with (
            patch.object(main, "stories_collection", self.stories),
            patch.object(
                main,
                "character_profiles_collection",
                self.profiles,
            ),
        ):
            response = await main.save_story_characters(
                self.story_id,
                payload,
                self._request(),
            )

        hero = next(
            member for member in response["story_cast"] if member["role"] == "hero"
        )
        self.assertEqual(hero["character_key"], "face_target_01")
        self.assertEqual(hero["selection_source"], "user")
        self.assertEqual(
            self.stories.story["character_overrides"],
            {"hero": "face_target_01"},
        )

    async def test_main_save_rejects_invalid_object_id_without_db_call(self):
        payload = main.StoryCharactersSchema(
            characters=self.characters,
            user_id=self.owner_id,
        )

        with patch.object(main, "stories_collection", self.stories):
            with self.assertRaises(HTTPException) as raised:
                await main.save_story_characters(
                    "not-an-object-id",
                    payload,
                    self._request(),
                )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(self.stories.find_queries, [])
        self.assertEqual(self.stories.update_calls, [])

    async def test_main_save_rejects_owner_mismatch_without_update(self):
        payload = main.StoryCharactersSchema(
            characters=self.characters,
            user_id=str(ObjectId()),
        )

        with (
            patch.object(main, "stories_collection", self.stories),
            patch.object(
                main,
                "character_profiles_collection",
                self.profiles,
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await main.save_story_characters(
                    self.story_id,
                    payload,
                    self._request(str(ObjectId())),
                )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(len(self.stories.find_queries), 1)
        self.assertEqual(self.stories.update_calls, [])
        self.assertEqual(self.profiles.find_queries, [])

    async def test_main_load_rejects_invalid_story_id_without_db_call(self):
        with patch.object(main, "stories_collection", self.stories):
            selected = await main.load_story_cast_member(
                "invalid-story-id",
                "Arin waited.",
            )

        self.assertIsNone(selected)
        self.assertEqual(self.stories.find_queries, [])

    async def test_media_generation_rejects_story_without_locked_cast(self):
        with (
            patch.object(main, "load_story_cast", return_value=[]),
            patch.object(main, "load_visual_context", AsyncMock(return_value={})),
        ):
            with self.assertRaises(main.HfMediaError) as raised:
                await main.generate_and_store_backend_media(
                    story_id=str(ObjectId()),
                    story_text="Arin walks toward the castle.",
                    include_video=True,
                )

        self.assertIn("character selection", str(raised.exception).lower())

    async def test_character_scene_without_profile_never_uses_flux_fallback(self):
        generate_flux = AsyncMock()
        with (
            patch.object(main, "load_story_cast", return_value=[]),
            patch.object(main, "load_visual_context", AsyncMock(return_value={})),
            patch.object(main, "generate_hf_fairytale_image", generate_flux),
        ):
            with self.assertRaises(main.HfMediaError) as raised:
                await main.generate_and_store_backend_media(
                    story_text="A child walks toward the castle.",
                    include_video=False,
                )

        self.assertIn("selected character profile", str(raised.exception).lower())
        generate_flux.assert_not_awaited()

    async def test_profile_without_scene_asset_never_uses_flux_fallback(self):
        selected_cast = [
            {
                "role": "hero",
                "name": "Arin",
                "character_key": "female_04",
                "selection_source": "user",
                "source_description": "Hero 'Arin'",
            },
            {
                "role": "companion",
                "name": "Luna",
                "character_key": "female_05",
                "selection_source": "automatic",
                "source_description": "Forest fairy 'Luna'",
            },
        ]
        generate_flux = AsyncMock()
        with (
            patch.object(main, "load_story_cast", return_value=selected_cast),
            patch.object(main, "load_visual_context", AsyncMock(return_value={})),
            patch.object(
                main,
                "load_active_character_profile",
                AsyncMock(
                    return_value={
                        "character_key": "female_04",
                        "name": "Selected Hero",
                        "assets": [],
                    }
                ),
            ),
            patch.object(main, "generate_hf_fairytale_image", generate_flux),
        ):
            with self.assertRaises(main.HfMediaError) as raised:
                await main.generate_and_store_backend_media(
                    story_id=str(ObjectId()),
                    story_text="Arin walks toward the castle.",
                    include_video=False,
                )

        self.assertIn("preserve character identity", str(raised.exception).lower())
        generate_flux.assert_not_awaited()

    async def test_media_generation_uses_the_locked_user_selected_profile(self):
        selected_profile = {
            "character_key": "female_04",
            "name": "Selected Hero",
            "description": "The profile chosen in the story start screen.",
            "style_prompt": "storybook",
            "assets": [
                {
                    "pose": "walking",
                    "emotion": "determined",
                    "image_file_id": "selected-walking-file",
                    "image_url": "/api/media/images/selected-walking-file",
                    "scene_keywords": ["walk"],
                },
                {
                    "pose": "motion-sheet",
                    "emotion": "dynamic",
                    "quality_tier": "video_motion_sheet_v3",
                    "image_file_id": "selected-motion-file",
                    "image_url": "/api/media/images/selected-motion-file",
                },
                {
                    "pose": "target-journey-sheet",
                    "emotion": "determined",
                    "quality_tier": "video_target_journey_sheet_v4",
                    "image_file_id": "selected-target-motion-file",
                    "image_url": "/api/media/images/selected-target-motion-file",
                },
            ],
        }
        selected_cast = [
            {
                "role": "hero",
                "name": "Arin",
                "character_key": "female_04",
                "selection_source": "user",
                "source_description": "Hero 'Arin'",
            }
        ]
        composite_result = {
            "image_bytes": b"image",
            "background_bytes": b"background",
            "character_bytes": b"selected-character-body",
            "secondary_character_bytes": None,
            "content_type": "image/png",
            "provider": "local-composite",
            "model": "storybook-asset-compositor-v1",
            "inference_provider": "local",
            "attempted_providers": [],
            "image_mode": "local_composite",
            "background_key": "fantasy_castle",
            "background_source": "bundled_asset",
        }
        generated_video = {
            "video_bytes": b"video",
            "content_type": "video/mp4",
            "provider": "local-animation",
            "model": "storybook-layered-action-v2",
            "parameters": {
                "animation_mode": "layered_action",
                "motion_plan": {"action": "journey"},
            },
        }
        load_profile = AsyncMock(return_value=selected_profile)
        generate_video = AsyncMock(return_value=generated_video)
        upload_media = AsyncMock(
            side_effect=[
                {"file_id": "image-file", "url": "/api/media/images/image-file"},
                {"file_id": "video-file", "url": "/api/media/videos/video-file"},
            ]
        )

        with (
            patch.object(main, "load_story_cast", return_value=selected_cast),
            patch.object(main, "load_visual_context", AsyncMock(return_value={})),
            patch.object(main, "load_active_character_profile", load_profile),
            patch.object(
                main,
                "generate_composite_scene",
                AsyncMock(return_value=composite_result),
            ),
            patch.object(main, "generate_hf_fairytale_video", generate_video),
            patch.object(
                main,
                "inspect_generated_media",
                return_value={
                    "passed": True,
                    "reasons": [],
                    "measurements": {},
                    "metadata": {},
                },
            ),
            patch.object(
                main,
                "download_gridfs_file",
                AsyncMock(
                    side_effect=[
                        b"selected-motion-sheet",
                        b"selected-target-motion-sheet",
                    ]
                ),
            ),
            patch.object(main, "upload_generated_media_file", upload_media),
        ):
            result = await main.generate_and_store_backend_media(
                story_id=str(ObjectId()),
                story_text="Luna ran ahead while Arin walked toward the castle.",
                character_key="female_04",
                include_video=True,
            )

        self.assertEqual(load_profile.await_args.args[0], "female_04")
        self.assertEqual(result["metadata"]["character_key"], "female_04")
        self.assertEqual(
            result["metadata"]["character_selection_source"],
            "user",
        )
        motion_context = generate_video.await_args.kwargs["motion_context"]
        self.assertEqual(
            motion_context["character_bytes"],
            b"selected-character-body",
        )
        self.assertIsNone(motion_context["character_motion_sheet_bytes"])
        self.assertEqual(
            motion_context["character_target_journey_sheet_bytes"],
            b"selected-motion-sheet",
        )
        self.assertEqual(result["metadata"]["motion_assets_loaded"], ["target"])
        self.assertEqual(motion_context["character_key"], "female_04")


class StoryCastSelectionEdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.cast = build_story_cast(
            {
                "hero": "Arin",
                "antagonist": "Darkron",
                "companion": "Forest fairy 'Luna'",
            },
            PROFILES,
            genre="fantasy",
        )
        self.by_role = {member["role"]: member for member in self.cast}

    def test_hero_and_antagonist_together_selects_hero_priority(self):
        selected = select_story_cast_member(
            self.cast,
            "Arin challenged Darkron at the gate.",
        )

        self.assertEqual(selected["role"], "hero")
        self.assertEqual(
            selected["character_key"],
            self.by_role["hero"]["character_key"],
        )

    def test_unquoted_character_name_is_detected(self):
        self.assertEqual(self.by_role["hero"]["name"], "Arin")

        selected = select_story_cast_member(
            self.cast,
            "Arin opened the glowing door.",
        )

        self.assertEqual(selected["role"], "hero")

    def test_role_only_text_selects_matching_role(self):
        selected = select_story_cast_member(
            self.cast,
            "The antagonist blocked the narrow bridge.",
        )

        self.assertEqual(selected["role"], "antagonist")
        self.assertEqual(
            selected["character_key"],
            self.by_role["antagonist"]["character_key"],
        )

    def test_pronoun_only_text_defaults_to_hero(self):
        selected = select_story_cast_member(
            self.cast,
            "He gathered his courage and stepped forward.",
        )

        self.assertEqual(selected["role"], "hero")
        self.assertEqual(
            selected["character_key"],
            self.by_role["hero"]["character_key"],
        )


if __name__ == "__main__":
    unittest.main()
