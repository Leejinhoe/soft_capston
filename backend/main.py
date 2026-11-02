import os
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import httpx
import bcrypt
import google.generativeai as genai
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

from auth import (
    create_jwt,
    get_google_access_token,
    get_google_user_info,
    get_kakao_access_token,
    get_kakao_user_info,
    get_naver_access_token,
    get_naver_user_info,
)

# 📌 database.py에서 필요한 컬렉션들을 가져옵니다.
from database import (
    users_collection,
    reports_collection,
    stories_collection,
    posts_collection,
    notifications_collection,
    vocabularies_collection,
)

app = FastAPI()

# ----------------------------------------
# 정적 파일 (프로필 이미지 업로드 디렉토리) 설정
# ----------------------------------------
UPLOAD_DIR = "static/profile_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ----------------------------------------
# CORS 설정
# ----------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------
# 国立国語院 (국립국어원) API 키 설정
# ----------------------------------------
DICT_API_KEY = os.getenv("KOREAN_DICT_API_KEY")

async def fetch_korean_dict_definition(word: str) -> str:
    """국립국어원 표준국어대사전 API를 호출하여 단어의 정확한 표준 정의를 가져옵니다."""
    url = "https://stdict.korean.go.kr/api/search.do"
    params = {
        "key": DICT_API_KEY,
        "q": word,
        "req_type": "xml",
        "part": "word",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)

            if response.status_code == 200:
                root = ET.fromstring(response.text)
                definition_node = root.find(".//definition")
                if definition_node is not None and definition_node.text:
                    return definition_node.text.strip()

                return "표준 사전 정의를 찾을 수 없습니다."
    except Exception as e:
        print(f"국립국어원 API 호출 실패: {e}")

    return "사전 정보 불러오기 실패"

# ----------------------------------------
# Gemini API 설정
# ----------------------------------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
llm_model = genai.GenerativeModel("gemini-1.5-flash")


# ----------------------------------------
# 요청 모델 (Pydantic Schema)
# ----------------------------------------
class KakaoCodeRequest(BaseModel):
    code: str

class NaverCodeRequest(BaseModel):
    code: str
    state: str

class GoogleCodeRequest(BaseModel):
    code: str

class IdRequest(BaseModel):
    id: str

class ReportRequest(BaseModel):
    reporter: str
    author: str
    story_title: str
    reason: str

class SignUpRequest(BaseModel):
    id: str
    password: str
    name: str
    birth: str
    email: Optional[str] = None

class LoginRequest(BaseModel):
    id: str
    password: str

class AdminLoginRequest(BaseModel):
    id: str
    password: str

class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class GenerateStoryRequest(BaseModel):
    prompt: str
    genre: str
    age: str

class VocabularySchema(BaseModel):
    user_id: str
    hard: str
    easy: Optional[str] = ""
    definition: Optional[str] = ""
    source_story_title: Optional[str] = "동화"
    origin_story_id: Optional[str] = "650000000000000000000001"
    created_at: Optional[datetime] = None

class SaveStoryRequest(BaseModel):
    user_id: str
    title: str
    content: str
    genre: str
    is_public: bool = False

class ContextSearchRequest(BaseModel):
    word: str
    sentence: str
    age: Optional[str] = "5-7세"


# ----------------------------------------
# 💡 Gemini 단어 원형(기본형) 정제 함수
# ----------------------------------------
async def normalize_word_with_gemini(raw_word: str) -> str:
    """'토끼를' -> '토끼', '작은' -> '작다', '숲으로' -> '숲' 변환"""
    clean_raw = raw_word.strip()
    if not clean_raw:
        return clean_raw

    prompt = f"""
    너는 한국어 어휘 분석 전문가야.
    다음 단어에서 조사, 어미, 접미사를 제거하고 국어사전에 등재된 '기본형' 또는 '원형' 단어 1개만 추출해줘.

    [규칙]
    - 명사 + 조사 ("토끼를", "숲으로") -> 명사 원형 ("토끼", "숲")
    - 용언 관형형 ("작은", "빛나는") -> 기본형 ("작다", "빛나다")
    - 과거형/어미 ("떠났답니다", "웃었어요") -> 기본형 ("떠나다", "웃다")

    입력 단어: {clean_raw}
    응답: 오직 변환된 단어 1개만 텍스트로 출력 (부연설명 금지)
    """
    try:
        response = llm_model.generate_content(prompt)
        normalized = response.text.strip().replace(" ", "").replace("\n", "")
        return normalized if normalized else clean_raw
    except Exception as e:
        print(f"Gemini 단어 정제 오류: {e}")
        clean = re.sub(r"[^\w\s가-힣]", "", clean_raw)
        return re.sub(r"(은|는|이|가|을|를|과|와|으로|로|에서|에게|도|만|의|에)$", "", clean)


