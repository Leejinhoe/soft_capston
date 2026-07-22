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
    personality_type: Optional[str] = "Unknown"
    radar_stats: Optional[Dict] = Field(default_factory=dict)
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


class MediaGenerationSchema(BaseModel):
    story_text: str
    genre: Optional[str] = None
    age: Optional[str] = None
    include_video: bool = False
    width: int = Field(default=512, ge=256, le=1536)
    height: int = Field(default=512, ge=256, le=1536)
    flux_steps: int = Field(default=1, ge=1, le=8)
    video_width: int = Field(default=512, ge=256, le=1280)
    video_height: int = Field(default=384, ge=256, le=768)
    num_frames: int = Field(default=48, ge=9, le=240)
    video_steps: int = Field(default=2, ge=2, le=50)
    frame_rate: Optional[int] = Field(default=12, ge=6, le=30)
    video_timeout: Optional[int] = Field(default=None, ge=30, le=1800)


class MediaGenerationWithStorySchema(MediaGenerationSchema):
    story_id: Optional[str] = None
    step_number: Optional[int] = None


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
    story_emoji: str = "?"
    created_at: datetime = Field(default_factory=datetime.utcnow)
