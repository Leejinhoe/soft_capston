"""분기형 동화 API: 첫 장면 → 선택지 고르기 → … → 결말 (장면 생성은 story_engine.py)

API는 두 가지 모양 (내용은 같음)
    - 일반: POST /api/stories/branching/start, /{id}/choose, /{id}/finish → 최종 상태 JSON
    - 스트리밍: 같은 주소 + /stream → NDJSON 이벤트 (Colab이 글을 쓰는 대로 화면에 보여 주기, 아래 _stream 설명)
      화면은 스트리밍을 먼저 쓰고, 스트리밍 연결이 안 되면 일반 API로

stories 문서 (기존 필드 title/content/genre/is_public/created_at은 그대로 유지)
    mode: "branching"
    status: "in_progress" | "completed"   (예전 통짜 동화엔 없음 → completed로 취급)
    topic, age
    scenes: [{text, choices, chosen_index, chosen, is_ending, engine, created_at}]
        engine: 만든 엔진 colab(팀원 Colab) / gemini / template → 화면에 작게 표시
    choice_history: [{scene, index, choice, at, emotion?}]   ← 심리분석에서 쓸 고른 선택지 기록
        emotion: Colab이 장면을 만들었을 때 받은 고른 선택지의 KOTE 감정 (colab_client.compact_emotion)
    colab_story_id: Colab 서버가 준 story_id (Colab이 첫 장면을 만들었을 때만)
    scene_images: {"1": "/static/story_images/...jpg"}  ← 장면 그림 (story_images.py, scenes 배열과 따로 저장)
    content: 모든 장면 본문을 빈 줄로 이은 전체 본문 (커뮤니티·관리자·마이페이지가 그대로 씀)
    vocab_list, completed_at: 완료 때 채움
"""
import asyncio
import json
from datetime import datetime
from typing import Awaitable, Callable, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import stories_collection
from security import get_current_user
from story_engine import (
    CHOICE_COUNT,
    MAX_SCENES,
    Emit,
    SceneResult,
    StoryEngine,
    StoryEngineError,
    StorySetup,
    build_story_engine,
    default_title,
)
from story_vocab import recommend_vocab

router = APIRouter(tags=["분기형 동화"])

STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STORY_NOT_FOUND = "동화를 찾지 못했어요."
ENGINE_FAILED = "이야기를 다 만들지 못했어요. 조금 뒤에 다시 눌러 주세요."
ALREADY_MOVED = "이야기가 벌써 다음으로 넘어갔어요. 화면을 새로 불러올게요."

_engine: Optional[StoryEngine] = None
_vocab_model = None
_on_error = None


def configure(model, on_error=None, engine: Optional[StoryEngine] = None) -> None:
    """main.py가 시작할 때 Gemini 모델을 넘겨줍니다. (테스트에서는 가짜 모델/엔진)"""
    global _engine, _vocab_model, _on_error
    _engine = engine or build_story_engine(model)
    _vocab_model = model
    _on_error = on_error


# ----------------------------------------
# 스키마
# ----------------------------------------
class StartStoryRequest(BaseModel):
    prompt: str = Field(..., description="주제/주인공")
    genre: str
    age: str = "5-7세"


class ChooseRequest(BaseModel):
    scene_number: int = Field(..., description="선택지를 고른 장면 번호 (1부터, 지금 마지막 장면이어야 함)")
    choice_index: int = Field(..., ge=0, lt=CHOICE_COUNT)


class FinishRequest(BaseModel):
    scene_number: int = Field(..., description="지금 마지막 장면 번호 (두 번 눌림 방지)")


class SceneOut(BaseModel):
    number: int
    text: str
    choices: list[str] = []
    chosen_index: Optional[int] = None
    is_ending: bool = False
    engine: str = ""                      # colab / gemini / template
    image_url: Optional[str] = None       # "/static/story_images/..." (앞에 서버 주소를 붙여서 씀)
    image_failed: bool = False            # 그림을 못 받음 → 그림 없이 보여 주기


class StoryStateResponse(BaseModel):
    story_id: str
    title: str
    topic: str = ""
    genre: str = ""
    age: str = ""
    status: str
    scenes: list[SceneOut]
    content: str
    max_scenes: int = MAX_SCENES
    vocab_list: list[dict] = []


# ----------------------------------------
# 도우미
# ----------------------------------------
def story_status(doc: dict) -> str:
    return doc.get("status") or STATUS_COMPLETED