# ----------------------------------------
# [신규] 단어장 추가 API (국립국어원 연동)
# ----------------------------------------
@app.post("/api/vocabularies/add", response_description="모르는 단어 추가")
async def add_vocabulary(vocab: VocabularySchema):
    now = vocab.created_at or datetime.utcnow()
    official_definition = await fetch_korean_dict_definition(vocab.hard)

    final_meaning = vocab.definition or vocab.easy or official_definition

    vocab_dict = {
        "user_id": vocab.user_id,
        "word": vocab.hard,
        "meaning": final_meaning,
        "official_definition": official_definition,
        "easy_meaning": vocab.easy,
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
            "official_definition": official_definition,
            "created": bool(result.upserted_id),
        }

    raise HTTPException(status_code=500, detail="단어 등재 실패")


# ----------------------------------------
# 💡 단어 클릭 실시간 조회 (쉬운 뜻 제거 및 다정한 설명 단일화)
# ----------------------------------------
@app.post("/api/vocabularies/search-context")
async def search_vocabulary_with_context(body: ContextSearchRequest):
    raw_word = body.word.strip()
    sentence = body.sentence.strip()
    age = body.age or "5-7세"

    prompt = f"""
    너는 다정한 동화 선생님이야.
    아래 [문장] 속에 나오는 [클릭한 단어]의 조사/어미를 떼어내고, 아이에게 설명해줄 다정한 뜻풀이를 작성해줘.

    [전체 문장]: "{sentence}"
    [클릭한 단어]: "{raw_word}"

    [요구사항]
    1. 'normalized_word': 문맥에 맞게 조사/어미를 뗀 사전용 기본형 단어 1개 (예: "토끼를" -> "토끼", "작은" -> "작다")
    2. 'definition': {age} 아이에게 말해주듯 다정하고 명확한 1~2문장의 뜻풀이

    반드시 아래 JSON 형식으로 응답해줘:
    {{
      "normalized_word": "원형 단어",
      "definition": "다정한 뜻풀이"
    }}
    """

    try:
        response = llm_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        res_json = json.loads(response.text)
        normalized_word = res_json.get("normalized_word", raw_word)
        detailed_def = res_json.get("definition", "")

        if not detailed_def:
            detailed_def = await fetch_korean_dict_definition(normalized_word)

        return {
            "hard": normalized_word,
            "easy": "",
            "definition": detailed_def
        }
    except Exception as e:
        clean_word = re.sub(r"[^\w\s가-힣]", "", raw_word)
        official_def = await fetch_korean_dict_definition(clean_word)
        return {
            "hard": clean_word,
            "easy": "",
            "definition": official_def
        }


# ----------------------------------------
# [신규] 유저별 내 단어장 실시간 조회 API
# ----------------------------------------
@app.get("/api/vocabularies/user/{user_id}")
async def get_user_vocabularies(user_id: str):
    clean_id = user_id.strip()
    vocab_list = []

    cursor = vocabularies_collection.find({"user_id": clean_id}).sort("saved_at", -1)
    async for item in cursor:
        vocab_list.append({
            "id": str(item["_id"]),
            "word": item.get("word", ""),
            "easy": item.get("easy_meaning") or item.get("meaning", ""),
            "definition": item.get("official_definition") or item.get("meaning", ""),
            "source_story_title": item.get("origin_story_title", "동화"),
            "saved_at": item.get("saved_at").isoformat() if item.get("saved_at") else ""
        })

    return vocab_list


