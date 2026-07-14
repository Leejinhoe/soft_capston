import asyncio
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from gridfs.errors import NoFile
from pydantic import BaseModel
from pymongo import ReturnDocument

from database import (
    community_posts_collection,
    init_database,
    media_files_bucket,
    media_jobs_collection,
    stories_collection,
    users_collection,
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
from hf_media_provider import (
    HfMediaError,
    generate_hf_fairytale_image,
    generate_hf_fairytale_video,
    get_hf_media_config,
)
from models import (
    CommunityCommentSchema,
    CommunityPostSchema,
    LoginSchema,
    MediaGenerationSchema,
    MediaGenerationWithStorySchema,
    SceneSchema,
    StorySchema,
    UserSchema,
    VocabularySchema,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fairytale Backend",
    description="FastAPI and MongoDB backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserUpdateSchema(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
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
MEDIA_JOB_SYNC_INTERVAL_SECONDS = 5
MEDIA_GENERATION_WORKER_INTERVAL_SECONDS = 2
MEDIA_JOB_STALE_SECONDS = 15 * 60
MEDIA_GENERATION_WORKER_ID = f"fastapi-{secrets.token_hex(4)}"
media_job_sync_task: Optional[asyncio.Task] = None
media_generation_worker_task: Optional[asyncio.Task] = None


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


def owner_matches(document_user_id, requested_user_id: Optional[str]) -> bool:
    if not requested_user_id:
        return True
    return str(document_user_id) == str(requested_user_id)


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
    step_number: Optional[int] = None,
    provider: str = "huggingface",
    model: Optional[str] = None,
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
        "step_number": step_number,
        "created_at": datetime.utcnow().isoformat(),
    }
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


async def generate_and_store_backend_media(
    *,
    story_text: str,
    story_id: Optional[str] = None,
    step_number: Optional[int] = None,
    genre: Optional[str] = None,
    age: Optional[str] = None,
    include_video: bool = False,
    width: int = 512,
    height: int = 512,
    flux_steps: int = 1,
    video_width: int = 512,
    video_height: int = 384,
    num_frames: int = 48,
    video_steps: int = 2,
    frame_rate: Optional[int] = None,
    seed: Optional[int] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    started_at = time.monotonic()
    image_task = asyncio.create_task(generate_hf_fairytale_image(
        story_text=story_text,
        genre=genre,
        age=age,
        width=width,
        height=height,
        steps=flux_steps,
        seed=seed,
    ))
    generated = await image_task

    video_generated = None
    video_error = None
    video_task = None
    if include_video:
        video_task = asyncio.create_task(generate_hf_fairytale_video(
            image_bytes=generated["image_bytes"],
            story_text=story_text,
            genre=genre,
            age=age,
            width=video_width,
            height=video_height,
            num_frames=num_frames,
            steps=video_steps,
            seed=seed,
            frame_rate=frame_rate,
        ))

    image_file = await upload_generated_media_file(
        content=generated["image_bytes"],
        content_type=generated["content_type"],
        media_kind="image",
        job_id=job_id,
        story_id=story_id,
        step_number=step_number,
        provider=generated["provider"],
        model=generated["model"],
    )

    if video_task is not None:
        try:
            video_generated = await video_task
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
            step_number=step_number,
            provider=video_generated["provider"],
            model=video_generated["model"],
        )
        video_file_id = video_file["file_id"]
        video_url = video_file["url"]

    scene_saved = False
    if story_id is not None and step_number is not None:
        scene_saved = await persist_scene_media(
            story_id=story_id,
            step_number=step_number,
            image_url=image_url,
            video_url=video_url,
            image_file_id=image_file_id,
            video_file_id=video_file_id,
        )

    elapsed_seconds = round(time.monotonic() - started_at, 2)
    video_status = "not_requested"
    if include_video:
        video_status = "completed" if video_url else "failed"
    metadata = {
        "image_model": generated["model"],
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
        "video_error": video_error,
        "video_parameters": video_generated.get("parameters") if video_generated else None,
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
    include_video: bool = False,
    width: int = 512,
    height: int = 512,
    flux_steps: int = 1,
    video_width: int = 512,
    video_height: int = 384,
    num_frames: int = 48,
    video_steps: int = 2,
    frame_rate: Optional[int] = None,
):
    media = await generate_and_store_backend_media(
        story_text=story_text,
        story_id=story_id,
        step_number=step_number,
        genre=genre,
        age=age,
        include_video=include_video,
        width=width,
        height=height,
        flux_steps=flux_steps,
        video_width=video_width,
        video_height=video_height,
        num_frames=num_frames,
        video_steps=video_steps,
        frame_rate=frame_rate,
    )
    result = media["result"]
    return {**result, "saved": media["scene_saved"]}


def build_media_job_document(
    payload: MediaGenerationWithStorySchema,
    *,
    story_id: Optional[str],
    step_number: Optional[int],
) -> Dict[str, Any]:
    now = datetime.utcnow()
    request_payload = {
        "story_id": story_id,
        "step_number": step_number,
        "story_text": payload.story_text,
        "genre": payload.genre,
        "age": payload.age,
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
    return {
        "story_id": ObjectId(story_id) if story_id else None,
        "step_number": step_number,
        "story_text": payload.story_text,
        "genre": payload.genre,
        "age": payload.age,
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
        "request": request_payload,
        "result": None,
        "result_metadata": None,
        "scene_synced_at": None,
        "schema_version": 2,
    }


async def enqueue_media_job(
    payload: MediaGenerationWithStorySchema,
    *,
    story_id: Optional[str],
    step_number: Optional[int],
):
    job = build_media_job_document(
        payload,
        story_id=story_id,
        step_number=step_number,
    )
    result = await media_jobs_collection.insert_one(job)
    created_job = await media_jobs_collection.find_one({"_id": result.inserted_id})
    if not created_job:
        raise HTTPException(status_code=500, detail="Media job could not be created.")
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
                {"started_at": {"$lt": cutoff}},
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
        {"_id": job["_id"]},
        {
            "$set": {
                "status": "failed",
                "updated_at": now,
                "completed_at": now,
                "error": error_message,
            }
        },
    )


async def complete_media_job_with_backend_provider(job: Dict[str, Any]) -> None:
    job_id = serialize_object_id(job["_id"])
    story_id = serialize_object_id(_media_job_request_value(job, "story_id"))
    step_number = _media_job_request_value(job, "step_number")
    generated = await generate_and_store_backend_media(
        story_text=str(_media_job_request_value(job, "story_text", "")),
        story_id=story_id,
        step_number=step_number,
        genre=_media_job_request_value(job, "genre"),
        age=_media_job_request_value(job, "age"),
        include_video=bool(_media_job_request_value(job, "include_video", False)),
        width=int(_media_job_request_value(job, "width", 512)),
        height=int(_media_job_request_value(job, "height", 512)),
        flux_steps=int(_media_job_request_value(job, "flux_steps", 1)),
        video_width=int(_media_job_request_value(job, "video_width", 512)),
        video_height=int(_media_job_request_value(job, "video_height", 384)),
        num_frames=int(_media_job_request_value(job, "num_frames", 48)),
        video_steps=int(_media_job_request_value(job, "video_steps", 2)),
        frame_rate=(
            int(_media_job_request_value(job, "frame_rate"))
            if _media_job_request_value(job, "frame_rate") is not None
            else None
        ),
        seed=_media_job_request_value(job, "seed"),
        job_id=job_id,
    )

    now = datetime.utcnow()
    image_object_id = coerce_object_id(generated["image_file_id"])
    video_object_id = coerce_object_id(generated["video_file_id"])
    await media_jobs_collection.update_one(
        {"_id": job["_id"]},
        {
            "$set": {
                "status": "completed",
                "updated_at": now,
                "completed_at": now,
                "error": None,
                "image_file_id": image_object_id or generated["image_file_id"],
                "video_file_id": video_object_id or generated["video_file_id"],
                "image_url": generated["image_url"],
                "video_url": generated["video_url"],
                "provider": generated["provider"],
                "result_metadata": generated["metadata"],
                "result": generated["result"],
                "scene_synced_at": now if generated["scene_saved"] or story_id is None else None,
            }
        },
    )


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
    if job.get("status") != "completed":
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
            image_url=image_url,
            video_url=video_url,
            image_file_id=image_file_id,
            video_file_id=video_file_id,
        )
        if scene_saved:
            update_fields["scene_synced_at"] = datetime.utcnow()

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
            "status": "completed",
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
    if media_job_sync_task is None or media_job_sync_task.done():
        media_job_sync_task = asyncio.create_task(media_job_sync_loop())
    if media_generation_worker_task is None or media_generation_worker_task.done():
        media_generation_worker_task = asyncio.create_task(media_generation_worker_loop())


