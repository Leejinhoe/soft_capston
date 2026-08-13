import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "DB연결 테스트"
sys.path.insert(0, str(BACKEND_DIR))
EVENT_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(EVENT_LOOP)

from database import stories_collection  # noqa: E402


def clean_cast_member(member):
    return {
        "role": member.get("role"),
        "name": member.get("name"),
        "character_key": member.get("character_key"),
        "source_description": member.get("source_description"),
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Print recent stories that have a locked character cast."
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--require-cast", action="store_true")
    args = parser.parse_args()

    projection = {
        "title": 1,
        "genre": 1,
        "target_age": 1,
        "story_cast": 1,
        "characters": 1,
        "character_overrides": 1,
        "scenes": 1,
        "created_at": 1,
        "updated_at": 1,
    }
    query = {"story_cast.0": {"$exists": True}} if args.require_cast else {}
    stories = await stories_collection.find(query, projection).sort(
        [("updated_at", -1), ("created_at", -1)]
    ).to_list(length=args.limit)
    rows = []
    for story in stories:
        scenes = sorted(
            story.get("scenes") or [],
            key=lambda scene: scene.get("step_number", 0),
        )
        latest_scene = scenes[-1] if scenes else {}
        rows.append(
            {
                "story_id": str(story["_id"]),
                "title": story.get("title"),
                "genre": story.get("genre"),
                "age": story.get("target_age"),
                "updated_at": str(story.get("updated_at") or story.get("created_at")),
                "cast": [clean_cast_member(item) for item in story.get("story_cast", [])],
                "characters": story.get("characters") or {},
                "character_overrides": story.get("character_overrides") or {},
                "latest_scene": {
                    "step_number": latest_scene.get("step_number"),
                    "story_text": latest_scene.get("story_text") or latest_scene.get("text"),
                },
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    try:
        EVENT_LOOP.run_until_complete(main())
    finally:
        EVENT_LOOP.close()