# ----------------------------------------
# 💡 동화 생성 + 자동 DB 저장 + 본문 실존 단어 3~5개 추천 API
# ----------------------------------------
@app.post("/api/generate-story")
async def generate_story(body: GenerateStoryRequest):
    story_prompt = f"""
    주제: {body.prompt}
    장르: {body.genre}
    연령대: {body.age}

    위 설정을 바탕으로 아이들이 재미있게 읽을 수 있는 다정한 동화를 한국어로 작성해줘.
    문단 구분을 자연스럽게 해줘.
    """

    try:
        story_response = llm_model.generate_content(story_prompt)
        story_text = story_response.text.strip()
    except Exception as e:
        print(f"동화 생성 오류: {e}")
        story_text = f"옛날 옛날에 {body.prompt}이(가) 살고 있었어요.\n어느 날 {body.genre} 분위기가 물씬 풍기는 신비한 숲 속으로 여행을 떠났답니다.\n숲 속에서 반짝이는 별을 발견하고 행복하게 웃었어요."

    # 1. 💾 [신규] 생성된 동화 무조건 자동 저장 (보관함 수동 저장 버튼 제거 대응)
    now = datetime.utcnow()
    story_doc = {
        "user_id": "user123",
        "title": body.prompt.strip() or "신비한 동화 이야기",
        "content": story_text,
        "genre": body.genre,
        "is_public": False,
        "created_at": now
    }
    saved_story = await stories_collection.insert_one(story_doc)
    story_id = str(saved_story.inserted_id)

    # 2. 📖 본문에 '실제로 존재하는 단어'만 엄격하게 3~5개 추출
    vocab_prompt = f"""
    너는 다정한 어린이 언어 선생님이야.
    아래 [동화 텍스트]를 자세히 읽고, **반드시 텍스트 안에 실제로 등장하는 어휘/표현 중에서만** {body.age} 어린이가 학습하기 좋은 주요 단어 3~5개를 선택해줘.

    [동화 텍스트]
    {story_text}

    [필수 규칙]
    1. 'hard' 항목은 동화 텍스트에 쓰인 단어의 조사/어미를 뗀 기본형/원형으로 작성할 것. (예: 본문에 '날아갔어요'가 있으면 '날아가다')
    2. 절대 동화 텍스트 본문에 없는 단어를 지어내지 마!
    3. 'definition': 아이 눈높이에 맞춘 다정한 뜻풀이 1문장.

    반드시 아래 JSON 배열 형식으로만 응답해줘:
    [
      {{
        "hard": "본문에 있는 단어 원형",
        "definition": "다정한 뜻풀이"
      }}
    ]
    """

    try:
        vocab_response = llm_model.generate_content(
            vocab_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        raw_vocab = json.loads(vocab_response.text)

        # 본문 포함 여부 2차 파이썬 정밀 검증
        vocab_list = []
        for item in raw_vocab:
            word_stem = item.get("hard", "").replace("다", "")
            if word_stem and (word_stem in story_text or item.get("hard") in story_text):
                vocab_list.append(item)
            elif len(vocab_list) < 3:
                vocab_list.append(item)

    except Exception as e:
        print(f"추천 단어 추출 오류: {e}")
        vocab_list = [
            {"hard": "여행", "definition": "새로운 곳으로 떠나는 즐거운 길이에요."},
            {"hard": "친구", "definition": "서로 사이좋게 지내는 다정한 사이예요."}
        ]

    return {
        "story_id": story_id,
        "story": story_text,
        "vocab_list": vocab_list
    }


# ----------------------------------------
# [신규] 생성된 동화 저장 / 커뮤니티 업로드 API
# ----------------------------------------
@app.post("/api/stories/save")
async def save_story(body: SaveStoryRequest):
    now = datetime.utcnow()
    story_doc = {
        "user_id": body.user_id,
        "title": body.title,
        "content": body.content,
        "genre": body.genre,
        "is_public": body.is_public,
        "created_at": now
    }

    result = await stories_collection.insert_one(story_doc)
    story_id = str(result.inserted_id)

    if body.is_public:
        post_doc = {
            "story_id": story_id,
            "user_id": body.user_id,
            "title": body.title,
            "content": body.content,
            "genre": body.genre,
            "likes_count": 0,
            "created_at": now
        }
        await posts_collection.insert_one(post_doc)

    return {"success": True, "message": "동화가 저장되었습니다.", "story_id": story_id}


# ----------------------------------------
# [신규] 사용자 통계 수치 조회 API
# ----------------------------------------
@app.get("/api/users/{user_id}/stats")
async def get_user_stats(user_id: str):
    clean_id = user_id.strip()

    story_count = await stories_collection.count_documents({"user_id": clean_id})
    post_count = await posts_collection.count_documents({"user_id": clean_id})

    pipeline = [
        {"$match": {"user_id": clean_id}},
        {"$group": {"_id": None, "total_likes": {"$sum": "$likes_count"}}}
    ]
    likes_result = await posts_collection.aggregate(pipeline).to_list(length=1)
    total_likes = likes_result[0]["total_likes"] if likes_result else 0

    return {
        "story_count": story_count,
        "post_count": post_count,
        "like_count": total_likes
    }


# ----------------------------------------
# [신규] 유저 알림 목록 조회 API
# ----------------------------------------
@app.get("/api/users/{user_id}/notifications")
async def get_user_notifications(user_id: str):
    clean_id = user_id.strip()
    notifications = []

    cursor = notifications_collection.find({"user_id": clean_id}).sort("created_at", -1)
    async for item in cursor:
        notifications.append({
            "id": str(item["_id"]),
            "title": item.get("title", "알림"),
            "message": item.get("message", ""),
            "is_read": item.get("is_read", False),
            "created_at": item.get("created_at").isoformat() if item.get("created_at") else ""
        })

    return notifications


# ----------------------------------------
# 사용자 프로필 조회 API (GET)
# ----------------------------------------
@app.get("/api/users/{user_id}")
async def get_user_profile(user_id: str):
    clean_id = user_id.strip()

    user = await users_collection.find_one({
        "$or": [
            {"id": clean_id},
            {"social_id": clean_id},
            {"kakao_id": clean_id},
            {"name": clean_id},
            {"nickname": clean_id}
        ]
    })

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    return {
        "nickname": user.get("nickname") or user.get("name") or "사용자",
        "email": user.get("email") or "",
        "bio": user.get("bio") or "상상력이 풍부한 동화 탐험가 ✨",
        "profileImageUrl": user.get("profile_image_url") or None,
        "warning_count": user.get("warning_count", 0)
    }


# ----------------------------------------
# 사용자 프로필 수정 API (PATCH)
# ----------------------------------------
@app.patch("/api/users/{user_id}")
async def update_user_profile(user_id: str, body: ProfileUpdateRequest):
    clean_id = user_id.strip()

    user = await users_collection.find_one({
        "$or": [
            {"id": clean_id},
            {"social_id": clean_id},
            {"kakao_id": clean_id},
            {"name": clean_id},
            {"nickname": clean_id}
        ]
    })

    if not user:
        new_user = {
            "id": clean_id,
            "name": body.nickname or "사용자",
            "nickname": body.nickname or "사용자",
            "email": body.email or "",
            "bio": body.bio or "상상력이 풍부한 동화 탐험가 ✨",
            "role": "user",
            "warning_count": 0,
            "created_at": datetime.utcnow()
        }
        await users_collection.insert_one(new_user)
        return {"success": True, "message": "새 프로필이 생성되었습니다."}

    update_data = {}
    if body.nickname is not None:
        update_data["name"] = body.nickname
        update_data["nickname"] = body.nickname
    if body.email is not None:
        update_data["email"] = body.email
    if body.bio is not None:
        update_data["bio"] = body.bio

    if update_data:
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": update_data}
        )

    return {"success": True, "message": "프로필 정보가 수정되었습니다."}


