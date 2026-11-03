"""End-to-end identity checks for choice, scene persistence, and media requests.

These tests deliberately use the production orchestration functions while keeping
MongoDB and external media providers in-memory/mocked.  A failing test is useful:
it records an integration contract that the current implementation does not keep.
"""

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException

import main
from models import SceneContractSchema


OWNER_ID = "owner-choice-flow"


def _profile(key, name, role):
    return {
        "character_key": key,
        "name": name,
        "description": f"fixed face for {name}",
        "style_prompt": "consistent storybook character",
        "genres": ["fantasy"],
        "role_tags": [role],
        "active": True,
        "assets": [{
            "pose": "default",
            "emotion": "neutral",
            "image_file_id": f"{key}-image",
            "image_url": f"/api/media/images/{key}-image",
            "tags": [role],
        }],
    }


PROFILES = [
    _profile("hero_fixed_01", "Arin", "hero"),
    _profile("companion_fixed_01", "Luna", "companion"),
    _profile("villain_fixed_01", "Darkron", "antagonist"),
]


class _Result:
    def __init__(self, *, inserted_id=None, modified_count=1, matched_count=1):
        self.inserted_id = inserted_id or ObjectId()
        self.modified_count = modified_count
        self.matched_count = matched_count


class FakeProfiles:
    def __init__(self, profiles):
        self.profiles = copy.deepcopy(profiles)
        self.find_queries = []

    async def find_one(self, query, **kwargs):
        key = query.get("character_key")
        if isinstance(key, dict):
            return next((p for p in self.profiles if p["character_key"] != key.get("$ne")), None)
        return next((p for p in self.profiles if p["character_key"] == key), None)

    def find(self, query):
        self.find_queries.append(copy.deepcopy(query))
        return _Cursor(self.profiles)


class _Cursor:
    def __init__(self, values):
        self.values = values

    async def to_list(self, length):
        return copy.deepcopy(self.values[:length])


class FakeStories:
    def __init__(self, story):
        self.story = copy.deepcopy(story)
        self.update_calls = []

    async def find_one(self, query, projection=None):
        if query.get("_id") != self.story["_id"]:
            return None
        if "scenes.step_number" in query:
            step = query["scenes.step_number"]
            if not any(s.get("step_number") == step for s in self.story.get("scenes", [])):
                return None
        if "scenes" in query and "$elemMatch" in query["scenes"]:
            match = query["scenes"]["$elemMatch"]
            if not any(
                s.get("step_number") == match.get("step_number")
                and s.get("media_job_id") == match.get("media_job_id")
                for s in self.story.get("scenes", [])
            ):
                return None
        if projection == {"story_cast": 1}:
            return {"story_cast": copy.deepcopy(self.story.get("story_cast"))}
        return copy.deepcopy(self.story)

    async def update_one(self, query, update):
        self.update_calls.append((copy.deepcopy(query), copy.deepcopy(update)))
        if query.get("_id") != self.story["_id"]:
            return _Result(modified_count=0, matched_count=0)
        if "$push" in update:
            self.story.setdefault("scenes", []).append(copy.deepcopy(update["$push"]["scenes"]))
        for key, value in update.get("$set", {}).items():
            if key.startswith("scenes.$."):
                field = key.split(".", 2)[2]
                step = query.get("scenes.step_number")
                if step is None and "$elemMatch" in query.get("scenes", {}):
                    step = query["scenes"]["$elemMatch"]["step_number"]
                for scene in self.story.get("scenes", []):
                    if scene.get("step_number") == step:
                        scene[field] = copy.deepcopy(value)
            else:
                self.story[key] = copy.deepcopy(value)
        return _Result()


