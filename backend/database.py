import logging
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)
database = client["fairytale_db"]

users_collection = database.get_collection("users")
stories_collection = database.get_collection("stories")
vocabularies_collection = database.get_collection("vocabularies")
reports_collection = database.get_collection("reports")
posts_collection = database.get_collection("posts")
notifications_collection = database.get_collection("notifications")
notices_collection = database.get_collection("notices")
post_likes_collection = database.get_collection("post_likes")
post_scraps_collection = database.get_collection("post_scraps")
comments_collection = database.get_collection("comments")
word_meaning_cache_collection = database.get_collection("word_meaning_cache")
# 1:1 쪽지. "messages"는 팀원 기능(캐릭터 대화 등)이 쓸 수 있어 따로 둡니다.
direct_messages_collection = database.get_collection("direct_messages")


# ----------------------------------------
# 인덱스 만들기 (서버 시작 시 ensure_indexes에서 사용)
# ----------------------------------------
logger = logging.getLogger("uvicorn.error")

# 85: IndexOptionsConflict (같은 키인데 이름/옵션이 다름), 86: IndexKeySpecsConflict (같은 이름인데 키/옵션이 다름)
_INDEX_CONFLICT_CODES = {85, 86}


async def safe_create_index(collection, keys, **kwargs) -> None:
    """이미 다른 이름/옵션으로 같은 인덱스가 있어서 충돌하면 경고만 남기고 넘어갑니다. (서버는 계속 켜짐)"""
    try:
        await collection.create_index(keys, **kwargs)
    except OperationFailure as e:
        if e.code not in _INDEX_CONFLICT_CODES:
            raise
        logger.warning(
            "[index] %s %s 인덱스 충돌(code %s)로 건너뜀: %s",
            collection.name, keys, e.code, e.details.get("errmsg") if e.details else e,
        )
