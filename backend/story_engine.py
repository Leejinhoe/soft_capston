"""분기형 동화 엔진: 장면 하나(본문 + 선택지 3개) / 결말(본문 + 제목)을 만듭니다.

엔진 순서 (build_story_engine)
    1. RemoteStoryEngine  - .env의 STORY_SERVER_URL(팀원 Colab 서버)이 있을 때만. /story/start, /story/continue
                            (꺼져 있거나 120초 넘게 걸리거나 실패하면 → 다음으로)
    2. GeminiStoryEngine  - 장면 하나당 Gemini 1번 (JSON으로 본문 + 선택지, 결말이면 본문 + 제목)
    3. TemplateStoryEngine - AI 없이 쓰는 예비 장면 (Gemini 한도 초과여도 앱이 멈추지 않게)
앞 엔진이 실패하면(예외) 다음 엔진으로 넘어갑니다. (ChainStoryEngine)

장면 규칙
    - 첫 장면 이후 아무 때나 마무리 가능, 장면이 MAX_SCENES개가 되면 마지막 장면은 자동으로 결말
    - WRAP_UP_FROM번째 장면부터는 마무리 쪽으로 자연스럽게 이끌기
"""
import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import colab_client
from story_text import clean_story_text

MAX_SCENES = 8
WRAP_UP_FROM = 6
CHOICE_COUNT = 3
CHOICE_MAX_LEN = 40
TITLE_MAX_LEN = 30


@dataclass
class StorySetup:
    topic: str
    genre: str
    age: str
    remote_story_id: str = ""   # Colab이 준 story_id (stories.colab_story_id)


@dataclass
class SceneResult:
    text: str
    choices: list[str] = field(default_factory=list)  # 결말이면 []
    title: str = ""                                     # 결말일 때만
    engine: str = ""                                    # 만든 엔진 이름 (colab / gemini / template, 화면에 작게 표시)
    choice_emotion: Optional[dict] = None               # Colab: 방금 고른 선택지의 감정 분석 (심리분석용)
    remote_story_id: str = ""                           # Colab: 첫 장면에서 받은 story_id


class StoryEngineError(RuntimeError):
    """엔진이 장면을 만들지 못함 → 다음 엔진으로"""


# ----------------------------------------
# 응답 정리
# ----------------------------------------
_CHOICE_PREFIX = re.compile(r"^\s*(?:[0-9]+[.)]|[①②③④⑤]|[-*•]|선택\s*[0-9]*\s*[:：.])\s*")
_TITLE_STRIP = "\"'“”‘’「」『』<>《》*#` "


def _parse_json(text: str) -> dict:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise StoryEngineError(f"JSON 객체가 아님: {type(data).__name__}")
    return data


def clean_choices(raw, fallback: list[str]) -> list[str]:
    """선택지 3개로 맞추기: 번호·기호 제거, 너무 긴 것 자르기, 중복 제거, 모자라면 예비 선택지로 채움."""
    result: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, str):
            continue
        choice = clean_story_text(_CHOICE_PREFIX.sub("", item)).replace("\n", " ").strip()
        if len(choice) > CHOICE_MAX_LEN:
            choice = choice[:CHOICE_MAX_LEN].rstrip() + "…"
        if choice and choice not in result:
            result.append(choice)
        if len(result) == CHOICE_COUNT:
            return result
    for choice in fallback:
        if len(result) == CHOICE_COUNT:
            break
        if choice not in result:
            result.append(choice)
    return result


def clean_title(raw, topic: str) -> str:
    title = clean_story_text(raw if isinstance(raw, str) else "").replace("\n", " ")
    title = re.sub(r"^\s*(제목|title)\s*[:：]\s*", "", title, flags=re.IGNORECASE).strip(_TITLE_STRIP)
    if len(title) > TITLE_MAX_LEN:
        title = title[:TITLE_MAX_LEN].rstrip()
    return title or default_title(topic)


def default_title(topic: str) -> str:
    topic = (topic or "").strip()
    return f"{topic} 이야기" if topic else "신비한 동화 이야기"


def _clean_scene_text(raw) -> str:
    text = clean_story_text(raw if isinstance(raw, str) else "")
    if not text:
        raise StoryEngineError("장면 본문이 비어 있음")
    return text


GENERIC_CHOICES = [
    "친구에게 도와 달라고 말해 본다",
    "반짝이는 쪽으로 조심조심 걸어가 본다",
    "잠깐 멈춰서 주위를 살펴본다",
]


