from datetime import datetime
from typing import Any, Dict, List, Optional

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
    email_verification_token: Optional[str] = None
    personality_type: Optional[str] = "Unknown"
    radar_stats: Optional[Dict] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoginSchema(BaseModel):
    account_id: str
    password: str


class EmailVerificationSendSchema(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class EmailVerificationVerifySchema(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(min_length=6, max_length=6)


class StorySchema(BaseModel):
    user_id: str
    title: str
    genre: str
    age: str
    prompt: str
    characters: Dict[str, str] = Field(default_factory=dict)
    character_overrides: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StoryCharactersSchema(BaseModel):
    characters: Dict[str, str] = Field(default_factory=dict)
    character_overrides: Optional[Dict[str, str]] = None
    user_id: Optional[str] = None


class SceneContractSchema(BaseModel):
    version: int = Field(default=1, ge=1, le=1)
    character_key: Optional[str] = Field(default=None, max_length=64)
    scene_goal: Optional[str] = Field(default=None, max_length=180)
    action: Optional[str] = Field(default=None, max_length=40)
    target: Optional[str] = Field(default=None, max_length=100)
    required_props: List[str] = Field(default_factory=list, max_length=8)
    participant_count: Optional[int] = Field(default=None, ge=0, le=4)
    participants: List[Dict[str, Any]] = Field(default_factory=list, max_length=4)
    character_keys: List[str] = Field(default_factory=list, max_length=4)
    participant_roles: Dict[str, str] = Field(default_factory=dict)
    requires_partner: Optional[bool] = None
    requires_object: Optional[bool] = None
    visual_anchor: Optional[str] = Field(default=None, max_length=240)
    background_direction: Optional[str] = Field(default=None, max_length=40)
    dialogue: Optional[str] = Field(default=None, max_length=240)


class SceneSchema(BaseModel):
    step_number: int
    story_text: str
    choice_made: Optional[str] = None
    scene_contract: Optional[SceneContractSchema] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CharacterAssetSchema(BaseModel):
    pose: str = Field(default="default", min_length=1, max_length=40)
    emotion: str = Field(default="neutral", min_length=1, max_length=40)
    image_file_id: Optional[str] = None
    image_url: Optional[str] = None
    quality_tier: Optional[str] = Field(default=None, max_length=40)
    tags: List[str] = Field(default_factory=list)
    scene_keywords: List[str] = Field(default_factory=list)
    sheet_columns: Optional[int] = Field(default=None, ge=1, le=8)
    sheet_rows: Optional[int] = Field(default=None, ge=1, le=8)
    motion_cells: Dict[str, List[int]] = Field(default_factory=dict)
    asset_version: Optional[str] = Field(default=None, max_length=80)
    asset_fingerprint: Optional[str] = Field(default=None, max_length=128)
    identity_context: Dict[str, str] = Field(default_factory=dict)


class CharacterProfileUpsertSchema(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)
    style_prompt: Optional[str] = Field(default=None, max_length=500)
    genres: List[str] = Field(default_factory=list, max_length=20)
    assets: List[CharacterAssetSchema] = Field(default_factory=list, max_length=40)
    active: bool = True


class MediaGenerationSchema(BaseModel):
    story_text: str = Field(min_length=1, max_length=12000)
    genre: Optional[str] = Field(default=None, max_length=80)
    age: Optional[str] = Field(default=None, max_length=20)
    character_key: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    scene_contract: Optional[SceneContractSchema] = None
    include_video: bool = False
    width: int = Field(default=512, ge=256, le=1536)
    height: int = Field(default=512, ge=256, le=1536)
    flux_steps: int = Field(default=1, ge=1, le=8)
    video_width: int = Field(default=960, ge=256, le=1280)
    video_height: int = Field(default=480, ge=256, le=768)
    num_frames: int = Field(default=180, ge=9, le=450)
    video_steps: int = Field(default=2, ge=2, le=50)
    frame_rate: Optional[int] = Field(default=30, ge=6, le=30)
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


class AdminNoticeCreateSchema(BaseModel):
    account_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=2, max_length=5000)
    is_pinned: bool = False
    send_email: bool = False


class AdminNoticeUpdateSchema(BaseModel):
    account_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=2, max_length=5000)
    is_pinned: bool = False


class AdminNoticeEmailSchema(BaseModel):
    account_id: str = Field(min_length=1, max_length=120)


class StoryCharacterDiscoverySchema(BaseModel):
    story_id: Optional[str] = None
    story_title: str = Field(default="", max_length=500)
    story_text: str = Field(default="", max_length=12000)
    age: Optional[str] = Field(default=None, max_length=40)


class StoryCharacterChatSchema(BaseModel):
    story_id: Optional[str] = None
    story_title: str = Field(default="", max_length=500)
    story_text: str = Field(default="", max_length=12000)
    age: Optional[str] = Field(default=None, max_length=40)
    user_name: Optional[str] = Field(default=None, max_length=120)
    character: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, str]] = Field(default_factory=list, max_length=20)
    user_message: str = Field(min_length=1, max_length=1000)
