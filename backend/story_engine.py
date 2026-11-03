"""분기형 동화 엔진: 장면 하나(본문 + 선택지 3개) / 결말(본문 + 제목)을 만듭니다.

엔진 순서 (build_story_engine)
    1. RemoteStoryEngine  - 우리 팀이 학습시킨 Colab 모델 (.env의 STORY_SERVER_URL). 동화 생성의 주인공
                            스트리밍으로 글자가 나오는 대로 화면에 전달, 선택지가 기본값이면 다시 만들기,
                            조사 앞 띄어쓰기 등 후처리
    2. GeminiStoryEngine  - Colab이 꺼지거나 실패할 때만. 장면 하나당 Gemini 1번 (JSON으로 본문 + 선택지, 결말이면 본문 + 제목)
    3. TemplateStoryEngine - AI 없이 쓰는 예비 장면 (Gemini 한도 초과여도 앱이 멈추지 않게)
앞 엔진이 실패하면(예외) 다음 엔진으로 넘어갑니다. (ChainStoryEngine)

장면 규칙
    - 첫 장면 이후 아무 때나 마무리 가능, 장면이 MAX_SCENES개가 되면 마지막 장면은 자동으로 결말
    - WRAP_UP_FROM번째 장면부터는 마무리 쪽으로 자연스럽게 이끌기
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

import colab_client
from story_choices import COLAB_FALLBACK_CHOICES, acceptable_choices, finalize_choices
from story_text import clean_story_text, fix_particle_spacing

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
    previous_choices: list[str] = field(default_factory=list)  # 이 동화에서 이미 보여 준 선택지 (겹치지 않게)


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


def _avoid_block(setup: StorySetup) -> str:
    """이전 장면 선택지와 겹치지 않게 (Gemini 프롬프트용)"""
    if not setup.previous_choices:
        return ""
    listed = "\n".join(f"- {c}" for c in setup.previous_choices[-9:])
    return f"\n- 선택지는 이번 장면 내용에 맞게 새로 만들어. 아래 이전 선택지와 같거나 비슷하면 안 돼.\n{listed}\n"


def _story_so_far(scenes: list[str]) -> str:
    return "\n\n".join(f"[장면 {i}]\n{text}" for i, text in enumerate(scenes, 1))


def opening_prompt(setup: StorySetup) -> str:
    return f"""너는 아이들을 위한 다정한 동화 작가야. 아이가 선택지를 고르며 이어 가는 동화의 첫 장면을 써 줘.

{_setup_block(setup)}

첫 장면에서는 주인공과 배경을 소개하고, 작은 사건이나 궁금한 일이 생기게 해.
{_COMMON_RULES.format(age=setup.age)}{_CHOICE_RULES}{_avoid_block(setup)}
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
{_COMMON_RULES.format(age=setup.age)}{_CHOICE_RULES}{_avoid_block(setup)}
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
        return SceneResult(_clean_scene_text(data.get("scene")), clean_choices(data.get("choices"), []))

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str) -> SceneResult:
        data = await self._ask(next_scene_prompt(setup, scenes, choice))
        return SceneResult(_clean_scene_text(data.get("scene")), clean_choices(data.get("choices"), []))

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None) -> SceneResult:
        data = await self._ask(ending_prompt(setup, scenes, choice))
        return SceneResult(_clean_scene_text(data.get("scene")), [], clean_title(data.get("title"), setup.topic))


# ----------------------------------------
# 팀원 Colab 서버 (동화 생성의 주인공)
# ----------------------------------------
# Colab에는 마무리 기능이 없어서, 결말이 필요할 때 이 선택지를 보내 결말 장면을 받습니다. (돌아온 선택지는 버림)
ENDING_CHOICE = "모두 함께 행복하게 이야기를 마무리한다"
TITLE_TIMEOUT_SEC = 20
CHOICES_GEMINI_TIMEOUT_SEC = 20
_ZERO_WIDTH = re.compile("[​-‏⁠﻿]")

# 화면으로 보내는 스트리밍 이벤트 (branching.py가 NDJSON으로 그대로 전달)
#   {"type": "engine", "engine": "colab"}   이 엔진이 쓰기 시작함
#   {"type": "text", "text": "지금까지 정리한 본문"}  Colab이 글자를 내보낼 때마다
#   {"type": "status", "message": "..."}     본문 다음 단계 (선택지·감정 준비 등)
#   {"type": "reset"}                        쓰던 글이 실패함 → 화면의 글을 지우고 다음 엔진/방법으로
Emit = Optional[Callable[[dict], None]]


