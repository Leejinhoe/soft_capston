import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    community_posts_collection,
    stories_collection,
    users_collection,
    vocabularies_collection,
)
from models import (
    CommunityCommentSchema,
    CommunityPostSchema,
    LoginSchema,
    SceneSchema,
    StorySchema,
    UserSchema,
    VocabularySchema,
)

app = FastAPI(title="동화 생성 앱 백엔드", description="FastAPI 및 MongoDB 연동")

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
    "판타지": "🏰",
    "모험": "🗺️",
    "우정": "🤝",
    "자연": "🌿",
    "동물": "🐰",
    "미스터리": "🔍",
}

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 120_000
ADMIN_ACCOUNT_ID = "1111"


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

    # 기존 DB에 평문으로 들어간 비밀번호도 로그인은 허용하고, 성공 시 해시로 업그레이드한다.
    return hmac.compare_digest(saved_password, password)


def serialize_datetime(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value:
        return str(value)
    return datetime.utcnow().isoformat()


def serialize_optional_datetime(value):
    if not value:
        return None
    return serialize_datetime(value)


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


async def require_admin(account_id: Optional[str]):
    if account_id != ADMIN_ACCOUNT_ID:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    admin = await users_collection.find_one({"account_id": ADMIN_ACCOUNT_ID})
    if not admin:
        raise HTTPException(status_code=404, detail="관리자 계정을 찾을 수 없습니다.")


def serialize_admin_user(user: dict, story_count: int = 0, vocab_count: int = 0):
    return {
        "id": str(user["_id"]),
        "account_id": user.get("account_id"),
        "nickname": user.get("nickname", "이름 없음"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "address": user.get("address"),
        "provider": user.get("provider", "local"),
        "personality_type": user.get("personality_type", "분석 전"),
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
        "author_nickname": story.get("author_nickname", "동화 친구"),
        "title": story.get("title", "제목 없는 동화"),
        "genre": story.get("genre", "동화"),
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
    return {"message": "동화 생성 API 서버가 정상적으로 실행 중입니다!"}


@app.post("/api/users/register", response_description="신규 회원가입")
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
            raise HTTPException(status_code=409, detail="이미 가입된 아이디입니다.")

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
            "message": f"{user.nickname}님, 기존 계정으로 로그인되었습니다.",
            "account_id": user.account_id,
            "id": str(existing["_id"]),
            "status": "existing",
        }

    result = await users_collection.insert_one(user_dict)

    if result.inserted_id:
        return {
            "message": f"{user.nickname}님, 회원가입이 성공적으로 완료되었습니다!",
            "account_id": user.account_id,
            "id": str(result.inserted_id),
            "status": "created",
        }

    raise HTTPException(status_code=500, detail="회원가입 데이터베이스 저장에 실패했습니다.")


@app.post("/api/users/login", response_description="일반 로그인")
async def login_user(login_data: LoginSchema):
    user = await users_collection.find_one({"account_id": login_data.account_id})
    if not user:
        raise HTTPException(status_code=404, detail="가입된 계정을 찾을 수 없습니다.")

    provider = user.get("provider", "local")
    if provider != "local":
        raise HTTPException(
            status_code=400,
            detail="이 계정은 일반 로그인이 아닌 소셜 로그인을 사용해야 합니다.",
        )

    saved_password = user.get("password")
    if not saved_password:
        raise HTTPException(status_code=400, detail="비밀번호가 설정되지 않은 계정입니다.")
    saved_password = str(saved_password)

    if not verify_password(login_data.password, saved_password):
        raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다.")

    update_fields = {"last_login": datetime.utcnow()}
    if not saved_password.startswith(f"{PASSWORD_ALGORITHM}$"):
        update_fields["password"] = hash_password(login_data.password)

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": update_fields},
    )

    return {
        "message": f'{user.get("nickname", "사용자")}님 환영합니다!',
        "id": str(user["_id"]),
        "account_id": user.get("account_id"),
        "nickname": user.get("nickname"),
        "email": user.get("email"),
        "provider": provider,
        "phone": user.get("phone"),
        "address": user.get("address"),
    }


@app.put("/api/users/{account_id}/profile", response_description="유저 추가 정보 업데이트")
async def update_user_profile(account_id: str, update_data: UserUpdateSchema):
    existing_user = await users_collection.find_one({"account_id": account_id})
    if not existing_user:
        raise HTTPException(status_code=404, detail="가입된 계정을 찾을 수 없습니다.")

    update_dict = {}
    for key, value in update_data.model_dump().items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        update_dict[key] = value

    if not update_dict:
        return {
            "message": "업데이트할 정보가 없습니다.",
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
            "message": "프로필 정보가 저장되었습니다.",
            "id": str(user["_id"]),
            "account_id": user.get("account_id"),
            "nickname": user.get("nickname"),
            "email": user.get("email"),
            "provider": user.get("provider", "local"),
            "phone": user.get("phone"),
            "address": user.get("address"),
        }

    return {"message": "저장된 내역이 없거나 이미 최신 상태입니다."}


@app.patch("/api/users/{account_id}/password", response_description="비밀번호 변경")
async def change_password(account_id: str, password_data: PasswordChangeSchema):
    user = await users_collection.find_one({"account_id": account_id})
    if not user:
        raise HTTPException(status_code=404, detail="가입된 계정을 찾을 수 없습니다.")

    if user.get("provider", "local") != "local":
        raise HTTPException(status_code=400, detail="소셜 로그인 계정은 비밀번호를 변경할 수 없습니다.")

    saved_password = user.get("password")
    if not saved_password or not verify_password(
        password_data.current_password,
        str(saved_password),
    ):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 일치하지 않습니다.")

    new_password = password_data.new_password.strip()
    if len(new_password) < 9:
        raise HTTPException(status_code=400, detail="새 비밀번호는 9자 이상이어야 합니다.")

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": hash_password(new_password)}},
    )
    return {"message": "비밀번호가 변경되었습니다."}


