"""심리분석 API: 완료된 분기형 동화의 choice_history로 아이의 놀이 속 성향을 보여 줍니다. (분석은 psych_engine.py)

- 결과는 그 동화 문서의 psych_analysis에 저장 → 다시 볼 때 Gemini를 또 부르지 않음
    psych_analysis: {traits{5가지 0~100}, insights[{scene, choice, options, insight}], summary, questions[2], engine, analyzed_at}
- 심리 화면(GET /api/psych/me)을 열 때 아직 분석 안 된 완료 동화만 최신순으로 최대 ANALYZE_PER_VISIT개 분석
- 분석 중 표시(psych_claimed_at)로 동시에 두 번 열어도 같은 동화를 두 번 분석하지 않음
- 분석이 실패하면 저장하지 않고 다음에 다시 시도 (한도 초과일 수 있으니 그 방문에서는 더 시도하지 않음)
"""
from datetime import datetime, timedelta
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import safe_create_index, stories_collection
from psych_engine import (
    TRAIT_KEYS,
    TRAITS,
    ChoiceStep,
    PsychEngine,
    PsychEngineError,
    PsychInput,
    build_psych_engine,
)
from security import get_current_user

router = APIRouter(tags=["심리분석"])

ANALYZE_PER_VISIT = 3
TREND_COUNT = 5
CLAIM_TIMEOUT = timedelta(minutes=2)

NOTICE = (
    "놀이 속 선택을 바탕으로 한 참고용 이야기예요. 아이의 마음을 진단하는 검사가 아니니, "
    "아이와 즐겁게 대화를 나누는 데 가볍게 활용해 주세요."
)
EMPTY_MESSAGE = "동화를 끝까지 만들면 분석해 줄게요!"
NOT_ANALYZABLE = "선택지를 골라 가며 끝까지 만든 동화만 볼 수 있어요."
ENGINE_FAILED = "분석 요정이 잠깐 쉬고 있어요. 조금 뒤에 다시 열어 주세요."

_engine: Optional[PsychEngine] = None
_on_error = None


def configure(model, on_error=None, engine: Optional[PsychEngine] = None) -> None:
    """main.py가 시작할 때 Gemini 모델을 넘겨줍니다. (테스트에서는 가짜 모델/엔진)"""
    global _engine, _on_error
    _engine = engine or build_psych_engine(model)
    _on_error = on_error


async def ensure_indexes() -> None:
    await safe_create_index(stories_collection, [("user_id", 1), ("status", 1), ("completed_at", -1)])


# ----------------------------------------
# 스키마
# ----------------------------------------
class TraitInfo(BaseModel):
    key: str
    label: str


class ChoiceInsight(BaseModel):
    scene: int
    choice: str
    options: list[str] = []
    insight: str


class PsychStoryCard(BaseModel):
    story_id: str
    title: str
    genre: str = ""
    completed_at: Optional[datetime] = None
    choice_count: int
    analyzed: bool
    traits: Optional[dict[str, int]] = None
    top_trait: Optional[str] = None  # 가장 높은 성향 key
    summary: str = ""


class TrendPoint(BaseModel):
    story_id: str
    title: str
    completed_at: Optional[datetime] = None
    traits: dict[str, int]


class PsychOverviewResponse(BaseModel):
    traits: list[TraitInfo]
    notice: str
    message: str = ""                       # 동화가 없을 때 안내 / 분석 대기 안내
    completed_count: int                    # 분석할 수 있는 완료 동화 수
    analyzed_count: int
    pending_count: int                      # 아직 분석 못 한 동화 수 (다음에 열 때 이어서)
    newly_analyzed: int                     # 이번에 새로 분석한 수
    average: Optional[dict[str, int]] = None  # 분석된 동화 전체 평균 (레이더 차트)
    trend: list[TrendPoint] = []            # 최근 분석 동화 5개, 오래된 것 → 최근 (꺾은선)
    stories: list[PsychStoryCard] = []      # 최근 완료 순


