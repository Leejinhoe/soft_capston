from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class UserSchema(BaseModel):
    account_id: str
    password: Optional[str] = None
    nickname: str
    email: Optional[str] = None
    provider: str = "local"
    provider_id: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    personality_type: Optional[str] = "분석 전"
    radar_stats: Optional[Dict] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoginSchema(BaseModel):
    account_id: str
    password: str


class StorySchema(BaseModel):
    user_id: str
    title: str
    genre: str
    age: str
    prompt: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SceneSchema(BaseModel):
    step_number: int
    story_text: str
    choice_made: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VocabularySchema(BaseModel):
    user_id: str
    origin_story_id: str
    hard: str
    easy: str
    definition: str
    source_story_title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommunityCommentSchema(BaseModel):
    author_name: str
    author_account_id: Optional[str] = None
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommunityPostSchema(BaseModel):
    author_name: str
    author_account_id: Optional[str] = None
    story_id: Optional[str] = None
    genre: str
    title: str
    preview: str
    full_text: str
    story_emoji: str = "📖"
    created_at: datetime = Field(default_factory=datetime.utcnow)
