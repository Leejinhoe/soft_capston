import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)

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
notices_collection = database.get_collection("notices")
email_verifications_collection = database.get_collection("email_verifications")
messages_collection = database.get_collection("messages")
media_jobs_collection = database.get_collection("media_jobs")
character_profiles_collection = database.get_collection("character_profiles")
media_files_bucket = AsyncIOMotorGridFSBucket(
    database,
    bucket_name=MEDIA_GRIDFS_BUCKET,
)


async def ensure_index(collection, keys, **options):
    """Create an index without failing when an equivalent legacy name exists."""
    try:
        return await collection.create_index(keys, **options)
    except OperationFailure as exc:
        # MongoDB reports code 85 when the same key pattern already exists
        # with a different name or index options.
        if exc.code != 85:
            raise

        requested_keys = list(keys)
        requested_unique = bool(options.get("unique", False))
        requested_sparse = bool(options.get("sparse", False))
        requested_expire = options.get("expireAfterSeconds")
        for existing_name, details in (await collection.index_information()).items():
            if list(details.get("key", [])) != requested_keys:
                continue
            if bool(details.get("unique", False)) != requested_unique:
                continue
            if bool(details.get("sparse", False)) != requested_sparse:
                continue
            if requested_expire is not None and details.get("expireAfterSeconds") != requested_expire:
                continue

            logger.info(
                "Reusing existing MongoDB index %s for requested index %s",
                existing_name,
                options.get("name"),
            )
            return existing_name

        raise


async def init_database() -> None:
    await ensure_index(notices_collection,
        [("is_published", ASCENDING), ("is_pinned", DESCENDING), ("published_at", DESCENDING)],
        name="notices_published_pinned_idx",
    )
    await ensure_index(notices_collection,
        [("author_account_id", ASCENDING), ("created_at", DESCENDING)],
        name="notices_author_created_idx",
    )
    await ensure_index(email_verifications_collection,
        [("email", ASCENDING), ("created_at", DESCENDING)],
        name="email_verifications_email_created_idx",
    )
    await ensure_index(email_verifications_collection,
        [("expires_at", ASCENDING)],
        name="email_verifications_expire_idx",
        expireAfterSeconds=0,
    )
    await ensure_index(messages_collection,
        [("story_id", ASCENDING), ("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="messages_story_user_created_idx",
    )
    await ensure_index(reports_collection,
        [("status", ASCENDING), ("created_at", DESCENDING)],
        name="reports_status_created_idx",
    )
    await ensure_index(reports_collection,
        [("target_type", ASCENDING), ("target_id", ASCENDING), ("created_at", DESCENDING)],
        name="reports_target_created_idx",
    )
    await ensure_index(reports_collection,
        [("reporter_account_id", ASCENDING), ("target_type", ASCENDING), ("target_id", ASCENDING)],
        name="reports_reporter_target_idx",
    )
    await ensure_index(user_warnings_collection,
        [("user_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
        name="warnings_user_status_created_idx",
    )
    await ensure_index(visual_vocabulary_collection,
        [("source_key", ASCENDING)],
        name="visual_vocabulary_source_key_unique_idx",
        unique=True,
    )
    await ensure_index(visual_vocabulary_collection,
        [("enabled", ASCENDING), ("usable_for_image", ASCENDING), ("fit_score", DESCENDING)],
        name="visual_vocabulary_runtime_idx",
    )
    await ensure_index(visual_vocabulary_collection,
        [("match_terms", ASCENDING)],
        name="visual_vocabulary_match_terms_idx",
    )
    await ensure_index(character_profiles_collection,
        [("character_key", ASCENDING)],
        name="character_profiles_key_unique_idx",
        unique=True,
    )
    await ensure_index(character_profiles_collection,
        [("active", ASCENDING), ("updated_at", DESCENDING)],
        name="character_profiles_active_updated_idx",
    )
    await ensure_index(character_profiles_collection,
        [("genres", ASCENDING), ("active", ASCENDING)],
        name="character_profiles_genres_active_idx",
    )
    await ensure_index(media_jobs_collection,
        [("status", ASCENDING), ("created_at", ASCENDING)],
        name="media_jobs_status_created_idx",
    )
    await ensure_index(media_jobs_collection,
        [
            ("owner_user_id", ASCENDING),
            ("status", ASCENDING),
            ("created_at", DESCENDING),
        ],
        name="media_jobs_owner_status_created_idx",
    )
    await ensure_index(media_jobs_collection,
        [("story_id", ASCENDING), ("step_number", ASCENDING), ("created_at", DESCENDING)],
        name="media_jobs_story_scene_created_idx",
    )
    await ensure_index(media_jobs_collection,
        [("active_key", ASCENDING)],
        name="media_jobs_active_key_unique_idx",
        unique=True,
        sparse=True,
    )
    await ensure_index(media_jobs_collection,
        [("owner_user_id", ASCENDING), ("cache_key", ASCENDING), ("status", ASCENDING)],
        name="media_jobs_owner_cache_status_idx",
    )
    await ensure_index(media_jobs_collection,
        [("scene_synced_at", ASCENDING), ("completed_at", ASCENDING)],
        name="media_jobs_scene_sync_idx",
        sparse=True,
    )