@app.get("/api/users/by-account/{account_id}", response_description="계정 ID로 유저 조회")
async def get_user_by_account(account_id: str):
    user = await users_collection.find_one({"account_id": account_id})
    if not user:
        raise HTTPException(status_code=404, detail="해당 계정을 찾을 수 없습니다.")

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
        "title": story.get("title", "제목 없는 동화"),
        "genre": story.get("genre", "동화"),
        "age": story.get("target_age") or story.get("age", ""),
        "prompt": prompt_inputs.get("title", story.get("prompt", story.get("title", ""))),
        "created_at": serialize_datetime(story.get("created_at")),
        "scenes": [serialize_scene(scene) for scene in sorted_scenes],
        "vocab": [serialize_vocabulary(vocab) for vocab in vocabularies or []],
    }


@app.get("/api/users/{user_id}/stories", response_description="사용자 동화 목록 조회")
async def list_user_stories(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")

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


@app.post("/api/stories/create", response_description="새로운 동화 세션 생성")
async def create_story(story: StorySchema):
    if not ObjectId.is_valid(story.user_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")

    now = story.created_at or datetime.utcnow()
    user = await users_collection.find_one({"_id": ObjectId(story.user_id)})
    story_dict = {
        "user_id": story.user_id,
        "author_nickname": (user or {}).get("nickname", "동화 친구"),
        "genre": story.genre,
        "target_age": story.age,
        "difficulty": "보통",
        "title": story.title,
        "emoji": GENRE_EMOJIS.get(story.genre, "📖"),
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
                "difficulty": "보통",
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
            "message": "새로운 동화 생성 프로세스가 개시되었습니다.",
            "story_id": str(result.inserted_id),
        }

    raise HTTPException(status_code=500, detail="동화 세션 생성 데이터베이스 오류")


@app.post("/api/stories/{story_id}/scenes", response_description="동화 하위 장면 추가")
async def push_scene(story_id: str, scene: SceneSchema):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 세션 ID입니다.")

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
        return {"message": f"{scene.step_number}장 데이터가 저장되었습니다."}

    raise HTTPException(status_code=404, detail="해당 동화 세션을 찾을 수 없습니다.")


@app.patch("/api/stories/{story_id}/scenes/{step_number}/video", response_description="장면 미디어 URL 업데이트")
async def update_scene_media(
    story_id: str,
    step_number: int,
    video_url: str,
    image_url: Optional[str] = None,
):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 세션 ID입니다.")

    update_data = {"scenes.$.video_url": video_url}
    if image_url:
        update_data["scenes.$.image_url"] = image_url

    result = await stories_collection.update_one(
        {"_id": ObjectId(story_id), "scenes.step_number": step_number},
        {"$set": update_data},
    )

    if result.modified_count > 0:
        return {"message": f"{step_number}번 장면 미디어 업데이트 성공"}

    raise HTTPException(status_code=404, detail="해당 장면을 찾을 수 없습니다.")


@app.delete("/api/stories/{story_id}", response_description="동화 삭제")
async def delete_story(story_id: str, owner: OwnerActionSchema):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 동화 ID입니다.")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="동화를 찾을 수 없습니다.")

    if owner.user_id:
        if not ObjectId.is_valid(owner.user_id):
            raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")
        if not owner_matches(story.get("user_id"), owner.user_id):
            raise HTTPException(status_code=403, detail="내 동화만 삭제할 수 있습니다.")

    await stories_collection.delete_one({"_id": story_object_id})
    await vocabularies_collection.delete_many(
        {"origin_story_id": {"$in": [story_id, story_object_id]}},
    )
    await community_posts_collection.update_many(
        {"story_id": {"$in": [story_id, story_object_id]}},
        {"$unset": {"story_id": ""}},
    )
    return {"message": "동화와 연결 단어장이 삭제되었습니다.", "story_id": story_id}


@app.patch("/api/stories/{story_id}", response_description="동화 메타데이터 수정")
async def update_story(story_id: str, update: StoryUpdateSchema):
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 동화 ID입니다.")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="동화를 찾을 수 없습니다.")

    if update.user_id:
        if not ObjectId.is_valid(update.user_id):
            raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")
        if not owner_matches(story.get("user_id"), update.user_id):
            raise HTTPException(status_code=403, detail="내 동화만 수정할 수 있습니다.")

    update_fields = {}
    if update.title is not None:
        title = update.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="제목은 비워둘 수 없습니다.")
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
        raise HTTPException(status_code=404, detail="동화를 찾을 수 없습니다.")
    return serialize_story(updated)


@app.post("/api/vocabularies/add", response_description="모르는 단어 추가")
async def add_vocabulary(vocab: VocabularySchema):
    if not ObjectId.is_valid(vocab.user_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")
    if not ObjectId.is_valid(vocab.origin_story_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 동화 ID입니다.")

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
            "message": "단어가 성공적으로 데이터베이스 단어장에 등록되었습니다.",
            "id": str(saved["_id"]),
            "created": bool(result.upserted_id),
        }

    raise HTTPException(status_code=500, detail="단어 적재 실패")


@app.get("/api/users/{user_id}/vocabularies", response_description="사용자 단어장 조회")
async def list_user_vocabularies(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")

    vocabularies = await vocabularies_collection.find(
        {"user_id": user_id_filter(user_id)},
    ).to_list(length=1000)
    vocabularies.sort(
        key=lambda item: serialize_datetime(item.get("saved_at") or item.get("created_at")),
        reverse=True,
    )

    return {"vocabularies": [serialize_vocabulary(vocab) for vocab in vocabularies]}


@app.delete("/api/vocabularies/{vocab_id}", response_description="단어장 항목 삭제")
async def delete_vocabulary(vocab_id: str, owner: OwnerActionSchema):
    if not ObjectId.is_valid(vocab_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 단어 ID입니다.")

    vocab_object_id = ObjectId(vocab_id)
    vocab = await vocabularies_collection.find_one({"_id": vocab_object_id})
    if not vocab:
        raise HTTPException(status_code=404, detail="단어를 찾을 수 없습니다.")

    if owner.user_id:
        if not ObjectId.is_valid(owner.user_id):
            raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")
        if not owner_matches(vocab.get("user_id"), owner.user_id):
            raise HTTPException(status_code=403, detail="내 단어만 삭제할 수 있습니다.")

    await vocabularies_collection.delete_one({"_id": vocab_object_id})
    return {"message": "단어가 삭제되었습니다.", "vocab_id": vocab_id}


def serialize_comment(comment: dict):
    return {
        "id": str(comment.get("_id", "")),
        "author_name": comment.get("author_name", "동화 친구"),
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
        "author_name": post.get("author_name", "동화 친구"),
        "author_account_id": post.get("author_account_id"),
        "story_id": str(post["story_id"]) if post.get("story_id") else None,
        "genre": post.get("genre", "동화"),
        "title": post.get("title", "제목 없는 동화"),
        "preview": post.get("preview", ""),
        "full_text": post.get("full_text", ""),
        "story_emoji": post.get("story_emoji", "📖"),
        "created_at": serialize_datetime(post.get("created_at")),
        "view_count": post.get("view_count", 0),
        "like_count": post.get("like_count", post.get("likes", 0)),
        "liked_by": post.get("liked_by", []),
        "comments": [serialize_comment(comment) for comment in sorted_comments],
    }


@app.get("/api/community/posts", response_description="커뮤니티 게시글 목록")
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


@app.post("/api/community/posts", response_description="동화 게시글 공유")
async def create_community_post(post: CommunityPostSchema):
    post_dict = post.model_dump()
    if post.story_id:
        if not ObjectId.is_valid(post.story_id):
            raise HTTPException(status_code=400, detail="유효하지 않은 동화 ID입니다.")
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

    raise HTTPException(status_code=500, detail="게시글 저장 실패")


@app.get("/api/community/posts/{post_id}", response_description="게시글 상세 조회")
async def get_community_post(post_id: str):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 게시글 ID입니다.")

    await community_posts_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$inc": {"view_count": 1}},
    )
    post = await community_posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return serialize_post(post)


@app.post("/api/community/posts/{post_id}/like", response_description="게시글 좋아요")
async def like_community_post(post_id: str, like: LikeSchema):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 게시글 ID입니다.")

    post_object_id = ObjectId(post_id)
    account_id = like.account_id.strip() if like.account_id else None

    if account_id:
        post = await community_posts_collection.find_one({"_id": post_object_id})
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
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
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return serialize_post(post)


@app.post("/api/community/posts/{post_id}/comments", response_description="게시글 댓글 작성")
async def add_community_comment(post_id: str, comment: CommunityCommentSchema):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 게시글 ID입니다.")

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
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    post = await community_posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return serialize_post(post)


@app.delete("/api/community/posts/{post_id}", response_description="게시글 삭제")
async def delete_community_post(post_id: str, owner: OwnerActionSchema):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 게시글 ID입니다.")
    if not owner.account_id:
        raise HTTPException(status_code=401, detail="로그인 계정 정보가 필요합니다.")

    post_object_id = ObjectId(post_id)
    post = await community_posts_collection.find_one({"_id": post_object_id})
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if post.get("author_account_id") != owner.account_id:
        raise HTTPException(status_code=403, detail="내 게시글만 삭제할 수 있습니다.")

    await community_posts_collection.delete_one({"_id": post_object_id})
    return {"message": "게시글이 삭제되었습니다.", "post_id": post_id}


@app.delete(
    "/api/community/posts/{post_id}/comments/{comment_id}",
    response_description="게시글 댓글 삭제",
)
async def delete_community_comment(
    post_id: str,
    comment_id: str,
    owner: OwnerActionSchema,
):
    if not ObjectId.is_valid(post_id) or not ObjectId.is_valid(comment_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 ID입니다.")
    if not owner.account_id:
        raise HTTPException(status_code=401, detail="로그인 계정 정보가 필요합니다.")

    post_object_id = ObjectId(post_id)
    comment_object_id = ObjectId(comment_id)
    post = await community_posts_collection.find_one({"_id": post_object_id})
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    comments = post.get("comments", [])
    target_comment = next(
        (comment for comment in comments if comment.get("_id") == comment_object_id),
        None,
    )
    if not target_comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")

    is_comment_owner = target_comment.get("author_account_id") == owner.account_id
    is_post_owner = post.get("author_account_id") == owner.account_id
    if not is_comment_owner and not is_post_owner:
        raise HTTPException(status_code=403, detail="내 댓글만 삭제할 수 있습니다.")

    await community_posts_collection.update_one(
        {"_id": post_object_id},
        {"$pull": {"comments": {"_id": comment_object_id}}},
    )
    updated = await community_posts_collection.find_one({"_id": post_object_id})
    if not updated:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return serialize_post(updated)


@app.get("/api/admin/dashboard", response_description="관리자 대시보드 데이터")
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


@app.delete("/api/admin/users/{user_id}", response_description="관리자 회원 삭제")
async def admin_delete_user(user_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 사용자 ID입니다.")

    user_object_id = ObjectId(user_id)
    user = await users_collection.find_one({"_id": user_object_id})
    if not user:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    if user.get("account_id") == ADMIN_ACCOUNT_ID:
        raise HTTPException(status_code=400, detail="관리자 계정은 삭제할 수 없습니다.")

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

    return {"message": "회원 및 연결 데이터가 삭제되었습니다.", "user_id": user_id}


@app.delete("/api/admin/stories/{story_id}", response_description="관리자 동화 삭제")
async def admin_delete_story(story_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 동화 ID입니다.")

    story_object_id = ObjectId(story_id)
    story = await stories_collection.find_one({"_id": story_object_id})
    if not story:
        raise HTTPException(status_code=404, detail="동화를 찾을 수 없습니다.")

    await stories_collection.delete_one({"_id": story_object_id})
    await vocabularies_collection.delete_many(
        {"origin_story_id": {"$in": [story_id, story_object_id]}},
    )
    await community_posts_collection.update_many(
        {"story_id": {"$in": [story_id, story_object_id]}},
        {"$unset": {"story_id": ""}},
    )
    return {"message": "동화가 삭제되었습니다.", "story_id": story_id}


@app.delete("/api/admin/vocabularies/{vocab_id}", response_description="관리자 단어 삭제")
async def admin_delete_vocabulary(vocab_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(vocab_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 단어 ID입니다.")

    result = await vocabularies_collection.delete_one({"_id": ObjectId(vocab_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="단어를 찾을 수 없습니다.")
    return {"message": "단어가 삭제되었습니다.", "vocab_id": vocab_id}


@app.delete("/api/admin/community/posts/{post_id}", response_description="관리자 게시글 삭제")
async def admin_delete_community_post(post_id: str, account_id: str):
    await require_admin(account_id)
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 게시글 ID입니다.")

    result = await community_posts_collection.delete_one({"_id": ObjectId(post_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return {"message": "게시글이 삭제되었습니다.", "post_id": post_id}


@app.patch("/api/admin/community/posts/{post_id}/visibility", response_description="관리자 게시글 숨김 처리")
async def admin_update_post_visibility(post_id: str, visibility: AdminVisibilitySchema):
    await require_admin(visibility.account_id)
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 게시글 ID입니다.")

    status = "hidden" if visibility.is_hidden else "visible"
    result = await community_posts_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {"is_hidden": visibility.is_hidden, "moderation_status": status}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    post = await community_posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return serialize_admin_post(post)