def _emit(emit: Emit, event: dict) -> None:
    if emit is not None:
        try:
            emit(event)
        except Exception:
            pass


_BR_TAG = re.compile(r"<\s*/?\s*br\s*/?\s*>", re.IGNORECASE)
_HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][a-zA-Z0-9]*\b[^<>]*>")
_EMPTY_TAG = re.compile(r"<\s*/?\s*>")


def _strip_html(text: str) -> str:
    """Colab이 가끔 섞는 HTML 찌꺼기: </br> → 줄바꿈, <p> <strong> 등 → 지움, 남은 > 와 [ ] 도 지움"""
    text = _BR_TAG.sub("\n", text)
    text = _HTML_TAG.sub("", text)
    text = _EMPTY_TAG.sub("", text)
    text = re.sub(r"(?<=[가-힣.!?~”’\"'])>+", "", text)
    return text.replace("[", "").replace("]", "")


def _light_clean(raw: str) -> str:
    """Colab 글 공통 정리: HTML 찌꺼기, 보이지 않는 문자, "!???" 같은 겹친 문장부호, 조사 앞 띄어쓰기"""
    text = _strip_html(_ZERO_WIDTH.sub("", raw or ""))
    text = re.sub(r"([?!])[?!]+", r"\1", text)
    text = re.sub(r"\.([?!])", r"\1", text)
    text = re.sub(r"~{2,}", "~", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return fix_particle_spacing(text)


def clean_colab_text(raw) -> str:
    """Colab 본문 최종 정리: _light_clean + 기존 후처리(마크다운·제목 줄, Gemini 결과와 똑같이)"""
    return _clean_scene_text(_light_clean(raw if isinstance(raw, str) else ""))


def stream_preview_text(raw: str) -> str:
    """스트리밍 중 화면에 보일 글 (제목 줄 빼기는 글이 다 나와야 알 수 있어서 마크다운 기호만 정리)"""
    text = _light_clean(re.sub(r"<[^<>]*$", "", raw or "")).lstrip()  # 아직 덜 온 태그("</ str")는 숨김
    text = re.sub(r"(\*\*|__)", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text




def title_prompt(setup: StorySetup, full_text: str) -> str:
    return f"""아이들을 위한 동화에 어울리는 제목을 지어 줘. (15자 이내, 따옴표·기호 없이)

{_setup_block(setup)}

[동화]
{full_text[-1500:]}

반드시 아래 JSON 형식으로만 답해:
{{"title": "동화 제목"}}
"""


def choices_prompt(setup: StorySetup, story_text: str) -> str:
    return f"""너는 아이들을 위한 다정한 동화 작가야. 아래 동화의 다음에 주인공이 할 행동 선택지 3개만 만들어 줘.

{_setup_block(setup)}

[지금까지의 이야기]
{story_text[-1500:]}
{_CHOICE_RULES}{_avoid_block(setup)}
반드시 아래 JSON 형식으로만 답해:
{{"choices": ["선택지1", "선택지2", "선택지3"]}}
"""


class RemoteStoryEngine(StoryEngine):
    """STORY_SERVER_URL의 팀원 Colab 서버 (우리 팀이 학습시킨 EXAONE). 실패하면 예외 → ChainStoryEngine이 Gemini로.

    - 첫 장면: /story/start/stream (안 되면 /story/start) {genre, age, prompt} → {story_id, story_text, choices}
    - 다음 장면: /story/continue/stream (안 되면 /story/continue) {story_id, story_so_far, choice, genre, age}
        → {new_text, choices, selected_choice_emotion}
      스트리밍은 화면이 글을 받을 때(emit이 있을 때)만. 스트리밍이 실패하면 같은 Colab 일반 호출로 한 번 더.
    - 선택지가 Colab 기본값이면: Colab /story/choices로 다시 → 그래도 기본값이면 그때만 Gemini로 선택지만
    - 결말: ENDING_CHOICE(마지막 선택이 있으면 함께)를 보내고 선택지는 버림. 제목은 Gemini가 되면 Gemini로, 안 되면 주제로
    """

    name = "colab"
    streams = True  # ChainStoryEngine이 emit을 넘겨 줌

    def __init__(self, base_url: str = "", title_model=None):
        self.base_url = base_url.rstrip("/")
        self.title_model = title_model  # 제목·선택지 보완용 Gemini (없어도 됨)

    async def _scene(self, path: str, body: dict, text_key: str, emit: Emit) -> dict:
        """Colab 장면 하나: 스트리밍 → 안 되면 일반 호출. 받은 그대로(dict) 돌려줌."""
        if emit is not None:
            chunks: list[str] = []

            def on_event(event: dict) -> None:
                kind = event.get("type")
                if kind == "delta" and isinstance(event.get("text"), str):
                    chunks.append(event["text"])
                    _emit(emit, {"type": "text", "text": stream_preview_text("".join(chunks))})
                elif kind == "status" and event.get("message"):
                    _emit(emit, {"type": "status", "message": "🤖 " + str(event["message"])})

            try:
                return await colab_client.post_ndjson(f"{path}/stream", body, on_event)
            except colab_client.ColabError as e:
                print(f"[동화 엔진] colab 스트리밍 실패 → 일반 호출로 ({e})", flush=True)
                _emit(emit, {"type": "reset"})
                _emit(emit, {"type": "status", "message": "🤖 우리 팀 AI가 다시 쓰고 있어요"})
        data = await colab_client.post_json(path, body, colab_client.STORY_TIMEOUT_SEC)
        if emit is not None and isinstance(data.get(text_key), str):
            _emit(emit, {"type": "text", "text": stream_preview_text(data[text_key])})
        return data

    def _continue_body(self, setup: StorySetup, scenes: list[str], choice: str) -> dict:
        return {
            "story_id": setup.remote_story_id or "story_local",
            "story_so_far": "\n\n".join(scenes),
            "choice": choice,
            "genre": setup.genre,
            "age": setup.age,
        }

    async def _gemini_json(self, prompt: str, timeout: float) -> dict:
        if self.title_model is None:
            raise StoryEngineError("Gemini 모델 없음")
        response = await asyncio.wait_for(
            self.title_model.generate_content_async(prompt, generation_config={"response_mime_type": "application/json"}),
            timeout,
        )
        return _parse_json(response.text)

    async def _title(self, setup: StorySetup, full_text: str) -> str:
        try:
            data = await self._gemini_json(title_prompt(setup, full_text), TITLE_TIMEOUT_SEC)
            return clean_title(data.get("title"), setup.topic)
        except Exception as e:
            print(f"[동화 엔진] colab 결말 제목: Gemini 실패 → 주제로 제목 ({type(e).__name__}: {str(e)[:120]})", flush=True)
            return default_title(setup.topic)

    async def _good_choices(self, setup: StorySetup, story_text: str, raw, emit: Emit) -> list[str]:
        """Colab 선택지 중 쓸 만한 것(기본값·찌꺼기·이전 선택지와 겹침 제외)이 3개가 안 되면:
        Colab /story/choices로 다시 → 그래도 모자라면 Gemini. 그래도 모자란 만큼은 ChainStoryEngine이 템플릿으로 채움"""
        previous = setup.previous_choices
        good = acceptable_choices(raw, previous)
        if len(good) >= CHOICE_COUNT:
            print("[선택지] colab 첫 선택지 그대로", flush=True)
            return good[:CHOICE_COUNT]
        print(f"[선택지] colab 첫 선택지 쓸 만한 것 {len(good)}개 (받은 것: {raw}) → /story/choices로 다시", flush=True)
        _emit(emit, {"type": "status", "message": "🤖 선택지를 다시 골라 보고 있어요"})
        try:
            data = await colab_client.post_json(
                "/story/choices",
                {"story_so_far": story_text, "genre": setup.genre, "age": setup.age},
                colab_client.CHOICES_TIMEOUT_SEC,
            )
            good += acceptable_choices(data.get("choices"), previous + good)
            if len(good) >= CHOICE_COUNT:
                print("[선택지] colab /story/choices로 다시 만듦", flush=True)
                return good[:CHOICE_COUNT]
            print(f"[선택지] /story/choices도 모자람 (받은 것: {data.get('choices')}) → Gemini", flush=True)
        except Exception as e:
            print(f"[선택지] colab /story/choices 실패 → Gemini ({e})", flush=True)
        try:
            data = await self._gemini_json(choices_prompt(setup, story_text), CHOICES_GEMINI_TIMEOUT_SEC)
            good += acceptable_choices(clean_choices(data.get("choices"), []), previous + good)
            if len(good) >= CHOICE_COUNT:
                print("[선택지] Gemini로 만듦", flush=True)
                return good[:CHOICE_COUNT]
        except Exception as e:
            print(f"[선택지] Gemini 실패 ({type(e).__name__}: {str(e)[:120]})", flush=True)
        return good  # 모자란 만큼은 장면 본문 낱말로 템플릿 (ChainStoryEngine)

    async def opening(self, setup: StorySetup, emit: Emit = None) -> SceneResult:
        data = await self._scene(
            "/story/start", {"genre": setup.genre, "age": setup.age, "prompt": setup.topic}, "story_text", emit
        )
        text = clean_colab_text(data.get("story_text"))
        return SceneResult(
            text,
            await self._good_choices(setup, text, data.get("choices"), emit),
            remote_story_id=str(data.get("story_id") or ""),
        )

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str, emit: Emit = None) -> SceneResult:
        data = await self._scene("/story/continue", self._continue_body(setup, scenes, choice), "new_text", emit)
        text = clean_colab_text(data.get("new_text"))
        return SceneResult(
            text,
            await self._good_choices(setup, "\n\n".join(scenes + [text]), data.get("choices"), emit),
            choice_emotion=colab_client.compact_emotion(data.get("selected_choice_emotion")),
        )

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None, emit: Emit = None) -> SceneResult:
        ending_choice = f"{choice} 그리고 {ENDING_CHOICE}" if choice else ENDING_CHOICE
        data = await self._scene("/story/continue", self._continue_body(setup, scenes, ending_choice), "new_text", emit)
        text = clean_colab_text(data.get("new_text"))
        _emit(emit, {"type": "status", "message": "🏷️ 이야기에 어울리는 제목을 짓고 있어요"})
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
        return SceneResult(text, [])

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str) -> SceneResult:
        text = (
            f"주인공은 \"{choice}\" 하기로 마음먹었어요.\n\n"
            "용기를 내어 한 걸음 내딛자 새로운 친구가 반갑게 인사해 주었어요. 둘은 함께 웃으며 다음 길을 찾아보기로 했답니다."
        )
        return SceneResult(text, [])

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
def _finish_choices(result: SceneResult, setup: StorySetup, number: int) -> None:
    """어느 엔진이든: 이번 장면에 맞고 이전 선택지와 안 겹치는 3개. 모자라면 본문의 인물·장소 낱말로 템플릿"""
    choices, filled = finalize_choices(
        result.choices, result.text, setup.topic, setup.previous_choices,
        seed=f"{setup.remote_story_id}|{number}", wrap_up=number >= WRAP_UP_FROM,
    )
    if filled:
        print(f"[선택지] {result.engine} 장면 {number}: {filled}개를 본문 낱말 템플릿으로 채움 → {choices}", flush=True)
    result.choices = choices