# ----------------------------------------
# 엔진 공통 모양
# ----------------------------------------
class StoryEngine:
    name = "base"

    async def opening(self, setup: StorySetup) -> SceneResult:
        raise NotImplementedError

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str) -> SceneResult:
        """scenes: 지금까지의 장면 본문들, choice: 방금 고른 선택지. 새 장면은 len(scenes)+1번째."""
        raise NotImplementedError

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None) -> SceneResult:
        """결말 장면 + 제목. choice가 있으면 그 선택을 반영한 결말 (장면 수가 꽉 찼을 때)."""
        raise NotImplementedError


# ----------------------------------------
# Gemini
# ----------------------------------------
_COMMON_RULES = """
[꼭 지킬 규칙]
- {age} 아이가 읽는 동화야. 짧고 쉬운 문장, 다정하고 따뜻한 말투(~했어요, ~답니다)로 써.
- 아이에게 안전한 내용만 써. 무섭거나 잔인한 장면, 다치거나 죽는 이야기, 나쁜 말, 어른용 내용은 절대 쓰지 마.
  어려움이 생겨도 가볍게, 친절·용기·우정·도움으로 풀어 가게 해.
- 마크다운을 절대 쓰지 마. (**, *, #, -, ` 같은 기호 금지) 본문에 제목을 쓰지 마.
- 문단은 2~3개, 문단 사이는 빈 줄 하나(\\n\\n)로만 나눠.
"""

_CHOICE_RULES = """
- "choices"에는 주인공이 다음에 할 행동 3개를 넣어. 서로 다른 방향으로, 아이가 고르기 쉬운 짧은 문장(25자 이내)으로.
  (예: "반짝이는 동굴에 들어가 본다") 번호나 기호는 붙이지 마. 모두 안전하고 다정한 행동이어야 해.
"""


def _setup_block(setup: StorySetup) -> str:
    return f"주제(주인공): {setup.topic}\n장르: {setup.genre}\n연령대: {setup.age}"


def _story_so_far(scenes: list[str]) -> str:
    return "\n\n".join(f"[장면 {i}]\n{text}" for i, text in enumerate(scenes, 1))


def opening_prompt(setup: StorySetup) -> str:
    return f"""너는 아이들을 위한 다정한 동화 작가야. 아이가 선택지를 고르며 이어 가는 동화의 첫 장면을 써 줘.

{_setup_block(setup)}

첫 장면에서는 주인공과 배경을 소개하고, 작은 사건이나 궁금한 일이 생기게 해.
{_COMMON_RULES.format(age=setup.age)}{_CHOICE_RULES}
반드시 아래 JSON 형식으로만 답해:
{{"scene": "첫 장면 본문", "choices": ["선택지1", "선택지2", "선택지3"]}}
"""


def next_scene_prompt(setup: StorySetup, scenes: list[str], choice: str) -> str:
    number = len(scenes) + 1
    if number >= WRAP_UP_FROM:
        pacing = (
            f"이번은 {number}번째 장면이야. 이야기가 곧 끝나니까 문제를 하나씩 풀고 마무리 쪽으로 자연스럽게 이끌어 줘. "
            "새로운 큰 사건은 만들지 말고, 선택지도 이야기를 따뜻하게 정리하는 행동으로 골라."
        )
    else:
        pacing = f"이번은 {number}번째 장면이야. 이야기를 재미있게 한 걸음 더 펼쳐 줘."
    return f"""너는 아이들을 위한 다정한 동화 작가야. 아이가 선택지를 고르며 이어 가는 동화의 다음 장면을 써 줘.

{_setup_block(setup)}

[지금까지의 이야기]
{_story_so_far(scenes)}

[아이가 고른 선택]
{choice}

아이가 고른 선택을 주인공이 실제로 하는 것으로 장면을 시작하고, 앞 이야기와 자연스럽게 이어지게 써.
{pacing}
{_COMMON_RULES.format(age=setup.age)}{_CHOICE_RULES}
반드시 아래 JSON 형식으로만 답해:
{{"scene": "다음 장면 본문", "choices": ["선택지1", "선택지2", "선택지3"]}}
"""


def ending_prompt(setup: StorySetup, scenes: list[str], choice: Optional[str]) -> str:
    chosen = f"\n[아이가 마지막으로 고른 선택]\n{choice}\n아이가 고른 선택을 주인공이 하는 것으로 결말을 시작해.\n" if choice else ""
    return f"""너는 아이들을 위한 다정한 동화 작가야. 아이가 선택지를 고르며 이어 온 동화의 결말 장면을 써 줘.

{_setup_block(setup)}

[지금까지의 이야기]
{_story_so_far(scenes)}
{chosen}
지금까지의 흐름에 맞게 남은 일을 다정하게 풀고, 행복하고 따뜻하게 끝내 줘. 마지막 문장은 포근한 마무리 문장으로.
선택지는 만들지 마.
그리고 이야기 전체에 어울리는 동화 제목을 지어 줘. (15자 이내, 따옴표·기호 없이)
{_COMMON_RULES.format(age=setup.age)}
반드시 아래 JSON 형식으로만 답해:
{{"scene": "결말 장면 본문", "title": "동화 제목"}}
"""