def _join(scenes: list[dict]) -> str:
    return "\n\n".join(s["text"] for s in scenes if s.get("text"))


def _scene_doc(result: SceneResult, is_ending: bool) -> dict:
    return {
        "text": result.text,
        "choices": [] if is_ending else result.choices,
        "chosen_index": None,
        "chosen": None,
        "is_ending": is_ending,
        "engine": result.engine,
        "created_at": datetime.utcnow(),
    }


def _setup(doc: dict) -> StorySetup:
    return StorySetup(
        topic=doc.get("topic") or doc.get("title") or "",
        genre=doc.get("genre") or "",
        age=doc.get("age") or "5-7세",
        remote_story_id=doc.get("colab_story_id") or "",
        previous_choices=[c for sc in (doc.get("scenes") or []) for c in (sc.get("choices") or []) if isinstance(c, str)],
    )


def _state(doc: dict) -> StoryStateResponse:
    scenes = doc.get("scenes")
    if not scenes:  # 예전 통짜 동화: 본문 전체를 장면 하나로
        scenes = [{"text": doc.get("content") or "", "choices": [], "is_ending": True}]
    images = doc.get("scene_images") or {}
    failed = doc.get("scene_image_failed") or {}
    return StoryStateResponse(
        story_id=str(doc["_id"]),
        title=doc.get("title") or "제목 없는 이야기",
        topic=doc.get("topic") or "",
        genre=doc.get("genre") or "",
        age=doc.get("age") or "",
        status=story_status(doc),
        scenes=[
            SceneOut(
                number=i,
                text=s.get("text") or "",
                choices=s.get("choices") or [],
                chosen_index=s.get("chosen_index"),
                is_ending=bool(s.get("is_ending")),
                engine=s.get("engine") or "",
                image_url=images.get(str(i)) or None,
                image_failed=bool(failed.get(str(i))),
            )
            for i, s in enumerate(scenes, 1)
        ],
        content=doc.get("content") or _join(scenes),
        vocab_list=doc.get("vocab_list") or [],
    )


def _oid(story_id: str) -> ObjectId:
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=404, detail=STORY_NOT_FOUND)
    return ObjectId(story_id)


async def _my_story(story_id: str, user_id: str) -> dict:
    doc = await stories_collection.find_one({"_id": _oid(story_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail=STORY_NOT_FOUND)
    return doc


def _check_playable(doc: dict, scene_number: int) -> list[dict]:
    """진행 중인 분기형 동화이고, scene_number가 지금 마지막 장면인지 확인"""
    scenes = doc.get("scenes") or []
    if story_status(doc) != STATUS_IN_PROGRESS or not scenes:
        raise HTTPException(status_code=409, detail="이미 끝난 이야기예요.")
    if scene_number != len(scenes):
        raise HTTPException(status_code=409, detail=ALREADY_MOVED)
    return scenes


async def _generate(method: str, *args, emit: Emit = None) -> SceneResult:
    if _engine is None:
        raise HTTPException(status_code=503, detail=ENGINE_FAILED)
    try:
        if emit is not None:
            return await getattr(_engine, method)(*args, emit=emit)
        return await getattr(_engine, method)(*args)
    except StoryEngineError:
        raise HTTPException(status_code=503, detail=ENGINE_FAILED)


async def _save_step(doc: dict, scenes: list[dict], new_scene: dict, extra_set: dict, history: Optional[dict]) -> dict:
    """장면 수가 그대로일 때만 저장 (동시에 두 번 눌러도 장면이 한 번만 붙음)
    scenes: 고른 선택지까지 반영한 기존 장면들"""
    all_scenes = scenes + [new_scene]
    update: dict = {"$set": {**extra_set, "scenes": all_scenes, "content": _join(all_scenes), "updated_at": datetime.utcnow()}}
    if history:
        update["$push"] = {"choice_history": history}
    result = await stories_collection.update_one(
        {"_id": doc["_id"], "user_id": doc["user_id"], "status": STATUS_IN_PROGRESS, "scenes": {"$size": len(scenes)}},
        update,
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail=ALREADY_MOVED)
    return await stories_collection.find_one({"_id": doc["_id"]})


async def _completion_fields(doc: dict, scenes: list[dict], ending: SceneResult) -> dict:
    """결말이 나오면: 제목 + 전체 본문 기준 추천 단어"""
    full_text = _join(scenes + [{"text": ending.text}])
    vocab = await recommend_vocab(_vocab_model, full_text, doc.get("age") or "5-7세", on_error=_on_error)
    return {
        "status": STATUS_COMPLETED,
        "title": ending.title or default_title(doc.get("topic") or ""),
        "vocab_list": vocab,
        "completed_at": datetime.utcnow(),
    }


# ----------------------------------------
# 만들기 + 저장 (일반 API와 스트리밍 API가 같이 씀)
#   prepare_*: 요청 확인 (잘못된 요청은 스트리밍 시작 전에 보통 HTTP 오류로)
#   run_*: 장면 만들기 → DB 저장 → 최종 상태
# ----------------------------------------
def _prepare_start(body: StartStoryRequest) -> StorySetup:
    topic = body.prompt.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="동화 주제를 입력해 주세요.")
    if len(topic) > 100:
        raise HTTPException(status_code=400, detail="주제는 100자까지 쓸 수 있어요.")
    return StorySetup(topic=topic, genre=body.genre.strip()[:20], age=body.age.strip()[:20] or "5-7세")


async def _run_start(setup: StorySetup, user_id: str, emit: Emit = None) -> StoryStateResponse:
    first = await _generate("opening", setup, emit=emit)
    scene = _scene_doc(first, is_ending=False)
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "title": setup.topic[:50],  # 완료되면 AI가 지은 제목으로 바뀜
        "topic": setup.topic,
        "genre": setup.genre,
        "age": setup.age,
        "mode": "branching",
        "status": STATUS_IN_PROGRESS,
        "scenes": [scene],
        "choice_history": [],
        "content": scene["text"],
        "is_public": False,
        **({"colab_story_id": first.remote_story_id} if first.remote_story_id else {}),
        "created_at": now,
        "updated_at": now,
    }
    result = await stories_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _state(doc)


