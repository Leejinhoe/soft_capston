import os
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import httpx
import bcrypt
import google.generativeai as genai
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

from auth import (
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
from quiz import build_questions, card_definition
from security import (
    ROLE_ADMIN,
    ROLE_USER,
    STATUS_ACTIVE,
    BANNED_MESSAGE,
    banned_exception,
    create_access_token,
    get_current_user,
    is_banned,
    new_user_defaults,
    public_user_id,
    require_admin,
    user_summary,
)

app = FastAPI()


# ----------------------------------------
# 기존 사용자 문서에 role / status / warnings 기본값 채우기 (이미 있으면 건드리지 않음)
# ----------------------------------------
@app.on_event("startup")
async def backfill_user_fields():
    defaults = {"role": ROLE_USER, "status": STATUS_ACTIVE, "warnings": []}
    for field, value in defaults.items():
        result = await users_collection.update_many(
            {field: {"$exists": False}}, {"$set": {field: value}}
        )
        if result.modified_count:
            print(f"[users] '{field}' 기본값 채움: {result.modified_count}명", flush=True)

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
# gemini-1.5-flash는 지원 종료(404). 바꾸고 싶으면 .env에 GEMINI_MODEL=... 지정
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
llm_model = genai.GenerativeModel(GEMINI_MODEL)


def log_gemini_error(where: str, e: Exception) -> None:
    """Gemini 호출 실패 시 예비 동작으로 넘어가기 전에 서버 터미널에 원인을 남깁니다."""
    print(
        f"[Gemini 오류] {where} 실패 → 예비 동작 사용 "
        f"(model={GEMINI_MODEL}) {type(e).__name__}: {e}",
        flush=True,
    )


def word_in_story(item: dict, story_text: str) -> bool:
    """추천 단어가 동화 본문에 실제로 들어 있는지 확인합니다.

    - surface: Gemini가 알려준 '본문에 쓰인 그대로'의 표현
    - hard: 기본형 (용언이면 끝의 '다'를 뗀 어간도 확인. 예: '떠나다' → '떠나')
    """
    surface = (item.get("surface") or "").strip()
    hard = (item.get("hard") or "").strip()
    if surface and surface in story_text:
        return True
    if not hard:
        return False
    if hard in story_text:
        return True
    if hard.endswith("다") and len(hard) >= 3 and hard[:-1] in story_text:
        return True
    return False


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
    # 신고자는 토큰에서 꺼냅니다. (요청 본문의 reporter 값은 무시)
    author: str
    story_title: str
    reason: str

class WarningRequest(BaseModel):
    reason: Optional[str] = ""

class UserSummary(BaseModel):
    id: str
    name: str
    role: str
    status: str

class AuthResponse(BaseModel):
    success: bool
    message: str = ""
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserSummary] = None

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
    # user_id는 토큰에서 꺼냅니다.
    hard: str
    easy: Optional[str] = ""
    definition: Optional[str] = ""
    source_story_title: Optional[str] = "동화"
    origin_story_id: Optional[str] = "650000000000000000000001"
    created_at: Optional[datetime] = None

class SaveStoryRequest(BaseModel):
    # user_id는 토큰에서 꺼냅니다.
    title: str
    content: str
    genre: str
    is_public: bool = False

class ContextSearchRequest(BaseModel):
    word: str
    sentence: str
    age: Optional[str] = "5-7세"

class DeleteVocabularyResponse(BaseModel):
    success: bool
    id: str

class QuizQuestion(BaseModel):
    vocab_id: str
    definition: str          # 다정한 뜻풀이 (정답 단어는 ○○로 가림)
    choices: list[str]       # 보기 4개
    answer: str              # 정답 단어 (아이에게 바로 맞음/틀림을 보여주기 위해 함께 보냄)
    is_mastered: bool

class QuizResponse(BaseModel):
    questions: list[QuizQuestion]
    total_words: int
    message: str = ""        # 문제가 없을 때 안내 문구

class QuizResultRequest(BaseModel):
    correct_vocab_ids: list[str] = []
    wrong_vocab_ids: list[str] = []