class GeminiStoryEngine(StoryEngine):
    """장면 하나당 generate_content_async 1번. model은 gemini_client.FallbackModel (테스트에서는 가짜 모델)."""

    name = "gemini"

    def __init__(self, model):
        self.model = model

    async def _ask(self, prompt: str) -> dict:
        response = await self.model.generate_content_async(
            prompt, generation_config={"response_mime_type": "application/json"}
        )
        return _parse_json(response.text)

    async def opening(self, setup: StorySetup) -> SceneResult:
        data = await self._ask(opening_prompt(setup))
        return SceneResult(_clean_scene_text(data.get("scene")), clean_choices(data.get("choices"), GENERIC_CHOICES))

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str) -> SceneResult:
        data = await self._ask(next_scene_prompt(setup, scenes, choice))
        return SceneResult(_clean_scene_text(data.get("scene")), clean_choices(data.get("choices"), GENERIC_CHOICES))

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None) -> SceneResult:
        data = await self._ask(ending_prompt(setup, scenes, choice))
        return SceneResult(_clean_scene_text(data.get("scene")), [], clean_title(data.get("title"), setup.topic))


# ----------------------------------------
# 팀원 Colab 서버
# ----------------------------------------
# Colab 서버가 선택지 JSON을 못 읽었을 때 돌려주는 기본 선택지 (서버 normalize_choices의 fallback)
COLAB_FALLBACK_CHOICES = ["계속 나아간다", "도움을 요청한다", "잠깐 생각해본다"]
# Colab에는 마무리 기능이 없어서, 결말이 필요할 때 이 선택지를 보내 결말 장면을 받습니다. (돌아온 선택지는 버림)
ENDING_CHOICE = "모두 함께 행복하게 이야기를 마무리한다"
TITLE_TIMEOUT_SEC = 20
_ZERO_WIDTH = re.compile("[\u200b-\u200f\u2060\ufeff]")


def clean_colab_text(raw) -> str:
    """Colab 본문 정리: 기존 후처리(마크다운·제목 줄) + 보이지 않는 문자, "!???" 같은 겹친 문장부호"""
    text = _ZERO_WIDTH.sub("", raw if isinstance(raw, str) else "")
    text = re.sub(r"([?!])[?!]+", r"\1", text)
    text = re.sub(r"\.([?!])", r"\1", text)
    text = re.sub(r"~{2,}", "~", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return _clean_scene_text(text)


def title_prompt(setup: StorySetup, full_text: str) -> str:
    return f"""아이들을 위한 동화에 어울리는 제목을 지어 줘. (15자 이내, 따옴표·기호 없이)

{_setup_block(setup)}

[동화]
{full_text[-1500:]}

반드시 아래 JSON 형식으로만 답해:
{{"title": "동화 제목"}}
"""


class RemoteStoryEngine(StoryEngine):
    """STORY_SERVER_URL의 팀원 Colab 서버 (EXAONE). 실패하면 예외 → ChainStoryEngine이 Gemini로 넘어감.

    - 첫 장면: POST /story/start {genre, age, prompt} → {story_id, story_text, choices}
    - 다음 장면: POST /story/continue {story_id, story_so_far, choice, genre, age}
        → {new_text, choices, selected_choice_emotion}
    - 결말: /story/continue에 ENDING_CHOICE(마지막 선택이 있으면 함께)를 보내고 선택지는 버림.
      제목은 Gemini가 되면 Gemini로, 안 되면 주제로 (default_title)
    """

    name = "colab"

    def __init__(self, base_url: str = "", title_model=None):
        self.base_url = base_url.rstrip("/")
        self.title_model = title_model

    async def _continue(self, setup: StorySetup, scenes: list[str], choice: str) -> dict:
        return await colab_client.post_json(
            "/story/continue",
            {
                "story_id": setup.remote_story_id or "story_local",
                "story_so_far": "\n\n".join(scenes),
                "choice": choice,
                "genre": setup.genre,
                "age": setup.age,
            },
            colab_client.STORY_TIMEOUT_SEC,
        )

    async def _title(self, setup: StorySetup, full_text: str) -> str:
        if self.title_model is None:
            return default_title(setup.topic)
        try:
            response = await asyncio.wait_for(
                self.title_model.generate_content_async(
                    title_prompt(setup, full_text), generation_config={"response_mime_type": "application/json"}
                ),
                TITLE_TIMEOUT_SEC,
            )
            return clean_title(_parse_json(response.text).get("title"), setup.topic)
        except Exception as e:
            print(f"[동화 엔진] colab 결말 제목: Gemini 실패 → 주제로 제목 ({type(e).__name__}: {str(e)[:120]})", flush=True)
            return default_title(setup.topic)

    async def opening(self, setup: StorySetup) -> SceneResult:
        data = await colab_client.post_json(
            "/story/start",
            {"genre": setup.genre, "age": setup.age, "prompt": setup.topic},
            colab_client.STORY_TIMEOUT_SEC,
        )
        return SceneResult(
            clean_colab_text(data.get("story_text")),
            clean_choices(data.get("choices"), GENERIC_CHOICES),
            remote_story_id=str(data.get("story_id") or ""),
        )

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str) -> SceneResult:
        data = await self._continue(setup, scenes, choice)
        return SceneResult(
            clean_colab_text(data.get("new_text")),
            clean_choices(data.get("choices"), GENERIC_CHOICES),
            choice_emotion=colab_client.compact_emotion(data.get("selected_choice_emotion")),
        )

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None) -> SceneResult:
        ending_choice = f"{choice} 그리고 {ENDING_CHOICE}" if choice else ENDING_CHOICE
        data = await self._continue(setup, scenes, ending_choice)
        text = clean_colab_text(data.get("new_text"))
        title = await self._title(setup, "\n\n".join(scenes + [text]))
        return SceneResult(
            text,
            [],
            title,
            choice_emotion=colab_client.compact_emotion(data.get("selected_choice_emotion")) if choice else None,
        )