@app.on_event("shutdown")
async def shutdown_event():
    global media_job_sync_task, media_generation_worker_task
    tasks = [media_job_sync_task, media_generation_worker_task]
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


async def require_admin(account_id: Optional[str]):
    if account_id != ADMIN_ACCOUNT_ID:
        raise HTTPException(status_code=403, detail="愿由ъ옄 沅뚰븳???꾩슂?⑸땲??")

    admin = await users_collection.find_one({"account_id": ADMIN_ACCOUNT_ID})
    if not admin:
        raise HTTPException(status_code=404, detail="愿由ъ옄 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")


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


@app.get("/")
async def root():
    return {"message": "?숉솕 ?앹꽦 API ?쒕쾭媛 ?뺤긽?곸쑝濡??ㅽ뻾 以묒엯?덈떎!"}


@app.post("/api/users/register", response_description="Register user")
async def register_user(user: UserSchema):
    user_dict = user.model_dump()
    if user_dict.get("password"):
        user_dict["password"] = hash_password(user_dict["password"])
    user_dict["social_info"] = {
        "provider": user.provider,
        "social_id": user.provider_id or user.account_id,
    }
    user_dict["last_login"] = None
    user_dict["schema_version"] = 1

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
        return {
            "message": f"{user.nickname}?? 湲곗〈 怨꾩젙?쇰줈 濡쒓렇?몃릺?덉뒿?덈떎.",
            "account_id": user.account_id,
            "id": str(existing["_id"]),
            "status": "existing",
        }

    result = await users_collection.insert_one(user_dict)

    if result.inserted_id:
        return {
            "message": f"{user.nickname}?? ?뚯썝媛?낆씠 ?깃났?곸쑝濡??꾨즺?섏뿀?듬땲??",
            "account_id": user.account_id,
            "id": str(result.inserted_id),
            "status": "created",
        }

    raise HTTPException(status_code=500, detail="?뚯썝媛???곗씠?곕쿋?댁뒪 ??μ뿉 ?ㅽ뙣?덉뒿?덈떎.")


