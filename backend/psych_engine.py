"""심리분석 엔진: 완료된 분기형 동화 하나에서 아이가 고른 선택지들을 보고 성향을 읽어 줍니다.

story_engine.py와 같은 구조 (build_psych_engine)
    1. RemotePsychEngine - .env의 STORY_SERVER_URL(팀원 Colab 서버)이 있을 때만 /story/psych. 아직 연결 전이라 항상 실패 → 다음으로
    2. GeminiPsychEngine - 동화 하나당 Gemini 1번 (JSON)
앞 엔진이 실패하면 다음으로 (ChainPsychEngine). 모두 실패하면 PsychEngineError → 저장하지 않고 다음에 다시 시도.
(AI 없이 지어낸 점수는 보호자에게 보여 주기 곤란해서 예비 엔진은 두지 않습니다.)

결과 (PsychResult)
    traits: {courage, empathy, curiosity, caution, creativity} 각 0~100
    insights: 선택마다 짧은 해석 한 줄 (choices와 같은 순서·개수)
    summary: 전체 요약 2~3문장, questions: 보호자가 아이와 나눌 대화 질문 2개
"""
import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from story_text import clean_story_text

# 순서 = 화면 차트 순서 (lib/pages/mind_page.dart의 kTraits와 같게)
TRAITS: list[tuple[str, str]] = [
    ("courage", "용기·도전"),
    ("empathy", "배려·공감"),
    ("curiosity", "호기심·탐구"),
    ("caution", "신중함"),
    ("creativity", "창의성"),
]
TRAIT_KEYS = [k for k, _ in TRAITS]
# Gemini가 한글 이름으로 답해도 받아 줌
_TRAIT_ALIASES = {
    **{k: k for k in TRAIT_KEYS},
    **{label: k for k, label in TRAITS},
    "용기": "courage", "도전": "courage", "배려": "empathy", "공감": "empathy",
    "호기심": "curiosity", "탐구": "curiosity", "신중": "caution",
}

INSIGHT_MAX_LEN = 80
SUMMARY_MAX_LEN = 300
QUESTION_MAX_LEN = 80
QUESTION_COUNT = 2
SCENE_SNIPPET_LEN = 220

DEFAULT_QUESTIONS = [
    "이야기에서 어떤 선택이 제일 재미있었어?",
    "다음에 주인공이 된다면 무엇을 해 보고 싶어?",
]


@dataclass
class ChoiceStep:
    scene: int              # 선택지를 고른 장면 번호
    scene_text: str         # 그 장면 본문 (문맥)
    options: list[str]      # 보여 준 선택지
    choice: str             # 고른 선택지


@dataclass
class PsychInput:
    story_id: str
    title: str
    topic: str
    genre: str
    age: str
    steps: list[ChoiceStep]


@dataclass
class PsychResult:
    traits: dict[str, int]
    insights: list[str]
    summary: str
    questions: list[str]
    engine: str = ""


class PsychEngineError(RuntimeError):
    """엔진이 분석하지 못함 → 다음 엔진으로"""


# ----------------------------------------
# 응답 정리
# ----------------------------------------
def _parse_json(text: str) -> dict:
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PsychEngineError(f"JSON이 아님: {e}") from e
    if not isinstance(data, dict):
        raise PsychEngineError(f"JSON 객체가 아님: {type(data).__name__}")
    return data


def _short(raw, limit: int) -> str:
    text = clean_story_text(raw if isinstance(raw, str) else "").replace("\n", " ").strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def clean_traits(raw) -> dict[str, int]:
    """5가지 성향 점수를 0~100 정수로. 3개 이상 없으면 믿을 수 없는 응답으로 보고 실패."""
    if not isinstance(raw, dict):
        raise PsychEngineError("traits가 객체가 아님")
    traits: dict[str, int] = {}
    for key, value in raw.items():
        name = _TRAIT_ALIASES.get(str(key).strip())
        if not name or name in traits:
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if 0 < score <= 1 and not float(score).is_integer():  # 0.7 같은 비율로 답하면 100점 기준으로
            score *= 100
        traits[name] = int(round(min(100.0, max(0.0, score))))
    if len(traits) < 3:
        raise PsychEngineError(f"성향 점수가 모자람: {list(traits)}")
    for key in TRAIT_KEYS:
        traits.setdefault(key, 50)
    return {key: traits[key] for key in TRAIT_KEYS}