# ----------------------------------------
# AI 없이 쓰는 예비 장면
# ----------------------------------------
def _josa(word: str, with_jong: str, without_jong: str) -> str:
    last = (word or " ")[-1]
    if "가" <= last <= "힣":
        return with_jong if (ord(last) - 0xAC00) % 28 else without_jong
    return f"{with_jong}({without_jong})"


class TemplateStoryEngine(StoryEngine):
    name = "template"

    async def opening(self, setup: StorySetup) -> SceneResult:
        topic = setup.topic.strip() or "작은 친구"
        text = (
            f"옛날 옛날에 {topic}{_josa(topic, '이', '가')} 살고 있었어요.\n\n"
            f"어느 맑은 아침, {topic}{_josa(topic, '은', '는')} {setup.genre} 이야기처럼 신기한 일이 생길 것 같은 "
            "예감이 들었어요. 저 멀리서 반짝이는 빛이 손짓하고 있었답니다."
        )
        return SceneResult(text, list(GENERIC_CHOICES))

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str) -> SceneResult:
        text = (
            f"주인공은 \"{choice}\" 하기로 마음먹었어요.\n\n"
            "용기를 내어 한 걸음 내딛자 새로운 친구가 반갑게 인사해 주었어요. 둘은 함께 웃으며 다음 길을 찾아보기로 했답니다."
        )
        return SceneResult(text, list(GENERIC_CHOICES))

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None) -> SceneResult:
        first = f"주인공은 \"{choice}\" 하기로 했어요.\n\n" if choice else ""
        text = (
            f"{first}해가 뉘엿뉘엿 질 무렵, 모두 함께 집으로 돌아왔어요. 오늘 있었던 일을 떠올리니 마음이 포근해졌어요.\n\n"
            "그날 밤, 주인공은 새 친구들을 생각하며 행복한 꿈나라로 떠났답니다. 끝."
        )
        return SceneResult(text, [], default_title(setup.topic))


# ----------------------------------------
# 순서대로 시도
# ----------------------------------------
class ChainStoryEngine(StoryEngine):
    name = "chain"

    def __init__(self, engines: list[StoryEngine]):
        self.engines = engines

    async def _run(self, method: str, *args) -> SceneResult:
        last_error: Optional[Exception] = None
        for engine in self.engines:
            try:
                result = await getattr(engine, method)(*args)
                result.engine = engine.name
                return result
            except Exception as e:
                print(f"[동화 엔진] {engine.name}.{method} 실패 → 다음 엔진 ({type(e).__name__}: {e})", flush=True)
                last_error = e
        raise StoryEngineError("모든 동화 엔진이 실패했어요.") from last_error

    async def opening(self, setup: StorySetup) -> SceneResult:
        return await self._run("opening", setup)

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str) -> SceneResult:
        return await self._run("next_scene", setup, scenes, choice)

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None) -> SceneResult:
        return await self._run("ending", setup, scenes, choice)


def build_story_engine(model) -> ChainStoryEngine:
    engines: list[StoryEngine] = []
    if colab_client.colab_enabled():
        engines.append(RemoteStoryEngine(colab_client.colab_url(), title_model=model))
    engines.append(GeminiStoryEngine(model))
    engines.append(TemplateStoryEngine())
    return ChainStoryEngine(engines)