# ----------------------------------------
# 비밀번호 변경 API (PATCH)
# ----------------------------------------
@app.patch("/api/users/{user_id}/password")
async def change_password(user_id: str, body: PasswordChangeRequest):
    clean_id = user_id.strip()

    user = await users_collection.find_one({
        "$or": [
            {"id": clean_id},
            {"social_id": clean_id},
            {"kakao_id": clean_id},
            {"name": clean_id},
            {"nickname": clean_id}
        ]
    })

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if "password" not in user or not user["password"]:
        raise HTTPException(status_code=400, detail="소셜 로그인 계정은 비밀번호를 변경할 수 없습니다.")

    is_correct = bcrypt.checkpw(
        body.current_password.encode('utf-8'),
        user["password"].encode('utf-8')
    )

    if not is_correct:
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")

    new_hashed_password = bcrypt.hashpw(
        body.new_password.encode('utf-8'),
        bcrypt.gensalt()
    )

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": new_hashed_password.decode('utf-8')}}
    )

    return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}


# ----------------------------------------
# 프로필 이미지 업로드 API (POST)
# ----------------------------------------
@app.post("/api/users/{user_id}/image")
async def upload_user_image(user_id: str, profile_image: UploadFile = File(...)):
    clean_id = user_id.strip()

    user = await users_collection.find_one({
        "$or": [
            {"id": clean_id},
            {"social_id": clean_id},
            {"kakao_id": clean_id},
            {"name": clean_id},
            {"nickname": clean_id}
        ]
    })

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    file_extension = profile_image.filename.split(".")[-1] if profile_image.filename else "png"
    file_name = f"{clean_id}_{int(datetime.utcnow().timestamp())}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    contents = await profile_image.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    image_url = f"http://127.0.0.1:8000/static/profile_images/{file_name}"

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"profile_image_url": image_url}}
    )

    return {"success": True, "imageUrl": image_url}