class ChainStoryEngine(StoryEngine):
    """Colab → Gemini → 예비 장면. emit이 있으면 엔진을 바꿀 때마다 화면에 알려 줌 (engine / reset 이벤트)."""

    name = "chain"

    def __init__(self, engines: list[StoryEngine]):
        self.engines = engines

    async def _run(self, method: str, *args, emit: Emit = None) -> SceneResult:
        last_error: Optional[Exception] = None
        for engine in self.engines:
            _emit(emit, {"type": "engine", "engine": engine.name})
            try:
                if getattr(engine, "streams", False):
                    result = await getattr(engine, method)(*args, emit=emit)
                else:
                    result = await getattr(engine, method)(*args)
                result.engine = engine.name
                if method != "ending":
                    _finish_choices(result, args[0], len(args[1]) + 1 if len(args) > 1 else 1)
                return result
            except Exception as e:
                print(f"[동화 엔진] {engine.name}.{method} 실패 → 다음 엔진 ({type(e).__name__}: {e})", flush=True)
                _emit(emit, {"type": "reset"})
                last_error = e
        raise StoryEngineError("모든 동화 엔진이 실패했어요.") from last_error

    async def opening(self, setup: StorySetup, emit: Emit = None) -> SceneResult:
        return await self._run("opening", setup, emit=emit)

    async def next_scene(self, setup: StorySetup, scenes: list[str], choice: str, emit: Emit = None) -> SceneResult:
        return await self._run("next_scene", setup, scenes, choice, emit=emit)

    async def ending(self, setup: StorySetup, scenes: list[str], choice: Optional[str] = None, emit: Emit = None) -> SceneResult:
        return await self._run("ending", setup, scenes, choice, emit=emit)


def build_story_engine(model) -> ChainStoryEngine:
    engines: list[StoryEngine] = []
    if colab_client.colab_enabled():
        engines.append(RemoteStoryEngine(colab_client.colab_url(), title_model=model))
    engines.append(GeminiStoryEngine(model))
    engines.append(TemplateStoryEngine())
    return ChainStoryEngine(engines)
