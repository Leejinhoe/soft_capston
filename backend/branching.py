"""분기형 동화 API: 첫 장면 → 선택지 고르기 → … → 결말 (장면 생성은 story_engine.py)

stories 문서 (기존 필드 title/content/genre/is_public/created_at은 그대로 유지)
    mode: "branching"
    status: "in_progress" | "completed"   (예전 통짜 동화엔 없음 → completed로 취급)
    topic, age
    scenes: [{text, choices, chosen_index, chosen, is_ending, engine, created_at}]
    choice_history: [{scene, index, choice, at}]   ← 심리분석에서 쓸 고른 선택지 기록
    content: 모든 장면 본문을 빈 줄로 이은 전체 본문 (커뮤니티·관리자·마이페이지가 그대로 씀)
    vocab_list, completed_at: 완료 때 채움
"""
from datetime import datetime
from typing import Optional
import re
import asyncio
import hashlib
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from gridfs.errors import NoFile
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field

from database import database, stories_collection, MEDIA_FILES_BUCKET
import cloudflare_character
import hf_space_video
from story_video_assembly import assemble_scene_videos
from security import get_current_user
from story_engine import (
    CHOICE_COUNT,
    MAX_SCENES,
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
ENGINE_FAILED = "이야기 요정이 잠깐 쉬고 있어요. 조금 뒤에 다시 눌러 주세요."
CHARACTER_NAMES = {
    **{f"male_{i:02d}": name for i, name in enumerate(("민호", "준", "태산", "도윤", "보리", "레이븐", "이안", "하늘"), 1)},
    **{f"female_{i:02d}": name for i, name in enumerate(("미나", "하나", "미란", "루나", "서연", "아린", "나라", "솔"), 1)},
}
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
    character_key: Optional[str] = None


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
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    is_ending: bool = False


class StoryStateResponse(BaseModel):
    story_id: str
    title: str
    topic: str = ""
    genre: str = ""
    age: str = ""
    character_key: Optional[str] = None
    assembled_video_url: Optional[str] = None
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
        character_name=CHARACTER_NAMES.get(doc.get("character_key"), ""),
    )


def _state(doc: dict) -> StoryStateResponse:
    scenes = doc.get("scenes")
    if not scenes:  # 예전 통짜 동화: 본문 전체를 장면 하나로
        scenes = [{"text": doc.get("content") or "", "choices": [], "is_ending": True}]
    return StoryStateResponse(
        story_id=str(doc["_id"]),
        title=doc.get("title") or "제목 없는 이야기",
        topic=doc.get("topic") or "",
        genre=doc.get("genre") or "",
        age=doc.get("age") or "",
        character_key=doc.get("character_key"),
        assembled_video_url=doc.get("assembled_video_url"),
        status=story_status(doc),
        scenes=[
            SceneOut(
                number=i,
                text=s.get("text") or "",
                choices=s.get("choices") or [],
                chosen_index=s.get("chosen_index"),
                image_url=s.get("image_url"),
                video_url=s.get("video_url"),
                is_ending=bool(s.get("is_ending")),
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


async def _generate(method: str, *args) -> SceneResult:
    if _engine is None:
        raise HTTPException(status_code=503, detail=ENGINE_FAILED)
    try:
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
        {"_id": doc["_id"], "user_id": doc["user_id"], "status": STATUS_IN_PROGRESS, "scenes": doc["scenes"]},
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
# API
# ----------------------------------------
@router.post("/api/stories/branching/start", response_model=StoryStateResponse)
async def start_story(body: StartStoryRequest, current_user: dict = Depends(get_current_user)):
    topic = body.prompt.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="동화 주제를 입력해 주세요.")
    if len(topic) > 100:
        raise HTTPException(status_code=400, detail="주제는 100자까지 쓸 수 있어요.")
    if body.character_key and not re.fullmatch(r"(?:male|female)_0[1-8]", body.character_key):
        raise HTTPException(status_code=400, detail="선택할 수 없는 캐릭터예요.")
    setup = StorySetup(topic=topic, genre=body.genre.strip()[:20], age=body.age.strip()[:20] or "5-7세",
                       character_name=CHARACTER_NAMES.get(body.character_key, ""))

    first = await _generate("opening", setup)
    scene = _scene_doc(first, is_ending=False)
    now = datetime.utcnow()
    doc = {
        "user_id": current_user["user_id"],
        "title": topic[:50],  # 완료되면 AI가 지은 제목으로 바뀜
        "topic": topic,
        "genre": setup.genre,
        "age": setup.age,
        "character_key": body.character_key,
        "mode": "branching",
        "status": STATUS_IN_PROGRESS,
        "scenes": [scene],
        "choice_history": [],
        "content": scene["text"],
        "is_public": False,
        "created_at": now,
        "updated_at": now,
    }
    result = await stories_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _state(doc)


@router.get("/api/stories/{story_id}/branching", response_model=StoryStateResponse)
async def get_story_state(story_id: str, current_user: dict = Depends(get_current_user)):
    """이어하기 / 다시 보기 (예전 통짜 동화도 완료된 장면 1개로 보여줌)"""
    return _state(await _my_story(story_id, current_user["user_id"]))


@router.get("/api/stories/{story_id}/scenes/{scene_number}/image")
async def get_scene_image(story_id: str, scene_number: int, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    scenes = doc.get("scenes") or []
    if scene_number < 1 or scene_number > len(scenes):
        raise HTTPException(status_code=404, detail="장면을 찾지 못했어요.")
    scene = scenes[scene_number - 1]
    file_id = scene.get("image_file_id")
    if not file_id:
        url = str(scene.get("image_url") or "")
        prefix = "/api/media/images/"
        file_id = url[len(prefix):] if url.startswith(prefix) else ""
    if not ObjectId.is_valid(str(file_id or "")):
        raise HTTPException(status_code=404, detail="장면 이미지가 없어요.")
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=MEDIA_FILES_BUCKET)
    try:
        stream = await bucket.open_download_stream(ObjectId(str(file_id)))
        if stream.length > 10_000_000:
            raise HTTPException(status_code=413, detail="이미지가 너무 커요.")
        data = await stream.read()
    except NoFile:
        raise HTTPException(status_code=404, detail="장면 이미지가 없어요.")
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "private, no-store"})