# ----------------------------------------
# 소셜 로그인 API (카카오 / 네이버 / 구글)
# ----------------------------------------
@app.post("/auth/kakao")
async def kakao_login(body: KakaoCodeRequest):
    access_token = await get_kakao_access_token(body.code)
    user_info = await get_kakao_user_info(access_token)

    await users_collection.update_one(
        {"kakao_id": user_info["kakao_id"]},
        {"$set": {**user_info, "last_login": datetime.utcnow()}},
        upsert=True,
    )
    jwt_token = create_jwt(user_info["kakao_id"])
    return {"access_token": jwt_token, "user": user_info}


@app.post("/auth/naver")
async def naver_login(body: NaverCodeRequest):
    access_token = await get_naver_access_token(body.code, body.state)
    user_info = await get_naver_user_info(access_token)

    await users_collection.update_one(
        {"provider": "naver", "social_id": user_info["social_id"]},
        {"$set": {**user_info, "provider": "naver", "last_login": datetime.utcnow()}},
        upsert=True,
    )
    jwt_token = create_jwt(user_info["social_id"])
    return {"access_token": jwt_token, "user": user_info}


@app.post("/auth/google")
async def google_login(body: GoogleCodeRequest):
    access_token = await get_google_access_token(body.code)
    user_info = await get_google_user_info(access_token)

    await users_collection.update_one(
        {"provider": "google", "social_id": user_info["social_id"]},
        {"$set": {**user_info, "provider": "google", "last_login": datetime.utcnow()}},
        upsert=True,
    )
    jwt_token = create_jwt(user_info["social_id"])
    return {"access_token": jwt_token, "user": user_info}


# ----------------------------------------
# 일반 회원가입 / 로그인 / 중복 검사 API
# ----------------------------------------
@app.post("/check-id")
async def check_id(body: IdRequest):
    user = await users_collection.find_one({"id": body.id})
    return {"available": not bool(user)}


@app.post("/signup")
async def signup(body: SignUpRequest):
    existing_user = await users_collection.find_one({"id": body.id})
    if existing_user:
        return {"success": False, "message": "이미 존재하는 아이디입니다."}

    hashed_password = bcrypt.hashpw(body.password.encode('utf-8'), bcrypt.gensalt())
    user_data = {
        "id": body.id,
        "password": hashed_password.decode('utf-8'),
        "name": body.name,
        "birth": body.birth,
        "email": body.email,
        "role": "user",
        "warning_count": 0,
        "created_at": datetime.utcnow(),
    }
    await users_collection.insert_one(user_data)
    return {"success": True, "message": "회원가입 성공"}