def fallback_insight(choice: str) -> str:
    return f"\"{choice}\" 하고 골라서 자기만의 방법으로 이야기를 이어 갔어요."


def clean_insights(raw, steps: list[ChoiceStep]) -> list[str]:
    """선택 개수와 똑같이. 빠진 해석은 기본 문장으로 채움."""
    items = raw if isinstance(raw, list) else []
    result = []
    for i, step in enumerate(steps):
        item = items[i] if i < len(items) else None
        if isinstance(item, dict):
            item = item.get("insight") or item.get("text")
        text = _short(item, INSIGHT_MAX_LEN)
        result.append(text or fallback_insight(step.choice))
    return result


def clean_questions(raw) -> list[str]:
    result = []
    for item in raw if isinstance(raw, list) else []:
        text = _short(item, QUESTION_MAX_LEN)
        if text and text not in result:
            result.append(text)
        if len(result) == QUESTION_COUNT:
            return result
    for q in DEFAULT_QUESTIONS:
        if len(result) == QUESTION_COUNT:
            break
        if q not in result:
            result.append(q)
    return result


def clean_summary(raw) -> str:
    text = _short(raw, SUMMARY_MAX_LEN)
    if not text:
        raise PsychEngineError("요약이 비어 있음")
    return text


# ----------------------------------------
# 엔진 공통 모양
# ----------------------------------------
class PsychEngine:
    name = "base"

    async def analyze(self, data: PsychInput) -> PsychResult:
        raise NotImplementedError


# ----------------------------------------
# Gemini
# ----------------------------------------
def _steps_block(steps: list[ChoiceStep]) -> str:
    lines = []
    for i, step in enumerate(steps, 1):
        snippet = step.scene_text.replace("\n", " ").strip()
        if len(snippet) > SCENE_SNIPPET_LEN:
            snippet = snippet[:SCENE_SNIPPET_LEN].rstrip() + "…"
        options = " / ".join(step.options) if step.options else "(기록 없음)"
        lines.append(
            f"[선택 {i}] (장면 {step.scene})\n"
            f"장면 내용: {snippet}\n"
            f"보여 준 선택지: {options}\n"
            f"아이가 고른 것: {step.choice}"
        )
    return "\n\n".join(lines)


def psych_prompt(data: PsychInput) -> str:
    trait_lines = "\n".join(f'- "{k}": {label}' for k, label in TRAITS)
    trait_json = ", ".join(f'"{k}": 0' for k in TRAIT_KEYS)
    insight_json = ", ".join(f'"선택 {i} 해석"' for i in range(1, len(data.steps) + 1))
    return f"""너는 어린이 놀이를 따뜻하게 관찰하는 선생님이야.
{data.age} 아이가 선택지를 골라 가며 만든 동화에서, 아이가 고른 선택들을 보고 놀이 속 성향을 읽어 줘.
이건 진단이 아니라 보호자가 아이와 이야기 나누도록 돕는 참고용 이야기야.

[동화]
제목: {data.title}
주제(주인공): {data.topic}
장르: {data.genre}

[아이의 선택 기록]
{_steps_block(data.steps)}

[성향 5가지] 각각 0~100 정수 점수 (이 동화의 선택에서 드러난 정도. 드러나지 않았으면 낮게, 근거 없이 높게 주지 마)
{trait_lines}

[꼭 지킬 규칙]
- 아이가 "다른 선택지 대신 그것을 고른 것"을 근거로 판단해.
- "choice_insights": 선택마다 한 줄씩, 선택 개수와 똑같이 {len(data.steps)}개. 40자 안팎, 어떤 마음이 보이는지 다정하게. (예: "길 잃은 친구를 먼저 챙기는 따뜻한 마음이 보여요.")
- "summary": 2~3문장. 아이의 좋은 점을 중심으로, 보호자가 읽기 편한 따뜻한 말투(~해요, ~보여요).
- "questions": 보호자가 아이에게 물어볼 쉬운 대화 질문 2개. 아이에게 직접 말하는 반말로. (예: "친구를 도와줬을 때 기분이 어땠어?")
- 진단·병명·문제 행동·부정적인 평가·비교는 절대 쓰지 마. "~한 아이다"처럼 단정하지 말고 "이 이야기에서는 ~하는 모습이 보여요"처럼 써.
- 마크다운 기호(**, #, - 등)는 쓰지 마.

반드시 아래 JSON 형식으로만 답해:
{{"traits": {{{trait_json}}}, "choice_insights": [{insight_json}], "summary": "요약", "questions": ["질문1", "질문2"]}}
"""