@router.get("/api/stories/{story_id}/scenes/{scene_number}/video")
async def get_scene_video(story_id: str, scene_number: int, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    scenes = doc.get("scenes") or []
    if scene_number < 1 or scene_number > len(scenes):
        raise HTTPException(status_code=404, detail="장면을 찾지 못했어요.")
    scene = scenes[scene_number - 1]
    file_id = scene.get("video_file_id")
    if not file_id:
        url = str(scene.get("video_url") or "")
        prefix = "/api/media/videos/"
        file_id = url[len(prefix):] if url.startswith(prefix) else ""
    if not ObjectId.is_valid(str(file_id or "")):
        raise HTTPException(status_code=404, detail="장면 영상이 없어요.")
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=MEDIA_FILES_BUCKET)
    try:
        stream = await bucket.open_download_stream(ObjectId(str(file_id)))
        if stream.length > 30_000_000:
            raise HTTPException(status_code=413, detail="영상이 너무 커요.")
        data = await stream.read()
    except NoFile:
        raise HTTPException(status_code=404, detail="장면 영상이 없어요.")
    return Response(content=data, media_type="video/mp4", headers={"Cache-Control": "private, no-store"})


@router.post("/api/stories/{story_id}/scenes/{scene_number}/video")
async def create_scene_video(story_id: str, scene_number: int, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    scenes = doc.get("scenes") or []
    if scene_number < 1 or scene_number > len(scenes):
        raise HTTPException(status_code=404, detail="장면을 찾지 못했어요.")
    scene = scenes[scene_number - 1]
    if scene.get("video_url") or scene.get("video_file_id"):
        return _state(doc)
    if not hf_space_video.enabled():
        raise HTTPException(status_code=503, detail="영상 생성 서비스가 설정되지 않았어요.")
    source = await get_scene_image(story_id, scene_number, current_user)
    choice = scenes[scene_number - 2].get("chosen") if scene_number > 1 else None
    action = choice or scene.get("text") or ""
    try:
        result = await hf_space_video.generate_scene_video(source.body, action)
        video = result["video_bytes"]
    except Exception:
        raise HTTPException(status_code=503, detail="장면 영상을 생성하지 못했어요. 잠시 후 다시 시도해 주세요.") from None
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=MEDIA_FILES_BUCKET)
    file_id = await bucket.upload_from_stream(
        f"scene-{story_id}-{scene_number}.mp4", video,
        metadata={"owner_user_id": current_user["user_id"], "story_id": story_id,
                  "character_key": doc.get("character_key"), "provider": result.get("provider")},
    )
    idx = scene_number - 1
    update = await stories_collection.update_one(
        {"_id": doc["_id"], "user_id": current_user["user_id"],
         f"scenes.{idx}.text": scene.get("text"),
         f"scenes.{idx}.image_url": scene.get("image_url"),
         f"scenes.{idx}.image_file_id": scene.get("image_file_id"),
         f"scenes.{idx}.video_url": {"$in": [None, ""]},
         f"scenes.{idx}.video_file_id": {"$in": [None, ""]}},
        {"$set": {f"scenes.{idx}.video_file_id": str(file_id),
                  f"scenes.{idx}.video_url": f"/api/media/videos/{file_id}"}},
    )
    if not update.matched_count:
        await bucket.delete(file_id)
    return _state(await _my_story(story_id, current_user["user_id"]))


