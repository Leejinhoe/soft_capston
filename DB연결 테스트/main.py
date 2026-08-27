import asyncio
from contextlib import suppress
import ast
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import smtplib
import tempfile
import time
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from gridfs.errors import NoFile
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from account_moderation import (
    DELETED_NICKNAME,
    build_soft_delete_fields,
    serialize_report,
    serialize_warning,
)
from background_assets import select_background_asset
from character_assets import (
    build_character_action_hint,
    select_character_asset,
    select_character_motion_sheet,
    select_character_action_sheet,
    select_character_action_cycle_sheet,
    select_character_jump_cycle_sheet,
    select_character_run_cycle_sheet,
    select_character_target_journey_sheet,
)
from character_seed import DEFAULT_CHARACTERS, seed_default_character_profiles
from character_identity import (
    build_character_identity_context,
    identity_context_from_profile,
    with_character_identity,
)
from database import (
    character_profiles_collection,
    community_posts_collection,
    email_verifications_collection,
    fit_vocabulary_collection,
    init_database,
    media_files_bucket,
    media_jobs_collection,
    messages_collection,
    notices_collection,
    reports_collection,
    stories_collection,
    user_warnings_collection,
    users_collection,
    visual_vocabulary_collection,
    vocabularies_collection,
)
from media_queue import (
    build_media_file_url,
    coerce_object_id,
    extract_media_result,
    serialize_datetime,
    serialize_media_job_document,
    serialize_object_id,
    serialize_optional_datetime,
)
from media_cache import build_media_cache_key
from media_quality_gate import evaluate_media_quality
from media_compositor import compose_background_scene, compose_story_scene
from hf_media_provider import (
    HfMediaError,
    build_video_motion_plan,
    generate_hf_fairytale_image,
    generate_hf_fairytale_video,
    get_hf_media_config,
)
from models import (
    AccountWithdrawalSchema,
    AdminNoticeCreateSchema,
    AdminNoticeEmailSchema,
    AdminNoticeUpdateSchema,
    CharacterProfileUpsertSchema,
    CommunityCommentSchema,
    CommunityPostSchema,
    CommunityReportSchema,
    EmailVerificationSendSchema,
    EmailVerificationVerifySchema,
    LoginSchema,
    MediaGenerationSchema,
    MediaGenerationWithStorySchema,
    ReportResolutionSchema,
    SceneSchema,
    StoryCharacterChatSchema,
    StoryCharacterDiscoverySchema,
    StoryCharactersSchema,
    StorySchema,
    UserSchema,
    VocabularySchema,
    WarningCreateSchema,
    WarningResolutionSchema,
)
from story_cast import (
    build_story_cast,
    extract_character_name,
    normalize_story_characters,
    select_scene_partner,
    select_story_cast_member,
)
from scene_contract import (
    apply_scene_contract,
    normalize_scene_contract,
    resolve_scene_contract,
    validate_scene_contract,
)
from visual_vocabulary_seed import load_visual_context, sync_visual_vocabulary

logger = logging.getLogger(__name__)


def configured_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def route_access_policy(path: str, method: str) -> str:
    normalized_method = method.upper()
    if normalized_method == "OPTIONS":
        return "public"
    if path.startswith("/api/admin/"):
        return "admin"
    if normalized_method == "PUT" and re.fullmatch(
        r"/api/media/characters/[a-zA-Z0-9_-]+", path
    ):
        return "admin"
    if re.fullmatch(r"/api/users/by-account/[^/]+", path):
        return "account_owner"
    if re.fullmatch(r"/api/users/[^/]+/(?:stories|vocabularies)", path):
        return "user_resource_owner"
    if re.fullmatch(r"/api/users/[^/]+(?:/(?:profile|password))?", path) and (
        normalized_method in {"DELETE", "PUT", "PATCH"}
    ):
        return "account_owner"
    if path.startswith("/api/media/"):
        return "authenticated"
    if path == "/api/community/reports" and normalized_method == "POST":
        return "authenticated"
    if path.startswith("/api/stories/") and normalized_method in {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }:
        return "authenticated"
    return "public"

app = FastAPI(
    title="Fairytale Backend",
    description="FastAPI and MongoDB backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def protect_sensitive_routes(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()
    policy = route_access_policy(path, method)
    if policy == "public":
        return await call_next(request)

    user_match = re.fullmatch(r"/api/users/([^/]+)(?:/(?:profile|password))?", path)
    account_lookup_match = re.fullmatch(r"/api/users/by-account/([^/]+)", path)
    user_resource_match = re.fullmatch(
        r"/api/users/([^/]+)/(?:stories|vocabularies)", path
    )

    try:
        auth = verify_access_token(request.headers.get("authorization"))
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication is required."},
        )

    if policy == "admin" and not is_admin_account_id(auth.get("account_id")):
        return JSONResponse(
            status_code=403,
            content={"detail": "Administrator permission is required."},
        )
    if policy == "account_owner" and (user_match or account_lookup_match):
        requested_account_id = (user_match or account_lookup_match).group(1)
        if auth.get("account_id") != requested_account_id:
            return JSONResponse(
                status_code=403,
                content={"detail": "You can only modify your own account."},
            )
    if policy == "user_resource_owner" and user_resource_match:
        requested_user_id = user_resource_match.group(1)
        if str(auth.get("uid") or "") != requested_user_id:
            return JSONResponse(
                status_code=403,
                content={"detail": "You can only access your own data."},
            )
    request.state.auth = auth
    return await call_next(request)