class GeminiPsychEngine(PsychEngine):
    """동화 하나당 generate_content_async 1번. model은 gemini_client.FallbackModel (테스트에서는 가짜 모델)."""

    name = "gemini"

    def __init__(self, model):
        self.model = model

    async def analyze(self, data: PsychInput) -> PsychResult:
        response = await self.model.generate_content_async(
            psych_prompt(data), generation_config={"response_mime_type": "application/json"}
        )
        raw = _parse_json(response.text)
        return PsychResult(
            traits=clean_traits(raw.get("traits")),
            insights=clean_insights(raw.get("choice_insights"), data.steps),
            summary=clean_summary(raw.get("summary")),
            questions=clean_questions(raw.get("questions")),
        )


# ----------------------------------------
# 팀원 Colab 서버 (아직 연결 전)
# ----------------------------------------
class RemotePsychEngine(PsychEngine):
    """STORY_SERVER_URL의 팀원 서버 POST /story/psych를 부를 자리.

    팀원 노트북(team_code/colab/fairytale_emotion_server_colab.ipynb) 요청 형식:
        {"story_id", "story_title", "choices_made": [고른 선택지...], "choice_emotions": [], "completed": true}
    응답: {"type", "description", "traits": {팀원 성향 이름: 0~100}, "dominant_emotions", "choice_insights": [...]}
    연결할 때 analyze만 채우면 됩니다: httpx.AsyncClient로 POST → traits 이름을 TRAIT_KEYS로 맞추고
    (clean_traits/_TRAIT_ALIASES), description → summary, 질문이 없으면 clean_questions([])로 기본 질문.
    실패하면 예외를 던지면 ChainPsychEngine이 Gemini로 넘어갑니다.
    """

    name = "colab"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def analyze(self, data: PsychInput) -> PsychResult:
        raise PsychEngineError("Colab 심리분석 서버 연결은 아직 준비 중이에요.")


# ----------------------------------------
# 순서대로 시도
# ----------------------------------------
class ChainPsychEngine(PsychEngine):
    name = "chain"

    def __init__(self, engines: list[PsychEngine]):
        self.engines = engines

    async def analyze(self, data: PsychInput) -> PsychResult:
        last_error: Optional[Exception] = None
        for engine in self.engines:
            try:
                result = await engine.analyze(data)
                result.engine = engine.name
                return result
            except Exception as e:
                print(f"[심리분석 엔진] {engine.name} 실패 → 다음 엔진 ({type(e).__name__}: {e})", flush=True)
                last_error = e
        raise PsychEngineError("모든 심리분석 엔진이 실패했어요.") from last_error


def build_psych_engine(model) -> ChainPsychEngine:
    engines: list[PsychEngine] = []
    server_url = (os.getenv("STORY_SERVER_URL") or "").strip()
    if server_url:
        engines.append(RemotePsychEngine(server_url))
    engines.append(GeminiPsychEngine(model))
    return ChainPsychEngine(engines)
