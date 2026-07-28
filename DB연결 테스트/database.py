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
fit_vocabulary_collection = database.get_collection("fit_vocabulary")
visual_vocabulary_collection = database.get_collection("visual_vocabulary")
community_posts_collection = database.get_collection("community_posts")
reports_collection = database.get_collection("reports")
user_warnings_collection = database.get_collection("user_warnings")
media_jobs_collection = database.get_collection("media_jobs")
character_profiles_collection = database.get_collection("character_profiles")
media_files_bucket = AsyncIOMotorGridFSBucket(
    database,
    bucket_name=MEDIA_GRIDFS_BUCKET,
)


async def init_database() -> None:
    await reports_collection.create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)],
        name="reports_status_created_idx",
    )
    await reports_collection.create_index(
        [("target_type", ASCENDING), ("target_id", ASCENDING), ("created_at", DESCENDING)],
        name="reports_target_created_idx",
    )
    await reports_collection.create_index(
        [("reporter_account_id", ASCENDING), ("target_type", ASCENDING), ("target_id", ASCENDING)],
        name="reports_reporter_target_idx",
    )
    await user_warnings_collection.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
        name="warnings_user_status_created_idx",
    )
    await visual_vocabulary_collection.create_index(
        [("source_key", ASCENDING)],
        name="visual_vocabulary_source_key_unique_idx",
        unique=True,
    )
    await visual_vocabulary_collection.create_index(
        [("enabled", ASCENDING), ("usable_for_image", ASCENDING), ("fit_score", DESCENDING)],
        name="visual_vocabulary_runtime_idx",
    )
    await visual_vocabulary_collection.create_index(
        [("match_terms", ASCENDING)],
        name="visual_vocabulary_match_terms_idx",
    )
    await character_profiles_collection.create_index(
        [("character_key", ASCENDING)],
        name="character_profiles_key_unique_idx",
        unique=True,
    )
    await character_profiles_collection.create_index(
        [("active", ASCENDING), ("updated_at", DESCENDING)],
        name="character_profiles_active_updated_idx",
    )
    await character_profiles_collection.create_index(
        [("genres", ASCENDING), ("active", ASCENDING)],
        name="character_profiles_genres_active_idx",
    )
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