class PsychDetailResponse(BaseModel):
    story_id: str
    title: str
    genre: str = ""
    completed_at: Optional[datetime] = None
    traits_info: list[TraitInfo]
    traits: dict[str, int]
    insights: list[ChoiceInsight]
    summary: str
    questions: list[str]
    notice: str


# ----------------------------------------
# 도우미
# ----------------------------------------
def _trait_infos() -> list[TraitInfo]:
    return [TraitInfo(key=k, label=label) for k, label in TRAITS]


def _analyzable_query(user_id: str) -> dict:
    """완료된 분기형 동화 중 선택을 1번 이상 한 것"""
    return {"user_id": user_id, "status": "completed", "mode": "branching", "choice_history.0": {"$exists": True}}


def _build_input(doc: dict) -> PsychInput:
    scenes = doc.get("scenes") or []
    steps = []
    for h in doc.get("choice_history") or []:
        number = int(h.get("scene") or 0)
        scene = scenes[number - 1] if 1 <= number <= len(scenes) else {}
        steps.append(ChoiceStep(
            scene=number,
            scene_text=scene.get("text") or "",
            options=list(scene.get("choices") or []),
            choice=h.get("choice") or "",
        ))
    return PsychInput(
        story_id=str(doc["_id"]),
        title=doc.get("title") or "",
        topic=doc.get("topic") or "",
        genre=doc.get("genre") or "",
        age=doc.get("age") or "5-7세",
        steps=steps,
    )


async def analyze_story(doc: dict) -> Optional[dict]:
    """동화 하나 분석 → 저장한 psych_analysis. 다른 요청이 분석 중이면 None, 엔진 실패면 PsychEngineError."""
    if _engine is None:
        raise PsychEngineError("심리분석 엔진이 준비되지 않았어요.")
    now = datetime.utcnow()
    claimed = await stories_collection.update_one(
        {
            "_id": doc["_id"],
            "psych_analysis": {"$exists": False},
            "$or": [{"psych_claimed_at": {"$exists": False}}, {"psych_claimed_at": {"$lt": now - CLAIM_TIMEOUT}}],
        },
        {"$set": {"psych_claimed_at": now}},
    )
    if claimed.modified_count == 0:
        return None

    data = _build_input(doc)
    try:
        result = await _engine.analyze(data)
    except Exception as e:
        await stories_collection.update_one({"_id": doc["_id"]}, {"$unset": {"psych_claimed_at": ""}})
        if _on_error:
            _on_error("심리분석", e)
        raise PsychEngineError(str(e)) from e

    analysis = {
        "traits": result.traits,
        "insights": [
            {"scene": step.scene, "choice": step.choice, "options": step.options, "insight": insight}
            for step, insight in zip(data.steps, result.insights)
        ],
        "summary": result.summary,
        "questions": result.questions,
        "engine": result.engine,
        "analyzed_at": datetime.utcnow(),
    }
    await stories_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"psych_analysis": analysis}, "$unset": {"psych_claimed_at": ""}},
    )
    return analysis


def _top_trait(traits: dict[str, int]) -> str:
    return max(TRAIT_KEYS, key=lambda k: traits.get(k, 0))


def _average(items: list[dict[str, int]]) -> Optional[dict[str, int]]:
    if not items:
        return None
    return {k: round(sum(t.get(k, 0) for t in items) / len(items)) for k in TRAIT_KEYS}


def _completed_sort_key(doc: dict) -> datetime:
    return doc.get("completed_at") or doc.get("created_at") or datetime.min


