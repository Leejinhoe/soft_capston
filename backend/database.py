import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

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
messages_collection = database.get_collection("messages")