@app.post("/api/users/login", response_description="User login")
async def login_user(login_data: LoginSchema):
    user = await users_collection.find_one({"account_id": login_data.account_id})
    if not user:
        raise HTTPException(status_code=404, detail="媛?낅맂 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")

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
    }


@app.put("/api/users/{account_id}/profile", response_description="?좎? 異붽? ?뺣낫 ?낅뜲?댄듃")
async def update_user_profile(account_id: str, update_data: UserUpdateSchema):
    existing_user = await users_collection.find_one({"account_id": account_id})
    if not existing_user:
        raise HTTPException(status_code=404, detail="媛?낅맂 怨꾩젙??李얠쓣 ???놁뒿?덈떎.")

    update_dict = {}
    for key, value in update_data.model_dump().items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
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
        "video_url": scene.get("video_url"),
        "image_url": scene.get("image_url"),
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
async def create_story(story: StorySchema):
    if not ObjectId.is_valid(story.user_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?ъ슜??ID?낅땲??")

    now = story.created_at or datetime.utcnow()
    user = await users_collection.find_one({"_id": ObjectId(story.user_id)})
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


@app.post("/api/stories/{story_id}/scenes", response_description="?숉솕 ?섏쐞 ?λ㈃ 異붽?")
async def push_scene(story_id: str, scene: SceneSchema):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?몄뀡 ID?낅땲??")

    scene_dict = {
        "step_number": scene.step_number,
        "content": scene.story_text,
        "audio_url": "",
        "options": [],
        "user_choice_key": f"choice_{scene.step_number}" if scene.choice_made else "",
        "user_choice": scene.choice_made,
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
    image_url: Optional[str] = None,
):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="Invalid story ID.")

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
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    image_file_id: Optional[str] = None,
    video_file_id: Optional[str] = None,
):
    update_data = {}
    if image_url:
        update_data["scenes.$.image_url"] = image_url
    if video_url:
        update_data["scenes.$.video_url"] = video_url
    if image_file_id:
        update_data["scenes.$.image_file_id"] = image_file_id
    if video_file_id:
        update_data["scenes.$.video_file_id"] = video_file_id
    if not update_data:
        return False

    result = await stories_collection.update_one(
        {"_id": ObjectId(story_id), "scenes.step_number": step_number},
        {"$set": {**update_data, "updated_at": datetime.utcnow()}},
    )
    return result.matched_count > 0