@router.post("/api/stories/{story_id}/journey-video")
async def create_journey_video(story_id: str, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    if story_status(doc) != STATUS_COMPLETED:
        raise HTTPException(status_code=409, detail="동화를 완성한 후 영상을 만들 수 있어요.")
    scenes = doc.get("scenes") or []
    numbers = [i + 1 for i, scene in enumerate(scenes) if scene.get("video_url") or scene.get("video_file_id")]
    if not numbers:
        raise HTTPException(status_code=409, detail="이어 붙일 장면 영상이 없어요.")
    if len(numbers) > 20:
        raise HTTPException(status_code=400, detail="장면 영상이 너무 많아요.")
    fingerprint = hashlib.sha256("|".join(
        str(scenes[n - 1].get("video_file_id") or scenes[n - 1].get("video_url"))
        for n in numbers
    ).encode()).hexdigest()
    if doc.get("assembled_video_url") and doc.get("assembled_video_fingerprint") == fingerprint:
        return _state(doc)
    clips = []
    for number in numbers:
        response = await get_scene_video(story_id, number, current_user)
        clips.append(response.body)
        if sum(map(len, clips)) > 150_000_000:
            raise HTTPException(status_code=413, detail="장면 영상의 전체 크기가 너무 커요.")
    try:
        video = await asyncio.to_thread(assemble_scene_videos, clips)
    except Exception:
        raise HTTPException(status_code=503, detail="동화 영상을 이어 붙이지 못했어요.") from None
    if len(video) > 30_000_000:
        raise HTTPException(status_code=413, detail="완성 영상이 너무 커요.")
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=MEDIA_FILES_BUCKET)
    file_id = await bucket.upload_from_stream(
        f"journey-{story_id}.mp4", video,
        metadata={"owner_user_id": current_user["user_id"], "story_id": story_id, "type": "journey"},
    )
    result = await stories_collection.update_one(
        {"_id": doc["_id"], "user_id": current_user["user_id"], "scenes": scenes,
         "assembled_video_fingerprint": doc.get("assembled_video_fingerprint")},
        {"$set": {"assembled_video_file_id": str(file_id),
                  "assembled_video_url": f"/api/stories/{story_id}/journey-video?v={file_id}",
                  "assembled_video_fingerprint": fingerprint}},
    )
    if not result.matched_count:
        await bucket.delete(file_id)
        raise HTTPException(status_code=409, detail="장면이 변경됐어요. 다시 시도해 주세요.")
    return _state(await _my_story(story_id, current_user["user_id"]))


@router.get("/api/stories/{story_id}/journey-video")
async def get_journey_video(story_id: str, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    file_id = doc.get("assembled_video_file_id")
    if not ObjectId.is_valid(str(file_id or "")):
        raise HTTPException(status_code=404, detail="완성된 동화 영상이 없어요.")
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=MEDIA_FILES_BUCKET)
    try:
        stream = await bucket.open_download_stream(ObjectId(str(file_id)))
        if stream.length > 30_000_000:
            raise HTTPException(status_code=413, detail="영상이 너무 커요.")
        video = await stream.read()
    except NoFile:
        raise HTTPException(status_code=404, detail="완성된 동화 영상이 없어요.")
    return Response(content=video, media_type="video/mp4", headers={"Cache-Control": "private, no-store"})


