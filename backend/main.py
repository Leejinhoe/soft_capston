import os
import re
import json
from datetime import datetime
from typing import Optional

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
    stories_collection,
    posts_collection,
    notifications_collection,
    notices_collection,
    vocabularies_collection,
)
from community import (
    ensure_indexes as ensure_community_indexes,
    existing_story_ids,
    linked_post_ids,
    remove_post_relations,
    router as community_router,
)
from messages import ensure_indexes as ensure_message_indexes, router as messages_router
from reports import ensure_indexes as ensure_report_indexes, router as reports_router
from admin import notice_visible_query, router as admin_router
from password_reset import ensure_indexes as ensure_password_reset_indexes, router as password_reset_router
from quiz import build_questions, card_definition
from story_text import clean_story_text
from gemini_client import FallbackModel, parse_model_list
from meaning_cache import cached_explain_word, cached_explain_words, ensure_indexes as ensure_meaning_cache_indexes
from word_meaning import is_ambiguous_text, sentence_with, to_dictionary_style
from security import (
    ROLE_ADMIN,
    ROLE_USER,
    STATUS_ACTIVE,
    BANNED_MESSAGE,
    CONTACT_EMAIL,
    PASSWORD_RULE_MESSAGE,
    banned_exception,
    create_access_token,
    get_current_user,
    is_banned,
    is_social_user,
    is_strong_password,
    new_user_defaults,
    public_user_id,
    user_summary,
)

app = FastAPI()
app.include_router(community_router)
app.include_router(reports_router)
app.include_router(messages_router)
app.include_router(admin_router)
app.include_router(password_reset_router)


@app.on_event("startup")
async def create_community_indexes():
    await ensure_community_indexes()
    await ensure_meaning_cache_indexes()
    await ensure_report_indexes()
    await ensure_message_indexes()
    await ensure_password_reset_indexes()


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
# Gemini API 설정
# ----------------------------------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# gemini-1.5-flash는 지원 종료(404). 바꾸고 싶으면 .env에 GEMINI_MODEL=... 지정
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# 한도 초과(429)면 GEMINI_FALLBACK_MODELS(쉼표로 구분) 모델로 자동 재시도 (gemini_client.py)
GEMINI_FALLBACK_MODELS = parse_model_list(os.getenv("GEMINI_FALLBACK_MODELS"))
llm_model = FallbackModel(GEMINI_MODEL, GEMINI_FALLBACK_MODELS)