async def stream_gridfs_file(file_id: str):
    object_id = coerce_object_id(file_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Invalid file_id.")

    try:
        grid_out = await media_files_bucket.open_download_stream(object_id)
    except NoFile:
        raise HTTPException(status_code=404, detail="Media file not found.")

    metadata = getattr(grid_out, "metadata", None) or {}
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


@app.get("/api/media/files/{file_id}", response_description="Serve stored media file")
async def get_media_file(file_id: str):
    return await stream_gridfs_file(file_id)


@app.get("/api/media/images/{file_id}", response_description="Serve stored generated image")
async def get_media_image(file_id: str):
    return await stream_gridfs_file(file_id)


@app.get("/api/media/videos/{file_id}", response_description="Serve stored generated video")
async def get_media_video(file_id: str):
    return await stream_gridfs_file(file_id)


@app.get("/api/media/health", response_description="Media queue health")
async def media_health():
    provider_config = get_hf_media_config()
    pending_count = await media_jobs_collection.count_documents({"status": "pending"})
    running_count = await media_jobs_collection.count_documents({"status": "running"})
    failed_count = await media_jobs_collection.count_documents({"status": "failed"})
    completed_count = await media_jobs_collection.count_documents({"status": "completed"})

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
            "failed": failed_count,
            "sync_loop": bool(media_job_sync_task and not media_job_sync_task.done()),
        },
    }


@app.post("/api/media/jobs", status_code=202)
async def create_media_job(payload: MediaGenerationWithStorySchema):
    story_id, step_number = normalize_media_story_target(
        payload.story_id,
        payload.step_number,
        require_positive_step=True,
    )
    if story_id is not None and step_number is not None:
        await ensure_story_scene_exists(story_id, step_number)

    return await enqueue_media_job(
        payload,
        story_id=story_id,
        step_number=step_number,
    )


@app.post("/api/stories/{story_id}/scenes/{step_number}/media/jobs", status_code=202)
async def create_scene_media_job(
    story_id: str,
    step_number: int,
    payload: MediaGenerationSchema,
):
    story_id, step_number = normalize_media_story_target(
        story_id,
        step_number,
        require_positive_step=True,
    )
    await ensure_story_scene_exists(story_id, step_number)

    job_payload = MediaGenerationWithStorySchema(
        story_text=payload.story_text,
        genre=payload.genre,
        age=payload.age,
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
    )


@app.get("/api/media/jobs/{job_id}")
async def get_media_job(job_id: str):
    job = await load_media_job(job_id)
    return serialize_media_job_document(job)


