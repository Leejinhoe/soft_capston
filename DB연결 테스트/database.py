import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pymongo import ASCENDING, DESCENDING

BACKEND_ENV_FILE = Path(__file__).resolve().parent / ".env"
PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

load_dotenv(PROJECT_ENV_FILE)
load_dotenv(BACKEND_ENV_FILE, override=True)

MONGO_URI = (os.getenv("MONGO_URI") or os.getenv("MONGO_DETAILS") or "").strip()
MONGO_DETAILS = MONGO_URI
DB_NAME = (
    os.getenv("DB_NAME")
    or os.getenv("MONGO_DB_NAME")
    or os.getenv("MONGO_DATABASE_NAME")
    or "fairytale_db"
).strip()
MONGO_DATABASE_NAME = DB_NAME
MEDIA_FILES_BUCKET = (
    os.getenv("MEDIA_FILES_BUCKET")
    or os.getenv("MEDIA_GRIDFS_BUCKET")
    or "media_files"
).strip()
MEDIA_GRIDFS_BUCKET = MEDIA_FILES_BUCKET

if not MONGO_DETAILS:
    raise RuntimeError(
        "MongoDB connection string is missing. "
        "Set MONGO_DETAILS or MONGO_URI in your local .env file."
    )

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client[MONGO_DATABASE_NAME]

users_collection = database.get_collection("users")
stories_collection = database.get_collection("stories")
vocabularies_collection = database.get_collection("vocabularies")
community_posts_collection = database.get_collection("community_posts")
media_jobs_collection = database.get_collection("media_jobs")
media_files_bucket = AsyncIOMotorGridFSBucket(
    database,
    bucket_name=MEDIA_GRIDFS_BUCKET,
)


async def init_database() -> None:
    await media_jobs_collection.create_index(
        [("status", ASCENDING), ("created_at", ASCENDING)],
        name="media_jobs_status_created_idx",
    )
    await media_jobs_collection.create_index(
        [("story_id", ASCENDING), ("step_number", ASCENDING), ("created_at", DESCENDING)],
        name="media_jobs_story_scene_created_idx",
    )
    await media_jobs_collection.create_index(
        [("scene_synced_at", ASCENDING), ("completed_at", ASCENDING)],
        name="media_jobs_scene_sync_idx",
        sparse=True,
    )