# ----------------------------------------
# API
# ----------------------------------------
@router.get("/api/psych/me", response_model=PsychOverviewResponse)
async def my_psych(current_user: dict = Depends(get_current_user)):
    """심리 화면: 아직 분석 안 된 완료 동화 최대 3개 분석 → 평균(레이더) + 최근 5개 변화(꺾은선) + 동화별 카드"""
    query = _analyzable_query(current_user["user_id"])

    # 1) 분석 안 된 동화 최신순 최대 3개
    newly = 0
    pending_cursor = (
        stories_collection.find({**query, "psych_analysis": {"$exists": False}})
        .sort("completed_at", -1)
        .limit(ANALYZE_PER_VISIT)
    )
    async for doc in pending_cursor:
        try:
            if await analyze_story(doc):
                newly += 1
        except PsychEngineError:
            break  # 한도 초과일 수 있으니 이번에는 그만, 다음에 열 때 다시

    # 2) 목록 (본문은 빼고)
    projection = {"title": 1, "genre": 1, "completed_at": 1, "created_at": 1, "choice_history": 1, "psych_analysis": 1}
    docs = [d async for d in stories_collection.find(query, projection)]
    docs.sort(key=_completed_sort_key, reverse=True)

    cards: list[PsychStoryCard] = []
    analyzed: list[dict] = []
    for d in docs:
        analysis = d.get("psych_analysis")
        traits = (analysis or {}).get("traits")
        if traits:
            analyzed.append(d)
        cards.append(PsychStoryCard(
            story_id=str(d["_id"]),
            title=d.get("title") or "제목 없는 이야기",
            genre=d.get("genre") or "",
            completed_at=d.get("completed_at"),
            choice_count=len(d.get("choice_history") or []),
            analyzed=bool(traits),
            traits=traits,
            top_trait=_top_trait(traits) if traits else None,
            summary=(analysis or {}).get("summary") or "",
        ))

    trend = [
        TrendPoint(
            story_id=str(d["_id"]),
            title=d.get("title") or "제목 없는 이야기",
            completed_at=d.get("completed_at"),
            traits=d["psych_analysis"]["traits"],
        )
        for d in reversed(analyzed[:TREND_COUNT])
    ]
    pending = len(docs) - len(analyzed)
    if not docs:
        message = EMPTY_MESSAGE
    elif pending:
        message = f"아직 살펴보는 중인 동화가 {pending}개 있어요. 조금 뒤에 다시 열면 이어서 분석해 줄게요."
    else:
        message = ""

    return PsychOverviewResponse(
        traits=_trait_infos(),
        notice=NOTICE,
        message=message,
        completed_count=len(docs),
        analyzed_count=len(analyzed),
        pending_count=pending,
        newly_analyzed=newly,
        average=_average([d["psych_analysis"]["traits"] for d in analyzed]),
        trend=trend,
        stories=cards,
    )


@router.get("/api/psych/stories/{story_id}", response_model=PsychDetailResponse)
async def psych_detail(story_id: str, current_user: dict = Depends(get_current_user)):
    """동화 하나의 상세 분석. 아직 분석 전이면 이때 분석 (Gemini 1번)"""
    if not ObjectId.is_valid(story_id):
        raise HTTPException(status_code=404, detail=NOT_ANALYZABLE)
    doc = await stories_collection.find_one({**_analyzable_query(current_user["user_id"]), "_id": ObjectId(story_id)})
    if not doc:
        raise HTTPException(status_code=404, detail=NOT_ANALYZABLE)

    analysis = doc.get("psych_analysis")
    if not analysis:
        try:
            analysis = await analyze_story(doc)
        except PsychEngineError:
            raise HTTPException(status_code=503, detail=ENGINE_FAILED)
        if analysis is None:  # 다른 요청이 분석 중
            raise HTTPException(status_code=409, detail="지금 이 동화를 살펴보는 중이에요. 잠시 후 다시 열어 주세요.")

    return PsychDetailResponse(
        story_id=str(doc["_id"]),
        title=doc.get("title") or "제목 없는 이야기",
        genre=doc.get("genre") or "",
        completed_at=doc.get("completed_at"),
        traits_info=_trait_infos(),
        traits=analysis["traits"],
        insights=[ChoiceInsight(**i) for i in analysis.get("insights") or []],
        summary=analysis.get("summary") or "",
        questions=analysis.get("questions") or [],
        notice=NOTICE,
    )