class FakeJobs:
    def __init__(self):
        self.jobs = {}

    async def find_one(self, query):
        for job in self.jobs.values():
            if query.get("_id") == job.get("_id"):
                return copy.deepcopy(job)
            if query.get("active_key") == job.get("active_key") and job.get("status") in query.get("status", {}).get("$in", [job.get("status")]):
                return copy.deepcopy(job)
        return None

    async def count_documents(self, query):
        return sum(1 for job in self.jobs.values() if job.get("owner_user_id") == query.get("owner_user_id") and job.get("status") in query.get("status", {}).get("$in", []))

    async def insert_one(self, job):
        job = copy.deepcopy(job)
        job.setdefault("_id", ObjectId())
        self.jobs[str(job["_id"])] = job
        return _Result(inserted_id=job["_id"])


def _request():
    return SimpleNamespace(state=SimpleNamespace(auth={"uid": OWNER_ID}))


class ChoiceToMediaIdentityRedTeamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.story_oid = ObjectId()
        self.story_id = str(self.story_oid)
        self.story = {
            "_id": self.story_oid,
            "user_id": OWNER_ID,
            "genre": "fantasy",
            "characters": {"hero": "Brave child 'Arin'", "companion": "Forest fairy 'Luna'"},
            "story_cast": [],
            "scenes": [],
        }
        self.stories = FakeStories(self.story)
        self.profiles = FakeProfiles(PROFILES)
        self.jobs = FakeJobs()
        self.patches = (
            patch.object(main, "stories_collection", self.stories),
            patch.object(main, "character_profiles_collection", self.profiles),
            patch.object(main, "media_jobs_collection", self.jobs),
        )

    async def _lock_cast(self):
        payload = main.StoryCharactersSchema(characters=self.story["characters"], user_id=OWNER_ID)
        with self.patches[0], self.patches[1]:
            response = await main.save_story_characters(self.story_id, payload, _request())
        self.assertTrue(response["character_identity_locked"])
        return response

    async def _save_choice_scene(self, character_key, story_text, step=1):
        contract = SceneContractSchema(character_key=character_key, action="journey", target="castle")
        scene = main.SceneSchema(
            step_number=step,
            story_text=story_text,
            choice_made="Take the moonlit path",
            scene_contract=contract,
        )
        with self.patches[0]:
            await main.push_scene(self.story_id, scene, _request())

    async def test_selected_character_survives_choice_scene_and_image_video_job(self):
        locked = await self._lock_cast()
        hero_key = next(m["character_key"] for m in locked["story_cast"] if m["role"] == "hero")
        story_text = "Arin chose the moonlit path while Luna watched from the bridge."
        await self._save_choice_scene(hero_key, story_text)

        member = await self._load_member(story_text)
        self.assertEqual(member["character_key"], hero_key)
        self.assertEqual(self.stories.story["scenes"][0]["scene_contract"]["character_key"], hero_key)

        payload = main.MediaGenerationSchema(
            story_text=story_text,
            genre="fantasy",
            age="child",
            character_key=hero_key,
            scene_contract=SceneContractSchema(character_key=hero_key, action="journey"),
            include_video=True,
        )
        with self.patches[0], self.patches[1], self.patches[2]:
            queued = await main.create_scene_media_job(self.story_id, 1, payload, _request())
        self.assertEqual(queued["request"]["character_key"], hero_key)
        self.assertEqual(queued["request"]["scene_contract"]["character_key"], hero_key)
        self.assertEqual(self.stories.story["scenes"][0]["media_status"], "pending")

    async def _load_member(self, text):
        with self.patches[0], self.patches[1]:
            return await main.load_story_cast_member(self.story_id, text)

    async def test_name_change_does_not_change_the_selected_character_key(self):
        locked = await self._lock_cast()
        hero_key = next(m["character_key"] for m in locked["story_cast"] if m["role"] == "hero")
        member = await self._load_member("Arin was renamed to Rowan and entered the castle.")
        self.assertEqual(member["character_key"], hero_key)

    async def test_choice_mentioning_another_person_does_not_switch_primary_identity(self):
        locked = await self._lock_cast()
        hero_key = next(m["character_key"] for m in locked["story_cast"] if m["role"] == "hero")
        member = await self._load_member("Luna chose to rescue Arin before Darkron arrived.")
        self.assertEqual(member["character_key"], hero_key)

    async def test_companion_first_choice_text_still_uses_the_requested_hero_key(self):
        locked = await self._lock_cast()
        hero_key = next(m["character_key"] for m in locked["story_cast"] if m["role"] == "hero")
        story_text = "Luna ran ahead while Arin followed the moonlit path."
        payload = main.MediaGenerationWithStorySchema(
            story_id=self.story_id,
            step_number=1,
            story_text=story_text,
            genre="fantasy",
            age="child",
            character_key=hero_key,
        )
        self.story["scenes"] = [{"step_number": 1, "story_text": story_text}]
        with self.patches[0], self.patches[1], self.patches[2]:
            with patch.object(main, "require_story_owner", AsyncMock(return_value=self.story)):
                with patch.object(main, "ensure_story_scene_exists", AsyncMock()):
                    with patch.object(main, "enqueue_media_job", AsyncMock(return_value={"request": {}})):
                        result = await main.create_scene_media_job(
                            self.story_id,
                            1,
                            payload,
                            _request(),
                        )
        self.assertEqual(result["request"], {})

    async def test_old_scene_contract_without_character_key_is_rejected_at_media_boundary(self):
        locked = await self._lock_cast()
        hero_key = next(m["character_key"] for m in locked["story_cast"] if m["role"] == "hero")
        await self._save_choice_scene(hero_key, "Arin entered the castle.")
        payload = main.MediaGenerationSchema(story_text="Arin entered the castle.", genre="fantasy", age="child", character_key=None)
        with self.patches[0], self.patches[1], self.patches[2]:
            with self.assertRaises(HTTPException) as raised:
                await main.create_scene_media_job(self.story_id, 1, payload, _request())
        self.assertEqual(raised.exception.status_code, 409)

    async def test_wrong_key_injection_is_rejected_for_scene_media_request(self):
        await self._lock_cast()
        payload = main.MediaGenerationSchema(story_text="Arin entered the castle.", genre="fantasy", age="child", character_key="villain_fixed_01")
        with self.patches[0], self.patches[1], self.patches[2]:
            with self.assertRaises(HTTPException) as raised:
                await main.create_scene_media_job(self.story_id, 1, payload, _request())
        self.assertEqual(raised.exception.status_code, 404)

    async def test_legacy_story_migration_keeps_a_real_profile_key_before_media(self):
        self.story["story_cast"] = []
        self.story.pop("characters")
        self.story["character_overrides"] = {"hero": "hero_fixed_01"}
        with self.patches[0], self.patches[1]:
            cast = await main.load_story_cast(self.story_id)
        self.assertEqual(cast[0]["character_key"], "hero_fixed_01")
        self.assertTrue(self.stories.story["character_identity_locked"])

    async def test_sync_image_request_passes_character_key_to_generation_boundary(self):
        locked = await self._lock_cast()
        hero_key = next(m["character_key"] for m in locked["story_cast"] if m["role"] == "hero")
        await self._save_choice_scene(hero_key, "Arin entered the castle.")
        payload = main.MediaGenerationWithStorySchema(story_id=self.story_id, step_number=1, story_text="Arin entered the castle.", genre="fantasy", age="child", character_key=hero_key)
        fake_generation = AsyncMock(return_value={"image_url": "/image.png", "video_url": None, "saved": True})
        with self.patches[0], self.patches[1], patch.object(main, "execute_media_generation", fake_generation):
            result = await main.generate_media(payload, _request())
        self.assertEqual(result["image_url"], "/image.png")
        self.assertEqual(fake_generation.await_args.kwargs["character_key"], hero_key)


if __name__ == "__main__":
    unittest.main()