@router.post("/api/stories/{story_id}/scenes/{scene_number}/image")
async def create_scene_image(story_id: str, scene_number: int, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    scenes = doc.get("scenes") or []
    if scene_number < 1 or scene_number > len(scenes):
        raise HTTPException(status_code=404, detail="장면을 찾지 못했어요.")
    scene = scenes[scene_number - 1]
    if scene.get("image_url") or scene.get("image_file_id"):
        return _state(doc)
    key = str(doc.get("character_key") or "")
    if not re.fullmatch(r"(?:male|female)_0[1-8]", key):
        raise HTTPException(status_code=400, detail="동화에 선택된 캐릭터가 없어요.")
    if not cloudflare_character.enabled():
        raise HTTPException(status_code=503, detail="이미지 생성 서비스가 설정되지 않았어요.")
    reference = Path(__file__).resolve().parent.parent / "assets" / "characters" / f"{key}_reference_v2.png"
    if not reference.is_file():
        raise HTTPException(status_code=503, detail="캐릭터 이미지를 찾지 못했어요.")
    try:
        scene_text = scene.get("text") or ""
        choice = scenes[scene_number - 2].get("chosen") if scene_number > 1 else None
        if choice:
            scene_text = f"선택한 행동: {choice}\n장면: {scene_text}"
        direction = cloudflare_character.infer_reference_direction(scene_text)
        second = cloudflare_character.directional_reference(key, direction)
        image = await cloudflare_character.generate_scene(
            reference.read_bytes(), scene_text,
            direction_reference=second[1] if second else None,
            direction_view=second[0] if second else None,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="장면 이미지를 생성하지 못했어요. 잠시 후 다시 시도해 주세요.") from None
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=MEDIA_FILES_BUCKET)
    file_id = await bucket.upload_from_stream(
        f"scene-{story_id}-{scene_number}.png", image,
        metadata={"owner_user_id": current_user["user_id"], "story_id": story_id, "character_key": key},
    )
    idx = scene_number - 1
    update = await stories_collection.update_one(
        {"_id": doc["_id"], "user_id": current_user["user_id"],
         f"scenes.{idx}.text": scene.get("text"), f"scenes.{idx}.image_url": {"$in": [None, ""]},
         f"scenes.{idx}.image_file_id": {"$in": [None, ""]}},
        {"$set": {f"scenes.{idx}.image_file_id": str(file_id),
                  f"scenes.{idx}.image_url": f"/api/media/images/{file_id}"}},
    )
    if not update.matched_count:
        await bucket.delete(file_id)
    return _state(await _my_story(story_id, current_user["user_id"]))


@router.post("/api/stories/{story_id}/choose", response_model=StoryStateResponse)
async def choose(story_id: str, body: ChooseRequest, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    scenes = _check_playable(doc, body.scene_number)
    last = scenes[-1]
    if last.get("is_ending") or body.choice_index >= len(last.get("choices") or []):
        raise HTTPException(status_code=400, detail="고를 수 없는 선택지예요.")
    choice = last["choices"][body.choice_index]
    texts = [s["text"] for s in scenes]
    scenes = scenes[:-1] + [{**last, "chosen_index": body.choice_index, "chosen": choice}]
    history = {"scene": len(scenes), "index": body.choice_index, "choice": choice, "at": datetime.utcnow()}

    if len(scenes) + 1 >= MAX_SCENES:  # 마지막 자리 → 고른 선택을 반영한 결말로 자동 마무리
        ending = await _generate("ending", _setup(doc), texts, choice)
        extra = await _completion_fields(doc, scenes, ending)
        new_scene = _scene_doc(ending, is_ending=True)
    else:
        nxt = await _generate("next_scene", _setup(doc), texts, choice)
        extra = {}
        new_scene = _scene_doc(nxt, is_ending=False)

    saved = await _save_step(doc, scenes, new_scene, extra, history)
    return _state(saved)


@router.post("/api/stories/{story_id}/finish", response_model=StoryStateResponse)
async def finish(story_id: str, body: FinishRequest, current_user: dict = Depends(get_current_user)):
    """'이야기 마무리하기': 지금까지 흐름에 맞는 따뜻한 결말 장면을 붙이고 완료"""
    doc = await _my_story(story_id, current_user["user_id"])
    scenes = _check_playable(doc, body.scene_number)
    ending = await _generate("ending", _setup(doc), [s["text"] for s in scenes], None)
    extra = await _completion_fields(doc, scenes, ending)
    saved = await _save_step(doc, scenes, _scene_doc(ending, is_ending=True), extra, None)
    return _state(saved)