async def _prepare_choose(story_id: str, body: ChooseRequest, user_id: str) -> dict:
    doc = await _my_story(story_id, user_id)
    scenes = _check_playable(doc, body.scene_number)
    last = scenes[-1]
    if last.get("is_ending") or body.choice_index >= len(last.get("choices") or []):
        raise HTTPException(status_code=400, detail="고를 수 없는 선택지예요.")
    choice = last["choices"][body.choice_index]
    return {
        "doc": doc,
        "texts": [s["text"] for s in scenes],
        "choice": choice,
        "scenes": scenes[:-1] + [{**last, "chosen_index": body.choice_index, "chosen": choice}],
        "history": {"scene": len(scenes), "index": body.choice_index, "choice": choice, "at": datetime.utcnow()},
    }


async def _run_choose(ctx: dict, emit: Emit = None) -> StoryStateResponse:
    doc, scenes, texts, choice, history = ctx["doc"], ctx["scenes"], ctx["texts"], ctx["choice"], ctx["history"]
    if len(scenes) + 1 >= MAX_SCENES:  # 마지막 자리 → 고른 선택을 반영한 결말로 자동 마무리
        result = await _generate("ending", _setup(doc), texts, choice, emit=emit)
        _status(emit, "🧺 배울 단어를 골라 담고 있어요")
        extra = await _completion_fields(doc, scenes, result)
        new_scene = _scene_doc(result, is_ending=True)
    else:
        result = await _generate("next_scene", _setup(doc), texts, choice, emit=emit)
        extra = {}
        new_scene = _scene_doc(result, is_ending=False)
    if result.choice_emotion:  # Colab이 만든 장면이면 고른 선택지의 감정도 같이 (심리분석용)
        history["emotion"] = result.choice_emotion
    saved = await _save_step(doc, scenes, new_scene, extra, history)
    return _state(saved)


async def _prepare_finish(story_id: str, body: FinishRequest, user_id: str) -> dict:
    doc = await _my_story(story_id, user_id)
    return {"doc": doc, "scenes": _check_playable(doc, body.scene_number)}


async def _run_finish(ctx: dict, emit: Emit = None) -> StoryStateResponse:
    doc, scenes = ctx["doc"], ctx["scenes"]
    ending = await _generate("ending", _setup(doc), [s["text"] for s in scenes], None, emit=emit)
    _status(emit, "🧺 배울 단어를 골라 담고 있어요")
    extra = await _completion_fields(doc, scenes, ending)
    saved = await _save_step(doc, scenes, _scene_doc(ending, is_ending=True), extra, None)
    return _state(saved)