class QuizResultResponse(BaseModel):
    success: bool
    mastered_count: int


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
        log_gemini_error("단어 원형 정제", e)
        clean = re.sub(r"[^\w\s가-힣]", "", clean_raw)
        return re.sub(r"(은|는|이|가|을|를|과|와|으로|로|에서|에게|도|만|의|에)$", "", clean)


# ----------------------------------------
# [신규] 단어장 추가 API (국립국어원 연동)
# ----------------------------------------
@app.post("/api/vocabularies/add", response_description="모르는 단어 추가")
async def add_vocabulary(vocab: VocabularySchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    now = vocab.created_at or datetime.utcnow()
    official_definition = await fetch_korean_dict_definition(vocab.hard)

    final_meaning = vocab.definition or vocab.easy or official_definition

    vocab_dict = {
        "user_id": user_id,
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
        {"user_id": user_id, "word": vocab.hard},
        {"$setOnInsert": vocab_dict},
        upsert=True,
    )
    saved = await vocabularies_collection.find_one(
        {"user_id": user_id, "word": vocab.hard},
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
async def search_vocabulary_with_context(
    body: ContextSearchRequest, current_user: dict = Depends(get_current_user)
):
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
        log_gemini_error("단어 클릭 뜻풀이(search-context)", e)
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
@app.get("/api/vocabularies/me")
async def get_my_vocabularies(current_user: dict = Depends(get_current_user)):
    clean_id = current_user["user_id"]
    vocab_list = []

    cursor = vocabularies_collection.find({"user_id": clean_id}).sort("saved_at", -1)
    async for item in cursor:
        vocab_list.append({
            "id": str(item["_id"]),
            "word": item.get("word", ""),
            "easy": item.get("easy_meaning") or item.get("meaning", ""),
            # 사전 뜻을 먼저 보여주고, 비어 있거나 실패 문구면 다정한 뜻풀이로 대신합니다.
            "definition": card_definition(item),
            "source_story_title": item.get("origin_story_title", "동화"),
            "saved_at": item.get("saved_at").isoformat() if item.get("saved_at") else "",
            "is_mastered": bool(item.get("is_mastered")),
        })

    return vocab_list


# ----------------------------------------
# 내 단어 삭제
# ----------------------------------------
@app.delete("/api/vocabularies/{vocab_id}", response_model=DeleteVocabularyResponse)
async def delete_my_vocabulary(vocab_id: str, current_user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(vocab_id):
        raise HTTPException(status_code=400, detail="단어 정보가 올바르지 않아요.")

    # 내 단어만 지울 수 있도록 user_id 조건을 함께 겁니다.
    result = await vocabularies_collection.delete_one(
        {"_id": ObjectId(vocab_id), "user_id": current_user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="단어를 찾지 못했어요.")
    return DeleteVocabularyResponse(success=True, id=vocab_id)


# ----------------------------------------
# 단어장 퀴즈: 다정한 뜻풀이를 보고 맞는 단어 고르기 (4지선다, 최대 5문제)
# ----------------------------------------
@app.get("/api/quiz", response_model=QuizResponse)
async def get_quiz(current_user: dict = Depends(get_current_user)):
    vocabs = await vocabularies_collection.find(
        {"user_id": current_user["user_id"]}
    ).to_list(length=1000)

    questions = build_questions(vocabs)
    if not questions:
        return QuizResponse(questions=[], total_words=len(vocabs), message="단어를 먼저 저장해 보세요")
    return QuizResponse(
        questions=[QuizQuestion(**q) for q in questions],
        total_words=len(vocabs),
    )


@app.post("/api/quiz/result", response_model=QuizResultResponse)
async def submit_quiz_result(body: QuizResultRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    now = datetime.utcnow()

    def to_object_ids(ids: list[str]) -> list[ObjectId]:
        return [ObjectId(i) for i in dict.fromkeys(ids) if ObjectId.is_valid(i)]

    correct_ids = to_object_ids(body.correct_vocab_ids)
    wrong_ids = [i for i in to_object_ids(body.wrong_vocab_ids) if i not in correct_ids]

    mastered_count = 0
    if correct_ids:
        result = await vocabularies_collection.update_many(
            {"_id": {"$in": correct_ids}, "user_id": user_id},
            {
                "$set": {"is_mastered": True, "review_stage": "mastered", "last_reviewed_at": now},
                "$inc": {"review_count": 1},
            },
        )
        mastered_count = result.modified_count
    if wrong_ids:
        await vocabularies_collection.update_many(
            {"_id": {"$in": wrong_ids}, "user_id": user_id},
            {"$set": {"last_reviewed_at": now}, "$inc": {"review_count": 1}},
        )

    return QuizResultResponse(success=True, mastered_count=mastered_count)


# ----------------------------------------
# 💡 동화 생성 + 자동 DB 저장 + 본문 실존 단어 3~5개 추천 API
# ----------------------------------------
@app.post("/api/generate-story")
async def generate_story(body: GenerateStoryRequest, current_user: dict = Depends(get_current_user)):
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
        log_gemini_error("동화 생성", e)
        story_text = f"옛날 옛날에 {body.prompt}이(가) 살고 있었어요.\n어느 날 {body.genre} 분위기가 물씬 풍기는 신비한 숲 속으로 여행을 떠났답니다.\n숲 속에서 반짝이는 별을 발견하고 행복하게 웃었어요."

    # 1. 💾 [신규] 생성된 동화 무조건 자동 저장 (보관함 수동 저장 버튼 제거 대응)
    now = datetime.utcnow()
    story_doc = {
        "user_id": current_user["user_id"],
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
    1. 'surface' 항목은 동화 텍스트에 쓰인 모습 그대로 복사할 것. (예: '날아갔어요')
    2. 'hard' 항목은 그 단어의 조사/어미를 뗀 기본형/원형으로 작성할 것. (예: '날아가다')
    3. 절대 동화 텍스트 본문에 없는 단어를 지어내지 마!
    4. 'definition': 아이 눈높이에 맞춘 다정한 뜻풀이 1문장.

    반드시 아래 JSON 배열 형식으로만 응답해줘:
    [
      {{
        "surface": "본문에 쓰인 그대로의 표현",
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
        if not isinstance(raw_vocab, list):
            raise ValueError(f"추천 단어 응답이 배열이 아님: {type(raw_vocab).__name__}")
    except Exception as e:
        log_gemini_error("추천 단어 추출", e)
        raw_vocab = [
            {"hard": "여행", "definition": "새로운 곳으로 떠나는 즐거운 길이에요."},
            {"hard": "친구", "definition": "서로 사이좋게 지내는 다정한 사이예요."}
        ]

    # 최종 목록: 동화 본문에 실제로 들어 있는 단어만 (예비용 기본 단어도 동일하게 검증)
    vocab_list = []
    seen = set()
    for item in raw_vocab:
        if not isinstance(item, dict):
            continue
        hard = (item.get("hard") or "").strip()
        if not hard or hard in seen:
            continue
        if word_in_story(item, story_text):
            vocab_list.append(item)
            seen.add(hard)
        else:
            print(f"[추천 단어 제외] 본문에 없음: {hard!r}", flush=True)
        if len(vocab_list) >= 5:
            break

    return {
        "story_id": story_id,
        "story": story_text,
        "vocab_list": vocab_list
    }


# ----------------------------------------
# [신규] 생성된 동화 저장 / 커뮤니티 업로드 API
# ----------------------------------------
@app.post("/api/stories/save")
async def save_story(body: SaveStoryRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    now = datetime.utcnow()
    story_doc = {
        "user_id": user_id,
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
            "user_id": user_id,
            "title": body.title,
            "content": body.content,
            "genre": body.genre,
            "likes_count": 0,
            "created_at": now
        }
        await posts_collection.insert_one(post_doc)

    return {"success": True, "message": "동화가 저장되었습니다.", "story_id": story_id}


# ----------------------------------------
# 내 정보 (로그인한 사용자 기준, 토큰에서 user_id를 꺼냄)
# ----------------------------------------
@app.get("/api/users/me/stats")
async def get_my_stats(current_user: dict = Depends(get_current_user)):
    clean_id = current_user["user_id"]

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


@app.get("/api/users/me/notifications")
async def get_my_notifications(current_user: dict = Depends(get_current_user)):
    clean_id = current_user["user_id"]
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


@app.get("/api/users/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    user = current_user
    return {
        **user_summary(user),
        "nickname": user.get("nickname") or user.get("name") or "사용자",
        "email": user.get("email") or "",
        "bio": user.get("bio") or "상상력이 풍부한 동화 탐험가 ✨",
        "profileImageUrl": user.get("profile_image_url") or None,
        "warning_count": user.get("warning_count", 0),
    }


@app.patch("/api/users/me")
async def update_my_profile(body: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
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
            {"_id": current_user["_id"]},
            {"$set": update_data}
        )

    return {"success": True, "message": "프로필 정보가 수정되었습니다."}


@app.patch("/api/users/me/password")
async def change_my_password(body: PasswordChangeRequest, current_user: dict = Depends(get_current_user)):
    user = current_user

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


@app.post("/api/users/me/image")
async def upload_my_image(
    profile_image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # 파일 이름에는 영문/숫자/_/-만 사용
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", current_user["user_id"]) or "user"
    file_extension = profile_image.filename.split(".")[-1] if profile_image.filename else "png"
    file_extension = re.sub(r"[^A-Za-z0-9]", "", file_extension)[:5] or "png"
    file_name = f"{safe_id}_{int(datetime.utcnow().timestamp())}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    contents = await profile_image.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    image_url = f"http://127.0.0.1:8000/static/profile_images/{file_name}"

    await users_collection.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"profile_image_url": image_url}}
    )

    return {"success": True, "imageUrl": image_url}


# ----------------------------------------
# 소셜 로그인 API (카카오 / 네이버 / 구글) → JWT 발급
# ----------------------------------------
async def _finish_social_login(filter_query: dict, user_info: dict, extra: dict) -> dict:
    """소셜 사용자 upsert → 정지 확인 → JWT 발급. 첫 로그인이면 role/status/warnings 기본값을 넣습니다."""
    await users_collection.update_one(
        filter_query,
        {
            "$set": {**user_info, **extra, "last_login": datetime.utcnow()},
            "$setOnInsert": new_user_defaults(),
        },
        upsert=True,
    )
    user = await users_collection.find_one(filter_query)
    if not user:
        raise HTTPException(status_code=500, detail="로그인 처리 중 문제가 생겼어요.")
    if is_banned(user):
        raise banned_exception()

    return {
        "success": True,
        "message": "로그인 성공",
        "access_token": create_access_token(public_user_id(user)),
        "user": user_summary(user),
    }


@app.post("/auth/kakao", response_model=AuthResponse)
async def kakao_login(body: KakaoCodeRequest):
    access_token = await get_kakao_access_token(body.code)
    user_info = await get_kakao_user_info(access_token)
    return await _finish_social_login(
        {"kakao_id": user_info["kakao_id"]}, user_info, {"provider": "kakao"}
    )


@app.post("/auth/naver", response_model=AuthResponse)
async def naver_login(body: NaverCodeRequest):
    access_token = await get_naver_access_token(body.code, body.state)
    user_info = await get_naver_user_info(access_token)
    return await _finish_social_login(
        {"provider": "naver", "social_id": user_info["social_id"]}, user_info, {"provider": "naver"}
    )


@app.post("/auth/google", response_model=AuthResponse)
async def google_login(body: GoogleCodeRequest):
    access_token = await get_google_access_token(body.code)
    user_info = await get_google_user_info(access_token)
    return await _finish_social_login(
        {"provider": "google", "social_id": user_info["social_id"]}, user_info, {"provider": "google"}
    )


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
        **new_user_defaults(),  # role=user, status=active, warnings=[]
    }
    await users_collection.insert_one(user_data)
    return {"success": True, "message": "회원가입 성공"}


async def _check_password_login(user_id: str, password: str) -> Optional[dict]:
    """아이디/비밀번호가 맞으면 사용자 문서를, 아니면 None을 돌려줍니다."""
    user = await users_collection.find_one({"id": user_id})
    if not user or not user.get("password"):
        return None
    if not bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
        return None
    return user


@app.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    user = await users_collection.find_one({"id": body.id})
    if not user:
        return {"success": False, "message": "존재하지 않는 아이디입니다."}

    user = await _check_password_login(body.id, body.password)
    if not user:
        return {"success": False, "message": "비밀번호가 올바르지 않습니다."}

    if is_banned(user):
        return {"success": False, "message": BANNED_MESSAGE}

    await users_collection.update_one({"_id": user["_id"]}, {"$set": {"last_login": datetime.utcnow()}})
    return {
        "success": True,
        "message": "로그인 성공",
        "access_token": create_access_token(public_user_id(user)),
        "user": user_summary(user),
    }


# ----------------------------------------
# 관리자 API (로그인, 회원 목록, 경고 부여, 삭제, 신고 조회)
# ----------------------------------------
@app.post("/admin-login", response_model=AuthResponse)
async def admin_login(body: AdminLoginRequest):
    """users 컬렉션에서 role == "admin" 인 계정만 로그인할 수 있습니다."""
    user = await _check_password_login(body.id, body.password)
    if not user or user.get("role") != ROLE_ADMIN:
        return {"success": False, "message": "관리자 정보가 올바르지 않습니다."}
    if is_banned(user):
        return {"success": False, "message": BANNED_MESSAGE}

    await users_collection.update_one({"_id": user["_id"]}, {"$set": {"last_login": datetime.utcnow()}})
    return {
        "success": True,
        "message": "관리자 로그인 성공",
        "access_token": create_access_token(public_user_id(user)),
        "user": user_summary(user),
    }


@app.get("/admin/users")
async def get_users(admin: dict = Depends(require_admin)):
    users = []
    async for user in users_collection.find():
        users.append({
            "id": public_user_id(user),
            "name": user.get("name") or user.get("nickname") or "이름 없음",
            "email": user.get("email"),
            "birth": user.get("birth"),
            "role": user.get("role", ROLE_USER),
            "status": user.get("status", STATUS_ACTIVE),
            "warning_count": user.get("warning_count", 0),
            "created_at": str(user.get("created_at")),
        })
    return users


@app.put("/admin/warning/{user_id}")
async def warning_user(
    user_id: str,
    body: Optional[WarningRequest] = None,
    admin: dict = Depends(require_admin),
):
    clean_user_id = user_id.strip()
    # 신고 목록에는 작성자 '이름'만 있어서 이름/닉네임/이메일로도 찾습니다. (관리자 전용)
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

    now = datetime.utcnow()
    warning_entry = {
        "reason": (body.reason if body else "") or "",
        "admin_id": admin["user_id"],
        "created_at": now,
    }
    new_warning_count = user.get("warning_count", 0) + 1

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"warning_count": new_warning_count}, "$push": {"warnings": warning_entry}},
    )
    target_user_id = public_user_id(user)
    await notifications_collection.insert_one({
        "user_id": target_user_id,
        "title": "⚠️ 커뮤니티 가이드라인 경고 알림",
        "message": f"서비스 이용 수칙 위반으로 경고가 부여되었습니다. (누적 경고 횟수: {new_warning_count}회)",
        "is_read": False,
        "created_at": now
    })
    return {"success": True, "warning_count": new_warning_count}


@app.delete("/admin/user/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없습니다.")
    result = await users_collection.delete_one({
        "$or": [{"id": user_id}, {"social_id": user_id}, {"kakao_id": user_id}]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    return {"success": True, "message": "회원이 삭제되었습니다."}


@app.post("/report")
async def report_story(body: ReportRequest, current_user: dict = Depends(get_current_user)):
    reporter = user_summary(current_user)
    report = {
        "reporter": reporter["name"],
        "reporter_id": reporter["id"],
        "author": body.author,
        "story_title": body.story_title,
        "reason": body.reason,
        "status": "waiting",
        "created_at": datetime.utcnow(),
    }
    await reports_collection.insert_one(report)
    return {"success": True, "message": "신고가 접수되었습니다."}


@app.get("/admin/reports")
async def get_admin_reports(admin: dict = Depends(require_admin)):
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
