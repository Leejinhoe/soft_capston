from datetime import datetime
from typing import Dict, List, Optional

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
    characters: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StoryCharactersSchema(BaseModel):
    characters: Dict[str, str] = Field(default_factory=dict)
    user_id: Optional[str] = None


class SceneSchema(BaseModel):
    step_number: int
    story_text: str
    choice_made: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CharacterAssetSchema(BaseModel):
    pose: str = Field(default="default", min_length=1, max_length=40)
    emotion: str = Field(default="neutral", min_length=1, max_length=40)
    image_file_id: Optional[str] = None
    image_url: Optional[str] = None
    quality_tier: Optional[str] = Field(default=None, max_length=40)
    animation_group: Optional[str] = Field(default=None, max_length=40)
    animation_layout: Optional[str] = Field(default=None, max_length=20)
    animation_frame_count: Optional[int] = Field(default=None, ge=2, le=16)
    animation_version: Optional[int] = Field(default=None, ge=1, le=100)
    animation_cycle_seconds: Optional[float] = Field(
        default=None,
        ge=0.25,
        le=15.0,
    )
    tags: List[str] = Field(default_factory=list)
    scene_keywords: List[str] = Field(default_factory=list)


class CharacterProfileUpsertSchema(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)
    style_prompt: Optional[str] = Field(default=None, max_length=500)
    genres: List[str] = Field(default_factory=list, max_length=20)
    assets: List[CharacterAssetSchema] = Field(default_factory=list, max_length=40)
    active: bool = True


class MediaGenerationSchema(BaseModel):
    story_text: str
    genre: Optional[str] = None
    age: Optional[str] = None
    character_key: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    include_video: bool = False
    width: int = Field(default=512, ge=256, le=1536)
    height: int = Field(default=512, ge=256, le=1536)
    flux_steps: int = Field(default=1, ge=1, le=8)
    video_width: int = Field(default=512, ge=256, le=1280)
    video_height: int = Field(default=384, ge=256, le=768)
    num_frames: int = Field(default=48, ge=9, le=240)
    video_steps: int = Field(default=12, ge=2, le=16)
    frame_rate: Optional[int] = Field(default=12, ge=6, le=30)
    video_timeout: Optional[int] = Field(default=15, ge=5, le=15)


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


class WarningCreateSchema(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    severity: str = Field(
        default="notice",
        pattern=r"^(notice|caution|final)$",
    )
    expires_at: Optional[datetime] = None


class WarningResolutionSchema(BaseModel):
    status: str = Field(pattern=r"^(resolved|dismissed)$")
    resolution_note: Optional[str] = Field(default=None, max_length=1000)


class CommunityReportSchema(BaseModel):
    reporter_account_id: Optional[str] = Field(default=None, max_length=120)
    target_type: str = Field(pattern=r"^(post|comment|user)$")
    target_id: str = Field(min_length=1, max_length=64)
    post_id: Optional[str] = Field(default=None, max_length=64)
    reason: str = Field(min_length=2, max_length=200)
    details: Optional[str] = Field(default=None, max_length=1000)


class ReportResolutionSchema(BaseModel):
    status: str = Field(pattern=r"^(reviewed|resolved|dismissed)$")
    action_taken: Optional[str] = Field(default=None, max_length=100)
    resolution_note: Optional[str] = Field(default=None, max_length=1000)


class AccountWithdrawalSchema(BaseModel):
    password: Optional[str] = Field(default=None, max_length=200)
    reason: Optional[str] = Field(default=None, max_length=500)