def _status(emit: Emit, message: str) -> None:
    if emit is not None:
        emit({"type": "status", "message": message})


# ----------------------------------------
# 스트리밍 응답 (NDJSON 한 줄에 이벤트 하나)
#   {"type": "engine", "engine": "colab" | "gemini" | "template"}  이 엔진이 쓰기 시작
#   {"type": "text", "text": "지금까지 쓴 본문"}                    Colab이 글자를 내보낼 때마다 (전체 본문)
#   {"type": "status", "message": "..."}                            선택지·제목·단어 준비 중
#   {"type": "reset"}                                               쓰던 글 실패 → 화면의 글을 지움
#   {"type": "state", "state": StoryStateResponse}                  DB 저장까지 끝난 최종 상태 (마지막 줄)
#   {"type": "error", "status": 409|503|..., "message": "..."}      실패 (마지막 줄)
# 만들기는 별도 작업으로 돌아서, 화면이 중간에 닫혀도 끝까지 만들고 저장합니다. (다시 열면 이어하기로 보임)
# ----------------------------------------
_background: set = set()


def _stream(job: Callable[[Emit], Awaitable[StoryStateResponse]]) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue()

    async def runner() -> None:
        try:
            state = await job(queue.put_nowait)
            queue.put_nowait({"type": "state", "state": state.model_dump(mode="json")})
        except HTTPException as e:
            queue.put_nowait({"type": "error", "status": e.status_code, "message": e.detail})
        except Exception as e:
            print(f"[분기형 동화] 스트리밍 만들기 오류: {type(e).__name__}: {e}", flush=True)
            queue.put_nowait({"type": "error", "status": 500, "message": ENGINE_FAILED})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(runner())
    _background.add(task)
    task.add_done_callback(_background.discard)

    async def lines():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


# ----------------------------------------
# API
# ----------------------------------------
@router.post("/api/stories/branching/start", response_model=StoryStateResponse)
async def start_story(body: StartStoryRequest, current_user: dict = Depends(get_current_user)):
    return await _run_start(_prepare_start(body), current_user["user_id"])


@router.post("/api/stories/branching/start/stream")
async def start_story_stream(body: StartStoryRequest, current_user: dict = Depends(get_current_user)):
    """첫 장면을 스트리밍으로 (NDJSON 이벤트는 위 설명)"""
    setup = _prepare_start(body)
    user_id = current_user["user_id"]
    return _stream(lambda emit: _run_start(setup, user_id, emit))


@router.get("/api/stories/{story_id}/branching", response_model=StoryStateResponse)
async def get_story_state(story_id: str, current_user: dict = Depends(get_current_user)):
    """이어하기 / 다시 보기 (예전 통짜 동화도 완료된 장면 1개로 보여줌)"""
    return _state(await _my_story(story_id, current_user["user_id"]))


@router.post("/api/stories/{story_id}/choose", response_model=StoryStateResponse)
async def choose(story_id: str, body: ChooseRequest, current_user: dict = Depends(get_current_user)):
    return await _run_choose(await _prepare_choose(story_id, body, current_user["user_id"]))


@router.post("/api/stories/{story_id}/choose/stream")
async def choose_stream(story_id: str, body: ChooseRequest, current_user: dict = Depends(get_current_user)):
    """선택 → 다음 장면(또는 8장면째 결말)을 스트리밍으로"""
    ctx = await _prepare_choose(story_id, body, current_user["user_id"])
    return _stream(lambda emit: _run_choose(ctx, emit))


@router.post("/api/stories/{story_id}/finish", response_model=StoryStateResponse)
async def finish(story_id: str, body: FinishRequest, current_user: dict = Depends(get_current_user)):
    """'이야기 마무리하기': 지금까지 흐름에 맞는 따뜻한 결말 장면을 붙이고 완료"""
    return await _run_finish(await _prepare_finish(story_id, body, current_user["user_id"]))


@router.post("/api/stories/{story_id}/finish/stream")
async def finish_stream(story_id: str, body: FinishRequest, current_user: dict = Depends(get_current_user)):
    """'이야기 마무리하기'를 스트리밍으로"""
    ctx = await _prepare_finish(story_id, body, current_user["user_id"])
    return _stream(lambda emit: _run_finish(ctx, emit))