class UserUpdateSchema(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    email_verification_token: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class PasswordChangeSchema(BaseModel):
    current_password: str
    new_password: str


class LikeSchema(BaseModel):
    account_id: Optional[str] = None


class OwnerActionSchema(BaseModel):
    account_id: Optional[str] = None
    user_id: Optional[str] = None


class StoryUpdateSchema(BaseModel):
    user_id: Optional[str] = None
    title: Optional[str] = None


class AdminVisibilitySchema(BaseModel):
    account_id: str
    is_hidden: bool


GENRE_EMOJIS = {
    "?먰?吏": "?룿",
    "紐⑦뿕": "?뿺截?",
    "?곗젙": "?쩃",
    "?먯뿰": "?뙼",
    "?숇Ъ": "?맧",
    "誘몄뒪?곕━": "?뵇",
}

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 120_000
ADMIN_ACCOUNT_ID = "1111"
AUTH_TOKEN_TTL_SECONDS = 24 * 60 * 60
_auth_secret_source = (
    os.getenv("APP_AUTH_SECRET")
    or os.getenv("JWT_SECRET_KEY")
    or secrets.token_urlsafe(48)
)
AUTH_TOKEN_SECRET = hashlib.sha256(
    f"fairytale-auth-v1|{_auth_secret_source}".encode("utf-8")
).digest()
MEDIA_JOB_SYNC_INTERVAL_SECONDS = 5
MEDIA_GENERATION_WORKER_INTERVAL_SECONDS = 2
MEDIA_JOB_STALE_SECONDS = 15 * 60
MEDIA_JOB_HEARTBEAT_SECONDS = max(
    10,
    int(os.getenv("MEDIA_JOB_HEARTBEAT_SECONDS", "30")),
)
MEDIA_MAX_ACTIVE_JOBS_PER_USER = max(
    1,
    int(os.getenv("MEDIA_MAX_ACTIVE_JOBS_PER_USER", "3")),
)
MEDIA_GENERATION_WORKER_ID = f"fastapi-{secrets.token_hex(4)}"
media_job_sync_task: Optional[asyncio.Task] = None
media_generation_worker_task: Optional[asyncio.Task] = None
media_enqueue_locks: Dict[str, asyncio.Lock] = {}
notice_email_tasks: set[asyncio.Task] = set()


def is_admin_account_id(account_id: Optional[str]) -> bool:
    return str(account_id or "").strip() == ADMIN_ACCOUNT_ID


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMAIL_VERIFICATION_TTL_MINUTES = max(
    3,
    int(os.getenv("EMAIL_VERIFICATION_TTL_MINUTES", "10")),
)
EMAIL_VERIFICATION_EXPOSE_CODE = (
    os.getenv("EMAIL_VERIFICATION_EXPOSE_CODE", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)


def normalize_email(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="올바른 이메일 주소를 입력해 주세요.")
    return normalized


def safe_normalize_email(value: Optional[str]) -> Optional[str]:
    try:
        return normalize_email(value)
    except HTTPException:
        logger.warning("Ignoring malformed stored email address: %r", value)
        return None


def _secret_digest(value: str) -> str:
    return hmac.new(
        AUTH_TOKEN_SECRET,
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _smtp_settings() -> Dict[str, Any]:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = (os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return {
        "host": host,
        "port": port,
        "sender": sender,
        "username": os.getenv("SMTP_USER", "").strip(),
        "password": password,
        "use_tls": use_tls,
    }


def smtp_is_configured() -> bool:
    settings = _smtp_settings()
    return bool(settings["host"] and settings["sender"])


def send_smtp_message(*, recipient: str, subject: str, body: str) -> None:
    settings = _smtp_settings()
    if not settings["host"] or not settings["sender"]:
        raise RuntimeError("SMTP_HOST와 SMTP_FROM 설정이 필요합니다.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["sender"]
    message["To"] = recipient
    message.set_content(body)

    if settings["use_tls"]:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if settings["username"] and settings["password"]:
                server.login(settings["username"], settings["password"])
            server.send_message(message)
        return

    with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as server:
        if settings["username"] and settings["password"]:
            server.login(settings["username"], settings["password"])
        server.send_message(message)


async def consume_email_verification_token(email: str, token: Optional[str]) -> None:
    if not token:
        raise HTTPException(
            status_code=400,
            detail="이메일 인증을 완료한 뒤 다시 시도해 주세요.",
        )
    now = datetime.utcnow()
    record = await email_verifications_collection.find_one(
        {
            "email": email,
            "verification_token_hash": _secret_digest(token.strip()),
            "verified_at": {"$ne": None},
            "verification_expires_at": {"$gt": now},
        }
    )
    if not record:
        raise HTTPException(
            status_code=400,
            detail="이메일 인증이 만료되었거나 유효하지 않습니다.",
        )
    await email_verifications_collection.delete_one({"_id": record["_id"]})


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, saved_password: str) -> bool:
    if saved_password.startswith(f"{PASSWORD_ALGORITHM}$"):
        try:
            _, iterations, salt, digest = saved_password.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return hmac.compare_digest(candidate, digest)
        except (ValueError, TypeError):
            return False

    # 湲곗〈 DB???됰Ц?쇰줈 ?ㅼ뼱媛?鍮꾨?踰덊샇??濡쒓렇?몄? ?덉슜?섍퀬, ?깃났 ???댁떆濡??낃렇?덉씠?쒗븳??
    return hmac.compare_digest(saved_password, password)


def issue_access_token(user: Dict[str, Any]) -> str:
    payload = {
        "uid": str(user["_id"]),
        "account_id": str(user.get("account_id") or ""),
        "exp": int(time.time()) + AUTH_TOKEN_TTL_SECONDS,
    }
    payload_bytes = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=")
    signature = hmac.new(AUTH_TOKEN_SECRET, encoded, hashlib.sha256).digest()
    return (
        f"{encoded.decode('ascii')}."
        f"{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"
    )


def verify_access_token(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    encoded, encoded_signature = token.split(".", 1)
    expected = hmac.new(
        AUTH_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    signature = base64.urlsafe_b64decode(
        encoded_signature + "=" * (-len(encoded_signature) % 4)
    )
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid token signature.")
    payload_bytes = base64.urlsafe_b64decode(
        encoded + "=" * (-len(encoded) % 4)
    )
    payload = json.loads(payload_bytes.decode("utf-8"))
    if int(payload.get("exp") or 0) <= int(time.time()):
        raise ValueError("Expired token.")
    if not payload.get("uid") or not payload.get("account_id"):
        raise ValueError("Incomplete token.")
    return payload


def owner_matches(document_user_id, requested_user_id: Optional[str]) -> bool:
    if not requested_user_id:
        return True
    return str(document_user_id) == str(requested_user_id)


def authenticated_user_id(request: Request) -> str:
    auth = getattr(request.state, "auth", None) or {}
    user_id = str(auth.get("uid") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    return user_id


def is_shared_character_asset(metadata: Dict[str, Any]) -> bool:
    asset_role = str(metadata.get("asset_role") or "").strip().lower()
    character_key = str(metadata.get("character_key") or "").strip()
    return asset_role.startswith("character_") and bool(character_key)


async def require_story_owner(story_id: str, request: Request) -> Dict[str, Any]:
    story_object_id = require_object_id(story_id, "story_id")
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    if not owner_matches(story.get("user_id"), authenticated_user_id(request)):
        raise HTTPException(status_code=403, detail="Only the story owner can modify it.")
    return story


async def require_media_job_owner(job: Dict[str, Any], request: Request) -> None:
    user_id = authenticated_user_id(request)
    owner_user_id = str(job.get("owner_user_id") or "").strip()
    if owner_user_id:
        if not owner_matches(owner_user_id, user_id):
            raise HTTPException(status_code=403, detail="Media job access denied.")
        return

    story_id = serialize_object_id(job.get("story_id"))
    if story_id:
        await require_story_owner(story_id, request)
        return

    auth = getattr(request.state, "auth", None) or {}
    if not is_admin_account_id(auth.get("account_id")):
        raise HTTPException(status_code=403, detail="Legacy media job access denied.")


def user_id_filter(user_id: str):
    values = [user_id]
    if ObjectId.is_valid(user_id):
        values.append(ObjectId(user_id))
    return {"$in": values}


def story_id_filter(story_ids: list):
    values = [str(story_id) for story_id in story_ids]
    values.extend(story_ids)
    return {"$in": values}


def require_object_id(value: str, field_name: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}.")
    return ObjectId(value)


def normalize_media_story_target(
    story_id: Optional[str],
    step_number: Optional[int],
    *,
    require_positive_step: bool = False,
):
    normalized_story_id = story_id.strip() if isinstance(story_id, str) else story_id
    if normalized_story_id == "":
        normalized_story_id = None

    has_story_id = normalized_story_id is not None
    has_step_number = step_number is not None
    if has_story_id != has_step_number:
        raise HTTPException(
            status_code=400,
            detail="story_id and step_number must be provided together.",
        )

    if not has_story_id:
        return None, None

    if not ObjectId.is_valid(normalized_story_id):
        raise HTTPException(status_code=400, detail="Invalid story_id.")

    if require_positive_step and step_number <= 0:
        raise HTTPException(
            status_code=400,
            detail="step_number must be greater than 0 for media jobs.",
        )

    return normalized_story_id, step_number


def normalize_character_key(character_key: str) -> str:
    normalized = character_key.strip().lower()
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if (
        not normalized
        or len(normalized) > 64
        or normalized[0] not in set("abcdefghijklmnopqrstuvwxyz0123456789")
        or any(character not in allowed for character in normalized)
    ):
        raise HTTPException(
            status_code=400,
            detail="character_key must use lowercase letters, numbers, hyphens, or underscores.",
        )
    return normalized


def normalize_story_character_overrides(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: Dict[str, str] = {}
    for raw_role, raw_character_key in value.items():
        role = str(raw_role).strip().lower()
        character_key = str(raw_character_key).strip()
        if not role or not character_key:
            continue
        normalized[role[:40]] = normalize_character_key(character_key)
    return normalized


def serialize_character_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": serialize_object_id(profile.get("_id")),
        "character_key": profile.get("character_key"),
        "name": profile.get("name"),
        "gender": profile.get("gender"),
        "age_group": profile.get("age_group"),
        "role_tags": profile.get("role_tags", []),
        "description": profile.get("description"),
        "style_prompt": profile.get("style_prompt"),
        "genres": profile.get("genres", []),
        "assets": profile.get("assets", []),
        "active": bool(profile.get("active", True)),
        "created_at": serialize_optional_datetime(profile.get("created_at")),
        "updated_at": serialize_optional_datetime(profile.get("updated_at")),
    }


async def load_active_character_profile(
    character_key: Optional[str],
    genre: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if character_key:
        normalized = normalize_character_key(character_key)
        return await character_profiles_collection.find_one(
            {"character_key": normalized, "active": True}
        )
    if genre and genre.strip():
        return await character_profiles_collection.find_one(
            {"genres": genre.strip().lower(), "active": True},
            sort=[("updated_at", -1)],
        )
    return None


async def load_semantic_partner_profile(
    primary_character_key: Optional[str],
    genre: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    query: Dict[str, Any] = {
        "active": True,
        "assets.0": {"$exists": True},
    }
    normalized_primary = str(primary_character_key or "").strip().lower()
    if normalized_primary:
        query["character_key"] = {"$ne": normalized_primary}

    if genre and genre.strip():
        genre_match = await character_profiles_collection.find_one(
            {**query, "genres": genre.strip().lower()},
            sort=[("updated_at", -1), ("character_key", 1)],
        )
        if genre_match:
            return genre_match
    return await character_profiles_collection.find_one(
        query,
        sort=[("updated_at", -1), ("character_key", 1)],
    )


async def ensure_active_character_profile(character_key: Optional[str]) -> None:
    if character_key and not await load_active_character_profile(character_key):
        raise HTTPException(status_code=404, detail="Active character profile not found.")


async def ensure_story_character_profile(
    story_id: Optional[str],
    character_key: Optional[str],
) -> None:
    if not story_id:
        return
    story_cast = await load_story_cast(story_id)
    if not character_key or not str(character_key).strip():
        raise HTTPException(
            status_code=409,
            detail="Story media requests must include the story's locked character_key.",
        )
    normalized_key = str(character_key).strip().lower()
    allowed_keys = {
        str(member.get("character_key") or "").strip().lower()
        for member in story_cast
        if isinstance(member, dict)
    }
    if normalized_key not in allowed_keys:
        raise HTTPException(
            status_code=409,
            detail="Selected character does not belong to this story cast.",
        )


async def build_persistent_story_cast(
    characters: Dict[str, str],
    genre: Optional[str],
    character_overrides: Optional[Dict[str, str]] = None,
) -> list:
    normalized = normalize_story_characters(characters)
    if not normalized:
        return []
    overrides = normalize_story_character_overrides(character_overrides)
    profiles = await character_profiles_collection.find(
        {"active": True, "assets.0": {"$exists": True}}
    ).to_list(length=100)
    available_keys = {
        str(profile.get("character_key") or "").strip().lower()
        for profile in profiles
    }
    unavailable = sorted(set(overrides.values()).difference(available_keys))
    if unavailable:
        raise HTTPException(
            status_code=409,
            detail="Selected character profile is not available.",
        )
    return build_story_cast(
        normalized,
        profiles,
        genre=genre,
        character_overrides=overrides,
    )


async def load_story_cast_member(
    story_id: Optional[str],
    story_text: str,
) -> Optional[Dict[str, Any]]:
    story_cast = await load_story_cast(story_id)
    return select_story_cast_member(story_cast, story_text)


async def load_story_cast(story_id: Optional[str]) -> list:
    if not story_id or not ObjectId.is_valid(story_id):
        return []
    story = await stories_collection.find_one(
        {"_id": ObjectId(story_id)},
        {
            "story_cast": 1,
            "characters": 1,
            "character_overrides": 1,
            "genre": 1,
        },
    )
    if not story:
        return []
    story_cast = (story or {}).get("story_cast")
    if isinstance(story_cast, list) and story_cast:
        return story_cast

    characters = normalize_story_characters((story or {}).get("characters"))
    overrides = normalize_story_character_overrides(
        (story or {}).get("character_overrides")
    )
    if not characters and overrides:
        characters = {
            role: "The selected story character"
            for role in overrides
            if role != "key_item"
        }
    if not characters:
        characters = {"hero": "Legacy story hero"}

    migrated_cast = await build_persistent_story_cast(
        characters,
        (story or {}).get("genre"),
        overrides,
    )
    if migrated_cast:
        await stories_collection.update_one(
            {"_id": ObjectId(story_id)},
            {
                "$set": {
                    "story_cast": migrated_cast,
                    "characters": characters,
                    "character_identity_locked": True,
                    "schema_version": 2,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
    return migrated_cast


async def ensure_story_scene_exists(story_id: str, step_number: int):
    story = await stories_collection.find_one(
        {"_id": ObjectId(story_id), "scenes.step_number": step_number},
        {"_id": 1},
    )
    if not story:
        raise HTTPException(status_code=404, detail="Scene not found for this story.")


def _media_job_request_value(job: Dict[str, Any], key: str, default: Any = None) -> Any:
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    return job.get(key) if job.get(key) is not None else request_payload.get(key, default)


def _media_file_extension(content_type: Optional[str]) -> str:
    normalized = (content_type or "").split(";")[0].strip().lower()
    if normalized == "image/jpeg":
        return "jpg"
    if normalized == "image/webp":
        return "webp"
    if normalized == "image/gif":
        return "gif"
    if normalized == "video/mp4":
        return "mp4"
    if normalized == "video/webm":
        return "webm"
    return "png"


async def upload_generated_media_file(
    *,
    content: bytes,
    content_type: str,
    media_kind: str,
    job_id: Optional[str] = None,
    story_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    step_number: Optional[int] = None,
    provider: str = "huggingface",
    model: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    extension = _media_file_extension(content_type)
    token = job_id or secrets.token_hex(12)
    filename = f"{media_kind}_{token}.{extension}"
    metadata = {
        "content_type": content_type,
        "media_kind": media_kind,
        "provider": provider,
        "model": model,
        "job_id": job_id,
        "story_id": story_id,
        "owner_user_id": owner_user_id,
        "step_number": step_number,
        "created_at": datetime.utcnow().isoformat(),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    file_id = await media_files_bucket.upload_from_stream(
        filename,
        content,
        metadata=metadata,
    )
    file_id_text = serialize_object_id(file_id)
    return {
        "file_id": file_id_text,
        "url": build_media_file_url(file_id_text, media_kind),
    }


def inspect_generated_media(
    content: bytes,
    *,
    content_type: str,
    metadata: Optional[Dict[str, Any]] = None,
    expected_character_key: Optional[str] = None,
    expected_asset_fingerprint: Optional[str] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the model-free quality gate on generated bytes before GridFS upload."""

    media_kind = "video" if content_type.lower().startswith("video/") else "image"
    suffix = ".mp4" if media_kind == "video" else ".png"
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(content or b"")
            temporary_path = Path(handle.name)
        return evaluate_media_quality(
            temporary_path,
            media_kind,
            metadata=metadata,
            expected_character_key=expected_character_key,
            expected_asset_fingerprint=expected_asset_fingerprint,
            thresholds=thresholds,
        )
    finally:
        if temporary_path is not None:
            with suppress(FileNotFoundError):
                temporary_path.unlink()


def bind_scene_contract_participants(
    contract: Dict[str, Any],
    *,
    primary_member: Optional[Dict[str, Any]],
    secondary_member: Optional[Dict[str, Any]],
    story_cast: list,
    environment_only: bool,
) -> Dict[str, Any]:
    """Bind a scene contract to persisted cast keys before media generation."""

    bound = dict(contract)
    declared = [
        dict(item)
        for item in (bound.get("participants") or [])
        if isinstance(item, dict) and item.get("character_key")
    ]
    allowed_keys = {
        str(member.get("character_key") or "").strip().lower()
        for member in story_cast
        if isinstance(member, dict) and member.get("character_key")
    }
    for member in (primary_member, secondary_member):
        if isinstance(member, dict) and member.get("character_key"):
            allowed_keys.add(str(member["character_key"]).strip().lower())

    if declared:
        declared_keys = {
            str(item.get("character_key") or "").strip().lower()
            for item in declared
        }
        if any(key not in allowed_keys for key in declared_keys):
            bound["validation_errors"] = ["participant_not_in_story_cast"]
            bound["valid"] = False
            return bound
        participants = declared
    elif environment_only:
        participants = []
    else:
        participants = []
        for member in (primary_member, secondary_member):
            if isinstance(member, dict) and member.get("character_key"):
                participants.append(
                    {
                        "character_key": str(member["character_key"]).strip(),
                        "role": member.get("role"),
                    }
                )

    bound["participants"] = participants
    bound["character_keys"] = [item["character_key"] for item in participants]
    bound["participant_roles"] = {
        item["character_key"]: item.get("role")
        for item in participants
        if item.get("character_key") and item.get("role")
    }
    bound["participant_count"] = len(participants)
    bound["validation_errors"] = validate_scene_contract(bound)
    bound["valid"] = not bound["validation_errors"]
    return bound


async def download_gridfs_file(file_id: str) -> bytes:
    object_id = coerce_object_id(file_id)
    if object_id is None:
        raise ValueError(f"Invalid GridFS file id: {file_id}")
    grid_out = await media_files_bucket.open_download_stream(object_id)
    chunks = []
    try:
        while True:
            chunk = await grid_out.readchunk()
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        close = getattr(grid_out, "close", None)
        if callable(close):
            close()
    return b"".join(chunks)


async def download_profile_motion_sheet(
    profile: Optional[Dict[str, Any]],
) -> tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    asset = select_character_motion_sheet(profile)
    file_id = (asset or {}).get("image_file_id")
    if not file_id:
        return asset, None
    try:
        content = await download_gridfs_file(str(file_id))
    except Exception as exc:
        logger.warning(
            "Character motion sheet download failed for %s: %s",
            (profile or {}).get("character_key"),
            exc,
        )
        return asset, None
    return asset, content


async def download_profile_target_journey_sheet(
    profile: Optional[Dict[str, Any]],
) -> tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    asset = select_character_target_journey_sheet(profile)
    file_id = (asset or {}).get("image_file_id")
    if not file_id:
        return asset, None
    try:
        content = await download_gridfs_file(str(file_id))
    except Exception as exc:
        logger.warning(
            "Character target journey sheet download failed for %s: %s",
            (profile or {}).get("character_key"),
            exc,
        )
        return asset, None
    return asset, content


async def download_profile_run_cycle_sheet(
    profile: Optional[Dict[str, Any]],
) -> tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    asset = select_character_run_cycle_sheet(profile)
    file_id = (asset or {}).get("image_file_id")
    if not file_id:
        return asset, None
    try:
        content = await download_gridfs_file(str(file_id))
    except Exception as exc:
        logger.warning(
            "Character run cycle sheet download failed for %s: %s",
            (profile or {}).get("character_key"),
            exc,
        )
        return asset, None
    return asset, content


async def download_profile_jump_cycle_sheet(
    profile: Optional[Dict[str, Any]],
) -> tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    asset = select_character_jump_cycle_sheet(profile)
    file_id = (asset or {}).get("image_file_id")
    if not file_id:
        return asset, None
    try:
        content = await download_gridfs_file(str(file_id))
    except Exception as exc:
        logger.warning(
            "Character jump cycle sheet download failed for %s: %s",
            (profile or {}).get("character_key"),
            exc,
        )
        return asset, None
    return asset, content


async def download_profile_action_sheet(
    profile: Optional[Dict[str, Any]],
) -> tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    asset = select_character_action_sheet(profile)
    file_id = (asset or {}).get("image_file_id")
    if not file_id:
        return asset, None
    try:
        content = await download_gridfs_file(str(file_id))
    except Exception as exc:
        logger.warning(
            "Character action sheet download failed for %s: %s",
            (profile or {}).get("character_key"),
            exc,
        )
        return asset, None
    return asset, content


async def download_profile_action_cycle_sheet(
    profile: Optional[Dict[str, Any]],
    action: str,
) -> tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    asset = select_character_action_cycle_sheet(profile, action)
    file_id = (asset or {}).get("image_file_id")
    if not file_id:
        return asset, None
    try:
        content = await download_gridfs_file(str(file_id))
    except Exception as exc:
        logger.warning(
            "Character %s cycle sheet download failed for %s: %s",
            action,
            (profile or {}).get("character_key"),
            exc,
        )
        return asset, None
    return asset, content


async def generate_composite_scene(
    *,
    selected_character_asset: Dict[str, Any],
    secondary_character_asset: Optional[Dict[str, Any]] = None,
    genre: Optional[str],
    story_text: str,
    width: int,
    height: int,
    visual_context: Optional[Dict[str, Any]] = None,
    background_asset: Optional[Dict[str, Any]] = None,
    include_video: bool = True,
) -> Dict[str, Any]:
    image_file_id = selected_character_asset.get("image_file_id")
    if not image_file_id:
        raise ValueError("Selected character asset has no GridFS image_file_id.")
    background_asset = background_asset or select_background_asset(
        genre,
        story_text,
        visual_context=visual_context,
    )
    if not background_asset:
        raise FileNotFoundError(f"No local background is available for genre: {genre}")

    secondary_image_file_id = (
        secondary_character_asset.get("image_file_id")
        if secondary_character_asset
        else None
    )
    downloads = [
        download_gridfs_file(str(image_file_id)),
        asyncio.to_thread(background_asset["path"].read_bytes),
    ]
    if include_video:
        downloads.append(asyncio.to_thread(background_asset["video_path"].read_bytes))
    if secondary_image_file_id:
        downloads.append(download_gridfs_file(str(secondary_image_file_id)))
    downloaded = await asyncio.gather(*downloads)
    character_bytes, background_bytes = downloaded[:2]
    video_background_bytes = downloaded[2] if include_video else None
    secondary_index = 3 if include_video else 2
    secondary_character_bytes = (
        downloaded[secondary_index] if len(downloaded) > secondary_index else None
    )
    image_bytes = await asyncio.to_thread(
        compose_story_scene,
        background_bytes,
        character_bytes,
        secondary_character_bytes=secondary_character_bytes,
        effect_tags=(visual_context or {}).get("effect_tags", []),
        prop_tags=(visual_context or {}).get("prop_tags", []),
        width=width,
        height=height,
    )
    return {
        "image_bytes": image_bytes,
        "background_bytes": background_bytes,
        "video_background_bytes": video_background_bytes,
        "character_bytes": character_bytes,
        "secondary_character_bytes": secondary_character_bytes,
        "content_type": "image/png",
        "provider": "local-composite",
        "model": "storybook-asset-compositor-v1",
        "inference_provider": "local",
        "attempted_providers": [],
        "image_mode": "local_composite",
        "background_key": background_asset["key"],
        "background_source": "bundled_asset",
        "video_background_source": background_asset["video_source"],
        "video_background_filename": background_asset["video_path"].name,
    }


async def generate_background_only_scene(
    *,
    genre: Optional[str],
    story_text: str,
    width: int,
    height: int,
    visual_context: Optional[Dict[str, Any]] = None,
    background_asset: Optional[Dict[str, Any]] = None,
    include_video: bool = True,
) -> Dict[str, Any]:
    background_asset = background_asset or select_background_asset(
        genre,
        story_text,
        visual_context=visual_context,
    )
    if not background_asset:
        raise FileNotFoundError(f"No local background is available for genre: {genre}")

    background_bytes = await asyncio.to_thread(background_asset["path"].read_bytes)
    video_background_bytes = None
    if include_video:
        video_background_bytes = await asyncio.to_thread(
            background_asset["video_path"].read_bytes
        )
    image_bytes = await asyncio.to_thread(
        compose_background_scene,
        background_bytes,
        effect_tags=(visual_context or {}).get("effect_tags", []),
        width=width,
        height=height,
    )
    return {
        "image_bytes": image_bytes,
        "background_bytes": background_bytes,
        "video_background_bytes": video_background_bytes,
        "character_bytes": None,
        "secondary_character_bytes": None,
        "content_type": "image/png",
        "provider": "local-background",
        "model": "storybook-background-compositor-v1",
        "inference_provider": "local",
        "attempted_providers": [],
        "image_mode": "local_background_only",
        "background_key": background_asset["key"],
        "background_source": "bundled_asset",
        "video_background_source": background_asset["video_source"],
        "video_background_filename": background_asset["video_path"].name,
    }


async def generate_and_store_backend_media(
    *,
    story_text: str,
    story_id: Optional[str] = None,
    step_number: Optional[int] = None,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    character_key: Optional[str] = None,
    scene_contract: Optional[Dict[str, Any]] = None,
    include_video: bool = False,
    width: int = 512,
    height: int = 512,
    flux_steps: int = 1,
    video_width: int = 960,
    video_height: int = 480,
    num_frames: int = 180,
    video_steps: int = 2,
    frame_rate: Optional[int] = None,
    seed: Optional[int] = None,
    job_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    started_at = time.monotonic()
    provided_contract = normalize_scene_contract(
        scene_contract,
        character_key=character_key,
        source="explicit" if scene_contract else "derived",
    )
    if scene_contract is not None and not provided_contract["valid"]:
        raise HfMediaError(
            "Scene contract contains unsupported values: "
            + ", ".join(provided_contract["validation_errors"])
        )
    contract_character_key = provided_contract.get("character_key")
    if character_key and contract_character_key and (
        str(character_key).strip().lower() != str(contract_character_key).strip().lower()
    ):
        raise HfMediaError(
            "Scene contract character_key does not match the selected character."
        )
    if not character_key and contract_character_key:
        character_key = contract_character_key
    story_cast = await load_story_cast(story_id)
    visual_context: Dict[str, Any] = {}
    try:
        visual_context = await load_visual_context(story_text)
    except Exception:
        logger.exception(
            "Visual vocabulary matching failed for media job %s; using base selection.",
            job_id,
        )
    if scene_contract is not None:
        visual_context = apply_scene_contract(visual_context, provided_contract)
    action_semantics = visual_context.get("action_semantics") or {}
    environment_only = action_semantics.get("participant_count") == 0
    story_cast_member = None
    if not environment_only:
        requested_key = str(character_key or "").strip().lower()
        if requested_key:
            story_cast_member = next(
                (
                    member
                    for member in story_cast
                    if isinstance(member, dict)
                    and str(member.get("character_key") or "").strip().lower()
                    == requested_key
                ),
                None,
            )
        if story_cast_member is None and not requested_key:
            story_cast_member = select_story_cast_member(
                story_cast,
                story_text,
            )
    if story_id and not environment_only and not story_cast:
        raise HfMediaError(
            "Story character selection is not initialized. Save the selected cast before generating media."
        )
    if story_id and not environment_only and (
        not story_cast_member or not story_cast_member.get("character_key")
    ):
        raise HfMediaError(
            "The story does not have a usable selected character profile."
        )
    if story_cast_member and story_cast_member.get("character_key"):
        story_character_key = str(story_cast_member["character_key"])
        if character_key and character_key.strip().lower() != story_character_key.strip().lower():
            raise HfMediaError(
                "Selected character does not match the story's locked character."
            )
        character_key = story_character_key
    if not story_id and not character_key and not environment_only:
        raise HfMediaError(
            "Character scenes require a selected character profile when no story is provided."
        )
    character_profile = await load_active_character_profile(
        character_key,
        None if environment_only else genre,
    )
    if character_key and not character_profile:
        raise HfMediaError(f"Active character profile not found: {character_key}")
    selected_background_asset = select_background_asset(
        genre,
        story_text,
        visual_context=visual_context,
    )
    asset_motion_plan = build_video_motion_plan(
        story_text=story_text,
        scene_action=provided_contract.get("action"),
        scene_target=provided_contract.get("target"),
        directionality=provided_contract.get("background_direction"),
        action_tags=visual_context.get("action_tags", []),
        effect_tags=visual_context.get("effect_tags", []),
        motion_modifier_tags=visual_context.get("motion_modifier_tags", []),
        required_props=(
            visual_context.get("prop_tags", [])
            or provided_contract.get("required_props", [])
        ),
        visual_anchor=provided_contract.get("visual_anchor"),
        background_key=(selected_background_asset or {}).get("key"),
        action_semantics=visual_context.get("action_semantics", {}),
        ensemble_profile=visual_context.get("ensemble_profile") or {},
    )
    selected_character_asset = select_character_asset(
        character_profile,
        story_text,
        visual_context=visual_context,
        preferred_pose=asset_motion_plan.get("preferred_asset_pose"),
        preferred_emotion=asset_motion_plan.get("preferred_asset_emotion"),
        prefer_premium_reference=True,
    )
    if not environment_only and not selected_character_asset:
        raise HfMediaError(
            "The selected character profile has no usable scene asset. "
            "Generation stopped to preserve character identity."
        )
    secondary_story_cast_member = select_scene_partner(
        story_cast,
        story_cast_member,
        str(asset_motion_plan.get("action") or ""),
        requires_partner=bool(asset_motion_plan.get("requires_partner")),
    )
    secondary_character_profile = None
    secondary_character_asset = None
    if selected_character_asset:
        secondary_character_key = (secondary_story_cast_member or {}).get(
            "character_key"
        )
        if secondary_character_key:
            secondary_character_profile = await load_active_character_profile(
                str(secondary_character_key),
                genre,
            )
        if (
            asset_motion_plan.get("requires_partner")
            and not secondary_character_profile
            and not story_id
        ):
            secondary_character_profile = await load_semantic_partner_profile(
                (character_profile or {}).get("character_key"),
                genre,
            )
            if secondary_character_profile:
                secondary_story_cast_member = {
                    "role": asset_motion_plan.get("partner_role") or "partner",
                    "name": secondary_character_profile.get("name"),
                    "character_key": secondary_character_profile.get(
                        "character_key"
                    ),
                    "selection_source": "semantic_auto",
                }
        secondary_preferences = {
            "battle": ("default", "angry"),
            "rescue": ("default", "sad"),
            "interaction": ("talking", "friendly"),
            "conversation": ("talking", "friendly"),
        }
        secondary_pose, secondary_emotion = secondary_preferences.get(
            str(asset_motion_plan.get("action") or ""),
            (None, None),
        )
        secondary_character_asset = select_character_asset(
            secondary_character_profile,
            story_text,
            visual_context=visual_context,
            preferred_pose=secondary_pose,
            preferred_emotion=secondary_emotion,
            prefer_premium_reference=True,
        )

    resolved_scene_contract = resolve_scene_contract(
        story_text=story_text,
        visual_context=visual_context,
        motion_plan=asset_motion_plan,
        character_key=character_key,
        explicit=scene_contract,
    )
    resolved_scene_contract = bind_scene_contract_participants(
        resolved_scene_contract,
        primary_member=story_cast_member,
        secondary_member=secondary_story_cast_member,
        story_cast=story_cast,
        environment_only=environment_only,
    )
    if not resolved_scene_contract["valid"]:
        raise HfMediaError(
            "Scene contract could not be resolved: "
            + ", ".join(resolved_scene_contract["validation_errors"])
        )
    if resolved_scene_contract["action"] != asset_motion_plan["action"]:
        raise HfMediaError(
            "Scene contract action and motion plan disagree; media generation was stopped."
        )

    # Keep the selected face/reference anchor attached to every scene asset.
    character_identity_context = {}
    if character_profile:
        profile_anchor = identity_context_from_profile(character_profile)
        character_identity_context = build_character_identity_context(
            character_key=character_profile.get("character_key"),
            face_asset=profile_anchor.get("face_asset"),
            image_file_id=profile_anchor.get("image_file_id"),
            asset_version=profile_anchor.get("asset_version"),
            fingerprint=profile_anchor.get("asset_fingerprint"),
            asset=selected_character_asset,
            profile=character_profile,
        )
        selected_character_asset = with_character_identity(
            selected_character_asset,
            character_identity_context,
        )

    secondary_character_identity_context = {}
    if secondary_character_profile:
        profile_anchor = identity_context_from_profile(secondary_character_profile)
        secondary_character_identity_context = build_character_identity_context(
            character_key=secondary_character_profile.get("character_key"),
            face_asset=profile_anchor.get("face_asset"),
            image_file_id=profile_anchor.get("image_file_id"),
            asset_version=profile_anchor.get("asset_version"),
            fingerprint=profile_anchor.get("asset_fingerprint"),
            asset=secondary_character_asset,
            profile=secondary_character_profile,
        )
        secondary_character_asset = with_character_identity(
            secondary_character_asset,
            secondary_character_identity_context,
        )
    if (
        include_video
        and asset_motion_plan.get("requires_partner")
        and not secondary_character_asset
    ):
        source_word = asset_motion_plan.get("semantic_source_word") or "This action"
        raise HfMediaError(
            f"{source_word} requires two active character profiles for video generation."
    )
    composite_error = None
    if environment_only:
        try:
            generated = await generate_background_only_scene(
                genre=genre,
                story_text=story_text,
                width=width,
                height=height,
                visual_context=visual_context,
                background_asset=selected_background_asset,
                include_video=include_video,
            )
        except Exception as exc:
            composite_error = str(exc)
            logger.warning(
                "Local environment composition failed for media job %s; using HF fallback: %s",
                job_id,
                composite_error,
            )
            generated = await generate_hf_fairytale_image(
                story_text=story_text,
                genre=genre,
                age=age,
                character_action_hint=build_character_action_hint(
                    None,
                    visual_context=visual_context,
                ),
                width=width,
                height=height,
                steps=flux_steps,
                seed=seed,
            )
            generated["image_mode"] = "hf_environment_fallback"
    elif selected_character_asset:
        try:
            generated = await generate_composite_scene(
                selected_character_asset=selected_character_asset,
                secondary_character_asset=secondary_character_asset,
                genre=genre,
                story_text=story_text,
                width=width,
                height=height,
                visual_context=visual_context,
                background_asset=selected_background_asset,
                include_video=include_video,
            )
        except Exception as exc:
            composite_error = str(exc)
            logger.exception(
                "Character-preserving composition failed for media job %s.",
                job_id,
            )
            raise HfMediaError(
                "Character-preserving scene composition failed; retry the media job."
            ) from exc
    else:
        raise HfMediaError(
            "Character-preserving image generation requires a selected scene asset."
        )

    video_generated = None
    video_error = None
    video_task = None
    character_motion_sheet_asset = None
    secondary_motion_sheet_asset = None
    character_target_journey_sheet_asset = None
    character_run_cycle_sheet_asset = None
    character_jump_cycle_sheet_asset = None
    character_action_sheet_asset = None
    character_battle_cycle_sheet_asset = None
    character_magic_cycle_sheet_asset = None
    character_interaction_cycle_sheet_asset = None
    character_sit_cycle_sheet_asset = None
    character_stand_cycle_sheet_asset = None
    character_crawl_cycle_sheet_asset = None
    character_climb_cycle_sheet_asset = None
    character_motion_sheet_bytes = None
    secondary_motion_sheet_bytes = None
    character_target_journey_sheet_bytes = None
    character_run_cycle_sheet_bytes = None
    character_jump_cycle_sheet_bytes = None
    character_action_sheet_bytes = None
    character_battle_cycle_sheet_bytes = None
    character_magic_cycle_sheet_bytes = None
    character_interaction_cycle_sheet_bytes = None
    character_sit_cycle_sheet_bytes = None
    character_stand_cycle_sheet_bytes = None
    character_crawl_cycle_sheet_bytes = None
    character_climb_cycle_sheet_bytes = None
    action_fx_sheet_bytes = None
    motion_asset_load_names: list[str] = []
    if include_video:
        planned_action = str(asset_motion_plan.get("action") or "")
        pace = str(asset_motion_plan.get("pace") or "walk")
        dedicated_cycle_action = (
            pace
            if planned_action == "journey" and pace in {"crawl", "climb"}
            else "interaction" if planned_action == "rescue" else planned_action
        )
        dedicated_cycle_actions = (
            (dedicated_cycle_action,)
            if dedicated_cycle_action in {
                "battle", "magic", "interaction", "sit", "stand", "crawl", "climb",
            }
            else ()
        )
        dedicated_asset_available = bool(
            dedicated_cycle_actions
            and select_character_action_cycle_sheet(
                character_profile,
                dedicated_cycle_action,
            )
        )
        action_asset_available = bool(
            planned_action in {"wave", "magic", "battle", "rescue", "investigate", "interaction"}
            and select_character_action_sheet(character_profile)
        )
        target_asset_available = bool(
            planned_action == "journey"
            and pace in {"walk", "run"}
            and asset_motion_plan.get("target") != "scene"
            and select_character_target_journey_sheet(character_profile)
        )
        run_asset_available = bool(
            planned_action == "journey"
            and pace in {"walk", "run"}
            and select_character_run_cycle_sheet(character_profile)
        )
        jump_asset_available = bool(
            planned_action == "jump"
            and select_character_jump_cycle_sheet(character_profile)
        )
        use_dedicated_asset = dedicated_asset_available
        use_action_asset = not use_dedicated_asset and action_asset_available
        use_run_asset = bool(
            not use_dedicated_asset
            and not use_action_asset
            and run_asset_available
            and (pace == "run" or not target_asset_available)
        )
        use_target_asset = bool(
            not use_dedicated_asset
            and not use_action_asset
            and not use_run_asset
            and target_asset_available
        )
        use_jump_asset = bool(
            not use_dedicated_asset
            and not use_action_asset
            and jump_asset_available
        )
        use_generic_asset = not any(
            (use_dedicated_asset, use_action_asset, use_run_asset, use_target_asset, use_jump_asset)
        )
        load_secondary_motion = bool(
            secondary_character_profile and planned_action != "interaction"
        )
        action_fx_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "effects"
            / "action_fx_sheet_v23.png"
        )
        if planned_action in {
            "journey", "jump", "magic", "battle", "rescue", "interaction",
        } and action_fx_path.is_file():
            action_fx_sheet_bytes = await asyncio.to_thread(action_fx_path.read_bytes)
        motion_jobs = []

        def add_motion_job(name: str, coroutine):
            motion_jobs.append((name, coroutine))

        if use_generic_asset:
            add_motion_job("generic", download_profile_motion_sheet(character_profile))
        if load_secondary_motion:
            add_motion_job(
                "secondary",
                download_profile_motion_sheet(secondary_character_profile),
            )
        if use_target_asset:
            add_motion_job(
                "target",
                download_profile_target_journey_sheet(character_profile),
            )
        if use_run_asset:
            add_motion_job("run", download_profile_run_cycle_sheet(character_profile))
        if use_jump_asset:
            add_motion_job("jump", download_profile_jump_cycle_sheet(character_profile))
        if use_action_asset:
            add_motion_job("action", download_profile_action_sheet(character_profile))
        if use_dedicated_asset:
            add_motion_job(
                f"cycle:{dedicated_cycle_action}",
                download_profile_action_cycle_sheet(
                    character_profile,
                    dedicated_cycle_action,
                ),
            )

        motion_sheet_results = await asyncio.gather(
            *(coroutine for _, coroutine in motion_jobs)
        )
        motion_asset_load_names = [name for name, _ in motion_jobs]
        for (name, _), result in zip(motion_jobs, motion_sheet_results):
            asset, content = result
            if name == "generic":
                character_motion_sheet_asset, character_motion_sheet_bytes = asset, content
            elif name == "secondary":
                secondary_motion_sheet_asset, secondary_motion_sheet_bytes = asset, content
            elif name == "target":
                character_target_journey_sheet_asset, character_target_journey_sheet_bytes = asset, content
            elif name == "run":
                character_run_cycle_sheet_asset, character_run_cycle_sheet_bytes = asset, content
            elif name == "jump":
                character_jump_cycle_sheet_asset, character_jump_cycle_sheet_bytes = asset, content
            elif name == "action":
                character_action_sheet_asset, character_action_sheet_bytes = asset, content
            elif name == f"cycle:{dedicated_cycle_action}":
                cycle_asset, cycle_bytes = asset, content
                action = dedicated_cycle_action
                if action == "battle":
                    character_battle_cycle_sheet_asset = cycle_asset
                    character_battle_cycle_sheet_bytes = cycle_bytes
                elif action == "magic":
                    character_magic_cycle_sheet_asset = cycle_asset
                    character_magic_cycle_sheet_bytes = cycle_bytes
                elif action == "interaction":
                    character_interaction_cycle_sheet_asset = cycle_asset
                    character_interaction_cycle_sheet_bytes = cycle_bytes
                elif action == "sit":
                    character_sit_cycle_sheet_asset = cycle_asset
                    character_sit_cycle_sheet_bytes = cycle_bytes
                elif action == "stand":
                    character_stand_cycle_sheet_asset = cycle_asset
                    character_stand_cycle_sheet_bytes = cycle_bytes
                elif action == "crawl":
                    character_crawl_cycle_sheet_asset = cycle_asset
                    character_crawl_cycle_sheet_bytes = cycle_bytes
                elif action == "climb":
                    character_climb_cycle_sheet_asset = cycle_asset
                    character_climb_cycle_sheet_bytes = cycle_bytes
        selected_motion_asset = next(
            (
                asset
                for asset in (
                    character_jump_cycle_sheet_asset,
                    character_battle_cycle_sheet_asset,
                    character_magic_cycle_sheet_asset,
                    character_interaction_cycle_sheet_asset,
                    character_sit_cycle_sheet_asset,
                    character_stand_cycle_sheet_asset,
                    character_crawl_cycle_sheet_asset,
                    character_climb_cycle_sheet_asset,
                    character_action_sheet_asset,
                    character_run_cycle_sheet_asset,
                    character_target_journey_sheet_asset,
                    character_motion_sheet_asset,
                )
                if asset
            ),
            None,
        )
        selected_quality_tier = str(
            (selected_motion_asset or {}).get("quality_tier") or ""
        )
        version_match = re.search(r"(_v\d+)$", selected_quality_tier)
        motion_asset_version = version_match.group(1)[1:] if version_match else None
        video_task = asyncio.create_task(generate_hf_fairytale_video(
            image_bytes=(
                generated.get("video_background_bytes")
                if environment_only
                else generated["image_bytes"]
            ) or generated["image_bytes"],
            story_text=story_text,
            genre=genre,
            age=age,
            width=video_width,
            height=video_height,
            num_frames=num_frames,
            steps=video_steps,
            seed=seed,
            frame_rate=frame_rate,
            motion_context={
                "background_bytes": (
                    generated.get("video_background_bytes")
                    or generated.get("background_bytes")
                ),
                "character_bytes": generated.get("character_bytes"),
                "secondary_character_bytes": generated.get("secondary_character_bytes"),
                "character_motion_sheet_bytes": character_motion_sheet_bytes,
                "secondary_character_motion_sheet_bytes": secondary_motion_sheet_bytes,
                "character_target_journey_sheet_bytes": (
                    character_target_journey_sheet_bytes
                ),
                "character_run_cycle_sheet_bytes": character_run_cycle_sheet_bytes,
                "character_jump_cycle_sheet_bytes": character_jump_cycle_sheet_bytes,
                "character_action_sheet_bytes": character_action_sheet_bytes,
                "character_battle_cycle_sheet_bytes": character_battle_cycle_sheet_bytes,
                "character_magic_cycle_sheet_bytes": character_magic_cycle_sheet_bytes,
                "character_interaction_cycle_sheet_bytes": (
                    character_interaction_cycle_sheet_bytes
                ),
                "character_sit_cycle_sheet_bytes": character_sit_cycle_sheet_bytes,
                "character_stand_cycle_sheet_bytes": character_stand_cycle_sheet_bytes,
                "character_crawl_cycle_sheet_bytes": character_crawl_cycle_sheet_bytes,
                "character_climb_cycle_sheet_bytes": character_climb_cycle_sheet_bytes,
                "motion_asset_version": motion_asset_version,
                "action_fx_sheet_bytes": action_fx_sheet_bytes,
                "character_key": (character_profile or {}).get("character_key"),
                "secondary_character_key": (
                    secondary_character_profile or {}
                ).get("character_key"),
                "character_pose": (
                    selected_character_asset.get("pose")
                    if selected_character_asset
                    else None
                ),
                "action_tags": visual_context.get("action_tags", []),
                "effect_tags": visual_context.get("effect_tags", []),
                "motion_modifier_tags": visual_context.get(
                    "motion_modifier_tags", []
                ),
                "action_semantics": visual_context.get("action_semantics", {}),
                "ensemble_profile": visual_context.get("ensemble_profile") or {},
                "scene_contract": resolved_scene_contract,
                "background_key": generated.get("background_key"),
                "motion_focus": visual_context.get("motion_focus", "character"),
            },
        ))

    identity_metadata = {
        key: value
        for key, value in {
            "character_key": (character_profile or {}).get("character_key"),
            "asset_fingerprint": character_identity_context.get(
                "asset_fingerprint"
            ),
        }.items()
        if value
    }
    image_quality_report = inspect_generated_media(
        generated["image_bytes"],
        content_type=generated["content_type"],
        metadata=identity_metadata,
        expected_character_key=(character_profile or {}).get("character_key"),
        expected_asset_fingerprint=character_identity_context.get(
            "asset_fingerprint"
        ),
    )
    if not image_quality_report["passed"]:
        reasons = ", ".join(
            str(reason.get("code"))
            for reason in image_quality_report.get("reasons", [])
        )
        raise HfMediaError(
            f"Generated image failed the quality gate: {reasons or 'unknown_error'}"
        )

    image_file = await upload_generated_media_file(
        content=generated["image_bytes"],
        content_type=generated["content_type"],
        media_kind="image",
        job_id=job_id,
        story_id=story_id,
        owner_user_id=owner_user_id,
        step_number=step_number,
        provider=generated["provider"],
        model=generated["model"],
        extra_metadata={
            "character_key": (character_profile or {}).get("character_key"),
            "asset_fingerprint": character_identity_context.get(
                "asset_fingerprint"
            ),
            "asset_version": character_identity_context.get("asset_version"),
            "quality_gate_passed": True,
        },
    )

    video_quality_report = None
    if video_task is not None:
        try:
            video_generated = await video_task
            video_quality_report = inspect_generated_media(
                video_generated["video_bytes"],
                content_type=video_generated["content_type"],
                metadata=identity_metadata,
                expected_character_key=(character_profile or {}).get(
                    "character_key"
                ),
                expected_asset_fingerprint=character_identity_context.get(
                    "asset_fingerprint"
                ),
                thresholds=(
                    {"min_motion_score": 0.0}
                    if str(asset_motion_plan.get("action") or "")
                    in {"idle", "sit", "stand"}
                    else None
                ),
            )
            if not video_quality_report["passed"]:
                reasons = ", ".join(
                    str(reason.get("code"))
                    for reason in video_quality_report.get("reasons", [])
                )
                video_error = (
                    "Video failed the quality gate: "
                    f"{reasons or 'unknown_error'}"
                )
                video_generated = None
        except HfMediaError as exc:
            video_error = str(exc)
            logger.warning("Video generation failed for media job %s: %s", job_id, video_error)
        except Exception as exc:
            video_error = str(exc)
            logger.exception("Unexpected video generation failure for media job %s.", job_id)

    image_file_id = image_file["file_id"]
    image_url = image_file["url"]
    video_file_id = None
    video_url = None
    if video_generated is not None:
        video_file = await upload_generated_media_file(
            content=video_generated["video_bytes"],
            content_type=video_generated["content_type"],
            media_kind="video",
            job_id=job_id,
            story_id=story_id,
            owner_user_id=owner_user_id,
            step_number=step_number,
            provider=video_generated["provider"],
            model=video_generated["model"],
            extra_metadata={
                "character_key": (character_profile or {}).get("character_key"),
                "asset_fingerprint": character_identity_context.get(
                    "asset_fingerprint"
                ),
                "asset_version": character_identity_context.get("asset_version"),
                "quality_gate_passed": bool(
                    video_quality_report and video_quality_report["passed"]
                ),
            },
        )
        video_file_id = video_file["file_id"]
        video_url = video_file["url"]

    scene_saved = False
    if story_id is not None and step_number is not None:
        scene_media_status = (
            "partial" if include_video and not video_url else "completed"
        )
        scene_saved = await persist_scene_media(
            story_id=story_id,
            step_number=step_number,
            scene_contract=resolved_scene_contract,
            image_url=image_url,
            video_url=video_url,
            image_file_id=image_file_id,
            video_file_id=video_file_id,
            media_job_id=job_id,
            media_status=scene_media_status,
            media_error=video_error if scene_media_status == "partial" else None,
            expected_media_job_id=job_id,
        )

    elapsed_seconds = round(time.monotonic() - started_at, 2)
    video_status = "not_requested"
    if include_video:
        video_status = "completed" if video_url else "failed"
    metadata = {
        "image_model": generated["model"],
        "character_key": (character_profile or {}).get("character_key"),
        "character_name": (character_profile or {}).get("name"),
        "story_cast_role": (story_cast_member or {}).get("role"),
        "character_selection_source": (
            (story_cast_member or {}).get("selection_source")
        ),
        "story_character_name": (story_cast_member or {}).get("name"),
        "story_character_description": (story_cast_member or {}).get(
            "source_description"
        ),
        "character_identity_locked": bool(story_cast_member),
        "character_identity_context": character_identity_context or None,
        "secondary_character_identity_context": (
            secondary_character_identity_context or None
        ),
        "character_asset_version": character_identity_context.get(
            "asset_version"
        ),
        "character_asset_fingerprint": character_identity_context.get(
            "asset_fingerprint"
        ),
        "quality_gate": {
            "image": image_quality_report,
            "video": video_quality_report,
            "status": (
                "passed"
                if image_quality_report.get("passed")
                and (video_quality_report is None or video_quality_report.get("passed"))
                else "partial"
            ),
        },
        "scene_contract": resolved_scene_contract,
        "contract_validation": {
            "character_locked": bool(
                (character_profile or {}).get("character_key")
                and (
                    not story_cast_member
                    or story_cast_member.get("character_key")
                    == (character_profile or {}).get("character_key")
                )
            ),
            "action_locked": resolved_scene_contract["action"]
            == asset_motion_plan["action"],
            "direction_locked": bool(
                resolved_scene_contract.get("background_direction")
            ),
            "required_props_declared": bool(
                resolved_scene_contract.get("required_props")
            ),
            "status": "metadata_only",
            "pixel_validation": "not_run",
        },
        "character_asset_count": len((character_profile or {}).get("assets", [])),
        "selected_character_asset": (
            {
                "pose": selected_character_asset.get("pose"),
                "emotion": selected_character_asset.get("emotion"),
                "image_file_id": selected_character_asset.get("image_file_id"),
                "image_url": selected_character_asset.get("image_url"),
                "asset_version": selected_character_asset.get("asset_version"),
                "asset_fingerprint": selected_character_asset.get(
                    "asset_fingerprint"
                ),
            }
            if selected_character_asset
            else None
        ),
        "image_provider": generated.get("inference_provider"),
        "image_provider_attempts": generated.get("attempted_providers", []),
        "image_mode": generated.get("image_mode", "hf_full_scene"),
        "environment_only": environment_only,
        "background_key": generated.get("background_key"),
        "background_source": generated.get("background_source"),
        "video_background_source": generated.get("video_background_source"),
        "video_background_filename": generated.get("video_background_filename"),
        "composite_fallback_error": composite_error,
        "visual_vocabulary": {
            "matched_words": visual_context.get("matched_words", []),
            "background_keys": visual_context.get("background_keys", []),
            "action_tags": visual_context.get("action_tags", []),
            "action_semantics": visual_context.get("action_semantics", {}),
            "ensemble_profile": visual_context.get("ensemble_profile") or {},
            "emotion_tags": visual_context.get("emotion_tags", []),
            "effect_tags": visual_context.get("effect_tags", []),
            "prop_tags": visual_context.get("prop_tags", []),
            "motion_modifier_tags": visual_context.get(
                "motion_modifier_tags", []
            ),
            "match_score": visual_context.get("match_score", 0),
        },
        "video_model": video_generated["model"] if video_generated else None,
        "video_provider": video_generated["provider"] if video_generated else None,
        "provider": generated["provider"],
        "elapsed_seconds": elapsed_seconds,
        "width": width,
        "height": height,
        "steps": flux_steps,
        "include_video_requested": include_video,
        "video_width": video_width,
        "video_height": video_height,
        "num_frames": num_frames,
        "video_steps": video_steps,
        "frame_rate": (
            video_generated["parameters"].get("frame_rate")
            if video_generated and isinstance(video_generated.get("parameters"), dict)
            else frame_rate
        ),
        "video_status": video_status,
        "motion_assets_loaded": motion_asset_load_names,
        "video_background_loaded": bool(generated.get("video_background_bytes")),
        "video_error": video_error,
        "video_parameters": video_generated.get("parameters") if video_generated else None,
        "video_animation_mode": (
            video_generated.get("parameters", {}).get("animation_mode")
            if video_generated
            else None
        ),
        "character_motion_sheet": (
            {
                "image_file_id": character_motion_sheet_asset.get("image_file_id"),
                "image_url": character_motion_sheet_asset.get("image_url"),
                "quality_tier": character_motion_sheet_asset.get("quality_tier"),
            }
            if character_motion_sheet_asset
            else None
        ),
        "secondary_motion_sheet": (
            {
                "image_file_id": secondary_motion_sheet_asset.get("image_file_id"),
                "image_url": secondary_motion_sheet_asset.get("image_url"),
                "quality_tier": secondary_motion_sheet_asset.get("quality_tier"),
            }
            if secondary_motion_sheet_asset
            else None
        ),
        "character_target_journey_sheet": (
            {
                "image_file_id": character_target_journey_sheet_asset.get(
                    "image_file_id"
                ),
                "image_url": character_target_journey_sheet_asset.get("image_url"),
                "quality_tier": character_target_journey_sheet_asset.get(
                    "quality_tier"
                ),
            }
            if character_target_journey_sheet_asset
            else None
        ),
        "character_run_cycle_sheet": (
            {
                "image_file_id": character_run_cycle_sheet_asset.get(
                    "image_file_id"
                ),
                "image_url": character_run_cycle_sheet_asset.get("image_url"),
                "quality_tier": character_run_cycle_sheet_asset.get(
                    "quality_tier"
                ),
            }
            if character_run_cycle_sheet_asset
            else None
        ),
        "character_crawl_cycle_sheet": (
            {
                "image_file_id": character_crawl_cycle_sheet_asset.get(
                    "image_file_id"
                ),
                "image_url": character_crawl_cycle_sheet_asset.get("image_url"),
                "quality_tier": character_crawl_cycle_sheet_asset.get(
                    "quality_tier"
                ),
            }
            if character_crawl_cycle_sheet_asset
            else None
        ),
        "character_climb_cycle_sheet": (
            {
                "image_file_id": character_climb_cycle_sheet_asset.get(
                    "image_file_id"
                ),
                "image_url": character_climb_cycle_sheet_asset.get("image_url"),
                "quality_tier": character_climb_cycle_sheet_asset.get(
                    "quality_tier"
                ),
            }
            if character_climb_cycle_sheet_asset
            else None
        ),
        "character_action_sheet": (
            {
                "image_file_id": character_action_sheet_asset.get("image_file_id"),
                "image_url": character_action_sheet_asset.get("image_url"),
                "quality_tier": character_action_sheet_asset.get("quality_tier"),
            }
            if character_action_sheet_asset
            else None
        ),
        "scene_partner_role": (secondary_story_cast_member or {}).get("role"),
        "scene_partner_name": (secondary_story_cast_member or {}).get("name"),
        "secondary_character_key": (
            (secondary_character_profile or {}).get("character_key")
        ),
        "secondary_selected_character_asset": (
            {
                "pose": secondary_character_asset.get("pose"),
                "emotion": secondary_character_asset.get("emotion"),
                "image_file_id": secondary_character_asset.get("image_file_id"),
                "image_url": secondary_character_asset.get("image_url"),
                "asset_version": secondary_character_asset.get("asset_version"),
                "asset_fingerprint": secondary_character_asset.get(
                    "asset_fingerprint"
                ),
            }
            if secondary_character_asset
            else None
        ),
        "video_motion_plan": (
            video_generated.get("parameters", {}).get("motion_plan")
            if video_generated
            else None
        ),
        "saved": scene_saved,
    }
    result = {
        "job_id": job_id,
        "prompt_id": job_id,
        "provider": generated["provider"],
        "image_file_id": image_file_id,
        "video_file_id": video_file_id,
        "image_url": image_url,
        "video_url": video_url,
        "elapsed_seconds": elapsed_seconds,
        "saved": scene_saved,
        "metadata": metadata,
    }
    return {
        "result": result,
        "metadata": metadata,
        "image_file_id": image_file_id,
        "image_url": image_url,
        "video_file_id": video_file_id,
        "video_url": video_url,
        "provider": generated["provider"],
        "scene_saved": scene_saved,
    }


async def execute_media_generation(
    *,
    story_text: str,
    story_id: Optional[str] = None,
    step_number: Optional[int] = None,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    character_key: Optional[str] = None,
    scene_contract: Optional[Dict[str, Any]] = None,
    include_video: bool = False,
    width: int = 512,
    height: int = 512,
    flux_steps: int = 1,
    video_width: int = 960,
    video_height: int = 480,
    num_frames: int = 180,
    video_steps: int = 2,
    frame_rate: Optional[int] = None,
    owner_user_id: Optional[str] = None,
):
    media = await generate_and_store_backend_media(
        story_text=story_text,
        story_id=story_id,
        step_number=step_number,
        genre=genre,
        age=age,
        character_key=character_key,
        scene_contract=scene_contract,
        include_video=include_video,
        width=width,
        height=height,
        flux_steps=flux_steps,
        video_width=video_width,
        video_height=video_height,
        num_frames=num_frames,
        video_steps=video_steps,
        frame_rate=frame_rate,
        owner_user_id=owner_user_id,
    )
    result = media["result"]
    return {**result, "saved": media["scene_saved"]}


def build_active_media_job_key(
    owner_user_id: str,
    story_id: Optional[str],
    step_number: Optional[int],
) -> Optional[str]:
    if not story_id or step_number is None:
        return None
    return f"{owner_user_id}:{story_id}:{step_number}"


def build_media_job_cache_key(
    payload: MediaGenerationWithStorySchema,
    *,
    story_id: Optional[str],
    step_number: Optional[int],
) -> str:
    contract = (
        payload.scene_contract.model_dump(exclude_none=True)
        if payload.scene_contract
        else None
    )
    return build_media_cache_key(
        request={
            "story_id": story_id,
            "step_number": step_number,
            "story_text": payload.story_text,
            "genre": payload.genre,
            "age": payload.age,
            "character_key": payload.character_key,
            "scene_contract": contract,
            "include_video": payload.include_video,
            "width": payload.width,
            "height": payload.height,
            "flux_steps": payload.flux_steps,
            "video_width": payload.video_width,
            "video_height": payload.video_height,
            "num_frames": payload.num_frames,
            "video_steps": payload.video_steps,
            "frame_rate": payload.frame_rate,
            "video_timeout": payload.video_timeout,
        }
    )


def media_job_request_matches(
    job: Dict[str, Any],
    payload: MediaGenerationWithStorySchema,
) -> bool:
    expected = payload.model_dump(exclude={"story_id", "step_number"})
    return all(
        _media_job_request_value(job, key) == value
        for key, value in expected.items()
    )


def build_media_job_document(
    payload: MediaGenerationWithStorySchema,
    *,
    story_id: Optional[str],
    step_number: Optional[int],
    owner_user_id: str,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    request_payload = {
        "story_id": story_id,
        "step_number": step_number,
        "story_text": payload.story_text,
        "genre": payload.genre,
        "age": payload.age,
        "character_key": payload.character_key,
        "scene_contract": (
            payload.scene_contract.model_dump(exclude_none=True)
            if payload.scene_contract
            else None
        ),
        "include_video": payload.include_video,
        "width": payload.width,
        "height": payload.height,
        "flux_steps": payload.flux_steps,
        "video_width": payload.video_width,
        "video_height": payload.video_height,
        "num_frames": payload.num_frames,
        "video_steps": payload.video_steps,
        "frame_rate": payload.frame_rate,
        "video_timeout": payload.video_timeout,
    }
    cache_key = build_media_job_cache_key(
        payload,
        story_id=story_id,
        step_number=step_number,
    )
    job = {
        "story_id": ObjectId(story_id) if story_id else None,
        "owner_user_id": owner_user_id,
        "step_number": step_number,
        "story_text": payload.story_text,
        "genre": payload.genre,
        "age": payload.age,
        "character_key": payload.character_key,
        "scene_contract": (
            payload.scene_contract.model_dump(exclude_none=True)
            if payload.scene_contract
            else None
        ),
        "include_video": payload.include_video,
        "width": payload.width,
        "height": payload.height,
        "flux_steps": payload.flux_steps,
        "video_width": payload.video_width,
        "video_height": payload.video_height,
        "num_frames": payload.num_frames,
        "video_steps": payload.video_steps,
        "frame_rate": payload.frame_rate,
        "video_timeout": payload.video_timeout,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "worker_id": None,
        "error": None,
        "image_file_id": None,
        "video_file_id": None,
        "image_url": None,
        "video_url": None,
        "provider": None,
        "cache_key": cache_key,
        "request": request_payload,
        "result": None,
        "result_metadata": None,
        "scene_synced_at": None,
        "schema_version": 2,
    }
    active_key = build_active_media_job_key(owner_user_id, story_id, step_number)
    if active_key:
        job["active_key"] = active_key
    return job


async def enqueue_media_job(
    payload: MediaGenerationWithStorySchema,
    *,
    story_id: Optional[str],
    step_number: Optional[int],
    owner_user_id: str,
):
    lock = media_enqueue_locks.setdefault(owner_user_id, asyncio.Lock())
    async with lock:
        cache_key = build_media_job_cache_key(
            payload,
            story_id=story_id,
            step_number=step_number,
        )
        active_key = build_active_media_job_key(
            owner_user_id,
            story_id,
            step_number,
        )
        if active_key:
            existing_job = await media_jobs_collection.find_one(
                {
                    "active_key": active_key,
                    "status": {"$in": ["pending", "running"]},
                }
            )
            if existing_job:
                if not media_job_request_matches(existing_job, payload):
                    raise HTTPException(
                        status_code=409,
                        detail="A different media job is already active for this scene.",
                    )
                if story_id is not None and step_number is not None:
                    await persist_scene_media(
                        story_id=story_id,
                        step_number=step_number,
                        media_job_id=serialize_object_id(existing_job.get("_id")),
                        media_status=str(existing_job.get("status") or "pending"),
                    )
                return serialize_media_job_document(existing_job)

        cached_job = await media_jobs_collection.find_one(
            {
                "owner_user_id": owner_user_id,
                "cache_key": cache_key,
                "status": "completed",
            }
        )
        if cached_job:
            if story_id is not None and step_number is not None:
                await persist_scene_media(
                    story_id=story_id,
                    step_number=step_number,
                    media_job_id=serialize_object_id(cached_job.get("_id")),
                    media_status="completed",
                    image_url=cached_job.get("image_url"),
                    video_url=cached_job.get("video_url"),
                    image_file_id=serialize_object_id(cached_job.get("image_file_id")),
                    video_file_id=serialize_object_id(cached_job.get("video_file_id")),
                )
            return serialize_media_job_document(cached_job)

        active_count = await media_jobs_collection.count_documents(
            {
                "owner_user_id": owner_user_id,
                "status": {"$in": ["pending", "running"]},
            }
        )
        if active_count >= MEDIA_MAX_ACTIVE_JOBS_PER_USER:
            raise HTTPException(
                status_code=429,
                detail="Too many active media jobs. Wait for the current jobs to finish.",
            )

        job = build_media_job_document(
            payload,
            story_id=story_id,
            step_number=step_number,
            owner_user_id=owner_user_id,
        )
        try:
            result = await media_jobs_collection.insert_one(job)
        except DuplicateKeyError:
            existing_job = await media_jobs_collection.find_one(
                {"active_key": active_key}
            )
            if existing_job:
                if not media_job_request_matches(existing_job, payload):
                    raise HTTPException(
                        status_code=409,
                        detail="A different media job is already active for this scene.",
                    )
                if story_id is not None and step_number is not None:
                    await persist_scene_media(
                        story_id=story_id,
                        step_number=step_number,
                        media_job_id=serialize_object_id(existing_job.get("_id")),
                        media_status=str(existing_job.get("status") or "pending"),
                    )
                return serialize_media_job_document(existing_job)
            raise HTTPException(status_code=409, detail="Media job is already active.")

        created_job = await media_jobs_collection.find_one({"_id": result.inserted_id})
        if not created_job:
            raise HTTPException(status_code=500, detail="Media job could not be created.")

        if story_id is not None and step_number is not None:
            job_id = serialize_object_id(result.inserted_id)
            scene_marked = await persist_scene_media(
                story_id=story_id,
                step_number=step_number,
                media_job_id=job_id,
                media_status="pending",
            )
            if not scene_marked:
                now = datetime.utcnow()
                await media_jobs_collection.update_one(
                    {"_id": result.inserted_id},
                    {
                        "$set": {
                            "status": "failed",
                            "updated_at": now,
                            "completed_at": now,
                            "error": "Story scene disappeared before media generation.",
                        },
                        "$unset": {"active_key": ""},
                    },
                )
                raise HTTPException(status_code=404, detail="Scene not found.")

        return serialize_media_job_document(created_job)


async def claim_pending_media_job() -> Optional[Dict[str, Any]]:
    now = datetime.utcnow()
    return await media_jobs_collection.find_one_and_update(
        {"status": "pending"},
        {
            "$set": {
                "status": "running",
                "worker_id": MEDIA_GENERATION_WORKER_ID,
                "started_at": now,
                "updated_at": now,
                "error": None,
            }
        },
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def reset_stale_running_media_jobs() -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=MEDIA_JOB_STALE_SECONDS)
    result = await media_jobs_collection.update_many(
        {
            "status": "running",
            "$or": [
                {"updated_at": {"$lt": cutoff}},
                {
                    "updated_at": None,
                    "started_at": {"$lt": cutoff},
                },
            ],
        },
        {
            "$set": {
                "status": "pending",
                "updated_at": datetime.utcnow(),
                "error": "Requeued stale running media job.",
            },
            "$unset": {
                "worker_id": "",
                "started_at": "",
            },
        },
    )
    return result.modified_count


async def mark_media_job_failed(job: Dict[str, Any], error_message: str) -> None:
    now = datetime.utcnow()
    await media_jobs_collection.update_one(
        {
            "_id": job["_id"],
            "status": "running",
            "worker_id": MEDIA_GENERATION_WORKER_ID,
        },
        {
            "$set": {
                "status": "failed",
                "updated_at": now,
                "completed_at": now,
                "error": error_message,
            },
            "$unset": {"active_key": ""},
        },
    )


async def heartbeat_media_job(job: Dict[str, Any]) -> None:
    while True:
        await asyncio.sleep(MEDIA_JOB_HEARTBEAT_SECONDS)
        result = await media_jobs_collection.update_one(
            {
                "_id": job["_id"],
                "status": "running",
                "worker_id": MEDIA_GENERATION_WORKER_ID,
            },
            {"$set": {"updated_at": datetime.utcnow()}},
        )
        if result.matched_count == 0:
            return


async def complete_media_job_with_backend_provider(job: Dict[str, Any]) -> None:
    job_id = serialize_object_id(job["_id"])
    story_id = serialize_object_id(_media_job_request_value(job, "story_id"))
    step_number = _media_job_request_value(job, "step_number")
    include_video = bool(_media_job_request_value(job, "include_video", False))
    heartbeat_task = asyncio.create_task(heartbeat_media_job(job))
    try:
        generated = await generate_and_store_backend_media(
            story_text=str(_media_job_request_value(job, "story_text", "")),
            story_id=story_id,
            step_number=step_number,
            genre=_media_job_request_value(job, "genre"),
            age=_media_job_request_value(job, "age"),
            character_key=_media_job_request_value(job, "character_key"),
            scene_contract=_media_job_request_value(job, "scene_contract"),
            include_video=include_video,
            width=int(_media_job_request_value(job, "width", 512)),
            height=int(_media_job_request_value(job, "height", 512)),
            flux_steps=int(_media_job_request_value(job, "flux_steps", 1)),
            video_width=int(_media_job_request_value(job, "video_width", 960)),
            video_height=int(_media_job_request_value(job, "video_height", 480)),
            num_frames=int(_media_job_request_value(job, "num_frames", 180)),
            video_steps=int(_media_job_request_value(job, "video_steps", 2)),
            frame_rate=(
                int(_media_job_request_value(job, "frame_rate"))
                if _media_job_request_value(job, "frame_rate") is not None
                else None
            ),
            seed=_media_job_request_value(job, "seed"),
            job_id=job_id,
            owner_user_id=str(job.get("owner_user_id") or "") or None,
        )
    finally:
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task

    now = datetime.utcnow()
    image_object_id = coerce_object_id(generated["image_file_id"])
    video_object_id = coerce_object_id(generated["video_file_id"])
    video_failed = include_video and not generated.get("video_url")
    final_status = "partial" if video_failed else "completed"
    video_error = (generated.get("metadata") or {}).get("video_error")
    result = await media_jobs_collection.update_one(
        {
            "_id": job["_id"],
            "status": "running",
            "worker_id": MEDIA_GENERATION_WORKER_ID,
        },
        {
            "$set": {
                "status": final_status,
                "updated_at": now,
                "completed_at": now,
                "error": video_error if video_failed else None,
                "image_file_id": image_object_id or generated["image_file_id"],
                "video_file_id": video_object_id or generated["video_file_id"],
                "image_url": generated["image_url"],
                "video_url": generated["video_url"],
                "provider": generated["provider"],
                "result_metadata": generated["metadata"],
                "result": generated["result"],
                "scene_synced_at": now if generated["scene_saved"] or story_id is None else None,
            },
            "$unset": {"active_key": ""},
        },
    )
    if result.matched_count == 0:
        logger.warning("Media job %s lost its worker lease before completion.", job_id)


async def media_generation_worker_loop() -> None:
    last_stale_check = 0.0
    while True:
        try:
            now = time.monotonic()
            if now - last_stale_check >= 60:
                reset_count = await reset_stale_running_media_jobs()
                if reset_count:
                    logger.info("Requeued %s stale media jobs.", reset_count)
                last_stale_check = now

            job = await claim_pending_media_job()
            if job is None:
                await asyncio.sleep(MEDIA_GENERATION_WORKER_INTERVAL_SECONDS)
                continue

            try:
                await complete_media_job_with_backend_provider(job)
            except (HfMediaError, Exception) as exc:
                logger.exception("Media job %s failed.", job.get("_id"))
                await mark_media_job_failed(job, str(exc))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Media generation worker loop failed.")
            await asyncio.sleep(MEDIA_GENERATION_WORKER_INTERVAL_SECONDS)


async def sync_story_scene_for_job(job: Dict[str, Any]) -> Dict[str, Any]:
    if job.get("status") not in {"completed", "partial"}:
        return job

    media_result = extract_media_result(job) or {}
    image_url = media_result.get("image_url")
    video_url = media_result.get("video_url")
    image_file_id = media_result.get("image_file_id")
    video_file_id = media_result.get("video_file_id")
    update_fields: Dict[str, Any] = {}

    if image_url and job.get("image_url") != image_url:
        update_fields["image_url"] = image_url
    if video_url and job.get("video_url") != video_url:
        update_fields["video_url"] = video_url
    if image_file_id and serialize_object_id(job.get("image_file_id")) != image_file_id:
        update_fields["image_file_id"] = ObjectId(image_file_id)
    if video_file_id and serialize_object_id(job.get("video_file_id")) != video_file_id:
        update_fields["video_file_id"] = ObjectId(video_file_id)

    story_id = serialize_object_id(job.get("story_id"))
    if not story_id and not job.get("scene_synced_at"):
        update_fields["scene_synced_at"] = datetime.utcnow()
    elif (
        story_id
        and job.get("step_number") is not None
        and not job.get("scene_synced_at")
        and (image_url or video_url)
    ):
        scene_saved = await persist_scene_media(
            story_id=story_id,
            step_number=job["step_number"],
            scene_contract=(job.get("result_metadata") or {}).get("scene_contract"),
            image_url=image_url,
            video_url=video_url,
            image_file_id=image_file_id,
            video_file_id=video_file_id,
            media_job_id=serialize_object_id(job.get("_id")),
            media_status=str(job.get("status") or "completed"),
            media_error=job.get("error"),
            expected_media_job_id=serialize_object_id(job.get("_id")),
        )
        update_fields["scene_synced_at"] = datetime.utcnow()
        if not scene_saved:
            update_fields["scene_sync_status"] = "skipped_superseded"

    if not update_fields:
        return job

    update_fields["updated_at"] = datetime.utcnow()
    await media_jobs_collection.update_one(
        {"_id": job["_id"]},
        {"$set": update_fields},
    )
    return {**job, **update_fields}


async def load_media_job(job_id: str, *, sync_scene: bool = True) -> Dict[str, Any]:
    job = await media_jobs_collection.find_one({"_id": require_object_id(job_id, "job_id")})
    if not job:
        raise HTTPException(status_code=404, detail="Media job not found.")
    if sync_scene:
        job = await sync_story_scene_for_job(job)
    return job


async def sync_completed_media_jobs_batch(limit: int = 20) -> None:
    cursor = media_jobs_collection.find(
        {
            "status": {"$in": ["completed", "partial"]},
            "$or": [
                {"scene_synced_at": None},
                {"scene_synced_at": {"$exists": False}},
            ],
        }
    ).sort("completed_at", 1).limit(limit)

    async for job in cursor:
        try:
            await sync_story_scene_for_job(job)
        except Exception:
            logger.exception("Failed to sync completed media job %s", job.get("_id"))


async def media_job_sync_loop() -> None:
    while True:
        try:
            await sync_completed_media_jobs_batch()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Media job sync loop failed.")
        await asyncio.sleep(MEDIA_JOB_SYNC_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_event():
    global media_job_sync_task, media_generation_worker_task
    await init_database()
    try:
        seeded_characters = await seed_default_character_profiles()
        logger.info("Seeded %s default character profiles.", seeded_characters)
    except Exception:
        logger.exception("Default character profile seeding failed.")
    try:
        visual_sync = await sync_visual_vocabulary()
        logger.info("Visual vocabulary sync completed: %s", visual_sync)
    except Exception:
        logger.exception("Visual vocabulary sync failed; base media selection remains active.")
    if media_job_sync_task is None or media_job_sync_task.done():
        media_job_sync_task = asyncio.create_task(media_job_sync_loop())
    if media_generation_worker_task is None or media_generation_worker_task.done():
        media_generation_worker_task = asyncio.create_task(media_generation_worker_loop())


@app.on_event("shutdown")
async def shutdown_event():
    global media_job_sync_task, media_generation_worker_task
    tasks = [
        media_job_sync_task,
        media_generation_worker_task,
        *list(notice_email_tasks),
    ]
    for task in tasks:
        if task is None:
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    media_job_sync_task = None
    media_generation_worker_task = None
    notice_email_tasks.clear()


async def require_admin(account_id: Optional[str]):
    if not is_admin_account_id(account_id):
        raise HTTPException(status_code=403, detail="愿由ъ옄 沅뚰븳???꾩슂?⑸땲??")

    admin = await users_collection.find_one({"account_id": ADMIN_ACCOUNT_ID})
    if not admin:
        raise HTTPException(status_code=404, detail="愿由ъ옄 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")


async def soft_delete_user_account(
    user: Dict[str, Any],
    *,
    reason: Optional[str],
    deleted_by: str,
) -> Dict[str, Any]:
    user_id = str(user["_id"])
    old_account_id = user.get("account_id")
    now = datetime.utcnow()
    anonymized_fields = build_soft_delete_fields(
        user_id,
        reason=reason,
        deleted_by=deleted_by,
        now=now,
    )

    story_result = await stories_collection.update_many(
        {"user_id": user_id_filter(user_id)},
        {
            "$set": {
                "author_nickname": DELETED_NICKNAME,
                "owner_deleted": True,
                "owner_deleted_at": now,
                "updated_at": now,
            }
        },
    )
    vocabulary_result = await vocabularies_collection.delete_many(
        {"user_id": user_id_filter(user_id)}
    )

    anonymized_posts = 0
    anonymized_comment_threads = 0
    if old_account_id:
        post_result = await community_posts_collection.update_many(
            {"author_account_id": old_account_id},
            {
                "$set": {
                    "author_name": DELETED_NICKNAME,
                    "author_account_id": None,
                    "author_deleted": True,
                    "author_deleted_at": now,
                }
            },
        )
        anonymized_posts = post_result.modified_count
        comment_result = await community_posts_collection.update_many(
            {"comments.author_account_id": old_account_id},
            {
                "$set": {
                    "comments.$[comment].author_name": DELETED_NICKNAME,
                    "comments.$[comment].author_account_id": None,
                    "comments.$[comment].author_deleted": True,
                }
            },
            array_filters=[{"comment.author_account_id": old_account_id}],
        )
        anonymized_comment_threads = comment_result.modified_count
        await community_posts_collection.update_many(
            {"liked_by": old_account_id},
            {
                "$pull": {"liked_by": old_account_id},
                "$inc": {"like_count": -1, "likes": -1},
            },
        )
        await reports_collection.update_many(
            {"reporter_account_id": old_account_id},
            {
                "$set": {
                    "reporter_account_id": None,
                    "reporter_deleted": True,
                }
            },
        )

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": anonymized_fields},
    )
    return {
        "user_id": user_id,
        "status": "deleted",
        "anonymized_stories": story_result.modified_count,
        "deleted_vocabularies": vocabulary_result.deleted_count,
        "anonymized_posts": anonymized_posts,
        "anonymized_comment_threads": anonymized_comment_threads,
        "deleted_at": now,
    }


def serialize_admin_user(user: dict, story_count: int = 0, vocab_count: int = 0):
    return {
        "id": str(user["_id"]),
        "account_id": user.get("account_id"),
        "nickname": user.get("nickname", "?대쫫 ?놁쓬"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "address": user.get("address"),
        "provider": user.get("provider", "local"),
        "personality_type": user.get("personality_type", "Unknown"),
        "created_at": serialize_optional_datetime(user.get("created_at")),
        "last_login": serialize_optional_datetime(user.get("last_login")),
        "story_count": story_count,
        "vocab_count": vocab_count,
        "account_status": user.get("account_status", "active"),
        "warning_count": int(user.get("warning_count", 0) or 0),
        "report_count": int(user.get("report_count", 0) or 0),
        "deleted_at": serialize_optional_datetime(user.get("deleted_at")),
    }


def serialize_admin_story(story: dict):
    scenes = story.get("scenes", [])
    comments = story.get("comments", [])
    return {
        "id": str(story["_id"]),
        "user_id": str(story.get("user_id", "")),
        "author_nickname": story.get("author_nickname", "?숉솕 移쒓뎄"),
        "title": story.get("title", "?쒕ぉ ?녿뒗 ?숉솕"),
        "genre": story.get("genre", "?숉솕"),
        "target_age": story.get("target_age") or story.get("age", ""),
        "scene_count": len(scenes),
        "is_shared": bool(story.get("is_shared", False)),
        "likes": int(story.get("likes", 0) or 0),
        "comment_count": len(comments),
        "created_at": serialize_optional_datetime(story.get("created_at")),
        "updated_at": serialize_optional_datetime(story.get("updated_at")),
    }


def serialize_admin_post(post: dict):
    serialized = serialize_post(post)
    serialized["is_hidden"] = bool(post.get("is_hidden", False))
    serialized["moderation_status"] = post.get("moderation_status", "visible")
    serialized["report_count"] = int(post.get("report_count", 0) or 0)
    return serialized


def serialize_notice(notice: dict, *, include_delivery_error: bool = False) -> Dict[str, Any]:
    result = {
        "id": serialize_object_id(notice.get("_id")),
        "title": notice.get("title", "공지사항"),
        "content": notice.get("content", ""),
        "is_pinned": bool(notice.get("is_pinned", False)),
        "is_published": bool(notice.get("is_published", True)),
        "author_account_id": notice.get("author_account_id"),
        "created_at": serialize_optional_datetime(notice.get("created_at")),
        "published_at": serialize_optional_datetime(notice.get("published_at")),
        "updated_at": serialize_optional_datetime(notice.get("updated_at")),
        "email_requested": bool(notice.get("email_requested", False)),
        "email_delivery_status": notice.get("email_delivery_status", "not_requested"),
        "email_recipient_count": int(notice.get("email_recipient_count", 0) or 0),
        "email_sent_count": int(notice.get("email_sent_count", 0) or 0),
        "email_failed_count": int(notice.get("email_failed_count", 0) or 0),
    }
    if include_delivery_error:
        result["email_delivery_error"] = notice.get("email_delivery_error")
    return result


async def deliver_notice_emails(notice_id: ObjectId) -> None:
    notice = await notices_collection.find_one({"_id": notice_id})
    if not notice:
        return
    if not smtp_is_configured():
        await notices_collection.update_one(
            {"_id": notice_id},
            {
                "$set": {
                    "email_delivery_status": "failed",
                    "email_delivery_error": "SMTP_HOST와 SMTP_FROM이 설정되지 않았습니다.",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return

    recipients = await users_collection.find(
        {
            "account_status": {"$ne": "deleted"},
            "email": {"$type": "string", "$ne": ""},
        },
        {"email": 1},
    ).to_list(length=5000)
    recipient_emails = sorted(
        {
            normalized
            for user in recipients
            for normalized in [safe_normalize_email(user.get("email"))]
            if normalized
        }
    )
    await notices_collection.update_one(
        {"_id": notice_id},
        {
            "$set": {
                "email_delivery_status": "sending",
                "email_recipient_count": len(recipient_emails),
                "email_sent_count": 0,
                "email_failed_count": 0,
                "email_delivery_error": None,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    sent_count = 0
    failed_count = 0
    errors = []
    subject = f"[동화 AI] {notice.get('title', '공지사항')}"
    body = str(notice.get("content", "")).strip()
    for recipient in recipient_emails:
        try:
            await asyncio.to_thread(
                send_smtp_message,
                recipient=recipient,
                subject=subject,
                body=body,
            )
            sent_count += 1
        except Exception as exc:
            failed_count += 1
            if len(errors) < 3:
                errors.append(str(exc)[:240])
        await notices_collection.update_one(
            {"_id": notice_id},
            {
                "$set": {
                    "email_sent_count": sent_count,
                    "email_failed_count": failed_count,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    status = "completed" if failed_count == 0 else "completed_with_failures"
    await notices_collection.update_one(
        {"_id": notice_id},
        {
            "$set": {
                "email_delivery_status": status,
                "email_delivery_error": "; ".join(errors) if errors else None,
                "updated_at": datetime.utcnow(),
            }
        },
    )


def schedule_notice_email_delivery(notice_id: ObjectId) -> None:
    task = asyncio.create_task(deliver_notice_emails(notice_id))
    notice_email_tasks.add(task)
    task.add_done_callback(notice_email_tasks.discard)


def _character_emoji(role: str) -> str:
    return {
        "hero": "🧭",
        "target": "🌟",
        "antagonist": "🛡️",
        "companion": "🪽",
        "guide": "🌲",
    }.get(role, "✨")


def _character_personality(member: Dict[str, Any]) -> str:
    description = str(
        member.get("fixed_description")
        or member.get("source_description")
        or "따뜻하고 용감한 마음"
    ).strip()
    return " ".join(description.split())[:180]


def _serialize_story_character(member: Dict[str, Any]) -> Dict[str, str]:
    role = str(member.get("role") or "companion").strip().lower()
    name = str(member.get("name") or member.get("profile_name") or "이야기 속 친구").strip()
    return {
        "name": name[:80],
        "role": role[:40],
        "personality": _character_personality(member),
        "greeting": f"안녕! 나는 {name}야. 우리 모험에서 궁금한 점을 물어봐.",
        "avatar_emoji": _character_emoji(role),
    }


def _parse_legacy_story_characters(story_text: str) -> list[Dict[str, Any]]:
    match = re.search(
        r"\[(?:등장인물|CHARACTERS)\]\s*(\{.*?\})",
        story_text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    try:
        parsed = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    return [
        {
            "role": str(role),
            "name": extract_character_name(str(description)),
            "source_description": str(description),
        }
        for role, description in parsed.items()
        if str(role).strip() not in {"key_item", "item", "location"}
    ][:5]


async def resolve_chat_characters(payload: StoryCharacterDiscoverySchema) -> list[Dict[str, Any]]:
    cast = await load_story_cast(payload.story_id)
    if cast:
        return [_serialize_story_character(member) for member in cast[:5]]
    return [
        _serialize_story_character(member)
        for member in _parse_legacy_story_characters(payload.story_text)
    ]


def _character_chat_reply(character: Dict[str, Any], message: str) -> Dict[str, Any]:
    name = str(character.get("name") or "이야기 속 친구")
    personality = str(character.get("personality") or "따뜻하고 용감한 마음")
    normalized = " ".join(message.split())
    if re.search(r"기분|마음|무서|두려", normalized):
        reply = (
            f"솔직히 조금 떨렸지만, {personality[:70]} 마음을 잃지 않으려고 했어. "
            "친구들과 함께라서 끝까지 용기를 낼 수 있었지."
        )
    elif re.search(r"왜|이유|어째서", normalized):
        reply = (
            f"나는 {name}에게 소중한 것을 지키는 일이 가장 중요하다고 생각했어. "
            "그래서 서두르지 않고 친구들의 이야기를 들은 다음 움직였지."
        )
    elif re.search(r"친구|좋아|고마", normalized):
        reply = "그렇게 물어봐 줘서 정말 고마워! 우리 모험에서 친구의 마음은 가장 큰 힘이었어."
    else:
        reply = (
            f"재미있는 질문이야. 나는 {personality[:90]} 성격으로 그 순간을 지나왔어. "
            "너라면 우리 이야기에서 어떤 선택을 했을지 궁금해!"
        )
    return {
        "reply": reply,
        "suggested_replies": [
            "다시 모험한다면 무엇을 하고 싶어?",
            "가장 고마웠던 친구는 누구야?",
            "나도 용기를 내려면 어떻게 해야 해?",
        ],
    }


@app.post("/story/characters")
async def discover_story_characters(payload: StoryCharacterDiscoverySchema):
    characters = await resolve_chat_characters(payload)
    if not characters:
        characters = [
            {
                "name": "이야기 친구",
                "role": "companion",
                "personality": "이야기를 함께 돌아보고 질문을 들어주는 다정한 친구",
                "greeting": "안녕! 나는 이야기 친구야. 동화에서 궁금했던 걸 물어봐.",
                "avatar_emoji": "✨",
            }
        ]
    return {"story_id": payload.story_id, "characters": characters}


@app.post("/story/character-chat")
async def chat_with_story_character(
    payload: StoryCharacterChatSchema,
    request: Request,
):
    character = {
        "name": str(payload.character.get("name") or "이야기 친구").strip()[:80],
        "personality": str(
            payload.character.get("personality") or "따뜻하고 용감한 마음"
        ).strip()[:240],
    }
    result = _character_chat_reply(character, payload.user_message)

    auth = None
    try:
        auth = verify_access_token(request.headers.get("authorization"))
    except Exception:
        auth = None
    story_id = str(payload.story_id or "").strip() or None
    user_id = str((auth or {}).get("uid") or "guest").strip()
    now = datetime.utcnow()
    if story_id:
        messages = []
        for message in payload.messages[-12:]:
            role = str(message.get("role") or "").strip()
            content = str(message.get("content") or "").strip()
            if role in {"user", "character"} and content:
                messages.append(
                    {
                        "story_id": story_id,
                        "user_id": user_id,
                        "character_name": character["name"],
                        "role": role,
                        "content": content[:2000],
                        "created_at": now,
                        "source": "character_chat",
                    }
                )
        messages.append(
            {
                "story_id": story_id,
                "user_id": user_id,
                "character_name": character["name"],
                "role": "character",
                "content": result["reply"],
                "created_at": now,
                "source": "character_chat",
            }
        )
        if messages:
            await messages_collection.insert_many(messages)
    return result


@app.get("/")
async def root():
    return {"message": "동화 생성 API 서버가 정상적으로 실행 중입니다."}


@app.post("/api/auth/email-verifications/send")
async def send_email_verification(payload: EmailVerificationSendSchema):
    email = normalize_email(payload.email)
    if not email:
        raise HTTPException(status_code=400, detail="이메일 주소를 입력해 주세요.")
    if not smtp_is_configured() and not EMAIL_VERIFICATION_EXPOSE_CODE:
        raise HTTPException(
            status_code=503,
            detail="이메일 발송 설정이 준비되지 않았습니다. 관리자에게 문의해 주세요.",
        )

    now = datetime.utcnow()
    code = f"{secrets.randbelow(1_000_000):06d}"
    await email_verifications_collection.delete_many({"email": email})
    record = {
        "email": email,
        "code_hash": _secret_digest(code),
        "created_at": now,
        "expires_at": now + timedelta(minutes=EMAIL_VERIFICATION_TTL_MINUTES),
        "verification_expires_at": now
        + timedelta(minutes=EMAIL_VERIFICATION_TTL_MINUTES),
        "verified_at": None,
        "verification_token_hash": None,
        "attempts": 0,
    }
    insert_result = await email_verifications_collection.insert_one(record)

    if smtp_is_configured():
        try:
            await asyncio.to_thread(
                send_smtp_message,
                recipient=email,
                subject="[동화 AI] 이메일 인증번호",
                body=(
                    f"인증번호는 {code}입니다.\n"
                    f"{EMAIL_VERIFICATION_TTL_MINUTES}분 안에 입력해 주세요."
                ),
            )
        except Exception as exc:
            await email_verifications_collection.delete_one({"_id": insert_result.inserted_id})
            logger.exception("Email verification delivery failed")
            raise HTTPException(
                status_code=502,
                detail="인증번호 이메일을 발송하지 못했습니다.",
            ) from exc

    response = {
        "message": "인증번호를 이메일로 발송했습니다.",
        "email": email,
        "expires_in_seconds": EMAIL_VERIFICATION_TTL_MINUTES * 60,
    }
    if EMAIL_VERIFICATION_EXPOSE_CODE and not smtp_is_configured():
        response["dev_code"] = code
    return response


@app.post("/api/auth/email-verifications/verify")
async def verify_email_code(payload: EmailVerificationVerifySchema):
    email = normalize_email(payload.email)
    if not email or not payload.code.isdigit():
        raise HTTPException(status_code=400, detail="이메일과 6자리 인증번호를 확인해 주세요.")

    now = datetime.utcnow()
    record = await email_verifications_collection.find_one(
        {"email": email, "expires_at": {"$gt": now}},
        sort=[("created_at", -1)],
    )
    if not record:
        raise HTTPException(status_code=400, detail="인증번호가 만료되었거나 없습니다.")
    if int(record.get("attempts", 0) or 0) >= 5:
        raise HTTPException(status_code=429, detail="인증번호 입력 횟수를 초과했습니다.")
    if not hmac.compare_digest(
        str(record.get("code_hash") or ""),
        _secret_digest(payload.code),
    ):
        await email_verifications_collection.update_one(
            {"_id": record["_id"]},
            {"$inc": {"attempts": 1}},
        )
        raise HTTPException(status_code=400, detail="인증번호가 일치하지 않습니다.")

    verification_token = secrets.token_urlsafe(32)
    await email_verifications_collection.update_one(
        {"_id": record["_id"]},
        {
            "$set": {
                "verified_at": now,
                "verification_token_hash": _secret_digest(verification_token),
                "verification_expires_at": now + timedelta(minutes=10),
            }
        },
    )
    return {
        "message": "이메일 인증이 완료되었습니다.",
        "email": email,
        "verification_token": verification_token,
    }


@app.post("/api/users/register", response_description="Register user")
async def register_user(user: UserSchema):
    if is_admin_account_id(user.account_id):
        raise HTTPException(
            status_code=403,
            detail="The administrator account ID is reserved.",
        )
    email = normalize_email(user.email)
    if user.provider == "local" and email:
        await consume_email_verification_token(email, user.email_verification_token)
    user_dict = user.model_dump(exclude={"email_verification_token"})
    user_dict["email"] = email
    if user_dict.get("password"):
        user_dict["password"] = hash_password(user_dict["password"])
    user_dict.pop("email_verification_token", None)
    user_dict["social_info"] = {
        "provider": user.provider,
        "social_id": user.provider_id or user.account_id,
    }
    user_dict["last_login"] = None
    user_dict["account_status"] = "active"
    user_dict["warning_count"] = 0
    user_dict["report_count"] = 0
    user_dict["schema_version"] = 2

    existing = await users_collection.find_one({"account_id": user.account_id})
    if existing:
        existing_provider = existing.get("provider", "local")
        if user.provider == "local" or existing_provider == "local":
            raise HTTPException(status_code=409, detail="?대? 媛?낅맂 ?꾩씠?붿엯?덈떎.")

        update_fields = {
            key: value
            for key, value in user_dict.items()
            if value is not None and key not in {"created_at", "password"}
        }
        if user.password:
            update_fields["password"] = hash_password(user.password)
        if update_fields:
            await users_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_fields},
            )
        auth_user = {**existing, **update_fields}
        return {
            "message": f"{user.nickname}?? 湲곗〈 怨꾩젙?쇰줈 濡쒓렇?몃릺?덉뒿?덈떎.",
            "account_id": user.account_id,
            "id": str(existing["_id"]),
            "status": "existing",
            "access_token": issue_access_token(auth_user),
            "token_type": "bearer",
        }

    result = await users_collection.insert_one(user_dict)

    if result.inserted_id:
        created_user = {**user_dict, "_id": result.inserted_id}
        return {
            "message": f"{user.nickname}?? ?뚯썝媛?낆씠 ?깃났?곸쑝濡??꾨즺?섏뿀?듬땲??",
            "account_id": user.account_id,
            "id": str(result.inserted_id),
            "status": "created",
            "access_token": issue_access_token(created_user),
            "token_type": "bearer",
        }

    raise HTTPException(status_code=500, detail="?뚯썝媛???곗씠?곕쿋?댁뒪 ??μ뿉 ?ㅽ뙣?덉뒿?덈떎.")


@app.post("/api/users/login", response_description="User login")
async def login_user(login_data: LoginSchema):
    user = await users_collection.find_one({"account_id": login_data.account_id})
    if not user:
        raise HTTPException(status_code=404, detail="媛?낅맂 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")
    if user.get("account_status") == "deleted":
        raise HTTPException(status_code=410, detail="탈퇴한 계정입니다.")

    provider = user.get("provider", "local")
    if provider != "local":
        raise HTTPException(
            status_code=400,
            detail="??怨꾩젙? ?쇰컲 濡쒓렇?몄씠 ?꾨땶 ?뚯뀥 濡쒓렇?몄쓣 ?ъ슜?댁빞 ?⑸땲??",
        )

    saved_password = user.get("password")
    if not saved_password:
        raise HTTPException(status_code=400, detail="鍮꾨?踰덊샇媛 ?ㅼ젙?섏? ?딆? 怨꾩젙?낅땲??")
    saved_password = str(saved_password)

    if not verify_password(login_data.password, saved_password):
        raise HTTPException(status_code=401, detail="鍮꾨?踰덊샇媛 ?쇱튂?섏? ?딆뒿?덈떎.")

    update_fields = {"last_login": datetime.utcnow()}
    if not saved_password.startswith(f"{PASSWORD_ALGORITHM}$"):
        update_fields["password"] = hash_password(login_data.password)

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": update_fields},
    )

    return {
        "message": f'{user.get("nickname", "User")} welcome back.',
        "id": str(user["_id"]),
        "account_id": user.get("account_id"),
        "nickname": user.get("nickname"),
        "email": user.get("email"),
        "provider": provider,
        "phone": user.get("phone"),
        "address": user.get("address"),
        "access_token": issue_access_token(user),
        "token_type": "bearer",
    }


@app.delete("/api/users/{account_id}", response_description="Withdraw user account")
async def withdraw_user_account(
    account_id: str,
    withdrawal: AccountWithdrawalSchema,
):
    user = await users_collection.find_one({"account_id": account_id})
    if not user:
        raise HTTPException(status_code=404, detail="가입된 계정을 찾을 수 없습니다.")
    if is_admin_account_id(user.get("account_id")):
        raise HTTPException(status_code=400, detail="관리자 계정은 탈퇴할 수 없습니다.")
    if user.get("account_status") == "deleted":
        return {
            "message": "이미 탈퇴 처리된 계정입니다.",
            "user_id": str(user["_id"]),
            "status": "deleted",
        }

    if user.get("provider", "local") == "local":
        if not withdrawal.password:
            raise HTTPException(status_code=400, detail="비밀번호를 입력해야 합니다.")
        saved_password = str(user.get("password") or "")
        if not saved_password or not verify_password(withdrawal.password, saved_password):
            raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다.")

    result = await soft_delete_user_account(
        user,
        reason=withdrawal.reason,
        deleted_by="self",
    )
    return {"message": "회원 탈퇴와 개인정보 익명화가 완료되었습니다.", **result}


@app.put("/api/users/{account_id}/profile", response_description="?좎? 異붽? ?뺣낫 ?낅뜲?댄듃")
async def update_user_profile(account_id: str, update_data: UserUpdateSchema):
    existing_user = await users_collection.find_one({"account_id": account_id})
    if not existing_user:
        raise HTTPException(status_code=404, detail="媛?낅맂 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")

    current_email = normalize_email(existing_user.get("email"))
    email_was_sent = "email" in update_data.model_fields_set
    requested_email = (
        normalize_email(update_data.email) if email_was_sent else current_email
    )
    if email_was_sent and requested_email != current_email:
        if requested_email:
            await consume_email_verification_token(
                requested_email,
                update_data.email_verification_token,
            )

        duplicate = await users_collection.find_one(
            {
                "email": requested_email,
                "account_id": {"$ne": account_id},
                "account_status": {"$ne": "deleted"},
            },
            {"_id": 1},
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")

    update_dict = {}
    for key, value in update_data.model_dump(
        exclude={"email_verification_token"},
        exclude_unset=True,
    ).items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        if key == "email":
            value = requested_email
        update_dict[key] = value

    if not update_dict:
        return {
            "message": "?낅뜲?댄듃???뺣낫媛 ?놁뒿?덈떎.",
            "id": str(existing_user["_id"]),
            "account_id": existing_user.get("account_id"),
            "nickname": existing_user.get("nickname"),
            "email": existing_user.get("email"),
            "provider": existing_user.get("provider", "local"),
            "phone": existing_user.get("phone"),
            "address": existing_user.get("address"),
        }

    await users_collection.update_one(
        {"account_id": account_id},
        {"$set": update_dict},
    )

    user = await users_collection.find_one({"account_id": account_id})
    if user:
        return {
            "message": "?꾨줈???뺣낫媛 ??λ릺?덉뒿?덈떎.",
            "id": str(user["_id"]),
            "account_id": user.get("account_id"),
            "nickname": user.get("nickname"),
            "email": user.get("email"),
            "provider": user.get("provider", "local"),
            "phone": user.get("phone"),
            "address": user.get("address"),
        }

    return {"message": "??λ맂 ?댁뿭???녾굅???대? 理쒖떊 ?곹깭?낅땲??"}


@app.patch("/api/users/{account_id}/password", response_description="Change password")
async def change_password(account_id: str, password_data: PasswordChangeSchema):
    user = await users_collection.find_one({"account_id": account_id})
    if not user:
        raise HTTPException(status_code=404, detail="媛?낅맂 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")

    if user.get("provider", "local") != "local":
        raise HTTPException(status_code=400, detail="?뚯뀥 濡쒓렇??怨꾩젙? 鍮꾨?踰덊샇瑜?蹂寃쏀븷 ???놁뒿?덈떎.")

    saved_password = user.get("password")
    if not saved_password or not verify_password(
        password_data.current_password,
        str(saved_password),
    ):
        raise HTTPException(status_code=401, detail="?꾩옱 鍮꾨?踰덊샇媛 ?쇱튂?섏? ?딆뒿?덈떎.")

    new_password = password_data.new_password.strip()
    if len(new_password) < 9:
        raise HTTPException(status_code=400, detail="??鍮꾨?踰덊샇??9???댁긽?댁뼱???⑸땲??")

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": hash_password(new_password)}},
    )
    return {"message": "鍮꾨?踰덊샇媛 蹂寃쎈릺?덉뒿?덈떎."}


@app.get("/api/users/by-account/{account_id}", response_description="怨꾩젙 ID濡??좎? 議고쉶")
async def get_user_by_account(account_id: str):
    user = await users_collection.find_one({"account_id": account_id})
    if not user:
        raise HTTPException(status_code=404, detail="?대떦 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")

    return {
        "id": str(user["_id"]),
        "account_id": user.get("account_id"),
        "nickname": user.get("nickname"),
        "email": user.get("email"),
        "provider": user.get("provider", "local"),
        "phone": user.get("phone"),
        "address": user.get("address"),
    }


def serialize_scene(scene: dict):
    story_text = scene.get("content")
    if story_text is None:
        story_text = scene.get("story_text", "")
    choice_made = scene.get("user_choice")
    if choice_made is None:
        choice_made = scene.get("choice_made")
    return {
        "step_number": scene.get("step_number", 1),
        "story_text": story_text or "",
        "choice_made": choice_made,
        "scene_contract": scene.get("scene_contract"),
        "video_url": scene.get("video_url"),
        "image_url": scene.get("image_url"),
        "media_job_id": serialize_object_id(scene.get("media_job_id")),
        "media_status": scene.get("media_status"),
        "media_error": scene.get("media_error"),
        "created_at": serialize_datetime(scene.get("created_at")),
    }


def serialize_vocabulary(vocab: dict):
    word = vocab.get("word")
    if word is None:
        word = vocab.get("hard", "")
    meaning = vocab.get("meaning")
    if meaning is None:
        meaning = vocab.get("definition", "")
    easy = vocab.get("easy") or meaning
    return {
        "id": str(vocab.get("_id", "")),
        "user_id": str(vocab.get("user_id", "")),
        "origin_story_id": str(vocab.get("origin_story_id", "")),
        "hard": word or "",
        "easy": easy or "",
        "definition": meaning or "",
        "source_story_title": vocab.get("origin_story_title") or vocab.get("source_story_title"),
        "created_at": serialize_datetime(vocab.get("saved_at") or vocab.get("created_at")),
    }


def serialize_story(story: dict, vocabularies: Optional[list] = None):
    scenes = story.get("scenes", [])
    sorted_scenes = sorted(
        scenes,
        key=lambda item: item.get("step_number", 0),
    )
    generation_meta = story.get("generation_meta") or {}
    prompt_inputs = generation_meta.get("prompt_inputs") or {}
    return {
        "id": str(story["_id"]),
        "user_id": str(story.get("user_id", "")),
        "title": story.get("title", "?쒕ぉ ?녿뒗 ?숉솕"),
        "genre": story.get("genre", "?숉솕"),
        "age": story.get("target_age") or story.get("age", ""),
        "prompt": prompt_inputs.get("title", story.get("prompt", story.get("title", ""))),
        "characters": story.get("characters", {}),
        "character_overrides": story.get("character_overrides", {}),
        "story_cast": story.get("story_cast", []),
        "created_at": serialize_datetime(story.get("created_at")),
        "scenes": [serialize_scene(scene) for scene in sorted_scenes],
        "vocab": [serialize_vocabulary(vocab) for vocab in vocabularies or []],
    }


@app.get("/api/users/{user_id}/stories", response_description="?ъ슜???숉솕 紐⑸줉 議고쉶")
async def list_user_stories(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")

    stories = await stories_collection.find({"user_id": user_id_filter(user_id)}).to_list(length=200)
    stories.sort(key=lambda item: serialize_datetime(item.get("created_at")), reverse=True)

    story_ids = [story["_id"] for story in stories]
    vocabularies_by_story = {}
    if story_ids:
        vocabularies = await vocabularies_collection.find(
            {"origin_story_id": story_id_filter(story_ids)},
        ).to_list(length=1000)
        for vocab in vocabularies:
            key = str(vocab.get("origin_story_id", ""))
            vocabularies_by_story.setdefault(key, []).append(vocab)

    return {
        "stories": [
            serialize_story(story, vocabularies_by_story.get(str(story["_id"]), []))
            for story in stories
        ]
    }


@app.post("/api/stories/create", response_description="?덈줈???숉솕 ?몄뀡 ?앹꽦")
async def create_story(story: StorySchema, request: Request):
    if not ObjectId.is_valid(story.user_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")
    if story.user_id != authenticated_user_id(request):
        raise HTTPException(status_code=403, detail="You can only create your own stories.")

    now = story.created_at or datetime.utcnow()
    user = await users_collection.find_one({"_id": ObjectId(story.user_id)})
    characters = normalize_story_characters(story.characters)
    character_overrides = normalize_story_character_overrides(
        story.character_overrides
    )
    story_cast = await build_persistent_story_cast(
        characters,
        story.genre,
        character_overrides,
    )
    story_dict = {
        "user_id": story.user_id,
        "author_nickname": (user or {}).get("nickname", "?숉솕 移쒓뎄"),
        "genre": story.genre,
        "target_age": story.age,
        "difficulty": "蹂댄넻",
        "title": story.title,
        "emoji": GENRE_EMOJIS.get(story.genre, "?뱰"),
        "scenes": [],
        "read_progress": 0,
        "is_shared": False,
        "likes": 0,
        "comments": [],
        "community_post_id": None,
        "characters": characters,
        "character_overrides": character_overrides,
        "story_cast": story_cast,
        "character_identity_locked": bool(story_cast),
        "generation_status": "completed",
        "generation_meta": {
            "text_model": "fairytale-app",
            "tts_enabled": False,
            "image_pipeline": "external",
            "video_pipeline": "external",
            "prompt_inputs": {
                "genre": story.genre,
                "target_age": story.age,
                "difficulty": "蹂댄넻",
                "title": story.prompt or story.title,
            },
        },
        "created_at": now,
        "updated_at": now,
        "schema_version": 1,
    }

    result = await stories_collection.insert_one(story_dict)
    if result.inserted_id:
        return {
            "message": "?덈줈???숉솕 ?앹꽦 ?꾨줈?몄뒪媛 媛쒖떆?섏뿀?듬땲??",
            "story_id": str(result.inserted_id),
        }

    raise HTTPException(status_code=500, detail="?숉솕 ?몄뀡 ?앹꽦 ?곗씠?곕쿋?댁뒪 ?ㅻ쪟")


@app.put(
    "/api/stories/{story_id}/characters",
    response_description="Save and lock story character identities",
)
async def save_story_characters(
    story_id: str,
    payload: StoryCharactersSchema,
    request: Request,
):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="Invalid story_id.")
    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    authenticated_user_id = str(request.state.auth.get("uid") or "")
    if not owner_matches(story.get("user_id"), authenticated_user_id):
        raise HTTPException(status_code=403, detail="Only the story owner can update its cast.")

    characters = normalize_story_characters(payload.characters)
    if not characters:
        raise HTTPException(status_code=400, detail="At least one character is required.")
    character_overrides = (
        normalize_story_character_overrides(payload.character_overrides)
        if payload.character_overrides is not None
        else normalize_story_character_overrides(story.get("character_overrides"))
    )
    story_cast = await build_persistent_story_cast(
        characters,
        story.get("genre"),
        character_overrides,
    )
    if not story_cast:
        raise HTTPException(
            status_code=409,
            detail="No active character image profiles are available.",
        )

    await stories_collection.update_one(
        {"_id": story_object_id},
        {
            "$set": {
                "characters": characters,
                "character_overrides": character_overrides,
                "story_cast": story_cast,
                "character_identity_locked": True,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    return {
        "story_id": story_id,
        "characters": characters,
        "story_cast": story_cast,
        "character_identity_locked": True,
    }


@app.post("/api/stories/{story_id}/scenes", response_description="?숉솕 ?섏쐞 ?λ㈃ 異붽?")
async def push_scene(story_id: str, scene: SceneSchema, request: Request):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?몄뀡 ID?낅땲??")
    await require_story_owner(story_id, request)

    scene_dict = {
        "step_number": scene.step_number,
        "content": scene.story_text,
        "audio_url": "",
        "options": [],
        "user_choice_key": f"choice_{scene.step_number}" if scene.choice_made else "",
        "user_choice": scene.choice_made,
        "scene_contract": (
            scene.scene_contract.model_dump(exclude_none=True)
            if scene.scene_contract
            else None
        ),
        "image_url": scene.image_url,
        "video_url": scene.video_url,
        "difficult_words": [],
        "created_at": scene.created_at or datetime.utcnow(),
    }

    result = await stories_collection.update_one(
        {"_id": ObjectId(story_id)},
        {
            "$push": {"scenes": scene_dict},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    if result.modified_count > 0:
        return {"message": f"{scene.step_number}???곗씠?곌? ??λ릺?덉뒿?덈떎."}

    raise HTTPException(status_code=404, detail="?대떦 ?숉솕 ?몄뀡??李얠쓣 ???놁뒿?덈떎.")


@app.patch("/api/stories/{story_id}/scenes/{step_number}/video", response_description="Scene media URL update")
async def update_scene_media(
    story_id: str,
    step_number: int,
    video_url: str,
    request: Request,
    image_url: Optional[str] = None,
):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="Invalid story ID.")
    await require_story_owner(story_id, request)

    update_data = {"scenes.$.video_url": video_url}
    if image_url:
        update_data["scenes.$.image_url"] = image_url

    result = await stories_collection.update_one(
        {"_id": ObjectId(story_id), "scenes.step_number": step_number},
        {"$set": {**update_data, "updated_at": datetime.utcnow()}},
    )

    if result.matched_count > 0:
        return {"message": f"Scene {step_number} media updated."}

    raise HTTPException(status_code=404, detail="Scene not found.")


async def persist_scene_media(
    story_id: str,
    step_number: int,
    scene_contract: Optional[Dict[str, Any]] = None,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    image_file_id: Optional[str] = None,
    video_file_id: Optional[str] = None,
    media_job_id: Optional[str] = None,
    media_status: Optional[str] = None,
    media_error: Optional[str] = None,
    expected_media_job_id: Optional[str] = None,
):
    update_data = {}
    if scene_contract:
        update_data["scenes.$.scene_contract"] = scene_contract
    if image_url:
        update_data["scenes.$.image_url"] = image_url
    if video_url:
        update_data["scenes.$.video_url"] = video_url
    if image_file_id:
        update_data["scenes.$.image_file_id"] = image_file_id
    if video_file_id:
        update_data["scenes.$.video_file_id"] = video_file_id
    if media_job_id:
        update_data["scenes.$.media_job_id"] = media_job_id
    if media_status:
        update_data["scenes.$.media_status"] = media_status
        update_data["scenes.$.media_error"] = media_error
    if not update_data:
        return False

    query: Dict[str, Any] = {
        "_id": ObjectId(story_id),
        "scenes.step_number": step_number,
    }
    if expected_media_job_id:
        query["scenes"] = {
            "$elemMatch": {
                "step_number": step_number,
                "media_job_id": expected_media_job_id,
            }
        }
        query.pop("scenes.step_number", None)

    result = await stories_collection.update_one(
        query,
        {"$set": {**update_data, "updated_at": datetime.utcnow()}},
    )
    return result.matched_count > 0


async def stream_gridfs_file(file_id: str, request: Request):
    object_id = coerce_object_id(file_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Invalid file_id.")

    try:
        grid_out = await media_files_bucket.open_download_stream(object_id)
    except NoFile:
        raise HTTPException(status_code=404, detail="Media file not found.")

    metadata = getattr(grid_out, "metadata", None) or {}
    auth = getattr(request.state, "auth", None) or {}
    is_admin = is_admin_account_id(auth.get("account_id"))
    try:
        if not is_admin and not is_shared_character_asset(metadata):
            owner_user_id = str(metadata.get("owner_user_id") or "").strip()
            story_id = serialize_object_id(metadata.get("story_id"))
            job_id = serialize_object_id(metadata.get("job_id"))
            if owner_user_id:
                if not owner_matches(owner_user_id, authenticated_user_id(request)):
                    raise HTTPException(status_code=403, detail="Media file access denied.")
            elif story_id:
                await require_story_owner(story_id, request)
            elif job_id and ObjectId.is_valid(job_id):
                job = await load_media_job(job_id, sync_scene=False)
                await require_media_job_owner(job, request)
            else:
                raise HTTPException(status_code=403, detail="Legacy media file access denied.")
    except HTTPException:
        close = getattr(grid_out, "close", None)
        if callable(close):
            close()
        raise

    content_type = (
        metadata.get("content_type")
        or getattr(grid_out, "content_type", None)
        or "application/octet-stream"
    )
    filename = getattr(grid_out, "filename", None) or str(object_id)

    async def iterator():
        try:
            while True:
                chunk = await grid_out.readchunk()
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(grid_out, "close", None)
            if callable(close):
                close()

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(getattr(grid_out, "length", 0)),
    }
    return StreamingResponse(iterator(), media_type=content_type, headers=headers)


@app.put("/api/media/characters/{character_key}")
async def upsert_character_profile(
    character_key: str,
    payload: CharacterProfileUpsertSchema,
):
    normalized_key = normalize_character_key(character_key)
    now = datetime.utcnow()
    assets = []
    for asset in payload.assets:
        asset_data = asset.model_dump()
        if not asset_data.get("image_file_id") and not asset_data.get("image_url"):
            raise HTTPException(
                status_code=400,
                detail="Each character asset needs image_file_id or image_url.",
            )
        asset_data["tags"] = sorted(
            {
                tag.strip().lower()
                for tag in asset_data.get("tags", [])
                if tag.strip()
            }
        )
        asset_data["scene_keywords"] = sorted(
            {
                keyword.strip().lower()
                for keyword in asset_data.get("scene_keywords", [])
                if keyword.strip()
            }
        )
        assets.append(asset_data)

    profile = await character_profiles_collection.find_one_and_update(
        {"character_key": normalized_key},
        {
            "$set": {
                "name": payload.name.strip(),
                "description": payload.description.strip(),
                "style_prompt": (
                    payload.style_prompt.strip() if payload.style_prompt else None
                ),
                "genres": sorted(
                    {genre.strip().lower() for genre in payload.genres if genre.strip()}
                ),
                "assets": assets,
                "active": payload.active,
                "updated_at": now,
            },
            "$setOnInsert": {
                "character_key": normalized_key,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return serialize_character_profile(profile)


@app.get("/api/media/characters")
async def list_character_profiles(active_only: bool = True, genre: Optional[str] = None):
    query = {"active": True} if active_only else {}
    if genre and genre.strip():
        query["genres"] = genre.strip().lower()
    profiles = await character_profiles_collection.find(query).sort(
        "updated_at", -1
    ).to_list(length=100)
    return [serialize_character_profile(profile) for profile in profiles]


@app.get("/api/media/characters/{character_key}")
async def get_character_profile(character_key: str):
    normalized_key = normalize_character_key(character_key)
    profile = await character_profiles_collection.find_one(
        {"character_key": normalized_key}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Character profile not found.")
    return serialize_character_profile(profile)


def build_usable_visual_vocabulary_filter(**conditions: Any) -> Dict[str, Any]:
    """Build the shared Mongo filter for vocabulary usable by media generation."""
    return {
        "enabled": True,
        "usable_for_image": True,
        **conditions,
    }


def build_enabled_visual_vocabulary_filter(**conditions: Any) -> Dict[str, Any]:
    """Build a filter for enabled derived vocabulary, including non-visual terms."""
    return {
        "enabled": True,
        **conditions,
    }


def build_usable_visual_action_filter(**conditions: Any) -> Dict[str, Any]:
    """Build the shared filter for usable, classified character-action verbs."""
    return build_usable_visual_vocabulary_filter(
        pos_group="verb",
        primary_role="action",
        **conditions,
    )


@app.get("/api/media/readiness", response_description="Media preparation progress")
async def media_readiness(request: Request):
    target_asset_count = 8
    expected_characters = {
        character["character_key"]: character for character in DEFAULT_CHARACTERS
    }
    profiles = await character_profiles_collection.find(
        {"character_key": {"$in": list(expected_characters)}}
    ).to_list(length=len(expected_characters))
    profiles_by_key = {profile["character_key"]: profile for profile in profiles}

    character_statuses = []
    ready_profile_count = 0
    ready_asset_count = 0
    for character_key, expected in expected_characters.items():
        profile = profiles_by_key.get(character_key, {})
        asset_count = len(profile.get("assets", []))
        ready = bool(profile.get("active")) and asset_count >= target_asset_count
        ready_profile_count += int(ready)
        ready_asset_count += min(asset_count, target_asset_count)
        character_statuses.append(
            {
                "character_key": character_key,
                "name": profile.get("name") or expected["name"],
                "asset_count": asset_count,
                "target_asset_count": target_asset_count,
                "ready": ready,
            }
        )

    target_profile_count = len(expected_characters)
    target_total_assets = target_profile_count * target_asset_count
    target_units = target_profile_count + target_total_assets
    ready_units = ready_profile_count + ready_asset_count
    progress_percent = round((ready_units / target_units) * 100) if target_units else 100

    auth = getattr(request.state, "auth", None) or {}
    queue_owner_filter = (
        {} if is_admin_account_id(auth.get("account_id"))
        else {"owner_user_id": authenticated_user_id(request)}
    )
    pending_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "pending"}
    )
    running_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "running"}
    )
    completed_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "completed"}
    )
    partial_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "partial"}
    )
    failed_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "failed"}
    )
    visual_total = await visual_vocabulary_collection.count_documents({})
    visual_enabled = await visual_vocabulary_collection.count_documents({"enabled": True})
    visual_usable = await visual_vocabulary_collection.count_documents(
        build_usable_visual_vocabulary_filter()
    )
    visual_ambiguous = await visual_vocabulary_collection.count_documents(
        build_usable_visual_vocabulary_filter(ambiguous=True)
    )

    return {
        "status": "ok",
        "progress_percent": progress_percent,
        "profiles": {
            "ready": ready_profile_count,
            "target": target_profile_count,
        },
        "assets": {
            "ready": ready_asset_count,
            "target": target_total_assets,
        },
        "worker": {
            "running": bool(
                media_generation_worker_task
                and not media_generation_worker_task.done()
            ),
        },
        "queue": {
            "pending": pending_count,
            "running": running_count,
            "completed": completed_count,
            "partial": partial_count,
            "failed": failed_count,
        },
        "visual_vocabulary": {
            "total": visual_total,
            "enabled": visual_enabled,
            "usable_for_image": visual_usable,
            "ambiguous": visual_ambiguous,
        },
        "characters": character_statuses,
    }


@app.get(
    "/api/media/visual-vocabulary/readiness",
    response_description="Visual vocabulary derivation status",
)
async def visual_vocabulary_readiness():
    total = await visual_vocabulary_collection.count_documents({})
    enabled = await visual_vocabulary_collection.count_documents({"enabled": True})
    usable_filter = build_usable_visual_vocabulary_filter()
    usable = await visual_vocabulary_collection.count_documents(usable_filter)
    ambiguous = await visual_vocabulary_collection.count_documents(
        build_usable_visual_vocabulary_filter(ambiguous=True)
    )
    ambiguous_usable = ambiguous
    non_visual = await visual_vocabulary_collection.count_documents(
        build_enabled_visual_vocabulary_filter(primary_role="non_visual")
    )
    role_pipeline = [
        {
            "$match": {
                **usable_filter,
            }
        },
        {"$group": {"_id": "$primary_role", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ]
    role_counts = {
        item["_id"]: item["count"]
        async for item in visual_vocabulary_collection.aggregate(role_pipeline)
    }
    source_verbs = await fit_vocabulary_collection.count_documents(
        {
            "$or": [
                {"pos_group": "동사"},
                {"part_of_speech": "동사"},
            ]
        }
    )
    visualized_verbs = await visual_vocabulary_collection.count_documents(
        build_usable_visual_vocabulary_filter(pos_group="verb")
    )
    character_action_verbs = await visual_vocabulary_collection.count_documents(
        build_usable_visual_action_filter(
            **{"$or": [
                {"action_tags.0": {"$exists": True}},
                {
                    "action_semantics.animation_action": {
                        "$exists": True,
                        "$ne": "idle",
                    }
                },
            ]},
        )
    )
    solo_action_verbs = await visual_vocabulary_collection.count_documents(
        build_usable_visual_action_filter(solo_action=True)
    )
    action_tag_pipeline = [
        {
            "$match": {
                **build_usable_visual_vocabulary_filter(
                    pos_group="verb",
                ),
                "action_tags.0": {"$exists": True},
            }
        },
        {"$unwind": "$action_tags"},
        {"$group": {"_id": "$action_tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ]
    action_tag_counts = {
        item["_id"]: item["count"]
        async for item in visual_vocabulary_collection.aggregate(
            action_tag_pipeline
        )
    }
    motion_mode_pipeline = [
        {
            "$match": {
                **build_usable_visual_vocabulary_filter(
                    pos_group="verb",
                ),
                "action_semantics.motion_mode": {"$exists": True},
            }
        },
        {
            "$group": {
                "_id": "$action_semantics.motion_mode",
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1, "_id": 1}},
    ]
    motion_mode_counts = {
        item["_id"]: item["count"]
        async for item in visual_vocabulary_collection.aggregate(
            motion_mode_pipeline
        )
    }
    partner_required_verbs = await visual_vocabulary_collection.count_documents(
        build_usable_visual_action_filter(
            **{"action_semantics.requires_partner": True},
        )
    )
    object_required_verbs = await visual_vocabulary_collection.count_documents(
        build_usable_visual_action_filter(
            **{"action_semantics.requires_object": True},
        )
    )
    target_required_verbs = await visual_vocabulary_collection.count_documents(
        build_usable_visual_action_filter(
            **{"action_semantics.requires_target": True},
        )
    )
    semantic_feature_counts = {
        "background_words": await visual_vocabulary_collection.count_documents(
            build_usable_visual_vocabulary_filter(
                **{"background_keys.0": {"$exists": True}}
            )
        ),
        "prop_words": await visual_vocabulary_collection.count_documents(
            build_usable_visual_vocabulary_filter(
                **{"prop_tags.0": {"$exists": True}}
            )
        ),
        "emotion_words": await visual_vocabulary_collection.count_documents(
            build_usable_visual_vocabulary_filter(
                **{"emotion_tags.0": {"$exists": True}}
            )
        ),
        "environment_words": await visual_vocabulary_collection.count_documents(
            build_usable_visual_vocabulary_filter(
                **{"effect_tags.0": {"$exists": True}}
            )
        ),
        "motion_modifier_words": await visual_vocabulary_collection.count_documents(
            build_usable_visual_vocabulary_filter(
                **{"motion_modifier_tags.0": {"$exists": True}}
            )
        ),
    }
    return {
        "status": "ok",
        "total": total,
        "enabled": enabled,
        "usable_for_image": usable,
        "not_yet_usable": max(0, enabled - usable),
        "non_visual": non_visual,
        "ambiguous": ambiguous,
        "ambiguous_usable": ambiguous_usable,
        "roles": role_counts,
        "semantic_features": semantic_feature_counts,
        "verbs": {
            "source": source_verbs,
            "visualized": visualized_verbs,
            "character_actions": character_action_verbs,
            "solo_actions": solo_action_verbs,
            "coverage_percent": round(
                visualized_verbs * 100 / max(source_verbs, 1),
                1,
            ),
            "action_tags": action_tag_counts,
            "motion_modes": motion_mode_counts,
            "partner_required": partner_required_verbs,
            "object_required": object_required_verbs,
            "target_required": target_required_verbs,
        },
    }


@app.get("/api/media/files/{file_id}", response_description="Serve stored media file")
async def get_media_file(file_id: str, request: Request):
    return await stream_gridfs_file(file_id, request)


@app.get("/api/media/images/{file_id}", response_description="Serve stored generated image")
async def get_media_image(file_id: str, request: Request):
    return await stream_gridfs_file(file_id, request)


@app.get("/api/media/videos/{file_id}", response_description="Serve stored generated video")
async def get_media_video(file_id: str, request: Request):
    return await stream_gridfs_file(file_id, request)


@app.get("/api/media/health", response_description="Media queue health")
async def media_health(request: Request):
    provider_config = get_hf_media_config()
    auth = getattr(request.state, "auth", None) or {}
    queue_owner_filter = (
        {} if is_admin_account_id(auth.get("account_id"))
        else {"owner_user_id": authenticated_user_id(request)}
    )
    pending_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "pending"}
    )
    running_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "running"}
    )
    failed_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "failed"}
    )
    completed_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "completed"}
    )
    partial_count = await media_jobs_collection.count_documents(
        {**queue_owner_filter, "status": "partial"}
    )

    return {
        "status": "ok",
        "mode": "backend_hf_provider",
        "provider": provider_config,
        "worker": {
            "id": MEDIA_GENERATION_WORKER_ID,
            "running": bool(media_generation_worker_task and not media_generation_worker_task.done()),
            "stale_seconds": MEDIA_JOB_STALE_SECONDS,
        },
        "queue": {
            "pending": pending_count,
            "running": running_count,
            "completed": completed_count,
            "partial": partial_count,
            "failed": failed_count,
            "sync_loop": bool(media_job_sync_task and not media_job_sync_task.done()),
        },
    }


@app.post("/api/media/jobs", status_code=202)
async def create_media_job(payload: MediaGenerationWithStorySchema, request: Request):
    owner_user_id = authenticated_user_id(request)
    story_id, step_number = normalize_media_story_target(
        payload.story_id,
        payload.step_number,
        require_positive_step=True,
    )
    if story_id is not None and step_number is not None:
        await require_story_owner(story_id, request)
        await ensure_story_scene_exists(story_id, step_number)
    await ensure_active_character_profile(payload.character_key)
    await ensure_story_character_profile(story_id, payload.character_key)

    return await enqueue_media_job(
        payload,
        story_id=story_id,
        step_number=step_number,
        owner_user_id=owner_user_id,
    )


@app.post("/api/stories/{story_id}/scenes/{step_number}/media/jobs", status_code=202)
async def create_scene_media_job(
    story_id: str,
    step_number: int,
    payload: MediaGenerationSchema,
    request: Request,
):
    owner_user_id = authenticated_user_id(request)
    story_id, step_number = normalize_media_story_target(
        story_id,
        step_number,
        require_positive_step=True,
    )
    await require_story_owner(story_id, request)
    await ensure_story_scene_exists(story_id, step_number)
    await ensure_active_character_profile(payload.character_key)
    await ensure_story_character_profile(story_id, payload.character_key)

    job_payload = MediaGenerationWithStorySchema(
        story_text=payload.story_text,
        genre=payload.genre,
        age=payload.age,
        character_key=payload.character_key,
        scene_contract=payload.scene_contract,
        include_video=payload.include_video,
        width=payload.width,
        height=payload.height,
        flux_steps=payload.flux_steps,
        video_width=payload.video_width,
        video_height=payload.video_height,
        num_frames=payload.num_frames,
        video_steps=payload.video_steps,
        frame_rate=payload.frame_rate,
        video_timeout=payload.video_timeout,
        story_id=story_id,
        step_number=step_number,
    )
    return await enqueue_media_job(
        job_payload,
        story_id=story_id,
        step_number=step_number,
        owner_user_id=owner_user_id,
    )


@app.get("/api/media/jobs/{job_id}")
async def get_media_job(job_id: str, request: Request):
    job = await load_media_job(job_id)
    await require_media_job_owner(job, request)
    return serialize_media_job_document(job)


@app.post("/api/media/generate", response_description="Generate fairytale scene media")
async def generate_media(payload: MediaGenerationWithStorySchema, request: Request):
    owner_user_id = authenticated_user_id(request)
    story_id, step_number = normalize_media_story_target(
        payload.story_id,
        payload.step_number,
        require_positive_step=True,
    )
    if story_id is not None and step_number is not None:
        await require_story_owner(story_id, request)
        await ensure_story_scene_exists(story_id, step_number)
    await ensure_active_character_profile(payload.character_key)
    await ensure_story_character_profile(story_id, payload.character_key)

    try:
        return await execute_media_generation(
            story_text=payload.story_text,
            story_id=story_id,
            step_number=step_number,
            genre=payload.genre,
            age=payload.age,
            character_key=payload.character_key,
            scene_contract=(
                payload.scene_contract.model_dump(exclude_none=True)
                if payload.scene_contract
                else None
            ),
            include_video=payload.include_video,
            width=payload.width,
            height=payload.height,
            flux_steps=payload.flux_steps,
            video_width=payload.video_width,
            video_height=payload.video_height,
            num_frames=payload.num_frames,
            video_steps=payload.video_steps,
            frame_rate=payload.frame_rate,
            owner_user_id=owner_user_id,
        )
    except HfMediaError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media generation failed: {e}")


@app.post(
    "/api/stories/{story_id}/scenes/{step_number}/media/generate",
    response_description="Generate and save fairytale scene media",
)
async def generate_and_store_scene_media(
    story_id: str,
    step_number: int,
    payload: MediaGenerationSchema,
    request: Request,
):
    owner_user_id = authenticated_user_id(request)
    story_id, step_number = normalize_media_story_target(
        story_id,
        step_number,
        require_positive_step=True,
    )
    await require_story_owner(story_id, request)
    await ensure_story_scene_exists(story_id, step_number)
    await ensure_active_character_profile(payload.character_key)
    await ensure_story_character_profile(story_id, payload.character_key)

    try:
        media = await execute_media_generation(
            story_text=payload.story_text,
            story_id=story_id,
            step_number=step_number,
            genre=payload.genre,
            age=payload.age,
            character_key=payload.character_key,
            scene_contract=(
                payload.scene_contract.model_dump(exclude_none=True)
                if payload.scene_contract
                else None
            ),
            include_video=payload.include_video,
            width=payload.width,
            height=payload.height,
            flux_steps=payload.flux_steps,
            video_width=payload.video_width,
            video_height=payload.video_height,
            num_frames=payload.num_frames,
            video_steps=payload.video_steps,
            frame_rate=payload.frame_rate,
            owner_user_id=owner_user_id,
        )
    except HfMediaError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media generation failed: {e}")

    if not media.get("saved"):
        raise HTTPException(status_code=404, detail="Generated media could not be saved to the scene.")
    return media

@app.delete("/api/stories/{story_id}", response_description="?숉솕 ??젣")
async def delete_story(story_id: str, owner: OwnerActionSchema, request: Request):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?숉솕 ID?낅땲??")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="?숉솕瑜?李얠쓣 ???놁뒿?덈떎.")
    await require_story_owner(story_id, request)

    if owner.user_id:
        if not ObjectId.is_valid(owner.user_id):
            raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")
        if not owner_matches(story.get("user_id"), owner.user_id):
            raise HTTPException(status_code=403, detail="???숉솕留???젣?????덉뒿?덈떎.")

    await stories_collection.delete_one({"_id": story_object_id})
    await vocabularies_collection.delete_many(
        {"origin_story_id": {"$in": [story_id, story_object_id]}},
    )
    await community_posts_collection.update_many(
        {"story_id": {"$in": [story_id, story_object_id]}},
        {"$unset": {"story_id": ""}},
    )
    return {"message": "?숉솕? ?곌껐 ?⑥뼱?μ씠 ??젣?섏뿀?듬땲??", "story_id": story_id}


@app.patch("/api/stories/{story_id}", response_description="?숉솕 硫뷀??곗씠???섏젙")
async def update_story(story_id: str, update: StoryUpdateSchema, request: Request):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?숉솕 ID?낅땲??")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="?숉솕瑜?李얠쓣 ???놁뒿?덈떎.")
    await require_story_owner(story_id, request)

    if update.user_id:
        if not ObjectId.is_valid(update.user_id):
            raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")
        if not owner_matches(story.get("user_id"), update.user_id):
            raise HTTPException(status_code=403, detail="???숉솕留??섏젙?????덉뒿?덈떎.")

    update_fields = {}
    if update.title is not None:
        title = update.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="?쒕ぉ? 鍮꾩썙?????놁뒿?덈떎.")
        update_fields["title"] = title
        update_fields["generation_meta.prompt_inputs.title"] = title
        update_fields["updated_at"] = datetime.utcnow()

    if not update_fields:
        return serialize_story(story)

    await stories_collection.update_one(
        {"_id": story_object_id},
        {"$set": update_fields},
    )
    updated = await stories_collection.find_one({"_id": story_object_id})
    if not updated:
        raise HTTPException(status_code=404, detail="?숉솕瑜?李얠쓣 ???놁뒿?덈떎.")
    return serialize_story(updated)


@app.post("/api/vocabularies/add", response_description="紐⑤Ⅴ???⑥뼱 異붽?")
async def add_vocabulary(vocab: VocabularySchema):
    if not ObjectId.is_valid(vocab.user_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")
    if not ObjectId.is_valid(vocab.origin_story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?숉솕 ID?낅땲??")

    now = vocab.created_at or datetime.utcnow()
    meaning = vocab.definition or vocab.easy
    vocab_dict = {
        "user_id": vocab.user_id,
        "word": vocab.hard,
        "meaning": meaning,
        "progress_rate": 0,
        "origin_story_title": vocab.source_story_title,
        "origin_story_id": vocab.origin_story_id,
        "origin_scene_number": 0,
        "review_count": 0,
        "saved_at": now,
        "last_reviewed_at": None,
        "source_collection": "vocabularies",
        "is_mastered": False,
        "next_review_at": None,
        "review_stage": "new",
        "schema_version": 1,
    }

    result = await vocabularies_collection.update_one(
        {"user_id": vocab.user_id, "word": vocab.hard},
        {"$setOnInsert": vocab_dict},
        upsert=True,
    )
    saved = await vocabularies_collection.find_one(
        {"user_id": vocab.user_id, "word": vocab.hard},
    )
    if saved:
        return {
            "message": "?⑥뼱媛 ?깃났?곸쑝濡??곗씠?곕쿋?댁뒪 ?⑥뼱?μ뿉 ?깅줉?섏뿀?듬땲??",
            "id": str(saved["_id"]),
            "created": bool(result.upserted_id),
        }

    raise HTTPException(status_code=500, detail="?⑥뼱 ?곸옱 ?ㅽ뙣")


@app.get("/api/users/{user_id}/vocabularies", response_description="?ъ슜???⑥뼱??議고쉶")
async def list_user_vocabularies(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")

    vocabularies = await vocabularies_collection.find(
        {"user_id": user_id_filter(user_id)},
    ).to_list(length=1000)
    vocabularies.sort(
        key=lambda item: serialize_datetime(item.get("saved_at") or item.get("created_at")),
        reverse=True,
    )

    return {"vocabularies": [serialize_vocabulary(vocab) for vocab in vocabularies]}


@app.delete("/api/vocabularies/{vocab_id}", response_description="?⑥뼱????ぉ ??젣")
async def delete_vocabulary(
    vocab_id: str,
    owner: OwnerActionSchema,
):
    if not ObjectId.is_valid(vocab_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?⑥뼱 ID?낅땲??")

    vocab_object_id = ObjectId(vocab_id)
    vocab = await vocabularies_collection.find_one({"_id": vocab_object_id})
    if not vocab:
        raise HTTPException(status_code=404, detail="?⑥뼱瑜?李얠쓣 ???놁뒿?덈떎.")

    if owner.user_id:
        if not ObjectId.is_valid(owner.user_id):
            raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")
        if not owner_matches(vocab.get("user_id"), owner.user_id):
            raise HTTPException(status_code=403, detail="???⑥뼱留???젣?????덉뒿?덈떎.")

    await vocabularies_collection.delete_one({"_id": vocab_object_id})
    return {"message": "?⑥뼱媛 ??젣?섏뿀?듬땲??", "vocab_id": vocab_id}


def serialize_comment(comment: dict):
    is_hidden = bool(comment.get("is_hidden", False))
    return {
        "id": str(comment.get("_id", "")),
        "author_name": comment.get("author_name", "?숉솕 移쒓뎄"),
        "author_account_id": comment.get("author_account_id"),
        "content": (
            "관리자에 의해 숨겨진 댓글입니다."
            if is_hidden
            else comment.get("content", "")
        ),
        "created_at": serialize_datetime(comment.get("created_at")),
        "moderation_status": comment.get("moderation_status", "visible"),
        "report_count": int(comment.get("report_count", 0) or 0),
    }


def serialize_post(post: dict):
    comments = post.get("comments", [])
    sorted_comments = sorted(
        comments,
        key=lambda item: serialize_datetime(item.get("created_at")),
    )
    return {
        "id": str(post["_id"]),
        "author_name": post.get("author_name", "?숉솕 移쒓뎄"),
        "author_account_id": post.get("author_account_id"),
        "story_id": str(post["story_id"]) if post.get("story_id") else None,
        "genre": post.get("genre", "?숉솕"),
        "title": post.get("title", "?쒕ぉ ?녿뒗 ?숉솕"),
        "preview": post.get("preview", ""),
        "full_text": post.get("full_text", ""),
        "story_emoji": post.get("story_emoji", "?뱰"),
        "created_at": serialize_datetime(post.get("created_at")),
        "view_count": post.get("view_count", 0),
        "like_count": post.get("like_count", post.get("likes", 0)),
        "liked_by": post.get("liked_by", []),
        "comments": [serialize_comment(comment) for comment in sorted_comments],
    }


@app.get("/api/community/posts", response_description="而ㅻ??덊떚 寃뚯떆湲 紐⑸줉")
async def list_community_posts(sort: str = "latest"):
    posts = await community_posts_collection.find(
        {"is_hidden": {"$ne": True}}
    ).to_list(length=200)
    if sort == "popular":
        posts.sort(
            key=lambda item: (
                item.get("like_count", item.get("likes", 0)),
                item.get("view_count", 0),
            ),
            reverse=True,
        )
    else:
        posts.sort(
            key=lambda item: serialize_datetime(item.get("created_at")),
            reverse=True,
        )

    return {"posts": [serialize_post(post) for post in posts]}


@app.post("/api/community/posts", response_description="?숉솕 寃뚯떆湲 怨듭쑀")
async def create_community_post(post: CommunityPostSchema):
    post_dict = post.model_dump()
    if post.story_id:
        if not ObjectId.is_valid(post.story_id):
            raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?숉솕 ID?낅땲??")
        post_dict["story_id"] = post.story_id

    post_dict["comments"] = []
    post_dict["view_count"] = 0
    post_dict["like_count"] = 0
    post_dict["likes"] = 0
    post_dict["liked_by"] = []
    post_dict["source_collection"] = "community_posts"
    post_dict["moderation_status"] = "visible"
    post_dict["is_hidden"] = False
    post_dict["report_count"] = 0
    post_dict["last_activity_at"] = post.created_at or datetime.utcnow()
    post_dict["schema_version"] = 1

    result = await community_posts_collection.insert_one(post_dict)
    created = await community_posts_collection.find_one({"_id": result.inserted_id})
    if created:
        return serialize_post(created)

    raise HTTPException(status_code=500, detail="寃뚯떆湲 ????ㅽ뙣")


@app.get("/api/community/posts/{post_id}", response_description="寃뚯떆湲 ?곸꽭 議고쉶")
async def get_community_post(post_id: str):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? 寃뚯떆湲 ID?낅땲??")

    await community_posts_collection.update_one(
        {"_id": ObjectId(post_id), "is_hidden": {"$ne": True}},
        {"$inc": {"view_count": 1}},
    )
    post = await community_posts_collection.find_one(
        {"_id": ObjectId(post_id), "is_hidden": {"$ne": True}}
    )
    if not post:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
    return serialize_post(post)


@app.post("/api/community/posts/{post_id}/like", response_description="Like community post")
async def like_community_post(post_id: str, like: LikeSchema):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? 寃뚯떆湲 ID?낅땲??")

    post_object_id = ObjectId(post_id)
    account_id = like.account_id.strip() if like.account_id else None

    if account_id:
        post = await community_posts_collection.find_one({"_id": post_object_id})
        if not post:
            raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
        liked_by = post.get("liked_by", [])
        if account_id in liked_by:
            await community_posts_collection.update_one(
                {"_id": post_object_id},
                {
                    "$inc": {"like_count": -1, "likes": -1},
                    "$pull": {"liked_by": account_id},
                },
            )
        else:
            await community_posts_collection.update_one(
                {"_id": post_object_id},
                {
                    "$inc": {"like_count": 1, "likes": 1},
                    "$addToSet": {"liked_by": account_id},
                },
            )
    else:
        await community_posts_collection.update_one(
            {"_id": post_object_id},
            {"$inc": {"like_count": 1, "likes": 1}},
        )

    post = await community_posts_collection.find_one({"_id": post_object_id})
    if not post:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
    return serialize_post(post)


@app.post("/api/community/posts/{post_id}/comments", response_description="寃뚯떆湲 ?볤? ?묒꽦")
async def add_community_comment(post_id: str, comment: CommunityCommentSchema):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? 寃뚯떆湲 ID?낅땲??")

    comment_dict = comment.model_dump()
    comment_dict["_id"] = ObjectId()
    comment_dict["schema_version"] = 2
    comment_dict["moderation_status"] = "visible"
    comment_dict["is_hidden"] = False
    comment_dict["report_count"] = 0

    result = await community_posts_collection.update_one(
        {"_id": ObjectId(post_id)},
        {
            "$push": {"comments": comment_dict},
            "$set": {"last_activity_at": comment.created_at or datetime.utcnow()},
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")

    post = await community_posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
    return serialize_post(post)


@app.delete("/api/community/posts/{post_id}", response_description="寃뚯떆湲 ??젣")
async def delete_community_post(post_id: str, owner: OwnerActionSchema):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? 寃뚯떆湲 ID?낅땲??")
    if not owner.account_id:
        raise HTTPException(status_code=401, detail="濡쒓렇??怨꾩젙 ?뺣낫媛 ?꾩슂?⑸땲??")

    post_object_id = ObjectId(post_id)
    post = await community_posts_collection.find_one({"_id": post_object_id})
    if not post:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
    if post.get("author_account_id") != owner.account_id:
        raise HTTPException(status_code=403, detail="??寃뚯떆湲留???젣?????덉뒿?덈떎.")

    await community_posts_collection.delete_one({"_id": post_object_id})
    return {"message": "寃뚯떆湲????젣?섏뿀?듬땲??", "post_id": post_id}


@app.delete(
    "/api/community/posts/{post_id}/comments/{comment_id}",
    response_description="寃뚯떆湲 ?볤? ??젣",
)
async def delete_community_comment(
    post_id: str,
    comment_id: str,
    owner: OwnerActionSchema,
):
    if not ObjectId.is_valid(post_id) or not ObjectId.is_valid(comment_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ID?낅땲??")
    if not owner.account_id:
        raise HTTPException(status_code=401, detail="濡쒓렇??怨꾩젙 ?뺣낫媛 ?꾩슂?⑸땲??")

    post_object_id = ObjectId(post_id)
    comment_object_id = ObjectId(comment_id)
    post = await community_posts_collection.find_one({"_id": post_object_id})
    if not post:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")

    comments = post.get("comments", [])
    target_comment = next(
        (comment for comment in comments if comment.get("_id") == comment_object_id),
        None,
    )
    if not target_comment:
        raise HTTPException(status_code=404, detail="?볤???李얠쓣 ???놁뒿?덈떎.")

    is_comment_owner = target_comment.get("author_account_id") == owner.account_id
    is_post_owner = post.get("author_account_id") == owner.account_id
    if not is_comment_owner and not is_post_owner:
        raise HTTPException(status_code=403, detail="???볤?留???젣?????덉뒿?덈떎.")

    await community_posts_collection.update_one(
        {"_id": post_object_id},
        {"$pull": {"comments": {"_id": comment_object_id}}},
    )
    updated = await community_posts_collection.find_one({"_id": post_object_id})
    if not updated:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
    return serialize_post(updated)


async def resolve_report_target(payload: CommunityReportSchema) -> Dict[str, Any]:
    if not ObjectId.is_valid(payload.target_id):
        raise HTTPException(status_code=400, detail="신고 대상 ID가 올바르지 않습니다.")
    target_id = ObjectId(payload.target_id)
    if payload.target_type == "post":
        post = await community_posts_collection.find_one({"_id": target_id}, {"_id": 1})
        if not post:
            raise HTTPException(status_code=404, detail="신고할 게시물을 찾을 수 없습니다.")
        return {"target_id": target_id, "post_id": target_id}
    if payload.target_type == "comment":
        if not payload.post_id or not ObjectId.is_valid(payload.post_id):
            raise HTTPException(status_code=400, detail="댓글 신고에는 게시물 ID가 필요합니다.")
        post_id = ObjectId(payload.post_id)
        post = await community_posts_collection.find_one(
            {"_id": post_id, "comments._id": target_id},
            {"_id": 1},
        )
        if not post:
            raise HTTPException(status_code=404, detail="신고할 댓글을 찾을 수 없습니다.")
        return {"target_id": target_id, "post_id": post_id}

    user = await users_collection.find_one({"_id": target_id}, {"_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="신고할 사용자를 찾을 수 없습니다.")
    return {"target_id": target_id, "post_id": None}


@app.post("/api/community/reports", response_description="Create community report")
async def create_community_report(payload: CommunityReportSchema, request: Request):
    target = await resolve_report_target(payload)
    auth = getattr(request.state, "auth", None) or {}
    authenticated_account_id = str(auth.get("account_id") or "").strip()
    reporter_account_id = (
        payload.reporter_account_id.strip()
        if payload.reporter_account_id
        else authenticated_account_id
    )
    if reporter_account_id != authenticated_account_id:
        raise HTTPException(
            status_code=403,
            detail="You can only submit reports under your own account.",
        )
    if reporter_account_id:
        reporter = await users_collection.find_one(
            {"account_id": reporter_account_id, "account_status": {"$ne": "deleted"}},
            {"_id": 1},
        )
        if not reporter:
            raise HTTPException(status_code=404, detail="신고자 계정을 찾을 수 없습니다.")
        duplicate = await reports_collection.find_one(
            {
                "reporter_account_id": reporter_account_id,
                "target_type": payload.target_type,
                "target_id": target["target_id"],
                "status": "pending",
            }
        )
        if duplicate:
            return {
                "message": "이미 접수된 신고입니다.",
                "report": serialize_report(duplicate),
                "created": False,
            }

    now = datetime.utcnow()
    report_document = {
        "reporter_account_id": reporter_account_id,
        "target_type": payload.target_type,
        "target_id": target["target_id"],
        "post_id": target["post_id"],
        "reason": payload.reason.strip(),
        "details": payload.details.strip() if payload.details else None,
        "status": "pending",
        "action_taken": None,
        "resolution_note": None,
        "created_at": now,
        "resolved_at": None,
        "resolved_by": None,
        "schema_version": 1,
    }
    result = await reports_collection.insert_one(report_document)
    report_document["_id"] = result.inserted_id

    if payload.target_type == "post":
        await community_posts_collection.update_one(
            {"_id": target["target_id"]},
            {"$inc": {"report_count": 1}},
        )
    elif payload.target_type == "comment":
        await community_posts_collection.update_one(
            {
                "_id": target["post_id"],
                "comments._id": target["target_id"],
            },
            {"$inc": {"comments.$.report_count": 1}},
        )
    else:
        await users_collection.update_one(
            {"_id": target["target_id"]},
            {"$inc": {"report_count": 1}},
        )

    return {
        "message": "신고가 접수되었습니다.",
        "report": serialize_report(report_document),
        "created": True,
    }


@app.post(
    "/api/admin/users/{user_id}/warnings",
    response_description="Create user warning",
)
async def create_user_warning(
    user_id: str,
    warning: WarningCreateSchema,
    account_id: str,
):
    await require_admin(account_id)
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="사용자 ID가 올바르지 않습니다.")
    user_object_id = ObjectId(user_id)
    user = await users_collection.find_one({"_id": user_object_id})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if user.get("account_status") == "deleted":
        raise HTTPException(status_code=409, detail="탈퇴한 사용자에게 경고할 수 없습니다.")

    now = datetime.utcnow()
    document = {
        "user_id": user_object_id,
        "reason": warning.reason.strip(),
        "severity": warning.severity,
        "status": "active",
        "created_by": account_id,
        "created_at": now,
        "expires_at": warning.expires_at,
        "resolved_at": None,
        "schema_version": 1,
    }
    result = await user_warnings_collection.insert_one(document)
    document["_id"] = result.inserted_id
    await users_collection.update_one(
        {"_id": user_object_id},
        {
            "$inc": {"warning_count": 1},
            "$set": {
                "last_warning_at": now,
                "account_status": "warned",
            },
        },
    )
    return {
        "message": "경고가 기록되었습니다.",
        "warning": serialize_warning(document),
    }


@app.get("/api/admin/reports", response_description="List reports")
async def list_admin_reports(
    account_id: str,
    status: Optional[str] = None,
):
    await require_admin(account_id)
    query = {"status": status} if status else {}
    reports = await reports_collection.find(query).sort(
        "created_at",
        -1,
    ).to_list(length=500)
    return {"reports": [serialize_report(report) for report in reports]}


@app.get("/api/admin/warnings", response_description="List warnings")
async def list_admin_warnings(
    account_id: str,
    user_id: Optional[str] = None,
):
    await require_admin(account_id)
    query: Dict[str, Any] = {}
    if user_id:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="사용자 ID가 올바르지 않습니다.")
        query["user_id"] = ObjectId(user_id)
    warnings = await user_warnings_collection.find(query).sort(
        "created_at",
        -1,
    ).to_list(length=500)
    return {"warnings": [serialize_warning(warning) for warning in warnings]}


@app.patch(
    "/api/admin/warnings/{warning_id}",
    response_description="Resolve warning",
)
async def resolve_admin_warning(
    warning_id: str,
    resolution: WarningResolutionSchema,
    account_id: str,
):
    await require_admin(account_id)
    if not ObjectId.is_valid(warning_id):
        raise HTTPException(status_code=400, detail="경고 ID가 올바르지 않습니다.")
    now = datetime.utcnow()
    warning = await user_warnings_collection.find_one_and_update(
        {"_id": ObjectId(warning_id)},
        {
            "$set": {
                "status": resolution.status,
                "resolution_note": (
                    resolution.resolution_note.strip()
                    if resolution.resolution_note
                    else None
                ),
                "resolved_at": now,
                "resolved_by": account_id,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not warning:
        raise HTTPException(status_code=404, detail="경고를 찾을 수 없습니다.")

    active_count = await user_warnings_collection.count_documents(
        {"user_id": warning["user_id"], "status": "active"}
    )
    if active_count == 0:
        await users_collection.update_one(
            {
                "_id": warning["user_id"],
                "account_status": "warned",
            },
            {"$set": {"account_status": "active"}},
        )
    return {
        "message": "경고 처리가 저장되었습니다.",
        "warning": serialize_warning(warning),
    }


@app.patch("/api/admin/reports/{report_id}", response_description="Resolve report")
async def resolve_admin_report(
    report_id: str,
    resolution: ReportResolutionSchema,
    account_id: str,
):
    await require_admin(account_id)
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="신고 ID가 올바르지 않습니다.")
    now = datetime.utcnow()
    report = await reports_collection.find_one_and_update(
        {"_id": ObjectId(report_id)},
        {
            "$set": {
                "status": resolution.status,
                "action_taken": resolution.action_taken,
                "resolution_note": (
                    resolution.resolution_note.strip()
                    if resolution.resolution_note
                    else None
                ),
                "resolved_at": now,
                "resolved_by": account_id,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not report:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다.")

    if resolution.action_taken == "hide_content":
        if report.get("target_type") == "post":
            await community_posts_collection.update_one(
                {"_id": report["target_id"]},
                {
                    "$set": {
                        "is_hidden": True,
                        "moderation_status": "hidden",
                    }
                },
            )
        elif report.get("target_type") == "comment" and report.get("post_id"):
            await community_posts_collection.update_one(
                {
                    "_id": report["post_id"],
                    "comments._id": report["target_id"],
                },
                {
                    "$set": {
                        "comments.$.is_hidden": True,
                        "comments.$.moderation_status": "hidden",
                    }
                },
            )

    return {
        "message": "신고 처리가 저장되었습니다.",
        "report": serialize_report(report),
    }


@app.get("/api/notices", response_description="Published notices")
async def list_notices(limit: int = 500):
    bounded_limit = max(1, min(int(limit), 500))
    notices = await notices_collection.find(
        {"is_published": True}
    ).sort(
        [("is_pinned", -1), ("published_at", -1), ("created_at", -1)]
    ).to_list(length=bounded_limit)
    return {"notices": [serialize_notice(notice) for notice in notices]}


@app.get("/api/notices/{notice_id}", response_description="Notice detail")
async def get_notice(notice_id: str):
    if not ObjectId.is_valid(notice_id):
        raise HTTPException(status_code=400, detail="공지사항 ID가 올바르지 않습니다.")
    notice = await notices_collection.find_one(
        {"_id": ObjectId(notice_id), "is_published": True}
    )
    if not notice:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    return serialize_notice(notice)


@app.post("/api/admin/notices", response_description="Create notice")
async def create_admin_notice(payload: AdminNoticeCreateSchema):
    await require_admin(payload.account_id)
    now = datetime.utcnow()
    notice = {
        "title": payload.title.strip(),
        "content": payload.content.strip(),
        "is_pinned": payload.is_pinned,
        "is_published": True,
        "author_account_id": payload.account_id.strip(),
        "created_at": now,
        "published_at": now,
        "updated_at": now,
        "email_requested": payload.send_email,
        "email_delivery_status": "queued" if payload.send_email else "not_requested",
        "email_recipient_count": 0,
        "email_sent_count": 0,
        "email_failed_count": 0,
        "email_delivery_error": None,
        "schema_version": 1,
    }
    result = await notices_collection.insert_one(notice)
    notice["_id"] = result.inserted_id
    if payload.send_email:
        schedule_notice_email_delivery(result.inserted_id)
    return serialize_notice(notice, include_delivery_error=True)


@app.patch("/api/admin/notices/{notice_id}", response_description="Update notice")
async def update_admin_notice(
    notice_id: str,
    payload: AdminNoticeUpdateSchema,
):
    await require_admin(payload.account_id)
    if not ObjectId.is_valid(notice_id):
        raise HTTPException(status_code=400, detail="공지사항 ID가 올바르지 않습니다.")
    now = datetime.utcnow()
    notice = await notices_collection.find_one_and_update(
        {"_id": ObjectId(notice_id)},
        {
            "$set": {
                "title": payload.title.strip(),
                "content": payload.content.strip(),
                "is_pinned": payload.is_pinned,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not notice:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    return serialize_notice(notice, include_delivery_error=True)


@app.post("/api/admin/notices/{notice_id}/email", response_description="Send notice email")
async def send_admin_notice_email(
    notice_id: str,
    payload: AdminNoticeEmailSchema,
):
    await require_admin(payload.account_id)
    if not ObjectId.is_valid(notice_id):
        raise HTTPException(status_code=400, detail="공지사항 ID가 올바르지 않습니다.")
    object_id = ObjectId(notice_id)
    notice = await notices_collection.find_one({"_id": object_id})
    if not notice:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    if notice.get("email_delivery_status") in {"queued", "sending"}:
        return serialize_notice(notice, include_delivery_error=True)
    await notices_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "email_requested": True,
                "email_delivery_status": "queued",
                "email_delivery_error": None,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    notice["email_requested"] = True
    notice["email_delivery_status"] = "queued"
    notice["email_delivery_error"] = None
    schedule_notice_email_delivery(object_id)
    return serialize_notice(notice, include_delivery_error=True)


@app.delete("/api/admin/notices/{notice_id}", response_description="Delete notice")
async def delete_admin_notice(notice_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(notice_id):
        raise HTTPException(status_code=400, detail="공지사항 ID가 올바르지 않습니다.")
    result = await notices_collection.delete_one({"_id": ObjectId(notice_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    return {"message": "공지사항이 삭제되었습니다.", "notice_id": notice_id}


@app.get("/api/admin/dashboard", response_description="Admin dashboard data")
async def get_admin_dashboard(account_id: str):
    await require_admin(account_id)

    users = await users_collection.find().to_list(length=500)
    stories = await stories_collection.find().to_list(length=500)
    vocabularies = await vocabularies_collection.find().to_list(length=1000)
    posts = await community_posts_collection.find().to_list(length=500)
    notices = await notices_collection.find().to_list(length=500)

    stories_by_user = {}
    for story in stories:
        stories_by_user[str(story.get("user_id", ""))] = (
            stories_by_user.get(str(story.get("user_id", "")), 0) + 1
        )

    vocab_by_user = {}
    for vocab in vocabularies:
        vocab_by_user[str(vocab.get("user_id", ""))] = (
            vocab_by_user.get(str(vocab.get("user_id", "")), 0) + 1
        )

    users.sort(
        key=lambda item: serialize_datetime(item.get("created_at")),
        reverse=True,
    )
    stories.sort(
        key=lambda item: serialize_datetime(item.get("updated_at") or item.get("created_at")),
        reverse=True,
    )
    vocabularies.sort(
        key=lambda item: serialize_datetime(item.get("saved_at") or item.get("created_at")),
        reverse=True,
    )
    posts.sort(
        key=lambda item: serialize_datetime(item.get("last_activity_at") or item.get("created_at")),
        reverse=True,
    )
    notices.sort(
        key=lambda item: (
            bool(item.get("is_pinned", False)),
            serialize_datetime(item.get("published_at") or item.get("created_at")),
        ),
        reverse=True,
    )

    comment_count = sum(len(post.get("comments", [])) for post in posts)
    hidden_post_count = sum(1 for post in posts if post.get("is_hidden", False))
    pending_report_count = await reports_collection.count_documents({"status": "pending"})
    active_warning_count = await user_warnings_collection.count_documents(
        {"status": "active"}
    )

    return {
        "stats": {
            "user_count": len(users),
            "local_user_count": sum(1 for user in users if user.get("provider", "local") == "local"),
            "social_user_count": sum(1 for user in users if user.get("provider", "local") != "local"),
            "story_count": len(stories),
            "shared_story_count": sum(1 for story in stories if story.get("is_shared", False)),
            "vocabulary_count": len(vocabularies),
            "community_post_count": len(posts),
            "comment_count": comment_count,
            "hidden_post_count": hidden_post_count,
            "pending_report_count": pending_report_count,
            "active_warning_count": active_warning_count,
            "notice_count": len(notices),
            "deleted_user_count": sum(
                1 for user in users if user.get("account_status") == "deleted"
            ),
        },
        "users": [
            serialize_admin_user(
                user,
                stories_by_user.get(str(user["_id"]), 0),
                vocab_by_user.get(str(user["_id"]), 0),
            )
            for user in users[:200]
        ],
        "stories": [serialize_admin_story(story) for story in stories[:200]],
        "community_posts": [serialize_admin_post(post) for post in posts[:200]],
        "notices": [
            serialize_notice(notice, include_delivery_error=True)
            for notice in notices[:200]
        ],
        "vocabularies": [serialize_vocabulary(vocab) for vocab in vocabularies[:300]],
    }


@app.delete("/api/admin/users/{user_id}", response_description="愿由ъ옄 ?뚯썝 ??젣")
async def admin_delete_user(user_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")

    user_object_id = ObjectId(user_id)
    user = await users_collection.find_one({"_id": user_object_id})
    if not user:
        raise HTTPException(status_code=404, detail="?뚯썝??李얠쓣 ???놁뒿?덈떎.")
    if is_admin_account_id(user.get("account_id")):
        raise HTTPException(status_code=400, detail="愿由ъ옄 怨꾩젙? ??젣?????놁뒿?덈떎.")

    if user.get("account_status") == "deleted":
        return {
            "message": "이미 탈퇴 처리된 사용자입니다.",
            "user_id": user_id,
            "status": "deleted",
        }

    result = await soft_delete_user_account(
        user,
        reason="관리자 처리",
        deleted_by=account_id,
    )
    return {"message": "회원 개인정보 익명화와 탈퇴 처리가 완료되었습니다.", **result}


@app.delete("/api/admin/stories/{story_id}", response_description="愿由ъ옄 ?숉솕 ??젣")
async def admin_delete_story(story_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?숉솕 ID?낅땲??")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="?숉솕瑜?李얠쓣 ???놁뒿?덈떎.")

    await stories_collection.delete_one({"_id": story_object_id})
    await vocabularies_collection.delete_many(
        {"origin_story_id": {"$in": [story_id, story_object_id]}},
    )
    await community_posts_collection.update_many(
        {"story_id": {"$in": [story_id, story_object_id]}},
        {"$unset": {"story_id": ""}},
    )
    return {"message": "?숉솕媛 ??젣?섏뿀?듬땲??", "story_id": story_id}


@app.delete("/api/admin/vocabularies/{vocab_id}", response_description="愿由ъ옄 ?⑥뼱 ??젣")
async def admin_delete_vocabulary(vocab_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(vocab_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?⑥뼱 ID?낅땲??")

    result = await vocabularies_collection.delete_one({"_id": ObjectId(vocab_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="?⑥뼱瑜?李얠쓣 ???놁뒿?덈떎.")
    return {"message": "?⑥뼱媛 ??젣?섏뿀?듬땲??", "vocab_id": vocab_id}


@app.delete("/api/admin/community/posts/{post_id}", response_description="愿由ъ옄 寃뚯떆湲 ??젣")
async def admin_delete_community_post(post_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? 寃뚯떆湲 ID?낅땲??")

    result = await community_posts_collection.delete_one({"_id": ObjectId(post_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
    return {"message": "寃뚯떆湲????젣?섏뿀?듬땲??", "post_id": post_id}


@app.patch("/api/admin/community/posts/{post_id}/visibility", response_description="愿由ъ옄 寃뚯떆湲 ?④? 泥섎━")
async def admin_update_post_visibility(post_id: str, visibility: AdminVisibilitySchema):
    await require_admin(visibility.account_id)
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? 寃뚯떆湲 ID?낅땲??")

    status = "hidden" if visibility.is_hidden else "visible"
    result = await community_posts_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {"is_hidden": visibility.is_hidden, "moderation_status": status}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")

    post = await community_posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="寃뚯떆湲??李얠쓣 ???놁뒿?덈떎.")
    return serialize_admin_post(post)
