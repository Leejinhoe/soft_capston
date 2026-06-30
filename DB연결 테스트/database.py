import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_DETAILS = os.getenv("MONGO_DETAILS") or os.getenv("MONGO_URI")

if not MONGO_DETAILS:
    raise RuntimeError(
        "MongoDB connection string is missing. "
        "Set MONGO_DETAILS or MONGO_URI in your local .env file."
    )

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.fairytale_db

users_collection = database.get_collection("users")
stories_collection = database.get_collection("stories")
vocabularies_collection = database.get_collection("vocabularies")
community_posts_collection = database.get_collection("community_posts")
