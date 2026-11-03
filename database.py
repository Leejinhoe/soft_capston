# app/database.py
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

# Accept the documented name and the legacy variable, but never fall back to
# credentials embedded in source code.
MONGO_DETAILS = os.getenv("MONGO_URI") or os.getenv("MONGO_DETAILS")
if not MONGO_DETAILS:
    raise RuntimeError("Set MONGO_URI (or legacy MONGO_DETAILS) in the server environment.")

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.fairytale_db

# 비동기 조작용 핵심 컬렉션 참조 명시
users_collection = database.get_collection("users")
stories_collection = database.get_collection("stories")
vocabularies_collection = database.get_collection("vocabularies")