@app.post("/api/media/generate", response_description="Generate fairytale scene media")
async def generate_media(payload: MediaGenerationWithStorySchema):
    story_id, step_number = normalize_media_story_target(
        payload.story_id,
        payload.step_number,
        require_positive_step=True,
    )
    if story_id is not None and step_number is not None:
        await ensure_story_scene_exists(story_id, step_number)

    try:
        return await execute_media_generation(
            story_text=payload.story_text,
            story_id=story_id,
            step_number=step_number,
            genre=payload.genre,
            age=payload.age,
            include_video=payload.include_video,
            width=payload.width,
            height=payload.height,
            flux_steps=payload.flux_steps,
            video_width=payload.video_width,
            video_height=payload.video_height,
            num_frames=payload.num_frames,
            video_steps=payload.video_steps,
            frame_rate=payload.frame_rate,
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
):
    story_id, step_number = normalize_media_story_target(
        story_id,
        step_number,
        require_positive_step=True,
    )
    await ensure_story_scene_exists(story_id, step_number)

    try:
        media = await execute_media_generation(
            story_text=payload.story_text,
            story_id=story_id,
            step_number=step_number,
            genre=payload.genre,
            age=payload.age,
            include_video=payload.include_video,
            width=payload.width,
            height=payload.height,
            flux_steps=payload.flux_steps,
            video_width=payload.video_width,
            video_height=payload.video_height,
            num_frames=payload.num_frames,
            video_steps=payload.video_steps,
            frame_rate=payload.frame_rate,
        )
    except HfMediaError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media generation failed: {e}")

    if not media.get("saved"):
        raise HTTPException(status_code=404, detail="Generated media could not be saved to the scene.")
    return media

@app.delete("/api/stories/{story_id}", response_description="?숉솕 ??젣")
async def delete_story(story_id: str, owner: OwnerActionSchema):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?숉솕 ID?낅땲??")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="?숉솕瑜?李얠쓣 ???놁뒿?덈떎.")

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
async def update_story(story_id: str, update: StoryUpdateSchema):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="?좏슚?섏? ?딆? ?숉솕 ID?낅땲??")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="?숉솕瑜?李얠쓣 ???놁뒿?덈떎.")

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
async def delete_vocabulary(vocab_id: str, owner: OwnerActionSchema):
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
    return {
        "id": str(comment.get("_id", "")),
        "author_name": comment.get("author_name", "?숉솕 移쒓뎄"),
        "author_account_id": comment.get("author_account_id"),
        "content": comment.get("content", ""),
        "created_at": serialize_datetime(comment.get("created_at")),
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
    posts = await community_posts_collection.find().to_list(length=200)
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
        {"_id": ObjectId(post_id)},
        {"$inc": {"view_count": 1}},
    )
    post = await community_posts_collection.find_one({"_id": ObjectId(post_id)})
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


@app.get("/api/admin/dashboard", response_description="Admin dashboard data")
async def get_admin_dashboard(account_id: str):
    await require_admin(account_id)

    users = await users_collection.find().to_list(length=500)
    stories = await stories_collection.find().to_list(length=500)
    vocabularies = await vocabularies_collection.find().to_list(length=1000)
    posts = await community_posts_collection.find().to_list(length=500)

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

    comment_count = sum(len(post.get("comments", [])) for post in posts)
    hidden_post_count = sum(1 for post in posts if post.get("is_hidden", False))

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
    if user.get("account_id") == ADMIN_ACCOUNT_ID:
        raise HTTPException(status_code=400, detail="愿由ъ옄 怨꾩젙? ??젣?????놁뒿?덈떎.")

    await users_collection.delete_one({"_id": user_object_id})
    await stories_collection.delete_many({"user_id": user_id_filter(user_id)})
    await vocabularies_collection.delete_many({"user_id": user_id_filter(user_id)})
    if user.get("account_id"):
        await community_posts_collection.delete_many(
            {"author_account_id": user.get("account_id")},
        )
        await community_posts_collection.update_many(
            {},
            {"$pull": {"comments": {"author_account_id": user.get("account_id")}}},
        )

    return {"message": "?뚯썝 諛??곌껐 ?곗씠?곌? ??젣?섏뿀?듬땲??", "user_id": user_id}


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