@app.post("/login")
async def login(body: LoginRequest):
    user = await users_collection.find_one({"id": body.id})
    if not user:
        return {"success": False, "message": "존재하지 않는 아이디입니다."}

    is_correct_password = bcrypt.checkpw(body.password.encode('utf-8'), user["password"].encode('utf-8'))
    if not is_correct_password:
        return {"success": False, "message": "비밀번호가 올바르지 않습니다."}

    return {
        "success": True,
        "message": "로그인 성공",
        "user": {"id": user["id"], "name": user["name"], "role": user["role"]}
    }


# ----------------------------------------
# 관리자 API (로그인, 회원 목록, 경고 부여, 삭제, 신고 조회)
# ----------------------------------------
@app.post("/admin-login")
async def admin_login(body: AdminLoginRequest):
    if body.id != "admin" or body.password != "1234":
        return {"success": False, "message": "관리자 정보가 올바르지 않습니다."}
    return {"success": True, "message": "관리자 로그인 성공"}


@app.get("/admin/users")
async def get_users():
    users = []
    async for user in users_collection.find():
        users.append({
            "id": user.get("id") or user.get("social_id") or user.get("kakao_id") or "",
            "name": user.get("name") or user.get("nickname") or "이름 없음",
            "email": user.get("email"),
            "birth": user.get("birth"),
            "role": user.get("role"),
            "warning_count": user.get("warning_count", 0),
            "created_at": str(user.get("created_at")),
        })
    return users


@app.put("/admin/warning/{user_id}")
async def warning_user(user_id: str):
    clean_user_id = user_id.strip()
    query = {
        "$or": [
            {"id": clean_user_id},
            {"social_id": clean_user_id},
            {"kakao_id": clean_user_id},
            {"name": clean_user_id},
            {"nickname": clean_user_id},
            {"email": clean_user_id},
        ]
    }
    user = await users_collection.find_one(query)
    if not user:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")

    current = user.get("warning_count", 0)
    new_warning_count = current + 1

    await users_collection.update_one({"_id": user["_id"]}, {"$set": {"warning_count": new_warning_count}})
    target_user_id = user.get("id") or user.get("social_id") or user.get("kakao_id")
    await notifications_collection.insert_one({
        "user_id": target_user_id,
        "title": "⚠️ 커뮤니티 가이드라인 경고 알림",
        "message": f"서비스 이용 수칙 위반으로 경고가 부여되었습니다. (누적 경고 횟수: {new_warning_count}회)",
        "is_read": False,
        "created_at": datetime.utcnow()
    })
    return {"success": True, "warning_count": new_warning_count}


@app.delete("/admin/user/{user_id}")
async def delete_user(user_id: str):
    result = await users_collection.delete_one({
        "$or": [{"id": user_id}, {"social_id": user_id}, {"kakao_id": user_id}]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    return {"success": True, "message": "회원이 삭제되었습니다."}


@app.post("/report")
async def report_story(body: ReportRequest):
    report = {
        "reporter": body.reporter,
        "author": body.author,
        "story_title": body.story_title,
        "reason": body.reason,
        "status": "waiting",
        "created_at": datetime.utcnow(),
    }
    await reports_collection.insert_one(report)
    return {"success": True, "message": "신고가 접수되었습니다."}


@app.get("/admin/reports")
async def get_admin_reports():
    reports = []
    cursor = reports_collection.find().sort("created_at", -1)
    async for report in cursor:
        reports.append({
            "id": str(report["_id"]),
            "reporter": report.get("reporter", ""),
            "author": report.get("author", ""),
            "story_title": report.get("story_title", ""),
            "reason": report.get("reason", ""),
            "status": report.get("status", "waiting"),
            "created_at": report.get("created_at").isoformat() if report.get("created_at") else "",
        })
    return reports