def log_gemini_error(where: str, e: Exception) -> None:
    """Gemini 호출 실패 시 예비 동작으로 넘어가기 전에 서버 터미널에 원인을 남깁니다."""
    print(
        f"[Gemini 오류] {where} 실패 → 예비 동작 사용 "
        f"(models={llm_model.model_names}) {type(e).__name__}: {e}",
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
    code: str = ""             # banned = 정지된 계정
    contact_email: str = ""    # 정지 안내에 보여 줄 문의 메일 주소

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
    # 보낸 항목만 바꿉니다. (프로필 수정: nickname/bio, 개인정보 수정: name/email)
    nickname: Optional[str] = None
    bio: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None

class MyProfileResponse(BaseModel):
    id: str
    name: str                    # 화면에 보여줄 이름 (닉네임 우선)
    role: str
    status: str
    nickname: str
    real_name: str               # 개인정보: 이름
    email: str
    bio: str
    profileImageUrl: Optional[str] = None
    warning_count: int = 0
    is_social: bool = False      # True면 비밀번호 변경 메뉴 대신 안내 문구
    provider: str = ""

class SimpleResponse(BaseModel):
    success: bool
    message: str = ""

class MyItem(BaseModel):
    """내 동화 / 내 게시글 공통 항목"""
    id: str
    title: str
    content: str
    genre: str = ""
    likes_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    # 동화 ↔ 게시글 연결: 동화면 연결된 게시글 id, 게시글이면 원본 동화 id (없거나 지워졌으면 "")
    linked_id: str = ""

class ItemUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class NoticeItem(BaseModel):
    id: str
    title: str
    content: str
    created_at: str = ""

class WarningItem(BaseModel):
    reason: str
    created_at: str = ""
    is_unread: bool = False

class InboxItem(BaseModel):
    type: str                 # warning / notice
    id: str = ""              # 공지면 공지 id
    title: str
    body: str = ""
    created_at: str = ""
    is_unread: bool = False   # 안 읽은 경고

class MyInboxResponse(BaseModel):
    notices: list[NoticeItem]
    warnings: list[WarningItem]
    # 알림함 화면용: 안 읽은 경고가 먼저, 나머지(읽은 경고 + 공지)는 최신순
    items: list[InboxItem] = []
    unread_warning_count: int = 0

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
    definition: Optional[str] = ""       # 문맥에 맞춘 사전식 한 문장 (팝업에서 받은 값)
    dict_definition: Optional[str] = ""  # 고른 표준국어대사전 원문 뜻 (없으면 "")
    sentence: Optional[str] = ""         # 뜻을 새로 찾을 때 쓰는 문장 (문맥)
    ambiguous: bool = False              # True면 Gemini가 뜻을 못 골라 후보만 보여준 상태 → 저장 때 다시 고름
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
# [신규] 단어장 추가 API (국립국어원 연동)
# ----------------------------------------
@app.post("/api/vocabularies/add", response_description="모르는 단어 추가")
async def add_vocabulary(vocab: VocabularySchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    now = vocab.created_at or datetime.utcnow()

    # 팝업/추천 단어에서 이미 문맥에 맞춘 뜻을 받았으면 그대로 저장합니다.
    # 뜻이 없거나 "뜻이 여러 가지예요"(Gemini 실패) 상태면 지금 다시 고릅니다.
    raw_meaning = vocab.definition or vocab.easy or ""
    pending = vocab.ambiguous or is_ambiguous_text(raw_meaning)
    final_meaning = "" if pending else to_dictionary_style(raw_meaning)
    official_definition = "" if pending else (vocab.dict_definition or "").strip()
    sentence = (vocab.sentence or "").strip()
    if not final_meaning:
        found = await cached_explain_word(llm_model, vocab.hard, sentence or vocab.hard)
        final_meaning = found["definition"]
        official_definition = found["dict_definition"]
        pending = found["ambiguous"]

    vocab_dict = {
        "user_id": user_id,
        "word": vocab.hard,
        "meaning": final_meaning,
        "official_definition": official_definition,
        # 뜻을 아직 못 고른 단어: 확정 뜻으로 두지 않고 단어장을 열 때 다시 고릅니다.
        "meaning_pending": pending,
        "context_sentence": sentence,
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
    if not pending:
        # 예전에 뜻을 못 고른 채 저장된 같은 단어가 있으면 이번에 고른 뜻으로 채웁니다.
        await vocabularies_collection.update_one(
            {"user_id": user_id, "word": vocab.hard, "meaning_pending": True},
            {"$set": {"meaning": final_meaning, "official_definition": official_definition,
                      "meaning_pending": False, "context_sentence": sentence}},
        )
    saved = await vocabularies_collection.find_one(
        {"user_id": user_id, "word": vocab.hard},
    )
    if saved:
        return {
            "message": "단어가 성공적으로 데이터베이스 단어장에 등록되었습니다.",
            "id": str(saved["_id"]),
            "official_definition": official_definition,
            "meaning_pending": pending,
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
    """클릭한 말 → 기본형 + 문맥에 맞는 사전 뜻 (국어사전 형식 한 문장)

    - 기본형 후보(노란 → 노랗다)를 모두 표준국어대사전에서 찾아 모든 뜻을 가져오고,
      Gemini가 문장 문맥에 맞는 뜻을 고릅니다. 맞는 뜻이 없으면 Gemini가 직접 씁니다.
    - source: dictionary(사전 뜻) / ai(직접 씀) / fallback(Gemini 실패)
    - Gemini 실패 시 사전 뜻이 1개면 그대로, 여러 개면 "뜻이 여러 가지예요" + 짧은 뜻 2~3개 (ambiguous=true)
    """
    result = await cached_explain_word(llm_model, body.word, body.sentence.strip(), body.age or "5-7세")
    hard = result["hard"] or re.sub(r"[^\w가-힣]", "", body.word)
    return {
        "hard": hard,
        "easy": "",
        "definition": result["definition"] or "사전에서 뜻을 찾지 못했어요.",
        "dict_definition": result["dict_definition"],
        "source": result["source"],
        "ambiguous": result["ambiguous"],
    }


# ----------------------------------------
# [신규] 유저별 내 단어장 실시간 조회 API
# ----------------------------------------
@app.get("/api/vocabularies/me")
async def get_my_vocabularies(current_user: dict = Depends(get_current_user)):
    clean_id = current_user["user_id"]
    vocab_list = []
    items = await vocabularies_collection.find({"user_id": clean_id}).sort("saved_at", -1).to_list(length=2000)
    await _resolve_pending_meanings(items)

    for item in items:
        vocab_list.append({
            "id": str(item["_id"]),
            "word": item.get("word", ""),
            "easy": item.get("easy_meaning") or item.get("meaning", ""),
            # 사전 뜻을 먼저 보여주고, 비어 있거나 실패 문구면 다정한 뜻풀이로 대신합니다.
            "definition": card_definition(item),
            "source_story_title": item.get("origin_story_title", "동화"),
            "saved_at": item.get("saved_at").isoformat() if item.get("saved_at") else "",
            "is_mastered": bool(item.get("is_mastered")),
            "meaning_pending": bool(item.get("meaning_pending")),
        })

    return vocab_list


RESOLVE_PENDING_PER_REQUEST = 3  # 무료 Gemini 할당량을 아끼려고 한 번에 조금씩만 다시 고릅니다.


async def _resolve_pending_meanings(items: list[dict]) -> None:
    """뜻을 못 고른 채 저장된 단어를 다시 골라 봅니다. (Gemini가 돌아왔으면 확정 뜻으로 바뀜)"""
    pending = [it for it in items if it.get("meaning_pending")][:RESOLVE_PENDING_PER_REQUEST]
    for item in pending:
        found = await cached_explain_word(llm_model, item.get("word", ""), item.get("context_sentence") or item.get("word", ""))
        if found["ambiguous"] or not found["definition"]:
            continue
        fields = {"meaning": found["definition"], "official_definition": found["dict_definition"],
                  "meaning_pending": False}
        await vocabularies_collection.update_one({"_id": item["_id"]}, {"$set": fields})
        item.update(fields)


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

    [형식 규칙]
    - 마크다운을 절대 쓰지 마. (**, *, #, -, ` 같은 기호 금지)
    - 제목은 쓰지 말고 첫 문장부터 바로 이야기를 시작해.
    - 문단 사이는 빈 줄 하나로만 나눠.
    """

    try:
        story_response = llm_model.generate_content(story_prompt)
        # 프롬프트로 막아도 마크다운/제목 줄이 섞여 올 수 있어 저장 전에 한 번 더 정리합니다.
        story_text = clean_story_text(story_response.text) or story_response.text.strip()
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
    4. 'definition': 국어사전처럼 간결한 한 문장 (동사·형용사는 '~다.', 명사는 명사로 끝냄. '~해요/~랍니다' 말투 금지).

    반드시 아래 JSON 배열 형식으로만 응답해줘:
    [
      {{
        "surface": "본문에 쓰인 그대로의 표현",
        "hard": "본문에 있는 단어 원형",
        "definition": "사전식 한 문장."
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
            {"hard": "여행", "definition": "일이나 구경을 위하여 다른 고장이나 나라에 가는 일."},
            {"hard": "친구", "definition": "가깝게 오래 사귄 사람."}
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

    # 3. 추천 단어 뜻: 본문 문장 문맥에 맞는 사전 뜻으로 맞춥니다. (단어 클릭 팝업과 같은 형식, Gemini 1번)
    if vocab_list:
        items = []
        for item in vocab_list:
            hard = item["hard"].strip()
            needles = [(item.get("surface") or "").strip(), hard, hard[:-1] if hard.endswith("다") else ""]
            item["sentence"] = sentence_with(story_text, needles)  # 단어장 저장 때 다시 고를 문맥
            items.append({"word": hard, "sentence": item["sentence"]})
        for item, found in zip(vocab_list, await cached_explain_words(llm_model, items, body.age)):
            item["definition"] = found["definition"] or to_dictionary_style(item.get("definition") or "")
            item["dict_definition"] = found["dict_definition"]
            item["ambiguous"] = found["ambiguous"]

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
            "comments_count": 0,
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


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def iso(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else "")


def _clean_text(value: str, label: str, max_len: int, required: bool) -> str:
    text = value.strip()
    if required and not text:
        raise HTTPException(status_code=400, detail=f"{label}을(를) 입력해 주세요.")
    if len(text) > max_len:
        raise HTTPException(status_code=400, detail=f"{label}은(는) {max_len}자 이하로 적어 주세요.")
    return text


@app.get("/api/users/me", response_model=MyProfileResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    user = current_user
    return MyProfileResponse(
        **user_summary(user),
        nickname=user.get("nickname") or user.get("name") or "사용자",
        real_name=user.get("name") or "",
        email=user.get("email") or "",
        bio=user.get("bio") or "상상력이 풍부한 동화 탐험가 ✨",
        profileImageUrl=user.get("profile_image_url") or None,
        warning_count=user.get("warning_count", 0),
        is_social=is_social_user(user),
        provider=user.get("provider") or "",
    )


@app.patch("/api/users/me", response_model=SimpleResponse)
async def update_my_profile(body: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    update_data = {}
    if body.nickname is not None:
        update_data["nickname"] = _clean_text(body.nickname, "닉네임", 20, required=True)
    if body.bio is not None:
        update_data["bio"] = _clean_text(body.bio, "한 줄 소개", 50, required=False)
    if body.name is not None:
        update_data["name"] = _clean_text(body.name, "이름", 20, required=True)
    if body.email is not None:
        email = _clean_text(body.email, "이메일", 100, required=False)
        if email and not EMAIL_PATTERN.match(email):
            raise HTTPException(status_code=400, detail="이메일 형식이 올바르지 않아요.")
        update_data["email"] = email

    if update_data:
        await users_collection.update_one({"_id": current_user["_id"]}, {"$set": update_data})

    return SimpleResponse(success=True, message="정보가 수정되었어요.")


@app.patch("/api/users/me/password", response_model=SimpleResponse)
async def change_my_password(body: PasswordChangeRequest, current_user: dict = Depends(get_current_user)):
    user = current_user

    if is_social_user(user):
        raise HTTPException(status_code=400, detail="소셜 로그인 계정은 비밀번호를 변경할 수 없어요.")

    if not bcrypt.checkpw(body.current_password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않아요.")

    if not is_strong_password(body.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MESSAGE)

    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="새 비밀번호가 지금 비밀번호와 같아요.")

    new_hashed_password = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt())
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": new_hashed_password.decode("utf-8")}},
    )

    return SimpleResponse(success=True, message="비밀번호가 변경되었어요.")


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
# 마이페이지: 내 동화 / 내 게시글 (토큰의 user_id 기준, 내 것만 보기·수정·삭제)
# ----------------------------------------
STORY_NOT_FOUND = "동화를 찾지 못했어요."
POST_NOT_FOUND = "게시글을 찾지 못했어요."


def _to_my_item(doc: dict, linked_id: str = "") -> MyItem:
    return MyItem(
        id=str(doc["_id"]),
        title=doc.get("title") or "제목 없는 이야기",
        content=doc.get("content") or "",
        genre=doc.get("genre") or "",
        likes_count=int(doc.get("likes_count") or 0),
        created_at=iso(doc.get("created_at")),
        updated_at=iso(doc.get("updated_at")),
        linked_id=linked_id,
    )


def _my_doc_filter(item_id: str, user_id: str) -> dict:
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="잘못된 요청이에요.")
    return {"_id": ObjectId(item_id), "user_id": user_id}


def _item_update_fields(body: ItemUpdateRequest) -> dict:
    fields = {}
    if body.title is not None:
        fields["title"] = _clean_text(body.title, "제목", 50, required=True)
    if body.content is not None:
        fields["content"] = _clean_text(body.content, "내용", 20000, required=True)
    if not fields:
        raise HTTPException(status_code=400, detail="바꿀 내용이 없어요.")
    fields["updated_at"] = datetime.utcnow()
    return fields


async def _story_items(docs: list[dict], user_id: str) -> list[MyItem]:
    links = await linked_post_ids([str(d["_id"]) for d in docs], user_id)
    return [_to_my_item(d, links.get(str(d["_id"]), "")) for d in docs]


async def _post_items(docs: list[dict], user_id: str) -> list[MyItem]:
    alive = await existing_story_ids([d.get("story_id") or "" for d in docs], user_id)
    return [_to_my_item(d, d.get("story_id") if d.get("story_id") in alive else "") for d in docs]


async def _find_mine_or_404(collection, item_id: str, user_id: str, not_found: str) -> dict:
    doc = await collection.find_one(_my_doc_filter(item_id, user_id))
    if not doc:
        raise HTTPException(status_code=404, detail=not_found)
    return doc


async def _delete_my_posts(query: dict) -> int:
    """게시글 삭제 + 딸린 좋아요/스크랩/댓글 정리"""
    ids = [str(d["_id"]) async for d in posts_collection.find(query, {"_id": 1})]
    if not ids:
        return 0
    await posts_collection.delete_many({"_id": {"$in": [ObjectId(i) for i in ids]}})
    await remove_post_relations(ids)
    return len(ids)


# ---------- 내 동화 ----------
@app.get("/api/users/me/stories", response_model=list[MyItem])
async def get_my_stories(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    docs = await stories_collection.find({"user_id": user_id}).sort("created_at", -1).to_list(length=1000)
    return await _story_items(docs, user_id)


@app.get("/api/stories/{story_id}", response_model=MyItem)
async def get_my_story(story_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    doc = await _find_mine_or_404(stories_collection, story_id, user_id, STORY_NOT_FOUND)
    return (await _story_items([doc], user_id))[0]


@app.patch("/api/stories/{story_id}", response_model=MyItem)
async def update_my_story(
    story_id: str,
    body: ItemUpdateRequest,
    sync: bool = False,  # True면 연결된 커뮤니티 글에도 반영
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    query = _my_doc_filter(story_id, user_id)
    fields = _item_update_fields(body)
    result = await stories_collection.update_one(query, {"$set": fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=STORY_NOT_FOUND)
    if sync:
        await posts_collection.update_many({"user_id": user_id, "story_id": story_id}, {"$set": fields})
    return (await _story_items([await stories_collection.find_one(query)], user_id))[0]


@app.delete("/api/stories/{story_id}", response_model=SimpleResponse)
async def delete_my_story(
    story_id: str,
    with_linked: bool = False,  # True면 연결된 커뮤니티 글도 함께 삭제
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    result = await stories_collection.delete_one(_my_doc_filter(story_id, user_id))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=STORY_NOT_FOUND)
    if with_linked:
        await _delete_my_posts({"user_id": user_id, "story_id": story_id})
    return SimpleResponse(success=True, message="삭제했어요.")


# ---------- 내 게시글 ----------
@app.get("/api/users/me/posts", response_model=list[MyItem])
async def get_my_posts(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    docs = await posts_collection.find({"user_id": user_id}).sort("created_at", -1).to_list(length=1000)
    return await _post_items(docs, user_id)


@app.get("/api/posts/{post_id}", response_model=MyItem)
async def get_my_post(post_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    doc = await _find_mine_or_404(posts_collection, post_id, user_id, POST_NOT_FOUND)
    return (await _post_items([doc], user_id))[0]


@app.patch("/api/posts/{post_id}", response_model=MyItem)
async def update_my_post(
    post_id: str,
    body: ItemUpdateRequest,
    sync: bool = False,  # True면 원본 동화(내 동화)에도 반영
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    query = _my_doc_filter(post_id, user_id)
    doc = await _find_mine_or_404(posts_collection, post_id, user_id, POST_NOT_FOUND)
    fields = _item_update_fields(body)
    await posts_collection.update_one(query, {"$set": fields})
    story_id = doc.get("story_id") or ""
    if sync and ObjectId.is_valid(story_id):
        await stories_collection.update_one({"_id": ObjectId(story_id), "user_id": user_id}, {"$set": fields})
    return (await _post_items([await posts_collection.find_one(query)], user_id))[0]


@app.delete("/api/posts/{post_id}", response_model=SimpleResponse)
async def delete_my_post(
    post_id: str,
    with_linked: bool = False,  # True면 원본 동화(내 동화)도 함께 삭제
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    doc = await _find_mine_or_404(posts_collection, post_id, user_id, POST_NOT_FOUND)
    await _delete_my_posts({"_id": doc["_id"], "user_id": user_id})
    story_id = doc.get("story_id") or ""
    if with_linked and ObjectId.is_valid(story_id):
        await stories_collection.delete_one({"_id": ObjectId(story_id), "user_id": user_id})
    return SimpleResponse(success=True, message="삭제했어요.")


# ----------------------------------------
# 마이페이지: 공지사항 + 내가 받은 경고 (users.warnings)
# ----------------------------------------
def _to_notice(doc: dict) -> NoticeItem:
    return NoticeItem(
        id=str(doc["_id"]),
        title=doc.get("title") or "공지사항",
        content=doc.get("content") or "",
        created_at=iso(doc.get("created_at")),
    )


def _warning_unread(warning: dict, seen_at) -> bool:
    """warnings_seen_at(알림함 전체 보기를 연 시각)보다 뒤에 받은 경고는 안 읽은 경고"""
    created = warning.get("created_at")
    if not isinstance(created, datetime):
        return seen_at is None
    return seen_at is None or created > seen_at


@app.get("/api/users/me/inbox", response_model=MyInboxResponse)
async def get_my_inbox(
    limit: int = 0,  # 0이면 전체, 마이페이지 미리보기는 3
    current_user: dict = Depends(get_current_user),
):
    # 전체 공지 + 나를 대상으로 한 공지만 (특정 회원 공지는 그 회원에게만 보임)
    cursor = notices_collection.find(notice_visible_query(current_user["user_id"])).sort("created_at", -1).limit(100)
    notice_docs = [doc async for doc in cursor]
    notices = [_to_notice(doc) for doc in notice_docs]

    # 어떤 관리자가 줬는지는 빼고, 사유와 날짜만 최신순으로 내려줍니다.
    seen_at = current_user.get("warnings_seen_at")
    raw_warnings = [w for w in reversed(current_user.get("warnings") or []) if isinstance(w, dict)]
    warnings = [
        WarningItem(
            reason=w.get("reason") or "이용 수칙 위반",
            created_at=iso(w.get("created_at")),
            is_unread=_warning_unread(w, seen_at),
        )
        for w in raw_warnings
    ]

    def sort_key(item: tuple) -> tuple:
        when, inbox_item = item
        return (inbox_item.is_unread, when if isinstance(when, datetime) else datetime.min)

    rows = [
        (w.get("created_at"), InboxItem(type="warning", title="받은 경고", body=item.reason,
                                        created_at=item.created_at, is_unread=item.is_unread))
        for w, item in zip(raw_warnings, warnings)
    ] + [
        (doc.get("created_at"), InboxItem(type="notice", id=n.id, title=n.title, body=n.content, created_at=n.created_at))
        for doc, n in zip(notice_docs, notices)
    ]
    items = [row[1] for row in sorted(rows, key=sort_key, reverse=True)]
    if limit > 0:
        items = items[:limit]

    return MyInboxResponse(
        notices=notices,
        warnings=warnings,
        items=items,
        unread_warning_count=sum(1 for w in warnings if w.is_unread),
    )


@app.post("/api/users/me/inbox/read", response_model=SimpleResponse)
async def mark_my_inbox_read(current_user: dict = Depends(get_current_user)):
    """알림함 전체 보기를 열면 받은 경고를 모두 읽은 것으로 표시합니다."""
    await users_collection.update_one({"_id": current_user["_id"]}, {"$set": {"warnings_seen_at": datetime.utcnow()}})
    return SimpleResponse(success=True, message="")


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
        return {"success": False, "message": BANNED_MESSAGE, "code": "banned", "contact_email": CONTACT_EMAIL}

    await users_collection.update_one({"_id": user["_id"]}, {"$set": {"last_login": datetime.utcnow()}})
    return {
        "success": True,
        "message": "로그인 성공",
        "access_token": create_access_token(public_user_id(user)),
        "user": user_summary(user),
    }


# ----------------------------------------
# 관리자 로그인 (나머지 관리자 API는 admin.py / reports.py)
# ----------------------------------------
@app.post("/admin-login", response_model=AuthResponse)
async def admin_login(body: AdminLoginRequest):
    """users 컬렉션에서 role == "admin" 인 계정만 로그인할 수 있습니다."""
    user = await _check_password_login(body.id, body.password)
    if not user or user.get("role") != ROLE_ADMIN:
        return {"success": False, "message": "관리자 정보가 올바르지 않습니다."}
    if is_banned(user):
        return {"success": False, "message": BANNED_MESSAGE, "code": "banned", "contact_email": CONTACT_EMAIL}

    await users_collection.update_one({"_id": user["_id"]}, {"$set": {"last_login": datetime.utcnow()}})
    return {
        "success": True,
        "message": "관리자 로그인 성공",
        "access_token": create_access_token(public_user_id(user)),
        "user": user_summary(user),
    }


# 회원·동화·공지 관리 API: /api/admin/... (backend/admin.py)
# 신고: POST /api/reports, 관리자 신고 목록: GET·PATCH /api/admin/reports (backend/reports.py)
